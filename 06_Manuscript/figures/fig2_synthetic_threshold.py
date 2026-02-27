"""
Fig 2 — Exemple synthétique : Σ(t) et C(t) avec seuil de détection
Cas A (pas d'injection) vs Cas B (injection symbolique à t₀=75)
Output : fig2_synthetic_threshold.png
"""
import matplotlib
matplotlib.use("Agg")
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

SEED = 1235
rng  = np.random.default_rng(SEED)

# ── Style ─────────────────────────────────────────────────────────────
BG     = "#0d0f12"
SURF   = "#171a1f"
TEXT   = "#d4d0c8"
MUTED  = "#5a5850"
GREEN  = "#4a9a6a"
AMBER  = "#c08a40"
BLUE   = "#4a78a8"
RED    = "#a04050"

# ── Parameters (ex ante, immuables) ───────────────────────────────────
N        = 250
T0       = 75      # injection à t₀
d        = 0.02    # taux de déplétion
b        = 0.15    # gain symbolique
k        = 2.5     # seuil
m        = 3       # pas consécutifs
w        = 20      # fenêtre baseline

# ── Synthetic ORI ─────────────────────────────────────────────────────
t   = np.arange(N)
Cap = 0.55 + 0.05 * np.sin(2 * np.pi * t / 80) + rng.normal(0, 0.02, N)
D   = 0.65 + 0.08 * np.sin(2 * np.pi * t / 60 + 1) + rng.normal(0, 0.02, N)
Sig = np.maximum(0, D - Cap)

def simulate_C(S_series):
    C = np.zeros(N)
    for i in range(1, N):
        g = S_series[i] * Sig[i]
        C[i] = (1 - d) * C[i-1] + b * g
    return C

# Cas A — pas d'injection
S_A = rng.normal(0.05, 0.01, N).clip(0, 1)
C_A = simulate_C(S_A)

# Cas B — injection symbolique à T0
S_B = S_A.copy()
S_B[T0:] = rng.normal(0.55, 0.05, N - T0).clip(0, 1)
C_B = simulate_C(S_B)

# Threshold detection on Cas B
dC_B   = np.diff(C_B, prepend=C_B[0])
mu     = dC_B[:w].mean()
sigma  = dC_B[:w].std()
thresh = mu + k * sigma

# Consecutive flag
exceeded = dC_B > thresh
detected_start = None
consec = 0
for i in range(N):
    if exceeded[i]:
        consec += 1
        if consec >= m and detected_start is None:
            detected_start = i - m + 1
    else:
        consec = 0

# ── Plot ──────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(12, 7),
                         facecolor=BG,
                         gridspec_kw={"hspace": 0.45, "wspace": 0.32})
fig.patch.set_facecolor(BG)

style = dict(facecolor=SURF, edgecolor=MUTED, linewidth=0.5)

def style_ax(ax, title, xlabel="t", ylabel=""):
    ax.set_facecolor(SURF)
    for spine in ax.spines.values():
        spine.set_color(MUTED)
        spine.set_linewidth(0.6)
    ax.tick_params(colors=MUTED, labelsize=7)
    ax.set_title(title, color=TEXT, fontfamily="monospace",
                 fontsize=8.5, pad=6)
    ax.set_xlabel(xlabel, color=MUTED, fontfamily="monospace", fontsize=7)
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED, fontfamily="monospace", fontsize=7)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)

# ── (0,0) Σ(t) both cases ─────────────────────────────────────────────
ax = axes[0, 0]
ax.fill_between(t, Sig, color=AMBER, alpha=0.25, lw=0)
ax.plot(t, Sig, color=AMBER, lw=1.0)
ax.axhline(0, color=MUTED, lw=0.5, ls="--")
style_ax(ax, "Σ(t) — mismatch structural", ylabel="Σ(t)")
ax.text(N * 0.6, Sig.max() * 0.85,
        "D(t) − Cap(t)", color=MUTED, fontfamily="monospace", fontsize=7)

