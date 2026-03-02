\
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

# matplotlib is only used to write PNGs; safe for CI
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


STATES_RE = re.compile(
    r"STATES_(?P<device>[^_]+)_(?P<algo>[A-Z0-9]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$"
)
ATTR_RE = re.compile(
    r"ATTR_(?P<device>[^_]+)_(?P<algo>[A-Z0-9]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$"
)

@dataclass(frozen=True)
class RunKey:
    algo: str
    device: str
    instance: int
    shots: int


def _is_truthy(s: str) -> bool:
    return str(s).strip().lower() in {"1", "true", "yes", "y", "on"}


def _ensure_dataset_root(dataset_path: str) -> Path:
    p = Path(dataset_path)
    if p.is_file() and p.suffix.lower() == ".zip":
        tmp = Path("_ci_out/_tmp_stateprob_extract") / f"extract_{int(time.time())}"
        tmp.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(p, "r") as zf:
            zf.extractall(tmp)
        return tmp
    if p.is_dir():
        return p
    # try repo-wide search (limited)
    root = Path(".")
    candidates: List[Path] = []
    for cand in root.rglob(p.name):
        candidates.append(cand)
        if len(candidates) >= 5:
            break
    if candidates:
        c = candidates[0]
        if c.is_file() and c.suffix.lower() == ".zip":
            return _ensure_dataset_root(str(c))
        if c.is_dir():
            return c
    raise FileNotFoundError(f"dataset_path not found (zip or dir): {dataset_path}")


def _read_states_probs(path: Path) -> List[float]:
    probs: List[float] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.reader(f)
        for row in rdr:
            if not row:
                continue
            # expected: bitstring, probability
            if len(row) < 2:
                continue
            try:
                p = float(row[1])
            except ValueError:
                # skip possible header
                continue
            if p < 0:
                continue
            probs.append(p)
    # normalize defensively
    s = sum(probs)
    if s > 0:
        probs = [p / s for p in probs]
    return probs


def _read_depth(path: Path) -> Optional[int]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        if rdr.fieldnames is None:
            return None
        # normalize column names
        fields = {name.strip().lower(): name for name in rdr.fieldnames}
        depth_field = None
        for cand in ("depth", " Depth", "Depth"):
            if cand.strip().lower() in fields:
                depth_field = fields[cand.strip().lower()]
                break
        for row in rdr:
            if depth_field and depth_field in row:
                v = row[depth_field]
                try:
                    return int(float(v))
                except Exception:
                    pass
            # fallback: search any field containing "depth"
            for k, v in row.items():
                if k and "depth" in k.strip().lower():
                    try:
                        return int(float(v))
                    except Exception:
                        continue
            break
    return None


def _ccl_from_probs(probs: List[float], metric: str) -> float:
    metric = metric.strip().lower()
    p = [x for x in probs if x > 0]
    if not p:
        return float("nan")
    if metric == "entropy":
        h = -sum(x * math.log(x) for x in p)
        # normalize by log(K) (purely mechanical; avoids needing n-qubits)
        denom = math.log(max(2, len(p)))
        return float(h / denom) if denom > 0 else 0.0
    if metric == "one_minus_max":
        return float(1.0 - max(p))
    if metric == "one_minus_purity":
        purity = sum(x * x for x in p)
        return float(1.0 - purity)
    raise ValueError(f"unknown metric: {metric}")


def _scan_pairs(dataset_root: Path) -> Tuple[Dict[RunKey, Path], Dict[RunKey, Path]]:
    states: Dict[RunKey, Path] = {}
    attrs: Dict[RunKey, Path] = {}
    for fp in dataset_root.rglob("*.csv"):
        name = fp.name
        m = STATES_RE.match(name)
        if m and "State_Probability" in str(fp.parent):
            key = RunKey(
                algo=m.group("algo"),
                device=m.group("device"),
                instance=int(m.group("instance")),
                shots=int(m.group("shots")),
            )
            states[key] = fp
            continue
        m2 = ATTR_RE.match(name)
        if m2 and ("Count_Depth" in str(fp.parent) or "Runtime" in str(fp.parent) or "Count_Depth" in str(fp)):
            key = RunKey(
                algo=m2.group("algo"),
                device=m2.group("device"),
                instance=int(m2.group("instance")),
                shots=int(m2.group("shots")),
            )
            attrs[key] = fp
    return states, attrs


