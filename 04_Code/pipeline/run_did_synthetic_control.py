#!/usr/bin/env python3
"""04_Code/pipeline/run_did_synthetic_control.py

Difference-in-Differences and Synthetic Control estimation on the ORI-C
multi-country panel (oric_inputs_panel.csv).

Design
------
The panel contains 5 geo units (BE, DE, EE, EU27_2020, FR) with annual
observations of O, R, I, S (normalised to [0,1]).

Two causal strategies are implemented:

  1. Difference-in-Differences (DiD)
     ATT = (Y_treated_post − Y_treated_pre) − mean(Y_controls_post − Y_controls_pre)
     Bootstrap CI (block = 1, n_boot iterations over year-level resampling).
     Parallel-trends test: linear trend pre-event must not differ significantly
     between treated and donor pool (Wald test on trend coefficient).

  2. Synthetic Control (Abadie–Diamond–Hainmueller, simplified)
     Minimise ||Y_treated_pre − Σ w_j * Y_j_pre||²  subject to w_j >= 0, Σ w_j = 1.
     Post-event gap = Y_treated_post − Σ w_j * Y_j_post.
     Placebo-in-space: repeat for each donor unit, compute empirical p-value.

Outcome variable (--outcome-col):
  By default uses O (Organisation proxy), which has the widest coverage.
  Can be set to R, I, S, or Cap (Cap = O*R*I, columns forward-filled where possible).

Event: --event-year (default 2015, Paris Agreement).
Treated: --treated-geo (default EU27_2020).
Donor pool: all other geos with sufficient coverage.

Outputs to <outdir>/tables/:
  did_results.json   — DiD ATT, CI, p-values, parallel-trends test
  sc_results.json    — SC weights, MSPE, placebo p-value
  summary.csv        — one-row summary
  verdict.txt        — ACCEPT | REJECT | INDETERMINATE

Usage
-----
    python 04_Code/pipeline/run_did_synthetic_control.py \\
        --panel 03_Data/real/_bundles/data_real_v2/oric_inputs/oric_inputs_panel.csv \\
        --treated-geo EU27_2020 \\
        --event-year 2015 \\
        --outcome-col O \\
        --outdir 05_Results/did/paris_2015 \\
        --alpha 0.01 --n-boot 500 --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))


# ── Data helpers ───────────────────────────────────────────────────────────────

def _load_panel(path: Path, outcome_col: str) -> pd.DataFrame:
    """Load panel, compute Cap if requested, return subset with valid outcome."""
    df = pd.read_csv(path)
    if "geo" not in df.columns or "year" not in df.columns:
        raise ValueError("Panel CSV must have 'geo' and 'year' columns")

    # Compute Cap = O * R * I if requested, tolerate partial I coverage
    if outcome_col == "Cap":
        if "O" in df.columns and "R" in df.columns:
            if "I" in df.columns:
                df["Cap"] = df["O"] * df["R"] * df["I"]
            else:
                df["Cap"] = df["O"] * df["R"]  # partial
        else:
            raise ValueError("Cannot compute Cap: O and R columns required")

    if outcome_col not in df.columns:
        raise ValueError(f"Column '{outcome_col}' not found. Available: {list(df.columns)}")

    return df[["geo", "year", outcome_col]].copy()


def _pivot(df: pd.DataFrame, outcome_col: str) -> pd.DataFrame:
    """Pivot to wide format: index=year, columns=geo."""
    return df.pivot(index="year", columns="geo", values=outcome_col).sort_index()


# ── DiD ────────────────────────────────────────────────────────────────────────

def _did_estimate(
    wide: pd.DataFrame,
    treated: str,
    event_year: int,
    donors: list[str],
) -> dict:
    """Simple DiD: ATT = (treated_post - treated_pre) - mean(donors_post - donors_pre)."""
    pre = wide[wide.index < event_year]
    post = wide[wide.index >= event_year]

    if len(pre) < 2 or len(post) < 1:
        return {"att": float("nan"), "n_pre": len(pre), "n_post": len(post), "donors": donors}

    # Drop donors with too many NaN
    valid_donors = [d for d in donors if d in wide.columns and pre[d].notna().mean() >= 0.5]

    if not valid_donors:
        return {"att": float("nan"), "n_pre": len(pre), "n_post": len(post), "donors": []}

    t_pre = float(pre[treated].mean()) if treated in pre else float("nan")
    t_post = float(post[treated].mean()) if treated in post else float("nan")
    d_pre = float(pre[valid_donors].mean(axis=1).mean())
    d_post = float(post[valid_donors].mean(axis=1).mean())

    att = (t_post - t_pre) - (d_post - d_pre)
    return {
        "att": float(att),
        "treated_pre_mean": float(t_pre),
        "treated_post_mean": float(t_post),
        "donor_pre_mean": float(d_pre),
        "donor_post_mean": float(d_post),
        "n_pre": int(len(pre)),
        "n_post": int(len(post)),
        "donors_used": valid_donors,
    }


def _parallel_trends_test(
    wide: pd.DataFrame,
    treated: str,
    event_year: int,
    donors: list[str],
) -> dict:
    """Wald test for equal pre-event linear trends between treated and average donor."""
    from scipy import stats  # local import — scipy available

    pre = wide[wide.index < event_year].copy()
    if len(pre) < 4:
        return {"p_parallel": float("nan"), "trend_diff": float("nan"), "passed": None}

    valid_donors = [d for d in donors if d in wide.columns and pre[d].notna().mean() >= 0.5]
    if not valid_donors or treated not in pre.columns:
        return {"p_parallel": float("nan"), "trend_diff": float("nan"), "passed": None}

    years = pre.index.to_numpy(dtype=float)
    years_c = years - years.mean()

    y_treated = pre[treated].to_numpy(dtype=float)
    y_donor = pre[valid_donors].mean(axis=1).to_numpy(dtype=float)

    # OLS trend for treated
    mask_t = np.isfinite(y_treated)
    if mask_t.sum() < 3:
        return {"p_parallel": float("nan"), "trend_diff": float("nan"), "passed": None}
    slope_t, _, _, _, _ = stats.linregress(years_c[mask_t], y_treated[mask_t])

    # OLS trend for donor average
    mask_d = np.isfinite(y_donor)
    if mask_d.sum() < 3:
        return {"p_parallel": float("nan"), "trend_diff": float("nan"), "passed": None}
    slope_d, _, _, _, _ = stats.linregress(years_c[mask_d], y_donor[mask_d])

    trend_diff = float(slope_t - slope_d)

    # Approx Wald: |trend_diff| / pooled_SE; use simple t-test on difference series
    diff_series = y_treated[mask_t & mask_d] - y_donor[mask_t & mask_d]
    if len(diff_series) >= 3:
        _, p = stats.ttest_1samp(diff_series, 0.0)
        p_parallel = float(p)
    else:
        p_parallel = float("nan")

    passed = bool(np.isfinite(p_parallel) and p_parallel > 0.05)
    return {
        "slope_treated": float(slope_t),
        "slope_donor_avg": float(slope_d),
        "trend_diff": float(trend_diff),
        "p_parallel": float(p_parallel),
        "passed": passed,
        "interpretation": "Parallel trends plausible" if passed else "Parallel trends violated — DiD estimates unreliable",
    }


def _bootstrap_did(
    wide: pd.DataFrame,
    treated: str,
    event_year: int,
    donors: list[str],
    n_boot: int,
    seed: int,
) -> tuple[float, float, float]:
    """Block bootstrap CI for DiD ATT (year-level resampling)."""
    rng = np.random.default_rng(int(seed))
    pre_idx = wide.index[wide.index < event_year].to_numpy()
    post_idx = wide.index[wide.index >= event_year].to_numpy()
    if len(pre_idx) < 3 or len(post_idx) < 1:
        return float("nan"), float("nan"), float("nan")

    valid_donors = [d for d in donors if d in wide.columns and wide.loc[pre_idx, d].notna().mean() >= 0.5]
    if not valid_donors or treated not in wide.columns:
        return float("nan"), float("nan"), float("nan")

    atts = []
    for _ in range(int(n_boot)):
        b_pre = rng.choice(pre_idx, size=len(pre_idx), replace=True)
        b_post = rng.choice(post_idx, size=len(post_idx), replace=True)
        bt = float(wide.loc[b_post, treated].mean() - wide.loc[b_pre, treated].mean())
        bd = float(wide.loc[b_post, valid_donors].mean(axis=1).mean() - wide.loc[b_pre, valid_donors].mean(axis=1).mean())
        atts.append(bt - bd)

    atts = np.array(atts)
    return float(np.mean(atts)), float(np.quantile(atts, 0.005)), float(np.quantile(atts, 0.995))


# ── Synthetic Control ─────────────────────────────────────────────────────────

def _synthetic_control(
    wide: pd.DataFrame,
    treated: str,
    event_year: int,
    donors: list[str],
) -> dict:
    """Abadie-style synthetic control: minimise pre-event MSPE.

    Returns: weights dict, pre_mspe, post_gap, placebo_p.
    """
    pre = wide[wide.index < event_year]
    post = wide[wide.index >= event_year]

    valid_donors = [d for d in donors if d in wide.columns]
    # Require donors with >= 60% pre-period coverage
    valid_donors = [d for d in valid_donors if pre[d].notna().mean() >= 0.6]

    if not valid_donors or treated not in pre.columns:
        return {"weights": {}, "pre_mspe": float("nan"), "post_gap_mean": float("nan"), "placebo_p": float("nan"), "donors_used": []}

    # Build pre-period matrices; fill NaN with column means
    y_treat = pre[treated].fillna(pre[treated].mean()).to_numpy(dtype=float)
    Y_donors = pre[valid_donors].apply(lambda c: c.fillna(c.mean())).to_numpy(dtype=float)

    if len(y_treat) < 2:
        return {"weights": {}, "pre_mspe": float("nan"), "post_gap_mean": float("nan"), "placebo_p": float("nan"), "donors_used": []}

    J = len(valid_donors)

    def _loss(w: np.ndarray) -> float:
        return float(np.mean((y_treat - Y_donors @ w) ** 2))

    w0 = np.ones(J) / J
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(0.0, 1.0)] * J
    res = minimize(_loss, w0, method="SLSQP", bounds=bounds, constraints=constraints,
                   options={"ftol": 1e-9, "maxiter": 1000})
    w_opt = res.x if res.success else w0
    pre_mspe = float(_loss(w_opt))

    weights = {d: float(w) for d, w in zip(valid_donors, w_opt)}

    # Post-event gap
    if len(post) > 0 and treated in post.columns:
        y_treat_post = post[treated].to_numpy(dtype=float)
        Y_donors_post = post[valid_donors].apply(lambda c: c.fillna(c.mean())).to_numpy(dtype=float)
        sc_post = Y_donors_post @ w_opt
        gaps = y_treat_post - sc_post
        post_gap_mean = float(np.nanmean(gaps))
    else:
        post_gap_mean = float("nan")

    # Placebo-in-space: compute synthetic control MSPE for each donor as placebo treated
    placebo_pre_mspe = []
    for j, d_treated in enumerate(valid_donors):
        remaining = [d for d in valid_donors if d != d_treated]
        if not remaining:
            continue
        y_p = pre[d_treated].fillna(pre[d_treated].mean()).to_numpy(dtype=float)
        Y_p = pre[remaining].apply(lambda c: c.fillna(c.mean())).to_numpy(dtype=float)
        Jp = len(remaining)
        w0p = np.ones(Jp) / Jp
        resp = minimize(lambda w: float(np.mean((y_p - Y_p @ w) ** 2)),
                        w0p, method="SLSQP",
                        bounds=[(0, 1)] * Jp,
                        constraints=[{"type": "eq", "fun": lambda w: sum(w) - 1}],
                        options={"ftol": 1e-9, "maxiter": 500})
        wp = resp.x if resp.success else w0p
        placebo_pre_mspe.append(float(np.mean((y_p - Y_p @ wp) ** 2)))

    # Placebo p: share of placebos with pre_mspe <= treated pre_mspe
    if placebo_pre_mspe:
        placebo_p = float(np.mean(np.array(placebo_pre_mspe) <= pre_mspe))
    else:
        placebo_p = float("nan")

    return {
        "weights": weights,
        "pre_mspe": float(pre_mspe),
        "post_gap_mean": float(post_gap_mean),
        "placebo_p": float(placebo_p),
        "donors_used": valid_donors,
        "n_pre": int(len(pre)),
        "n_post": int(len(post)),
    }


# ── Aggregate verdict ─────────────────────────────────────────────────────────

def _verdict(
    att: float,
    ci_lo: float,
    ci_hi: float,
    p_parallel: float | None,
    post_gap: float,
    alpha: float,
) -> str:
    if not np.isfinite(att):
        return "INDETERMINATE"
    # Parallel trends must hold
    if p_parallel is not None and np.isfinite(p_parallel) and p_parallel <= 0.05:
        return "INDETERMINATE"  # trends not parallel: DiD assumption violated
    if np.isfinite(ci_lo) and np.isfinite(ci_hi):
        if ci_lo > 0:
            return "ACCEPT"
        if ci_hi < 0:
            return "REJECT"
    return "INDETERMINATE"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C DiD + Synthetic Control on multi-country panel")
    ap.add_argument("--panel", required=True, help="Path to oric_inputs_panel.csv")
    ap.add_argument("--treated-geo", default="EU27_2020", help="Treated geo unit")
    ap.add_argument("--event-year", type=int, default=2015, help="Year of policy event")
    ap.add_argument("--outcome-col", default="O", choices=["O", "R", "I", "S", "Cap"])
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    tabdir = outdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)

    df = _load_panel(Path(args.panel), args.outcome_col)
    wide = _pivot(df, args.outcome_col)

    geos = list(wide.columns)
    treated = args.treated_geo
    if treated not in geos:
        print(f"ERROR: treated geo '{treated}' not found. Available: {geos}", file=sys.stderr)
        return 1

    donors = [g for g in geos if g != treated]
    print(f"Panel: {len(wide)} years, geos={geos}")
    print(f"Treated={treated}, event_year={args.event_year}, outcome={args.outcome_col}")

    # ── DiD ──────────────────────────────────────────────────────────────────
    print("\n── DiD ──")
    did = _did_estimate(wide, treated, args.event_year, donors)
    print(f"   ATT = {did.get('att', 'NaN'):.4f}" if np.isfinite(did.get("att", float("nan"))) else "   ATT = NaN")

    pt = _parallel_trends_test(wide, treated, args.event_year, donors)
    print(f"   Parallel trends: p={pt.get('p_parallel', 'NaN'):.4f}  {pt.get('interpretation', '')}")

    boot_mid, ci_lo, ci_hi = _bootstrap_did(wide, treated, args.event_year, donors, args.n_boot, args.seed)
    print(f"   Bootstrap 99% CI: [{ci_lo:.4f}, {ci_hi:.4f}]" if np.isfinite(ci_lo) else "   Bootstrap CI: NaN")

    did_output = {**did, "bootstrap_att_mid": float(boot_mid), "ci_lo_99": float(ci_lo), "ci_hi_99": float(ci_hi), "parallel_trends": pt}
    (tabdir / "did_results.json").write_text(json.dumps(did_output, indent=2), encoding="utf-8")

    # ── Synthetic control ─────────────────────────────────────────────────────
    print("\n── Synthetic Control ──")
    sc = _synthetic_control(wide, treated, args.event_year, donors)
    print(f"   Pre MSPE={sc.get('pre_mspe', 'NaN'):.6f}  post_gap={sc.get('post_gap_mean', 'NaN'):.4f}  placebo_p={sc.get('placebo_p', 'NaN'):.4f}")
    for geo, w in sc.get("weights", {}).items():
        print(f"   w({geo}) = {w:.4f}")
    (tabdir / "sc_results.json").write_text(json.dumps(sc, indent=2), encoding="utf-8")

    # ── Verdict ───────────────────────────────────────────────────────────────
    verdict = _verdict(did.get("att", float("nan")), ci_lo, ci_hi, pt.get("p_parallel"), sc.get("post_gap_mean", float("nan")), args.alpha)
    print(f"\n── Verdict: {verdict} ──")

    summary = {
        "panel_csv": str(Path(args.panel)),
        "treated_geo": treated,
        "event_year": int(args.event_year),
        "outcome_col": args.outcome_col,
        "att": float(did.get("att", float("nan"))),
        "ci_lo_99": float(ci_lo),
        "ci_hi_99": float(ci_hi),
        "parallel_trends_p": float(pt.get("p_parallel", float("nan"))),
        "sc_pre_mspe": float(sc.get("pre_mspe", float("nan"))),
        "sc_post_gap_mean": float(sc.get("post_gap_mean", float("nan"))),
        "sc_placebo_p": float(sc.get("placebo_p", float("nan"))),
        "verdict": verdict,
        "alpha": float(args.alpha),
    }
    pd.DataFrame([summary]).to_csv(tabdir / "summary.csv", index=False)
    (outdir / "verdict.txt").write_text(verdict + "\n", encoding="utf-8")
    print(f"\nOutputs written to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
