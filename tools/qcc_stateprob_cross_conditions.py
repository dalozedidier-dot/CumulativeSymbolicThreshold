#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Filename patterns (seen in 04-09-2020 dataset)
# STATES_<device>_<algo>_<instance>_<shots>.csv
# ATTR_<device>_<algo>_<instance>_<shots>.csv
STATES_RE = re.compile(r"STATES_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$", re.IGNORECASE)
ATTR_RE   = re.compile(r"ATTR_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$", re.IGNORECASE)

@dataclass(frozen=True)
class RunKey:
    algo: str
    device: str
    shots: int

def _read_states_csv(path: Path) -> pd.DataFrame:
    # Try with header first; if not, use header=None
    df = None
    try:
        df = pd.read_csv(path)
        if df.shape[1] < 2:
            raise ValueError("Too few columns")
    except Exception:
        df = pd.read_csv(path, header=None)
    # Normalize columns
    cols = [c.strip() if isinstance(c, str) else c for c in df.columns]
    df.columns = cols
    # Guess probability column
    if "Probability" in df.columns:
        prob_col = "Probability"
    elif "probability" in df.columns:
        prob_col = "probability"
    else:
        prob_col = df.columns[-1]
    df = df[[df.columns[0], prob_col]].copy()
    df.columns = ["bitstring", "p"]
    df["p"] = pd.to_numeric(df["p"], errors="coerce").fillna(0.0)
    s = float(df["p"].sum())
    if s > 0:
        df["p"] = df["p"] / s
    return df

def _read_attr_depth(path: Path) -> Optional[float]:
    try:
        df = pd.read_csv(path)
    except Exception:
        df = pd.read_csv(path, header=None)
    # Try common column names
    for cand in ["Depth", "depth", "Circuit Depth", "circuit_depth"]:
        if cand in df.columns:
            v = pd.to_numeric(df[cand], errors="coerce").dropna()
            if len(v) > 0:
                return float(v.iloc[0])
    # fallback: search any column containing 'depth'
    for c in df.columns:
        if isinstance(c, str) and "depth" in c.lower():
            v = pd.to_numeric(df[c], errors="coerce").dropna()
            if len(v) > 0:
                return float(v.iloc[0])
    return None

def ccl_from_probs(p: np.ndarray, metric: str) -> float:
    p = np.asarray(p, dtype=float)
    p = p[p > 0]
    if len(p) == 0:
        return float("nan")
    metric = metric.lower()
    if metric == "entropy":
        h = -float(np.sum(p * np.log(p)))
        # normalize by log(|support|)
        hmax = float(np.log(len(p))) if len(p) > 1 else 1.0
        return h / hmax if hmax > 0 else 0.0
    if metric == "impurity":
        return 1.0 - float(np.sum(p**2))
    if metric in ("1-max", "one_minus_max", "oneminusmax"):
        return 1.0 - float(np.max(p))
    raise ValueError(f"Unknown metric: {metric}")

def discover_pairs(root: Path) -> List[dict]:
    states = {}
    attrs = {}
    for p in root.rglob("*.csv"):
        m = STATES_RE.search(p.name)
        if m:
            d = m.groupdict()
            key = (d["algo"], d["device"], int(d["instance"]), int(d["shots"]))
            states[key] = p
            continue
        m = ATTR_RE.search(p.name)
        if m:
            d = m.groupdict()
            key = (d["algo"], d["device"], int(d["instance"]), int(d["shots"]))
            attrs[key] = p
            continue

    pairs = []
    for k, s_path in states.items():
        a_path = attrs.get(k)
        if a_path is None:
            continue
        algo, device, instance, shots = k
        pairs.append({
            "algo": algo,
            "device": device,
            "instance": int(instance),
            "shots": int(shots),
            "states_csv": s_path,
            "attr_csv": a_path,
        })
    return pairs