def _build_inventory(states: Dict[RunKey, Path], attrs: Dict[RunKey, Path]) -> Tuple[List[dict], List[RunKey]]:
    keys = sorted(set(states.keys()) & set(attrs.keys()), key=lambda k: (k.algo, k.device, k.shots, k.instance))
    rows: List[dict] = []
    # map (algo, device, shots) -> stats
    agg: Dict[Tuple[str, str, int], dict] = {}
    for k in keys:
        depth = _read_depth(attrs[k])
        akey = (k.algo, k.device, k.shots)
        d = agg.setdefault(
            akey,
            {"algo": k.algo, "device": k.device, "shots": k.shots, "pairs_count": 0, "instances": set(), "depths": set()},
        )
        d["pairs_count"] += 1
        d["instances"].add(k.instance)
        if depth is not None:
            d["depths"].add(depth)
    for (algo, device, shots), d in agg.items():
        depths = sorted(d["depths"])
        rows.append(
            {
                "algo": algo,
                "device": device,
                "shots": shots,
                "pairs_count": d["pairs_count"],
                "instances_count": len(d["instances"]),
                "depth_distinct_total": len(depths),
                "depth_min": depths[0] if depths else "",
                "depth_max": depths[-1] if depths else "",
            }
        )
    # sort by richness
    rows.sort(key=lambda r: (r["pairs_count"], r["instances_count"], r["depth_distinct_total"]), reverse=True)
    return rows, keys


def _recommend_top10(inventory_rows: List[dict]) -> dict:
    topk = inventory_rows[:10]
    # simple mechanical score
    for r in topk:
        r["score"] = int(r["pairs_count"]) * 100 + int(r["instances_count"]) * 10 + int(r["depth_distinct_total"])
    return {"topk": topk, "scoring": "score = pairs*100 + instances*10 + depth_distinct_total"}


def _select_auto_plan(inventory_rows: List[dict]) -> Tuple[str, str]:
    # pick best (algo, device) aggregated across shots
    agg: Dict[Tuple[str, str], dict] = {}
    for r in inventory_rows:
        key = (r["algo"], r["device"])
        d = agg.setdefault(key, {"algo": r["algo"], "device": r["device"], "pairs": 0, "instances": set(), "depths": set(), "shots": set()})
        d["pairs"] += int(r["pairs_count"])
        d["shots"].add(int(r["shots"]))
        # instances_count is per shots; we can't recover exact set here, but we can approximate with sum
        # still, for selection, pairs+shots+depths is enough and mechanical
        if r["depth_min"] != "":
            d["depths"].add(int(r["depth_min"]))
        if r["depth_max"] != "":
            d["depths"].add(int(r["depth_max"]))
    best = None
    best_score = -1
    for key, d in agg.items():
        score = d["pairs"] * 100 + len(d["shots"]) * 20 + len(d["depths"])
        if score > best_score:
            best_score = score
            best = d
    if best is None:
        raise RuntimeError("No pairs available to build auto plan.")
    return best["algo"], best["device"]


def _parse_shots_filter(s: str) -> Optional[set]:
    s = str(s or "").strip()
    if not s:
        return None
    out = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        out.add(int(part))
    return out


