#!/usr/bin/env python3
"""
qcc_stateprob_stability_battery.py

Stability battery for QCC StateProb cross-conditions.

Works from the ccl_points.csv produced by a prior densify run —
no re-parsing of raw ZIP data required for resampling, bootstrap,
or windowing. Plan variants are re-sliced from the existing points.

Writes under <run_dir>/stability/:
  resampling/resample_runs.csv
  resampling/resample_summary.json
  bootstrap/bootstrap_by_shots.csv
  bootstrap/bootstrap_summary.json
  windowing/window_metrics.csv
  windowing/window_summary.json
  plan_variants/plan_comparison.csv
  plan_variants/plan_comparison.json
  stability_summary.json
  figures/resample_tstar_hist.png
  figures/window_ccl_profile.png
  figures/plan_comparison.png

Exit code 0 on success, 1 on error.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ── helpers ──────────────────────────────────────────────────────────────────

def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_placeholder(path: Path, title: str, msg: str = "") -> None:
    _ensure_dir(path.parent)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.axis("off")
    ax.text(0.5, 0.6, title, ha="center", va="center", fontsize=13)
    if msg:
        ax.text(0.5, 0.42, msg, ha="center", va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


def _latest_run_dir(out_root: Path) -> Path:
    runs_dir = out_root / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError(f"No runs/ under {out_root}")
    candidates = sorted([p for p in runs_dir.iterdir() if p.is_dir()])
    if not candidates:
        raise FileNotFoundError(f"No run directories in {runs_dir}")
    return candidates[-1]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _tstar(depths: List[float], ccls: List[float], threshold: float) -> Optional[float]:
    if not depths:
        return None
    df = pd.DataFrame({"depth": depths, "ccl": ccls}).sort_values("depth")
    hit = df[df["ccl"] >= threshold]
    return float(hit.iloc[0]["depth"]) if not hit.empty else None


# ── 1. resampling ─────────────────────────────────────────────────────────────

def run_resampling(
    points: pd.DataFrame,
    threshold: float,
    n: int = 50,
    frac: float = 0.7,
    seed: int = 1337,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    rng = np.random.default_rng(seed)
    rows: List[Dict[str, Any]] = []

    for i in range(n):
        sub = points.sample(
            frac=frac, replace=False, random_state=int(rng.integers(0, 2**31))
        ) if len(points) >= 2 else points.copy()

        for shots, g in (sub.groupby("shots") if not sub.empty else []):
            ts = _tstar(g["depth"].tolist(), g["ccl"].tolist(), threshold)
            rows.append(
                {
                    "resample_id": i,
                    "shots": int(shots),
                    "n_points": int(len(g)),
                    "tstar": ts,
                }
            )

    df = (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(columns=["resample_id", "shots", "n_points", "tstar"])
    )

    summary_shots: List[Dict[str, Any]] = []
    for shots, g in (df.groupby("shots") if not df.empty else []):
        vals = g["tstar"].dropna().tolist()
        summary_shots.append(
            {
                "shots": int(shots),
                "n_resamples": int(len(g)),
                "tstar_found_rate": float(g["tstar"].notna().mean()),
                "tstar_mean": float(np.mean(vals)) if vals else None,
                "tstar_std": float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
                "tstar_p10": float(np.percentile(vals, 10)) if vals else None,
                "tstar_p90": float(np.percentile(vals, 90)) if vals else None,
            }
        )

    summary = {
        "n_resamples": n,
        "subsample_frac": frac,
        "threshold": threshold,
        "shots": summary_shots,
    }
    return df, summary


# ── 2. bootstrap ──────────────────────────────────────────────────────────────

def run_bootstrap(
    points: pd.DataFrame,
    threshold: float,
    n: int = 200,
    seed: int = 1337,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    rng = np.random.default_rng(seed)
    rows: List[Dict[str, Any]] = []

    for shots, g in (points.groupby("shots") if not points.empty else []):
        depths = g["depth"].tolist()
        ccls = g["ccl"].tolist()
        idx = np.arange(len(depths))
        for i in range(n):
            sample = rng.choice(idx, size=len(idx), replace=True)
            ts = _tstar([depths[j] for j in sample], [ccls[j] for j in sample], threshold)
            rows.append({"boot_id": i, "shots": int(shots), "tstar": ts})

    df = (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(columns=["boot_id", "shots", "tstar"])
    )

    summary_shots: List[Dict[str, Any]] = []
    for shots, g in (df.groupby("shots") if not df.empty else []):
        vals = g["tstar"].dropna().tolist()
        summary_shots.append(
            {
                "shots": int(shots),
                "n_bootstraps": int(len(g)),
                "tstar_found_rate": float(g["tstar"].notna().mean()),
                "tstar_mean": float(np.mean(vals)) if vals else None,
                "tstar_std": float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
            }
        )

    summary = {"n_bootstraps": n, "threshold": threshold, "shots": summary_shots}
    return df, summary


# ── 3. windowing ──────────────────────────────────────────────────────────────

def run_windowing(
    points: pd.DataFrame,
    window_sizes: List[int],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if points.empty:
        return (
            pd.DataFrame(
                columns=[
                    "shots", "window_size", "window_idx",
                    "depth_min", "depth_max", "ccl_mean", "ccl_std", "n_points",
                ]
            ),
            {"note": "no points available for windowing"},
        )

    rows: List[Dict[str, Any]] = []
    for shots, g in points.groupby("shots"):
        g_sorted = g.sort_values("depth").reset_index(drop=True)
        n = len(g_sorted)
        for W in window_sizes:
            if W > n:
                continue
            for start in range(n - W + 1):
                w = g_sorted.iloc[start : start + W]
                rows.append(
                    {
                        "shots": int(shots),
                        "window_size": int(W),
                        "window_idx": int(start),
                        "depth_min": float(w["depth"].min()),
                        "depth_max": float(w["depth"].max()),
                        "ccl_mean": float(w["ccl"].mean()),
                        "ccl_std": float(w["ccl"].std(ddof=1)) if len(w) > 1 else 0.0,
                        "n_points": int(len(w)),
                    }
                )

    df = (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(
            columns=[
                "shots", "window_size", "window_idx",
                "depth_min", "depth_max", "ccl_mean", "ccl_std", "n_points",
            ]
        )
    )

    windows_summary: List[Dict[str, Any]] = []
    if not df.empty:
        for (shots, W), g in df.groupby(["shots", "window_size"]):
            means = g["ccl_mean"].tolist()
            mu = float(np.mean(means))
            rel_var = float(np.std(means, ddof=1) / mu) if mu > 0 and len(means) > 1 else None
            windows_summary.append(
                {
                    "shots": int(shots),
                    "window_size": int(W),
                    "n_windows": int(len(g)),
                    "ccl_mean_global": mu,
                    "ccl_relative_variation": rel_var,
                }
            )

    summary = {"window_sizes": window_sizes, "windows": windows_summary}
    return df, summary


# ── 4. plan variants ──────────────────────────────────────────────────────────

def run_plan_variants(
    run_dir: Path,
    threshold: float,
    metric: str,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Re-slices existing ccl_points.csv with different (algo, device) selections
    drawn from the run's inventory. No re-parsing of raw dataset.
    """
    points_path = run_dir / "tables" / "ccl_points.csv"
    inv_path = run_dir / "tables" / "inventory.csv"

    if not points_path.exists() or not inv_path.exists():
        note = "ccl_points.csv or inventory.csv missing — skipping plan variants"
        return pd.DataFrame(), {"note": note}

    pts = pd.read_csv(points_path)
    inv = pd.read_csv(inv_path)

    if pts.empty or inv.empty:
        return pd.DataFrame(), {"note": "points or inventory empty"}

    # Build candidate plans from top rows of inventory
    plans: List[Dict[str, str]] = []
    for rank, row in enumerate(inv.itertuples(), start=1):
        plans.append(
            {"name": f"rank{rank}", "algo": str(row.algo), "device": str(row.device)}
        )
        if rank >= 3:  # top-3 only
            break

    compare_rows: List[Dict[str, Any]] = []
    for plan in plans:
        sub = pts[(pts["algo"] == plan["algo"]) & (pts["device"] == plan["device"])]
        tstar_by_shots: Dict[str, Any] = {}
        for shots, g in (sub.groupby("shots") if not sub.empty else []):
            ts = _tstar(g["depth"].tolist(), g["ccl"].tolist(), threshold)
            tstar_by_shots[str(int(shots))] = ts
        compare_rows.append(
            {
                "plan_name": plan["name"],
                "algo": plan["algo"],
                "device": plan["device"],
                "n_points": int(len(sub)),
                "tstar_by_shots": json.dumps(tstar_by_shots),
            }
        )

    df = pd.DataFrame(compare_rows)
    summary = {
        "plans_compared": len(plans),
        "threshold": threshold,
        "metric": metric,
        "note": "Re-sliced from existing ccl_points.csv; no re-parsing of raw dataset.",
        "plans": compare_rows,
    }
    return df, summary