def build_inventory(pairs: List[dict]) -> pd.DataFrame:
    rows = []
    grp = {}
    for p in pairs:
        rk = RunKey(algo=p["algo"], device=p["device"], shots=p["shots"])
        grp.setdefault(rk, []).append(p)
    for rk, plist in grp.items():
        inst = sorted({p["instance"] for p in plist})
        depths = []
        inst_to_depths = {}
        for p in plist:
            d = _read_attr_depth(p["attr_csv"])
            if d is None or math.isnan(d):
                continue
            depths.append(d)
            inst_to_depths.setdefault(p["instance"], set()).add(d)
        depth_total = len(set(depths))
        per_inst = [len(v) for v in inst_to_depths.values()] or [0]
        score = (len(plist) * 10) + (len(inst) * 5) + depth_total
        rows.append({
            "algo": rk.algo,
            "device": rk.device,
            "shots": rk.shots,
            "pairs_count": len(plist),
            "instances_count": len(inst),
            "depth_distinct_total": depth_total,
            "depth_distinct_min": int(np.min(per_inst)),
            "depth_distinct_median": float(np.median(per_inst)),
            "depth_distinct_max": int(np.max(per_inst)),
            "score": score,
        })
    df = pd.DataFrame(rows).sort_values(["score","pairs_count","instances_count","depth_distinct_total"], ascending=False)
    return df

def choose_plan(inventory: pd.DataFrame, algo: str, device_filter: str) -> Tuple[str,str]:
    df = inventory.copy()
    if algo:
        df = df[df["algo"].str.upper() == algo.upper()]
    if device_filter:
        df = df[df["device"].str.contains(device_filter, case=False, na=False)]
    if df.empty:
        raise RuntimeError("No combinations available for given filters.")
    top = df.iloc[0]
    return str(top["algo"]), str(top["device"])

