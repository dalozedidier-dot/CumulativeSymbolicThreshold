#!/usr/bin/env python3
import argparse
import json
import math
import os
import re
import shutil
import statistics
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

# -----------------------------
# Helpers
# -----------------------------

def _is_blank(x: Optional[str]) -> bool:
    if x is None:
        return True
    s = str(x).strip()
    return s == "" or s.lower() == "nan" or s.lower() == "none"

def _safe_float(x: str, default: float) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def _extract_if_zip(dataset_path: Path, work_dir: Path) -> Path:
    """Return directory containing extracted dataset."""
    if dataset_path.is_dir():
        return dataset_path

    if dataset_path.is_file() and dataset_path.suffix.lower() == ".zip":
        _ensure_dir(work_dir)
        marker = work_dir / ".extracted_ok"
        if not marker.exists():
            with zipfile.ZipFile(dataset_path, "r") as zf:
                zf.extractall(work_dir)
            marker.write_text("ok", encoding="utf-8")
        return work_dir

    raise FileNotFoundError(f"Dataset path not found or unsupported: {dataset_path}")

# Filenames examples:
# STATES_ibmqx2_BV_0_8192.csv
# ATTR_ibmqx2_BV_0_8192.csv
_RE = re.compile(r"^(STATES|ATTR)_(?P<device>.+?)_(?P<algo>.+?)_(?P<instance>\d+?)_(?P<shots>\d+)\.csv$", re.IGNORECASE)

@dataclass(frozen=True)
class RunKey:
    algo: str
    device: str
    shots: int
    instance: int

def _parse_name(fname: str) -> Optional[Tuple[str, str, int, int, str]]:
    m = _RE.match(Path(fname).name)
    if not m:
        return None
    kind = m.group(1).upper()
    device = m.group("device")
    algo = m.group("algo")
    instance = int(m.group("instance"))
    shots = int(m.group("shots"))
    return kind, device, shots, instance, algo

def _iter_algo_dirs(root: Path, algo_filter: str) -> List[Path]:
    if not _is_blank(algo_filter):
        d = root / algo_filter
        return [d] if d.exists() and d.is_dir() else []
    # all algos = directories at root level
    return [p for p in root.iterdir() if p.is_dir()]

def _collect_pairs(root: Path, algo_filter: str, device_filter: str, shots_filter: str) -> Dict[RunKey, Dict[str, Path]]:
    pairs: Dict[RunKey, Dict[str, Path]] = {}
    for algo_dir in _iter_algo_dirs(root, algo_filter):
        algo_name = algo_dir.name
        states_dir = algo_dir / "State_Probability"
        attr_dir = algo_dir / "Count_Depth"
        if not states_dir.exists() or not attr_dir.exists():
            continue

        for p in list(states_dir.glob("STATES_*.csv")) + list(attr_dir.glob("ATTR_*.csv")):
            parsed = _parse_name(p.name)
            if not parsed:
                continue
            kind, device, shots, instance, algo_from_name = parsed
            # prefer folder name as algo to be consistent
            algo = algo_name if algo_name else algo_from_name

            if not _is_blank(device_filter) and device_filter not in device:
                continue
            if not _is_blank(shots_filter):
                if str(shots) != str(shots_filter).strip():
                    continue

            rk = RunKey(algo=algo, device=device, shots=shots, instance=instance)
            pairs.setdefault(rk, {})
            pairs[rk][kind] = p
    # keep only keys with at least one file (later filtered)
    return pairs

def _read_states_prob_csv(path: Path) -> pd.DataFrame:
    """Return df with columns: bitstring, prob."""
    df = pd.read_csv(path, header=None)
    # Some files might have 2 cols; sometimes extra whitespace
    if df.shape[1] < 2:
        raise ValueError(f"Unexpected STATES format: {path} cols={df.shape[1]}")
    df = df.iloc[:, :2]
    df.columns = ["bitstring", "prob"]
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce").fillna(0.0)
    return df