# ── (0,1) S(t) cas A vs B ─────────────────────────────────────────────
ax = axes[0, 1]
ax.plot(t, S_A, color=MUTED, lw=0.9, label="Cas A — S faible")
ax.plot(t, S_B, color=BLUE, lw=1.0, label="Cas B — injection t₀=75")
ax.axvline(T0, color=BLUE, lw=0.8, ls=":", alpha=0.7)
ax.text(T0 + 3, S_B.max() * 0.9, "t₀ = 75",
        color=BLUE, fontfamily="monospace", fontsize=7)
style_ax(ax, "S(t) — stock symbolique", ylabel="S(t)")
ax.legend(fontsize=7, facecolor=SURF, edgecolor=MUTED, labelcolor=TEXT,
          loc="upper left", framealpha=0.8)

# ── (1,0) C(t) cas A vs B + seuil ─────────────────────────────────────
ax = axes[1, 0]
ax.plot(t, C_A, color=MUTED, lw=0.9, label="Cas A")
ax.plot(t, C_B, color=GREEN, lw=1.2, label="Cas B")
if detected_start is not None:
    ax.axvline(detected_start, color=GREEN, lw=0.9, ls="--", alpha=0.8)
    ax.text(detected_start + 3, C_B.max() * 0.7,
            f"seuil franchi\nt={detected_start}",
            color=GREEN, fontfamily="monospace", fontsize=6.5)
style_ax(ax, "C(t) — variable d'ordre", ylabel="C(t)")
ax.legend(fontsize=7, facecolor=SURF, edgecolor=MUTED, labelcolor=TEXT,
          loc="upper left", framealpha=0.8)

# ── (1,1) ΔC(t) + seuil détection ────────────────────────────────────
ax = axes[1, 1]
ax.fill_between(t, dC_B, where=(dC_B > thresh),
                color=GREEN, alpha=0.3, lw=0, label=f"ΔC > μ+{k}σ")
ax.plot(t, dC_B, color=GREEN, lw=0.8)
ax.axhline(thresh, color=AMBER, lw=0.9, ls="--",
           label=f"seuil μ+{k}σ = {thresh:.3f}")
ax.axhline(mu, color=MUTED, lw=0.6, ls=":", label=f"μ = {mu:.3f}")
style_ax(ax, "ΔC(t) — détection de seuil (Cas B)", ylabel="ΔC(t)")
ax.legend(fontsize=6.5, facecolor=SURF, edgecolor=MUTED, labelcolor=TEXT,
          framealpha=0.8)

# ── Verdict boxes ─────────────────────────────────────────────────────
for ax_loc, verdict, color, case in [
    (axes[1, 0], "CAS A — INDETERMINATE", AMBER, "Cas A"),
    (axes[1, 0], "CAS B — ACCEPT",        GREEN,  "Cas B"),
]:
    pass  # handled in title

axes[1, 0].set_title(
    "C(t)  ·  Cas A : INDETERMINATE   ·   Cas B : ACCEPT",
    color=TEXT, fontfamily="monospace", fontsize=8.5, pad=6)

# ── Main title ────────────────────────────────────────────────────────
fig.suptitle(
    "Fig. 2 — Exemple synthétique : Σ(t) · S(t) · C(t) · détection de seuil",
    color=TEXT, fontfamily="monospace", fontsize=10, y=0.98)

# ── Params annotation ─────────────────────────────────────────────────
param_str = f"seed={SEED}  |  k={k}  m={m}  w={w}  d={d}  b={b}  N={N}"
fig.text(0.5, 0.01, param_str, ha="center", va="bottom",
         fontsize=6.5, color=MUTED, fontfamily="monospace")

plt.savefig("fig2_synthetic_threshold.png", dpi=150, bbox_inches="tight",
            facecolor=BG, edgecolor="none")
print("Saved: fig2_synthetic_threshold.png")
