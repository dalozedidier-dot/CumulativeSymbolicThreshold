#!/usr/bin/env python3
"""QCC StateProb Bootstrap (Ccl)

Fix: accept both --out-dir (preferred) and legacy --out-root used by older workflow packs.
"""

from __future__ import annotations

import argparse
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

# -----------------------------
# Helpers
# -----------------------------

def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _read_states_csv(path: Path) -> pd.DataFrame:
    # States csv files in the dataset typically have two columns: bitstring, probability
    # Sometimes without headers.
    df = pd.read_csv(path, header=None)
    if df.shape[1] < 2:
        raise ValueError(f"Invalid STATES csv (expected 2 columns): {path}")
    df = df.iloc[:, :2]
    df.columns = ["bitstring", "prob"]
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce")
    df = df.dropna(subset=["prob"])
    return df

def _read_attr_csv(path: Path) -> pd.DataFrame:
    # ATTR files usually have headers; keep as-is but normalize common column names
    df = pd.read_csv(path)
    # Normalize spaces in columns
    df.columns = [c.strip() for c in df.columns]
    return df

def _entropy_norm(p: np.ndarray) -> float:
    p = p[p > 0]
    if p.size == 0:
        return float("nan")
    h = -np.sum(p * np.log(p))
    # Normalize by log(K) where K is number of outcomes observed (upper bound within file)
    denom = math.log(max(p.size, 2))
    return float(h / denom) if denom > 0 else float("nan")

def _impurity(p: np.ndarray) -> float:
    p = p[p >= 0]
    if p.size == 0:
        return float("nan")
    return float(1.0 - np.sum(p * p))

def _one_minus_max(p: np.ndarray) -> float:
    p = p[p >= 0]
    if p.size == 0:
        return float("nan")
    return float(1.0 - np.max(p))

@dataclass(frozen=True)
class RunKey:
    algo: str
    device: str
    shots: int
    instance: str

_STATES_RE = re.compile(r"STATES_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+?)_(?P<shots>\d+)\.csv$", re.IGNORECASE)
_ATTR_RE   = re.compile(r"ATTR_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+?)_(?P<shots>\d+)\.csv$", re.IGNORECASE)

def _scan_dataset(root: Path) -> Tuple[Dict[RunKey, Path], Dict[RunKey, Path]]:
    states: Dict[RunKey, Path] = {}
    attrs: Dict[RunKey, Path] = {}

    for p in root.rglob("*.csv"):
        name = p.name
        m = _STATES_RE.match(name)
        if m:
            rk = RunKey(
                algo=m.group("algo"),
                device=m.group("device"),
                shots=int(m.group("shots")),
                instance=m.group("instance"),
            )
            states[rk] = p
            continue
        m = _ATTR_RE.match(name)
        if m:
            rk = RunKey(
                algo=m.group("algo"),
                device=m.group("device"),
                shots=int(m.group("shots")),
                instance=m.group("instance"),
            )
            attrs[rk] = p
            continue

    return states, attrs

def _metric_value(df_states: pd.DataFrame, metric: str) -> float:
    p = df_states["prob"].to_numpy(dtype=float)
    p = p[np.isfinite(p)]
    # Normalize defensively
    s = np.sum(p)
    if s <= 0:
        return float("nan")
    p = p / s
    if metric == "entropy":
        return _entropy_norm(p)
    if metric == "impurity":
        return _impurity(p)
    if metric == "1-max":
        return _one_minus_max(p)
    raise ValueError(f"Unknown metric: {metric}")

def _pick_depth(attr: pd.DataFrame) -> Optional[float]:
    # Try common column names
    for col in ("Depth", "depth", "DEPTH"):
        if col in attr.columns:
            v = pd.to_numeric(attr[col], errors="coerce").dropna()
            if not v.empty:
                # Some files have a single row; take first
                return float(v.iloc[0])
    return None

