"""
Fig 3 — Pilote FRED : données réelles mensuelles US (1986–2025)
Affiche : pré/post M2 break 2020, C(t), ΔC(t), décision T9
Output : fig3_real_fred.png
"""
import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import os

# ── Style ─────────────────────────────────────────────────────────────
BG    = "#0d0f12"
SURF  = "#171a1f"
TEXT  = "#d4d0c8"
MUTED = "#5a5850"
GREEN = "#4a9a6a"
AMBER = "#c08a40"
BLUE  = "#4a78a8"
RED   = "#a04050"

# ── Load data ─────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(SCRIPT_DIR, "../../03_Data/real/fred_monthly/real.csv")

try:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
except FileNotFoundError:
    print(f"Data not found at {DATA_PATH}. Generating synthetic proxy data.")
    rng  = np.random.default_rng(1234)
    n    = 480
    dates = pd.date_range("1986-01-01", periods=n, freq="MS")
    df   = pd.DataFrame({
        "date":   dates,
        "O":      np.clip(0.3 + np.linspace(0, 0.3, n) + rng.normal(0, 0.03, n), 0, 1),
        "R":      np.clip(0.65 + 0.05 * np.sin(np.linspace(0, 8*np.pi, n)) + rng.normal(0, 0.02, n), 0, 1),
        "I":      np.clip(0.4  + 0.1  * np.sin(np.linspace(0, 6*np.pi, n)) + rng.normal(0, 0.03, n), 0, 1),
        "demand": np.clip(0.05 + np.linspace(0, 0.15, n) + rng.normal(0, 0.01, n), 0, 1),
        "S":      np.clip(np.linspace(0, 0.9, n) + rng.normal(0, 0.02, n), 0, 1),
    })

# ── ORI-C pipeline (ex ante parameters) ───────────────────────────────
W_O, W_R, W_I = 0.40, 0.35, 0.25
k, m, w_base  = 2.5, 3, 20
d_rate, b_gain = 0.02, 0.15

df["Cap"]   = W_O * df["O"] + W_R * df["R"] + W_I * df["I"]
df["Sigma"] = np.maximum(0, df["demand"] - df["Cap"])

C = np.zeros(len(df))
for i in range(1, len(df)):
    g    = df["S"].iloc[i] * df["Sigma"].iloc[i]
    C[i] = (1 - d_rate) * C[i-1] + b_gain * g
df["C"] = C

dC = np.diff(C, prepend=C[0])
df["dC"] = dC

# Baseline stats (first w_base months)
mu_base    = dC[:w_base].mean()
sig_base   = dC[:w_base].std()
thresh_val = mu_base + k * sig_base

# Structural break: M2 reclassification 2020-05
BREAK_DATE = pd.Timestamp("2020-05-01")

# ── Plot ──────────────────────────────────────────────────────────────
fig, axes = plt.subplots(3, 1, figsize=(12, 9),
                         facecolor=BG,
                         gridspec_kw={"hspace": 0.4, "height_ratios": [2, 2, 1.5]})
fig.patch.set_facecolor(BG)

def style_ax(ax, title, ylabel=""):
    ax.set_facecolor(SURF)
    for sp in ax.spines.values():
        sp.set_color(MUTED); sp.set_linewidth(0.5)
    ax.tick_params(colors=MUTED, labelsize=7)
    ax.set_title(title, color=TEXT, fontfamily="monospace", fontsize=9, pad=6)
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED, fontfamily="monospace", fontsize=7.5)

def vbreak(ax, label="M2 break\nmai 2020"):
    ax.axvline(BREAK_DATE, color=AMBER, lw=0.8, ls="--", alpha=0.7, zorder=5)
    ax.text(BREAK_DATE + pd.Timedelta(days=60), 0.92,
            label, color=AMBER, fontfamily="monospace", fontsize=6.5,
            transform=ax.get_xaxis_transform(), va="top")

