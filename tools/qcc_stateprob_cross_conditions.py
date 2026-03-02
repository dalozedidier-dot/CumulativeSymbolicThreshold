#!/usr/bin/env python3
"""
QCC StateProb Cross-Conditions pipeline.

Produces:
- global inventory + recommendations over dataset
- filtered cross-conditions tables/figures comparing Ccl vs axis by shots
- t* per shots + bootstrap
- contracts + manifest sha256

Important:
- Non-interpretive: no verdicts, only metrics + summaries.
- Robust to dataset as .zip or extracted directory.

Output layout:
  <out_root>/runs/<timestamp>/{tables,figures,contracts,manifest.json}
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import zipfile


@dataclass(frozen=True)
class RunKey:
    algo: str
    device: str
    shots: int
    instance: int

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write_manifest(run_dir: Path) -> None:
    files: List[Dict[str, str]] = []
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(run_dir).as_posix()
            files.append({"path": rel, "sha256": sha256_file(p)})
    (run_dir / "manifest.json").write_text(json.dumps({"files": files}, indent=2), encoding="utf-8")

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())

def _open_dataset(dataset_path: Path, work_dir: Path) -> Path:
    """
    Returns a directory containing the extracted dataset tree.
    If dataset_path is a directory, returns it.
    If dataset_path is a zip, extracts to work_dir/dataset_extracted and returns that.
    """
    if dataset_path.is_dir():
        return dataset_path
    if dataset_path.is_file() and dataset_path.suffix.lower() == ".zip":
        out = work_dir / "dataset_extracted"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dataset_path) as zf:
            zf.extractall(out)
        return out
    raise SystemExit(f"dataset_path must be a directory or .zip file: {dataset_path}")

_state_prob_re = re.compile(r"STATES_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$", re.IGNORECASE)
_attr_re = re.compile(r"ATTR_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$", re.IGNORECASE)

def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.csv"):
        yield p

def _parse_states_csv(path: Path) -> pd.DataFrame:
    # Many files are headerless: bitstring,prob
    df = pd.read_csv(path, header=None)
    if df.shape[1] >= 2:
        df = df.iloc[:, :2]
        df.columns = ["bitstring", "prob"]
    else:
        raise ValueError(f"Unexpected STATES CSV format: {path}")
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce").fillna(0.0)
    return df

def _parse_attr_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize columns (strip)
    df.columns = [c.strip() for c in df.columns]
    return df

def ccl_entropy(probs: np.ndarray) -> float:
    probs = probs[probs > 0]
    if probs.size == 0:
        return float("nan")
    h = -np.sum(probs * np.log(probs))
    # normalize by log(K) where K is number of outcomes observed
    k = max(int(probs.size), 2)
    return float(h / math.log(k))

def ccl_one_minus_max(probs: np.ndarray) -> float:
    if probs.size == 0:
        return float("nan")
    return float(1.0 - np.max(probs))

def ccl_impurity(probs: np.ndarray) -> float:
    if probs.size == 0:
        return float("nan")
    return float(1.0 - np.sum(probs ** 2))

def compute_ccl(metric: str, probs: np.ndarray) -> float:
    metric = metric.lower().strip()
    if metric == "entropy":
        return ccl_entropy(probs)
    if metric in {"1-max", "one_minus_max", "oneminusmax"}:
        return ccl_one_minus_max(probs)
    if metric in {"impurity", "purity"}:
        return ccl_impurity(probs)
    raise ValueError(f"Unknown metric: {metric}")

def build_inventory(dataset_root: Path) -> Tuple[pd.DataFrame, Dict[Tuple[str,str,int], Dict[str,int]]]:
    """
    Returns inventory dataframe per (algo, device, shots) and also a dict with details.
    """
    states = {}
    attrs = {}
    for p in _iter_files(dataset_root):
        m = _state_prob_re.search(p.name)
        if m:
            key = RunKey(m.group("algo"), m.group("device"), int(m.group("shots")), int(m.group("instance")))
            states[key] = p
            continue
        m = _attr_re.search(p.name)
        if m:
            key = RunKey(m.group("algo"), m.group("device"), int(m.group("shots")), int(m.group("instance")))
            attrs[key] = p

    # Pairing
    pairs: Dict[RunKey, Tuple[Path, Path]] = {}
    for k, sp in states.items():
        ap = attrs.get(k)
        if ap is not None:
            pairs[k] = (sp, ap)

    # Aggregate
    rows = []
    by_combo: Dict[Tuple[str,str,int], Dict[str, int]] = {}
    depth_counts: Dict[Tuple[str,str,int], List[int]] = {}
    for k, (sp, ap) in pairs.items():
        combo = (k.algo, k.device, k.shots)
        by_combo.setdefault(combo, {"pairs_count": 0, "instances_count": 0})
        by_combo[combo]["pairs_count"] += 1

        # Count distinct depths within this ATTR file (often 1 row)
        try:
            df_attr = _parse_attr_csv(ap)
            depth_col = "Depth" if "Depth" in df_attr.columns else ("depth" if "depth" in df_attr.columns else None)
            depths = []
            if depth_col is not None:
                depths = [int(x) for x in pd.to_numeric(df_attr[depth_col], errors="coerce").dropna().unique().tolist()]
            depth_counts.setdefault(combo, []).extend(depths if depths else [])
        except Exception:
            depth_counts.setdefault(combo, []).extend([])

    # Instances count by unique instance per combo
    inst_seen = set()
    for k in pairs.keys():
        inst_seen.add((k.algo, k.device, k.shots, k.instance))
    inst_by_combo: Dict[Tuple[str,str,int], set] = {}
    for a,d,s,i in inst_seen:
        inst_by_combo.setdefault((a,d,s), set()).add(i)

    for combo, dct in by_combo.items():
        insts = inst_by_combo.get(combo, set())
        depths = depth_counts.get(combo, [])
        depth_distinct_total = len(set(depths)) if depths else 0
        # per-instance depth counts are not reliable without grouping, so report overall stats
        rows.append({
            "algo": combo[0],
            "device": combo[1],
            "shots": combo[2],
            "pairs_count": dct["pairs_count"],
            "instances_count": len(insts),
            "depth_distinct_total": depth_distinct_total,
        })

    inv = pd.DataFrame(rows)
    if not inv.empty:
        inv["score"] = inv["pairs_count"] + inv["instances_count"] + inv["depth_distinct_total"]
        inv = inv.sort_values(["score","pairs_count","instances_count","depth_distinct_total"], ascending=False).reset_index(drop=True)
    return inv, { (r["algo"], r["device"], int(r["shots"])): r for r in rows }

def pick_autoplan(inv: pd.DataFrame) -> Dict[str, object]:
    if inv.empty:
        raise SystemExit("No paired STATES/ATTR files found in dataset.")
    best = inv.iloc[0].to_dict()
    # plan chooses (algo, device) and includes all shots available for that pair
    algo = str(best["algo"]); device = str(best["device"])
    return {"algo": algo, "device": device, "reason": "max_score", "score": float(best.get("score", 0.0))}

def filter_pairs(dataset_root: Path, algo: Optional[str], device: Optional[str], shots: Optional[List[int]]) -> Dict[RunKey, Tuple[Path, Path]]:
    states = {}
    attrs = {}
    for p in _iter_files(dataset_root):
        m = _state_prob_re.search(p.name)
        if m:
            key = RunKey(m.group("algo"), m.group("device"), int(m.group("shots")), int(m.group("instance")))
            states[key] = p
            continue
        m = _attr_re.search(p.name)
        if m:
            key = RunKey(m.group("algo"), m.group("device"), int(m.group("shots")), int(m.group("instance")))
            attrs[key] = p

    pairs: Dict[RunKey, Tuple[Path, Path]] = {}
    for k, sp in states.items():
        ap = attrs.get(k)
        if ap is None:
            continue
        if algo and k.algo != algo:
            continue
        if device and k.device != device:
            continue
        if shots and k.shots not in shots:
            continue
        pairs[k] = (sp, ap)
    return pairs

def _parse_shots_filter(s: str) -> Optional[List[int]]:
    s = (s or "").strip()
    if not s:
        return None
    vals = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        vals.append(int(part))
    return vals or None

def _safe_savefig(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Path to dataset .zip or extracted directory")
    ap.add_argument("--out-dir", default=None, help="Preferred output root (contains runs/)")
    ap.add_argument("--out-root", default=None, help="Legacy alias for --out-dir")
    ap.add_argument("--algo", default="", help="Algo filter (empty=all)")
    ap.add_argument("--device-filter", default="", help="Device filter (empty=all)")
    ap.add_argument("--shots-filter", default="", help="Comma-separated shots filter (empty=all)")
    ap.add_argument("--metric", default="entropy", help="Ccl metric: entropy|1-max|impurity")
    ap.add_argument("--threshold", type=float, default=0.70, help="Ccl threshold for t*")
    ap.add_argument("--bootstrap-samples", type=int, default=500, help="Bootstrap samples")
    ap.add_argument("--auto-plan", action="store_true", help="Auto-select best (algo,device) and include all shots")
    ap.add_argument("--no-auto-plan", dest="auto_plan", action="store_false")
    ap.set_defaults(auto_plan=False)
    args = ap.parse_args()

    out_root = args.out_dir or args.out_root
    if not out_root:
        raise SystemExit("Either --out-dir or --out-root must be provided.")
    out_root = Path(out_root)
    _ensure_dir(out_root)

    run_dir = out_root / "runs" / _timestamp()
    _ensure_dir(run_dir / "tables")
    _ensure_dir(run_dir / "figures")
    _ensure_dir(run_dir / "contracts")
    work_dir = run_dir / "_work"
    _ensure_dir(work_dir)

    dataset_path = Path(args.dataset)
    dataset_root = _open_dataset(dataset_path, work_dir)

    inv_df, _ = build_inventory(dataset_root)

    # Write inventory + recommendations (global)
    inv_path = run_dir / "tables" / "inventory.csv"
    inv_df.to_csv(inv_path, index=False)

    topk = inv_df.head(10).to_dict(orient="records") if not inv_df.empty else []
    rec = {"topk": topk, "n_combinations": int(len(inv_df))}
    (run_dir / "tables" / "recommendations.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")

    selected_plan = {"auto_plan": bool(args.auto_plan)}
    algo = args.algo.strip() or None
    device = args.device_filter.strip() or None
    shots = _parse_shots_filter(args.shots_filter)

    if args.auto_plan:
        plan = pick_autoplan(inv_df)
        selected_plan.update(plan)
        algo = plan["algo"]
        device = plan["device"]
        # include all shots for selected (algo,device)
        shots = sorted(inv_df[(inv_df["algo"]==algo) & (inv_df["device"]==device)]["shots"].astype(int).unique().tolist())
        selected_plan["shots"] = shots

    (run_dir / "tables" / "selected_plan.json").write_text(json.dumps(selected_plan, indent=2), encoding="utf-8")

    pairs = filter_pairs(dataset_root, algo, device, shots)

    # Build points
    points_rows = []
    for k, (sp, ap) in pairs.items():
        try:
            df_states = _parse_states_csv(sp)
            df_attr = _parse_attr_csv(ap)
            depth_col = "Depth" if "Depth" in df_attr.columns else ("depth" if "depth" in df_attr.columns else None)
            depth = None
            if depth_col is not None and len(df_attr) > 0:
                depth = pd.to_numeric(df_attr.iloc[0][depth_col], errors="coerce")
                depth = int(depth) if not pd.isna(depth) else None
            probs = df_states["prob"].to_numpy(dtype=float)
            ccl = compute_ccl(args.metric, probs)
            points_rows.append({
                "algo": k.algo,
                "device": k.device,
                "shots": k.shots,
                "instance": k.instance,
                "axis": depth,
                "ccl": ccl,
            })
        except Exception:
            continue

    df_points = pd.DataFrame(points_rows)
    df_points.to_csv(run_dir / "tables" / "ccl_points.csv", index=False)

    # Aggregate by shots & axis
    if not df_points.empty:
        df_agg = (
            df_points.dropna(subset=["axis","ccl"])
            .groupby(["shots","axis"], as_index=False)
            .agg(ccl_mean=("ccl","mean"), ccl_std=("ccl","std"), n=("ccl","count"))
            .sort_values(["shots","axis"])
        )
    else:
        df_agg = pd.DataFrame(columns=["shots","axis","ccl_mean","ccl_std","n"])
    df_agg.to_csv(run_dir / "tables" / "ccl_by_shots.csv", index=False)

    # t* per shots: first axis where ccl_mean >= threshold
    tstar_rows = []
    for shots_val, grp in df_agg.groupby("shots"):
        grp2 = grp.sort_values("axis")
        hit = grp2[grp2["ccl_mean"] >= float(args.threshold)]
        if len(hit) > 0:
            tstar = int(hit.iloc[0]["axis"])
            c_at = float(hit.iloc[0]["ccl_mean"])
        else:
            tstar = None
            c_at = float("nan")
        tstar_rows.append({"shots": int(shots_val), "tstar": tstar, "ccl_at_tstar": c_at, "threshold": float(args.threshold)})
    df_tstar = pd.DataFrame(tstar_rows)
    df_tstar.to_csv(run_dir / "tables" / "tstar_by_shots.csv", index=False)

    # Bootstrap t* by shots: resample instances within each (shots, axis)
    bs_rows = []
    rng = np.random.default_rng(12345)
    for shots_val, sub in df_points.dropna(subset=["axis","ccl"]).groupby("shots"):
        # pool by instance
        instances = sub["instance"].unique().tolist()
        if not instances:
            continue
        axes = sorted(sub["axis"].dropna().unique().astype(int).tolist())
        for b in range(int(args.bootstrap_samples)):
            sample_insts = rng.choice(instances, size=len(instances), replace=True)
            tmp = sub[sub["instance"].isin(sample_insts)]
            if tmp.empty:
                bs_rows.append({"shots": int(shots_val), "bootstrap_i": b, "tstar": None})
                continue
            agg = tmp.groupby("axis", as_index=False)["ccl"].mean().sort_values("axis")
            hit = agg[agg["ccl"] >= float(args.threshold)]
            tstar = int(hit.iloc[0]["axis"]) if len(hit) > 0 else None
            bs_rows.append({"shots": int(shots_val), "bootstrap_i": b, "tstar": tstar})
    df_bs = pd.DataFrame(bs_rows)
    df_bs.to_csv(run_dir / "tables" / "bootstrap_tstar_by_shots.csv", index=False)

    # Summary
    summary = {
        "dataset": str(dataset_path),
        "metric": args.metric,
        "threshold": float(args.threshold),
        "bootstrap_samples": int(args.bootstrap_samples),
        "auto_plan": bool(args.auto_plan),
        "filters": {"algo": algo or "", "device": device or "", "shots": shots or []},
        "n_pairs": int(len(pairs)),
        "n_points": int(len(df_points)),
    }
    (run_dir / "tables" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Figures (always create, even placeholder)
    fig1 = run_dir / "figures" / "ccl_vs_axis_by_shots.png"
    plt.figure()
    if not df_agg.empty:
        for shots_val, grp in df_agg.groupby("shots"):
            plt.plot(grp["axis"].to_numpy(), grp["ccl_mean"].to_numpy(), label=f"shots={int(shots_val)}")
        plt.axhline(float(args.threshold), linestyle="--", linewidth=1.0)
        plt.xlabel("Depth")
        plt.ylabel(f"Ccl ({args.metric})")
        plt.legend()
        plt.title("Ccl vs Depth by shots")
    else:
        plt.text(0.5, 0.5, "No data to plot", ha="center", va="center")
        plt.axis("off")
    _safe_savefig(fig1)

    fig2 = run_dir / "figures" / "tstar_hist.png"
    plt.figure()
    if not df_bs.empty and df_bs["tstar"].notna().any():
        vals = df_bs["tstar"].dropna().astype(int).to_numpy()
        plt.hist(vals, bins=min(20, max(1, len(np.unique(vals)))))
        plt.xlabel("t*")
        plt.ylabel("count")
        plt.title("Bootstrap t* distribution (all shots pooled)")
    else:
        plt.text(0.5, 0.5, "No t* found", ha="center", va="center")
        plt.axis("off")
    _safe_savefig(fig2)

    # Contracts
    mapping = {
        "ccl_metric": args.metric,
        "axis": "Depth",
        "threshold": float(args.threshold),
        "auto_plan": bool(args.auto_plan),
        "notes": "Non-interpretive cross-conditions over (algo, device) comparing shots.",
    }
    (run_dir / "contracts" / "mapping_cross_conditions.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")

    # Manifest
    write_manifest(run_dir)

    # Print where run is
    print(f"Wrote run: {run_dir.as_posix()}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
