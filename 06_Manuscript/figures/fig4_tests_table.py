"""
Fig 4 — Tableau T1–T8 : une ligne par test, verdict, métrique principale, lien artefacts
Output : fig4_tests_table.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Style ─────────────────────────────────────────────────────────────
BG    = "#0d0f12"
SURF  = "#171a1f"
TEXT  = "#d4d0c8"
MUTED = "#5a5850"
BORDER = "#2a2e36"
GREEN  = "#3d7a5c"
AMBER  = "#8b6b3a"
BLUE   = "#3a5878"
RED    = "#7a3040"
INDET  = "#8b6b3a"

# ── Table data ────────────────────────────────────────────────────────
COLS = ["Test", "Hypothèse nulle locale", "Script", "Seed", "N", "Verdict", "Métrique principale"]

ROWS = [
    ("T1\nnoyau demand shock",
     "ΔV(post) ≤ ΔV(pré) après injection demande",
     "run_ori_c_demo.py",
     "1234", "60",
     "ACCEPT*",
     "ΔV post > pré  (p < 0.01, CI99%)"),

    ("T2\nthreshold demo",
     "Aucun seuil ΔC détecté sur données calibrées",
     "run_synthetic_demo.py",
     "1235", "1",
     "ACCEPT*",
     "Seuil ΔC détecté, cas B (n_consec=175)"),

    ("T3\nrobustness OOS",
     "Corrélation OOS ≤ 0 sur panel multi-pays",
     "run_robustness.py",
     "1236", "1",
     "INDET.†",
     "corr OOS = 0.503, frac seuil < 25%"),

    ("T4\nS-rich vs S-poor",
     "C(S_riche) ≤ C(S_pauvre)",
     "run_symbolic_T4_s_rich_poor.py",
     "1237", "60",
     "ACCEPT*",
     "C_riche > C_pauvre (Welch, p < 0.01)"),

    ("T5\nsymbolic injection",
     "Pas d'effet différé sur C à horizon T",
     "run_symbolic_T5_injection.py",
     "1238", "60",
     "ACCEPT*",
     "ΔC différé > baseline (p < 0.01)"),

    ("T6\nsymbolic cut",
     "C ne descend pas après suppression de S",
     "run_ori_c_demo.py",
     "1239", "60",
     "ACCEPT*",
     "C_post_cut < C_pre_cut (p < 0.01)"),

    ("T7\nprogressive sweep",
     "Pas de point de bascule S* détectable",
     "run_symbolic_T7_progressive_sweep.py",
     "1240", "50",
     "ACCEPT*",
     "S* = 0.45 ± 0.03, seuil détecté (cas B)"),

    ("T8\nreinjection recovery",
     "Pente de récupération ≤ 0 après réinjection",
     "run_reinjection_demo.py",
     "1241", "60",
     "ACCEPT*",
     "slope_recovery > 0 (p < 0.01)"),
]

VERDICT_COLORS = {
    "ACCEPT*": GREEN,
    "INDET.†": AMBER,
    "REJECT":  RED,
    "—":       MUTED,
}

# ── Figure ────────────────────────────────────────────────────────────
n_rows  = len(ROWS)
row_h   = 0.75
head_h  = 0.65
top_pad = 0.5
bot_pad = 0.8
fig_h   = n_rows * row_h + head_h + top_pad + bot_pad
fig_w   = 15

fig = plt.figure(figsize=(fig_w, fig_h), facecolor=BG)
ax  = fig.add_axes([0, 0, 1, 1])
ax.set_facecolor(BG)
ax.axis("off")

total_h = n_rows * row_h + head_h
y0      = bot_pad / fig_h  # normalized
y_top   = 1 - top_pad / fig_h

# Column x positions (normalized)
col_x = [0.03, 0.12, 0.38, 0.57, 0.65, 0.71, 0.79]
col_w = [0.09, 0.26, 0.19, 0.08, 0.06, 0.08, 0.21]

def cell(ax, x, y, w, h, text, fontsize=7.5, color=TEXT, ha="left",
         bg=None, bold=False, wrap=False):
    if bg:
        rect = mpatches.FancyBboxPatch(
            (x + 0.003, y + 0.01), w - 0.006, h - 0.02,
            boxstyle="round,pad=0.005",
            facecolor=bg, edgecolor="none", zorder=2,
            transform=ax.transAxes)
        ax.add_patch(rect)
    ax.text(x + 0.008, y + h / 2, text,
            ha=ha, va="center", fontsize=fontsize,
            color=color, fontfamily="monospace",
            fontweight="bold" if bold else "normal",
            transform=ax.transAxes, zorder=3,
            clip_on=True,
            wrap=True if wrap else False)

def hline(ax, y, color=BORDER, lw=0.5):
    ax.axhline(y, xmin=0.01, xmax=0.99,
               color=color, lw=lw, transform=ax.transAxes, zorder=1)

# ── Header ────────────────────────────────────────────────────────────
header_y = y_top - head_h / fig_h
head_labels = ["Test", "Hypothèse nulle locale", "Script",
               "Seed", "N", "Verdict", "Métrique principale"]
for xi, label in zip(col_x, head_labels):
    cell(ax, xi, header_y, 0.15, head_h / fig_h,
         label, fontsize=7, color=MUTED, bold=True)
hline(ax, header_y, color=MUTED, lw=0.8)
hline(ax, y_top, color=BORDER, lw=0.3)

# ── Rows ───────────────────────────────────────────────────────────────
for i, row in enumerate(ROWS):
    row_y = header_y - (i + 1) * row_h / fig_h
    rh    = row_h / fig_h
    bg_row = "#14161b" if i % 2 == 0 else "#111418"

    rect = mpatches.Rectangle((0.01, row_y), 0.98, rh,
                               facecolor=bg_row, edgecolor="none",
                               transform=ax.transAxes, zorder=1)
    ax.add_patch(rect)

    test_id, hyp, script, seed, n_runs, verdict, metric = row
    vcol = VERDICT_COLORS.get(verdict, TEXT)

    cell(ax, col_x[0], row_y, col_w[0], rh, test_id,
         fontsize=7, color=TEXT, bold=True)
    cell(ax, col_x[1], row_y, col_w[1], rh, hyp, fontsize=6.8, color=MUTED)
    cell(ax, col_x[2], row_y, col_w[2], rh, script, fontsize=6.5, color=BLUE)
    cell(ax, col_x[3], row_y, col_w[3], rh, seed, fontsize=7, color=MUTED, ha="center")
    cell(ax, col_x[4], row_y, col_w[4], rh, n_runs, fontsize=7, color=MUTED, ha="center")
    # Verdict badge
    cell(ax, col_x[5], row_y, col_w[5], rh, verdict,
         fontsize=7, color=vcol, bold=True, ha="center",
         bg=vcol + "22" if verdict != "—" else None)
    cell(ax, col_x[6], row_y, col_w[6], rh, metric, fontsize=6.8, color=TEXT)

    hline(ax, row_y, color=BORDER, lw=0.4)

# ── Footer notes ──────────────────────────────────────────────────────
note_y = y0 + 0.01
notes = (
    "* Verdict indicatif — à confirmer sur proof run complet (N ≥ 50, mode full_statistical). "
    "† INDETERMINATE : corr OOS > 0 mais frac seuil insuffisante (< 25 % sur ≥ 3 géos). "
    "Artefacts dans _runs/<test_id>/verdict.json. "
    "α = 0.01 · CI = 99 % · k = 2.5 · m = 3 · w = 20."
)
ax.text(0.02, note_y, notes, ha="left", va="bottom",
        fontsize=6.2, color=MUTED, fontfamily="monospace",
        transform=ax.transAxes, zorder=3)

# ── Title ─────────────────────────────────────────────────────────────
ax.text(0.5, y_top + 0.03, "Fig. 4 — Protocole T1–T8 : verdicts, métriques et artefacts",
        ha="center", va="center", fontsize=11, color=TEXT,
        fontfamily="monospace", fontweight="medium",
        transform=ax.transAxes, zorder=3)

plt.savefig("fig4_tests_table.png", dpi=150, bbox_inches="tight",
            facecolor=BG, edgecolor="none")
print("Saved: fig4_tests_table.png")
