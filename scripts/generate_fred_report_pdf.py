"""Generate a summary PDF report for the FRED monthly ORI-C run."""
from __future__ import annotations

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

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parents[1]
DATA    = ROOT / "03_Data/real/fred_monthly/real.csv"
OUTDIR  = ROOT / "05_Results/fred_monthly_report"
OUTDIR.mkdir(parents=True, exist_ok=True)
PDF_OUT = OUTDIR / "ORI_C_FRED_Monthly_Report.pdf"

# ── palette ───────────────────────────────────────────────────────────────────
DARK    = "#1a1a2e"
ACCENT  = "#e94560"
GREEN   = "#16c79a"
BLUE    = "#0f3460"
LBLUE   = "#533483"
GREY    = "#888888"
LGREY   = "#e8e8f0"

T_RESULTS = [
    ("T1", "ORI core (Cap / Sigma / V)",        "ACCEPT",       "Sigma_max = 0.558"),
    ("T2", "Threshold detection",                "ACCEPT",       "Seuil step 263 — nov. 2007 (pré-GFC)"),
    ("T3", "Robustness (normalisation)",         "ACCEPT",       "Robuste minmax ET robust"),
    ("T4", "Granger S → C",                      "ACCEPT",       "p = 5.6 × 10⁻¹⁰"),
    ("T5", "Injection symbolique (shift)",       "ACCEPT",       "Bootstrap CI positif"),
    ("T6", "Cointégration C-S (long run)",       "INDETERMINATE","p = 0.878 (attendu : C est un flux)"),
    ("T7", "VAR S → C",                          "ACCEPT",       "p = 3.7 × 10⁻⁶"),
    ("T8", "Stabilité C post-seuil",             "ACCEPT",       "C_post > C_pre (+21 %)"),
]

VERDICT_COLOR = {"ACCEPT": GREEN, "REJECT": ACCENT, "INDETERMINATE": "#f0a500"}


# ── helpers ───────────────────────────────────────────────────────────────────
def set_dark_bg(fig, ax_list):
    fig.patch.set_facecolor(DARK)
    for ax in ax_list:
        ax.set_facecolor(DARK)
        for spine in ax.spines.values():
            spine.set_edgecolor(GREY)
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")


def verdict_badge(ax, x, y, verdict, fontsize=9):
    col = VERDICT_COLOR[verdict]
    ax.text(x, y, f" {verdict} ", transform=ax.transAxes,
            fontsize=fontsize, fontweight="bold",
            color=DARK, ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=col, edgecolor="none"))


# ── load data ─────────────────────────────────────────────────────────────────
df = pd.read_csv(DATA, parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)
n  = len(df)

# recompute pipeline vars for plots
cap   = df["O"] * df["R"] * df["I"]
scale = df["demand"].mean() / cap.mean() if cap.mean() > 0 else 1.0
cap_s = cap * scale
sigma = (df["demand"] - cap_s).clip(lower=0)

# C(t) approximation: cumsum of delta-S  (illustrative)
s_diff = df["S"].diff().fillna(0)
C = s_diff.cumsum()

baseline_n = 60
mu   = C.iloc[:baseline_n].mean()
sd   = C.iloc[:baseline_n].std()
k    = 2.5
m    = 3
thr  = mu + k * sd

# threshold crossing
consec = 0
thr_t  = None
for i in range(baseline_n, n):
    if C.iloc[i] > thr:
        consec += 1
        if consec >= m:
            thr_t = i - m + 1
            break
    else:
        consec = 0