def ensure_png(path: Path, title: str, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 4))
    plt.title(title)
    plt.axis("off")
    plt.text(0.5, 0.5, message, ha="center", va="center")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", "--dataset-path", dest="dataset", required=True, help="Path to dataset zip OR extracted directory")
    ap.add_argument("--out-root", "--out-dir", dest="out_root", required=True, help="Output root directory (will create runs/<timestamp>/...)")
    ap.add_argument("--algo", default="", help="Optional algo filter (e.g. SIMON)")
    ap.add_argument("--device-filter", default="", help="Optional substring filter for device")
    ap.add_argument("--shots-filter", default="", help="Optional shots filter: comma-separated ints, or empty for all")
    ap.add_argument("--metric", default="entropy", choices=["entropy","impurity","1-max"], help="Ccl metric")
    ap.add_argument("--threshold", type=float, default=0.70, help="Ccl threshold for t*")
    ap.add_argument("--bootstrap-samples", type=int, default=500)
    ap.add_argument("--auto-plan", dest="auto_plan", action="store_true")
    ap.add_argument("--no-auto-plan", dest="auto_plan", action="store_false")
    ap.set_defaults(auto_plan=True)
    args = ap.parse_args()

    out_root = Path(args.out_root)
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / "runs" / run_ts
    (run_dir / "tables").mkdir(parents=True, exist_ok=True)
    (run_dir / "figures").mkdir(parents=True, exist_ok=True)
    (run_dir / "contracts").mkdir(parents=True, exist_ok=True)

    # Materialize dataset
    dataset_path = Path(args.dataset)
    tmpdir = None
    if dataset_path.is_dir():
        data_root = dataset_path
    else:
        tmpdir = tempfile.mkdtemp(prefix="qcc_stateprob_")
        data_root = Path(tmpdir)
        import zipfile
        with zipfile.ZipFile(dataset_path) as zf:
            zf.extractall(data_root)

    pairs = discover_pairs(data_root)
    if len(pairs) == 0:
        ensure_png(run_dir/"figures"/"ccl_vs_axis_by_shots.png","Ccl vs Axis","No STATES/ATTR pairs found.")
        ensure_png(run_dir/"figures"/"tstar_hist.png","t* histogram","No data.")
        # minimal outputs + manifest
        inv = pd.DataFrame([])
        inv.to_csv(run_dir/"tables"/"inventory.csv", index=False)
        (run_dir/"tables"/"recommendations.json").write_text(json.dumps({"topk":[]}, indent=2), encoding="utf-8")
        (run_dir/"tables"/"selected_plan.json").write_text(json.dumps({"selected":None,"reason":"no_pairs"}, indent=2), encoding="utf-8")
        (run_dir/"tables"/"summary.json").write_text(json.dumps({"n_pairs":0}, indent=2), encoding="utf-8")
        from tools.make_manifest import build_manifest
        mani = build_manifest(run_dir, exclude_names=set())
        (run_dir/"manifest.json").write_text(json.dumps(mani, indent=2, sort_keys=True), encoding="utf-8")
        return 0

    inventory = build_inventory(pairs)
    inventory.to_csv(run_dir/"tables"/"inventory.csv", index=False)
    # recommendations top10
    topk = inventory.head(10).to_dict(orient="records")
    (run_dir/"tables"/"recommendations.json").write_text(json.dumps({"topk": topk}, indent=2), encoding="utf-8")

    # Decide plan
    if args.auto_plan:
        sel_algo, sel_device = choose_plan(inventory, algo=args.algo, device_filter=args.device_filter)
        plan_reason = "auto_plan_best_score"
    else:
        sel_algo = args.algo or ""
        sel_device = args.device_filter or ""
        if not sel_algo or not sel_device:
            # if manual but missing, fall back to top
            sel_algo, sel_device = choose_plan(inventory, algo=args.algo, device_filter=args.device_filter)
            plan_reason = "manual_incomplete_fallback_to_best"
        else:
            plan_reason = "manual"
    plan = {"algo": sel_algo, "device": sel_device, "auto_plan": bool(args.auto_plan), "reason": plan_reason}
    (run_dir/"tables"/"selected_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    # Apply filters
    shots_set = None
    if args.shots_filter.strip():
        shots_set = {int(x.strip()) for x in args.shots_filter.split(",") if x.strip()}

    filt_pairs = []
    for p in pairs:
        if p["algo"].upper() != sel_algo.upper():
            continue
        if sel_device.lower() not in p["device"].lower():
            continue
        if shots_set is not None and p["shots"] not in shots_set:
            continue
        filt_pairs.append(p)

    # Build points
    point_rows = []
    for p in filt_pairs:
        depth = _read_attr_depth(p["attr_csv"])
        if depth is None or math.isnan(depth):
            continue
        dfp = _read_states_csv(p["states_csv"])
        ccl = ccl_from_probs(dfp["p"].to_numpy(), metric=args.metric)
        point_rows.append({
            "algo": p["algo"],
            "device": p["device"],
            "instance": p["instance"],
            "shots": p["shots"],
            "depth": float(depth),
            "ccl": float(ccl),
            "states_csv": str(p["states_csv"]),
            "attr_csv": str(p["attr_csv"]),
        })

    points = pd.DataFrame(point_rows)
    points.to_csv(run_dir/"tables"/"ccl_points.csv", index=False)

    # Aggregate by shots and depth
    if len(points) > 0:
        agg = points.groupby(["shots","depth"], as_index=False).agg(
            ccl_mean=("ccl","mean"),
            ccl_std=("ccl","std"),
            n=("ccl","count"),
        ).sort_values(["shots","depth"])
    else:
        agg = pd.DataFrame(columns=["shots","depth","ccl_mean","ccl_std","n"])
    agg.to_csv(run_dir/"tables"/"ccl_by_shots.csv", index=False)

    # t* per shots (first depth where mean crosses threshold)
    tstar_rows = []
    for shots, df in agg.groupby("shots"):
        df = df.sort_values("depth")
        hit = df[df["ccl_mean"] >= args.threshold]
        if len(hit) == 0:
            tstar = float("nan")
            ccl_at = float("nan")
        else:
            tstar = float(hit.iloc[0]["depth"])
            ccl_at = float(hit.iloc[0]["ccl_mean"])
        tstar_rows.append({"shots": int(shots), "tstar": tstar, "ccl_at_tstar": ccl_at, "threshold": args.threshold})
    tstar_df = pd.DataFrame(tstar_rows).sort_values("shots") if tstar_rows else pd.DataFrame(columns=["shots","tstar","ccl_at_tstar","threshold"])
    tstar_df.to_csv(run_dir/"tables"/"tstar_by_shots.csv", index=False)

    # Bootstrap t* by shots resampling instances
    boot_rows = []
    rng = np.random.default_rng(1337)
    if len(points) > 0:
        for shots, df_s in points.groupby("shots"):
            inst = sorted(df_s["instance"].unique())
            if len(inst) == 0:
                continue
            for b in range(args.bootstrap_samples):
                sample_inst = rng.choice(inst, size=len(inst), replace=True)
                df_b = df_s[df_s["instance"].isin(sample_inst)]
                agg_b = df_b.groupby("depth", as_index=False).agg(ccl_mean=("ccl","mean")).sort_values("depth")
                hit = agg_b[agg_b["ccl_mean"] >= args.threshold]
                tstar = float(hit.iloc[0]["depth"]) if len(hit) else float("nan")
                boot_rows.append({"shots": int(shots), "bootstrap_i": b, "tstar": tstar})
    boot_df = pd.DataFrame(boot_rows)
    boot_df.to_csv(run_dir/"tables"/"bootstrap_tstar_by_shots.csv", index=False)

    # Summary
    summary = {
        "selected_plan": plan,
        "metric": args.metric,
        "threshold": args.threshold,
        "bootstrap_samples": args.bootstrap_samples,
        "n_pairs_total": len(pairs),
        "n_pairs_filtered": len(filt_pairs),
        "n_points": int(len(points)),
        "shots_values": sorted(points["shots"].unique().tolist()) if len(points) else [],
    }
    (run_dir/"tables"/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Contracts
    mapping = {
        "dataset": str(dataset_path),
        "ccl_metric": args.metric,
        "ccl_definition": {
            "entropy": "H(p)/log(|support|) with p normalized from State_Probability",
            "impurity": "1 - sum p^2",
            "1-max": "1 - max(p)",
        }[args.metric],
        "axis": "Depth from ATTR files",
        "tstar_definition": "first depth where ccl_mean >= threshold",
        "bootstrap": "resample instances with replacement per shots",
        "filters": {
            "algo": args.algo,
            "device_filter": args.device_filter,
            "shots_filter": args.shots_filter,
            "auto_plan": bool(args.auto_plan),
        }
    }
    (run_dir/"contracts"/"mapping_cross_conditions.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")

    # Figures (always)
    if len(agg) == 0:
        ensure_png(run_dir/"figures"/"ccl_vs_axis_by_shots.png","Ccl vs Depth by shots","No data to plot.")
    else:
        plt.figure(figsize=(9,5))
        for shots, df in agg.groupby("shots"):
            plt.plot(df["depth"], df["ccl_mean"], marker="o", label=f"shots={int(shots)}")
        plt.axhline(args.threshold, linestyle="--")
        plt.xlabel("Depth")
        plt.ylabel(f"Ccl ({args.metric})")
        plt.title(f"Ccl vs Depth by shots (algo={sel_algo}, device~{sel_device})")
        plt.legend()
        plt.tight_layout()
        plt.savefig(run_dir/"figures"/"ccl_vs_axis_by_shots.png", dpi=150)
        plt.close()

    if len(boot_df) == 0 or boot_df["tstar"].dropna().empty:
        ensure_png(run_dir/"figures"/"tstar_hist.png","t* histogram","No t* found.")
    else:
        plt.figure(figsize=(9,5))
        # overlay hist by shots
        for shots, df in boot_df.groupby("shots"):
            vals = df["tstar"].dropna().to_numpy()
            if len(vals) == 0:
                continue
            plt.hist(vals, bins=min(15, max(3, len(np.unique(vals)))), alpha=0.5, label=f"shots={int(shots)}")
        plt.xlabel("t* (Depth)")
        plt.ylabel("count")
        plt.title("Bootstrap distribution of t* by shots")
        plt.legend()
        plt.tight_layout()
        plt.savefig(run_dir/"figures"/"tstar_hist.png", dpi=150)
        plt.close()

    # Manifest (hash everything under run_dir except manifest itself)
    from tools.make_manifest import build_manifest
    mani = build_manifest(run_dir, exclude_names={"manifest.json"})
    (run_dir/"manifest.json").write_text(json.dumps(mani, indent=2, sort_keys=True), encoding="utf-8")

    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"Wrote run: {run_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