# ── figures ───────────────────────────────────────────────────────────────────

def _plot_resample(df: pd.DataFrame, out: Path) -> None:
    _ensure_dir(out.parent)
    vals = df["tstar"].dropna().to_numpy(dtype=float) if not df.empty else np.array([])
    if vals.size == 0:
        _write_placeholder(out, "No t* found", "All resampling runs: tstar undefined")
        return
    plt.figure(figsize=(7, 4))
    plt.hist(vals, bins=min(25, max(5, int(math.sqrt(vals.size)))))
    plt.xlabel("t* (Depth)")
    plt.ylabel("count")
    plt.title("Resampling — t* distribution (all shots pooled)")
    plt.tight_layout()
    plt.savefig(out, dpi=130)
    plt.close()


def _plot_window(df: pd.DataFrame, out: Path) -> None:
    _ensure_dir(out.parent)
    if df.empty:
        _write_placeholder(out, "No windowing data", "")
        return
    plt.figure(figsize=(8, 5))
    for (shots, W), g in df.groupby(["shots", "window_size"]):
        g = g.sort_values("window_idx")
        plt.plot(
            g["window_idx"].tolist(),
            g["ccl_mean"].tolist(),
            marker="o",
            alpha=0.7,
            label=f"shots={shots} W={W}",
        )
    plt.xlabel("Window index")
    plt.ylabel("CCL mean in window")
    plt.title("Windowing — CCL mean profile")
    plt.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(out, dpi=130)
    plt.close()


