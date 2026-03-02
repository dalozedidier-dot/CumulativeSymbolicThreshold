#!/usr/bin/env python3
"""
QCC/ORI-C State-Probability Cross-Conditions (shots) analysis.

- Accepts dataset as .zip or extracted directory.
- Builds a GLOBAL inventory (all algo/device/shots combos).
- Builds GLOBAL recommendations (Top10).
- Runs cross-conditions analysis for a selected (algo, device) over multiple shots.
  * If --auto-plan true (default): selects best (algo, device) from inventory, then uses all shots for that pair.
  * Else: uses provided --algo and --device-filter (shots optional).

Outputs (under --out-dir/runs/<timestamp>/):
  tables/inventory.csv
  tables/recommendations.json
  tables/selected_plan.json
  tables/ccl_points.csv
  tables/ccl_by_shots.csv
  tables/tstar_by_shots.csv
  tables/bootstrap_tstar_by_shots.csv
  tables/summary.json
  figures/ccl_vs_depth_by_shots.png
  figures/tstar_bootstrap_by_shots.png
  contracts/mapping_cross_conditions.json
  manifest.json

No interpretative verdicts are produced.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


STATES_RE = re.compile(
    r"^STATES_(?P<device>.+?)_(?P<algo>.+?)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$"
)
ATTR_RE = re.compile(
    r"^ATTR_(?P<device>.+?)_(?P<algo>.+?)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$"
)


@dataclass(frozen=True)
class PairKey:
    algo: str
    device: str
    shots: int
    instance: int


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_csv(path: Path, fieldnames: List[str], rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            # Keep only known fields to avoid csv.DictWriter errors
            filtered = {k: r.get(k, "") for k in fieldnames}
            w.writerow(filtered)


def _read_states_csv(p: Path) -> pd.DataFrame:
    """
    Expected either:
      bitstring,prob
    or two unnamed columns.
    """
    df = pd.read_csv(p, header=None)
    if df.shape[1] < 2:
        raise ValueError(f"Invalid STATES csv (need 2 cols): {p}")
    df = df.iloc[:, :2].copy()
    df.columns = ["bitstring", "prob"]
    df["bitstring"] = df["bitstring"].astype(str)
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce").fillna(0.0)
    # Normalize defensively
    s = float(df["prob"].sum())
    if s > 0:
        df["prob"] = df["prob"] / s
    return df


def _read_attr_depth(p: Path) -> float:
    """
    ATTR files are csv with headers that may contain spaces. We only need Depth.
    """
    df = pd.read_csv(p)
    df.columns = [c.strip() for c in df.columns]
    if "Depth" not in df.columns:
        # sometimes 'depth' or 'DEPTH'
        cand = [c for c in df.columns if c.lower() == "depth"]
        if cand:
            df.rename(columns={cand[0]: "Depth"}, inplace=True)
        else:
            raise ValueError(f"ATTR csv missing Depth column: {p} cols={list(df.columns)}")
    # Many ATTR files are single-row
    depth = float(pd.to_numeric(df["Depth"], errors="coerce").dropna().iloc[0])
    return depth


def _ccl_from_probs(df: pd.DataFrame, metric: str) -> float:
    p = df["prob"].to_numpy(dtype=float)
    p = p[p > 0]
    if p.size == 0:
        return float("nan")

    metric = metric.lower().strip()
    if metric == "entropy":
        # Normalize by log(2^n) where n = max bitstring length
        nbits = int(df["bitstring"].map(len).max())
        norm = nbits * math.log(2.0) if nbits > 0 else 1.0
        h = float(-(p * np.log(p)).sum())
        return float(h / norm) if norm > 0 else float("nan")
    if metric == "impurity":
        return float(1.0 - float((p * p).sum()))
    if metric in ("one_minus_max", "1-max", "max"):
        return float(1.0 - float(p.max()))
    raise ValueError(f"Unknown ccl metric: {metric}")


def _find_dataset_root(dataset_path: Path) -> Path:
    """
    Accept either:
      - .zip containing 04-09-2020/<...>
      - directory already extracted (may be 04-09-2020/ or its parent).
    Returns a directory that contains algorithm folders (BV, SIMON, ...).
    """
    if dataset_path.is_dir():
        # if it directly contains algo dirs like BV/
        if any((dataset_path / d).is_dir() for d in ["BV", "SIMON", "QFT", "CHEM", "DJ"]):
            return dataset_path
        # if it contains 04-09-2020/
        cand = dataset_path / "04-09-2020"
        if cand.is_dir():
            return cand
        # else: search one level deep
        for child in dataset_path.iterdir():
            if child.is_dir() and any((child / d).is_dir() for d in ["BV", "SIMON", "QFT", "CHEM", "DJ"]):
                return child
        raise FileNotFoundError(f"Could not locate extracted dataset root under: {dataset_path}")

    if dataset_path.is_file() and dataset_path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="qcc_stateprob_ds_"))
        shutil.unpack_archive(str(dataset_path), str(tmp))
        # Often the zip contains "04-09-2020/"
        if (tmp / "04-09-2020").is_dir():
            return tmp / "04-09-2020"
        # Else if it extracted algo dirs directly
        return tmp

    raise FileNotFoundError(f"dataset_path must be a directory or .zip: {dataset_path}")


def _scan_pairs(dataset_root: Path) -> Tuple[Dict[PairKey, Tuple[Path, Path]], List[str]]:
    """
    Returns mapping PairKey -> (states_path, attr_path)
    and list of problems encountered (non-fatal).
    """
    problems: List[str] = []
    pairs: Dict[PairKey, Tuple[Path, Path]] = {}

    # algo directories are directly under dataset_root
    for algo_dir in sorted([p for p in dataset_root.iterdir() if p.is_dir()]):
        algo = algo_dir.name
        states_dir = algo_dir / "State_Probability"
        attr_dir = algo_dir / "Count_Depth"
        if not states_dir.is_dir() or not attr_dir.is_dir():
            # Some algorithms may have different folder names; skip quietly
            continue

        # Index ATTR files
        attr_index: Dict[Tuple[str, str, int, int], Path] = {}
        for p in attr_dir.glob("ATTR_*.csv"):
            m = ATTR_RE.match(p.name)
            if not m:
                continue
            device = m.group("device")
            algo2 = m.group("algo")
            instance = int(m.group("instance"))
            shots = int(m.group("shots"))
            attr_index[(algo2, device, instance, shots)] = p

        for sp in states_dir.glob("STATES_*.csv"):
            m = STATES_RE.match(sp.name)
            if not m:
                continue
            device = m.group("device")
            algo2 = m.group("algo")
            instance = int(m.group("instance"))
            shots = int(m.group("shots"))

            ap = attr_index.get((algo2, device, instance, shots))
            if ap is None:
                problems.append(f"Missing ATTR for {sp}")
                continue
            key = PairKey(algo=algo2, device=device, shots=shots, instance=instance)
            pairs[key] = (sp, ap)

    return pairs, problems


def _build_inventory(pairs: Dict[PairKey, Tuple[Path, Path]]) -> Tuple[List[Dict], List[Dict]]:
    """
    Returns (inventory_rows, recommendations_top10_rows)
    """
    # Aggregate by (algo, device, shots)
    grouped: Dict[Tuple[str, str, int], Dict] = {}
    for key, (_sp, ap) in pairs.items():
        gk = (key.algo, key.device, key.shots)
        g = grouped.setdefault(gk, {
            "algo": key.algo,
            "device": key.device,
            "shots": key.shots,
            "pairs_count": 0,
            "instances": set(),
            "depths": [],
        })
        g["pairs_count"] += 1
        g["instances"].add(key.instance)
        try:
            depth = _read_attr_depth(ap)
            g["depths"].append(depth)
        except Exception:
            # still count as a pair; depth stats will reflect missing
            pass

    inventory_rows: List[Dict] = []
    for (algo, device, shots), g in grouped.items():
        depths = sorted(set(g["depths"]))
        depth_total = len(depths)
        inst_count = len(g["instances"])
        # Per-instance depth coverage is not derivable without full join; keep global stats.
        # Score favors more pairs/instances/depth coverage.
        score = int(g["pairs_count"]) * 10 + int(inst_count) * 5 + int(depth_total)
        inventory_rows.append({
            "algo": algo,
            "device": device,
            "shots": shots,
            "pairs_count": int(g["pairs_count"]),
            "instances_count": int(inst_count),
            "depth_distinct_total": int(depth_total),
            "depth_min": float(depths[0]) if depths else float("nan"),
            "depth_median": float(np.median(depths)) if depths else float("nan"),
            "depth_max": float(depths[-1]) if depths else float("nan"),
            "score": score,
        })

    # Sort for recommendations
    inventory_sorted = sorted(
        inventory_rows,
        key=lambda r: (r["score"], r["pairs_count"], r["instances_count"], r["depth_distinct_total"]),
        reverse=True,
    )
    top10 = inventory_sorted[:10]
    return inventory_sorted, top10


def _select_autoplan(pairs: Dict[PairKey, Tuple[Path, Path]], inventory_rows: List[Dict]) -> Dict:
    """
    Select best (algo, device) pair from inventory, aggregating across shots.
    """
    # Aggregate inventory across shots
    agg: Dict[Tuple[str, str], Dict] = {}
    for r in inventory_rows:
        k = (r["algo"], r["device"])
        a = agg.setdefault(k, {
            "algo": r["algo"],
            "device": r["device"],
            "shots_available": set(),
            "pairs_total": 0,
            "instances_total": 0,
            "depth_total": 0,
        })
        a["shots_available"].add(int(r["shots"]))
        a["pairs_total"] += int(r["pairs_count"])
        a["instances_total"] += int(r["instances_count"])
        a["depth_total"] += int(r["depth_distinct_total"])

    # Score across shots: emphasize pairs and instance coverage
    scored = []
    for k, a in agg.items():
        score = a["pairs_total"] * 10 + a["instances_total"] * 3 + a["depth_total"]
        scored.append((score, a))
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        raise RuntimeError("No usable (algo,device) pairs found in dataset.")

    best_score, best = scored[0]
    plan = {
        "algo": best["algo"],
        "device": best["device"],
        "shots_list": sorted(best["shots_available"]),
        "score": int(best_score),
        "pairs_total": int(best["pairs_total"]),
        "instances_total": int(best["instances_total"]),
        "depth_total": int(best["depth_total"]),
        "selection_rule": "max(pairs_total*10 + instances_total*3 + depth_total) across (algo,device)",
    }
    return plan


def _filter_pairs(
    pairs: Dict[PairKey, Tuple[Path, Path]],
    algo: Optional[str],
    device: Optional[str],
    shots_list: Optional[List[int]],
) -> Dict[PairKey, Tuple[Path, Path]]:
    out = {}
    for k, v in pairs.items():
        if algo and k.algo != algo:
            continue
        if device and k.device != device:
            continue
        if shots_list and k.shots not in set(shots_list):
            continue
        out[k] = v
    return out


def _compute_cross_conditions(
    pairs_sel: Dict[PairKey, Tuple[Path, Path]],
    metric: str,
    threshold: float,
    bootstrap_samples: int,
    rng_seed: int,
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
    """
    Returns:
      ccl_points_rows
      ccl_by_shots_rows
      tstar_by_shots_rows
      bootstrap_rows
    """
    ccl_points: List[Dict] = []
    for k, (sp, ap) in pairs_sel.items():
        states = _read_states_csv(sp)
        depth = _read_attr_depth(ap)
        ccl = _ccl_from_probs(states, metric=metric)
        ccl_points.append({
            "algo": k.algo,
            "device": k.device,
            "shots": k.shots,
            "instance": k.instance,
            "depth": depth,
            "ccl": ccl,
        })

    # Aggregate mean ccl by (shots, depth)
    df = pd.DataFrame(ccl_points)
    if df.empty:
        return ccl_points, [], [], []

    g = df.groupby(["shots", "depth"], as_index=False)["ccl"].mean()
    ccl_by_shots = g.sort_values(["shots", "depth"]).to_dict(orient="records")

    # t* per shots = smallest depth where mean ccl >= threshold
    tstar_by_shots: List[Dict] = []
    for shots, sub in g.groupby("shots"):
        sub2 = sub.sort_values("depth")
        hit = sub2[sub2["ccl"] >= threshold]
        if hit.empty:
            tstar = float("nan")
            ccl_at = float("nan")
        else:
            tstar = float(hit.iloc[0]["depth"])
            ccl_at = float(hit.iloc[0]["ccl"])
        tstar_by_shots.append({
            "shots": int(shots),
            "tstar": tstar,
            "ccl_at_tstar": ccl_at,
            "threshold": float(threshold),
            "metric": metric,
        })
    tstar_by_shots = sorted(tstar_by_shots, key=lambda r: r["shots"])

    # Bootstrap: resample instances within each shots group
    rng = np.random.default_rng(rng_seed)
    bootstrap_rows: List[Dict] = []
    for shots, sub in df.groupby("shots"):
        # Resample on instance IDs
        inst_ids = sorted(sub["instance"].unique().tolist())
        if len(inst_ids) == 0:
            continue
        for b in range(int(bootstrap_samples)):
            samp = rng.choice(inst_ids, size=len(inst_ids), replace=True)
            sub_samp = sub[sub["instance"].isin(samp)]
            # recompute mean by depth
            gb = sub_samp.groupby("depth", as_index=False)["ccl"].mean().sort_values("depth")
            hit = gb[gb["ccl"] >= threshold]
            tstar = float("nan") if hit.empty else float(hit.iloc[0]["depth"])
            bootstrap_rows.append({
                "shots": int(shots),
                "bootstrap_idx": int(b),
                "tstar": tstar,
            })

    return ccl_points, ccl_by_shots, tstar_by_shots, bootstrap_rows


def _plot_ccl(ccl_by_shots: List[Dict], out_png: Path) -> None:
    df = pd.DataFrame(ccl_by_shots)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        plt.figure()
        plt.title("Ccl vs Depth by shots (no data)")
        plt.savefig(out_png, dpi=160)
        plt.close()
        return

    plt.figure()
    for shots, sub in df.groupby("shots"):
        sub2 = sub.sort_values("depth")
        plt.plot(sub2["depth"], sub2["ccl"], marker="o", label=f"shots={int(shots)}")
    plt.xlabel("Depth")
    plt.ylabel("Ccl")
    plt.title("Ccl vs Depth (mean) by shots")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()


def _plot_bootstrap(bootstrap_rows: List[Dict], out_png: Path) -> None:
    df = pd.DataFrame(bootstrap_rows)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.figure()
    if df.empty:
        plt.title("Bootstrap t* (no data)")
        plt.savefig(out_png, dpi=160)
        plt.close()
        return

    # Plot histogram per shots (overlay)
    for shots, sub in df.groupby("shots"):
        vals = sub["tstar"].dropna().to_numpy()
        if vals.size == 0:
            continue
        plt.hist(vals, alpha=0.5, bins=min(20, max(5, int(vals.size ** 0.5))), label=f"shots={int(shots)}")
    plt.xlabel("t* (Depth)")
    plt.ylabel("count")
    plt.title("Bootstrap distribution of t* by shots")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()


def _make_manifest(run_dir: Path) -> Dict:
    entries = []
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(run_dir).as_posix()
            entries.append({
                "path": rel,
                "sha256": _sha256_file(p),
                "bytes": p.stat().st_size,
            })
    manifest = {
        "schema": "qcc_stateprob_cross_manifest_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-path", required=True, help="Path to dataset .zip or extracted directory.")
    ap.add_argument("--out-dir", required=False, default=None, help="Output directory root (preferred).")
    ap.add_argument("--out-root", required=False, default=None, help="Legacy alias for --out-dir.")
    ap.add_argument("--algo", default="", help="Algorithm filter (e.g., SIMON). Empty means auto/all.")
    ap.add_argument("--device-filter", default="", help="Device filter (e.g., ibmqx2). Empty means auto/all.")
    ap.add_argument("--shots-filter", default="", help="Comma-separated shots list. Empty means all available.")
    ap.add_argument("--metric", default="entropy", choices=["entropy", "impurity", "one_minus_max"], help="Ccl metric.")
    ap.add_argument("--threshold", type=float, default=0.70, help="Threshold for t*.")
    ap.add_argument("--bootstrap-samples", type=int, default=500, help="Bootstrap resamples per shots.")
    ap.add_argument("--seed", type=int, default=1337, help="RNG seed.")
    ap.add_argument("--auto-plan", action="store_true", default=True, help="Auto-select best (algo,device) and all shots.")
    ap.add_argument("--no-auto-plan", dest="auto_plan", action="store_false", help="Disable auto-plan.")

    args = ap.parse_args()

    out_dir = args.out_dir or args.out_root
    if not out_dir:
        print("ERROR: must provide --out-dir (or --out-root).", file=sys.stderr)
        return 2
    out_root = Path(out_dir)

    dataset_path = Path(args.dataset_path)
    ds_root = _find_dataset_root(dataset_path)

    pairs, problems = _scan_pairs(ds_root)

    # GLOBAL inventory and recommendations
    inventory_rows, top10 = _build_inventory(pairs)
    recommendations = {
        "schema": "qcc_stateprob_recommendations_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "topk": top10,
    }

    # Plan selection
    if args.auto_plan:
        plan = _select_autoplan(pairs, inventory_rows)
        algo_sel = plan["algo"]
        dev_sel = plan["device"]
        shots_list = plan["shots_list"]
    else:
        algo_sel = args.algo.strip() or None
        dev_sel = args.device_filter.strip() or None
        shots_list = None
        if args.shots_filter.strip():
            shots_list = [int(x.strip()) for x in args.shots_filter.split(",") if x.strip()]

        plan = {
            "algo": algo_sel or "",
            "device": dev_sel or "",
            "shots_list": shots_list or [],
            "selection_rule": "manual",
        }

    pairs_sel = _filter_pairs(pairs, algo=algo_sel, device=dev_sel, shots_list=shots_list)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / "runs" / ts
    (run_dir / "tables").mkdir(parents=True, exist_ok=True)
    (run_dir / "figures").mkdir(parents=True, exist_ok=True)
    (run_dir / "contracts").mkdir(parents=True, exist_ok=True)

    inv_fields = [
        "algo","device","shots","pairs_count","instances_count","depth_distinct_total",
        "depth_min","depth_median","depth_max","score"
    ]
    _write_csv(run_dir / "tables/inventory.csv", inv_fields, inventory_rows)
    (run_dir / "tables/recommendations.json").write_text(json.dumps(recommendations, indent=2, sort_keys=True), encoding="utf-8")
    (run_dir / "tables/selected_plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")

    # Compute cross-conditions
    ccl_points, ccl_by_shots, tstar_by_shots, bootstrap_rows = _compute_cross_conditions(
        pairs_sel,
        metric=args.metric,
        threshold=float(args.threshold),
        bootstrap_samples=int(args.bootstrap_samples),
        rng_seed=int(args.seed),
    )

    _write_csv(run_dir / "tables/ccl_points.csv",
               ["algo","device","shots","instance","depth","ccl"], ccl_points)
    _write_csv(run_dir / "tables/ccl_by_shots.csv",
               ["shots","depth","ccl"], ccl_by_shots)
    _write_csv(run_dir / "tables/tstar_by_shots.csv",
               ["shots","tstar","ccl_at_tstar","threshold","metric"], tstar_by_shots)
    _write_csv(run_dir / "tables/bootstrap_tstar_by_shots.csv",
               ["shots","bootstrap_idx","tstar"], bootstrap_rows)

    # Figures
    _plot_ccl(ccl_by_shots, run_dir / "figures/ccl_vs_depth_by_shots.png")
    _plot_bootstrap(bootstrap_rows, run_dir / "figures/tstar_bootstrap_by_shots.png")

    # Contracts
    mapping = {
        "schema": "qcc_stateprob_cross_mapping_v1",
        "metric": args.metric,
        "threshold": float(args.threshold),
        "axis": "Depth",
        "auto_plan": bool(args.auto_plan),
        "algo_selected": algo_sel or "",
        "device_selected": dev_sel or "",
        "shots_selected": shots_list or [],
        "bootstrap_samples": int(args.bootstrap_samples),
        "seed": int(args.seed),
        "notes": "Ccl computed from State_Probability distributions; Depth from Count_Depth ATTR files.",
    }
    (run_dir / "contracts/mapping_cross_conditions.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8"
    )

    summary = {
        "schema": "qcc_stateprob_cross_summary_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "dataset_root": str(ds_root),
        "pairs_total": len(pairs),
        "pairs_selected": len(pairs_sel),
        "problems_count": len(problems),
        "plan": plan,
        "metric": args.metric,
        "threshold": float(args.threshold),
        "bootstrap_samples": int(args.bootstrap_samples),
        "counts": {
            "ccl_points": len(ccl_points),
            "ccl_by_shots_rows": len(ccl_by_shots),
            "tstar_by_shots_rows": len(tstar_by_shots),
            "bootstrap_rows": len(bootstrap_rows),
        },
    }
    (run_dir / "tables/summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    _make_manifest(run_dir)

    # Cleanup extracted dataset temp directory if needed
    # If ds_root is under a temp dir created by _find_dataset_root, it will be removed by OS cleanup.
    # We avoid deleting user-provided directories.
    print(f"Wrote run: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
