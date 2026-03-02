#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QCC StateProb Bootstrap (Ccl)
Accepts dataset as a .zip path OR an extracted directory.
Produces inventory.csv and recommendations.json.
No interpretative verdicts.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RunKey:
    algo: str
    device: str
    shots: int
    instance: str


def _is_blank(x) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    s = str(x).strip()
    return s == "" or s.lower() in ("nan", "none")


def _safe_int(x, default: Optional[int] = None) -> Optional[int]:
    if _is_blank(x):
        return default
    try:
        return int(float(str(x).strip()))
    except Exception:
        return default


def _parse_states_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, header=None)
    if df.shape[1] < 2:
        df = pd.read_csv(path)
    df = df.iloc[:, :2].copy()
    df.columns = ["bitstring", "prob"]
    df["bitstring"] = df["bitstring"].astype(str)
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce").fillna(0.0)
    return df


def _parse_attr_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _entropy_norm(probs: np.ndarray) -> float:
    p = probs.astype(float)
    p = p[p > 0]
    if p.size == 0:
        return float("nan")
    H = float(-(p * np.log(p)).sum())
    K = int(p.size)
    denom = math.log(K) if K > 1 else 1.0
    return float(H / denom) if denom != 0 else 0.0


def _impurity(probs: np.ndarray) -> float:
    p = probs.astype(float)
    return float(1.0 - np.sum(p * p))


def _one_minus_max(probs: np.ndarray) -> float:
    p = probs.astype(float)
    if p.size == 0:
        return float("nan")
    return float(1.0 - np.max(p))


def _metric_value(metric: str, probs: np.ndarray) -> float:
    m = metric.strip().lower()
    if m == "entropy":
        return _entropy_norm(probs)
    if m == "impurity":
        return _impurity(probs)
    if m in ("1-max", "one_minus_max", "1max"):
        return _one_minus_max(probs)
    raise ValueError(f"Unknown ccl_metric: {metric}")


_STATES_RE = re.compile(r"STATES_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$", re.IGNORECASE)
_ATTR_RE = re.compile(r"ATTR_(?P<device>[^_]+)_(?P<algo>[^_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$", re.IGNORECASE)


def _collect_pairs(root: Path, algo: str, device_filter: Optional[str], shots_filter: Optional[int]) -> List[Tuple[RunKey, Path, Path]]:
    algo_dir = root / algo
    if not algo_dir.exists():
        raise FileNotFoundError(f"Algorithm folder not found: {algo_dir}")
    sp_dir = algo_dir / "State_Probability"
    cd_dir = algo_dir / "Count_Depth"
    if not sp_dir.exists():
        raise FileNotFoundError(f"Missing folder: {sp_dir}")
    if not cd_dir.exists():
        raise FileNotFoundError(f"Missing folder: {cd_dir}")

    states_files = list(sp_dir.rglob("STATES_*.csv"))
    attr_files = list(cd_dir.rglob("ATTR_*.csv"))

    states_map: Dict[RunKey, Path] = {}
    for p in states_files:
        m = _STATES_RE.search(p.name)
        if not m:
            continue
        rk = RunKey(m.group("algo"), m.group("device"), int(m.group("shots")), m.group("instance"))
        if rk.algo.upper() != algo.upper():
            continue
        if device_filter and rk.device != device_filter:
            continue
        if shots_filter is not None and rk.shots != shots_filter:
            continue
        states_map[rk] = p

    pairs: List[Tuple[RunKey, Path, Path]] = []
    for p in attr_files:
        m = _ATTR_RE.search(p.name)
        if not m:
            continue
        rk = RunKey(m.group("algo"), m.group("device"), int(m.group("shots")), m.group("instance"))
        if rk.algo.upper() != algo.upper():
            continue
        if device_filter and rk.device != device_filter:
            continue
        if shots_filter is not None and rk.shots != shots_filter:
            continue
        sp = states_map.get(rk)
        if sp is None:
            continue
        pairs.append((rk, sp, p))
    return pairs


def _make_inventory(pairs: List[Tuple[RunKey, Path, Path]], t_axis: str) -> pd.DataFrame:
    rows = []
    group: Dict[Tuple[str, str, int], List[Tuple[RunKey, Path, Path]]] = {}
    for rk, sp, ap in pairs:
        group.setdefault((rk.algo, rk.device, rk.shots), []).append((rk, sp, ap))

    for (algo, device, shots), items in group.items():
        inst = sorted({rk.instance for rk, _, _ in items})
        depth_counts = []
        total_depth_distinct = 0
        for rk, _, ap in items:
            adf = _parse_attr_csv(ap)
            if t_axis not in adf.columns:
                continue
            distinct = int(pd.Series(adf[t_axis]).nunique())
            depth_counts.append(distinct)
            total_depth_distinct += distinct
        if depth_counts:
            dmin = int(np.min(depth_counts))
            dmed = float(np.median(depth_counts))
            dmax = int(np.max(depth_counts))
        else:
            dmin, dmed, dmax = 0, float("nan"), 0

        rows.append({
            "algo": algo,
            "device": device,
            "shots": shots,
            "pairs_count": len(items),
            "instances_count": len(inst),
            "depth_distinct_total": total_depth_distinct,
            "depth_distinct_min": dmin,
            "depth_distinct_median": dmed,
            "depth_distinct_max": dmax,
        })

    if not rows:
        return pd.DataFrame(columns=[
            "algo","device","shots","pairs_count","instances_count",
            "depth_distinct_total","depth_distinct_min","depth_distinct_median","depth_distinct_max"
        ])
    return pd.DataFrame(rows).sort_values(
        ["algo","pairs_count","instances_count","depth_distinct_total"],
        ascending=[True, False, False, False],
    )


