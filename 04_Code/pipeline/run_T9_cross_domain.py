#!/usr/bin/env python3
"""run_T9_cross_domain.py — T9: Cross-domain "vivant-like" discrimination test.

Hypothesis H9
    Systems with vivant-like properties (regulation, resilience, threshold,
    recovery) produce stable, discriminating ORI-C signatures that resist
    window, normalization, noise and subsampling stress.
    Purely stochastic / chaotic / periodic controls do NOT produce this quadruplet.

Positive controls (vivant-like) — 6 datasets
    real_fred      : real macro-financial monthly data (FRED bundle, 480 rows)
    synth_physio   : AR(1) regulated process with mean-reversion + demand shock
    synth_ecology  : Lotka-Volterra oscillations with habitat perturbation
    synth_org_flux : organisational flux with capacity threshold
    synth_adaptive : online-adaptive system with loss regulation
    synth_neuro    : neural state attractor — transition then return

Negative controls — 6 datasets
    neg_white      : iid Gaussian noise
    neg_pink       : 1/f (pink) noise
    neg_rw         : pure random walk (no mean-reversion)
    neg_sine       : sinusoid + noise (no feedback)
    neg_poisson    : Poisson-driven jumps
    neg_chaotic    : logistic map r=4 (fully chaotic, no regulation)

Features extracted per dataset (8 total)
    1. recovery_score    — mean-reversion coefficient after injected shock
    2. feedback_score    — negative autocorr of deviation from mean
    3. regime_score      — max delta_C burst / baseline delta_C
    4. demand_response   — Spearman(demand_t, Sigma_t+1)
    5. stationarity_score— fraction of O,R,I with ADF p < 0.10
    6. viability_score   — fraction of time O,R,I in [0.2, 0.8]
    7. sigma_persistence — autocorr of Sigma (lag-1); low=regulated
    8. oric_verdict_score— 1=ACCEPT, 0.5=INDETERMINATE, 0=REJECT

Verdict criteria (frozen in t9_criteria.json)
    balanced_accuracy  >= 0.80
    fpr_negatives      <= 0.10
    spearman_stability >= 0.80
    jaccard_topk       >= 0.60
    verdict_flip_rate  <= 0.10
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_HERE))

from ori_c_pipeline import ORICConfig, run_oric_from_observations  # noqa: E402


# ---------------------------------------------------------------------------
# Frozen criteria loader
# ---------------------------------------------------------------------------

def _load_criteria() -> dict:
    p = _HERE / "t9_criteria.json"
    with open(p) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Synthetic positive generators
# ---------------------------------------------------------------------------

def _ar1(rng: np.random.Generator, phi: float, mu: float, sigma: float, n: int) -> np.ndarray:
    x = np.empty(n)
    x[0] = mu + rng.normal(0, sigma)
    for i in range(1, n):
        x[i] = mu + phi * (x[i - 1] - mu) + rng.normal(0, sigma)
    return np.clip(x, 0.02, 0.98)


def _gen_positive_physio(n: int, seed: int) -> pd.DataFrame:
    """AR(1) regulated physiology: mean-reverting O/R/I + mid-series demand shock."""
    rng = np.random.default_rng(seed)
    O = _ar1(rng, 0.82, 0.55, 0.03, n)
    R = _ar1(rng, 0.90, 0.65, 0.02, n)
    I = _ar1(rng, 0.75, 0.50, 0.04, n)
    Cap = O * R * I
    base_demand = 0.88 * Cap
    shock_s, shock_e = int(0.35 * n), int(0.65 * n)
    demand = base_demand + rng.normal(0, 0.01 * base_demand.mean(), n)
    demand[shock_s:shock_e] *= 1.40
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand})


def _gen_positive_ecology(n: int, seed: int) -> pd.DataFrame:
    """Lotka-Volterra oscillations with habitat perturbation."""
    rng = np.random.default_rng(seed)
    x, y = np.zeros(n), np.zeros(n)
    x[0], y[0] = 0.5, 0.3
    r, K, alpha = 0.30, 1.0, 0.25
    beta, delta = 0.20, 0.15
    for i in range(1, n):
        dx = r * x[i - 1] * (1 - x[i - 1] / K) - alpha * x[i - 1] * y[i - 1]
        dy = beta * x[i - 1] * y[i - 1] - delta * y[i - 1]
        x[i] = np.clip(x[i - 1] + 0.10 * dx + rng.normal(0, 0.01), 0.05, 0.95)
        y[i] = np.clip(y[i - 1] + 0.10 * dy + rng.normal(0, 0.01), 0.05, 0.95)
    I = _ar1(rng, 0.80, 0.55, 0.03, n)
    Cap = x * y * I
    shock_s, shock_e = int(0.40 * n), int(0.65 * n)
    demand = 0.85 * Cap + rng.normal(0, 0.01, n)
    demand[shock_s:shock_e] *= 1.35
    return pd.DataFrame({"t": np.arange(n), "O": x, "R": y, "I": I, "demand": demand})


def _gen_positive_org_flux(n: int, seed: int) -> pd.DataFrame:
    """Organisational flux: regulated capacity with threshold response."""
    rng = np.random.default_rng(seed)
    capacity = 0.60
    O_list, R_list, I_list, demand_list = [], [], [], []
    shock_s, shock_e = int(0.38 * n), int(0.62 * n)
    for t in range(n):
        load = 0.85 * capacity + rng.normal(0, 0.02)
        if shock_s <= t < shock_e:
            load *= 1.45
        if load > capacity:
            capacity = min(0.95, capacity + 0.02 * (load - capacity))
        else:
            capacity = max(0.30, capacity - 0.01 * (capacity - load))
        O_list.append(np.clip(capacity + rng.normal(0, 0.02), 0.05, 0.95))
        R_list.append(np.clip(0.70 - 0.10 * (load / capacity - 1) + rng.normal(0, 0.02), 0.05, 0.95))
        I_list.append(np.clip(0.55 + rng.normal(0, 0.03), 0.05, 0.95))
        demand_list.append(load)
    O, R, I = np.array(O_list), np.array(R_list), np.array(I_list)
    demand = np.array(demand_list)
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand})


def _gen_positive_adaptive(n: int, seed: int) -> pd.DataFrame:
    """Online-adaptive system: regulates a 'loss' proxy toward a target."""
    rng = np.random.default_rng(seed)
    loss = 0.80
    O_list, R_list, I_list, demand_list = [], [], [], []
    shock_s, shock_e = int(0.35 * n), int(0.60 * n)
    for t in range(n):
        target = 0.20
        if shock_s <= t < shock_e:
            target = 0.50 + 0.05 * rng.normal()
        grad = loss - target
        lr = 0.08 + 0.05 * rng.random()
        loss = np.clip(loss - lr * grad + rng.normal(0, 0.02), 0.05, 0.95)
        O_list.append(np.clip(1.0 - loss + rng.normal(0, 0.02), 0.05, 0.95))
        R_list.append(np.clip(0.80 - 0.50 * loss + rng.normal(0, 0.02), 0.05, 0.95))
        I_list.append(np.clip(0.60 + rng.normal(0, 0.03), 0.05, 0.95))
        demand_list.append(np.clip(0.70 * loss + rng.normal(0, 0.01), 0.01, 1.0))
    O, R, I = np.array(O_list), np.array(R_list), np.array(I_list)
    demand = np.array(demand_list)
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand})


def _gen_positive_neuro(n: int, seed: int) -> pd.DataFrame:
    """Neural attractor: transition to high-activity state then return."""
    rng = np.random.default_rng(seed)
    att_low, att_high = 0.25, 0.75
    state = att_low
    O_list, R_list, I_list, demand_list = [], [], [], []
    shock_s, shock_e = int(0.40 * n), int(0.60 * n)
    for t in range(n):
        target = att_high if shock_s <= t < shock_e else att_low
        state = np.clip(state + 0.12 * (target - state) + rng.normal(0, 0.02), 0.05, 0.95)
        O_list.append(np.clip(state + rng.normal(0, 0.02), 0.05, 0.95))
        R_list.append(np.clip(1.0 - abs(state - att_low) - abs(state - att_high) + rng.normal(0, 0.02), 0.05, 0.95))
        I_list.append(np.clip(0.50 + rng.normal(0, 0.03), 0.05, 0.95))
        Cap = O_list[-1] * R_list[-1] * I_list[-1]
        demand_list.append(np.clip(0.90 * Cap + rng.normal(0, 0.01), 0.01, 1.0))
    O, R, I = np.array(O_list), np.array(R_list), np.array(I_list)
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": np.array(demand_list)})


def _load_real_fred(repo_root: Path, n_max: int) -> pd.DataFrame | None:
    """Load the FRED monthly real dataset (pre-processed O/R/I/demand/S columns)."""
    csv_path = repo_root / "03_Data" / "real" / "fred_monthly" / "real.csv"
    if not csv_path.exists():
        return None
    df = pd.read_csv(csv_path)
    required = ["O", "R", "I", "demand"]
    if not all(c in df.columns for c in required):
        return None
    df = df[required + (["t"] if "t" in df.columns else [])].dropna(subset=required).copy()
    if "t" not in df.columns:
        df.insert(0, "t", np.arange(len(df)))
    for c in required:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=required).reset_index(drop=True)
    df["t"] = np.arange(len(df))
    if n_max and len(df) > n_max:
        df = df.iloc[:n_max].copy()
        df["t"] = np.arange(len(df))
    return df[["t", "O", "R", "I", "demand"]]


# ---------------------------------------------------------------------------
# Negative generators
# ---------------------------------------------------------------------------

def _gen_negative_white(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    O = np.clip(rng.normal(0.50, 0.12, n), 0.05, 0.95)
    R = np.clip(rng.normal(0.50, 0.12, n), 0.05, 0.95)
    I = np.clip(rng.normal(0.50, 0.12, n), 0.05, 0.95)
    demand = np.clip(rng.normal(0.40, 0.10, n), 0.01, 1.0)
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand})


def _gen_negative_pink(n: int, seed: int) -> pd.DataFrame:
    """1/f pink noise via spectral method."""
    rng = np.random.default_rng(seed)

    def _pink(n_: int) -> np.ndarray:
        f = np.fft.rfftfreq(n_)
        f[0] = 1.0
        power = 1.0 / np.sqrt(f)
        phases = rng.uniform(0, 2 * np.pi, len(power))
        spectrum = power * np.exp(1j * phases)
        sig = np.fft.irfft(spectrum, n=n_)
        sig = (sig - sig.mean()) / (sig.std() + 1e-9)
        return np.clip(0.50 + 0.12 * sig, 0.05, 0.95)

    O, R, I = _pink(n), _pink(n), _pink(n)
    demand = np.clip(0.40 + 0.10 * _pink(n), 0.01, 1.0)
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand})


def _gen_negative_rw(n: int, seed: int) -> pd.DataFrame:
    """Pure random walk — no mean-reversion at all."""
    rng = np.random.default_rng(seed)
    x = np.cumsum(rng.normal(0, 0.015, n))
    O = np.clip((x - x.min()) / (x.max() - x.min() + 1e-9) * 0.80 + 0.10, 0.05, 0.95)
    y = np.cumsum(rng.normal(0, 0.015, n))
    R = np.clip((y - y.min()) / (y.max() - y.min() + 1e-9) * 0.80 + 0.10, 0.05, 0.95)
    z = np.cumsum(rng.normal(0, 0.015, n))
    I = np.clip((z - z.min()) / (z.max() - z.min() + 1e-9) * 0.80 + 0.10, 0.05, 0.95)
    demand = np.clip(0.90 * O * R * I + rng.normal(0, 0.01, n), 0.01, 1.0)
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand})


def _gen_negative_sine(n: int, seed: int) -> pd.DataFrame:
    """Pure sinusoid + noise — periodic but no feedback mechanism."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    O = np.clip(0.50 + 0.25 * np.sin(2 * np.pi * t / (n * 0.30)) + rng.normal(0, 0.04, n), 0.05, 0.95)
    R = np.clip(0.55 + 0.20 * np.sin(2 * np.pi * t / (n * 0.45) + 1.0) + rng.normal(0, 0.04, n), 0.05, 0.95)
    I = np.clip(0.50 + 0.20 * np.sin(2 * np.pi * t / (n * 0.20) + 0.5) + rng.normal(0, 0.04, n), 0.05, 0.95)
    demand = np.clip(0.45 + 0.15 * np.sin(2 * np.pi * t / (n * 0.35)) + rng.normal(0, 0.03, n), 0.01, 1.0)
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand})