def _plot_plan_variants(df: pd.DataFrame, out: Path) -> None:
    _ensure_dir(out.parent)
    if df.empty:
        _write_placeholder(out, "No plan variants", "")
        return
    plt.figure(figsize=(6, 4))
    plt.bar(df["plan_name"].tolist(), df["n_points"].tolist())
    plt.xlabel("Plan")
    plt.ylabel("n_points")
    plt.title("Plan variants — point count")
    plt.tight_layout()
    plt.savefig(out, dpi=130)
    plt.close()


# ── stability criteria check ──────────────────────────────────────────────────

def _check_stability(
    resample_summary: Dict[str, Any],
    window_summary: Dict[str, Any],
    criteria: Dict[str, Any],
) -> Dict[str, Any]:
    checks: Dict[str, Any] = {}

    min_found_rate = float(criteria.get("resample_found_rate_min", 0.5))
    resample_shots = resample_summary.get("shots", [])
    if resample_shots:
        worst_rate = min(float(r.get("tstar_found_rate", 0.0)) for r in resample_shots)
        checks["resample_found_rate"] = {
            "worst_shots_value": worst_rate,
            "threshold": min_found_rate,
            "pass": worst_rate >= min_found_rate,
        }

    max_rel_var = float(criteria.get("relative_variation_max", 0.30))
    window_rows = window_summary.get("windows", [])
    finite_rvs = [
        float(r["ccl_relative_variation"])
        for r in window_rows
        if r.get("ccl_relative_variation") is not None
    ]
    if finite_rvs:
        worst_rv = max(finite_rvs)
        checks["relative_variation"] = {
            "worst_value": worst_rv,
            "threshold": max_rel_var,
            "pass": worst_rv <= max_rel_var,
        }

    all_pass: Optional[bool] = (
        all(v.get("pass", True) for v in checks.values()) if checks else None
    )
    return {"checks": checks, "all_pass": all_pass}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True, help="Output root (contains runs/)")
    ap.add_argument("--run-dir", default="", help="Explicit run dir; if omitted, use latest")
    ap.add_argument("--threshold", type=float, default=0.35, help="CCL threshold for t*")
    ap.add_argument("--metric", default="ccl", help="Metric label (for output annotation only)")
    ap.add_argument("--resamples", type=int, default=50)
    ap.add_argument("--subsample-frac", type=float, default=0.7)
    ap.add_argument("--bootstraps", type=int, default=200)
    ap.add_argument(
        "--window-sizes", default="3,5,7",
        help="Comma-separated depth-point window sizes"
    )
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument(
        "--stability-criteria",
        default="contracts/STABILITY_CRITERIA.json",
        help="Path to STABILITY_CRITERIA.json",
    )
    args = ap.parse_args()

    out_root = Path(args.out_root)
    if args.run_dir:
        run_dir = Path(args.run_dir)
    else:
        try:
            run_dir = _latest_run_dir(out_root)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 1

    points_path = run_dir / "tables" / "ccl_points.csv"
    if not points_path.exists():
        print(f"ccl_points.csv not found: {points_path}", file=sys.stderr)
        return 1

    points = pd.read_csv(points_path)
    threshold = float(args.threshold)
    window_sizes = [
        int(x.strip()) for x in args.window_sizes.split(",") if x.strip().isdigit()
    ]
    criteria = _load_json(Path(args.stability_criteria))

    stab_dir = run_dir / "stability"
    _ensure_dir(stab_dir / "resampling")
    _ensure_dir(stab_dir / "bootstrap")
    _ensure_dir(stab_dir / "windowing")
    _ensure_dir(stab_dir / "plan_variants")
    _ensure_dir(stab_dir / "figures")

    # 1. Resampling
    resample_df, resample_summary = run_resampling(
        points, threshold, n=args.resamples, frac=args.subsample_frac, seed=args.seed
    )
    resample_df.to_csv(stab_dir / "resampling" / "resample_runs.csv", index=False)
    (stab_dir / "resampling" / "resample_summary.json").write_text(
        json.dumps(resample_summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    # 2. Bootstrap
    boot_df, boot_summary = run_bootstrap(
        points, threshold, n=args.bootstraps, seed=args.seed
    )
    boot_df.to_csv(stab_dir / "bootstrap" / "bootstrap_by_shots.csv", index=False)
    (stab_dir / "bootstrap" / "bootstrap_summary.json").write_text(
        json.dumps(boot_summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    # 3. Windowing
    window_df, window_summary = run_windowing(points, window_sizes=window_sizes)
    window_df.to_csv(stab_dir / "windowing" / "window_metrics.csv", index=False)
    (stab_dir / "windowing" / "window_summary.json").write_text(
        json.dumps(window_summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    # 4. Plan variants (re-sliced from existing points)
    variants_df, variants_summary = run_plan_variants(
        run_dir=run_dir, threshold=threshold, metric=args.metric
    )
    variants_df.to_csv(stab_dir / "plan_variants" / "plan_comparison.csv", index=False)
    (stab_dir / "plan_variants" / "plan_comparison.json").write_text(
        json.dumps(variants_summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    # Figures
    _plot_resample(resample_df, stab_dir / "figures" / "resample_tstar_hist.png")
    _plot_window(window_df, stab_dir / "figures" / "window_ccl_profile.png")
    _plot_plan_variants(variants_df, stab_dir / "figures" / "plan_comparison.png")

    # Stability criteria check
    stab_check = _check_stability(resample_summary, window_summary, criteria)

    stability_summary: Dict[str, Any] = {
        "generated_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "run_dir": run_dir.as_posix(),
        "threshold": threshold,
        "metric": args.metric,
        "resampling": {
            "n_resamples": args.resamples,
            "subsample_frac": args.subsample_frac,
            "summary": resample_summary,
        },
        "bootstrap": {
            "n_bootstraps": args.bootstraps,
            "summary": boot_summary,
        },
        "windowing": {
            "window_sizes": window_sizes,
            "summary": window_summary,
        },
        "plan_variants": {
            "run": not variants_df.empty,
            "summary": variants_summary,
        },
        "stability_check": stab_check,
        "criteria_path": args.stability_criteria,
        "note": "Mechanical stability battery. No ORI-C verdict.",
    }
    (stab_dir / "stability_summary.json").write_text(
        json.dumps(stability_summary, indent=2, sort_keys=True), encoding="utf-8"
    )

    print(f"Stability battery complete: {stab_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