# ── PAGE 1 — cover ────────────────────────────────────────────────────────────
def page_cover(pdf: PdfPages):
    fig = plt.figure(figsize=(8.27, 11.69))  # A4
    fig.patch.set_facecolor(DARK)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(DARK)
    ax.axis("off")

    # top bar
    ax.axhline(0.88, color=ACCENT, lw=4, xmin=0.06, xmax=0.94)

    # title block
    ax.text(0.5, 0.80, "ORI-C HYPOTHESIS", ha="center", va="center",
            fontsize=28, fontweight="bold", color="white", transform=ax.transAxes)
    ax.text(0.5, 0.74, "FRED Monthly Real-Data Run", ha="center", va="center",
            fontsize=18, color=ACCENT, transform=ax.transAxes)
    ax.text(0.5, 0.69, "January 1986 – December 2025  •  480 observations",
            ha="center", va="center", fontsize=11, color=GREY, transform=ax.transAxes)

    # big verdict
    ax.text(0.5, 0.57, "GLOBAL VERDICT", ha="center", va="center",
            fontsize=13, color=GREY, transform=ax.transAxes)
    bbox = FancyBboxPatch((0.25, 0.48), 0.50, 0.085,
                          boxstyle="round,pad=0.01", facecolor=GREEN,
                          edgecolor="none", transform=ax.transAxes)
    ax.add_patch(bbox)
    ax.text(0.5, 0.522, "ACCEPT", ha="center", va="center",
            fontsize=28, fontweight="bold", color=DARK, transform=ax.transAxes)

    ax.text(0.5, 0.44, "7 / 8 tests ACCEPT  —  T6 INDETERMINATE (attendu)",
            ha="center", va="center", fontsize=10, color=GREY, transform=ax.transAxes)

    # variable mapping
    ax.text(0.5, 0.38, "Variables FRED", ha="center", va="center",
            fontsize=11, fontweight="bold", color="white", transform=ax.transAxes)
    mapping = [
        ("O",       "INDPRO",      "Production industrielle (mensuel)"),
        ("R",       "TCU",         "Taux d'utilisation des capacités (mensuel)"),
        ("I",       "T10YFF",      "Spread 10Y − Fed Funds (quotidien → mensuel)"),
        ("demand",  "DCOILWTICO",  "Prix WTI brut (quotidien → mensuel)"),
        ("S",       "M2SL",        "Masse monétaire M2 (mensuel)"),
    ]
    for i, (sym, code, desc) in enumerate(mapping):
        y = 0.345 - i * 0.038
        ax.text(0.18, y, sym,    fontsize=10, fontweight="bold", color=ACCENT, transform=ax.transAxes, ha="right")
        ax.text(0.20, y, "=",    fontsize=10, color=GREY, transform=ax.transAxes)
        ax.text(0.22, y, code,   fontsize=10, color=GREEN, transform=ax.transAxes, fontweight="bold")
        ax.text(0.36, y, f"({desc})", fontsize=9, color=LGREY, transform=ax.transAxes)

    # footer
    ax.axhline(0.08, color=ACCENT, lw=1.5, xmin=0.06, xmax=0.94)
    ax.text(0.5, 0.055, f"Généré le {date.today():%d %B %Y}  •  DOI : 10.17605/OSF.IO/G62PZ",
            ha="center", va="center", fontsize=8, color=GREY, transform=ax.transAxes)
    ax.text(0.5, 0.035, "CumulativeSymbolicThreshold  •  MIT License",
            ha="center", va="center", fontsize=7, color=GREY, transform=ax.transAxes)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── PAGE 2 — T1-T8 table ──────────────────────────────────────────────────────