def _compute_inventory(pairs: List[Tuple[RunKey, Path, Path]]) -> pd.DataFrame:
    rows = []
    # group by algo, device, shots
    for (algo, device, shots), group in pd.DataFrame(
        [{"algo": rk.algo, "device": rk.device, "shots": rk.shots, "instance": rk.instance, "attr": str(attrp)} for rk, _, attrp in pairs]
    ).groupby(["algo", "device", "shots"], dropna=False):
        instances = group["instance"].nunique()
        # Count distinct depths by reading ATTR (can be expensive but manageable for inventory)
        depths = []
        for ap in group["attr"].tolist():
            try:
                df_attr = _read_attr_csv(Path(ap))
                d = _pick_depth(df_attr)
                if d is not None and math.isfinite(d):
                    depths.append(d)
            except Exception:
                continue
        depths_arr = np.array(depths, dtype=float) if depths else np.array([], dtype=float)
        depth_distinct = int(len(np.unique(depths_arr))) if depths_arr.size else 0
        rows.append({
            "algo": algo,
            "device": device,
            "shots": int(shots),
            "n_pairs": int(len(group)),
            "n_instances": int(instances),
            "n_depth_distinct": int(depth_distinct),
            "depth_min": float(np.min(depths_arr)) if depths_arr.size else float("nan"),
            "depth_median": float(np.median(depths_arr)) if depths_arr.size else float("nan"),
            "depth_max": float(np.max(depths_arr)) if depths_arr.size else float("nan"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["n_pairs", "n_instances", "n_depth_distinct"], ascending=False).reset_index(drop=True)
    return df

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-zip", required=True, help="Path to dataset zip inside repo")
    ap.add_argument("--out-dir", required=False, help="Output directory (preferred)")
    ap.add_argument("--out-root", required=False, help="Legacy alias for --out-dir")
    ap.add_argument("--algo", default="BV")
    ap.add_argument("--shots", default="8192")
    ap.add_argument("--device", default="")
    ap.add_argument("--metric", choices=["entropy", "impurity", "1-max"], default="entropy")
    ap.add_argument("--t-axis", choices=["Depth"], default="Depth")
    ap.add_argument("--ccl-threshold", type=float, default=0.70)
    ap.add_argument("--bootstrap-samples", type=int, default=500)
    args = ap.parse_args(argv)

    out_dir = args.out_dir or args.out_root
    if not out_dir:
        ap.error("the following arguments are required: --out-dir (or legacy --out-root)")
    out_root = Path(out_dir)

    dataset_zip = Path(args.dataset_zip)
    if not dataset_zip.exists():
        raise FileNotFoundError(f"dataset_zip not found: {dataset_zip}")

    run_id = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / "runs" / run_id
    tables_dir = run_dir / "tables"
    figures_dir = run_dir / "figures"
    contracts_dir = run_dir / "contracts"
    _safe_mkdir(tables_dir)
    _safe_mkdir(figures_dir)
    _safe_mkdir(contracts_dir)

    # Extract zip to a temp folder under run_dir to keep artifacts self-contained
    extract_dir = run_dir / "_extracted_dataset"
    _safe_mkdir(extract_dir)
    with zipfile.ZipFile(dataset_zip) as zf:
        zf.extractall(extract_dir)

    # Scan extracted dataset
    states_map, attrs_map = _scan_dataset(extract_dir)

    # Build pairs
    pairs: List[Tuple[RunKey, Path, Path]] = []
    for rk, sp in states_map.items():
        apath = attrs_map.get(rk)
        if apath is None:
            continue
        if args.algo and rk.algo != args.algo:
            continue
        if args.device and rk.device != args.device:
            continue
        if args.shots and str(rk.shots) != str(args.shots):
            continue
        pairs.append((rk, sp, apath))

    # Inventory across full dataset (not only filtered) for recommendations
    all_pairs = [(rk, sp, attrs_map[rk]) for rk, sp in states_map.items() if rk in attrs_map]
    inv = _compute_inventory(all_pairs)
    inv_path = tables_dir / "inventory.csv"
    inv.to_csv(inv_path, index=False)

    # Recommendations top 10
    rec = []
    if not inv.empty:
        # Simple mechanical score: pairs * log(1+instances) * log(1+depth_distinct)
        score = inv["n_pairs"] * np.log1p(inv["n_instances"]) * np.log1p(inv["n_depth_distinct"])
        inv2 = inv.copy()
        inv2["score"] = score
        inv2 = inv2.sort_values("score", ascending=False).head(10)
        rec = inv2.to_dict(orient="records")
    rec_path = tables_dir / "recommendations.json"
    rec_path.write_text(json.dumps({"top10": rec}, indent=2), encoding="utf-8")

    # If no filtered pairs, still write minimal outputs
    ccl_rows = []
    tstar_rows = []

    for rk, sp, apath in pairs:
        df_s = _read_states_csv(sp)
        df_a = _read_attr_csv(apath)
        depth = _pick_depth(df_a)
        if depth is None:
            continue
        ccl = _metric_value(df_s, args.metric)
        ccl_rows.append({
            "algo": rk.algo,
            "device": rk.device,
            "shots": rk.shots,
            "instance": rk.instance,
            "t": depth,
            "Ccl": ccl,
        })

    ccl_df = pd.DataFrame(ccl_rows)
    ccl_path = tables_dir / "ccl_timeseries.csv"
    ccl_df.to_csv(ccl_path, index=False)

    # Determine t* per instance: first t where Ccl >= threshold (since higher entropy = more classical)
    if not ccl_df.empty:
        for (dev, inst), g in ccl_df.groupby(["device", "instance"], dropna=False):
            g2 = g.sort_values("t")
            hit = g2[g2["Ccl"] >= args.ccl_threshold]
            if hit.empty:
                tstar_rows.append({"device": dev, "instance": inst, "tstar": float("nan"), "ccl_at_tstar": float("nan")})
            else:
                row = hit.iloc[0]
                tstar_rows.append({"device": dev, "instance": inst, "tstar": float(row["t"]), "ccl_at_tstar": float(row["Ccl"])})
    tstar_df = pd.DataFrame(tstar_rows)
    tstar_path = tables_dir / "tstar_by_instance.csv"
    tstar_df.to_csv(tstar_path, index=False)

    # Bootstrap t* across instances (resampling instances with replacement)
    boot_rows = []
    if not tstar_df.empty and tstar_df["tstar"].notna().any():
        valid = tstar_df[np.isfinite(tstar_df["tstar"].to_numpy(dtype=float))]
        ts = valid["tstar"].to_numpy(dtype=float)
        if ts.size:
            rng = np.random.default_rng(1337)
            for i in range(int(args.bootstrap_samples)):
                sample = rng.choice(ts, size=ts.size, replace=True)
                boot_rows.append({"sample": i, "tstar": float(np.mean(sample))})
    boot_df = pd.DataFrame(boot_rows)
    boot_path = tables_dir / "bootstrap_tstar.csv"
    boot_df.to_csv(boot_path, index=False)

    # Summary
    summary = {
        "run_id": run_id,
        "dataset_zip": str(dataset_zip),
        "algo": args.algo,
        "device": args.device,
        "shots": args.shots,
        "t_axis": args.t_axis,
        "ccl_metric": args.metric,
        "ccl_threshold": args.ccl_threshold,
        "bootstrap_samples": args.bootstrap_samples,
        "n_pairs_filtered": len(pairs),
        "n_points": int(len(ccl_df)),
        "tstar_found_count": int(np.isfinite(tstar_df.get("tstar", pd.Series(dtype=float))).sum()) if not tstar_df.empty else 0,
    }
    (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Minimal plot (matplotlib optional dependency - already in requirements)
    try:
        import matplotlib.pyplot as plt  # type: ignore

        if not ccl_df.empty:
            # mean by t
            g = ccl_df.groupby("t")["Ccl"].mean().reset_index()
            plt.figure()
            plt.plot(g["t"], g["Ccl"])
            plt.xlabel(args.t_axis)
            plt.ylabel("Ccl")
            plt.title(f"Ccl mean ({args.metric})")
            plt.tight_layout()
            plt.savefig(figures_dir / "ccl_mean.png")
            plt.close()

        if not boot_df.empty:
            plt.figure()
            plt.hist(boot_df["tstar"].to_numpy(dtype=float), bins=20)
            plt.xlabel("tstar (bootstrap mean)")
            plt.ylabel("count")
            plt.title("Bootstrap tstar")
            plt.tight_layout()
            plt.savefig(figures_dir / "tstar_hist.png")
            plt.close()
    except Exception as e:
        # Keep pipeline non-blocking on plotting issues
        (tables_dir / "plot_warning.txt").write_text(str(e), encoding="utf-8")

    # Manifest
    from hashlib import sha256
    manifest = {}
    for p in run_dir.rglob("*"):
        if p.is_file():
            h = sha256(p.read_bytes()).hexdigest()
            manifest[str(p.relative_to(run_dir))] = h
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
