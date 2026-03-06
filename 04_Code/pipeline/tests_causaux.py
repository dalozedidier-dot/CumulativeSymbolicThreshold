#!/usr/bin/env python3
"""
04_Code/pipeline/tests_causaux.py

Causal and falsifiability checks for the cumulative symbolic threshold.

Core intent
- Validate that a transition (threshold hit) exists on delta_C(t)
- Validate that C(t) becomes stably positive post-transition
- Validate that the transition is attributable to S(t)

Implemented checks (lightweight but stricter than the legacy diff-in-diff)
- Threshold hit on delta_C (baseline-based)
- No false positives pre-threshold (same detector, same baseline)
- Mean shift test on C (pre vs post), with p-value (Welch)
- Block bootstrap CI for (mean_post - mean_pre)
- Granger causality tests (S -> delta_C, and reverse)
- VAR causality test (S -> delta_C)
- Cointegration test (C, S) as a robustness signal under non-stationarity

Important real-data robustness rules
- If Welch is not computable (p_value_mean_shift_C is NaN), cascade through:
    1. Mann-Whitney U test (non-parametric, one-tailed, same α)
    2. Block bootstrap CI lower bound > 0 as final fallback
  Never let a single undefined parametric statistic decide the verdict.
- Window slicing always uses integer step index (0..n-1), never raw t values
  (which may encode calendar day-counts). If the output CSV has a 'step' column
  it is used; otherwise the DataFrame's row position is used.
- sigma_zero_post is a DIAGNOSTIC, not a verdict override. When Sigma(t)=0
  in the post-threshold window (demand < capacity), the symbolic pathway is
  inoperative, but the statistical tests (Welch, bootstrap, MWU) still run
  on C(t) and produce a decidable verdict (DETECTED or NOT_DETECTED).
  sigma_zero_post only causes INDETERMINATE if all statistical tests also
  return NaN (verdict = indetermine_stats_indisponibles).
  Decidability rule:
    • DETECTED     : ok_p=True (p cascade significant), with or without ok_boot
    • NOT_DETECTED : ok_p=False and tests ran (p values finite)
    • INDETERMINATE: all p-value sources unavailable (Welch/boot/MWU all NaN)

Outputs
- tables/causal_tests_summary.csv
- tables/verdict.json
- tables/causal_report.md
- tables/causal_report.pdf (optional)

Usage (recommended with run_real_data_demo outputs)
python 04_Code/pipeline/tests_causaux.py \
  --run-dir 05_Results/real/.../ds_xxx \
  --alpha 0.01 --c-mean-post-min 0.1 --lags 1-10 --n-steps-min 0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# Ensure 04_Code is on sys.path so `import pipeline.*` works when scripts are executed directly.
_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))


def _make_dirs(outdir: Path) -> Path:
    tabdir = outdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)
    (outdir / "figures").mkdir(parents=True, exist_ok=True)
    return tabdir


def _parse_lags(s: str) -> list[int]:
    s = str(s).strip()
    if not s:
        return [1, 2, 3, 4, 5]
    if "-" in s:
        a, b = s.split("-", 1)
        lo = int(a.strip())
        hi = int(b.strip())
        if hi < lo:
            lo, hi = hi, lo
        return list(range(lo, hi + 1))
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return [int(p) for p in parts]


def _detect_threshold(delta_C: np.ndarray, k: float, m: int, baseline_n: int) -> tuple[int | None, float]:
    x = np.asarray(delta_C, dtype=float)
    n = int(len(x))
    if n == 0:
        return None, 0.0

    bn = int(baseline_n)
    if bn < 5:
        bn = 5
    bn = min(bn, n)

    base = x[:bn]
    mu = float(np.mean(base))
    sd = float(np.std(base))
    thr = mu + float(k) * sd

    consec = 0
    for i in range(n):
        if float(x[i]) > thr:
            consec += 1
            if consec >= int(m):
                return int(i), float(thr)
        else:
            consec = 0
    return None, float(thr)


def _block_bootstrap_mean_diff(
    x_pre: np.ndarray,
    x_post: np.ndarray,
    *,
    block: int,
    n_boot: int,
    seed: int,
) -> tuple[float, float, float]:
    rng = np.random.default_rng(int(seed))
    x_pre = np.asarray(x_pre, dtype=float)
    x_post = np.asarray(x_post, dtype=float)

    # Drop NaN values before size/variance checks
    x_pre = x_pre[np.isfinite(x_pre)]
    x_post = x_post[np.isfinite(x_post)]

    if len(x_pre) < 5 or len(x_post) < 5:
        return float("nan"), float("nan"), float("nan")

    # Constant-value guard: if either window has zero variance, bootstrap
    # mean-diff CI is degenerate (width=0) and misleading.
    if np.nanstd(x_pre) < 1e-12 or np.nanstd(x_post) < 1e-12:
        # Still return the point estimate (it may be useful for diagnostics)
        # but CI bounds are NaN to signal non-informative bootstrap.
        diff = float(np.mean(x_post) - np.mean(x_pre))
        return diff, float("nan"), float("nan")

    block = int(block)
    if block < 5:
        block = 5

    def _sample(x: np.ndarray) -> np.ndarray:
        n = len(x)
        if n <= block:
            idx = rng.integers(0, n, size=n)
            return x[idx]
        out: list[float] = []
        while len(out) < n:
            start = int(rng.integers(0, n - block))
            out.extend(list(x[start : start + block]))
        return np.asarray(out[:n], dtype=float)

    diffs = np.empty(int(n_boot), dtype=float)
    for i in range(int(n_boot)):
        bp = _sample(x_pre)
        bq = _sample(x_post)
        diffs[i] = float(np.mean(bq) - np.mean(bp))

    lo = float(np.quantile(diffs, 0.025))
    hi = float(np.quantile(diffs, 0.975))
    mid = float(np.mean(diffs))
    return mid, lo, hi


def _safe_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def _granger_pvalues(delta_c: np.ndarray, s: np.ndarray, lags: list[int]) -> dict[str, float]:
    # grangercausalitytests expects shape (n,2), tests whether 2nd col causes 1st col.
    try:
        from statsmodels.tsa.stattools import grangercausalitytests  # type: ignore

        data = np.column_stack([delta_c, s])
        maxlag = int(max(lags))
        res = grangercausalitytests(data, maxlag=maxlag, verbose=False)
        out: dict[str, float] = {}
        for lag in lags:
            lag = int(lag)
            if lag in res:
                p = res[lag][0]["ssr_ftest"][1]
                out[str(lag)] = _safe_float(p)
        return out
    except Exception:
        return {}


def _var_causality(delta_c: np.ndarray, s: np.ndarray, maxlag: int) -> tuple[float, int, str]:
    """VAR causality test: S → delta_C.

    Returns (p_value, lag_used, reason).
    reason is "" on success, or a diagnostic string explaining why p is NaN.
    """
    try:
        from statsmodels.tsa.api import VAR  # type: ignore

        df = pd.DataFrame({"delta_C": delta_c, "S": s}).dropna()
        n = len(df)
        n_min = max(20, maxlag * 5)
        if n < n_min:
            return float("nan"), 0, f"VAR: n={n} < n_min={n_min} after dropna"

        # Variance precheck: VAR is undefined on constant series
        if df["delta_C"].std() < 1e-12:
            return float("nan"), 0, "VAR: delta_C has zero variance"
        if df["S"].std() < 1e-12:
            return float("nan"), 0, "VAR: S has zero variance (Sigma_max=0?)"

        model = VAR(df)
        sel = model.select_order(maxlags=int(maxlag))
        lag = int(sel.aic) if getattr(sel, "aic", None) is not None else int(maxlag)
        if lag < 1:
            lag = 1

        fitted = model.fit(lag)
        test = fitted.test_causality(causing=["S"], caused=["delta_C"], kind="f")
        return _safe_float(test.pvalue), int(lag), ""
    except Exception as exc:
        return float("nan"), 0, f"VAR exception: {type(exc).__name__}: {exc}"


def _cointegration_p(C: np.ndarray, S: np.ndarray) -> tuple[float, str]:
    """Engle-Granger cointegration test between C and S.

    Returns (p_value, reason).
    reason is "" on success, or a diagnostic string explaining why p is NaN.
    """
    try:
        from statsmodels.tsa.stattools import coint  # type: ignore

        x = np.asarray(C, dtype=float)
        y = np.asarray(S, dtype=float)

        # Drop paired NaN
        mask = np.isfinite(x) & np.isfinite(y)
        x, y = x[mask], y[mask]
        n = len(x)

        if n < 50:
            return float("nan"), f"cointegration: n={n} < 50 after dropna"

        # Variance precheck: coint is undefined on constant series
        if np.std(x) < 1e-12:
            return float("nan"), "cointegration: C has zero variance"
        if np.std(y) < 1e-12:
            return float("nan"), "cointegration: S has zero variance (Sigma_max=0?)"

        _, p, _ = coint(x, y)
        return _safe_float(p), ""
    except Exception as exc:
        return float("nan"), f"cointegration exception: {type(exc).__name__}: {exc}"


def _render_md(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Rapport causal seuil cumulatif")
    lines.append("")
    lines.append(f"Run: {report.get('run_dir','')}".strip())
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"- Verdict: {report['verdict']}")
    lines.append(f"- Binaire (seuil detecte): {report['binary_detected']}")
    lines.append("")
    lines.append("## Seuil et persistence")
    lines.append("")
    lines.append(f"- threshold_hit_t: {report.get('threshold_hit_t')}")
    lines.append(f"- threshold_value: {report.get('threshold_value')}")
    lines.append(f"- C_mean_pre: {report.get('C_mean_pre'):.6g}")
    lines.append(f"- C_mean_post: {report.get('C_mean_post'):.6g}")
    lines.append(f"- C_mean_post_minus_pre: {report.get('C_mean_post_minus_pre'):.6g}")
    lines.append(f"- C_positive_frac_post: {report.get('C_positive_frac_post'):.6g}")
    lines.append(f"- no_false_positives_pre: {report.get('no_false_positives_pre')}")
    lines.append("")
    lines.append("## Tests statistiques")
    lines.append("")
    lines.append(f"- p_value_mean_shift_C (Welch): {report.get('p_value_mean_shift_C'):.6g}")
    lines.append(f"- p_value_mannwhitney_C (MWU, one-tailed): {report.get('p_value_mannwhitney_C'):.6g}")
    lines.append(f"- ok_p_source: {report.get('criteria',{}).get('ok_p_source')}")
    lines.append(
        f"- bootstrap_mean_diff_C: {report.get('boot_mean_diff_C'):.6g} (95% CI [{report.get('boot_ci_low_C'):.6g}, {report.get('boot_ci_high_C'):.6g}])"
    )
    if report.get("sigma_gate_note"):
        lines.append(f"- SIGMA GATE: {report.get('sigma_gate_note')}")
    lines.append("")
    lines.append("## Causalite")
    lines.append("")
    g = report.get("granger_S_to_deltaC_p", {})
    if g:
        lines.append("Granger S -> delta_C (p-values par lag)")
        for k in sorted(g.keys(), key=lambda z: int(z)):
            lines.append(f"- lag {k}: {g[k]:.6g}")
    else:
        lines.append("Granger S -> delta_C: non calcule")
    lines.append("")
    gr = report.get("granger_deltaC_to_S_p", {})
    if gr:
        lines.append("Granger delta_C -> S (p-values par lag)")
        for k in sorted(gr.keys(), key=lambda z: int(z)):
            lines.append(f"- lag {k}: {gr[k]:.6g}")
    else:
        lines.append("Granger delta_C -> S: non calcule")
    lines.append("")
    lines.append(f"- VAR causality S -> delta_C: p={report.get('var_S_to_deltaC_p'):.6g} (lag={report.get('var_lag_used')})")
    lines.append(f"- Cointegration(C,S): p={report.get('cointegration_p'):.6g}")
    lines.append("")
    lines.append("## Parametres")
    lines.append("")
    lines.append(f"- alpha: {report.get('alpha')}")
    lines.append(f"- c_mean_post_min: {report.get('c_mean_post_min')}")
    lines.append(f"- lags: {report.get('lags')}")
    lines.append(f"- pre_horizon: {report.get('pre_horizon')}")
    lines.append(f"- post_horizon: {report.get('post_horizon')}")
    lines.append(f"- baseline_n: {report.get('baseline_n')}")
    lines.append("")
    lines.append("## Critere ok_p (mean shift)")
    lines.append("")
    lines.append(f"- ok_p: {report.get('criteria',{}).get('ok_p')}")
    lines.append(f"- ok_p_source: {report.get('criteria',{}).get('ok_p_source')}")
    return "\n".join(lines) + "\n"


def _render_pdf(md_text: str, outpath: Path) -> None:
    # Minimal PDF renderer using reportlab. PDF generation is optional.
    try:
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.pdfbase import pdfmetrics  # type: ignore
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore

        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
            font_name = "DejaVuSans"
        except Exception:
            font_name = "Helvetica"

        c = canvas.Canvas(str(outpath), pagesize=A4)
        _, height = A4
        c.setFont(font_name, 12)

        x = 40
        y = height - 50
        line_h = 14
        for raw in md_text.splitlines():
            line = raw.replace("\t", " ")
            if y < 60:
                c.showPage()
                c.setFont(font_name, 12)
                y = height - 50
            c.drawString(x, y, line[:180])
            y -= line_h
        c.save()
    except Exception:
        return


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--run-dir", type=str, help="Directory containing tables/control_timeseries.csv and tables/test_timeseries.csv")
    src.add_argument("--control-csv", type=str, help="Control timeseries CSV")
    ap.add_argument("--test-csv", type=str, help="Test timeseries CSV (required if using --control-csv)")
    ap.add_argument("--outdir", type=str, default=None, help="Output directory. Default: run-dir")

    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--c-mean-post-min", type=float, default=0.1)

    ap.add_argument("--lags", type=str, default="1-10")
    ap.add_argument("--maxlag", type=int, default=10)

    ap.add_argument("--pre-horizon", type=int, default=500)
    ap.add_argument("--post-horizon", type=int, default=500)

    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=50)

    ap.add_argument("--block", type=int, default=25)
    ap.add_argument("--n-boot", type=int, default=800)
    ap.add_argument("--seed", type=int, default=123)
    ap.add_argument("--n-steps-min", type=int, default=0)

    ap.add_argument("--pdf", action="store_true", help="Also generate a minimal PDF report")
    args = ap.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir)
        control_csv = run_dir / "tables" / "control_timeseries.csv"
        test_csv = run_dir / "tables" / "test_timeseries.csv"
        outdir = Path(args.outdir) if args.outdir else run_dir
    else:
        if not args.test_csv:
            raise SystemExit("--test-csv is required when using --control-csv")
        control_csv = Path(args.control_csv)
        test_csv = Path(args.test_csv)
        outdir = Path(args.outdir) if args.outdir else control_csv.parent
        run_dir = outdir

    tabdir = _make_dirs(outdir)

    df_t = pd.read_csv(test_csv)

    # Basic sanity
    min_required = max(int(args.n_steps_min), int(args.baseline_n) + int(args.pre_horizon) + int(args.post_horizon), 30)
    short_series = bool(len(df_t) < min_required)
    for col in ["t", "C", "S", "delta_C"]:
        if col not in df_t.columns:
            raise SystemExit(f"Missing column in test: {col}")

    # Step index: always use 0..n-1 for window slicing regardless of what 't' encodes.
    # The 'step' column is written by run_real_data_demo.py; fall back to row position.
    if "step" in df_t.columns:
        df_t["_step"] = df_t["step"].reset_index(drop=True)
    else:
        df_t = df_t.reset_index(drop=True)
        df_t["_step"] = df_t.index.to_numpy(dtype=int)

    # Determine threshold hit
    thr_idx: int | None = None
    thr_val = float("nan")
    if "threshold_hit" in df_t.columns and bool((df_t["threshold_hit"] > 0).any()):
        thr_idx = int(df_t.index[df_t["threshold_hit"] > 0][0])
        thr_val = float(df_t["threshold_value"].iloc[0]) if "threshold_value" in df_t.columns else float("nan")
    else:
        thr_idx, thr_val = _detect_threshold(df_t["delta_C"].to_numpy(dtype=float), float(args.k), int(args.m), int(args.baseline_n))

    # If no hit yet, use sustained level criterion: C >= threshold_value for 3 consecutive steps.
    # This avoids false "non_detecte" when delta-based hit is silent but level is clearly above threshold.
    if thr_idx is None and ("C" in df_t.columns) and ("threshold_value" in df_t.columns):
        try:
            import numpy as _np
            c = df_t["C"].to_numpy(dtype=float)
            thr = df_t["threshold_value"].to_numpy(dtype=float)
            cond = (c >= thr)
            w = 3
            runlen = _np.convolve(cond.astype(int), _np.ones(w, dtype=int), mode="same")
            hits = _np.where(runlen >= w)[0]
            if hits.size > 0:
                thr_idx = int(hits[0])
                thr_val = float(thr[thr_idx])
        except Exception:
            pass

    # Use step index (not calendar t) for all window computations
    thr_step = None if thr_idx is None else int(df_t.loc[int(thr_idx), "_step"])
    thr_t = None if thr_idx is None else int(df_t.loc[int(thr_idx), "t"])

    # No false positives pre-threshold (slice by step)
    no_fp_pre = True
    if thr_step is not None:
        hit2, _ = _detect_threshold(
            df_t.loc[df_t["_step"] < int(thr_step), "delta_C"].to_numpy(dtype=float),
            float(args.k),
            int(args.m),
            int(args.baseline_n),
        )
        if hit2 is not None:
            no_fp_pre = False

    # Pre and post windows — always in step units
    if thr_step is None:
        s0 = int(df_t["_step"].iloc[len(df_t) // 2])
    else:
        s0 = int(thr_step)

    pre_start = max(0, s0 - int(args.pre_horizon))
    pre_end = s0
    post_start = s0
    post_end = min(int(df_t["_step"].max()) + 1, s0 + int(args.post_horizon))

    pre = df_t[(df_t["_step"] >= pre_start) & (df_t["_step"] < pre_end)].copy()
    post = df_t[(df_t["_step"] >= post_start) & (df_t["_step"] < post_end)].copy()

    C_mean_pre = float(pre["C"].mean()) if len(pre) else float("nan")
    C_mean_post = float(post["C"].mean()) if len(post) else float("nan")
    C_positive_frac_post = float((post["C"] > 0.0).mean()) if len(post) else float("nan")

    # Mean shift test (Welch)
    if len(pre) >= 10 and len(post) >= 10:
        p_shift = float(
            stats.ttest_ind(
                post["C"].to_numpy(dtype=float),
                pre["C"].to_numpy(dtype=float),
                equal_var=False,
            ).pvalue
        )
    else:
        p_shift = float("nan")

    # Mann-Whitney U (one-tailed: post > pre) — always computed for diagnostics
    # and as a fallback in the p-value cascade when Welch is NaN.
    p_mwu = float("nan")
    if len(pre) >= 5 and len(post) >= 5:
        try:
            mwu = stats.mannwhitneyu(
                post["C"].to_numpy(dtype=float),
                pre["C"].to_numpy(dtype=float),
                alternative="greater",
            )
            p_mwu = float(mwu.pvalue)
        except Exception:
            p_mwu = float("nan")

    # Bootstrap CI for mean diff
    boot_mid, boot_lo, boot_hi = _block_bootstrap_mean_diff(
        pre["C"].to_numpy(dtype=float),
        post["C"].to_numpy(dtype=float),
        block=int(args.block),
        n_boot=int(args.n_boot),
        seed=int(args.seed),
    )

    # Causality tests (S -> delta_C)
    lags = _parse_lags(str(args.lags))
    dC = df_t["delta_C"].to_numpy(dtype=float)
    S = df_t["S"].to_numpy(dtype=float)

    granger_s_to_dc = _granger_pvalues(dC, S, lags)
    granger_dc_to_s = _granger_pvalues(S, dC, lags)

    min_granger_s_to_dc = min(granger_s_to_dc.values()) if granger_s_to_dc else float("nan")
    min_granger_dc_to_s = min(granger_dc_to_s.values()) if granger_dc_to_s else float("nan")

    var_p, var_lag, var_reason = _var_causality(dC, S, maxlag=int(args.maxlag))
    coint_p, coint_reason = _cointegration_p(df_t["C"].to_numpy(dtype=float), S)

    # Criteria
    has_threshold = thr_idx is not None
    ok_c_level = bool(np.isfinite(C_mean_post) and (C_mean_post > float(args.c_mean_post_min)))
    ok_boot = bool(np.isfinite(boot_lo) and (boot_lo > 0.0))
    ok_granger = bool(np.isfinite(min_granger_s_to_dc) and (min_granger_s_to_dc <= float(args.alpha)))

    # Granger is diagnostic only in real-data mode, and especially unreliable on short series.
    granger_diagnostic_only = bool(short_series)


    # Robust ok_p: canonical nan-safe hierarchical cascade (fixed ex ante).
    # Matches WELCH_NAN_FALLBACK_POLICY in src/oric/decision.py — single source of truth.
    #
    # Priority 1: Welch t-test          (parametric, if finite)
    # Priority 2: Block bootstrap CI    (non-parametric, direction-sensitive)
    # Priority 3: Mann-Whitney U        (non-parametric, rank-based)
    # Priority 4: INDETERMINATE         (all unavailable — never a hard default failure)
    #
    # Bootstrap comes before MWU because the CI directly tests positive direction
    # shift, which is the causal claim of the triplet criterion. MWU tests rank
    # ordering without directionality.
    if np.isfinite(p_shift):
        ok_p = bool(p_shift <= float(args.alpha))
        ok_p_source = "welch"
    elif ok_boot:
        # Bootstrap CI excludes zero: strong non-parametric evidence of positive shift.
        ok_p = True
        ok_p_source = "bootstrap_fallback"
    elif np.isfinite(p_mwu):
        ok_p = bool(p_mwu <= float(args.alpha))
        ok_p_source = "mannwhitney_fallback"
    else:
        # All statistics unavailable → INDETERMINATE, not a default falsification.
        ok_p = False
        ok_p_source = "unavailable"

    # Sigma diagnostics: max |Sigma| over full series and post-window
    sigma_max_full = float("nan")
    if "Sigma" in df_t.columns:
        _sv = df_t["Sigma"].to_numpy(dtype=float)
        sigma_max_full = float(np.nanmax(np.abs(_sv))) if len(_sv) > 0 else 0.0

    # Sigma-gate: if Sigma is identically zero in the post window, the symbolic pathway
    # cannot operate. A non-detection in that context is INDETERMINATE, not a real failure.
    sigma_zero_post = False
    sigma_max_post = float("nan")
    if "Sigma" in post.columns and len(post) > 0:
        sigma_vals = post["Sigma"].to_numpy(dtype=float)
        sigma_max_post = float(np.nanmax(np.abs(sigma_vals)))
        sigma_zero_post = bool(sigma_max_post < 1e-9)

    # Reverse direction significance is a warning, not an automatic fail.
    reverse_warning = bool(np.isfinite(min_granger_dc_to_s) and (min_granger_dc_to_s <= float(args.alpha)))

    # Verdict — based solely on statistical test results.
    # sigma_zero_post is a DIAGNOSTIC (logged), never a verdict override.
    sigma_gate_note: str | None = None
    if sigma_zero_post:
        sigma_gate_note = (
            f"Sigma(t)=0 in post-window (sigma_max_post={sigma_max_post:.2e}): "
            f"symbolic pathway inoperative. Verdict based on statistical tests only."
        )

    if not has_threshold:
        verdict = "non_detecte"
        binary = False
    else:
        if (not no_fp_pre) or (not ok_c_level):
            verdict = "falsifie"
            binary = False
        elif ok_p and ok_boot:
            verdict = "seuil_detecte"
            binary = True
        elif ok_p:
            # p-value significant but bootstrap CI does not exclude zero.
            # Still decidable: detected via p-value cascade.
            verdict = "seuil_detecte"
            binary = True
            if sigma_zero_post:
                sigma_gate_note = (
                    f"Sigma(t)=0 in post-window, but mean-shift significant "
                    f"via {ok_p_source} (p <= {args.alpha}): DETECTED."
                )
        elif ok_p_source == "unavailable":
            # All statistical tests returned NaN — cannot decide.
            verdict = "indetermine_stats_indisponibles"
            binary = None  # genuinely undecidable — not False
            sigma_gate_note = (
                "All p-value sources unavailable (Welch NaN, bootstrap NaN, MWU NaN): "
                "INDETERMINATE per WELCH_NAN_FALLBACK_POLICY."
            )
        else:
            verdict = "non_detecte"
            binary = False

    report = {
        "run_dir": str(run_dir),
        "verdict": verdict,
        "binary_detected": binary,  # True/False/None (None = indeterminate)
        "alpha": float(args.alpha),
        "c_mean_post_min": float(args.c_mean_post_min),
        "lags": lags,
        "pre_horizon": int(args.pre_horizon),
        "post_horizon": int(args.post_horizon),
        "baseline_n": int(args.baseline_n),
        "series_short": bool(short_series),
        "threshold_hit_t": thr_t,
        "threshold_value": float(thr_val),
        "no_false_positives_pre": bool(no_fp_pre),
        "C_mean_pre": C_mean_pre,
        "C_mean_post": C_mean_post,
        "C_mean_post_minus_pre": float(C_mean_post - C_mean_pre) if np.isfinite(C_mean_pre) and np.isfinite(C_mean_post) else float("nan"),
        "C_positive_frac_post": C_positive_frac_post,
        "p_value_mean_shift_C": p_shift,
        "p_value_mannwhitney_C": float(p_mwu),
        "sigma_max_full": sigma_max_full,
        "sigma_max_post": sigma_max_post,
        "sigma_zero_post": bool(sigma_zero_post),
        "sigma_gate_note": sigma_gate_note,
        "boot_mean_diff_C": boot_mid,
        "boot_ci_low_C": boot_lo,
        "boot_ci_high_C": boot_hi,
        "granger_S_to_deltaC_p": granger_s_to_dc,
        "granger_deltaC_to_S_p": granger_dc_to_s,
        "min_granger_S_to_deltaC_p": _safe_float(min_granger_s_to_dc),
        "min_granger_deltaC_to_S_p": _safe_float(min_granger_dc_to_s),
        "reverse_warning": bool(reverse_warning),
        "granger_diagnostic_only": bool(granger_diagnostic_only),
        "var_S_to_deltaC_p": float(var_p),
        "var_lag_used": int(var_lag),
        "var_reason": var_reason or None,
        "cointegration_p": float(coint_p),
        "cointegration_reason": coint_reason or None,
        "criteria": {
            "has_threshold": bool(has_threshold),
            "ok_c_level": bool(ok_c_level),
            "ok_p": bool(ok_p),
            "ok_p_source": str(ok_p_source),
            "ok_boot": bool(ok_boot),
            "ok_granger": bool(ok_granger),
            "granger_diagnostic_only": bool(granger_diagnostic_only),
        },
    }

    # One-row summary CSV
    row = {
        "verdict": verdict,
        "binary_detected": binary,  # True/False/None (None = indeterminate)
        "threshold_hit_t": thr_t,
        "threshold_value": float(thr_val),
        "no_false_positives_pre": bool(no_fp_pre),
        "C_mean_pre": C_mean_pre,
        "C_mean_post": C_mean_post,
        "C_positive_frac_post": C_positive_frac_post,
        "p_value_mean_shift_C": p_shift,
        "p_value_mannwhitney_C": float(p_mwu),
        "sigma_zero_post": bool(sigma_zero_post),
        "ok_p_source": str(ok_p_source),
        "boot_ci_low_C": boot_lo,
        "boot_ci_high_C": boot_hi,
        "min_granger_S_to_deltaC_p": _safe_float(min_granger_s_to_dc),
        "var_S_to_deltaC_p": float(var_p),
        "cointegration_p": float(coint_p),
        "reverse_warning": bool(reverse_warning),
        "ok_p_source": str(ok_p_source),
    }

    pd.DataFrame([row]).to_csv(tabdir / "causal_tests_summary.csv", index=False)
    (tabdir / "verdict.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = _render_md(report)
    (tabdir / "causal_report.md").write_text(md, encoding="utf-8")
    if bool(args.pdf):
        _render_pdf(md, tabdir / "causal_report.pdf")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