def page_results_table(pdf: PdfPages):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(DARK)
    ax = fig.add_axes([0.05, 0.05, 0.90, 0.88])
    ax.set_facecolor(DARK)
    ax.axis("off")

    ax.text(0.5, 0.97, "Résultats T1–T8", ha="center", va="center",
            fontsize=16, fontweight="bold", color="white", transform=ax.transAxes)
    ax.axhline(0.94, color=ACCENT, lw=2)

    row_h   = 0.09
    y_start = 0.88
    col_x   = [0.01, 0.07, 0.40, 0.72]  # id, test, verdict, detail

    # header
    for x, lbl in zip(col_x, ["#", "Test", "Verdict", "Détail"]):
        ax.text(x, y_start + 0.01, lbl, fontsize=9, fontweight="bold",
                color=GREY, transform=ax.transAxes)

    for i, (tid, tname, verdict, detail) in enumerate(T_RESULTS):
        y = y_start - (i + 1) * row_h
        # row bg
        bg_col = "#1e1e38" if i % 2 == 0 else DARK
        rect = FancyBboxPatch((0.0, y - 0.015), 1.0, row_h - 0.005,
                              boxstyle="round,pad=0.005",
                              facecolor=bg_col, edgecolor="none",
                              transform=ax.transAxes)
        ax.add_patch(rect)

        ax.text(col_x[0], y + 0.025, tid,     fontsize=10, fontweight="bold",
                color=ACCENT, transform=ax.transAxes, va="center")
        ax.text(col_x[1], y + 0.025, tname,   fontsize=9,
                color="white", transform=ax.transAxes, va="center")
        # verdict badge
        vc = VERDICT_COLOR[verdict]
        bx = FancyBboxPatch((col_x[2] - 0.005, y + 0.005), 0.29, 0.055,
                            boxstyle="round,pad=0.005",
                            facecolor=vc, edgecolor="none",
                            transform=ax.transAxes)
        ax.add_patch(bx)
        ax.text(col_x[2] + 0.14, y + 0.030, verdict, fontsize=8.5,
                fontweight="bold", color=DARK, ha="center",
                transform=ax.transAxes, va="center")
        ax.text(col_x[3], y + 0.025, detail,  fontsize=8,
                color=LGREY, transform=ax.transAxes, va="center")

    # summary block
    y_sum = y_start - (len(T_RESULTS) + 1.5) * row_h
    rect2 = FancyBboxPatch((0.0, y_sum - 0.04), 1.0, 0.12,
                           boxstyle="round,pad=0.01",
                           facecolor=GREEN + "22", edgecolor=GREEN,
                           transform=ax.transAxes)
    ax.add_patch(rect2)
    ax.text(0.5, y_sum + 0.04, "Interprétation", ha="center",
            fontsize=10, fontweight="bold", color=GREEN, transform=ax.transAxes)
    lines = [
        "Noyau ORI validé (T1+T2+T3)  •  Canal symbolique S→C validé (T4+T5+T7)",
        "T6 INDETERMINATE : C est un flux, pas un stock — pas de cointégration attendue",
        "T8 ACCEPT : régime cumulatif stable après le seuil de nov. 2007",
    ]
    for j, line in enumerate(lines):
        ax.text(0.5, y_sum + 0.005 - j * 0.028, line, ha="center",
                fontsize=8, color=LGREY, transform=ax.transAxes)

    ax.text(0.5, 0.01, "α = 0.01  •  k = 2.5  •  m = 3  •  baseline_n = 60  •  auto-scale activé",
            ha="center", fontsize=7.5, color=GREY, transform=ax.transAxes)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── PAGE 3 — time series overview ─────────────────────────────────────────────
def page_time_series(pdf: PdfPages):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(DARK)
    gs = gridspec.GridSpec(3, 1, hspace=0.45,
                           left=0.10, right=0.93, top=0.93, bottom=0.06)

    fig.text(0.5, 0.965, "Séries temporelles FRED (1986–2025)",
             ha="center", fontsize=14, fontweight="bold", color="white")

    dates = df["date"]

    # --- ax1: O, R, I ---
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(dates, df["O"], color="#4cc9f0", lw=1.2, label="O — INDPRO (norm.)")
    ax1.plot(dates, df["R"], color="#f77f00", lw=1.2, label="R — TCU (norm.)")
    ax1.plot(dates, df["I"], color="#a8dadc", lw=1.0, label="I — T10YFF (norm.)", alpha=0.8)
    ax1.set_ylabel("Valeur normalisée", fontsize=8)
    ax1.set_title("O · R · I  (composantes Cap)", fontsize=9, pad=4)
    ax1.legend(fontsize=7, loc="upper left", facecolor=BLUE, edgecolor="none",
               labelcolor="white", ncol=3)

    # --- ax2: Cap, demand, Sigma ---
    ax2 = fig.add_subplot(gs[1])
    ax2.fill_between(dates, sigma, alpha=0.35, color=ACCENT, label="Σ(t) mismatch")
    ax2.plot(dates, cap_s, color=GREEN,  lw=1.3, label="Cap(t) = O·R·I (rescalé)")
    ax2.plot(dates, df["demand"], color=ACCENT, lw=1.0, label="demand — WTI")
    if thr_t is not None:
        ax2.axvline(df["date"].iloc[thr_t], color="yellow", lw=1.2,
                    ls="--", label=f"Seuil T2 → {df['date'].iloc[thr_t]:%b %Y}")
    ax2.set_ylabel("Valeur normalisée", fontsize=8)
    ax2.set_title("Cap · demand · Σ  — détection de seuil", fontsize=9, pad=4)
    ax2.legend(fontsize=7, loc="upper left", facecolor=BLUE, edgecolor="none",
               labelcolor="white", ncol=2)

    # --- ax3: S and C ---
    ax3 = fig.add_subplot(gs[2])
    ax3_r = ax3.twinx()
    ax3.plot(dates, df["S"], color=LBLUE, lw=1.3, label="S — M2 (norm.)")
    ax3_r.plot(dates, C, color="#ffd166", lw=1.2, label="C(t) approx.", alpha=0.85)
    if thr_t is not None:
        ax3.axvline(df["date"].iloc[thr_t], color="yellow", lw=1.2, ls="--")
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