def _recommendations(inv: pd.DataFrame, topk: int = 10) -> dict:
    if inv.empty:
        return {"topk": [], "note": "inventory empty"}
    score = (
        inv["pairs_count"].astype(float)
        * np.log1p(inv["instances_count"].astype(float))
        * np.log1p(inv["depth_distinct_total"].astype(float))
    )
    inv2 = inv.copy()
    inv2["score"] = score
    inv2 = inv2.sort_values("score", ascending=False).head(topk)
    top = []
    for _, r in inv2.iterrows():
        top.append({
            "algo": r["algo"],
            "device": r["device"],
            "shots": int(r["shots"]),
            "pairs_count": int(r["pairs_count"]),
            "instances_count": int(r["instances_count"]),
            "depth_distinct_total": int(r["depth_distinct_total"]),
            "depth_distinct_min": int(r["depth_distinct_min"]),
            "depth_distinct_median": float(r["depth_distinct_median"]) if not math.isnan(float(r["depth_distinct_median"])) else None,
            "depth_distinct_max": int(r["depth_distinct_max"]),
            "score": float(r["score"]),
        })
    return {"topk": top}


def _compute_ccl_timeseries(pairs: List[Tuple[RunKey, Path, Path]], t_axis: str, metric: str) -> pd.DataFrame:
    out_rows = []
    for rk, sp, ap in pairs:
        sdf = _parse_states_csv(sp)
        ccl = _metric_value(metric, sdf["prob"].to_numpy())
        adf = _parse_attr_csv(ap)
        if t_axis not in adf.columns:
            continue
        t_val = float(pd.to_numeric(adf[t_axis], errors="coerce").dropna().max())
        out_rows.append({
            "algo": rk.algo,
            "device": rk.device,
            "shots": rk.shots,
            "instance": rk.instance,
            "t": t_val,
            "ccl": float(ccl),
        })
    if not out_rows:
        return pd.DataFrame(columns=["algo","device","shots","instance","t","ccl"])
    return pd.DataFrame(out_rows).sort_values(["algo","device","shots","instance","t"]).reset_index(drop=True)