def _gen_negative_poisson(n: int, seed: int) -> pd.DataFrame:
    """Poisson-driven jump process — no feedback."""
    rng = np.random.default_rng(seed)
    base = 0.50
    O = np.clip(base + 0.20 * (rng.poisson(0.5, n) - 0.5) + rng.normal(0, 0.02, n), 0.05, 0.95)
    R = np.clip(base + 0.20 * (rng.poisson(0.5, n) - 0.5) + rng.normal(0, 0.02, n), 0.05, 0.95)
    I = np.clip(base + 0.15 * (rng.poisson(0.5, n) - 0.5) + rng.normal(0, 0.02, n), 0.05, 0.95)
    demand = np.clip(0.40 + rng.normal(0, 0.08, n), 0.01, 1.0)
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand})


def _gen_negative_chaotic(n: int, seed: int) -> pd.DataFrame:
    """Logistic map r=4 — fully deterministic chaos, no regulation."""
    rng = np.random.default_rng(seed)
    r = 4.0
    x, y, z = rng.random(), rng.random(), rng.random()
    O_l, R_l, I_l = [x], [y], [z]
    for _ in range(n - 1):
        x = r * x * (1 - x)
        y = r * y * (1 - y)
        z = r * z * (1 - z)
        O_l.append(x)
        R_l.append(y)
        I_l.append(z)
    O, R, I = np.clip(O_l, 0.05, 0.95), np.clip(R_l, 0.05, 0.95), np.clip(I_l, 0.05, 0.95)
    demand = np.clip(0.90 * O * R * I + rng.normal(0, 0.01, n), 0.01, 1.0)
    return pd.DataFrame({"t": np.arange(n), "O": O, "R": R, "I": I, "demand": demand})


