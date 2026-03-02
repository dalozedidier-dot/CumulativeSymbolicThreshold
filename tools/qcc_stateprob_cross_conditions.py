#!/usr/bin/env python3
"""
QCC StateProb Cross-Conditions

Goal: compare C_cl vs axis (Depth or Runtime) across shots for a given (algo, device filter).
- Computes a GLOBAL inventory (all algos/devices/shots) and Top-10 recommendations (mechanical score).
- Then applies user filters to compute cross-condition outputs.
- Produces tables + figures + contracts + manifest sha256. No interpretive verdict.

Dataset layout (from 04-09-2020 style bundle):
  <root>/<ALGO>/State_Probability/STATES_<device>_<ALGO>_<instance>_<shots>.csv
  <root>/<ALGO>/Count_Depth/ATTR_<device>_<ALGO>_<instance>_<shots>.csv
  (Runtime can be supported similarly if present; we keep Depth default)
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class PairKey:
    algo: str
    device: str
    shots: int
    instance: int


_STATES_RE = re.compile(
    r"STATES_(?P<device>[^_]+)_(?P<algo>[A-Z0-9]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$",
    re.IGNORECASE,
)
_ATTR_RE = re.compile(
    r"ATTR_(?P<device>[^_]+)_(?P<algo>[A-Z0-9]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$",
    re.IGNORECASE,
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_manifest(run_dir: Path) -> None:
    manifest = {"files": []}
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(run_dir).as_posix()
            manifest["files"].append({"path": rel, "sha256": _sha256_file(p), "bytes": p.stat().st_size})
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def _load_states_csv(path: Path) -> pd.DataFrame:
    """
    STATES files are typically 2 columns without a header: bitstring,probability
    Some variants may have a header; we handle both.
    """
    df = pd.read_csv(path, header=None)
    if df.shape[1] < 2:
        raise ValueError(f"STATES file has <2 columns: {path}")
    # If first row looks like header strings, re-read with header=0
    if isinstance(df.iloc[0, 0], str) and str(df.iloc[0, 0]).lower() in {"state", "bitstring", "bit_string"}:
        df = pd.read_csv(path, header=0)
        # normalize col names
        cols = {c.lower(): c for c in df.columns}
        bit_col = cols.get("state") or cols.get("bitstring") or cols.get("bit_string")
        prob_col = cols.get("prob") or cols.get("probability") or cols.get("p")
        if bit_col is None or prob_col is None:
            # fallback: first two columns
            bit_col, prob_col = df.columns[0], df.columns[1]
        df = df[[bit_col, prob_col]].rename(columns={bit_col: "bitstring", prob_col: "p"})
        return df
    df = df.iloc[:, :2].copy()
    df.columns = ["bitstring", "p"]
    return df


def _load_attr_csv(path: Path) -> pd.DataFrame:
    """
    ATTR files usually have a header; sometimes with leading/trailing spaces.
    We keep all columns and strip spaces.
    """
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _ccl_from_distribution(p: np.ndarray, metric: str) -> float:
    p = np.asarray(p, dtype=float)
    p = p[np.isfinite(p)]
    p = p[p > 0]
    if p.size == 0:
        return float("nan")
    p = p / p.sum()
    metric = metric.lower()
    if metric == "entropy":
        h = -np.sum(p * np.log(p))
        # normalize by log(K) where K = number of observed states (conservative)
        return float(h / math.log(max(2, p.size)))
    if metric == "impurity":
        return float(1.0 - np.sum(p ** 2))
    if metric in {"one_minus_max", "1-max", "max"}:
        return float(1.0 - np.max(p))
    raise ValueError(f"Unknown metric: {metric}")


def _extract_dataset(dataset_path: Path) -> Tuple[Path, Optional[tempfile.TemporaryDirectory]]:
    """
    Return a root directory. If dataset_path is a directory, use it.
    If it's a zip, extract to a temp dir.
    """
    if dataset_path.is_dir():
        return dataset_path, None
    if dataset_path.is_file() and dataset_path.suffix.lower() == ".zip":
        td = tempfile.TemporaryDirectory(prefix="qcc_stateprob_")
        out = Path(td.name)
        shutil.unpack_archive(str(dataset_path), str(out))
        # if archive contains a single top directory, use it
        children = [p for p in out.iterdir() if p.is_dir()]
        if len(children) == 1:
            return children[0], td
        return out, td
    raise FileNotFoundError(f"dataset not found: {dataset_path}")


def _discover_pairs(root: Path) -> Tuple[Dict[PairKey, Path], Dict[PairKey, Path]]:
    """
    Walk the dataset tree and map PairKey -> STATES/ATTR paths.
    """
    states: Dict[PairKey, Path] = {}
    attrs: Dict[PairKey, Path] = {}
    for p in root.rglob("*.csv"):
        name = p.name
        m = _STATES_RE.match(name)
        if m:
            key = PairKey(
                algo=m.group("algo").upper(),
                device=m.group("device"),
                shots=int(m.group("shots")),
                instance=int(m.group("instance")),
            )
            states[key] = p
            continue
        m = _ATTR_RE.match(name)
        if m:
            key = PairKey(
                algo=m.group("algo").upper(),
                device=m.group("device"),
                shots=int(m.group("shots")),
                instance=int(m.group("instance")),
            )
            attrs[key] = p
            continue
    return states, attrs


def _global_inventory(states: Dict[PairKey, Path], attrs: Dict[PairKey, Path], axis: str) -> pd.DataFrame:
    rows = []
    # intersect keys
    keys = sorted(set(states.keys()) & set(attrs.keys()), key=lambda k: (k.algo, k.device, k.shots, k.instance))
    # pre-read axis values per key
    axis = axis.strip()
    for k in keys:
        try:
            df_attr = _load_attr_csv(attrs[k])
            if axis not in df_attr.columns:
                # axis not present => skip
                continue
            # some attr files may have multiple rows; we keep unique values
            vals = pd.to_numeric(df_attr[axis], errors="coerce").dropna().unique().tolist()
            depth_vals = sorted(set(int(v) for v in vals))
            rows.append(
                {
                    "algo": k.algo,
                    "device": k.device,
                    "shots": k.shots,
                    "instance": k.instance,
                    "axis_values": depth_vals,
                    "axis_distinct": len(depth_vals),
                }
            )
        except Exception:
            continue
    if not rows:
        return pd.DataFrame(
            columns=[
                "algo",
                "device",
                "shots",
                "pairs_count",
                "instances_count",
                "axis_distinct_total",
                "axis_distinct_min",
                "axis_distinct_median",
                "axis_distinct_max",
            ]
        )
    df = pd.DataFrame(rows)
    agg = (
        df.groupby(["algo", "device", "shots"])
        .agg(
            pairs_count=("instance", "count"),
            instances_count=("instance", pd.Series.nunique),
            axis_distinct_total=("axis_values", lambda x: len(set(v for lst in x for v in lst))),
            axis_distinct_min=("axis_distinct", "min"),
            axis_distinct_median=("axis_distinct", "median"),
            axis_distinct_max=("axis_distinct", "max"),
        )
        .reset_index()
    )
    return agg.sort_values(["pairs_count", "instances_count", "axis_distinct_total"], ascending=False).reset_index(drop=True)


def _recommendations(inv: pd.DataFrame, topk: int = 10) -> dict:
    if inv.empty:
        return {"topk": [], "note": "no pairs found"}
    # mechanical score: prioritize pairs, then instances, then axis coverage
    inv = inv.copy()
    inv["score"] = inv["pairs_count"] * 10000 + inv["instances_count"] * 100 + inv["axis_distinct_total"]
    inv = inv.sort_values(["score", "pairs_count", "instances_count", "axis_distinct_total"], ascending=False)
    top = inv.head(topk)
    out = {"topk": []}
    for _, r in top.iterrows():
        out["topk"].append(
            {
                "algo": r["algo"],
                "device": r["device"],
                "shots": int(r["shots"]),
                "pairs_count": int(r["pairs_count"]),
                "instances_count": int(r["instances_count"]),
                "axis_distinct_total": int(r["axis_distinct_total"]),
                "axis_distinct_min": float(r["axis_distinct_min"]),
                "axis_distinct_median": float(r["axis_distinct_median"]),
                "axis_distinct_max": float(r["axis_distinct_max"]),
                "score": int(r["score"]),
            }
        )
    return out


def _filter_keys(
    keys: Iterable[PairKey],
    algo: str,
    device: str,
    shots: Optional[int],
) -> List[PairKey]:
    algo = algo.strip().upper()
    device = device.strip()
    out = []
    for k in keys:
        if algo and k.algo != algo:
            continue
        if device and k.device != device:
            continue
        if shots is not None and k.shots != shots:
            continue
        out.append(k)
    return sorted(out, key=lambda kk: (kk.shots, kk.instance))


def _compute_points(
    keys: List[PairKey],
    states: Dict[PairKey, Path],
    attrs: Dict[PairKey, Path],
    axis: str,
    metric: str,
) -> pd.DataFrame:
    rows = []
    for k in keys:
        df_states = _load_states_csv(states[k])
        df_attr = _load_attr_csv(attrs[k])
        if axis not in df_attr.columns:
            continue
        # for most files, axis is a single value; if multiple, we take the first unique
        axis_vals = pd.to_numeric(df_attr[axis], errors="coerce").dropna().unique()
        if axis_vals.size == 0:
            continue
        t_val = float(axis_vals[0])
        ccl = _ccl_from_distribution(pd.to_numeric(df_states["p"], errors="coerce").values, metric=metric)
        rows.append(
            {
                "algo": k.algo,
                "device": k.device,
                "shots": k.shots,
                "instance": k.instance,
                "axis": t_val,
                "ccl": ccl,
                "states_path": str(states[k]),
                "attr_path": str(attrs[k]),
            }
        )
    return pd.DataFrame(rows)


def _tstar_for_group(df: pd.DataFrame, threshold: float) -> Tuple[float, float]:
    """
    Given rows for a group (same algo/device/shots/instance) with axis and ccl,
    return (tstar, ccl_at_tstar). If no crossing, return (nan, nan).
    """
    if df.empty:
        return float("nan"), float("nan")
    d = df.sort_values("axis")
    # first axis where ccl >= threshold
    hit = d[d["ccl"] >= threshold]
    if hit.empty:
        return float("nan"), float("nan")
    row = hit.iloc[0]
    return float(row["axis"]), float(row["ccl"])


def _bootstrap_tstar(values: List[float], n: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    vals = [v for v in values if math.isfinite(v)]
    if not vals:
        return pd.DataFrame({"sample": list(range(n)), "tstar": [float("nan")] * n})
    out = []
    for i in range(n):
        samp = rng.choice(vals, size=len(vals), replace=True)
        out.append({"sample": i, "tstar": float(np.mean(samp))})
    return pd.DataFrame(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Path to dataset zip OR extracted directory")
    ap.add_argument("--algo", default="", help="Algorithm filter (e.g., SIMON). Empty = all")
    ap.add_argument("--device", default="", help="Device filter (exact, e.g., ibmqx2). Empty = all")
    ap.add_argument("--shots", default="", help="Shots filter. Empty = all")
    ap.add_argument("--t-axis", default="Depth", help="Axis column in ATTR file (Depth recommended)")
    ap.add_argument("--metric", default="entropy", choices=["entropy", "impurity", "one_minus_max"], help="Ccl metric")
    ap.add_argument("--threshold", type=float, default=0.70, help="Ccl threshold for t*")
    ap.add_argument("--bootstrap", type=int, default=500, help="Bootstrap samples")
    ap.add_argument("--out-dir", required=True, help="Output directory root")
    ap.add_argument("--out-root", default="", help="Legacy alias for --out-dir")
    args = ap.parse_args()

    out_root = Path(args.out_dir)
    if args.out_root:
        out_root = Path(args.out_root)

    dataset_path = Path(args.dataset)
    axis = str(args.t_axis).strip()
    shots_filter = None
    if str(args.shots).strip():
        shots_filter = int(str(args.shots).strip())

    # Create run dir
    ts = _dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / "runs" / ts
    tables_dir = run_dir / "tables"
    figs_dir = run_dir / "figures"
    contracts_dir = run_dir / "contracts"
    for d in [tables_dir, figs_dir, contracts_dir]:
        d.mkdir(parents=True, exist_ok=True)

    tmp = None
    try:
        root, tmp = _extract_dataset(dataset_path)
        states, attrs = _discover_pairs(root)

        inv = _global_inventory(states, attrs, axis=axis)
        inv.to_csv(tables_dir / "inventory.csv", index=False)
        rec = _recommendations(inv, topk=10)
        (tables_dir / "recommendations.json").write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")

        # Compute filtered points
        all_keys = sorted(set(states.keys()) & set(attrs.keys()), key=lambda k: (k.algo, k.device, k.shots, k.instance))
        filt_keys = _filter_keys(all_keys, algo=args.algo, device=args.device, shots=shots_filter)
        points = _compute_points(filt_keys, states, attrs, axis=axis, metric=args.metric)
        points.to_csv(tables_dir / "ccl_points.csv", index=False)

        # Aggregate by shots and axis
        if points.empty:
            ccl_by = pd.DataFrame(columns=["shots", "axis", "ccl_mean", "ccl_std", "n"])
        else:
            ccl_by = (
                points.groupby(["shots", "axis"])
                .agg(ccl_mean=("ccl", "mean"), ccl_std=("ccl", "std"), n=("ccl", "count"))
                .reset_index()
                .sort_values(["shots", "axis"])
            )
        ccl_by.to_csv(tables_dir / "ccl_by_shots.csv", index=False)

        # t* per shots: compute per instance then summarize
        tstar_rows = []
        if not points.empty:
            for (shots, instance), g in points.groupby(["shots", "instance"]):
                tstar, ccl_hit = _tstar_for_group(g, threshold=float(args.threshold))
                tstar_rows.append({"shots": int(shots), "instance": int(instance), "tstar": tstar, "ccl_at_tstar": ccl_hit})
        tstar_df = pd.DataFrame(tstar_rows)
        tstar_df.to_csv(tables_dir / "tstar_by_shots.csv", index=False)

        # Bootstrap by shots: mean t* over instances
        boot_rows = []
        for shots, g in tstar_df.groupby("shots") if not tstar_df.empty else []:
            vals = g["tstar"].tolist()
            boot = _bootstrap_tstar(vals, n=int(args.bootstrap), seed=7)
            boot["shots"] = int(shots)
            boot_rows.append(boot)
        boot_df = pd.concat(boot_rows, ignore_index=True) if boot_rows else pd.DataFrame(columns=["sample", "tstar", "shots"])
        boot_df.to_csv(tables_dir / "bootstrap_tstar_by_shots.csv", index=False)

        # Summary (REQUIRED by checks)
        summary = {
            "run_type": "qcc_stateprob_cross_conditions",
            "dataset": str(dataset_path.as_posix()),
            "dataset_mode": "dir" if dataset_path.is_dir() else "zip",
            "filters": {"algo": args.algo, "device": args.device, "shots": (None if shots_filter is None else shots_filter)},
            "t_axis": axis,
            "metric": args.metric,
            "threshold": float(args.threshold),
            "bootstrap_samples": int(args.bootstrap),
            "global_inventory_rows": int(inv.shape[0]),
            "filtered_pairs": int(len(filt_keys)),
            "filtered_points": int(points.shape[0]),
            "shots_distinct": int(points["shots"].nunique()) if not points.empty else 0,
        }
        (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

        # Contracts (minimal, but hashed)
        mapping = {
            "ccl_metric": args.metric,
            "t_axis": axis,
            "tstar_threshold": float(args.threshold),
            "notes": [
                "Ccl computed mechanically from output distribution p(x).",
                "No interpretive verdict; outputs are descriptive.",
            ],
        }
        (contracts_dir / "mapping_cross_conditions.json").write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")

        # Figure: Ccl vs axis by shots
        if not ccl_by.empty:
            plt.figure()
            for shots, g in ccl_by.groupby("shots"):
                plt.plot(g["axis"].values, g["ccl_mean"].values, marker="o", label=f"shots={int(shots)}")
            plt.xlabel(axis)
            plt.ylabel("Ccl (metric)")
            plt.title(f"Ccl vs {axis} by shots")
            plt.legend()
            plt.tight_layout()
            plt.savefig(figs_dir / "ccl_vs_axis_by_shots.png", dpi=160)
            plt.close()
        else:
            # still produce an empty placeholder plot to keep outputs stable
            plt.figure()
            plt.text(0.5, 0.5, "No points after filtering", ha="center", va="center")
            plt.axis("off")
            plt.tight_layout()
            plt.savefig(figs_dir / "ccl_vs_axis_by_shots.png", dpi=160)
            plt.close()

        # Figure: histogram of t* pooled
        if not tstar_df.empty and tstar_df["tstar"].notna().any():
            plt.figure()
            vals = tstar_df["tstar"].dropna().values
            plt.hist(vals, bins=min(20, max(3, len(vals))))
            plt.xlabel("t*")
            plt.ylabel("count")
            plt.title("t* distribution across instances")
            plt.tight_layout()
            plt.savefig(figs_dir / "tstar_hist.png", dpi=160)
            plt.close()
        else:
            plt.figure()
            plt.text(0.5, 0.5, "No t* found", ha="center", va="center")
            plt.axis("off")
            plt.tight_layout()
            plt.savefig(figs_dir / "tstar_hist.png", dpi=160)
            plt.close()

        _write_manifest(run_dir)

    finally:
        if tmp is not None:
            tmp.cleanup()

    print(f"Wrote run: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