def _tstar_by_instance(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    rows = []
    if df.empty:
        return pd.DataFrame(columns=["algo","device","shots","instance","tstar","ccl_at_tstar","n_points"])
    for (algo, device, shots, instance), g in df.groupby(["algo","device","shots","instance"], sort=False):
        g2 = g.sort_values("t")
        hit = g2[g2["ccl"] >= threshold]
        if hit.empty:
            rows.append({"algo": algo, "device": device, "shots": int(shots), "instance": str(instance),
                         "tstar": float("nan"), "ccl_at_tstar": float("nan"), "n_points": int(len(g2))})
        else:
            r0 = hit.iloc[0]
            rows.append({"algo": algo, "device": device, "shots": int(shots), "instance": str(instance),
                         "tstar": float(r0["t"]), "ccl_at_tstar": float(r0["ccl"]), "n_points": int(len(g2))})
    return pd.DataFrame(rows)


def _bootstrap_tstar(tstar_df: pd.DataFrame, n_boot: int, seed: int = 123) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = []
    if tstar_df.empty:
        return pd.DataFrame(columns=["algo","device","shots","sample","tstar_mean","n_instances"])
    for (algo, device, shots), g in tstar_df.groupby(["algo","device","shots"], sort=False):
        vals = pd.to_numeric(g["tstar"], errors="coerce").to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            for s in range(n_boot):
                out.append({"algo": algo, "device": device, "shots": int(shots), "sample": s,
                            "tstar_mean": float("nan"), "n_instances": 0})
            continue
        for s in range(n_boot):
            samp = rng.choice(vals, size=vals.size, replace=True)
            out.append({"algo": algo, "device": device, "shots": int(shots), "sample": s,
                        "tstar_mean": float(np.mean(samp)), "n_instances": int(vals.size)})
    return pd.DataFrame(out)


def _ensure(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _dataset_root(dataset: Path) -> Tuple[Path, Optional[Path]]:
    if dataset.is_dir():
        return dataset, None
    if dataset.is_file() and dataset.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="qcc_stateprob_"))
        with zipfile.ZipFile(dataset, "r") as zf:
            zf.extractall(tmp)
        children = [p for p in tmp.iterdir() if p.is_dir()]
        if len(children) == 1:
            return children[0], tmp
        return tmp, tmp
    raise FileNotFoundError(f"Dataset path must be a directory or a .zip file: {dataset}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Path to dataset .zip OR extracted directory")
    ap.add_argument("--algo", required=True, help="Algorithm folder (BV, QAOA, ...)")
    ap.add_argument("--device", default="", help="Device filter (empty = all)")
    ap.add_argument("--shots", default="", help="Shots filter (empty = all)")
    ap.add_argument("--t-axis", default="Depth", help="t axis column name (default Depth)")
    ap.add_argument("--ccl-metric", default="entropy", help="entropy | impurity | 1-max")
    ap.add_argument("--threshold", type=float, default=0.70, help="Threshold for t* detection")
    ap.add_argument("--bootstrap", type=int, default=500, help="Bootstrap samples")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    ap.add_argument("--out-root", default="", help="Legacy alias for out-dir")

    args = ap.parse_args()

    out_dir = Path(args.out_dir) if not _is_blank(args.out_dir) else Path(args.out_root)
    _ensure(out_dir)
    tables = out_dir / "tables"
    figs = out_dir / "figures"
    contracts = out_dir / "contracts"
    for p in (tables, figs, contracts):
        _ensure(p)

    dataset_path = Path(args.dataset)
    device_filter = args.device.strip() or None
    shots_filter = _safe_int(args.shots.strip(), None) if args.shots.strip() else None

    root, tmp = _dataset_root(dataset_path)
    try:
        pairs = _collect_pairs(root, args.algo, device_filter, shots_filter)

        inv = _make_inventory(pairs, args.t_axis)
        inv.to_csv(tables / "inventory.csv", index=False)

        rec = _recommendations(inv, topk=10)
        (tables / "recommendations.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")

        df = _compute_ccl_timeseries(pairs, args.t_axis, args.ccl_metric)
        df.to_csv(tables / "ccl_timeseries.csv", index=False)

        tstar = _tstar_by_instance(df, args.threshold)
        tstar.to_csv(tables / "tstar_by_instance.csv", index=False)

        boot = _bootstrap_tstar(tstar, args.bootstrap)
        boot.to_csv(tables / "bootstrap_tstar.csv", index=False)

        summary = {
            "algo": args.algo,
            "device_filter": device_filter or "",
            "shots_filter": shots_filter if shots_filter is not None else "",
            "t_axis": args.t_axis,
            "ccl_metric": args.ccl_metric,
            "ccl_threshold": args.threshold,
            "bootstrap_samples": args.bootstrap,
            "n_pairs": int(len(pairs)),
            "n_points": int(len(df)),
            "tstar_found_count": int(np.isfinite(pd.to_numeric(tstar["tstar"], errors="coerce")).sum()) if not tstar.empty else 0,
        }
        (tables / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        import matplotlib.pyplot as plt

        if df.empty:
            plt.figure(); plt.axis("off"); plt.text(0.5,0.5,"Ccl mean (empty)",ha="center",va="center")
            plt.savefig(figs / "ccl_mean.png", dpi=150, bbox_inches="tight"); plt.close()
        else:
            plt.figure()
            for (algo, device, shots), g in df.groupby(["algo","device","shots"], sort=False):
                gg = g.groupby("t")["ccl"].mean().reset_index().sort_values("t")
                plt.plot(gg["t"].to_numpy(), gg["ccl"].to_numpy(), label=f"{device} shots={shots}")
            plt.xlabel("t"); plt.ylabel("Ccl"); plt.title("Ccl mean vs t"); plt.legend()
            plt.savefig(figs / "ccl_mean.png", dpi=150, bbox_inches="tight"); plt.close()

        vals = pd.to_numeric(tstar["tstar"], errors="coerce").to_numpy(dtype=float) if not tstar.empty else np.array([])
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            plt.figure(); plt.axis("off"); plt.text(0.5,0.5,"t* histogram (no hits)",ha="center",va="center")
            plt.savefig(figs / "tstar_hist.png", dpi=150, bbox_inches="tight"); plt.close()
        else:
            plt.figure()
            plt.hist(vals, bins=min(20, max(5, int(np.sqrt(vals.size)))))
            plt.xlabel("t*"); plt.ylabel("count"); plt.title("t* across instances")
            plt.savefig(figs / "tstar_hist.png", dpi=150, bbox_inches="tight"); plt.close()

        (contracts / "DATA_CONTRACT.md").write_text(
            "Dataset input can be a zip or a directory.\n"
            "Ccl computed from state probability distribution.\n"
            "No interpretative verdicts.\n",
            encoding="utf-8",
        )
        (contracts / "mapping.json").write_text(json.dumps({
            "dataset": str(args.dataset),
            "algo": args.algo,
            "device_filter": device_filter or "",
            "shots_filter": shots_filter if shots_filter is not None else "",
            "t_axis": args.t_axis,
            "ccl_metric": args.ccl_metric,
            "threshold": args.threshold,
            "bootstrap": args.bootstrap,
        }, indent=2), encoding="utf-8")

        return 0
    finally:
        if tmp is not None and tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