# ── PAGE 4 — protocol & methodology ───────────────────────────────────────────
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

    ax.text(0.5, 0.97, "Méthodologie & Protocole", ha="center",
            fontsize=14, fontweight="bold", color="white", transform=ax.transAxes)
    ax.axhline(0.95, color=ACCENT, lw=2)

    sec(0.91, "Paramètres ex ante (fixes, pré-enregistrés)")
    params = [
        ("α (seuil statistique)",         "0.01"),
        ("k (nb de σ pour détection)",     "2.5"),
        ("m (pas consécutifs)",            "3"),
        ("baseline_n (estimation μ/σ)",    "60 mois"),
        ("Forme fonctionnelle Cap",        "O(t) × R(t) × I(t)"),
        ("Forme Σ",                        "max(0, demand − Cap_rescalé)"),
        ("CI",                             "99 %"),
        ("Power gate",                     "< 70 % → INDETERMINATE forcé"),
    ]
    for i, (k_lbl, v_lbl) in enumerate(params):
        yp = 0.875 - i * 0.032
        ax.text(0.02, yp, "▸ " + k_lbl, fontsize=9, color=LGREY, transform=ax.transAxes)
        ax.text(0.54, yp, v_lbl, fontsize=9, color=GREEN, transform=ax.transAxes, fontweight="bold")

    sec(0.59, "Sources de données FRED")
    srcs = [
        "INDPRO   — Federal Reserve  •  Industrial Production Index  •  1919–2025  •  mensuel",
        "TCU      — Federal Reserve  •  Total Capacity Utilization   •  1967–2025  •  mensuel",
        "T10YFF   — Federal Reserve  •  10Y Treasury − Fed Funds      •  1986–2025  •  quotidien→mensuel",
        "DCOILWTICO — EIA via FRED   •  WTI Crude Oil Spot Price      •  1986–2025  •  quotidien→mensuel",
        "M2SL     — Federal Reserve  •  M2 Money Stock                •  1960–2025  •  mensuel",
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

    sec(0.12, "Pré-enregistrement & reproductibilité")
    line(0.092, "▸ DOI OSF : 10.17605/OSF.IO/G62PZ", color=GREEN, size=9)
    line(0.065, "▸ Seed fixe pour chaque run ; config JSON archivé dans 04_Code/configs/", size=8, color=LGREY)
    line(0.040, "▸ Résultats CI GitHub Actions reproductibles (Python 3.12, requirements.txt)", size=8, color=LGREY)
    line(0.015, "▸ Tout changement de paramètre = nouveau pré-enregistrement obligatoire", size=8, color=LGREY)

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── ASSEMBLE PDF ──────────────────────────────────────────────────────────────
print(f"Generating {PDF_OUT} …")
with PdfPages(PDF_OUT) as pdf:
    page_cover(pdf)
    page_results_table(pdf)
    page_time_series(pdf)
    page_protocol(pdf)

    # metadata
    d = pdf.infodict()
    d["Title"]   = "ORI-C FRED Monthly Report — ACCEPT"
    d["Author"]  = "CumulativeSymbolicThreshold / Claude Code"
    d["Subject"] = "Cumulative Symbolic Threshold — real data validation"
    d["Keywords"] = "ORI-C, FRED, T1-T8, threshold, symbolic, Cap"
    d["CreationDate"] = date.today().isoformat()

print(f"Done — {PDF_OUT}")
print(f"Size: {PDF_OUT.stat().st_size / 1024:.0f} KB")
