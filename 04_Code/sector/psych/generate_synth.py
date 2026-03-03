"""generate_synth.py — Synthetic data generator for the Psych sector panel.

Two pilots:

  google_trends : Social trust / collective behaviour dynamics via search interest
  wvs_synthetic : World Values Survey-calibrated norm adoption model

ORI-C mappings:

  google_trends:
    O(t) = social_trust_norm        (organisational capacity: civic cohesion)
    R(t) = 1 − anxiety_norm          (societal resilience)
    I(t) = search_coherence_norm     (integration: co-movement of civic indicators)
    S(t) = civic_momentum_cumul      (symbolic stock: cumulative civic engagement)
    demand(t) = crisis_index_norm    (exogenous pressure: social crises)

  wvs_synthetic:
    O(t) = institutional_trust_norm  (organisational capacity)
    R(t) = 1 − inequality_index_norm (resilience: lower inequality = more resilient)
    I(t) = cultural_cohesion_norm    (integration: within-society value coherence)
    S(t) = norm_adoption_cumul       (symbolic stock: cumulative norm diffusion)
    demand(t) = social_stress_norm   (external pressure)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _robust_minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(x, 5), np.percentile(x, 95)
    if hi - lo < 1e-9:
        return np.zeros_like(x)
    return np.clip((x - lo) / (hi - lo), 0, 1)


def _cumsum_norm(x: np.ndarray) -> np.ndarray:
    cs = np.cumsum(x)
    mx = cs.max()
    return cs / mx if mx > 1e-9 else np.zeros_like(cs)


# ── Google Trends synthetic ───────────────────────────────────────────────────

def _generate_google_trends(n: int, seed: int) -> pd.DataFrame:
    """Simulate social trust / collective behaviour with:
    - Phase 1 (0 → n//3): stable civic society, moderate trust
    - Phase 2 (n//3 → 2n//3): crisis period — trust erodes, anxiety rises
    - Phase 3 (2n//3 → end): symbolic threshold — civic renewal self-reinforces

    This tests the symbolic canal: C(t) becomes auto-reinforcing when
    civic engagement crosses a threshold despite ongoing external stress.
    """
    rng = np.random.default_rng(seed)

    trust   = np.zeros(n)
    anxiety = np.zeros(n)
    civic   = np.zeros(n)
    crisis  = np.zeros(n)

    trust[0]   = 0.55
    anxiety[0] = 0.30
    civic[0]   = 0.40
    crisis[0]  = 0.20

    t_crisis = n // 3
    t_renewal = 2 * n // 3

    for t in range(1, n):
        if t < t_crisis:
            # Stable period
            trust[t]   = np.clip(trust[t-1]   + rng.normal(0.001, 0.015), 0.1, 0.9)
            anxiety[t] = np.clip(anxiety[t-1]  + rng.normal(-0.001, 0.015), 0.1, 0.9)
            civic[t]   = np.clip(civic[t-1]    + rng.normal(0.002, 0.012), 0.1, 0.9)
            crisis[t]  = np.clip(crisis[t-1]   + rng.normal(-0.001, 0.020), 0.05, 0.8)

        elif t < t_renewal:
            # Crisis: trust falls, anxiety rises, civic engagement declines
            crisis[t]  = np.clip(crisis[t-1]   + rng.normal(0.010, 0.025), 0.1, 1.0)
            trust[t]   = np.clip(trust[t-1]    - 0.008 * crisis[t] + rng.normal(0, 0.015), 0.05, 0.8)
            anxiety[t] = np.clip(anxiety[t-1]  + 0.012 * crisis[t] + rng.normal(0, 0.018), 0.1, 0.95)
            civic[t]   = np.clip(civic[t-1]    - 0.005 + rng.normal(0, 0.020), 0.05, 0.8)

        else:
            # Civic renewal: symbolic self-reinforcement
            progress = (t - t_renewal) / (n - t_renewal)
            # civic engagement drives trust recovery (symbolic loop)
            civic[t]   = np.clip(civic[t-1]    + 0.008 * progress + rng.normal(0, 0.012), 0.1, 0.9)
            trust[t]   = np.clip(trust[t-1]    + 0.006 * civic[t] + rng.normal(0, 0.012), 0.1, 0.9)
            anxiety[t] = np.clip(anxiety[t-1]  - 0.005 * progress + rng.normal(0, 0.012), 0.1, 0.8)
            crisis[t]  = np.clip(crisis[t-1]   - 0.003 + rng.normal(0, 0.015), 0.1, 0.9)

    O = _robust_minmax(trust)
    R = 1.0 - _robust_minmax(anxiety)
    # I: rolling corr trust × civic
    coh = np.zeros(n)
    w = 12
    for i in range(w, n):
        x, y = trust[i-w:i], civic[i-w:i]
        if x.std() > 1e-10 and y.std() > 1e-10:
            coh[i] = float(np.corrcoef(x, y)[0, 1])
    I = _robust_minmax(np.clip(coh, 0, None))

    civic_growth = np.clip(np.diff(civic, prepend=civic[0]), 0, None)
    S = _cumsum_norm(civic_growth)
    demand = _robust_minmax(crisis)

    return pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
    })


# ── WVS synthetic ─────────────────────────────────────────────────────────────

def _generate_wvs_synthetic(n: int, seed: int) -> pd.DataFrame:
    """Simulate WVS-calibrated norm diffusion over time.

    Models the spread of a new social norm (e.g., environmental values,
    democratic participation) across a society:
    - Phase 1 (0 → n//4): minority adoption, low integration
    - Phase 2 (n//4 → n//2): critical mass building — S(t) approaching threshold
    - Phase 3 (n//2 → 3n//4): threshold crossing — self-reinforcing diffusion
    - Phase 4 (3n//4 → end): consolidation or backlash test

    Calibrated to WVS Wave 4–7 typical inter-wave change rates.
    """
    rng = np.random.default_rng(seed)

    inst_trust = np.zeros(n)  # institutional trust [0,1]
    inequality = np.zeros(n)  # gini-like index [0,1]
    cohesion   = np.zeros(n)  # cultural cohesion [0,1]
    norm_adopt = np.zeros(n)  # norm adoption fraction [0,1]
    stress     = np.zeros(n)  # social stress [0,1]

    inst_trust[0] = 0.40
    inequality[0] = 0.35
    cohesion[0]   = 0.50
    norm_adopt[0] = 0.05
    stress[0]     = 0.30

    t_critical = n // 4
    t_threshold = n // 2
    t_consolidate = 3 * n // 4

    for t in range(1, n):
        if t < t_critical:
            # Early adopters — slow diffusion
            norm_adopt[t] = np.clip(norm_adopt[t-1] + 0.003 + rng.normal(0, 0.005), 0, 0.3)
            stress[t]     = np.clip(stress[t-1]     + rng.normal(0, 0.015), 0.1, 0.7)
            inst_trust[t] = np.clip(inst_trust[t-1] + rng.normal(0, 0.012), 0.2, 0.8)
            inequality[t] = np.clip(inequality[t-1] + rng.normal(0.001, 0.010), 0.15, 0.7)
            cohesion[t]   = np.clip(cohesion[t-1]   + rng.normal(-0.001, 0.012), 0.2, 0.8)

        elif t < t_threshold:
            # Critical mass: norm adoption accelerates via social proof
            adoption_accel = 0.01 * norm_adopt[t-1]  # social learning
            norm_adopt[t]  = np.clip(norm_adopt[t-1] + 0.006 + adoption_accel + rng.normal(0, 0.007), 0, 0.7)
            stress[t]      = np.clip(stress[t-1]     + rng.normal(0.002, 0.018), 0.1, 0.8)
            inst_trust[t]  = np.clip(inst_trust[t-1] + 0.003 * norm_adopt[t] + rng.normal(0, 0.010), 0.1, 0.9)
            inequality[t]  = np.clip(inequality[t-1] - 0.002 * norm_adopt[t] + rng.normal(0, 0.010), 0.1, 0.7)
            cohesion[t]    = np.clip(cohesion[t-1]   + 0.004 * norm_adopt[t] + rng.normal(0, 0.010), 0.2, 0.9)

        elif t < t_consolidate:
            # Self-reinforcing diffusion: symbolic threshold crossed
            adoption_accel = 0.02 * norm_adopt[t-1] * (1 - norm_adopt[t-1])  # logistic acceleration
            norm_adopt[t]  = np.clip(norm_adopt[t-1] + 0.012 + adoption_accel + rng.normal(0, 0.008), 0.1, 0.95)
            stress[t]      = np.clip(stress[t-1]     - 0.003 + rng.normal(0, 0.015), 0.05, 0.7)
            inst_trust[t]  = np.clip(inst_trust[t-1] + 0.005 + rng.normal(0, 0.010), 0.2, 0.95)
            inequality[t]  = np.clip(inequality[t-1] - 0.004 + rng.normal(0, 0.008), 0.05, 0.6)
            cohesion[t]    = np.clip(cohesion[t-1]   + 0.006 + rng.normal(0, 0.010), 0.3, 0.95)

        else:
            # Consolidation: norm institutionalised, stress test
            stress_shock = rng.uniform(0, 0.05)  # external shocks
            norm_adopt[t] = np.clip(norm_adopt[t-1] + rng.normal(0.001, 0.008), 0.5, 0.98)
            stress[t]     = np.clip(stress[t-1]     + stress_shock + rng.normal(-0.002, 0.015), 0.05, 0.6)
            inst_trust[t] = np.clip(inst_trust[t-1] + rng.normal(0.001, 0.010), 0.3, 0.95)
            inequality[t] = np.clip(inequality[t-1] + rng.normal(-0.001, 0.008), 0.05, 0.5)
            cohesion[t]   = np.clip(cohesion[t-1]   + rng.normal(0.001, 0.010), 0.4, 0.95)

    O = _robust_minmax(inst_trust)
    R = 1.0 - _robust_minmax(inequality)
    I = _robust_minmax(cohesion)

    # S: cumulative norm adoption momentum
    norm_growth = np.clip(np.diff(norm_adopt, prepend=norm_adopt[0]), 0, None)
    S = _cumsum_norm(norm_growth)

    demand = _robust_minmax(stress)

    return pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
    })


# ── proxy_spec.json ───────────────────────────────────────────────────────────

def _proxy_spec(dataset_id: str) -> dict:
    return {
        "dataset_id":   dataset_id,
        "spec_version": "2.1",
        "sector":       "psych",
        "time_column":  "t",
        "time_mode":    "index",
        "columns": [
            {
                "source_column": r,
                "oric_role": r,
                "oric_variable": r,
                "direction": "positive",
                "normalization": "robust_minmax",
                "missing_strategy": "linear_interp",
                "fragility_note": f"{r} psych proxy.",
                "manipulability_note": "Aggregated social indicator."
            }
            for r in ["O", "R", "I", "demand", "S"]
        ],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def generate(outdir: Path, seed: int, pilot_id: str, n: int = 240) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    if pilot_id == "google_trends":
        df = _generate_google_trends(n, seed)
        spec = _proxy_spec("sector_psych.pilot_google_trends.synth.v1")
    elif pilot_id == "wvs_synthetic":
        df = _generate_wvs_synthetic(n, seed)
        spec = _proxy_spec("sector_psych.pilot_wvs_synthetic.synth.v1")
    else:
        raise ValueError(f"Unknown pilot_id: {pilot_id!r}")

    df.to_csv(outdir / "real.csv", index=False)
    (outdir / "proxy_spec.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True,
                        choices=["google_trends", "wvs_synthetic"])
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n", type=int, default=240)
    args = parser.parse_args()
    generate(args.outdir, args.seed, args.pilot, args.n)
    print(f"Generated {args.n} rows for pilot={args.pilot} → {args.outdir}")