def _read_attr_depth_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # normalize column names
    df.columns = [str(c).strip() for c in df.columns]
    if "Depth" not in df.columns:
        # try common variants
        for cand in ["depth", "DEPTH"]:
            if cand in df.columns:
                df.rename(columns={cand: "Depth"}, inplace=True)
                break
    if "Depth" not in df.columns:
        raise ValueError(f"No Depth column in ATTR file: {path} columns={list(df.columns)[:20]}")
    df["Depth"] = pd.to_numeric(df["Depth"], errors="coerce")
    df = df.dropna(subset=["Depth"])
    return df

def _ccl_from_probs(probs: np.ndarray, metric: str) -> float:
    probs = np.asarray(probs, dtype=float)
    probs = probs[probs > 0]
    if probs.size == 0:
        return float("nan")
    s = probs.sum()
    if s <= 0:
        return float("nan")
    probs = probs / s

    metric = metric.strip().lower()
    if metric == "entropy":
        h = -np.sum(probs * np.log(probs + 1e-15))
        # normalize by log(K)
        k = max(2, probs.size)
        return float(h / math.log(k))
    if metric == "impurity":
        return float(1.0 - np.sum(probs ** 2))
    if metric in ("1-max", "1_max", "1max"):
        return float(1.0 - np.max(probs))
    raise ValueError(f"Unknown ccl_metric: {metric}")

def _compute_inventory(root: Path) -> Tuple[pd.DataFrame, dict]:
    pairs_all = _collect_pairs(root, algo_filter="", device_filter="", shots_filter="")
    # compute per runkey whether both exist
    rows = []
    per_combo: Dict[Tuple[str, str, int], Dict[str, object]] = {}
    for rk, files in pairs_all.items():
        if "ATTR" not in files or "STATES" not in files:
            continue
        combo = (rk.algo, rk.device, rk.shots)
        per_combo.setdefault(combo, {"instances": set(), "depth_counts": [], "depth_values": set()})
        per_combo[combo]["instances"].add(rk.instance)

        # depth distinct for this instance
        try:
            df_attr = _read_attr_depth_csv(files["ATTR"])
            dvals = sorted(set(int(x) for x in df_attr["Depth"].astype(int).tolist()))
            per_combo[combo]["depth_counts"].append(len(set(dvals)))
            for dv in dvals:
                per_combo[combo]["depth_values"].add(dv)
        except Exception:
            # if attr unreadable, still count pair but depth unknown
            per_combo[combo]["depth_counts"].append(0)

    for (algo, device, shots), info in per_combo.items():
        depth_counts = info["depth_counts"] or [0]
        rows.append({
            "algo": algo,
            "device": device,
            "shots": shots,
            "pairs_count": int(len(depth_counts)),
            "instances_count": int(len(info["instances"])),
            "depth_distinct_total": int(len(info["depth_values"])),
            "depth_distinct_min": int(min(depth_counts)),
            "depth_distinct_median": float(statistics.median(depth_counts)),
            "depth_distinct_max": int(max(depth_counts)),
        })

    inv = pd.DataFrame(rows).sort_values(["pairs_count", "instances_count", "depth_distinct_total"], ascending=False)
    # recommendations top10 by a mechanical score
    top = []
    for _, r in inv.head(200).iterrows():
        score = int(r["pairs_count"])*100000 + int(r["instances_count"])*1000 + int(r["depth_distinct_total"])
        top.append({
            "algo": r["algo"],
            "device": r["device"],
            "shots": int(r["shots"]),
            "pairs_count": int(r["pairs_count"]),
            "instances_count": int(r["instances_count"]),
            "depth_distinct_total": int(r["depth_distinct_total"]),
            "score": score,
        })
    top = sorted(top, key=lambda x: x["score"], reverse=True)[:10]
    rec = {"topk": top}
    return inv, rec

def _make_manifest(root: Path) -> dict:
    import hashlib
    items = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            items.append({"path": str(p.relative_to(root)), "sha256": h, "bytes": p.stat().st_size})
    return {"files": items}

