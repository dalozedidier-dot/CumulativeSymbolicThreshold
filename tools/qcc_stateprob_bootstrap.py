#!/usr/bin/env python3
"""
QCC StateProb Bootstrap (Ccl)

Adds:
- inventory.csv: counts available pairs by (algo, device, shots), plus instances and depth coverage
- recommendations.json: top 10 "richest" combinations for stable bootstrap

This script is intentionally "mechanical": it computes dispersion metrics from observed
state-probability distributions and circuit attributes, without any interpretive verdict.

Expected dataset layout inside the zip (example):
  04-09-2020/BV/State_Probability/STATES_<device>_BV_<instance>_<shots>.csv
  04-09-2020/BV/Count_Depth/ATTR_<device>_BV_<instance>_<shots>.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


STATES_RE = re.compile(r".*/(?P<algo>[A-Z0-9_]+)/State_Probability/STATES_(?P<device>[^_]+)_(?P=algo)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$")
ATTR_RE   = re.compile(r".*/(?P<algo>[A-Z0-9_]+)/Count_Depth/ATTR_(?P<device>[^_]+)_(?P=algo)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$")


@dataclass(frozen=True)
class RunKey:
    algo: str
    device: str
    shots: int
    instance: int


def _is_nan_like(x) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    if isinstance(x, str) and x.strip().lower() in {"", "nan", "none", "null"}:
        return True
    return False


def _norm_entropy(probs: np.ndarray) -> float:
    p = probs[probs > 0]
    if p.size == 0:
        return 0.0
    h = float(-(p * np.log(p)).sum())
    # normalize by log(K) where K is support size observed
    k = max(2, int(probs.size))
    return h / math.log(k)


def _impurity(probs: np.ndarray) -> float:
    p = probs
    return float(1.0 - (p * p).sum())


def _one_minus_max(probs: np.ndarray) -> float:
    if probs.size == 0:
        return 0.0
    return float(1.0 - probs.max())


def _compute_ccl_metric(metric: str, probs: np.ndarray) -> float:
    metric = metric.lower().strip()
    if metric == "entropy":
        return _norm_entropy(probs)
    if metric == "impurity":
        return _impurity(probs)
    if metric in {"1-max", "one_minus_max", "max"}:
        return _one_minus_max(probs)
    raise ValueError(f"Unknown ccl_metric: {metric}")


def _read_states_csv(zf: zipfile.ZipFile, name: str) -> np.ndarray:
    # STATES files are typically 2 columns: bitstring, prob (no header)
    with zf.open(name, "r") as f:
        df = pd.read_csv(f, header=None)
    if df.shape[1] < 2:
        raise ValueError(f"STATES file has <2 columns: {name}")
    probs = pd.to_numeric(df.iloc[:, 1], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    # numeric hygiene
    probs = np.clip(probs, 0.0, 1.0)
    s = probs.sum()
    if s > 0:
        probs = probs / s
    return probs


def _read_attr_depths(zf: zipfile.ZipFile, name: str) -> np.ndarray:
    # ATTR files have headers; column names sometimes include spaces.
    with zf.open(name, "r") as f:
        df = pd.read_csv(f)
    # try common variants
    candidates = ["Depth", " depth", "DEPTH", "Circuit_Depth", "circuit_depth"]
    depth_col = None
    for c in candidates:
        if c in df.columns:
            depth_col = c
            break
    if depth_col is None:
        # fall back: first column containing "depth" (case-insensitive)
        for c in df.columns:
            if "depth" in str(c).lower():
                depth_col = c
                break
    if depth_col is None:
        raise ValueError(f"ATTR file missing Depth column: {name} cols={list(df.columns)[:8]}")
    depths = pd.to_numeric(df[depth_col], errors="coerce").dropna().to_numpy(dtype=float)
    return depths


def _scan_zip_index(zf: zipfile.ZipFile) -> Tuple[Dict[RunKey, str], Dict[RunKey, str]]:
    states: Dict[RunKey, str] = {}
    attrs: Dict[RunKey, str] = {}
    for name in zf.namelist():
        m = STATES_RE.match(name)
        if m:
            rk = RunKey(
                algo=m.group("algo"),
                device=m.group("device"),
                shots=int(m.group("shots")),
                instance=int(m.group("instance")),
            )
            states[rk] = name
            continue
        m = ATTR_RE.match(name)
        if m:
            rk = RunKey(
                algo=m.group("algo"),
                device=m.group("device"),
                shots=int(m.group("shots")),
                instance=int(m.group("instance")),
            )
            attrs[rk] = name
    return states, attrs


def build_inventory(
    zf: zipfile.ZipFile,
    states: Dict[RunKey, str],
    attrs: Dict[RunKey, str],
) -> pd.DataFrame:
    # Pair keys are those present in both.
    pair_keys = sorted(set(states.keys()) & set(attrs.keys()), key=lambda k: (k.algo, k.device, k.shots, k.instance))

    rows = []
    # We'll compute depth coverage per pair by reading ATTR depths.
    # This is the heaviest part, but still manageable for CI sizes.
    depth_cache: Dict[RunKey, int] = {}
    for k in pair_keys:
        try:
            depths = _read_attr_depths(zf, attrs[k])
            depth_cache[k] = int(pd.Series(depths).nunique())
        except Exception:
            depth_cache[k] = 0

    # Aggregate by (algo, device, shots)
    agg: Dict[Tuple[str, str, int], Dict[str, object]] = {}
    for k in pair_keys:
        g = (k.algo, k.device, k.shots)
        if g not in agg:
            agg[g] = {
                "algo": k.algo,
                "device": k.device,
                "shots": k.shots,
                "n_pairs": 0,
                "instances": set(),
                "depth_counts": [],
            }
        agg[g]["n_pairs"] += 1
        agg[g]["instances"].add(k.instance)
        agg[g]["depth_counts"].append(depth_cache.get(k, 0))

    for g, v in agg.items():
        depth_counts = v["depth_counts"] or [0]
        rows.append({
            "algo": v["algo"],
            "device": v["device"],
            "shots": v["shots"],
            "n_pairs": int(v["n_pairs"]),
            "n_instances": int(len(v["instances"])),
            "depth_distinct_min": int(np.min(depth_counts)),
            "depth_distinct_median": float(np.median(depth_counts)),
            "depth_distinct_max": int(np.max(depth_counts)),
        })

    df = pd.DataFrame(rows).sort_values(["n_pairs", "n_instances", "depth_distinct_median"], ascending=[False, False, False])
    return df.reset_index(drop=True)


def recommend_combinations(inv: pd.DataFrame, top_k: int = 10) -> List[dict]:
    # Richness score emphasizes: many instances AND good depth coverage.
    # We avoid any interpretive "good/bad" language; it's just data richness.
    recs = []
    for _, r in inv.iterrows():
        n_instances = float(r["n_instances"])
        depth_med = float(r["depth_distinct_median"])
        n_pairs = float(r["n_pairs"])
        score = (n_instances * max(1.0, depth_med)) + 0.25 * n_pairs
        recs.append({
            "algo": r["algo"],
            "device": r["device"],
            "shots": int(r["shots"]),
            "n_pairs": int(r["n_pairs"]),
            "n_instances": int(r["n_instances"]),
            "depth_distinct_median": float(depth_med),
            "richness_score": float(score),
        })
    recs.sort(key=lambda x: x["richness_score"], reverse=True)
    return recs[:top_k]


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_json(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-zip", required=True, help="Path to 04-09-2020.zip (or similar)")
    ap.add_argument("--out-dir", required=True, help="Output directory for this run")
    ap.add_argument("--algo", default="BV", help="Algorithm family to process (e.g., BV, QAOA, ...)")
    ap.add_argument("--shots", type=int, default=8192, help="Shots to filter")
    ap.add_argument("--device", default="", help="Optional device filter. Empty means all devices.")
    ap.add_argument("--metric", default="entropy", choices=["entropy", "impurity", "1-max"], help="Ccl metric")
    ap.add_argument("--t-axis", default="Depth", choices=["Depth"], help="Axis used as t (currently Depth)")
    ap.add_argument("--ccl-threshold", type=float, default=0.70, help="Threshold for t* detection on Ccl")
    ap.add_argument("--bootstrap-samples", type=int, default=500, help="Bootstrap resamples")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    tables_dir = out_dir / "tables"
    figs_dir = out_dir / "figures"
    _ensure_dir(tables_dir)
    _ensure_dir(figs_dir)

    zpath = Path(args.dataset_zip)
    if not zpath.exists():
        raise FileNotFoundError(f"dataset_zip introuvable: {zpath}")

    with zipfile.ZipFile(zpath, "r") as zf:
        states, attrs = _scan_zip_index(zf)

        # Always produce inventory + recommendations (requested)
        inv = build_inventory(zf, states, attrs)
        inv_path = tables_dir / "inventory.csv"
        inv.to_csv(inv_path, index=False)

        recs = recommend_combinations(inv, top_k=10)
        _write_json(tables_dir / "recommendations.json", {"top10": recs})

        # Now run the main filtered pipeline (still produces ccl_timeseries etc.)
        # Filter to requested algo/shots/(device)
        pair_keys = [k for k in (set(states) & set(attrs))
                     if k.algo == args.algo and k.shots == args.shots and (not args.device or k.device == args.device)]
        pair_keys = sorted(pair_keys, key=lambda k: (k.device, k.instance))

        # Build per-instance Ccl(t) by joining Depth with a single Ccl value from the states distribution.
        # Note: STATES file does not encode per-depth distribution; it is the output distribution for the circuit.
        # We therefore associate the circuit-level Ccl to its circuit Depth (a scalar).
        rows = []
        tstars = []
        for k in pair_keys:
            probs = _read_states_csv(zf, states[k])
            ccl = _compute_ccl_metric(args.metric, probs)
            depths = _read_attr_depths(zf, attrs[k])
            # For ATTR, we take representative depth = max depth in file (typical for circuit attributes)
            t_val = float(np.nanmax(depths)) if depths.size else float("nan")
            rows.append({
                "algo": k.algo,
                "device": k.device,
                "shots": k.shots,
                "instance": k.instance,
                "t": t_val,
                "Ccl": float(ccl),
            })
        ts_df = pd.DataFrame(rows)
        ts_df.to_csv(tables_dir / "ccl_timeseries.csv", index=False)

        # t* per instance: first t where Ccl >= threshold (since higher dispersion/entropy = more "classical" here)
        # If no crossing, tstar is NaN.
        if not ts_df.empty:
            for (dev, inst), g in ts_df.groupby(["device", "instance"]):
                g2 = g.sort_values("t")
                hit = g2[g2["Ccl"] >= float(args.ccl_threshold)]
                if hit.empty:
                    tstars.append({"device": dev, "instance": int(inst), "tstar": float("nan"), "ccl_at_tstar": float("nan")})
                else:
                    first = hit.iloc[0]
                    tstars.append({"device": dev, "instance": int(inst), "tstar": float(first["t"]), "ccl_at_tstar": float(first["Ccl"])})
        tstar_df = pd.DataFrame(tstars)
        tstar_df.to_csv(tables_dir / "tstar_by_instance.csv", index=False)

        # Bootstrap tstar over instances (within each device)
        boot_rows = []
        rng = np.random.default_rng(12345)
        if not tstar_df.empty:
            for dev, g in tstar_df.groupby("device"):
                vals = g["tstar"].to_numpy(dtype=float)
                vals = vals[~np.isnan(vals)]
                if vals.size == 0:
                    # still write NaNs
                    for i in range(int(args.bootstrap_samples)):
                        boot_rows.append({"device": dev, "sample": i, "tstar": float("nan")})
                else:
                    for i in range(int(args.bootstrap_samples)):
                        sample = rng.choice(vals, size=vals.size, replace=True)
                        boot_rows.append({"device": dev, "sample": i, "tstar": float(np.nanmean(sample))})
        boot_df = pd.DataFrame(boot_rows)
        boot_df.to_csv(tables_dir / "bootstrap_tstar.csv", index=False)

        # Summary
        summary = {
            "algo": args.algo,
            "shots": int(args.shots),
            "device_filter": args.device or None,
            "t_axis": args.t_axis,
            "ccl_metric": args.metric,
            "ccl_threshold": float(args.ccl_threshold),
            "bootstrap_samples": int(args.bootstrap_samples),
            "n_pairs_total": int((set(states) & set(attrs)).__len__()),
            "n_pairs_selected": int(len(pair_keys)),
            "n_points": int(len(ts_df)),
            "tstar_found_count": int(np.sum(~np.isnan(tstar_df["tstar"].to_numpy(dtype=float))) if not tstar_df.empty else 0),
            "inventory_rows": int(len(inv)),
        }
        _write_json(tables_dir / "summary.json", summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
