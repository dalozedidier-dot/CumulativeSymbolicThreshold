#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QCC / ORI-C - State_Probability bootstrap pipeline (Ccl).
Strictly non-interpretative: computes descriptive proxies and audit artefacts only.

Inputs:
  --dataset-zip : path to 04-09-2020.zip inside repo
  --algo        : algorithm folder name (BV, QFT, ...)
  --device      : optional device filter (empty = all devices)
  --shots       : shots filter (string or int, e.g. 8192)
  --t-axis      : Depth (default) or Runtime
  --ccl-metric  : entropy | maxprob | impurity
  --ccl-threshold : float in [0,1]
  --bootstrap-samples : int
  --out-root    : output root (default 05_Results/qcc_stateprob_bootstrap)
Produces:
  runs/<timestamp>/{tables,figures}/ + summary.json + events + manifest handled by workflow.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class RunKey:
    algo: str
    device: str
    shots: int
    instance: str


_STATES_RE = re.compile(
    r"STATES_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$",
    re.IGNORECASE,
)
_ATTR_RE = re.compile(
    r"ATTR_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$",
    re.IGNORECASE,
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _safe_int(x: object) -> Optional[int]:
    try:
        if x is None:
            return None
        if isinstance(x, float) and math.isnan(x):
            return None
        s = str(x).strip()
        if not s:
            return None
        return int(float(s))
    except Exception:
        return None


def _read_states_csv(path: Path) -> pd.DataFrame:
    """
    STATES files are typically 2 columns: state, probability.
    Sometimes with header, sometimes without.
    """
    # Try pandas auto header detection. If it yields 1 column, fallback.
    try:
        df = pd.read_csv(path)
        if df.shape[1] >= 2:
            df = df.iloc[:, :2].copy()
            df.columns = ["state", "prob"]
            return df
    except Exception:
        pass

    # Fallback: read as headerless two columns
    df = pd.read_csv(path, header=None)
    if df.shape[1] < 2:
        raise ValueError(f"STATES csv malformed (needs >=2 cols): {path}")
    df = df.iloc[:, :2].copy()
    df.columns = ["state", "prob"]
    return df


def _read_attr_csv(path: Path) -> pd.DataFrame:
    """
    ATTR files can have column names with spaces. Keep them, then normalize.
    """
    df = pd.read_csv(path)
    # Normalize common columns
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _metric_ccl(probs: np.ndarray, metric: str) -> float:
    probs = np.asarray(probs, dtype=float)
    probs = probs[np.isfinite(probs)]
    if probs.size == 0:
        return float("nan")
    s = probs.sum()
    if not np.isfinite(s) or s <= 0:
        return float("nan")
    p = probs / s

    metric = metric.lower().strip()
    if metric == "entropy":
        # normalized Shannon entropy in [0,1]
        # if unknown dimension, normalize by log(K) where K = number of observed states
        k = int(p.size)
        if k <= 1:
            return 0.0
        h = -np.sum(np.where(p > 0, p * np.log(p), 0.0))
        return float(h / np.log(k))
    if metric == "maxprob":
        # 1 - max prob in [0,1]
        return float(1.0 - np.max(p))
    if metric == "impurity":
        # 1 - sum p^2 in [0,1)
        return float(1.0 - float(np.sum(p * p)))

    raise ValueError(f"Unknown ccl-metric: {metric}")


def _find_matching_files(base: Path, algo: str, shots: int, device_filter: str, t_axis: str) -> List[Tuple[RunKey, Path, Path]]:
    algo_dir = base / "04-09-2020" / algo
    if not algo_dir.exists():
        raise FileNotFoundError(f"Algo folder not found in zip: {algo_dir}")

    states_dir = algo_dir / "State_Probability"
    if not states_dir.exists():
        raise FileNotFoundError(f"Missing State_Probability dir: {states_dir}")

    attr_parent = algo_dir / ("Count_Depth" if t_axis.lower() == "depth" else "Runtime")
    if not attr_parent.exists():
        raise FileNotFoundError(f"Missing ATTR dir for t-axis={t_axis}: {attr_parent}")

    # Map ATTR by key
    attr_map: Dict[RunKey, Path] = {}
    for p in attr_parent.rglob("*.csv"):
        m = _ATTR_RE.search(p.name)
        if not m:
            continue
        dev = m.group("device")
        alg = m.group("algo")
        inst = m.group("instance")
        sh = int(m.group("shots"))
        if alg.upper() != algo.upper():
            continue
        if sh != shots:
            continue
        if device_filter and dev != device_filter:
            continue
        key = RunKey(algo=algo.upper(), device=dev, shots=shots, instance=inst)
        attr_map[key] = p

    pairs: List[Tuple[RunKey, Path, Path]] = []
    for p in states_dir.rglob("*.csv"):
        m = _STATES_RE.search(p.name)
        if not m:
            continue
        dev = m.group("device")
        alg = m.group("algo")
        inst = m.group("instance")
        sh = int(m.group("shots"))
        if alg.upper() != algo.upper():
            continue
        if sh != shots:
            continue
        if device_filter and dev != device_filter:
            continue
        key = RunKey(algo=algo.upper(), device=dev, shots=shots, instance=inst)
        attr_p = attr_map.get(key)
        if attr_p is None:
            # skip unmatched
            continue
        pairs.append((key, p, attr_p))

    return pairs


def _extract_zip(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-zip", required=True)
    ap.add_argument("--algo", required=True)
    ap.add_argument("--device", default="")
    ap.add_argument("--shots", required=True)
    ap.add_argument("--t-axis", default="Depth", choices=["Depth", "Runtime"])
    ap.add_argument("--ccl-metric", default="entropy", choices=["entropy", "maxprob", "impurity"])
    ap.add_argument("--ccl-threshold", default="0.70")
    ap.add_argument("--bootstrap-samples", default="500")
    ap.add_argument("--out-root", default="05_Results/qcc_stateprob_bootstrap")
    args = ap.parse_args()

    dataset_zip = Path(args.dataset_zip)
    if not dataset_zip.exists():
        raise FileNotFoundError(f"dataset_zip introuvable: {dataset_zip}")

    shots = int(float(args.shots))
    threshold = float(args.ccl_threshold)
    bs_n = int(float(args.bootstrap_samples))
    device_filter = str(args.device or "").strip()

    out_root = Path(args.out_root)
    run_id = _utc_stamp()
    run_dir = out_root / "runs" / run_id
    tables_dir = run_dir / "tables"
    figs_dir = run_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)

    # Extract zip to temp
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        _extract_zip(dataset_zip, td_path)

        pairs = _find_matching_files(
            td_path, algo=args.algo, shots=shots, device_filter=device_filter, t_axis=args.t_axis
        )
        if not pairs:
            # Still produce empty artefacts for auditability
            empty_ts = pd.DataFrame(columns=["algo", "device", "shots", "instance", "t", "ccl"])
            empty_ts.to_csv(tables_dir / "ccl_timeseries.csv", index=False)
            pd.DataFrame(columns=["algo", "device", "shots", "instance", "tstar", "ccl_at_tstar"]).to_csv(
                tables_dir / "tstar_by_instance.csv", index=False
            )
            pd.DataFrame(columns=["bootstrap_sample", "tstar"]).to_csv(tables_dir / "bootstrap_tstar.csv", index=False)
            summary = {
                "run_id": run_id,
                "algo": args.algo,
                "device_filter": device_filter,
                "shots": shots,
                "t_axis": args.t_axis,
                "ccl_metric": args.ccl_metric,
                "ccl_threshold": threshold,
                "bootstrap_samples": bs_n,
                "n_pairs": 0,
                "tstar_found_count": 0,
            }
            (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            # Minimal placeholder plot
            plt.figure()
            plt.title("No matching (algo/device/shots) in dataset")
            plt.savefig(figs_dir / "ccl_mean.png", dpi=140)
            plt.close()
            return 0

        rows: List[Dict[str, object]] = []
        for key, states_p, attr_p in pairs:
            sdf = _read_states_csv(states_p)
            adf = _read_attr_csv(attr_p)

            # t value:
            if args.t_axis.lower() == "depth":
                col_candidates = [c for c in adf.columns if c.lower() == "depth"]
            else:
                col_candidates = [c for c in adf.columns if c.lower() == "runtime"]
            if not col_candidates:
                # fallback: use first numeric col
                num_cols = [c for c in adf.columns if pd.api.types.is_numeric_dtype(adf[c])]
                if not num_cols:
                    t_val = float("nan")
                else:
                    t_val = float(pd.to_numeric(adf[num_cols[0]], errors="coerce").dropna().mean())
            else:
                t_val = float(pd.to_numeric(adf[col_candidates[0]], errors="coerce").dropna().mean())

            ccl = _metric_ccl(pd.to_numeric(sdf["prob"], errors="coerce").to_numpy(), args.ccl_metric)

            rows.append(
                {
                    "algo": key.algo,
                    "device": key.device,
                    "shots": key.shots,
                    "instance": key.instance,
                    "t": t_val,
                    "ccl": ccl,
                }
            )

        ts = pd.DataFrame(rows)
        ts = ts[np.isfinite(ts["t"])].copy()
        ts.to_csv(tables_dir / "ccl_timeseries.csv", index=False)

        # t* per instance: for each (device, instance) if we have multiple t points, take first t where ccl>=threshold
        tstar_rows: List[Dict[str, object]] = []
        for (dev, inst), g in ts.groupby(["device", "instance"], dropna=False):
            gg = g.sort_values("t")
            hit = gg[gg["ccl"] >= threshold]
            if hit.empty:
                tstar = float("nan")
                ccl_at = float("nan")
            else:
                tstar = float(hit.iloc[0]["t"])
                ccl_at = float(hit.iloc[0]["ccl"])
            tstar_rows.append(
                {"algo": args.algo, "device": dev, "shots": shots, "instance": inst, "tstar": tstar, "ccl_at_tstar": ccl_at}
            )
        tstar_df = pd.DataFrame(tstar_rows)
        # Always write, even if all NaN
        tstar_df.to_csv(tables_dir / "tstar_by_instance.csv", index=False)

        # Bootstrap: sample instances with replacement (within device) and compute median tstar ignoring NaN
        boot_rows: List[Dict[str, object]] = []
        rng = np.random.default_rng(1337)
        for i in range(bs_n):
            # resample rows (instance-level)
            sample = tstar_df.sample(n=len(tstar_df), replace=True, random_state=int(rng.integers(0, 2**31-1)))
            vals = pd.to_numeric(sample["tstar"], errors="coerce").to_numpy()
            vals = vals[np.isfinite(vals)]
            boot_tstar = float(np.median(vals)) if vals.size else float("nan")
            boot_rows.append({"bootstrap_sample": i, "tstar": boot_tstar})
        boot_df = pd.DataFrame(boot_rows)
        boot_df.to_csv(tables_dir / "bootstrap_tstar.csv", index=False)

        # Summary
        tstar_found = int(np.isfinite(pd.to_numeric(tstar_df["tstar"], errors="coerce")).sum())
        summary = {
            "run_id": run_id,
            "algo": args.algo,
            "device_filter": device_filter,
            "shots": shots,
            "t_axis": args.t_axis,
            "ccl_metric": args.ccl_metric,
            "ccl_threshold": threshold,
            "bootstrap_samples": bs_n,
            "n_pairs": int(len(pairs)),
            "n_points": int(len(ts)),
            "tstar_found_count": tstar_found,
        }
        (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        # Figures
        # Mean Ccl vs t by device
        plt.figure()
        for dev, g in ts.groupby("device"):
            gg = g.sort_values("t")
            plt.plot(gg["t"].to_numpy(), gg["ccl"].to_numpy(), marker="o", linestyle="-", label=str(dev))
        plt.axhline(threshold, linestyle="--")
        plt.xlabel(args.t_axis)
        plt.ylabel("Ccl")
        plt.title(f"Ccl vs {args.t_axis} ({args.algo}, shots={shots}, metric={args.ccl_metric})")
        plt.legend(loc="best", fontsize=8)
        plt.tight_layout()
        plt.savefig(figs_dir / "ccl_mean.png", dpi=160)
        plt.close()

        # Histogram of bootstrap tstar
        vals = pd.to_numeric(boot_df["tstar"], errors="coerce").dropna().to_numpy()
        plt.figure()
        if vals.size:
            plt.hist(vals, bins=min(30, max(5, int(math.sqrt(vals.size)))))
        plt.xlabel("tstar (bootstrap)")
        plt.ylabel("count")
        plt.title("Bootstrap distribution of tstar")
        plt.tight_layout()
        plt.savefig(figs_dir / "tstar_hist.png", dpi=160)
        plt.close()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[qcc_stateprob_bootstrap] ERROR: {e}", file=sys.stderr)
        raise