def _write_csv(path: Path, fieldnames: List[str], rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _plot_ccl_by_shots(df_rows: List[dict], out_png: Path) -> None:
    # df_rows expected keys: shots, depth, ccl_mean
    grouped: Dict[int, List[Tuple[int, float]]] = {}
    for r in df_rows:
        try:
            shots = int(r["shots"])
            depth = int(r["depth"])
            ccl = float(r["ccl_mean"])
        except Exception:
            continue
        grouped.setdefault(shots, []).append((depth, ccl))
    plt.figure()
    for shots, pts in sorted(grouped.items(), key=lambda x: x[0]):
        pts = sorted(pts, key=lambda x: x[0])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        plt.plot(xs, ys, marker="o", label=str(shots))
    plt.xlabel("Depth")
    plt.ylabel("Ccl")
    plt.title("Ccl vs Depth by shots")
    plt.legend()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=160, bbox_inches="tight")
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="Path to dataset zip or extracted dir")
    ap.add_argument("--auto-plan", default="true", help="true/false")
    ap.add_argument("--algo", default="", help="Algo filter; ignored if auto-plan=true")
    ap.add_argument("--device-filter", default="", help="Device filter; ignored if auto-plan=true")
    ap.add_argument("--shots-filter", default="", help="Comma-separated shots; empty=all")
    ap.add_argument("--metric", default="entropy")
    ap.add_argument("--threshold", type=float, default=0.70)
    ap.add_argument("--bootstrap-samples", type=int, default=500)
    ap.add_argument("--out-dir", required=False, default="")
    ap.add_argument("--out-root", required=False, default="")  # legacy alias
    args = ap.parse_args()

    out_dir = args.out_dir or args.out_root
    if not out_dir:
        raise SystemExit("Missing --out-dir (or legacy --out-root)")
    out_root = Path(out_dir)

    dataset_root = _ensure_dataset_root(args.dataset)
    states, attrs = _scan_pairs(dataset_root)
    inventory_rows, pair_keys = _build_inventory(states, attrs)
    recommendations = _recommend_top10(inventory_rows)

    # Decide filters
    auto_plan = _is_truthy(args.auto_plan)
    if auto_plan:
        algo_sel, device_sel = _select_auto_plan(inventory_rows)
        shots_set = None  # compare all available shots for that algo+device
        selection = {"mode": "auto_plan", "algo": algo_sel, "device": device_sel, "shots": "ALL"}
    else:
        algo_sel = args.algo.strip().upper() if args.algo else ""
        device_sel = args.device_filter.strip() if args.device_filter else ""
        shots_set = _parse_shots_filter(args.shots_filter)
        selection = {"mode": "manual", "algo": algo_sel or "ALL", "device": device_sel or "ALL", "shots": sorted(list(shots_set)) if shots_set else "ALL"}

    # Prepare run dir
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_dir = out_root / "runs" / ts
    (run_dir / "tables").mkdir(parents=True, exist_ok=True)
    (run_dir / "figures").mkdir(parents=True, exist_ok=True)
    (run_dir / "contracts").mkdir(parents=True, exist_ok=True)

    # Write inventory + recommendations always (global)
    inv_fields = ["algo","device","shots","pairs_count","instances_count","depth_distinct_total","depth_min","depth_max"]
    _write_csv(run_dir / "tables/inventory.csv", inv_fields, inventory_rows)
    (run_dir / "tables/recommendations.json").write_text(json.dumps(recommendations, indent=2), encoding="utf-8")
    (run_dir / "tables/selected_plan.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")

    # Build points for selection
    points: List[dict] = []
    for k in pair_keys:
        if algo_sel and k.algo != algo_sel:
            continue
        if device_sel and k.device != device_sel:
            continue
        if shots_set and k.shots not in shots_set:
            continue
        depth = _read_depth(attrs[k])
        if depth is None:
            continue
        probs = _read_states_probs(states[k])
        ccl = _ccl_from_probs(probs, args.metric)
        points.append({"algo": k.algo, "device": k.device, "shots": k.shots, "instance": k.instance, "depth": depth, "ccl": ccl})
    _write_csv(run_dir / "tables/ccl_points.csv", ["algo","device","shots","instance","depth","ccl"], points)

    # Aggregate by shots+depth
    agg: Dict[Tuple[int,int], List[float]] = {}
    inst_by_shots: Dict[int, set] = {}
    for r in points:
        key = (int(r["shots"]), int(r["depth"]))
        agg.setdefault(key, []).append(float(r["ccl"]))
        inst_by_shots.setdefault(int(r["shots"]), set()).add(int(r["instance"]))
    ccl_by_shots_rows: List[dict] = []
    for (shots, depth), vals in sorted(agg.items(), key=lambda x: (x[0][0], x[0][1])):
        ccl_by_shots_rows.append({"shots": shots, "depth": depth, "ccl_mean": float(np.mean(vals)), "ccl_std": float(np.std(vals)), "n": len(vals)})
    _write_csv(run_dir / "tables/ccl_by_shots.csv", ["shots","depth","ccl_mean","ccl_std","n"], ccl_by_shots_rows)

    # tstar by shots: first depth where ccl_mean >= threshold
    tstar_rows: List[dict] = []
    by_shots_depth: Dict[int, List[Tuple[int,float]]] = {}
    for r in ccl_by_shots_rows:
        by_shots_depth.setdefault(int(r["shots"]), []).append((int(r["depth"]), float(r["ccl_mean"])))
    for shots, pts in sorted(by_shots_depth.items(), key=lambda x: x[0]):
        pts = sorted(pts, key=lambda x: x[0])
        tstar = float("nan")
        ccl_at = float("nan")
        for depth, cclm in pts:
            if cclm >= args.threshold:
                tstar = depth
                ccl_at = cclm
                break
        tstar_rows.append({"shots": shots, "tstar": tstar, "ccl_at_tstar": ccl_at, "threshold": args.threshold, "points": len(pts), "instances": len(inst_by_shots.get(shots,set()))})
    _write_csv(run_dir / "tables/tstar_by_shots.csv", ["shots","tstar","ccl_at_tstar","threshold","points","instances"], tstar_rows)

    # Bootstrap tstar by shots by resampling points at each depth (conservative: resample instances isn't feasible when 1 depth per instance)
    boot_rows: List[dict] = []
    rng = np.random.default_rng(12345)
    for shots, pts in sorted(by_shots_depth.items(), key=lambda x: x[0]):
        pts = sorted(pts, key=lambda x: x[0])
        if not pts:
            boot_rows.append({"shots": shots, "bootstrap_samples": args.bootstrap_samples, "tstar_mean": float("nan"), "tstar_min": float("nan"), "tstar_max": float("nan")})
            continue
        depths = np.array([d for d,_ in pts], dtype=float)
        ccls = np.array([c for _,c in pts], dtype=float)
        tstars = []
        for _ in range(int(args.bootstrap_samples)):
            idx = rng.integers(0, len(pts), size=len(pts))
            samp = sorted(zip(depths[idx], ccls[idx]), key=lambda x: x[0])
            t = float("nan")
            for d,c in samp:
                if c >= args.threshold:
                    t = d
                    break
            tstars.append(t)
        # filter nan
        tstars_clean = [t for t in tstars if not (isinstance(t,float) and math.isnan(t))]
        if tstars_clean:
            boot_rows.append({
                "shots": shots,
                "bootstrap_samples": int(args.bootstrap_samples),
                "tstar_mean": float(np.mean(tstars_clean)),
                "tstar_min": float(np.min(tstars_clean)),
                "tstar_max": float(np.max(tstars_clean)),
                "tstar_found_frac": float(len(tstars_clean)/len(tstars)),
            })
        else:
            boot_rows.append({
                "shots": shots,
                "bootstrap_samples": int(args.bootstrap_samples),
                "tstar_mean": float("nan"),
                "tstar_min": float("nan"),
                "tstar_max": float("nan"),
                "tstar_found_frac": 0.0,
            })
    _write_csv(run_dir / "tables/bootstrap_tstar_by_shots.csv", ["shots","bootstrap_samples","tstar_mean","tstar_min","tstar_max","tstar_found_frac"], boot_rows)

    # Plot
    _plot_ccl_by_shots(ccl_by_shots_rows, run_dir / "figures/ccl_vs_axis_by_shots.png")

    # summary.json
    summary = {
        "dataset_path": args.dataset,
        "selection": selection,
        "metric": args.metric,
        "threshold": args.threshold,
        "bootstrap_samples": int(args.bootstrap_samples),
        "n_pairs_total": int(len(pair_keys)),
        "n_points_selected": int(len(points)),
        "n_shots_selected": int(len(by_shots_depth)),
        "generated_at": ts,
    }
    (run_dir / "tables/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Minimal manifest (sha256) for run outputs (mechanical)
    import hashlib
    man = {"sha256": {}, "root": str(run_dir)}
    for fp in run_dir.rglob("*"):
        if fp.is_file():
            h = hashlib.sha256()
            with fp.open("rb") as f:
                for chunk in iter(lambda: f.read(1024*1024), b""):
                    h.update(chunk)
            rel = str(fp.relative_to(run_dir)).replace("\\","/")
            man["sha256"][rel] = h.hexdigest()
    (run_dir / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")

    # contracts snapshot
    mapping = {
        "definitions": {
            "Ccl": f"metric({args.metric}) computed from State_Probability distribution p(x).",
            "t_axis": "Depth from ATTR files.",
            "tstar": f"first Depth where mean Ccl >= {args.threshold}",
            "bootstrap": "resample points (Depth,Ccl) with replacement per shots; compute tstar distribution (mechanical).",
        },
        "notes": [
            "This is a non-interpretive diagnostic run: it does not assert algorithmic success/failure.",
            "Auto-plan selects (algo,device) with maximal data richness across shots.",
        ],
    }
    (run_dir / "contracts/mapping_cross_conditions.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")

    print(f"OK: wrote run to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
