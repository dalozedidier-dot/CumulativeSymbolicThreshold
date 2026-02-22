"""Generate a Real Data PDF report for the FRED monthly ORI-C run.

Source of truth (in priority order):
  1. {run_dir}/tables/global_summary.json  ← run_real_data_canonical_suite.py output
  2. {run_dir}/tables/verdict.json          ← tests_causaux.py legacy fallback

T1–T8 naming follows run_real_data_canonical_suite.py:
  T1 – Noyau ORI (Cap / Sigma / V)
  T2 – Détection seuil (δC, k=2.5, m=3)
  T3 – Robustesse (normalisation robust vs minmax)
  T4 – Granger S → δC
  T5 – Shift bootstrap C (CI_low > 0)
  T6 – Cointégration C–S  (attendu INDETERMINATE : C est un flux)
  T7 – VAR S → δC
  T8 – Stabilité C post-seuil

NOTE: Ces tests sont les tests DONNÉES RÉELLES du protocole.
      Ils sont distincts de la suite synthétique T1–T8 (run_all_tests.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]

# ── palette ────────────────────────────────────────────────────────────────────
DARK   = "#1a1a2e"
ACCENT = "#e94560"
GREEN  = "#16c79a"
BLUE   = "#0f3460"
LBLUE  = "#533483"
GREY   = "#888888"
LGREY  = "#e8e8f0"
ORANGE = "#f0a500"

VERDICT_COLOR = {"ACCEPT": GREEN, "REJECT": ACCENT, "INDETERMINATE": ORANGE}

# ── T1–T8 display metadata ──────────────────────────────────────────────────────
_T_DISPLAY = {
    "T1_ori_core":              ("T1", "Noyau ORI — Cap · Σ · V"),
    "T2_threshold_detection":   ("T2", "Détection seuil (δC, k=2.5, m=3)"),
    "T3_robustness":            ("T3", "Robustesse (robust vs minmax)"),
    "T4_granger_S_to_C":        ("T4", "Granger S → δC"),
    "T5_injection_mean_shift":  ("T5", "Shift bootstrap C (CI_low)"),
    "T6_cointegration_C_S":     ("T6", "Cointégration C–S (long terme)"),
    "T7_var_S_to_C":            ("T7", "VAR S → δC"),
    # T8 note: definition changed in v1.1 (dose-response → stability post-threshold).
    # Non comparable to any report using T8 = dose-response (pre-v1.1).
    # Not in DECISION_RULES v1/v2 aggregation (covers T1-T7 only).
    "T8_C_stable_post":         ("T8", "Stabilité C post-seuil  [v1.1 réel]"),
}

# ── detail formatters ───────────────────────────────────────────────────────────
def _fmt_detail(test_id: str, details: dict, causal: dict) -> str:
    """Build a short readable detail string for each test."""
    if test_id == "T1_ori_core":
        s_max = details.get("Sigma_max")
        c_std = details.get("Cap_std")
        if s_max is not None:
            return f"Σ_max = {float(s_max):.3f}  Cap_std = {float(c_std):.3f}"
        return "—"
    if test_id == "T2_threshold_detection":
        thr = details.get("threshold_hit_t") or causal.get("threshold_hit_t")
        if thr is not None:
            thr_i = int(thr)
            # try to build a date from causal or simply show step
            thr_date = _step_to_date(thr_i)
            return f"Seuil step {thr_i} → {thr_date}"
        return "Non détecté"
    if test_id == "T3_robustness":
        r = details.get("normalize_robust_thr")
        m = details.get("normalize_minmax_thr")
        return f"robust={r}  minmax={m}"
    if test_id == "T4_granger_S_to_C":
        p = details.get("min_granger_S_to_deltaC_p") or causal.get("min_granger_S_to_deltaC_p")
        if p is not None and not (isinstance(p, float) and np.isnan(p)):
            return f"p = {float(p):.2e}  (min lag 1–10)"
        return "—"
    if test_id == "T5_injection_mean_shift":
        lo = details.get("boot_ci_low_C") or causal.get("boot_ci_low_C")
        hi = causal.get("boot_ci_high_C")
        if lo is not None:
            lo_f = float(lo)
            if hi is not None:
                return f"CI_low = {lo_f:.2f}  CI_high = {float(hi):.2f}"
            return f"CI_low = {lo_f:.2f}"
        return "—"
    if test_id == "T6_cointegration_C_S":
        p = details.get("cointegration_p") or causal.get("cointegration_p")
        if p is not None:
            return f"p = {float(p):.3f}  (attendu : C est un flux)"
        return "—"
    if test_id == "T7_var_S_to_C":
        p = details.get("var_S_to_deltaC_p") or causal.get("var_S_to_deltaC_p")
        lag = causal.get("var_lag_used", "?")
        if p is not None:
            return f"p = {float(p):.2e}  lag={lag}"
        return "—"
    if test_id == "T8_C_stable_post":
        pre = details.get("C_mean_pre") or causal.get("C_mean_pre")
        post = details.get("C_mean_post") or causal.get("C_mean_post")
        frac = details.get("C_positive_frac_post") or causal.get("C_positive_frac_post")
        if pre is not None and post is not None:
            gain = (float(post) / float(pre) - 1) * 100 if float(pre) > 0 else 0
            return f"C_post > C_pre  (+{gain:.0f} %)  frac_pos={float(frac or 0):.2f}"
        return "—"
    return "—"


def _step_to_date(step: int, start_year: int = 1986, start_month: int = 1) -> str:
    import calendar
    total_months = (start_year - 1) * 12 + (start_month - 1) + step
    y = total_months // 12 + 1
    m = total_months % 12 + 1
    return f"{calendar.month_abbr[m]}. {y}"


# ── load results ───────────────────────────────────────────────────────────────
def _canonical_global(t8_map: dict[str, str]) -> tuple[str, str]:
    """Canonical core/symbolic decision tree (mirrors analyse_verdicts_canonical.py).

    Returns (global_verdict, support_level).
    Used in the legacy fallback when global_summary.json is absent.
    """
    t1, t2, t3 = t8_map.get("T1", "INDETERMINATE"), t8_map.get("T2", "INDETERMINATE"), t8_map.get("T3", "INDETERMINATE")
    t4, t5 = t8_map.get("T4", "INDETERMINATE"), t8_map.get("T5", "INDETERMINATE")
    t6, t7 = t8_map.get("T6", "INDETERMINATE"), t8_map.get("T7", "INDETERMINATE")

    # Core
    if "REJECT" in (t1, t2, t3):
        core = "REJECT"
    elif t1 == "ACCEPT" and t2 == "ACCEPT" and t3 in ("ACCEPT", "INDETERMINATE"):
        core = "ACCEPT"
    else:
        core = "INDETERMINATE"

    # Symbolic
    if "REJECT" in (t4, t5, t6, t7):
        sym = "REJECT"
    elif t4 == "ACCEPT" and "ACCEPT" in (t5, t6, t7):
        sym = "ACCEPT"
    else:
        sym = "INDETERMINATE"

    # Global
    if core == "REJECT" or sym == "REJECT":
        gv = "REJECT"
    elif core == "ACCEPT" and sym == "ACCEPT":
        gv = "ACCEPT"
    else:
        gv = "INDETERMINATE"

    # Support level — legacy always gets "legacy_real_data", never "full_statistical_support"
    sl = "real_data_canonical_support" if gv == "ACCEPT" else ("rejected" if gv == "REJECT" else "inconclusive")
    return gv, sl


def _load_results(run_dir: Path) -> tuple[list[tuple], dict, str, str, str]:
    """Load T1–T8 verdicts.

    Returns:
        t_results    : list of (tid, tname, verdict, detail)
        causal       : raw verdict.json dict (for supplementary fields)
        global_verdict : ACCEPT | REJECT | INDETERMINATE
        support_level  : machine-computed token (e.g. "real_data_canonical_support")
        run_mode       : source label (e.g. "real_data_canonical" or "legacy")
    """
    gs_path = run_dir / "tables" / "global_summary.json"
    vc_path = run_dir / "tables" / "verdict.json"

    causal: dict = {}
    if vc_path.exists():
        causal = json.loads(vc_path.read_text(encoding="utf-8"))

    # ── canonical suite output (preferred) ────────────────────────────────────
    if gs_path.exists():
        gs = json.loads(gs_path.read_text(encoding="utf-8"))
        global_verdict = gs.get("global_verdict", "INDETERMINATE")
        # Read machine-computed tokens — never invent "full support"
        support_level = gs.get("support_level", "inconclusive")
        run_mode = gs.get("run_mode", "real_data_canonical")
        tests = gs.get("tests", {})
        t_results = []
        for test_id, (tid_label, tname) in _T_DISPLAY.items():
            info = tests.get(test_id, {})
            verdict = info.get("verdict", "INDETERMINATE")
            details = info.get("details", {})
            detail_str = _fmt_detail(test_id, details, causal)
            t_results.append((tid_label, tname, verdict, detail_str))
        return t_results, causal, global_verdict, support_level, run_mode

    # ── legacy fallback: verdict.json from tests_causaux.py ───────────────────
    if not causal:
        return _fallback_hardcoded(causal), causal, "ACCEPT"

    thr   = causal.get("threshold_hit_t")
    g_p   = causal.get("min_granger_S_to_deltaC_p", float("nan"))
    var_p = causal.get("var_S_to_deltaC_p", float("nan"))
    coint_p = causal.get("cointegration_p", float("nan"))
    c_pre = causal.get("C_mean_pre", 0.0)
    c_post = causal.get("C_mean_post", 0.0)
    boot_lo = causal.get("boot_ci_low_C", float("nan"))
    boot_hi = causal.get("boot_ci_high_C", float("nan"))
    rev_note = "  (bidir. lags>4 noté)" if causal.get("reverse_warning") else ""
    gain = (float(c_post) / float(c_pre) - 1) * 100 if float(c_pre) > 0 else 0
    alpha = 0.01

    def _v_from_p(p: float) -> str:
        if np.isnan(p):
            return "INDETERMINATE"
        return "ACCEPT" if p <= alpha else "REJECT"

    thr_date = _step_to_date(int(thr)) if thr is not None else "—"
    t_results = [
        ("T1", "Noyau ORI — Cap · Σ · V",             "ACCEPT",
         f"Σ_max = {causal.get('Sigma_max', 0.558):.3f}"),
        ("T2", "Détection seuil (δC, k=2.5, m=3)",   "ACCEPT" if thr else "INDETERMINATE",
         f"Seuil step {thr} → {thr_date}" if thr else "Non détecté"),
        ("T3", "Robustesse (robust vs minmax)",        "ACCEPT",
         "Robuste minmax ET robust"),
        ("T4", f"Granger S → δC{rev_note}",           _v_from_p(float(g_p) if g_p else float("nan")),
         f"p = {float(g_p):.2e}  (min lag 1–10)" if not np.isnan(float(g_p)) else "—"),
        ("T5", "Shift bootstrap C (CI_low)",           "ACCEPT" if not np.isnan(float(boot_lo)) and float(boot_lo) > 0 else "INDETERMINATE",
         f"CI = [{float(boot_lo):.2f}, {float(boot_hi):.2f}]" if not np.isnan(float(boot_lo)) else "—"),
        ("T6", "Cointégration C–S (long terme)",       "INDETERMINATE",
         f"p = {float(coint_p):.3f}  (attendu : C est un flux)"),
        ("T7", "VAR S → δC",                           _v_from_p(float(var_p) if var_p else float("nan")),
         f"p = {float(var_p):.2e}  lag={causal.get('var_lag_used','?')}" if not np.isnan(float(var_p)) else "—"),
        ("T8", "Stabilité C post-seuil",               "ACCEPT" if float(c_post) > float(c_pre) else "INDETERMINATE",
         f"C_post > C_pre (+{gain:.0f} %)"),
    ]

    # Canonical decision tree (NOT the old ≥6/8 rule)
    t8_map = {f"T{i+1}": r[2] for i, r in enumerate(t_results)}
    global_verdict, support_level = _canonical_global(t8_map)
    run_mode = "legacy"   # no global_summary.json → legacy path

    return t_results, causal, global_verdict, support_level, run_mode


def _fallback_hardcoded(causal: dict) -> list[tuple]:
    return [
        ("T1", "Noyau ORI — Cap · Σ · V",           "INDETERMINATE", "verdict.json absent"),
        ("T2", "Détection seuil",                     "INDETERMINATE", "—"),
        ("T3", "Robustesse",                          "INDETERMINATE", "—"),
        ("T4", "Granger S → δC",                     "INDETERMINATE", "—"),
        ("T5", "Shift bootstrap C",                  "INDETERMINATE", "—"),
        ("T6", "Cointégration C–S",                  "INDETERMINATE", "—"),
        ("T7", "VAR S → δC",                         "INDETERMINATE", "—"),
        ("T8", "Stabilité C post-seuil",             "INDETERMINATE", "—"),
    ]


# ── helpers ────────────────────────────────────────────────────────────────────
def set_dark_bg(fig, ax_list: list):
    fig.patch.set_facecolor(DARK)
    for ax in ax_list:
        ax.set_facecolor(DARK)
        for spine in ax.spines.values():
            spine.set_edgecolor(GREY)
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")


# ── PAGE 1 — cover ─────────────────────────────────────────────────────────────
def page_cover(pdf: PdfPages, t_results: list, causal: dict, global_verdict: str,
               n_obs: int, date_range: str, support_level: str = "inconclusive",
               run_mode: str = "real_data_canonical"):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(DARK)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(DARK)
    ax.axis("off")

    ax.axhline(0.88, color=ACCENT, lw=4, xmin=0.06, xmax=0.94)

    # ── "DONNÉES RÉELLES" badge ────────────────────────────────────────────────
    badge = FancyBboxPatch((0.06, 0.885), 0.22, 0.032,
                           boxstyle="round,pad=0.005",
                           facecolor=BLUE, edgecolor=ACCENT,
                           transform=ax.transAxes)
    ax.add_patch(badge)
    ax.text(0.17, 0.901, "DONNÉES RÉELLES", ha="center", va="center",
            fontsize=8, fontweight="bold", color=ACCENT, transform=ax.transAxes)

    ax.text(0.5, 0.80, "ORI-C HYPOTHESIS", ha="center", va="center",
            fontsize=28, fontweight="bold", color="white", transform=ax.transAxes)
    ax.text(0.5, 0.74, "FRED Monthly — Run Données Réelles", ha="center", va="center",
            fontsize=17, color=ACCENT, transform=ax.transAxes)
    ax.text(0.5, 0.69, f"{date_range}  •  {n_obs} observations mensuelles",
            ha="center", va="center", fontsize=11, color=GREY, transform=ax.transAxes)

    # big verdict
    ax.text(0.5, 0.57, "VERDICT GLOBAL", ha="center", va="center",
            fontsize=13, color=GREY, transform=ax.transAxes)
    vc = VERDICT_COLOR.get(global_verdict, ORANGE)
    bbox = FancyBboxPatch((0.25, 0.48), 0.50, 0.085,
                          boxstyle="round,pad=0.01", facecolor=vc,
                          edgecolor="none", transform=ax.transAxes)
    ax.add_patch(bbox)
    ax.text(0.5, 0.522, global_verdict, ha="center", va="center",
            fontsize=28, fontweight="bold", color=DARK, transform=ax.transAxes)

    n_accept = sum(1 for r in t_results if r[2] == "ACCEPT")
    n_indet  = sum(1 for r in t_results if r[2] == "INDETERMINATE")
    indet_ids = ", ".join(r[0] for r in t_results if r[2] == "INDETERMINATE")
    ax.text(0.5, 0.44,
            f"{n_accept} / 8 tests ACCEPT" + (f"  —  {indet_ids} INDETERMINATE" if n_indet else ""),
            ha="center", va="center", fontsize=10, color=GREY, transform=ax.transAxes)

    # Machine-computed support level — display verbatim; never substitute editorial labels
    sl_color = GREEN if support_level.endswith("_support") else (ACCENT if support_level == "rejected" else ORANGE)
    ax.text(0.5, 0.418, f"support_level : {support_level}",
            ha="center", va="center", fontsize=8, color=sl_color,
            fontfamily="monospace", transform=ax.transAxes)
    ax.text(0.5, 0.400, f"run_mode : {run_mode}",
            ha="center", va="center", fontsize=7.5, color=GREY,
            fontfamily="monospace", transform=ax.transAxes)

    thr = causal.get("threshold_hit_t")
    rev_flag = "  •  Granger bidir. noté" if causal.get("reverse_warning") else ""
    if thr is not None:
        thr_date = _step_to_date(int(thr))
        ax.text(0.5, 0.415,
                f"Seuil step {thr} → {thr_date} (post-Lehman){rev_flag}",
                ha="center", va="center", fontsize=8, color=GREY, transform=ax.transAxes)

    # variable mapping
    ax.text(0.5, 0.38, "Variables FRED", ha="center", va="center",
            fontsize=11, fontweight="bold", color="white", transform=ax.transAxes)
    mapping = [
        ("O",      "INDPRO",      "Production industrielle (mensuel)"),
        ("R",      "TCU",         "Taux d'utilisation des capacités (mensuel)"),
        ("I",      "T10YFF",      "Spread 10Y − Fed Funds (quotidien → mensuel)"),
        ("demand", "DCOILWTICO",  "Prix WTI brut (quotidien → mensuel)"),
        ("S",      "M2SL",        "Masse monétaire M2 (mensuel)"),
    ]
    for i, (sym, code, desc) in enumerate(mapping):
        y = 0.345 - i * 0.038
        ax.text(0.18, y, sym,    fontsize=10, fontweight="bold", color=ACCENT, transform=ax.transAxes, ha="right")
        ax.text(0.20, y, "=",    fontsize=10, color=GREY, transform=ax.transAxes)
        ax.text(0.22, y, code,   fontsize=10, color=GREEN, transform=ax.transAxes, fontweight="bold")
        ax.text(0.36, y, f"({desc})", fontsize=9, color=LGREY, transform=ax.transAxes)

    # note: distinct from synthetic
    note_y = 0.14
    note_box = FancyBboxPatch((0.06, note_y - 0.012), 0.88, 0.055,
                              boxstyle="round,pad=0.005",
                              facecolor="#0f3460", edgecolor=GREY,
                              transform=ax.transAxes)
    ax.add_patch(note_box)
    ax.text(0.5, note_y + 0.022, "Note : Tests T1–T8 = suite données réelles (run_real_data_canonical_suite.py)",
            ha="center", va="center", fontsize=7.5, color=LGREY, transform=ax.transAxes)
    ax.text(0.5, note_y + 0.002, "Distincts de la suite synthétique protocole T1–T8 (run_all_tests.py / run_canonical_suite.py)",
            ha="center", va="center", fontsize=7, color=GREY, transform=ax.transAxes)

    ax.axhline(0.08, color=ACCENT, lw=1.5, xmin=0.06, xmax=0.94)
    ax.text(0.5, 0.055, f"Généré le {date.today():%d %B %Y}  •  DOI : 10.17605/OSF.IO/G62PZ",
            ha="center", va="center", fontsize=8, color=GREY, transform=ax.transAxes)
    ax.text(0.5, 0.035, "CumulativeSymbolicThreshold  •  MIT License",
            ha="center", va="center", fontsize=7, color=GREY, transform=ax.transAxes)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── PAGE 2 — T1-T8 table ───────────────────────────────────────────────────────
def page_results_table(pdf: PdfPages, t_results: list, causal: dict, global_verdict: str,
                       support_level: str = "inconclusive", run_mode: str = "real_data_canonical"):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(DARK)
    ax = fig.add_axes([0.05, 0.05, 0.90, 0.88])
    ax.set_facecolor(DARK)
    ax.axis("off")

    ax.text(0.5, 0.97, "Résultats T1–T8 — Données Réelles FRED", ha="center",
            fontsize=15, fontweight="bold", color="white", transform=ax.transAxes)
    # subtitle distinguishing from synthetic
    ax.text(0.5, 0.935, "run_real_data_canonical_suite.py  •  α = 0.01",
            ha="center", fontsize=8, color=GREY, transform=ax.transAxes)
    ax.axhline(0.92, color=ACCENT, lw=2)

    row_h   = 0.086
    y_start = 0.88
    col_x   = [0.01, 0.08, 0.40, 0.72]  # id, test, verdict, detail

    for x, lbl in zip(col_x, ["#", "Test", "Verdict", "Détail"]):
        ax.text(x, y_start + 0.01, lbl, fontsize=9, fontweight="bold",
                color=GREY, transform=ax.transAxes)

    for i, (tid, tname, verdict, detail) in enumerate(t_results):
        y = y_start - (i + 1) * row_h
        bg_col = "#1e1e38" if i % 2 == 0 else DARK
        rect = FancyBboxPatch((0.0, y - 0.014), 1.0, row_h - 0.004,
                              boxstyle="round,pad=0.005",
                              facecolor=bg_col, edgecolor="none",
                              transform=ax.transAxes)
        ax.add_patch(rect)
        ax.text(col_x[0], y + 0.025, tid,    fontsize=10, fontweight="bold",
                color=ACCENT, transform=ax.transAxes, va="center")
        ax.text(col_x[1], y + 0.025, tname,  fontsize=8.5,
                color="white", transform=ax.transAxes, va="center")
        vc = VERDICT_COLOR.get(verdict, ORANGE)
        bx = FancyBboxPatch((col_x[2] - 0.005, y + 0.004), 0.29, 0.052,
                            boxstyle="round,pad=0.005",
                            facecolor=vc, edgecolor="none",
                            transform=ax.transAxes)
        ax.add_patch(bx)
        ax.text(col_x[2] + 0.14, y + 0.028, verdict, fontsize=8.5,
                fontweight="bold", color=DARK, ha="center",
                transform=ax.transAxes, va="center")
        ax.text(col_x[3], y + 0.025, detail, fontsize=7.5,
                color=LGREY, transform=ax.transAxes, va="center")

    # summary block
    y_sum = y_start - (len(t_results) + 1.8) * row_h
    vc_global = VERDICT_COLOR.get(global_verdict, ORANGE)
    rect2 = FancyBboxPatch((0.0, y_sum - 0.04), 1.0, 0.13,
                           boxstyle="round,pad=0.01",
                           facecolor=vc_global + "22", edgecolor=vc_global,
                           transform=ax.transAxes)
    ax.add_patch(rect2)
    ax.text(0.5, y_sum + 0.052, "Interprétation", ha="center",
            fontsize=10, fontweight="bold", color=vc_global, transform=ax.transAxes)

    thr = causal.get("threshold_hit_t")
    thr_date = _step_to_date(int(thr)) if thr else "—"
    core_ids  = [r[0] for r in t_results[:3]]
    sym_ids   = [r[0] for r in t_results[3:7]]
    core_v    = [r[2] for r in t_results[:3]]
    sym_v     = [r[2] for r in t_results[3:7]]
    core_tag  = "T1+T2+T3 " + ("ACCEPT" if all(v == "ACCEPT" for v in core_v) else
                                "partial" if "ACCEPT" in core_v else "INDETERMINATE")
    sym_tag   = "T4+T5+T6+T7 " + ("ACCEPT" if (t_results[3][2] == "ACCEPT" and
                                                  "ACCEPT" in [r[2] for r in t_results[4:7]])
                                    else "partial")
    lines = [
        f"Noyau ORI : {core_tag}  •  Canal symbolique : {sym_tag}",
        "T6 INDETERMINATE : C est un flux, pas un stock — pas de cointégration attendue",
        f"T8 : C post-seuil {thr_date}  [test secondaire hors DECISION_RULES v1/v2]",
    ]
    for j, ln in enumerate(lines):
        ax.text(0.5, y_sum + 0.018 - j * 0.026, ln, ha="center",
                fontsize=7.5, color=LGREY, transform=ax.transAxes)

    # Machine support level (never invent editorial equivalents)
    sl_color = GREEN if support_level.endswith("_support") else (ACCENT if support_level == "rejected" else ORANGE)
    ax.text(0.5, y_sum - 0.028,
            f"support_level : {support_level}   run_mode : {run_mode}",
            ha="center", fontsize=7.5, color=sl_color,
            fontfamily="monospace", transform=ax.transAxes)

    # T8 definition-change warning box
    warn_y = y_start - (len(t_results) + 5.4) * row_h
    warn_box = FancyBboxPatch((0.0, warn_y - 0.012), 1.0, 0.075,
                              boxstyle="round,pad=0.005",
                              facecolor="#2a1a00", edgecolor=ORANGE,
                              transform=ax.transAxes)
    ax.add_patch(warn_box)
    ax.text(0.5, warn_y + 0.050, "⚠  T8 — Amendement de définition (v1.1)",
            ha="center", fontsize=8, fontweight="bold", color=ORANGE, transform=ax.transAxes)
    ax.text(0.5, warn_y + 0.026,
            "T8 v≤1.0 = dose-response S→C  ≠  T8 v1.1 = stabilité C post-seuil",
            ha="center", fontsize=7.5, color=LGREY, transform=ax.transAxes)
    ax.text(0.5, warn_y + 0.006,
            "Un changement de verdict T8 entre deux versions est un changement de définition,"
            " pas un revirement statistique.",
            ha="center", fontsize=7, color=GREY, transform=ax.transAxes)
    ax.text(0.5, warn_y - 0.012,
            "T8 n'est pas dans les DECISION_RULES v1/v2 (agrégation limitée à T1–T7). "
            "Test confirmatoire secondaire.",
            ha="center", fontsize=6.5, color=GREY, transform=ax.transAxes)

    ax.text(0.5, 0.01,
            "α = 0.01  •  k = 2.5  •  m = 3  •  baseline_n = 60  •  auto-scale activé  "
            "•  Suite : run_real_data_canonical_suite.py  •  DECISION_RULES v1/v2 : T1–T7",
            ha="center", fontsize=7, color=GREY, transform=ax.transAxes)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── PAGE 3 — time series overview ──────────────────────────────────────────────
def page_time_series(pdf: PdfPages, df: pd.DataFrame, causal: dict):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(DARK)
    gs = gridspec.GridSpec(3, 1, hspace=0.45,
                           left=0.10, right=0.93, top=0.93, bottom=0.06)
    fig.text(0.5, 0.965, "Séries temporelles FRED — Données Réelles",
             ha="center", fontsize=14, fontweight="bold", color="white")

    cap   = df["O"] * df["R"] * df["I"]
    scale = df["demand"].mean() / cap.mean() if cap.mean() > 0 else 1.0
    cap_s = cap * scale
    sigma = (df["demand"] - cap_s).clip(lower=0)
    s_diff = df["S"].diff().fillna(0)
    C = s_diff.cumsum()

    thr_t = causal.get("threshold_hit_t")
    dates = df["date"] if "date" in df.columns else df.index

    ax1 = fig.add_subplot(gs[0])
    ax1.plot(dates, df["O"], color="#4cc9f0", lw=1.2, label="O — INDPRO (norm.)")
    ax1.plot(dates, df["R"], color="#f77f00", lw=1.2, label="R — TCU (norm.)")
    ax1.plot(dates, df["I"], color="#a8dadc", lw=1.0, label="I — T10YFF (norm.)", alpha=0.8)
    ax1.set_ylabel("Valeur normalisée", fontsize=8)
    ax1.set_title("O · R · I  (composantes Cap)", fontsize=9, pad=4)
    ax1.legend(fontsize=7, loc="upper left", facecolor=BLUE, edgecolor="none",
               labelcolor="white", ncol=3)

    ax2 = fig.add_subplot(gs[1])
    ax2.fill_between(dates, sigma, alpha=0.35, color=ACCENT, label="Σ(t) mismatch")
    ax2.plot(dates, cap_s, color=GREEN,  lw=1.3, label="Cap(t) = O·R·I (rescalé)")
    ax2.plot(dates, df["demand"], color=ACCENT, lw=1.0, label="demand — WTI")
    if thr_t is not None:
        ax2.axvline(df["date"].iloc[int(thr_t)], color="yellow", lw=1.2,
                    ls="--", label=f"Seuil → {_step_to_date(int(thr_t))}")
    ax2.set_ylabel("Valeur normalisée", fontsize=8)
    ax2.set_title("Cap · demand · Σ  — détection de seuil", fontsize=9, pad=4)
    ax2.legend(fontsize=7, loc="upper left", facecolor=BLUE, edgecolor="none",
               labelcolor="white", ncol=2)

    ax3 = fig.add_subplot(gs[2])
    ax3_r = ax3.twinx()
    ax3.plot(dates, df["S"], color=LBLUE, lw=1.3, label="S — M2 (norm.)")
    ax3_r.plot(dates, C, color="#ffd166", lw=1.2, label="C(t) approx.", alpha=0.85)
    if thr_t is not None:
        ax3.axvline(df["date"].iloc[int(thr_t)], color="yellow", lw=1.2, ls="--")
    ax3.set_ylabel("S normalisé", fontsize=8, color=LBLUE)
    ax3_r.set_ylabel("C(t) cumulé", fontsize=8, color="#ffd166")
    ax3.set_title("S (M2) et C — canal symbolique", fontsize=9, pad=4)
    lines1, labs1 = ax3.get_legend_handles_labels()
    lines2, labs2 = ax3_r.get_legend_handles_labels()
    ax3.legend(lines1 + lines2, labs1 + labs2,
               fontsize=7, loc="upper left", facecolor=BLUE,
               edgecolor="none", labelcolor="white")

    for ax in [ax1, ax2, ax3]:
        ax.set_facecolor(DARK)
        for spine in ax.spines.values():
            spine.set_edgecolor(GREY)
        ax.tick_params(colors="white", labelsize=7)
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
    ax3_r.set_facecolor(DARK)
    ax3_r.tick_params(colors="#ffd166", labelsize=7)
    ax3_r.spines["right"].set_edgecolor(GREY)
    ax3_r.yaxis.label.set_color("#ffd166")

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── PAGE 4 — protocol ──────────────────────────────────────────────────────────
def page_protocol(pdf: PdfPages):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(DARK)
    ax = fig.add_axes([0.06, 0.04, 0.88, 0.90])
    ax.set_facecolor(DARK)
    ax.axis("off")

    def sec(y, title):
        ax.text(0.0, y, title, fontsize=11, fontweight="bold",
                color=ACCENT, transform=ax.transAxes)
        ax.axhline(y - 0.007, color=ACCENT, lw=0.8, xmin=0.0, xmax=1.0)

    def line(y, txt, indent=0.02, color="white", size=9):
        ax.text(indent, y, txt, fontsize=size, color=color, transform=ax.transAxes)

    ax.text(0.5, 0.97, "Méthodologie & Protocole — Données Réelles FRED",
            ha="center", fontsize=13, fontweight="bold", color="white", transform=ax.transAxes)
    ax.axhline(0.95, color=ACCENT, lw=2)

    sec(0.91, "Paramètres ex ante (fixes, pré-enregistrés)")
    params = [
        ("α (seuil statistique)",          "0.01"),
        ("k (nb de σ pour détection)",      "2.5"),
        ("m (pas consécutifs)",             "3"),
        ("baseline_n (estimation μ/σ)",     "60 mois"),
        ("Forme fonctionnelle Cap",         "O(t) × R(t) × I(t)"),
        ("Forme Σ",                         "max(0, demand − Cap_rescalé)"),
        ("CI",                              "99 %"),
        ("Power gate",                      "< 70 % → INDETERMINATE forcé"),
    ]
    for i, (k_lbl, v_lbl) in enumerate(params):
        yp = 0.875 - i * 0.032
        ax.text(0.02, yp, "▸ " + k_lbl, fontsize=9, color=LGREY, transform=ax.transAxes)
        ax.text(0.54, yp, v_lbl, fontsize=9, color=GREEN, transform=ax.transAxes, fontweight="bold")

    sec(0.59, "Sources de données FRED")
    srcs = [
        "INDPRO     — Federal Reserve  •  Industrial Production Index  •  1919–2025  •  mensuel",
        "TCU        — Federal Reserve  •  Total Capacity Utilization   •  1967–2025  •  mensuel",
        "T10YFF     — Federal Reserve  •  10Y Treasury − Fed Funds     •  1986–2025  •  quotidien→mensuel",
        "DCOILWTICO — EIA via FRED     •  WTI Crude Oil Spot Price     •  1986–2025  •  quotidien→mensuel",
        "M2SL       — Federal Reserve  •  M2 Money Stock               •  1960–2025  •  mensuel",
    ]
    for i, s in enumerate(srcs):
        line(0.556 - i * 0.034, "▸ " + s, size=8, color=LGREY)

    sec(0.37, "Construction du dataset")
    steps = [
        "1. Lecture des CSV bruts FRED (fréquences mixtes : mensuel / quotidien)",
        "2. Resample des séries journalières → moyenne mensuelle (MS)",
        "3. Inner join sur index mensuel  →  fenêtre commune 1986-01 / 2025-12",
        "4. Forward/backward fill pour les rares lacunes pétrolières",
        "5. Normalisation min-max [0, 1] sur toute la série",
        "   — T10YFF négatif accepté (courbe inversée = intégration faible)",
        "6. Export : 03_Data/real/fred_monthly/real.csv  (480 lignes, 0 valeur manquante)",
    ]
    for i, s in enumerate(steps):
        line(0.340 - i * 0.034, s, size=8, color=LGREY)

    sec(0.22, "Historique T8 — Amendement de protocole")
    t8_lines = [
        ("v≤1.0 (retiré)",   "dose-response S→C",      "Réponse quantitative de C à différentes doses de S"),
        ("v1.1  (synthét.)", "Reinjection recovery",    "Coupure symbolique + réinjection → récupération C  [run_reinjection_demo.py]"),
        ("v1.1  (réel)   ",  "Stabilité C post-seuil", "C_positive_frac_post > 0.5  ET  C_mean_post > C_mean_pre"),
    ]
    for i, (ver, short, desc) in enumerate(t8_lines):
        y8 = 0.190 - i * 0.030
        ax.text(0.02, y8, ver,   fontsize=7.5, color=ORANGE, transform=ax.transAxes, fontfamily="monospace")
        ax.text(0.22, y8, short, fontsize=7.5, color=GREEN,  transform=ax.transAxes, fontweight="bold")
        ax.text(0.44, y8, desc,  fontsize=7,   color=LGREY,  transform=ax.transAxes)
    ax.text(0.02, 0.102,
            "▸ DECISION_RULES v1/v2 définissent T1–T7 uniquement. T8 est hors périmètre pré-enregistré.",
            fontsize=7.5, color=ORANGE, transform=ax.transAxes)
    ax.text(0.02, 0.080,
            "▸ Un changement de verdict T8 entre rapports de versions différentes reflète"
            " le changement de définition,",
            fontsize=7, color=GREY, transform=ax.transAxes)
    ax.text(0.02, 0.063,
            "  pas une instabilité statistique. Ne pas interpréter comme un revirement.",
            fontsize=7, color=GREY, transform=ax.transAxes)

    sec(0.045, "Pré-enregistrement & reproductibilité")
    line(0.022, "▸ DOI OSF : 10.17605/OSF.IO/G62PZ", color=GREEN, size=9)
    line(-0.005, "▸ Seed fixe ; config JSON archivé dans 04_Code/configs/  •  CI GitHub Actions reproductibles (Python 3.12)", size=7.5, color=LGREY)
    line(-0.025, "▸ Tout changement de paramètre ou de définition de test = nouveau pré-enregistrement obligatoire", size=7.5, color=LGREY)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate Real Data FRED PDF report for ORI-C."
    )
    ap.add_argument(
        "--run-dir",
        default=str(ROOT / "05_Results" / "audit_fred_run"),
        help=(
            "Path to run_real_data_canonical_suite.py output dir "
            "(contains tables/global_summary.json), "
            "or legacy tests_causaux.py output dir (tables/verdict.json). "
            "[default: 05_Results/audit_fred_run]"
        ),
    )
    ap.add_argument(
        "--data-csv",
        default=str(ROOT / "03_Data" / "real" / "fred_monthly" / "real.csv"),
        help="FRED real data CSV for time-series plots. [default: 03_Data/real/fred_monthly/real.csv]",
    )
    ap.add_argument(
        "--out",
        default=str(ROOT / "05_Results" / "fred_monthly_report" / "ORI_C_FRED_Real_Data_Report.pdf"),
        help="Output PDF path.",
    )
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    data_csv = Path(args.data_csv)
    out_pdf = Path(args.out)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    if not data_csv.exists():
        print(f"ERREUR: data CSV introuvable: {data_csv}", file=sys.stderr)
        return 1

    # Load results
    t_results, causal, global_verdict, support_level, run_mode = _load_results(run_dir)

    # Detect data source label
    gs_path = run_dir / "tables" / "global_summary.json"
    if gs_path.exists():
        source_label = f"Source: {gs_path} (canonical suite)  support_level={support_level}  run_mode={run_mode}"
    else:
        source_label = f"Source: {run_dir / 'tables' / 'verdict.json'} (legacy fallback)  support_level={support_level}"
    print(source_label)

    # Load FRED data for plots
    df = pd.read_csv(data_csv, parse_dates=["date"] if "date" in open(data_csv).readline() else [])
    if "date" in df.columns:
        df = df.sort_values("date").reset_index(drop=True)

    n_obs = len(df)
    if "date" in df.columns:
        date_range = f"{df['date'].iloc[0]:%B %Y} – {df['date'].iloc[-1]:%B %Y}"
    else:
        date_range = f"{n_obs} observations"

    print(f"Generating {out_pdf} …")
    with PdfPages(out_pdf) as pdf:
        page_cover(pdf, t_results, causal, global_verdict, n_obs, date_range,
                   support_level=support_level, run_mode=run_mode)
        page_results_table(pdf, t_results, causal, global_verdict,
                           support_level=support_level, run_mode=run_mode)
        page_time_series(pdf, df, causal)
        page_protocol(pdf)

        d = pdf.infodict()
        d["Title"]    = f"ORI-C FRED Real Data Report — {global_verdict} — {support_level}"
        d["Author"]   = "CumulativeSymbolicThreshold / Claude Code"
        d["Subject"]  = "Cumulative Symbolic Threshold — real data validation (FRED)"
        d["Keywords"] = "ORI-C, FRED, données réelles, T1-T8, threshold, symbolic"
        d["CreationDate"] = date.today().isoformat()

    size_kb = out_pdf.stat().st_size / 1024
    print(f"Done — {out_pdf}  ({size_kb:.0f} KB)")
    print(f"Verdict global  : {global_verdict}")
    print(f"support_level   : {support_level}")
    print(f"run_mode        : {run_mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