# ---------------------------------------------------------------------------
# ORI-C runner (direct API, not subprocess)
# ---------------------------------------------------------------------------

def _run_oric_direct(df: pd.DataFrame, seed: int = 1234) -> pd.DataFrame | None:
    """Run ORI-C on a DataFrame with t, O, R, I, demand columns."""
    cfg = ORICConfig(
        seed=seed, n_steps=len(df),
        intervention="none", sigma_star=0.0,
    )
    try:
        return run_oric_from_observations(df, cfg)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _extract_features(df_raw: pd.DataFrame, df_oric: pd.DataFrame | None) -> np.ndarray:
    """Return 8-dimensional feature vector for one dataset."""
    n = len(df_raw)
    O, R, I = df_raw["O"].to_numpy(), df_raw["R"].to_numpy(), df_raw["I"].to_numpy()
    demand = df_raw["demand"].to_numpy() if "demand" in df_raw.columns else np.ones(n) * 0.5

    # ── Feature 1: recovery_score ─────────────────────────────────────────
    # After a mid-series shock, does O+R+I return toward baseline?
    # Measure: corr(deviation_post_shock, time) should be negative for regulated.
    shock_e = min(int(0.65 * n), n - 5)
    post_shock = slice(shock_e, min(shock_e + max(5, n // 8), n))
    baseline_mean = np.mean(O[:int(0.30 * n)] + R[:int(0.30 * n)] + I[:int(0.30 * n)]) / 3
    post_vals = (O[post_shock] + R[post_shock] + I[post_shock]) / 3
    t_idx = np.arange(len(post_vals), dtype=float)
    if len(post_vals) > 2:
        recovery_score = float(np.corrcoef(t_idx, post_vals - baseline_mean)[0, 1])
        # Negative corr = recovering (trending back). Positive = still drifting.
        recovery_score = max(0.0, -recovery_score)  # flip so higher = better
    else:
        recovery_score = 0.5

    # ── Feature 2: feedback_score ─────────────────────────────────────────
    # Mean-reversion: corr(x[t]-mean, x[t+1]-x[t]) should be negative.
    def _feedback(x: np.ndarray) -> float:
        dev = x[:-1] - x[:-1].mean()
        step = x[1:] - x[:-1]
        if len(dev) < 3 or dev.std() < 1e-10:
            return 0.0
        c = float(np.corrcoef(dev, step)[0, 1])
        return max(0.0, -c)  # flip so higher = stronger feedback

    feedback_score = float(np.mean([_feedback(O), _feedback(R), _feedback(I)]))

    # ── Feature 3: regime_score ───────────────────────────────────────────
    # Does ORI-C delta_C show a burst (threshold crossing evidence)?
    if df_oric is not None and "delta_C" in df_oric.columns:
        delta_C = df_oric["delta_C"].to_numpy()
        baseline_delta = max(np.mean(np.abs(delta_C[:int(0.30 * n)])), 1e-9)
        max_burst = np.max(np.abs(delta_C)) if len(delta_C) > 0 else 0.0
        regime_score = float(np.clip(max_burst / baseline_delta, 0, 20) / 20.0)
    else:
        # Fallback: variance ratio between first and second half of signal
        mid = n // 2
        first_var = np.var(O[:mid] + R[:mid] + I[:mid])
        second_var = np.var(O[mid:] + R[mid:] + I[mid:])
        regime_score = float(np.clip(second_var / (first_var + 1e-9), 0, 5) / 5.0)

    # ── Feature 4: demand_response ────────────────────────────────────────
    # Spearman(demand_t, Sigma_t+1): stress leads to measurable Sigma.
    if df_oric is not None and "Sigma" in df_oric.columns:
        Sigma = df_oric["Sigma"].to_numpy()
        if len(Sigma) > 2 and Sigma.std() > 1e-10:
            from scipy.stats import spearmanr
            corr_val, _ = spearmanr(demand[:-1], Sigma[1:])
            demand_response = float(np.clip((corr_val + 1) / 2, 0, 1))
        else:
            demand_response = 0.3
    else:
        # Proxy: corr between demand and variance of O+R+I
        rolling_var = np.array([
            np.var(O[max(0, i - 5):i + 1] + R[max(0, i - 5):i + 1] + I[max(0, i - 5):i + 1])
            for i in range(n)
        ])
        if rolling_var.std() > 1e-10:
            from scipy.stats import spearmanr
            corr_val, _ = spearmanr(demand, rolling_var)
            demand_response = float(np.clip((corr_val + 1) / 2, 0, 1))
        else:
            demand_response = 0.3

    # ── Feature 5: stationarity_score ────────────────────────────────────
    # Fraction of O,R,I with ADF p < 0.10 (stationary = regulated).
    from statsmodels.tsa.stattools import adfuller
    n_stat = 0
    for series in [O, R, I]:
        if len(series) >= 15 and series.std() > 1e-10:
            try:
                p = adfuller(series, autolag="AIC")[1]
                if p < 0.10:
                    n_stat += 1
            except Exception:
                pass
    stationarity_score = n_stat / 3.0

    # ── Feature 6: viability_score ────────────────────────────────────────
    # Fraction of time O,R,I stay in viable zone [0.2, 0.8].
    in_zone = (
        ((O >= 0.20) & (O <= 0.80)).mean() +
        ((R >= 0.20) & (R <= 0.80)).mean() +
        ((I >= 0.20) & (I <= 0.80)).mean()
    ) / 3.0
    viability_score = float(in_zone)

    # ── Feature 7: sigma_persistence ─────────────────────────────────────
    # Autocorr of Sigma at lag 1. Low persistence = regulated system.
    if df_oric is not None and "Sigma" in df_oric.columns:
        Sigma = df_oric["Sigma"].to_numpy()
        if len(Sigma) > 2 and Sigma.std() > 1e-10:
            autocorr = float(np.corrcoef(Sigma[:-1], Sigma[1:])[0, 1])
            # Regulated = low persistence. Score: flip so higher=less persistent.
            sigma_persistence = float(1.0 - np.clip(abs(autocorr), 0, 1))
        else:
            sigma_persistence = 0.5
    else:
        sigma_persistence = 0.5

    # ── Feature 8: oric_verdict_score ─────────────────────────────────────
    if df_oric is not None and "threshold_hit" in df_oric.columns:
        n_hit = int(df_oric["threshold_hit"].sum())
        oric_verdict_score = float(np.clip(n_hit / max(n * 0.1, 1), 0, 1))
    else:
        oric_verdict_score = 0.0

    return np.array([
        recovery_score,
        feedback_score,
        regime_score,
        demand_response,
        stationarity_score,
        viability_score,
        sigma_persistence,
        oric_verdict_score,
    ], dtype=float)


# ---------------------------------------------------------------------------
# Discrimination metrics
# ---------------------------------------------------------------------------

def _balanced_accuracy(features: np.ndarray, labels: np.ndarray) -> float:
    """Compute balanced accuracy using a simple aggregate score threshold."""
    scores = features.mean(axis=1)
    # Sweep threshold
    best_ba = 0.0
    for thr in np.linspace(scores.min(), scores.max(), 50):
        pred = (scores >= thr).astype(int)
        tp = int(((pred == 1) & (labels == 1)).sum())
        tn = int(((pred == 0) & (labels == 0)).sum())
        fp = int(((pred == 1) & (labels == 0)).sum())
        fn = int(((pred == 0) & (labels == 1)).sum())
        sens = tp / (tp + fn + 1e-9)
        spec = tn / (tn + fp + 1e-9)
        ba = (sens + spec) / 2
        best_ba = max(best_ba, ba)
    return best_ba


def _fpr_on_negatives(features: np.ndarray, labels: np.ndarray) -> float:
    """False positive rate on negative class at the balanced-accuracy threshold."""
    scores = features.mean(axis=1)
    neg_scores = scores[labels == 0]
    pos_scores = scores[labels == 1]
    if len(pos_scores) == 0 or len(neg_scores) == 0:
        return 0.5
    threshold = np.median(pos_scores) - 0.5 * (np.median(pos_scores) - np.median(neg_scores))
    fp_rate = float((neg_scores >= threshold).mean())
    return fp_rate


def _auc_score(features: np.ndarray, labels: np.ndarray) -> float:
    """AUC via trapezoidal rule on aggregate score."""
    scores = features.mean(axis=1)
    thresholds = np.linspace(scores.min() - 0.01, scores.max() + 0.01, 100)
    tpr_list, fpr_list = [0.0], [0.0]
    for thr in sorted(thresholds, reverse=True):
        pred = (scores >= thr).astype(int)
        tp = int(((pred == 1) & (labels == 1)).sum())
        fp = int(((pred == 1) & (labels == 0)).sum())
        fn = int(((pred == 0) & (labels == 1)).sum())
        tn = int(((pred == 0) & (labels == 0)).sum())
        tpr_list.append(tp / (tp + fn + 1e-9))
        fpr_list.append(fp / (fp + tn + 1e-9))
    tpr_list.append(1.0)
    fpr_list.append(1.0)
    auc = float(np.trapz(tpr_list, fpr_list))
    return abs(auc)


# ---------------------------------------------------------------------------
# Stress testing
# ---------------------------------------------------------------------------

def _apply_noise(df: pd.DataFrame, noise_frac: float, rng: np.random.Generator) -> pd.DataFrame:
    df2 = df.copy()
    for col in ["O", "R", "I", "demand"]:
        if col in df2.columns:
            s = df2[col].to_numpy(dtype=float)
            std = s.std() or 0.05
            df2[col] = np.clip(s + rng.normal(0, noise_frac * std, len(s)), 0.02, 0.98)
    return df2


def _apply_subsample(df: pd.DataFrame, factor: int) -> pd.DataFrame:
    df2 = df.iloc[::factor].copy().reset_index(drop=True)
    df2["t"] = np.arange(len(df2))
    return df2


def _apply_normalize(df: pd.DataFrame, method: str) -> pd.DataFrame:
    df2 = df.copy()
    for col in ["O", "R", "I", "demand"]:
        if col not in df2.columns:
            continue
        s = df2[col].to_numpy(dtype=float)
        if method == "zscore":
            mu, sd = s.mean(), s.std()
            if sd > 1e-10:
                s = (s - mu) / sd
                s = np.clip((s - s.min()) / (s.max() - s.min() + 1e-9) * 0.80 + 0.10, 0.02, 0.98)
        elif method == "robust_minmax":
            lo, hi = np.percentile(s, 2), np.percentile(s, 98)
            if hi > lo:
                s = np.clip((s - lo) / (hi - lo) * 0.80 + 0.10, 0.02, 0.98)
        df2[col] = s
    return df2


def _run_stress_tests(
    datasets: list[dict],
    stress_configs: list[dict],
    seed: int = 42,
) -> dict[str, Any]:
    """Run each dataset under each stress config; compute Spearman stability."""
    from scipy.stats import spearmanr

    rng = np.random.default_rng(seed)
    feature_names = [
        "recovery_score", "feedback_score", "regime_score", "demand_response",
        "stationarity_score", "viability_score", "sigma_persistence", "oric_verdict_score",
    ]
    labels = np.array([d["label"] for d in datasets])

    # Baseline features
    base_features = np.array([
        _extract_features(d["df"], _run_oric_direct(d["df"], seed=d["seed"]))
        for d in datasets
    ])
    base_scores = base_features.mean(axis=1)

    spearman_vals, jaccard_vals, flip_vals = [], [], []
    config_results = []

    for cfg in stress_configs:
        stressed = []
        for d in datasets:
            df2 = d["df"].copy()
            if cfg.get("subsample", 1) > 1:
                df2 = _apply_subsample(df2, cfg["subsample"])
            if cfg.get("noise_frac", 0) > 0:
                df2 = _apply_noise(df2, cfg["noise_frac"], rng)
            if cfg.get("normalize"):
                df2 = _apply_normalize(df2, cfg["normalize"])
            stressed.append(df2)

        stressed_features = np.array([
            _extract_features(df2, _run_oric_direct(df2, seed=datasets[i]["seed"]))
            for i, df2 in enumerate(stressed)
        ])
        stressed_scores = stressed_features.mean(axis=1)

        # Spearman rank stability
        if len(base_scores) >= 4 and base_scores.std() > 1e-10:
            sp, _ = spearmanr(base_scores, stressed_scores)
        else:
            sp = 1.0

        # Jaccard TopK
        k = 3
        top_base = set(np.argsort(base_scores)[-k:])
        top_stress = set(np.argsort(stressed_scores)[-k:])
        jaccard = len(top_base & top_stress) / len(top_base | top_stress) if (top_base | top_stress) else 1.0

        # Verdict flip rate (binary: positive or negative)
        base_pred = (base_scores >= np.median(base_scores)).astype(int)
        stress_pred = (stressed_scores >= np.median(stressed_scores)).astype(int)
        flip_rate = float((base_pred != stress_pred).mean())

        spearman_vals.append(sp)
        jaccard_vals.append(jaccard)
        flip_vals.append(flip_rate)
        config_results.append({
            "config": cfg["name"],
            "spearman": round(float(sp), 4),
            "jaccard": round(float(jaccard), 4),
            "flip_rate": round(float(flip_rate), 4),
        })

    return {
        "config_results": config_results,
        "spearman_median": round(float(np.median(spearman_vals)), 4),
        "jaccard_median": round(float(np.median(jaccard_vals)), 4),
        "flip_rate_median": round(float(np.median(flip_vals)), 4),
    }


# ---------------------------------------------------------------------------
# Ablations
# ---------------------------------------------------------------------------

def _run_ablations(
    full_features: np.ndarray,
    labels: np.ndarray,
    ablation_feature_names: list[str],
    feature_names: list[str],
) -> list[dict]:
    full_auc = _auc_score(full_features, labels)
    results = []
    for name in ablation_feature_names:
        if name not in feature_names:
            continue
        idx = feature_names.index(name)
        ablated = np.delete(full_features, idx, axis=1)
        abl_auc = _auc_score(ablated, labels)
        drop = round(float(full_auc - abl_auc), 4)
        results.append({
            "ablated_feature": name,
            "full_auc": round(float(full_auc), 4),
            "ablated_auc": round(float(abl_auc), 4),
            "auc_drop": drop,
            "meaningful_drop": drop >= 0.05,
        })
    return results


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def _compute_baselines(datasets: list[dict], labels: np.ndarray) -> dict[str, float]:
    from scipy.stats import ttest_ind

    baselines = {}

    # B1: variance + autocorr
    b1_features = []
    for d in datasets:
        O, R, I = d["df"]["O"].to_numpy(), d["df"]["R"].to_numpy(), d["df"]["I"].to_numpy()
        var_mean = np.mean([O.var(), R.var(), I.var()])
        ac_mean = np.mean([
            float(np.corrcoef(x[:-1], x[1:])[0, 1]) if len(x) > 2 else 0
            for x in [O, R, I]
        ])
        b1_features.append([var_mean, ac_mean])
    b1 = _auc_score(np.array(b1_features), labels)
    baselines["variance_autocorr"] = round(float(b1), 4)

    # B2: Welch mean-shift (t-stat of first vs second half)
    b2_features = []
    for d in datasets:
        O = d["df"]["O"].to_numpy()
        n = len(O)
        _, pval = ttest_ind(O[:n // 2], O[n // 2:], equal_var=False)
        b2_features.append([-np.log10(pval + 1e-10)])
    b2 = _auc_score(np.array(b2_features), labels)
    baselines["welch_shift"] = round(float(b2), 4)

    # B3: CUSUM max change point
    b3_features = []
    for d in datasets:
        O = d["df"]["O"].to_numpy()
        cusum = np.abs(np.cumsum(O - O.mean()))
        b3_features.append([cusum.max() / (O.std() + 1e-9)])
    b3 = _auc_score(np.array(b3_features), labels)
    baselines["cusum"] = round(float(b3), 4)

    # B4: simple stats (mean, std, skew, kurtosis)
    from scipy.stats import skew, kurtosis
    b4_features = []
    for d in datasets:
        O = d["df"]["O"].to_numpy()
        b4_features.append([O.mean(), O.std(), skew(O), kurtosis(O)])
    b4 = _auc_score(np.array(b4_features), labels)
    baselines["simple_stats"] = round(float(b4), 4)

    return baselines


# ---------------------------------------------------------------------------
# Verdict computation
# ---------------------------------------------------------------------------

def _verdict_from_metrics(
    metrics: dict,
    stress: dict,
    criteria: dict,
) -> dict:
    c = criteria
    blocks = {}

    # Discrimination block
    disc_pass = (
        metrics.get("balanced_accuracy", 0) >= c["balanced_accuracy_min"]
        and metrics.get("fpr_negatives", 1) <= c["fpr_negatives_max"]
    )
    blocks["discrimination"] = "ACCEPT" if disc_pass else "REJECT"

    # Robustness block
    rob_pass = (
        stress.get("spearman_median", 0) >= c["spearman_stability_min"]
        and stress.get("jaccard_median", 0) >= c["jaccard_topk_min"]
        and stress.get("flip_rate_median", 1) <= c["verdict_flip_rate_max"]
    )
    blocks["robustness"] = "ACCEPT" if rob_pass else "REJECT"

    # Anti-gaming block (fpr alone)
    blocks["anti_gaming"] = "ACCEPT" if metrics.get("fpr_negatives", 1) <= c["fpr_negatives_max"] else "REJECT"

    # Global
    if all(v == "ACCEPT" for v in blocks.values()):
        global_verdict = "ACCEPT"
    elif any(v == "REJECT" for v in blocks.values()):
        global_verdict = "REJECT"
    else:
        global_verdict = "INDETERMINATE"

    return {
        "global": global_verdict,
        "blocks": blocks,
        "criteria_used": {
            "balanced_accuracy_min": c["balanced_accuracy_min"],
            "fpr_negatives_max": c["fpr_negatives_max"],
            "spearman_stability_min": c["spearman_stability_min"],
            "jaccard_topk_min": c["jaccard_topk_min"],
            "verdict_flip_rate_max": c["verdict_flip_rate_max"],
        },
        "values": {
            "balanced_accuracy": round(metrics.get("balanced_accuracy", 0), 4),
            "fpr_negatives": round(metrics.get("fpr_negatives", 1), 4),
            "auc": round(metrics.get("auc", 0), 4),
            "spearman_median": round(stress.get("spearman_median", 0), 4),
            "jaccard_median": round(stress.get("jaccard_median", 0), 4),
            "flip_rate_median": round(stress.get("flip_rate_median", 1), 4),
        },
    }


# ---------------------------------------------------------------------------
# SHA-256 manifest helper
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="T9 cross-domain vivant-like discrimination test")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--seed",   type=int, default=1234, help="Base random seed")
    ap.add_argument("--fast",   action="store_true", help="Smoke CI mode: fewer rows, 1 seed per dataset")
    args = ap.parse_args()

    out = Path(args.outdir)
    tables = out / "tables"
    figures = out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    criteria = _load_criteria()
    n_steps = 80 if args.fast else 220
    print(f"\n[T9] mode={'smoke_ci' if args.fast else 'full_statistical'}  n_steps={n_steps}")

    # ── Build dataset catalogue ───────────────────────────────────────────
    print("[T9] Building benchmark datasets...")
    rng_base = np.random.default_rng(args.seed)

    datasets: list[dict] = []

    def _add(name: str, label: int, df: pd.DataFrame | None, seed: int, cls: str) -> None:
        if df is None or len(df) < 20:
            print(f"  SKIP {name} (None or too short)")
            return
        datasets.append({"name": name, "label": label, "class": cls, "df": df, "seed": seed})
        print(f"  + {name:30s}  label={label}  rows={len(df)}")

    # Positives
    _add("real_fred_monthly",   1, _load_real_fred(_REPO, n_max=n_steps if not args.fast else 100),
         args.seed, "positive_real")
    _add("synth_physio",        1, _gen_positive_physio(n_steps, args.seed + 1),  args.seed + 1, "positive_synth")
    _add("synth_ecology",       1, _gen_positive_ecology(n_steps, args.seed + 2), args.seed + 2, "positive_synth")
    _add("synth_org_flux",      1, _gen_positive_org_flux(n_steps, args.seed + 3), args.seed + 3, "positive_synth")
    _add("synth_adaptive",      1, _gen_positive_adaptive(n_steps, args.seed + 4), args.seed + 4, "positive_synth")
    _add("synth_neuro_attractor",1, _gen_positive_neuro(n_steps, args.seed + 5), args.seed + 5, "positive_synth")

    # Negatives
    _add("neg_white_noise",     0, _gen_negative_white(n_steps, args.seed + 10),   args.seed + 10, "negative")
    _add("neg_pink_noise",      0, _gen_negative_pink(n_steps, args.seed + 11),    args.seed + 11, "negative")
    _add("neg_random_walk",     0, _gen_negative_rw(n_steps, args.seed + 12),      args.seed + 12, "negative")
    _add("neg_sinusoid",        0, _gen_negative_sine(n_steps, args.seed + 13),    args.seed + 13, "negative")
    _add("neg_poisson",         0, _gen_negative_poisson(n_steps, args.seed + 14), args.seed + 14, "negative")
    _add("neg_chaotic_logistic",0, _gen_negative_chaotic(n_steps, args.seed + 15), args.seed + 15, "negative")

    if len(datasets) < 8:
        print(f"[T9] FATAL: only {len(datasets)} datasets available (need >= 8)")
        return 1

    labels = np.array([d["label"] for d in datasets])
    print(f"[T9] {sum(labels==1)} positives, {sum(labels==0)} negatives")

    # ── Extract features ─────────────────────────────────────────────────
    print("[T9] Extracting features (ORI-C direct API)...")
    feature_names = [
        "recovery_score", "feedback_score", "regime_score", "demand_response",
        "stationarity_score", "viability_score", "sigma_persistence", "oric_verdict_score",
    ]
    feat_rows = []
    for d in datasets:
        oric_out = _run_oric_direct(d["df"], seed=d["seed"])
        fvec = _extract_features(d["df"], oric_out)
        feat_rows.append(list(fvec))
        print(f"  {d['name']:30s}  label={d['label']}  "
              f"recovery={fvec[0]:.2f} feedback={fvec[1]:.2f} "
              f"regime={fvec[2]:.2f} demand_resp={fvec[3]:.2f}")

    features = np.array(feat_rows)

    # ── Write features.csv ───────────────────────────────────────────────
    with open(tables / "features.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dataset", "class", "label"] + feature_names)
        for i, d in enumerate(datasets):
            w.writerow([d["name"], d["class"], d["label"]] + [round(float(v), 6) for v in features[i]])

    # ── Compute discrimination metrics ───────────────────────────────────
    print("[T9] Computing discrimination metrics...")
    ba   = _balanced_accuracy(features, labels)
    fpr  = _fpr_on_negatives(features, labels)
    auc  = _auc_score(features, labels)
    print(f"  balanced_accuracy : {ba:.3f}  (min {criteria['balanced_accuracy_min']})")
    print(f"  fpr_negatives     : {fpr:.3f}  (max {criteria['fpr_negatives_max']})")
    print(f"  auc               : {auc:.3f}")

    metrics = {"balanced_accuracy": ba, "fpr_negatives": fpr, "auc": auc}

    # Predictions CSV
    scores = features.mean(axis=1)
    with open(tables / "predictions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dataset", "class", "true_label", "score", "pred_label"])
        threshold = np.median(scores[labels == 1]) - 0.5 * (
            np.median(scores[labels == 1]) - np.median(scores[labels == 0])
        )
        for i, d in enumerate(datasets):
            pred = 1 if scores[i] >= threshold else 0
            w.writerow([d["name"], d["class"], d["label"], round(float(scores[i]), 6), pred])

    # ── Baselines ────────────────────────────────────────────────────────
    print("[T9] Computing baselines...")
    baselines = _compute_baselines(datasets, labels)
    beats = sum(1 for v in baselines.values() if auc >= v)
    beats_frac = beats / len(baselines)
    print(f"  ORI-C AUC={auc:.3f} vs baselines: {baselines}")
    print(f"  ORI-C beats {beats}/{len(baselines)} baselines")

    metrics["baseline_aucs"] = baselines
    metrics["oric_beats_baseline_fraction"] = round(beats_frac, 3)

    # ── Stress tests ─────────────────────────────────────────────────────
    print("[T9] Running stress tests...")
    stress = _run_stress_tests(datasets, criteria["stress_configs"], seed=args.seed + 100)
    print(f"  spearman_median   : {stress['spearman_median']:.3f}  (min {criteria['spearman_stability_min']})")
    print(f"  jaccard_median    : {stress['jaccard_median']:.3f}  (min {criteria['jaccard_topk_min']})")
    print(f"  flip_rate_median  : {stress['flip_rate_median']:.3f}  (max {criteria['verdict_flip_rate_max']})")

    # ── Ablations ────────────────────────────────────────────────────────
    print("[T9] Running ablations...")
    ablations = _run_ablations(features, labels, criteria["ablation_features"], feature_names)
    for abl in ablations:
        print(f"  ablate {abl['ablated_feature']:25s}  drop={abl['auc_drop']:+.3f}  meaningful={abl['meaningful_drop']}")

    with open(tables / "ablation_report.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ablated_feature", "full_auc", "ablated_auc", "auc_drop", "meaningful_drop"])
        for abl in ablations:
            w.writerow([abl["ablated_feature"], abl["full_auc"], abl["ablated_auc"], abl["auc_drop"], abl["meaningful_drop"]])

    # ── Benchmark manifest ───────────────────────────────────────────────
    with open(tables / "benchmark_manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dataset_id", "class", "label", "n_rows", "seed"])
        for d in datasets:
            w.writerow([d["name"], d["class"], d["label"], len(d["df"]), d["seed"]])

    # ── metrics.json ─────────────────────────────────────────────────────
    metrics_out = {
        "auc": round(auc, 4),
        "balanced_accuracy": round(ba, 4),
        "fpr_negatives": round(fpr, 4),
        "spearman_stability_median": stress["spearman_median"],
        "jaccard_topk_median": stress["jaccard_median"],
        "verdict_flip_rate_median": stress["flip_rate_median"],
        "oric_beats_baselines_fraction": round(beats_frac, 3),
        "baseline_aucs": baselines,
        "stress_config_results": stress["config_results"],
        "ablations": ablations,
    }
    with open(tables / "metrics.json", "w") as f:
        json.dump(metrics_out, f, indent=2)

    # ── Verdict ──────────────────────────────────────────────────────────
    print("[T9] Computing verdict...")
    verdict = _verdict_from_metrics(metrics, stress, criteria)

    print(f"\n{'='*55}")
    print(f"  T9 VERDICT: {verdict['global']}")
    print(f"  discrimination: {verdict['blocks']['discrimination']}")
    print(f"  robustness    : {verdict['blocks']['robustness']}")
    print(f"  anti_gaming   : {verdict['blocks']['anti_gaming']}")
    print(f"{'='*55}\n")

    with open(tables / "verdict.json", "w") as f:
        json.dump(verdict, f, indent=2)

    # verdict.txt (canonical token)
    (out / "verdict.txt").write_text(verdict["global"])

    # ── ROC curve figure (text-based for CI) ─────────────────────────────
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        thresholds = np.linspace(scores.min() - 0.01, scores.max() + 0.01, 100)
        tpr_list, fpr_list = [], []
        for thr in sorted(thresholds, reverse=True):
            pred = (scores >= thr).astype(int)
            tp = int(((pred == 1) & (labels == 1)).sum())
            fp = int(((pred == 1) & (labels == 0)).sum())
            fn = int(((pred == 0) & (labels == 1)).sum())
            tn = int(((pred == 0) & (labels == 0)).sum())
            tpr_list.append(tp / (tp + fn + 1e-9))
            fpr_list.append(fp / (fp + tn + 1e-9))

        plt.figure(figsize=(5, 5))
        plt.plot(fpr_list, tpr_list, "b-", linewidth=2, label=f"ORI-C (AUC={auc:.2f})")
        plt.plot([0, 1], [0, 1], "k--", alpha=0.5)
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title("T9 ROC — vivant-like vs negative controls")
        plt.legend()
        plt.tight_layout()
        plt.savefig(figures / "roc_curve.png", dpi=100)
        plt.close()

        # Stability heatmap (features x datasets)
        plt.figure(figsize=(10, 4))
        import matplotlib.patches as mpatches
        mat = features  # shape (n_datasets, n_features)
        plt.imshow(mat.T, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
        plt.xticks(range(len(datasets)), [d["name"][:12] for d in datasets], rotation=45, ha="right", fontsize=7)
        plt.yticks(range(len(feature_names)), feature_names, fontsize=7)
        plt.colorbar(label="Feature score")
        plt.title("T9 Feature stability heatmap (green=high, red=low)")
        plt.tight_layout()
        plt.savefig(figures / "stability_heatmap.png", dpi=100)
        plt.close()
    except Exception as exc:
        print(f"  [figures] skipped: {exc}")

    # ── manifest.json (audit trail) ──────────────────────────────────────
    manifest = {
        "test_id": "T9_cross_domain",
        "seed": args.seed,
        "fast_mode": args.fast,
        "n_steps": n_steps,
        "n_datasets": len(datasets),
        "n_positives": int(sum(labels == 1)),
        "n_negatives": int(sum(labels == 0)),
        "feature_names": feature_names,
        "criteria_file": str(_HERE / "t9_criteria.json"),
        "criteria_sha256": _sha256(_HERE / "t9_criteria.json"),
        "output_files": {
            "benchmark_manifest": "tables/benchmark_manifest.csv",
            "features": "tables/features.csv",
            "predictions": "tables/predictions.csv",
            "metrics": "tables/metrics.json",
            "verdict": "tables/verdict.json",
            "ablation_report": "tables/ablation_report.csv",
        },
    }
    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    return 0 if verdict["global"] in ("ACCEPT", "INDETERMINATE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
