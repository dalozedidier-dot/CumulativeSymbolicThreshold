"""
Fig 1 — Pipeline ORI-C
Architecture : O, R, I → Cap → Σ → C → verdict
Output : fig1_pipeline_oric.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

# ── Style ──────────────────────────────────────────────────────────────
BG       = "#0d0f12"
SURFACE  = "#171a1f"
BORDER   = "#2a2e36"
TEXT     = "#d4d0c8"
MUTED    = "#5a5850"
GREEN    = "#3d7a5c"
AMBER    = "#8b6b3a"
BLUE     = "#3a5878"
TENSION  = "#6b3a5a"

fig = plt.figure(figsize=(12, 5.5), facecolor=BG)
ax  = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 12)
ax.set_ylim(0, 5.5)
ax.set_facecolor(BG)
ax.axis("off")

# ── Helper: rounded rectangle ──────────────────────────────────────────
def box(cx, cy, w, h, color, label, sublabel=None, textcolor=TEXT):
    rect = mpatches.FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.08",
        facecolor=SURFACE, edgecolor=color, linewidth=1.2,
        zorder=3
    )
    ax.add_patch(rect)
    ax.text(cx, cy + (0.12 if sublabel else 0), label,
            ha="center", va="center", fontsize=9.5, color=textcolor,
            fontfamily="monospace", fontweight="medium", zorder=4)
    if sublabel:
        ax.text(cx, cy - 0.28, sublabel,
                ha="center", va="center", fontsize=7, color=MUTED,
                fontfamily="monospace", zorder=4)

# ── Helper: arrow ─────────────────────────────────────────────────────
def arrow(x1, y1, x2, y2, color=MUTED):
    ax.annotate("",
        xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color=color,
                        lw=1.2, mutation_scale=12),
        zorder=2)

# ── Inputs (O, R, I) — column 1 ───────────────────────────────────────
box(1.4, 3.8, 1.5, 0.7, GREEN, "O(t)", "Organisation")
box(1.4, 2.75, 1.5, 0.7, GREEN, "R(t)", "Résilience")
box(1.4, 1.7, 1.5, 0.7, GREEN, "I(t)", "Intégration")

# Bracket label
ax.text(0.45, 2.75, "Observables\n/ Proxies", ha="center", va="center",
        fontsize=7, color=MUTED, fontfamily="monospace", rotation=90)

# ── Cap ────────────────────────────────────────────────────────────────
box(3.6, 2.75, 1.5, 0.7, GREEN, "Cap(t)", "0.4·O+0.35·R+0.25·I")

# Arrows O,R,I → Cap
arrow(2.17, 3.8, 2.82, 3.0, GREEN)
arrow(2.17, 2.75, 2.82, 2.75, GREEN)
arrow(2.17, 1.7, 2.82, 2.5, GREEN)

# ── D (demand) ────────────────────────────────────────────────────────
box(3.6, 1.0, 1.5, 0.7, AMBER, "D(t)", "Demande")

# ── Sigma ──────────────────────────────────────────────────────────────
box(5.7, 2.0, 1.6, 0.7, AMBER, "Σ(t)", "max(0, D−Cap)")

# Cap → Sigma, D → Sigma
arrow(4.38, 2.6, 4.88, 2.25, AMBER)
arrow(4.38, 1.1, 4.88, 1.75, AMBER)

# ── S (stock symbolique) ───────────────────────────────────────────────
box(5.7, 3.7, 1.5, 0.7, BLUE, "S(t)", "Stock symbolique")

# ── C (variable d'ordre) ───────────────────────────────────────────────
box(8.0, 2.75, 1.7, 0.7, BLUE, "C(t)", "Variable d'ordre")

# S → C, Sigma → C
arrow(6.52, 3.7, 7.12, 3.05, BLUE)
arrow(6.52, 2.05, 7.12, 2.5, BLUE)

# Equation label on C arrow
ax.text(7.1, 3.65, "C(t+1) = (1−d)·C(t) + b·g(S,Σ)",
        ha="center", va="center", fontsize=6.8, color=MUTED,
        fontfamily="monospace", style="italic")

# ── V (viabilité) ──────────────────────────────────────────────────────
box(8.0, 1.3, 1.5, 0.7, TENSION, "V(t)", "Viabilité")
ax.text(7.1, 1.75, "T1, T6 only", ha="center", va="center",
        fontsize=6.5, color=MUTED, fontfamily="monospace")
arrow(6.52, 2.0, 7.12, 1.55, TENSION)

# ── Verdict ────────────────────────────────────────────────────────────
box(10.6, 2.75, 1.55, 0.7, GREEN, "ACCEPT", "T1–T8 ≥ threshold")
box(10.6, 1.6, 1.55, 0.7, AMBER, "INDET.", "power < 0.70 …")
box(10.6, 3.9, 1.55, 0.7, TENSION, "REJECT", "H_i falsified")

# C → verdicts
arrow(8.88, 2.75, 9.82, 2.75, TEXT)
arrow(8.88, 2.75, 9.82, 1.75, MUTED)
arrow(8.88, 2.75, 9.82, 3.82, MUTED)

# ── Aggregation rule box ───────────────────────────────────────────────
agg = mpatches.FancyBboxPatch((9.78, 1.1), 1.65, 3.25,
    boxstyle="round,pad=0.1",
    facecolor="none", edgecolor=BORDER, linewidth=0.8, linestyle="--",
    zorder=1)
ax.add_patch(agg)
ax.text(10.61, 0.82, "Règle d'agrégation déclarée ex ante",
        ha="center", va="center", fontsize=6.5, color=MUTED, fontfamily="monospace")

# ── Title & caption ───────────────────────────────────────────────────
ax.text(6, 5.1,
        "Fig. 1 — Architecture pipeline ORI-C",
        ha="center", va="center", fontsize=11, color=TEXT,
        fontfamily="monospace", fontweight="medium")
ax.text(6, 4.7,
        "O, R, I → Cap(t) → Σ(t) + S(t) → C(t) → verdict par test T1–T8",
        ha="center", va="center", fontsize=7.5, color=MUTED, fontfamily="monospace")

plt.savefig("fig1_pipeline_oric.png", dpi=150, bbox_inches="tight",
            facecolor=BG, edgecolor="none")
print("Saved: fig1_pipeline_oric.png")