# -----------------------------
# Main
# -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Path to dataset zip or extracted directory")
    ap.add_argument("--algo", default="", help="Algorithm folder (empty = all)")
    ap.add_argument("--device-filter", default="", help="Device substring filter (empty = all)")
    ap.add_argument("--shots-filter", default="", help="Shots filter (empty = all)")
    ap.add_argument("--t-axis", default="Depth", choices=["Depth", "Runtime"])
    ap.add_argument("--ccl-metric", default="entropy", choices=["entropy", "impurity", "1-max"])
    ap.add_argument("--ccl-threshold", default="0.70")
    ap.add_argument("--bootstrap-samples", default="500")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--out-root", default="", help="Legacy alias of --out-dir")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if _is_blank(str(out_dir)) and not _is_blank(args.out_root):
        out_dir = Path(args.out_root)
    _ensure_dir(out_dir)

    # create run folder
    run_id = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
    run_root = out_dir / "runs" / run_id
    _ensure_dir(run_root)
    tables = run_root / "tables"
    figs = run_root / "figures"
    contracts = run_root / "contracts"
    _ensure_dir(tables); _ensure_dir(figs); _ensure_dir(contracts)

    # extract dataset
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise FileNotFoundError(f"dataset not found: {dataset_path}")
    extracted = _extract_if_zip(dataset_path, run_root / "_dataset_extracted")

    # dataset root might contain a top-level folder like 04-09-2020
    # If extracted contains only one dir, use it.
    subdirs = [p for p in extracted.iterdir() if p.is_dir()]
    data_root = extracted
    if len(subdirs) == 1:
        data_root = subdirs[0]

    # inventory across ALL dataset (ignore filters)
    inv, rec = _compute_inventory(data_root)
    inv.to_csv(tables / "inventory.csv", index=False)
    (tables / "recommendations.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")

    # collect filtered pairs for analysis
    pairs = _collect_pairs(data_root, algo_filter=args.algo, device_filter=args.device_filter, shots_filter=args.shots_filter)
    # keep only complete pairs
    complete = [(rk, files) for rk, files in pairs.items() if "ATTR" in files and "STATES" in files]
    # build timeseries per instance, axis = depth (or runtime) but we implement Depth only for now
    ccl_rows = []
    tstar_rows = []
    thr = _safe_float(str(args.ccl_threshold), 0.7)

    for rk, files in sorted(complete, key=lambda x: (x[0].algo, x[0].device, x[0].shots, x[0].instance)):
        df_states = _read_states_prob_csv(files["STATES"])
        df_attr = _read_attr_depth_csv(files["ATTR"])
        # assume one depth per ATTR file or take median
        depth_vals = df_attr["Depth"].astype(float).values
        if depth_vals.size == 0:
            continue
        t_val = float(np.median(depth_vals))
        ccl = _ccl_from_probs(df_states["prob"].values, args.ccl_metric)
        ccl_rows.append({
            "algo": rk.algo,
            "device": rk.device,
            "shots": rk.shots,
            "instance": rk.instance,
            "t": t_val,
            "Ccl": ccl,
            "states_file": str(files["STATES"].name),
            "attr_file": str(files["ATTR"].name),
        })

    df_ccl = pd.DataFrame(ccl_rows)
    if not df_ccl.empty:
        df_ccl = df_ccl.sort_values(["algo","device","shots","instance","t"])

    df_ccl.to_csv(tables / "ccl_timeseries.csv", index=False)

    # t* detection per instance (first t where Ccl >= threshold)
    if not df_ccl.empty:
        for (algo, device, shots, instance), g in df_ccl.groupby(["algo","device","shots","instance"]):
            g = g.sort_values("t")
            tstar = float("nan")
            ccl_at = float("nan")
            for _, row in g.iterrows():
                if not (pd.isna(row["Ccl"])) and float(row["Ccl"]) >= thr:
                    tstar = float(row["t"])
                    ccl_at = float(row["Ccl"])
                    break
            tstar_rows.append({
                "algo": algo,
                "device": device,
                "shots": int(shots),
                "instance": int(instance),
                "tstar": tstar,
                "ccl_at_tstar": ccl_at,
                "threshold": thr,
            })

    df_tstar = pd.DataFrame(tstar_rows)
    df_tstar.to_csv(tables / "tstar_by_instance.csv", index=False)

    # bootstrap tstar (resample instances within each (algo,device,shots))
    bs_rows = []
    bs_n = int(_safe_float(str(args.bootstrap_samples), 500))
    if not df_tstar.empty:
        for (algo, device, shots), g in df_tstar.groupby(["algo","device","shots"]):
            vals = g["tstar"].dropna().values.astype(float)
            if vals.size == 0:
                # still emit empty bootstrap rows
                continue
            rng = np.random.default_rng(1337)
            for i in range(bs_n):
                sample = rng.choice(vals, size=vals.size, replace=True)
                bs_rows.append({
                    "algo": algo,
                    "device": device,
                    "shots": int(shots),
                    "bootstrap_i": i,
                    "tstar": float(np.mean(sample)),
                })
    df_bs = pd.DataFrame(bs_rows)
    df_bs.to_csv(tables / "bootstrap_tstar.csv", index=False)

    # figures
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # mean Ccl vs t per (algo,device,shots)
    if not df_ccl.empty:
        for (algo, device, shots), g in df_ccl.groupby(["algo","device","shots"]):
            gg = g.groupby("t")["Ccl"].mean().reset_index().sort_values("t")
            plt.figure()
            plt.plot(gg["t"].values, gg["Ccl"].values)
            plt.axhline(thr, linestyle="--")
            plt.xlabel("t")
            plt.ylabel("Ccl")
            plt.title(f"{algo} {device} shots={shots} metric={args.ccl_metric}")
            outp = figs / f"ccl_mean_{algo}_{device}_{shots}.png"
            plt.savefig(outp, dpi=160, bbox_inches="tight")
            plt.close()

    # histogram of per-instance tstar
    if not df_tstar.empty and df_tstar["tstar"].notna().any():
        plt.figure()
        plt.hist(df_tstar["tstar"].dropna().values, bins=20)
        plt.xlabel("tstar")
        plt.ylabel("count")
        plt.title("tstar distribution (instances)")
        plt.savefig(figs / "tstar_hist.png", dpi=160, bbox_inches="tight")
        plt.close()
    else:
        # still create placeholder
        plt.figure()
        plt.text(0.5,0.5,"No tstar found", ha="center", va="center")
        plt.axis("off")
        plt.savefig(figs / "tstar_hist.png", dpi=160, bbox_inches="tight")
        plt.close()

    # summary
    summary = {
        "algo": args.algo,
        "device_filter": args.device_filter,
        "shots_filter": args.shots_filter,
        "t_axis": args.t_axis,
        "ccl_metric": args.ccl_metric,
        "ccl_threshold": thr,
        "bootstrap_samples": bs_n,
        "n_pairs_filtered": int(len(complete)),
        "n_points": int(df_ccl.shape[0]),
        "tstar_found_count": int(df_tstar["tstar"].notna().sum()) if not df_tstar.empty else 0,
        "inventory_rows": int(inv.shape[0]),
    }
    (tables / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # contracts: save effective mapping
    mapping = {
        "dataset": str(dataset_path),
        "analysis_filters": {"algo": args.algo, "device_filter": args.device_filter, "shots_filter": args.shots_filter},
        "ccl_metric": args.ccl_metric,
        "t_axis": args.t_axis,
        "tstar_rule": "first t where Ccl >= threshold",
        "threshold": thr,
        "bootstrap_samples": bs_n,
        "inventory_scope": "global (ignores filters)",
    }
    (contracts / "mapping.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")

    # manifest over run_root
    manifest = _make_manifest(run_root)
    (run_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