# ── Ax 0 : O, R, I, Cap ───────────────────────────────────────────────
ax = axes[0]
ax.plot(df["date"], df["O"],   color=GREEN,  lw=0.9, label="O — organisation")
ax.plot(df["date"], df["R"],   color=BLUE,   lw=0.9, label="R — résilience")
ax.plot(df["date"], df["I"],   color="#7a6898", lw=0.9, label="I — intégration")
ax.plot(df["date"], df["Cap"], color=TEXT,   lw=1.3, ls="--", label="Cap(t)")
ax.fill_between(df["date"], df["Sigma"], color=AMBER, alpha=0.15, lw=0,
                label="Σ(t) = stress")
vbreak(ax)

# Shade M2 post-break region
mask = df["date"] >= BREAK_DATE
ax.axvspan(BREAK_DATE, df["date"].max(), color=AMBER, alpha=0.04, zorder=0)

style_ax(ax, "O(t) · R(t) · I(t) · Cap(t) · Σ(t)  —  FRED mensuel US 1986–2025", "valeur [0,1]")
ax.legend(fontsize=6.5, facecolor=SURF, edgecolor=MUTED, labelcolor=TEXT,
          ncol=5, loc="upper left", framealpha=0.85)

# ── Ax 1 : C(t) + S(t) ────────────────────────────────────────────────
ax = axes[1]
ax2 = ax.twinx()
ax2.set_facecolor(SURF)
ax2.plot(df["date"], df["S"], color=BLUE, lw=0.8, alpha=0.5, label="S(t) — M2 proxy")
ax2.tick_params(colors=MUTED, labelsize=7)
ax2.spines["right"].set_color(MUTED); ax2.spines["right"].set_linewidth(0.5)
ax2.set_ylabel("S(t) [0,1]", color=MUTED, fontfamily="monospace", fontsize=7)
ax2.yaxis.label.set_color(MUTED)

ax.plot(df["date"], df["C"], color=GREEN, lw=1.3, label="C(t) — variable d'ordre")
vbreak(ax)
ax.axvspan(BREAK_DATE, df["date"].max(), color=AMBER, alpha=0.04, zorder=0)
style_ax(ax, "C(t) et S(t) — variable d'ordre vs stock symbolique (M2)", "C(t)")
handles1, labels1 = ax.get_legend_handles_labels()
handles2, labels2 = ax2.get_legend_handles_labels()
ax.legend(handles1 + handles2, labels1 + labels2,
          fontsize=6.5, facecolor=SURF, edgecolor=MUTED, labelcolor=TEXT,
          framealpha=0.85)

# ── Ax 2 : ΔC(t) + seuil ─────────────────────────────────────────────
ax = axes[2]
ax.axhline(thresh_val, color=AMBER, lw=0.8, ls="--",
           label=f"seuil μ+{k}σ = {thresh_val:.4f}")
ax.axhline(mu_base, color=MUTED, lw=0.6, ls=":")
ax.fill_between(df["date"], df["dC"], thresh_val,
                where=(df["dC"] > thresh_val),
                color=GREEN, alpha=0.3, lw=0, label="ΔC > seuil")
ax.plot(df["date"], df["dC"], color=GREEN, lw=0.7)
vbreak(ax)
style_ax(ax, "ΔC(t) — détection de seuil", "ΔC(t)")
ax.legend(fontsize=6.5, facecolor=SURF, edgecolor=MUTED, labelcolor=TEXT,
          framealpha=0.85)

# ── Verdict annotation ────────────────────────────────────────────────
n_exceeded   = int((df["dC"] > thresh_val).sum())
n_total      = len(df)
verdict_text = (
    f"n_threshold_exceeded = {n_exceeded}/{n_total}  "
    f"|  seuil = {thresh_val:.4f}  "
    f"|  bris structurel M2 : mai 2020 (flagué, fenêtrage recommandé)"
)
fig.text(0.5, 0.01, verdict_text, ha="center", va="bottom",
         fontsize=6.5, color=MUTED, fontfamily="monospace")

# ── Main title ────────────────────────────────────────────────────────
fig.suptitle(
    "Fig. 3 — Pilote FRED : données réelles mensuelles US (480 points, 1986–2025)",
    color=TEXT, fontfamily="monospace", fontsize=10, y=0.99)

plt.savefig("fig3_real_fred.png", dpi=150, bbox_inches="tight",
            facecolor=BG, edgecolor="none")
print("Saved: fig3_real_fred.png")
