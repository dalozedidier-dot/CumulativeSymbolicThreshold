#!/usr/bin/env python3
"""04_Code/pipeline/tests_causaux.py

Causal and falsifiability checks for the cumulative symbolic threshold.

Core intent
- Validate that a transition (threshold hit) exists on delta_C(t)
- Validate that C(t) becomes stably positive post-transition
- Validate that the transition is attributable to S(t)

Implemented checks (lightweight but stricter than the legacy diff-in-diff)
- Threshold hit on delta_C (baseline-based)
- No false positives pre-threshold (same detector, same baseline)
- Mean shift test on C (pre vs post), with p-value
- Block bootstrap CI for (mean_post - mean_pre)
- Granger causality tests (S -> delta_C, and reverse)
- VAR causality test (S -> delta_C)
- Cointegration test (C, S) as a robustness signal under non-stationarity

Outputs
- <outdir>/tables/causal_tests_summary.csv
- <outdir>/tables/verdict.json
- <outdir>/tables/causal_report.md
- <outdir>/tables/causal_report.pdf (optional)

Usage (recommended with run_ori_c_demo outputs)
python 04_Code/pipeline/tests_causaux.py \
  --run-dir 05_Results/threshold_validation/demo_001/run_0001 \
  --alpha 0.01 --c-mean-post-min 0.1 --lags 1-10 --n-steps-min 2000
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure 04_Code is on sys.path so `import pipeline.*` works when scripts are executed directly.
_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import argparse
import json

import numpy as np
import pandas as pd
from scipy import stats


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

    if len(x_pre) < 5 or len(x_post) < 5:
        return float("nan"), float("nan"), float("nan")

    block = int(block)
    if block < 5:
        block = 5

    def _sample(x: np.ndarray) -> np.ndarray:
        n = len(x)
        if n <= block:
            idx = rng.integers(0, n, size=n)
            return x[idx]
        out = []
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


def _granger_pvalues(delta_c: np.ndarray, s: np.ndarray, lags: list[int]) -> dict:
    # grangercausalitytests expects shape (n,2), tests whether 2nd col causes 1st col.
    try:
        from statsmodels.tsa.stattools import grangercausalitytests

        data = np.column_stack([delta_c, s])
        maxlag = int(max(lags))
        res = grangercausalitytests(data, maxlag=maxlag, verbose=False)
        out = {}
        for lag in lags:
            lag = int(lag)
            if lag in res:
                p = res[lag][0]["ssr_ftest"][1]
                out[str(lag)] = _safe_float(p)
        return out
    except Exception:
        return {}


def _var_causality(delta_c: np.ndarray, s: np.ndarray, maxlag: int) -> tuple[float, int]:
    try:
        from statsmodels.tsa.api import VAR

        df = pd.DataFrame({"delta_C": delta_c, "S": s}).dropna()
        if len(df) < max(20, maxlag * 5):
            return float("nan"), 0

        model = VAR(df)
        sel = model.select_order(maxlags=int(maxlag))
        lag = int(sel.aic) if getattr(sel, "aic", None) is not None else int(maxlag)
        if lag < 1:
            lag = 1

        fitted = model.fit(lag)
        test = fitted.test_causality(causing=["S"], caused=["delta_C"], kind="f")
        return _safe_float(test.pvalue), int(lag)
    except Exception:
        return float("nan"), 0


def _cointegration_p(C: np.ndarray, S: np.ndarray) -> float:
    try:
        from statsmodels.tsa.stattools import coint

        x = np.asarray(C, dtype=float)
        y = np.asarray(S, dtype=float)
        n = min(len(x), len(y))
        if n < 50:
            return float("nan")
        stat, p, _ = coint(x[:n], y[:n])
        return _safe_float(p)
    except Exception:
        return float("nan")


def _render_md(report: dict) -> str:
    lines = []
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
    lines.append(
        f"- bootstrap_mean_diff_C: {report.get('boot_mean_diff_C'):.6g} (95% CI [{report.get('boot_ci_low_C'):.6g}, {report.get('boot_ci_high_C'):.6g}])"
    )
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

    return "\n".join(lines) + "\n"


def _render_pdf(md_text: str, outpath: Path) -> None:
    # Minimal PDF renderer using reportlab. No layout ambition, just stable export.
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas

        # Use a standard font if available; fall back to built-in if not.
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
            font_name = "DejaVuSans"
        except Exception:
            font_name = "Helvetica"

        c = canvas.Canvas(str(outpath), pagesize=A4)
        width, height = A4

        c.setFont(font_name, 12)
        x = 40
        y = height - 50
        line_h = 14

        for raw in md_text.splitlines():
            line = raw.replace("\t", "    ")
            if y < 60:
                c.showPage()
                c.setFont(font_name, 12)
                y = height - 50
            c.drawString(x, y, line[:180])
            y -= line_h

        c.save()
    except Exception:
        # PDF generation is optional
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

    ap.add_argument("--n-steps-min", type=int, default=2000)

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

    df_c = pd.read_csv(control_csv)
    df_t = pd.read_csv(test_csv)

    # Basic sanity
    if len(df_t) < int(args.n_steps_min):
        # Not a hard error, but record it
        short_series = True
    else:
        short_series = False

    for col in ["t", "C", "S", "delta_C"]:
        if col not in df_t.columns:
            raise SystemExit(f"Missing column in test: {col}")

    # Determine threshold hit
    thr_idx = None
    thr_val = float("nan")
    if "threshold_hit" in df_t.columns and bool((df_t["threshold_hit"] > 0).any()):
        thr_idx = int(df_t.index[df_t["threshold_hit"] > 0][0])
        thr_val = float(df_t["threshold_value"].iloc[0]) if "threshold_value" in df_t.columns else float("nan")
    else:
        thr_idx, thr_val = _detect_threshold(df_t["delta_C"].to_numpy(dtype=float), float(args.k), int(args.m), int(args.baseline_n))

    thr_t = None if thr_idx is None else int(df_t.loc[int(thr_idx), "t"])

    # No false positives pre-threshold
    no_fp_pre = True
    if thr_idx is not None:
        hit2, _ = _detect_threshold(df_t.loc[df_t["t"] < int(thr_t), "delta_C"].to_numpy(dtype=float), float(args.k), int(args.m), int(args.baseline_n))
        if hit2 is not None:
            no_fp_pre = False

    # Pre and post windows
    if thr_t is None:
        t0 = int(df_t["t"].iloc[len(df_t) // 2])
    else:
        t0 = int(thr_t)

    pre_start = max(0, t0 - int(args.pre_horizon))
    pre_end = t0
    post_start = t0
    post_end = min(int(df_t["t"].max()) + 1, t0 + int(args.post_horizon))

    pre = df_t[(df_t["t"] >= pre_start) & (df_t["t"] < pre_end)].copy()
    post = df_t[(df_t["t"] >= post_start) & (df_t["t"] < post_end)].copy()

    C_mean_pre = float(pre["C"].mean()) if len(pre) else float("nan")
    C_mean_post = float(post["C"].mean()) if len(post) else float("nan")

    C_positive_frac_post = float((post["C"] > 0.0).mean()) if len(post) else float("nan")

    # Mean shift test (Welch)
    if len(pre) >= 10 and len(post) >= 10:
        p_shift = float(stats.ttest_ind(post["C"].to_numpy(dtype=float), pre["C"].to_numpy(dtype=float), equal_var=False).pvalue)
    else:
        p_shift = float("nan")

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

    var_p, var_lag = _var_causality(dC, S, maxlag=int(args.maxlag))
    coint_p = _cointegration_p(df_t["C"].to_numpy(dtype=float), S)

    # Criteria
    has_threshold = thr_idx is not None
    ok_c_level = bool(np.isfinite(C_mean_post) and (C_mean_post > float(args.c_mean_post_min)))
    ok_p = bool(np.isfinite(p_shift) and (p_shift <= float(args.alpha)))
    ok_boot = bool(np.isfinite(boot_lo) and (boot_lo > 0.0))

    ok_granger = bool(np.isfinite(min_granger_s_to_dc) and (min_granger_s_to_dc <= float(args.alpha)))

    # If reverse direction is also strongly significant, we do not automatically fail.
    # We mark it as a warning signal in the report.
    reverse_warning = bool(np.isfinite(min_granger_dc_to_s) and (min_granger_dc_to_s <= float(args.alpha)))

    # Verdict
    if not has_threshold:
        verdict = "non_detecte"
        binary = False
    else:
        if (not no_fp_pre) or (not ok_c_level):
            verdict = "falsifie"
            binary = False
        elif ok_p and ok_boot and ok_granger:
            verdict = "seuil_detecte"
            binary = True
        else:
            verdict = "non_detecte"
            binary = False

    report = {
        "run_dir": str(run_dir),
        "verdict": verdict,
        "binary_detected": bool(binary),
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
        "boot_mean_diff_C": boot_mid,
        "boot_ci_low_C": boot_lo,
        "boot_ci_high_C": boot_hi,
        "granger_S_to_deltaC_p": granger_s_to_dc,
        "granger_deltaC_to_S_p": granger_dc_to_s,
        "min_granger_S_to_deltaC_p": _safe_float(min_granger_s_to_dc),
        "min_granger_deltaC_to_S_p": _safe_float(min_granger_dc_to_s),
        "reverse_warning": bool(reverse_warning),
        "var_S_to_deltaC_p": float(var_p),
        "var_lag_used": int(var_lag),
        "cointegration_p": float(coint_p),
        "criteria": {
            "has_threshold": bool(has_threshold),
            "ok_c_level": bool(ok_c_level),
            "ok_p": bool(ok_p),
            "ok_boot": bool(ok_boot),
            "ok_granger": bool(ok_granger),
        },
    }

    # One-row summary CSV
    row = {
        "verdict": verdict,
        "binary_detected": bool(binary),
        "threshold_hit_t": thr_t,
        "threshold_value": float(thr_val),
        "no_false_positives_pre": bool(no_fp_pre),
        "C_mean_pre": C_mean_pre,
        "C_mean_post": C_mean_post,
        "C_positive_frac_post": C_positive_frac_post,
        "p_value_mean_shift_C": p_shift,
        "boot_ci_low_C": boot_lo,
        "boot_ci_high_C": boot_hi,
        "min_granger_S_to_deltaC_p": _safe_float(min_granger_s_to_dc),
        "var_S_to_deltaC_p": float(var_p),
        "cointegration_p": float(coint_p),
        "reverse_warning": bool(reverse_warning),
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
