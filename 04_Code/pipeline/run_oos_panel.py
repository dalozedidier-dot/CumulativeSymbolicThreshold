#!/usr/bin/env python3
"""04_Code/pipeline/run_oos_panel.py

Out-of-sample evaluation on the multi-country ORI-C panel.

Design
------
For each geo unit in the panel:

  1. Split at --split-year: rows <= split_year = calibration, rows > split_year = test.
  2. On the calibration set, estimate:
       - Linear trend (slope, intercept) for each outcome variable (O, R, I, S, Cap)
       - Threshold detection parameters (mu, sigma) from delta_Cap
  3. On the test set, evaluate:
       - Trend extrapolation RMSE and correlation
       - Whether the calibration-derived threshold is exceeded in the test period
         (threshold-hit OOS: consistent with a self-reinforcing regime)
  4. Aggregate across all geos: mean OOS RMSE, hit-rate, coverage.

OOS prediction strategy
-----------------------
Cap(t) = O(t) * R(t) * I(t) where available, otherwise O(t) * R(t).
delta_Cap(t) = Cap(t) - Cap(t-1).
Calibration: fit OLS trend on Cap vs. year.
Test:         compare predicted Cap to observed Cap.

Threshold-hit OOS
-----------------
Compute (mu_Cal, sigma_Cal) of delta_Cap on calibration.
Apply threshold k=2.5, m=3 on the test delta_Cap.
Expected if ORI-C hypothesis holds: hit detected in at least one geo.

Outputs to <outdir>/tables/:
  oos_per_geo.csv     — per-geo OOS metrics
  oos_aggregate.json  — aggregate RMSE, hit-rate, verdict
  verdict.txt         — ACCEPT | REJECT | INDETERMINATE

Usage
-----
    python 04_Code/pipeline/run_oos_panel.py \\
        --panel 03_Data/real/_bundles/data_real_v2/oric_inputs/oric_inputs_panel.csv \\
        --split-year 2015 \\
        --outcome-col O \\
        --outdir 05_Results/oos_panel \\
        --k 2.5 --m 3 --alpha 0.01 --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_cap(df: pd.DataFrame) -> pd.Series:
    """Cap = O*R*I if all available, else O*R, else single available variable."""
    if "O" in df.columns and "R" in df.columns and "I" in df.columns:
        cap = df["O"] * df["R"] * df["I"]
    elif "O" in df.columns and "R" in df.columns:
        cap = df["O"] * df["R"]
    elif "O" in df.columns:
        cap = df["O"].copy()
    else:
        cap = pd.Series(np.nan, index=df.index)
    return cap


def _linear_trend_pred(
    years_cal: np.ndarray,
    y_cal: np.ndarray,
    years_test: np.ndarray,
) -> tuple[np.ndarray, float, float]:
    """Fit OLS trend on calibration, predict on test years."""
    mask = np.isfinite(y_cal)
    if mask.sum() < 2:
        return np.full(len(years_test), np.nan), float("nan"), float("nan")
    slope, intercept, _, _, _ = stats.linregress(years_cal[mask], y_cal[mask])
    y_pred = slope * years_test + intercept
    return y_pred, float(slope), float(intercept)


def _detect_threshold_cal_params(
    delta_cap_cal: np.ndarray,
    k: float,
    m: int,
) -> tuple[float, float, float]:
    """Estimate (mu, sigma, threshold) from calibration delta_Cap."""
    x = delta_cap_cal[np.isfinite(delta_cap_cal)]
    if len(x) < 3:
        return float("nan"), float("nan"), float("nan")
    mu = float(np.mean(x))
    sigma = float(np.std(x))
    threshold = mu + float(k) * sigma
    return mu, sigma, threshold


def _threshold_hit_test(
    delta_cap_test: np.ndarray,
    threshold: float,
    m: int,
) -> bool:
    """Return True if delta_Cap exceeds threshold for m consecutive steps in test period."""
    if not np.isfinite(threshold):
        return False
    consec = 0
    for v in delta_cap_test:
        if np.isfinite(v) and v > threshold:
            consec += 1
            if consec >= int(m):
                return True
        else:
            consec = 0
    return False


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if mask.sum() < 1:
        return float("nan")
    return float(np.sqrt(np.mean((y_true[mask] - y_pred[mask]) ** 2)))


def _correlation(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if mask.sum() < 3:
        return float("nan")
    r, _ = stats.pearsonr(y_true[mask], y_pred[mask])
    return float(r)


# ── Per-geo evaluation ─────────────────────────────────────────────────────────

def _evaluate_geo(
    df_geo: pd.DataFrame,
    outcome_col: str,
    split_year: int,
    k: float,
    m: int,
) -> dict:
    geo = str(df_geo["geo"].iloc[0])
    df_geo = df_geo.sort_values("year").reset_index(drop=True)

    # Compute Cap (for threshold analysis even if outcome_col != Cap)
    df_geo["Cap"] = _compute_cap(df_geo)
    df_geo["delta_Cap"] = df_geo["Cap"].diff()

    cal = df_geo[df_geo["year"] <= split_year].copy()
    test = df_geo[df_geo["year"] > split_year].copy()

    n_cal = int(cal[outcome_col].notna().sum()) if outcome_col in cal.columns else 0
    n_test = int(test[outcome_col].notna().sum()) if outcome_col in test.columns else 0

    if n_cal < 3:
        return {
            "geo": geo,
            "n_cal": n_cal,
            "n_test": n_test,
            "oos_rmse": float("nan"),
            "oos_corr": float("nan"),
            "threshold_hit_oos": None,
            "result": "SKIP",
            "reason": f"Too few calibration points ({n_cal})",
        }

    y_cal = cal[outcome_col].to_numpy(dtype=float)
    years_cal = cal["year"].to_numpy(dtype=float)

    # Predict test period via linear trend
    result: dict = {"geo": geo, "n_cal": n_cal, "n_test": n_test}

    if n_test >= 1:
        y_test = test[outcome_col].to_numpy(dtype=float)
        years_test = test["year"].to_numpy(dtype=float)

        y_pred, slope, intercept = _linear_trend_pred(years_cal, y_cal, years_test)
        result["oos_rmse"] = _rmse(y_test, y_pred)
        result["oos_corr"] = _correlation(y_test, y_pred)
        result["trend_slope_cal"] = float(slope)
        result["trend_intercept_cal"] = float(intercept)

        # Baseline RMSE (predict test mean with calibration mean — naive benchmark)
        naive_pred = np.full(len(y_test), float(np.nanmean(y_cal)))
        result["naive_rmse"] = _rmse(y_test, naive_pred)
        result["oos_vs_naive"] = (
            "better" if np.isfinite(result["oos_rmse"]) and np.isfinite(result["naive_rmse"])
            and result["oos_rmse"] < result["naive_rmse"]
            else "worse_or_equal"
        )
    else:
        result["oos_rmse"] = float("nan")
        result["oos_corr"] = float("nan")
        result["oos_vs_naive"] = "no_test_data"

    # Threshold analysis
    delta_cap_cal = cal["delta_Cap"].to_numpy(dtype=float)
    mu_cal, sigma_cal, thr_cal = _detect_threshold_cal_params(delta_cap_cal, k, m)
    result["mu_cal"] = float(mu_cal)
    result["sigma_cal"] = float(sigma_cal)
    result["threshold_cal"] = float(thr_cal)

    if n_test >= m and "delta_Cap" in test.columns:
        delta_cap_test = test["delta_Cap"].to_numpy(dtype=float)
        hit = _threshold_hit_oos = _threshold_hit_test(delta_cap_test, thr_cal, m)
        result["threshold_hit_oos"] = bool(hit)
    else:
        result["threshold_hit_oos"] = None

    result["result"] = "OK"
    return result


# ── Aggregate ──────────────────────────────────────────────────────────────────

def _aggregate(per_geo: list[dict], alpha: float) -> dict:
    valid = [r for r in per_geo if r.get("result") == "OK"]
    if not valid:
        return {"verdict": "INDETERMINATE", "reason": "No valid geo results"}

    rmse_vals = [r["oos_rmse"] for r in valid if np.isfinite(r.get("oos_rmse", float("nan")))]
    corr_vals = [r["oos_corr"] for r in valid if np.isfinite(r.get("oos_corr", float("nan")))]
    hits = [r["threshold_hit_oos"] for r in valid if r.get("threshold_hit_oos") is not None]
    n_better = sum(1 for r in valid if r.get("oos_vs_naive") == "better")

    agg: dict = {
        "n_geos_valid": len(valid),
        "n_geos_with_test": sum(1 for r in valid if r["n_test"] >= 1),
        "mean_oos_rmse": float(np.nanmean(rmse_vals)) if rmse_vals else float("nan"),
        "mean_oos_corr": float(np.nanmean(corr_vals)) if corr_vals else float("nan"),
        "n_geos_better_than_naive": int(n_better),
        "threshold_hit_geos": [r["geo"] for r in valid if r.get("threshold_hit_oos")],
        "threshold_hit_rate": float(sum(bool(h) for h in hits) / len(hits)) if hits else float("nan"),
    }

    # Verdict:
    # ACCEPT: ≥50% geos beat naive trend + at least one threshold hit OOS
    # REJECT: no threshold hit OOS and trend predictions worse than naive across all
    # INDETERMINATE: otherwise
    corr_ok = np.isfinite(agg["mean_oos_corr"]) and agg["mean_oos_corr"] > 0.5
    any_hit = bool(agg["threshold_hit_geos"])
    majority_better = (len(valid) > 0) and (n_better / len(valid) >= 0.5)

    if corr_ok and any_hit and majority_better:
        verdict = "ACCEPT"
    elif not any_hit and not majority_better and len(valid) >= 2:
        verdict = "REJECT"
    else:
        verdict = "INDETERMINATE"

    agg["verdict"] = verdict
    return agg


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C out-of-sample panel evaluation")
    ap.add_argument("--panel", required=True, help="Path to oric_inputs_panel.csv")
    ap.add_argument("--split-year", type=int, default=2015, help="Year separating calibration from test")
    ap.add_argument("--outcome-col", default="O", choices=["O", "R", "I", "S"])
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    tabdir = outdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(Path(args.panel))
    if "geo" not in df.columns or "year" not in df.columns:
        print("ERROR: panel must have 'geo' and 'year' columns", file=sys.stderr)
        return 1

    geos = df["geo"].unique().tolist()
    print(f"Panel: {len(df)} rows, {len(geos)} geos: {geos}")
    print(f"Split year: {args.split_year}, outcome: {args.outcome_col}")

    per_geo = []
    for geo in sorted(geos):
        g = df[df["geo"] == geo].copy()
        r = _evaluate_geo(g, args.outcome_col, args.split_year, args.k, args.m)
        per_geo.append(r)
        status = r["result"]
        rmse = f"{r['oos_rmse']:.4f}" if np.isfinite(r.get("oos_rmse", float("nan"))) else "NaN"
        corr = f"{r['oos_corr']:.4f}" if np.isfinite(r.get("oos_corr", float("nan"))) else "NaN"
        hit = r.get("threshold_hit_oos")
        print(f"  {geo:12s} n_cal={r['n_cal']} n_test={r['n_test']} "
              f"RMSE={rmse} corr={corr} thr_hit={hit}  [{status}]")

    agg = _aggregate(per_geo, args.alpha)
    verdict = agg["verdict"]
    print(f"\nAggregate: RMSE={agg.get('mean_oos_rmse', 'NaN'):.4f}  "
          f"corr={agg.get('mean_oos_corr', 'NaN'):.4f}  "
          f"hit_rate={agg.get('threshold_hit_rate', 'NaN'):.2f}")
    print(f"── Verdict: {verdict} ──")

    pd.DataFrame(per_geo).to_csv(tabdir / "oos_per_geo.csv", index=False)
    (tabdir / "oos_aggregate.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")

    # Canonical one-row summary.csv
    summary = {
        "split_year": int(args.split_year),
        "outcome_col": args.outcome_col,
        "n_geos_valid": agg["n_geos_valid"],
        "mean_oos_rmse": agg.get("mean_oos_rmse"),
        "mean_oos_corr": agg.get("mean_oos_corr"),
        "threshold_hit_rate": agg.get("threshold_hit_rate"),
        "verdict": verdict,
    }
    pd.DataFrame([summary]).to_csv(tabdir / "summary.csv", index=False)
    (outdir / "verdict.txt").write_text(verdict + "\n", encoding="utf-8")

    print(f"\nOutputs written to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
