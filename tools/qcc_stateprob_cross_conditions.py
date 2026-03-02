#!/usr/bin/env python3
"""
QCC StateProb Cross-Conditions (Ccl vs axis by shots) with optional auto-plan.

This version is robustness-focused:
- Always writes tables/summary.json
- Always writes figures/ccl_vs_axis_by_shots.png and figures/tstar_hist.png
  (even if empty / no t* found), so CI checks stay mechanical.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# -----------------------------
# Helpers
# -----------------------------
def _now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, float) and math.isnan(x):
            return None
        s = str(x).strip()
        if s == "" or s.lower() == "nan":
            return None
        return float(s)
    except Exception:
        return None

def _read_states_csv(path: Path) -> pd.DataFrame:
    """
    STATES_*.csv in this dataset often comes without a header:
      bitstring,prob
    but some variants may include headers.
    We'll detect and normalize to columns: bitstring, prob
    """
    # Try with header inference
    df = pd.read_csv(path, header=None)
    if df.shape[1] < 2:
        raise ValueError(f"STATES file malformed (need >=2 cols): {path}")
    # If first row looks like header, re-read with header=0
    first0 = str(df.iloc[0,0]).lower()
    first1 = str(df.iloc[0,1]).lower()
    if "bit" in first0 and ("prob" in first1 or "p(" in first1):
        df = pd.read_csv(path)
        cols = {c.lower(): c for c in df.columns}
        bcol = cols.get("bitstring") or cols.get("state") or list(df.columns)[0]
        pcol = cols.get("prob") or cols.get("probability") or list(df.columns)[1]
        out = df[[bcol, pcol]].copy()
        out.columns = ["bitstring", "prob"]
        return out
    out = df.iloc[:, :2].copy()
    out.columns = ["bitstring", "prob"]
    return out

def _read_attr_csv(path: Path) -> pd.DataFrame:
    """
    ATTR_*.csv typically has headers but may contain spaces.
    We'll read and normalize key columns:
      Depth, Runtime (if exists)
    """
    df = pd.read_csv(path)
    # Normalize columns stripping spaces
    df.columns = [str(c).strip() for c in df.columns]
    return df

def _ccl_from_probs(probs: np.ndarray, metric: str) -> float:
    probs = probs.astype(float)
    probs = probs[probs > 0]
    if probs.size == 0:
        return float("nan")
    metric = metric.lower().strip()
    if metric == "entropy":
        h = -(probs * np.log(probs)).sum()
        # normalize by log(K)
        k = int(probs.size)
        denom = math.log(k) if k > 1 else 1.0
        return float(h / denom) if denom > 0 else 0.0
    if metric in ("impurity", "gini"):
        return float(1.0 - (probs**2).sum())
    if metric in ("1-max", "one_minus_max", "one-minus-max"):
        return float(1.0 - probs.max())
    raise ValueError(f"Unknown ccl metric: {metric}")

@dataclass(frozen=True)
class RunKey:
    algo: str
    device: str
    shots: int
    instance: int


def _parse_name_bits(fname: str) -> Tuple[str, str, int, int]:
    """
    Parse filenames like:
      STATES_ibmqx2_BV_0_8192.csv
      ATTR_ibmqx2_BV_0_8192.csv
    Returns (device, algo, instance, shots)
    """
    m = re.search(r'_(?P<device>[^_]+)_(?P<algo>[A-Za-z0-9]+)_(?P<inst>\d+)_(?P<shots>\d+)\.csv$', fname)
    if not m:
        raise ValueError(f"Unrecognized filename pattern: {fname}")
    device = m.group("device")
    algo = m.group("algo")
    inst = int(m.group("inst"))
    shots = int(m.group("shots"))
    return device, algo, inst, shots


def _collect_pairs(root: Path) -> List[Tuple[RunKey, Path, Path]]:
    """
    Find matching STATES and ATTR files.
    Returns list of (RunKey, states_path, attr_path).
    """
    states_files = {}
    attr_files = {}
    for p in root.rglob("*.csv"):
        name = p.name
        if name.startswith("STATES_"):
            try:
                device, algo, inst, shots = _parse_name_bits(name)
            except Exception:
                continue
            states_files[(device, algo, inst, shots)] = p
        elif name.startswith("ATTR_"):
            try:
                device, algo, inst, shots = _parse_name_bits(name)
            except Exception:
                continue
            attr_files[(device, algo, inst, shots)] = p

    pairs = []
    for k, sp in states_files.items():
        ap = attr_files.get(k)
        if ap is None:
            continue
        device, algo, inst, shots = k
        pairs.append((RunKey(algo=algo, device=device, shots=shots, instance=inst), sp, ap))
    return pairs


def _write_inventory_and_recs(pairs: List[Tuple[RunKey, Path, Path]], out_tables: Path, topk: int = 10) -> Tuple[pd.DataFrame, dict]:
    rows = []
    # Compute depth distinct per instance too
    # Build a map to depths
    depth_map: Dict[Tuple[str,str,int], Dict[int, set]] = {}
    for rk, sp, ap in pairs:
        try:
            adf = _read_attr_csv(ap)
        except Exception:
            continue
        depth_col = None
        for c in adf.columns:
            if c.lower() == "depth":
                depth_col = c
                break
        if depth_col is None:
            continue
        depths = set(int(x) for x in pd.to_numeric(adf[depth_col], errors="coerce").dropna().unique())
        key = (rk.algo, rk.device, rk.shots)
        depth_map.setdefault(key, {}).setdefault(rk.instance, set()).update(depths)

    # Aggregate
    combos = {}
    for rk, _, _ in pairs:
        combos.setdefault((rk.algo, rk.device, rk.shots), set()).add(rk.instance)

    for (algo, device, shots), inst_set in combos.items():
        inst_count = len(inst_set)
        # pair count equals inst_count if 1 pair per instance; keep generic:
        pair_count = sum(1 for rk, _, _ in pairs if rk.algo==algo and rk.device==device and rk.shots==shots)
        dm = depth_map.get((algo, device, shots), {})
        depth_total = len(set().union(*dm.values())) if dm else 0
        per_inst = [len(dm.get(i,set())) for i in inst_set] if dm else [0]*inst_count
        dmin = min(per_inst) if per_inst else 0
        dmed = float(np.median(per_inst)) if per_inst else 0.0
        dmax = max(per_inst) if per_inst else 0
        score = float(pair_count + inst_count + depth_total)
        rows.append({
            "algo": algo,
            "device": device,
            "shots": shots,
            "pairs_count": pair_count,
            "instances_count": inst_count,
            "depth_distinct_total": depth_total,
            "depth_distinct_min": dmin,
            "depth_distinct_median": dmed,
            "depth_distinct_max": dmax,
            "score": score,
        })

    inv = pd.DataFrame(rows)
    if inv.empty:
        inv = pd.DataFrame(columns=[
            "algo","device","shots","pairs_count","instances_count","depth_distinct_total",
            "depth_distinct_min","depth_distinct_median","depth_distinct_max","score"
        ])
    inv = inv.sort_values(["score","pairs_count","depth_distinct_total","instances_count"], ascending=False).reset_index(drop=True)

    _ensure_dir(out_tables)
    inv.to_csv(out_tables / "inventory.csv", index=False)

    top = inv.head(topk).to_dict(orient="records")
    rec = {"topk": top, "scoring": "score = pairs_count + instances_count + depth_distinct_total"}
    (out_tables / "recommendations.json").write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
    return inv, rec


def _select_auto_plan(inv: pd.DataFrame) -> Tuple[str, str]:
    if inv.empty:
        raise RuntimeError("inventory is empty; cannot auto-plan")
    # Select best (algo, device) by aggregating score across shots
    agg = inv.groupby(["algo","device"]).agg(
        score_sum=("score","sum"),
        shots_count=("shots","nunique"),
        pairs_sum=("pairs_count","sum"),
        depth_sum=("depth_distinct_total","sum"),
        inst_sum=("instances_count","sum"),
    ).reset_index()
    agg = agg.sort_values(["score_sum","pairs_sum","depth_sum","inst_sum","shots_count"], ascending=False).reset_index(drop=True)
    best = agg.iloc[0]
    return str(best["algo"]), str(best["device"])


def _filter_pairs(pairs, algo: Optional[str], device: Optional[str], shots_list: Optional[List[int]]):
    out=[]
    for rk, sp, ap in pairs:
        if algo and rk.algo != algo:
            continue
        if device and rk.device != device:
            continue
        if shots_list and rk.shots not in shots_list:
            continue
        out.append((rk, sp, ap))
    return out


def _compute_points(pairs: List[Tuple[RunKey, Path, Path]], metric: str, t_axis: str) -> pd.DataFrame:
    rows=[]
    axis_key = t_axis.lower().strip()
    for rk, sp, ap in pairs:
        sdf = _read_states_csv(sp)
        adf = _read_attr_csv(ap)

        # axis value(s)
        # Expect one row in ATTR, but support multiple; take first non-null
        axis_col = None
        for c in adf.columns:
            if c.lower() == axis_key:
                axis_col = c
                break
        if axis_col is None:
            # common names
            for c in adf.columns:
                if axis_key == "depth" and c.lower().startswith("depth"):
                    axis_col = c; break
                if axis_key == "runtime" and "runtime" in c.lower():
                    axis_col = c; break
        if axis_col is None:
            continue
        axis_vals = pd.to_numeric(adf[axis_col], errors="coerce").dropna().tolist()
        if not axis_vals:
            continue
        axis_val = float(axis_vals[0])

        probs = pd.to_numeric(sdf["prob"], errors="coerce").dropna().to_numpy()
        ccl = _ccl_from_probs(probs, metric=metric)

        rows.append({
            "algo": rk.algo,
            "device": rk.device,
            "shots": rk.shots,
            "instance": rk.instance,
            "axis": axis_val,
            "ccl": ccl,
            "states_file": str(sp),
            "attr_file": str(ap),
        })
    df = pd.DataFrame(rows)
    return df


def _first_crossing(axis: np.ndarray, y: np.ndarray, threshold: float) -> Tuple[Optional[float], Optional[float]]:
    """Return (t*, y(t*)) where y crosses above threshold for the first time, after sorting by axis."""
    if axis.size == 0:
        return None, None
    order = np.argsort(axis)
    axis = axis[order]
    y = y[order]
    for a, v in zip(axis, y):
        if not (isinstance(v, float) and math.isnan(v)) and v >= threshold:
            return float(a), float(v)
    return None, None


def _bootstrap_tstar(points: pd.DataFrame, threshold: float, n: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows=[]
    if points.empty:
        return pd.DataFrame(columns=["shots","sample","tstar"])
    for shots, sub in points.groupby("shots"):
        vals = sub[["axis","ccl"]].dropna().to_numpy()
        if vals.shape[0] == 0:
            for i in range(n):
                rows.append({"shots": int(shots), "sample": i, "tstar": np.nan})
            continue
        for i in range(n):
            idx = rng.integers(0, vals.shape[0], size=vals.shape[0])
            sample = vals[idx]
            tstar, _ = _first_crossing(sample[:,0], sample[:,1], threshold)
            rows.append({"shots": int(shots), "sample": i, "tstar": (np.nan if tstar is None else tstar)})
    return pd.DataFrame(rows)


def _plot_ccl_by_shots(df: pd.DataFrame, out_png: Path, axis_name: str) -> None:
    _ensure_dir(out_png.parent)
    plt.figure()
    if df.empty:
        plt.text(0.5, 0.5, "No data to plot", ha="center", va="center")
        plt.axis("off")
        plt.savefig(out_png, dpi=160, bbox_inches="tight")
        plt.close()
        return

    for shots, sub in df.groupby("shots"):
        sub = sub.sort_values("axis")
        plt.plot(sub["axis"], sub["ccl_mean"], marker="o", label=str(shots))
    plt.xlabel(axis_name)
    plt.ylabel("Ccl (metric mean)")
    plt.title("Ccl vs axis by shots")
    plt.legend(title="shots", loc="best")
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()


def _plot_tstar_hist(df: pd.DataFrame, out_png: Path) -> None:
    _ensure_dir(out_png.parent)
    plt.figure()
    if df.empty or df["tstar"].dropna().empty:
        plt.text(0.5, 0.5, "No t* found", ha="center", va="center")
        plt.axis("off")
        plt.savefig(out_png, dpi=160, bbox_inches="tight")
        plt.close()
        return
    plt.hist(df["tstar"].dropna().to_numpy(), bins=15)
    plt.xlabel("t* (axis)")
    plt.ylabel("count")
    plt.title("Bootstrap t* distribution (pooled)")
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-path", required=True, help="Path to dataset zip OR extracted folder")
    ap.add_argument("--out-dir", required=False, help="Output run directory (preferred)")
    ap.add_argument("--out-root", required=False, help="Legacy alias for out dir")
    ap.add_argument("--metric", default="entropy", choices=["entropy","impurity","1-max"])
    ap.add_argument("--t-axis", default="Depth")
    ap.add_argument("--threshold", type=float, default=0.70)
    ap.add_argument("--bootstrap-samples", type=int, default=500)

    ap.add_argument("--algo", default="", help="Filter algo (empty=all)")
    ap.add_argument("--device-filter", default="", help="Filter device (empty=all)")
    ap.add_argument("--shots-filter", default="", help="Comma-separated list of shots to include (empty=all)")

    ap.add_argument("--auto-plan", action="store_true", help="Auto-select best (algo,device) across dataset")
    ap.add_argument("--no-auto-plan", action="store_true", help="Disable auto-plan even if provided")

    args = ap.parse_args()

    out_dir = args.out_dir or args.out_root
    if not out_dir:
        raise SystemExit("Need --out-dir (or legacy --out-root)")
    out_dir = Path(out_dir)

    dataset_path = Path(args.dataset_path)
    if not dataset_path.exists():
        raise SystemExit(f"dataset path not found: {dataset_path}")

    # Prepare working dataset root
    work_root = out_dir / "_dataset"
    if work_root.exists():
        shutil.rmtree(work_root)
    _ensure_dir(work_root)

    if dataset_path.is_dir():
        # use directory directly (copy minimal structure for manifestability)
        shutil.copytree(dataset_path, work_root / dataset_path.name, dirs_exist_ok=True)
        data_root = work_root / dataset_path.name
    else:
        # zip
        with zipfile.ZipFile(dataset_path, "r") as z:
            z.extractall(work_root)
        # If zip contains a single top folder, use it; else use work_root
        children = [p for p in work_root.iterdir()]
        if len(children) == 1 and children[0].is_dir():
            data_root = children[0]
        else:
            data_root = work_root

    pairs = _collect_pairs(data_root)

    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    contracts_dir = out_dir / "contracts"
    _ensure_dir(tables_dir); _ensure_dir(figs_dir); _ensure_dir(contracts_dir)

    inv, rec = _write_inventory_and_recs(pairs, tables_dir, topk=10)

    # Decide plan
    auto_plan = bool(args.auto_plan) and not bool(args.no_auto_plan)
    selected = {
        "auto_plan": auto_plan,
        "algo": None,
        "device": None,
        "shots_included": None,
        "filters": {
            "algo_arg": args.algo,
            "device_filter_arg": args.device_filter,
            "shots_filter_arg": args.shots_filter,
        },
    }

    algo = args.algo.strip() or None
    device = args.device_filter.strip() or None
    shots_list = None
    if args.shots_filter.strip():
        shots_list = [int(x.strip()) for x in args.shots_filter.split(",") if x.strip()]

    if auto_plan:
        algo, device = _select_auto_plan(inv)
        selected["algo"] = algo
        selected["device"] = device

    # If still None -> all
    filtered_pairs = _filter_pairs(pairs, algo=algo, device=device, shots_list=shots_list)
    points = _compute_points(filtered_pairs, metric=args.metric, t_axis=args.t_axis)
    points.to_csv(tables_dir / "ccl_points.csv", index=False)

    # Aggregate by (shots, axis)
    if points.empty:
        by_shots = pd.DataFrame(columns=["shots","axis","ccl_mean","n_points"])
    else:
        by_shots = points.groupby(["shots","axis"], as_index=False).agg(
            ccl_mean=("ccl","mean"),
            n_points=("ccl","size"),
        ).sort_values(["shots","axis"]).reset_index(drop=True)
    by_shots.to_csv(tables_dir / "ccl_by_shots.csv", index=False)

    # Compute t* per shots
    tstar_rows=[]
    for shots, sub in by_shots.groupby("shots"):
        tstar, ccl_at = _first_crossing(sub["axis"].to_numpy(), sub["ccl_mean"].to_numpy(), args.threshold)
        tstar_rows.append({"shots": int(shots), "tstar": (np.nan if tstar is None else tstar), "ccl_at_tstar": (np.nan if ccl_at is None else ccl_at)})
    tstar_df = pd.DataFrame(tstar_rows) if tstar_rows else pd.DataFrame(columns=["shots","tstar","ccl_at_tstar"])
    tstar_df.to_csv(tables_dir / "tstar_by_shots.csv", index=False)

    boot = _bootstrap_tstar(by_shots.rename(columns={"ccl_mean":"ccl"}), threshold=args.threshold, n=args.bootstrap_samples, seed=7)
    boot.to_csv(tables_dir / "bootstrap_tstar_by_shots.csv", index=False)

    # Always generate figures required by checks
    _plot_ccl_by_shots(by_shots, figs_dir / "ccl_vs_axis_by_shots.png", axis_name=args.t_axis)
    _plot_tstar_hist(boot, figs_dir / "tstar_hist.png")

    # contracts
    mapping = {
        "dataset_path": str(dataset_path),
        "metric": args.metric,
        "t_axis": args.t_axis,
        "threshold": args.threshold,
        "bootstrap_samples": args.bootstrap_samples,
        "notes": "Ccl computed mechanically from state probability distributions; cross-conditions compares shots.",
    }
    (contracts_dir / "mapping_cross_conditions.json").write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")
    (tables_dir / "selected_plan.json").write_text(json.dumps(selected, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "run_kind": "qcc_stateprob_cross_conditions",
        "timestamp_utc": _now_stamp(),
        "dataset_root_used": str(data_root),
        "filters_effective": {"algo": algo or "", "device": device or "", "shots_list": shots_list or []},
        "counts": {
            "pairs_total": len(pairs),
            "pairs_used": len(filtered_pairs),
            "points_used": int(points.shape[0]),
            "shots_groups": int(by_shots["shots"].nunique()) if not by_shots.empty else 0,
        },
    }
    (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    # manifest
    # reuse existing make_manifest.py if present in repo; else inline
    try:
        from tools.make_manifest import write_manifest  # type: ignore
        write_manifest(out_dir, out_dir / "manifest.json")
    except Exception:
        import hashlib
        entries=[]
        for p in out_dir.rglob("*"):
            if p.is_file():
                h=hashlib.sha256()
                with open(p,"rb") as f:
                    for chunk in iter(lambda: f.read(1024*1024), b""):
                        h.update(chunk)
                entries.append({"path": str(p.relative_to(out_dir)).replace("\\","/"), "sha256": h.hexdigest(), "bytes": p.stat().st_size})
        (out_dir / "manifest.json").write_text(json.dumps({"files": sorted(entries, key=lambda x: x["path"])}, indent=2), encoding="utf-8")

    print(f"Wrote run: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
