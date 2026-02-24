#!/usr/bin/env python3
"""04_Code/pipeline/run_oos_panel.py

Out-of-sample evaluation on the multi-country ORI-C panel.

Design
------
For each geo unit in the panel:

  1. Split at --split-year: rows <= split_year = calibration, rows > split_year = test.
  2. On the calibration set, estimate:
       - Linear trend (slope, intercept) for the outcome variable
       - Threshold detection parameters (mu, sigma, threshold) from delta_Cap
  3. On the test set, evaluate:
       - Trend extrapolation RMSE and correlation vs. naive mean baseline
       - Fraction of test steps where delta_Cap exceeds the calibration threshold
         (softer metric than requiring m consecutive hits — more appropriate for
         short annual test periods of 6-10 years)
       - Whether m consecutive threshold hits occur (strict binary hit)

Edge cases handled
------------------
  constant_calibration  sigma_cal < 1e-9: threshold = mu_cal (any positive delta > mu
                        would trigger). Flagged as threshold_cal_reliable=False; threshold
                        hit test still runs but result is marked with a note.
  NaN correlation       fewer than 3 finite pairs in (y_true, y_pred): oos_corr=NaN,
                        oos_vs_naive="insufficient_data" (not counted as "worse").
  sparse test period    n_test < m: skip threshold hit test (result = None).

Verdict logic (revised)
-----------------------
  The old logic required at least one threshold hit (m=3 consecutive) which is very
  stringent for annual panels with only 6-10 test years post-split. The revised verdict:

  ACCEPT      : majority of geos beat naive trend AND median_corr > 0.0 AND
                any geo has threshold_exceed_frac_post > 0.25
  REJECT      : majority have corr < -0.2 (trend actively wrong)
  INDETERMINATE: otherwise

Outputs to <outdir>/tables/:
  oos_per_geo.csv     — per-geo OOS metrics (including threshold_exceed_frac_post)
  oos_aggregate.json  — aggregate metrics + verdict
  summary.csv         — one-row canonical summary
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

def _cap_formula(df_reference: pd.DataFrame) -> str:
    """Select Cap formula based on coverage within df_reference (calibration window).

    Returns one of: 'ORI', 'OR', 'O', 'none'.

    The formula is chosen on the calibration period to ensure delta_Cap has
    enough finite values to estimate mu/sigma.  R and I in the panel are only
    available from ~2012; applying their coverage check over the whole series
    (which includes the post-split test period) would declare them available
    while the calibration window has < 3 non-NaN O*R values.
    """
    n = max(1, len(df_reference))
    has_O = "O" in df_reference.columns and df_reference["O"].notna().sum() / n >= 0.25
    has_R = "R" in df_reference.columns and df_reference["R"].notna().sum() / n >= 0.25
    has_I = "I" in df_reference.columns and df_reference["I"].notna().sum() / n >= 0.25
    if has_O and has_R and has_I:
        return "ORI"
    if has_O and has_R:
        return "OR"
    if has_O:
        return "O"
    return "none"


def _compute_cap(df: pd.DataFrame, formula: str = "") -> pd.Series:
    """Apply the given Cap formula to df.

    If formula is empty, infers it from df itself (backwards-compat).
    Supported: 'ORI', 'OR', 'O', 'none'.
    """
    if not formula:
        formula = _cap_formula(df)
    if formula == "ORI":
        return df["O"] * df["R"] * df["I"]
    if formula == "OR":
        return df["O"] * df["R"]
    if formula == "O":
        return df["O"].copy()
    return pd.Series(np.nan, index=df.index)


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


_SIGMA_MIN = 1e-9   # below this, the calibration series is considered constant


def _detect_threshold_cal_params(
    delta_cap_cal: np.ndarray,
    k: float,
    m: int,
) -> tuple[float, float, float, bool]:
    """Estimate (mu, sigma, threshold, reliable) from calibration delta_Cap.

    Returns
    -------
    mu, sigma, threshold : floats (NaN if too few points)
    reliable : bool — False when sigma < _SIGMA_MIN (constant calibration)
    """
    x = delta_cap_cal[np.isfinite(delta_cap_cal)]
    if len(x) < 3:
        return float("nan"), float("nan"), float("nan"), False
    mu = float(np.mean(x))
    sigma = float(np.std(x))
    if sigma < _SIGMA_MIN:
        # Constant calibration: threshold equals the mean of delta_Cap.
        # The threshold is technically well-defined but unreliable as a
        # regime-change detector — flag it and continue.
        threshold = mu
        return mu, sigma, threshold, False
    threshold = mu + float(k) * sigma
    return mu, sigma, threshold, True


def _threshold_hit_test(
    delta_cap_test: np.ndarray,
    threshold: float,
    m: int,
) -> tuple[bool, float, int]:
    """Test threshold exceedance in the test period.

    Returns
    -------
    hit_strict : bool — True if m consecutive steps exceed threshold
    exceed_frac : float — fraction of finite test steps that exceed threshold
    max_consec  : int  — maximum consecutive exceedance run
    """
    if not np.isfinite(threshold):
        return False, float("nan"), 0

    finite_test = np.asarray([v for v in delta_cap_test if np.isfinite(v)])
    if len(finite_test) == 0:
        return False, float("nan"), 0

    exceed = finite_test > threshold
    exceed_frac = float(exceed.sum() / len(finite_test))

    # Max consecutive run and strict hit
    max_consec = 0
    consec = 0
    hit_strict = False
    for v in exceed:
        if v:
            consec += 1
            max_consec = max(max_consec, consec)
            if consec >= int(m):
                hit_strict = True
        else:
            consec = 0

    return hit_strict, exceed_frac, int(max_consec)


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

    # Determine Cap formula using calibration-period coverage, then apply to full series.
    # This prevents R/I (available only post-2012) from appearing "available" when their
    # pre-split coverage is < 25%, which would make delta_Cap_cal nearly all-NaN.
    cal_prelim = df_geo[df_geo["year"] <= split_year]
    formula = _cap_formula(cal_prelim)
    df_geo["Cap"] = _compute_cap(df_geo, formula)
    df_geo["delta_Cap"] = df_geo["Cap"].diff()
    df_geo.attrs["cap_formula"] = formula

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
            "threshold_exceed_frac_post": float("nan"),
            "threshold_max_consec_post": 0,
            "threshold_cal_reliable": False,
            "result": "SKIP",
            "reason": f"Too few calibration points ({n_cal})",
        }

    y_cal = cal[outcome_col].to_numpy(dtype=float)
    years_cal = cal["year"].to_numpy(dtype=float)

    result: dict = {"geo": geo, "n_cal": n_cal, "n_test": n_test, "cap_formula": formula}

    if n_test >= 1:
        y_test = test[outcome_col].to_numpy(dtype=float)
        years_test = test["year"].to_numpy(dtype=float)

        y_pred, slope, intercept = _linear_trend_pred(years_cal, y_cal, years_test)
        result["oos_rmse"] = _rmse(y_test, y_pred)
        result["oos_corr"] = _correlation(y_test, y_pred)
        result["trend_slope_cal"] = float(slope)
        result["trend_intercept_cal"] = float(intercept)

        # Naive baseline: predict calibration mean for every test step
        cal_mean = float(np.nanmean(y_cal))
        naive_pred = np.full(len(y_test), cal_mean)
        result["naive_rmse"] = _rmse(y_test, naive_pred)

        # NaN corr = insufficient finite test/pred pairs → "insufficient_data" (not "worse")
        if np.isfinite(result["oos_rmse"]) and np.isfinite(result["naive_rmse"]):
            result["oos_vs_naive"] = "better" if result["oos_rmse"] < result["naive_rmse"] else "worse_or_equal"
        elif not np.isfinite(result["oos_corr"]):
            result["oos_vs_naive"] = "insufficient_data"
        else:
            result["oos_vs_naive"] = "worse_or_equal"
    else:
        result["oos_rmse"] = float("nan")
        result["oos_corr"] = float("nan")
        result["oos_vs_naive"] = "no_test_data"

    # Threshold analysis: uses delta_Cap (not the outcome column directly)
    delta_cap_cal = cal["delta_Cap"].to_numpy(dtype=float)
    mu_cal, sigma_cal, thr_cal, thr_reliable = _detect_threshold_cal_params(delta_cap_cal, k, m)
    result["mu_cal"] = float(mu_cal)
    result["sigma_cal"] = float(sigma_cal)
    result["threshold_cal"] = float(thr_cal)
    result["threshold_cal_reliable"] = bool(thr_reliable)
    if not thr_reliable:
        result["threshold_cal_note"] = (
            "constant_calibration: sigma_cal ≈ 0, threshold = mu_cal" if sigma_cal < _SIGMA_MIN
            else "too_few_points"
        )

    if n_test >= 1 and "delta_Cap" in test.columns:
        delta_cap_test = test["delta_Cap"].to_numpy(dtype=float)
        hit_strict, exceed_frac, max_consec = _threshold_hit_test(delta_cap_test, thr_cal, m)
        result["threshold_hit_oos"] = bool(hit_strict) if n_test >= m else None
        result["threshold_exceed_frac_post"] = float(exceed_frac)
        result["threshold_max_consec_post"] = int(max_consec)
    else:
        result["threshold_hit_oos"] = None
        result["threshold_exceed_frac_post"] = float("nan")
        result["threshold_max_consec_post"] = 0

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
    exceed_fracs = [
        r["threshold_exceed_frac_post"]
        for r in valid
        if np.isfinite(r.get("threshold_exceed_frac_post", float("nan")))
    ]

    # Only count geos with a RMSE comparison (skip "insufficient_data" and "no_test_data")
    n_better = sum(1 for r in valid if r.get("oos_vs_naive") == "better")
    n_comparable = sum(1 for r in valid if r.get("oos_vs_naive") in ("better", "worse_or_equal"))

    agg: dict = {
        "n_geos_valid": len(valid),
        "n_geos_with_test": sum(1 for r in valid if r["n_test"] >= 1),
        "mean_oos_rmse": float(np.nanmean(rmse_vals)) if rmse_vals else float("nan"),
        "mean_oos_corr": float(np.nanmean(corr_vals)) if corr_vals else float("nan"),
        "median_oos_corr": float(np.nanmedian(corr_vals)) if corr_vals else float("nan"),
        "n_geos_better_than_naive": int(n_better),
        "n_geos_comparable": int(n_comparable),
        "threshold_hit_geos": [r["geo"] for r in valid if r.get("threshold_hit_oos")],
        "threshold_hit_rate": float(sum(bool(h) for h in hits) / len(hits)) if hits else float("nan"),
        "mean_threshold_exceed_frac": float(np.nanmean(exceed_fracs)) if exceed_fracs else float("nan"),
        "any_exceed_frac_above_25pct": bool(any(f > 0.25 for f in exceed_fracs if np.isfinite(f))),
    }

    # Revised verdict logic (annual panels, short test periods):
    # Use median_corr (robust to one negative outlier) and threshold_exceed_frac as soft criterion.
    # ACCEPT:
    #   ≥50% of comparable geos beat naive trend
    #   AND median_corr > 0.0 (better than random on average)
    #   AND any geo has threshold_exceed_frac_post > 0.25 (25% of test steps above threshold)
    # REJECT:
    #   majority of geos with valid corr have corr < -0.2 (trend actively wrong)
    # INDETERMINATE: otherwise
    median_corr = agg.get("median_oos_corr", float("nan"))
    any_exceed = agg["any_exceed_frac_above_25pct"]
    majority_better = n_comparable > 0 and (n_better / n_comparable) >= 0.5

    n_neg_corr = sum(1 for c in corr_vals if c < -0.2)
    majority_negative = len(corr_vals) > 0 and (n_neg_corr / len(corr_vals)) > 0.5

    if majority_better and np.isfinite(median_corr) and median_corr > 0.0 and any_exceed:
        verdict = "ACCEPT"
    elif majority_negative:
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
        excf = r.get("threshold_exceed_frac_post", float("nan"))
        excf_s = f"{excf:.2f}" if np.isfinite(excf) else "NaN"
        reliable = r.get("threshold_cal_reliable", True)
        print(
            f"  {geo:12s} n_cal={r['n_cal']} n_test={r['n_test']} "
            f"RMSE={rmse} corr={corr} exceed_frac={excf_s} thr_hit={hit}"
            + ("" if reliable else " [threshold_unreliable]")
            + f"  [{status}]"
        )

    agg = _aggregate(per_geo, args.alpha)
    verdict = agg["verdict"]
    print(
        f"\nAggregate: RMSE={agg.get('mean_oos_rmse', float('nan')):.4f}  "
        f"median_corr={agg.get('median_oos_corr', float('nan')):.4f}  "
        f"mean_exceed_frac={agg.get('mean_threshold_exceed_frac', float('nan')):.2f}"
    )
    print(f"── Verdict: {verdict} ──")

    pd.DataFrame(per_geo).to_csv(tabdir / "oos_per_geo.csv", index=False)
    (tabdir / "oos_aggregate.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")

    summary = {
        "split_year": int(args.split_year),
        "outcome_col": args.outcome_col,
        "n_geos_valid": agg["n_geos_valid"],
        "mean_oos_rmse": agg.get("mean_oos_rmse"),
        "mean_oos_corr": agg.get("mean_oos_corr"),
        "median_oos_corr": agg.get("median_oos_corr"),
        "mean_threshold_exceed_frac": agg.get("mean_threshold_exceed_frac"),
        "threshold_hit_rate": agg.get("threshold_hit_rate"),
        "verdict": verdict,
    }
    pd.DataFrame([summary]).to_csv(tabdir / "summary.csv", index=False)
    (outdir / "verdict.txt").write_text(verdict + "\n", encoding="utf-8")

    print(f"\nOutputs written to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
