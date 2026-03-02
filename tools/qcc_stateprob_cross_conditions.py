#!/usr/bin/env python3
"""
QCC / ORI-C StateProb Cross-Conditions

- Ingests a dataset provided either as a .zip archive or as an extracted directory.
- Builds a global inventory and top-K recommendations across (algo, device, shots).
- Runs a cross-conditions analysis (Ccl vs Depth by shots) on either a user-specified plan
  or an auto-selected plan (best data coverage).
- Produces tables, figures, contracts, and a SHA256 manifest (excluding manifest itself).

This script is non-interpretive: it only computes mechanical statistics and does not output
any ORI-C verdict.

Outputs layout (always):
_out/<root>/runs/<timestamp>/
  tables/
    inventory.csv
    recommendations.json
    selected_plan.json
    ccl_points.csv
    ccl_by_shots.csv
    tstar_by_shots.csv
    bootstrap_tstar_by_shots.csv
    summary.json
  figures/
    ccl_vs_axis_by_shots.png
    tstar_hist.png
  contracts/
    mapping_cross_conditions.json
  manifest.json
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import math
import os
import re
import statistics
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Optional deps (installed in CI via requirements)
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Repo-local manifest helper (must be executed as module: python -m tools.qcc_stateprob_cross_conditions)
from tools.make_manifest import build_manifest  # type: ignore


@dataclass(frozen=True)
class Key:
    algo: str
    device: str
    shots: int


def _safe_int(x: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return default
        s = str(x).strip()
        if s == "" or s.lower() == "nan":
            return default
        return int(float(s))
    except Exception:
        return default


def _norm_str(x: Any) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    return s


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _extract_if_zip(dataset_path: Path) -> Path:
    """
    Returns a directory path that contains the extracted dataset.
    - If dataset_path is a directory: returns it.
    - If dataset_path is a .zip: extracts into a temp dir and returns extraction root.
    """
    if dataset_path.is_dir():
        return dataset_path

    if dataset_path.is_file() and dataset_path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="qcc_stateprob_"))
        with zipfile.ZipFile(dataset_path, "r") as zf:
            zf.extractall(tmp)
        # Some zips contain a single top-level folder
        children = [c for c in tmp.iterdir() if c.is_dir()]
        if len(children) == 1:
            return children[0]
        return tmp

    raise FileNotFoundError(f"Dataset path not found or unsupported: {dataset_path}")


_STATES_RE = re.compile(r"^STATES_(?P<device>[^_]+)_(?P<algo>[A-Za-z0-9]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$")
_ATTR_RE = re.compile(r"^ATTR_(?P<device>[^_]+)_(?P<algo>[A-Za-z0-9]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$")


def _discover_pairs(dataset_root: Path) -> List[Tuple[Path, Path, Dict[str, Any]]]:
    """
    Locate matching (STATES, ATTR) pairs. Returns list of (states_path, attr_path, meta)
    where meta has algo, device, instance, shots.
    """
    states_files: Dict[Tuple[str, str, int, int], Path] = {}
    attr_files: Dict[Tuple[str, str, int, int], Path] = {}

    for p in dataset_root.rglob("*.csv"):
        name = p.name
        m = _STATES_RE.match(name)
        if m:
            device = m.group("device")
            algo = m.group("algo")
            instance = int(m.group("instance"))
            shots = int(m.group("shots"))
            states_files[(algo, device, instance, shots)] = p
            continue
        m = _ATTR_RE.match(name)
        if m:
            device = m.group("device")
            algo = m.group("algo")
            instance = int(m.group("instance"))
            shots = int(m.group("shots"))
            attr_files[(algo, device, instance, shots)] = p

    pairs: List[Tuple[Path, Path, Dict[str, Any]]] = []
    for k, sp in states_files.items():
        if k in attr_files:
            algo, device, instance, shots = k
            ap = attr_files[k]
            pairs.append((sp, ap, {"algo": algo, "device": device, "instance": instance, "shots": shots}))
    return pairs


def _read_states_distribution(states_csv: Path) -> pd.DataFrame:
    """
    STATES files are typically 2 columns: bitstring, probability.
    Sometimes there is no header. We'll handle both.
    """
    try:
        df = pd.read_csv(states_csv)
        if df.shape[1] >= 2 and df.columns.tolist()[0] != 0:
            # if header likely present, normalize col names
            cols = df.columns.tolist()
            df = df.rename(columns={cols[0]: "state", cols[1]: "prob"})
        else:
            raise ValueError("No header")
    except Exception:
        df = pd.read_csv(states_csv, header=None)
        if df.shape[1] < 2:
            raise ValueError(f"STATES file has <2 columns: {states_csv}")
        df = df.rename(columns={0: "state", 1: "prob"})
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce").fillna(0.0)
    df = df[df["prob"] >= 0.0]
    s = float(df["prob"].sum())
    if s > 0:
        df["prob"] = df["prob"] / s
    return df[["state", "prob"]]


def _read_attr_depth(attr_csv: Path) -> Optional[float]:
    """
    ATTR files typically have a 'Depth' column.
    We'll accept common variants and return float depth.
    """
    df = pd.read_csv(attr_csv)
    # normalize columns
    cols = {c.strip(): c for c in df.columns}
    depth_col = None
    for cand in ("Depth", "depth", "DEPTH"):
        if cand in cols:
            depth_col = cols[cand]
            break
    if depth_col is None:
        # try fuzzy
        for c in df.columns:
            if "depth" in c.lower():
                depth_col = c
                break
    if depth_col is None:
        return None
    v = df.iloc[0][depth_col]
    try:
        return float(v)
    except Exception:
        return None


def _ccl_from_distribution(df: pd.DataFrame, metric: str) -> float:
    """
    Compute a mechanical classicity proxy from probabilities.
    metric:
      - 'entropy': normalized Shannon entropy in [0,1]
      - 'impurity': 1 - sum(p^2)
      - 'one_minus_max': 1 - max(p)
    """
    p = df["prob"].to_numpy(dtype=float)
    p = p[p > 0]
    if p.size == 0:
        return float("nan")

    metric = metric.lower().strip()
    if metric == "entropy":
        h = float(-(p * np.log(p)).sum())
        # normalize by log(K) where K is number of non-zero states
        denom = float(np.log(max(2, p.size)))
        return h / denom if denom > 0 else 0.0
    if metric == "impurity":
        return float(1.0 - (p * p).sum())
    if metric in ("one_minus_max", "1-max", "oneminusmax"):
        return float(1.0 - p.max())
    raise ValueError(f"Unknown ccl metric: {metric}")


def _build_inventory(pairs: List[Tuple[Path, Path, Dict[str, Any]]]) -> pd.DataFrame:
    rows = []
    # For depth distinct counts we need to read depth quickly. Cache.
    depth_cache: Dict[Path, Optional[float]] = {}

    for sp, ap, meta in pairs:
        algo = meta["algo"]; device = meta["device"]; shots = meta["shots"]; instance = meta["instance"]
        if ap not in depth_cache:
            depth_cache[ap] = _read_attr_depth(ap)
        depth = depth_cache[ap]
        rows.append({"algo": algo, "device": device, "shots": int(shots), "instance": int(instance), "depth": depth})

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=[
            "algo","device","shots","pairs_count","instances_count","depth_distinct_total",
            "depth_distinct_min","depth_distinct_median","depth_distinct_max","score"
        ])

    # group and compute stats
    out_rows = []
    for (algo, device, shots), g in df.groupby(["algo","device","shots"], dropna=False):
        pairs_count = int(len(g))
        instances_count = int(g["instance"].nunique())
        depth_distinct_total = int(pd.Series(g["depth"].dropna().unique()).size)

        # depth distinct per instance
        per_inst = []
        for inst, gi in g.groupby("instance"):
            per_inst.append(int(pd.Series(gi["depth"].dropna().unique()).size))
        if len(per_inst) == 0:
            dmin = dmed = dmax = 0
        else:
            dmin = int(min(per_inst))
            dmax = int(max(per_inst))
            dmed = float(statistics.median(per_inst))
        # mechanical score: prioritize coverage and repetitions
        score = pairs_count + instances_count + depth_distinct_total
        out_rows.append({
            "algo": str(algo),
            "device": str(device),
            "shots": int(shots),
            "pairs_count": pairs_count,
            "instances_count": instances_count,
            "depth_distinct_total": depth_distinct_total,
            "depth_distinct_min": dmin,
            "depth_distinct_median": dmed,
            "depth_distinct_max": dmax,
            "score": score,
        })
    out = pd.DataFrame(out_rows).sort_values(
        by=["score","pairs_count","instances_count","depth_distinct_total","algo","device","shots"],
        ascending=[False,False,False,False,True,True,True],
    )
    return out


def _recommendations(inventory: pd.DataFrame, k: int = 10) -> Dict[str, Any]:
    top = inventory.head(k).to_dict(orient="records") if not inventory.empty else []
    return {"topk": top, "k": k, "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z"}


def _select_plan(
    inventory: pd.DataFrame,
    algo: Optional[str],
    device: Optional[str],
    auto_plan: bool,
) -> Dict[str, Any]:
    """
    Plan selection:
    - If algo/device provided, choose those (best shots coverage will be taken later).
    - Else if auto_plan, pick the top row's (algo, device).
    """
    algo = _norm_str(algo) or None
    device = _norm_str(device) or None

    if algo and device:
        return {"mode": "explicit", "algo": algo, "device": device, "reason": "user provided"}
    if auto_plan and not inventory.empty:
        row = inventory.iloc[0]
        return {
            "mode": "auto_plan",
            "algo": str(row["algo"]),
            "device": str(row["device"]),
            "reason": "max score in inventory",
            "selected_score": float(row.get("score", float("nan"))),
            "selected_pairs_count": int(row.get("pairs_count", 0)),
            "selected_instances_count": int(row.get("instances_count", 0)),
            "selected_depth_distinct_total": int(row.get("depth_distinct_total", 0)),
        }
    # fallback: choose first available or empty
    if not inventory.empty:
        row = inventory.iloc[0]
        return {"mode": "fallback", "algo": str(row["algo"]), "device": str(row["device"]), "reason": "fallback first"}
    return {"mode": "empty", "algo": None, "device": None, "reason": "no pairs found"}


def _filter_pairs(
    pairs: List[Tuple[Path, Path, Dict[str, Any]]],
    algo: str,
    device: str,
    shots_filter: Optional[List[int]],
) -> List[Tuple[Path, Path, Dict[str, Any]]]:
    out = []
    shots_set = set(shots_filter) if shots_filter else None
    for sp, ap, meta in pairs:
        if meta["algo"] != algo:
            continue
        if meta["device"] != device:
            continue
        if shots_set is not None and int(meta["shots"]) not in shots_set:
            continue
        out.append((sp, ap, meta))
    return out


def _compute_points(
    pairs: List[Tuple[Path, Path, Dict[str, Any]]],
    metric: str,
) -> pd.DataFrame:
    rows = []
    for sp, ap, meta in pairs:
        depth = _read_attr_depth(ap)
        if depth is None or (isinstance(depth, float) and math.isnan(depth)):
            continue
        dist = _read_states_distribution(sp)
        ccl = _ccl_from_distribution(dist, metric=metric)
        rows.append({
            "algo": meta["algo"],
            "device": meta["device"],
            "shots": int(meta["shots"]),
            "instance": int(meta["instance"]),
            "depth": float(depth),
            "ccl": float(ccl),
            "states_csv": str(sp.as_posix()),
            "attr_csv": str(ap.as_posix()),
        })
    return pd.DataFrame(rows)


def _tstar_for_group(df: pd.DataFrame, threshold: float) -> Tuple[Optional[float], Optional[float]]:
    """
    df: rows with depth, ccl for a given group (e.g., specific shots).
    Define t* as the minimal depth where ccl >= threshold.
    Returns (tstar, ccl_at_tstar).
    """
    if df.empty:
        return (None, None)
    g = df.sort_values("depth")
    hit = g[g["ccl"] >= threshold]
    if hit.empty:
        return (None, None)
    first = hit.iloc[0]
    return (float(first["depth"]), float(first["ccl"]))


def _bootstrap_tstar(depths: List[float], ccls: List[float], threshold: float, n: int, seed: int = 1337) -> List[Optional[float]]:
    rng = np.random.default_rng(seed)
    if len(depths) == 0:
        return [None] * n
    idx = np.arange(len(depths))
    out: List[Optional[float]] = []
    for _ in range(n):
        sample = rng.choice(idx, size=len(idx), replace=True)
        d = [depths[i] for i in sample]
        c = [ccls[i] for i in sample]
        df = pd.DataFrame({"depth": d, "ccl": c})
        tstar, _ = _tstar_for_group(df, threshold)
        out.append(tstar)
    return out


def _write_placeholder_png(path: Path, title: str, subtitle: str) -> None:
    _ensure_dir(path.parent)
    plt.figure(figsize=(7, 4))
    plt.axis("off")
    plt.text(0.5, 0.6, title, ha="center", va="center", fontsize=14)
    plt.text(0.5, 0.45, subtitle, ha="center", va="center", fontsize=10)
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


def _plot_ccl_by_shots(df: pd.DataFrame, out_png: Path, axis_name: str = "Depth") -> None:
    _ensure_dir(out_png.parent)
    if df.empty:
        _write_placeholder_png(out_png, "No data to plot", "ccl_by_shots is empty")
        return
    plt.figure(figsize=(8, 5))
    for shots, g in df.groupby("shots"):
        g = g.sort_values("depth")
        plt.plot(g["depth"], g["ccl_mean"], marker="o", label=f"shots={shots}")
    plt.xlabel(axis_name)
    plt.ylabel("Ccl (metric)")
    plt.title("Ccl vs Depth by shots")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=140)
    plt.close()


def _plot_tstar_hist(df: pd.DataFrame, out_png: Path) -> None:
    _ensure_dir(out_png.parent)
    vals = df["tstar_boot"].dropna().to_numpy(dtype=float) if not df.empty and "tstar_boot" in df.columns else np.array([])
    if vals.size == 0:
        _write_placeholder_png(out_png, "No t* found", "bootstrap_tstar_by_shots has no finite values")
        return
    plt.figure(figsize=(7, 4))
    plt.hist(vals, bins=min(30, max(5, int(math.sqrt(vals.size)))))
    plt.xlabel("t* (Depth)")
    plt.ylabel("count")
    plt.title("Bootstrap distribution of t* (pooled)")
    plt.tight_layout()
    plt.savefig(out_png, dpi=140)
    plt.close()


def _load_power_criteria(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _evidence_strength(
    points_per_shot: Dict[int, int],
    depth_distinct_total: int,
    instances_count: int,
    criteria: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Mechanical "power" diagnostic based purely on counts (no ORI-C verdict).
    Thresholds are loaded from POWER_CRITERIA.json when criteria is provided;
    fallback to conservative defaults otherwise.
    """
    total_points = int(sum(points_per_shot.values()))
    d = int(depth_distinct_total)
    inst = int(instances_count)

    _default_high = {"total_points": 200, "depth_distinct_total": 10, "instances_count": 20}
    _default_med  = {"total_points": 60,  "depth_distinct_total": 6,  "instances_count": 8}

    thresholds = criteria.get("thresholds", {}) if isinstance(criteria, dict) else {}
    h = thresholds.get("high", _default_high)
    m = thresholds.get("medium", _default_med)
    criteria_source = (
        "POWER_CRITERIA.json"
        if isinstance(criteria, dict) and "thresholds" in criteria
        else "defaults"
    )

    if total_points >= h["total_points"] and d >= h["depth_distinct_total"] and inst >= h["instances_count"]:
        strength = "high"
    elif total_points >= m["total_points"] and d >= m["depth_distinct_total"] and inst >= m["instances_count"]:
        strength = "medium"
    else:
        strength = "low"

    diag = {
        "points_per_shot": {str(k): int(v) for k, v in sorted(points_per_shot.items())},
        "total_points": total_points,
        "depth_distinct_total": d,
        "instances_count": inst,
        "thresholds": {"high": h, "medium": m},
        "criteria_source": criteria_source,
        "note": "Purely mechanical diagnostic based on counts only; not an ORI-C verdict.",
    }
    return strength, diag


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", "--dataset-path", dest="dataset", required=True, help="Path to dataset .zip or extracted directory")
    ap.add_argument("--out-dir", dest="out_dir", default="_ci_out/qcc_stateprob_cross", help="Output root directory")
    ap.add_argument("--out-root", dest="out_root", default=None, help="Alias for --out-dir (legacy)")
    ap.add_argument("--auto-plan", dest="auto_plan", action="store_true", help="Auto-select best (algo, device) from inventory")
    ap.add_argument("--no-auto-plan", dest="auto_plan", action="store_false")
    ap.set_defaults(auto_plan=True)

    ap.add_argument("--algo", default="", help="Optional explicit algo (e.g., SIMON)")
    ap.add_argument("--device", default="", help="Optional explicit device (e.g., ibmqx2)")
    ap.add_argument("--shots", default="", help="Optional comma-separated shots list, or empty for all")
    ap.add_argument("--metric", default="entropy", choices=["entropy", "impurity", "one_minus_max"], help="Ccl metric")
    ap.add_argument("--threshold", type=float, default=0.70, help="Ccl threshold for t*")
    ap.add_argument("--bootstrap-samples", type=int, default=500, help="Bootstrap samples")
    ap.add_argument("--seed", type=int, default=1337, help="RNG seed")
    ap.add_argument(
        "--pooling", default="by-instance",
        choices=["by-instance", "pooled-by-depth", "multi-device"],
        help="Pooling strategy for cross-conditions analysis",
    )
    ap.add_argument(
        "--power-criteria", default="contracts/POWER_CRITERIA.json",
        help="Path to POWER_CRITERIA.json (frozen thresholds for evidence_strength)",
    )
    args = ap.parse_args(argv)

    out_root = Path(args.out_root) if args.out_root else Path(args.out_dir)
    dataset_path = Path(args.dataset)

    dataset_root = _extract_if_zip(dataset_path)
    pairs = _discover_pairs(dataset_root)

    run_ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / "runs" / run_ts
    tables_dir = run_dir / "tables"
    figs_dir = run_dir / "figures"
    contracts_dir = run_dir / "contracts"
    _ensure_dir(tables_dir); _ensure_dir(figs_dir); _ensure_dir(contracts_dir)

    # params.txt — written early so it exists even on early-return paths
    _git_sha = "unknown"
    try:
        import subprocess as _sp
        _r = _sp.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        if _r.returncode == 0:
            _git_sha = _r.stdout.strip()
    except Exception:
        pass
    import platform as _platform
    _params_lines = [
        f"generated_utc: {datetime.utcnow().isoformat(timespec='seconds')}Z",
        f"argv: {' '.join(sys.argv)}",
        f"python_version: {sys.version.splitlines()[0]}",
        f"platform: {_platform.platform()}",
        f"pooling_mode: {args.pooling}",
        f"power_criteria: {args.power_criteria}",
        f"git_sha: {_git_sha}",
    ]
    (run_dir / "params.txt").write_text("\n".join(_params_lines) + "\n", encoding="utf-8")

    # Load power criteria from versioned JSON (fallback to defaults if missing)
    power_criteria = _load_power_criteria(Path(args.power_criteria))
    # Copy criteria into run's contracts/ for self-contained auditability
    _criteria_src = Path(args.power_criteria)
    if _criteria_src.exists():
        import shutil as _shutil
        _shutil.copy2(_criteria_src, contracts_dir / "POWER_CRITERIA.json")

    # Inventory and recommendations (global, regardless of filters)
    inv = _build_inventory(pairs)
    inv_path = tables_dir / "inventory.csv"
    inv.to_csv(inv_path, index=False)

    rec = _recommendations(inv, k=10)
    rec_path = tables_dir / "recommendations.json"
    rec_path.write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")

    # Plan selection
    plan = _select_plan(inv, algo=args.algo, device=args.device, auto_plan=bool(args.auto_plan))
    plan_path = tables_dir / "selected_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")

    if not plan.get("algo") or not plan.get("device"):
        # no data found
        _write_placeholder_png(figs_dir / "ccl_vs_axis_by_shots.png", "No data", "No (algo, device) plan available")
        _write_placeholder_png(figs_dir / "tstar_hist.png", "No data", "No (algo, device) plan available")
        summary = {
            "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "plan": plan,
            "metric": args.metric,
            "threshold": args.threshold,
            "bootstrap_samples": args.bootstrap_samples,
            "n_pairs_total": len(pairs),
            "n_points": 0,
            "power_diagnostic": {"evidence_strength": "low", "details": {"reason": "no data"}},
        }
        (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        build_manifest(run_dir, exclude_names={"manifest.json"})
        return 0

    algo = str(plan["algo"])
    device = str(plan["device"])

    shots_filter = None
    if str(args.shots).strip():
        shots_filter = [_safe_int(s, None) for s in str(args.shots).split(",")]
        shots_filter = [s for s in shots_filter if s is not None]

    sel_pairs = _filter_pairs(pairs, algo=algo, device=device, shots_filter=shots_filter)

    # Compute points
    points = _compute_points(sel_pairs, metric=args.metric)

    # Pooling (by-instance is default/no-op; others call the pooling module)
    pool_membership = None
    if args.pooling == "pooled-by-depth":
        from tools import qcc_stateprob_pooling as _pooling  # type: ignore
        points, pool_membership = _pooling.pool_by_depth(points, out_dir=tables_dir)
    elif args.pooling == "multi-device":
        from tools import qcc_stateprob_pooling as _pooling  # type: ignore
        points, pool_membership = _pooling.multi_device_pool(points, out_dir=tables_dir)

    points_path = tables_dir / "ccl_points.csv"
    points.to_csv(points_path, index=False)

    # Aggregate by shots: mean Ccl per depth
    if points.empty:
        ccl_by = pd.DataFrame(columns=["shots","depth","ccl_mean","n_points"])
    else:
        ccl_by = (
            points.groupby(["shots","depth"])
            .agg(ccl_mean=("ccl","mean"), n_points=("ccl","size"))
            .reset_index()
            .sort_values(["shots","depth"])
        )
    ccl_by_path = tables_dir / "ccl_by_shots.csv"
    ccl_by.to_csv(ccl_by_path, index=False)

    # t* by shots
    tstar_rows = []
    for shots, g in points.groupby("shots") if not points.empty else []:
        tstar, c_at = _tstar_for_group(g[["depth","ccl"]], threshold=float(args.threshold))
        tstar_rows.append({"shots": int(shots), "tstar": tstar, "ccl_at_tstar": c_at, "n_points": int(len(g))})
    tstar_df = pd.DataFrame(tstar_rows) if tstar_rows else pd.DataFrame(columns=["shots","tstar","ccl_at_tstar","n_points"])
    tstar_path = tables_dir / "tstar_by_shots.csv"
    tstar_df.to_csv(tstar_path, index=False)

    # Bootstrap pooled by shots
    boot_rows = []
    if not points.empty:
        for shots, g in points.groupby("shots"):
            depths = g["depth"].tolist()
            ccls = g["ccl"].tolist()
            boot = _bootstrap_tstar(depths, ccls, threshold=float(args.threshold), n=int(args.bootstrap_samples), seed=int(args.seed))
            # write one row per sample for pooling/plotting
            for v in boot:
                boot_rows.append({"shots": int(shots), "tstar_boot": v})
    boot_df = pd.DataFrame(boot_rows) if boot_rows else pd.DataFrame(columns=["shots","tstar_boot"])
    boot_path = tables_dir / "bootstrap_tstar_by_shots.csv"
    boot_df.to_csv(boot_path, index=False)

    # Figures (always)
    _plot_ccl_by_shots(ccl_by, figs_dir / "ccl_vs_axis_by_shots.png", axis_name="Depth")
    _plot_tstar_hist(boot_df, figs_dir / "tstar_hist.png")

    # Contracts
    mapping = {
        "dataset": str(dataset_path.as_posix()),
        "dataset_mode": "dir" if Path(args.dataset).is_dir() else "zip",
        "algo": algo,
        "device": device,
        "shots_filter": shots_filter,
        "metric": args.metric,
        "threshold": float(args.threshold),
        "bootstrap_samples": int(args.bootstrap_samples),
        "auto_plan": bool(args.auto_plan),
        "note": "Non-interpretive cross-conditions Ccl vs Depth by shots.",
    }
    (contracts_dir / "mapping_cross_conditions.json").write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")

    # Power diagnostic for summary.json (counts only)
    points_per_shot = {}
    if not points.empty:
        for shots, g in points.groupby("shots"):
            points_per_shot[int(shots)] = int(len(g))
    # depth distinct total (within selected plan)
    depth_distinct_total = int(points["depth"].nunique()) if not points.empty else 0
    instances_count = int(points["instance"].nunique()) if not points.empty else 0
    evidence_strength, power_diag = _evidence_strength(
        points_per_shot, depth_distinct_total, instances_count, criteria=power_criteria
    )

    summary = {
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "plan": plan,
        "metric": args.metric,
        "threshold": float(args.threshold),
        "bootstrap_samples": int(args.bootstrap_samples),
        "seed": int(args.seed),
        "pooling_mode": args.pooling,
        "n_pairs_total": int(len(pairs)),
        "n_pairs_selected": int(len(sel_pairs)),
        "n_points": int(len(points)),
        "shots_included": sorted([int(s) for s in points["shots"].unique().tolist()]) if not points.empty else [],
        "tstar_found_shots_count": int(tstar_df["tstar"].notna().sum()) if not tstar_df.empty else 0,
        "evidence_strength": evidence_strength,
        "power_diagnostic": {
            "evidence_strength": evidence_strength,
            "details": power_diag,
        },
    }
    (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    # Manifest (hash everything in run_dir except manifest.json itself)
    build_manifest(run_dir, exclude_names={"manifest.json"})

    print(f"Wrote run: {run_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
