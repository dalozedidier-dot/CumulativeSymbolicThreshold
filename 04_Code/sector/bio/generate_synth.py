"""generate_synth.py — Synthetic data generator for the Bio sector panel.

Three pilots, each producing a real.csv + proxy_spec.json:

  epidemic   : SIR-like epidemic with intervention → phase transition in C(t)
  geneexpr   : cellular stress response, heat-shock proteins → symbolic saturation
  ecology    : Lotka-Volterra with habitat perturbation → ecosystem collapse / recovery

Usage:
  python generate_synth.py --pilot epidemic --outdir 05_Results/bio_synth/epidemic --seed 42
  python generate_synth.py --pilot geneexpr --outdir 05_Results/bio_synth/geneexpr --seed 42
  python generate_synth.py --pilot ecology  --outdir 05_Results/bio_synth/ecology  --seed 42
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Epidemic (SIR-like)
# --------------------------------------------------------------------------- #
# ORI-C mapping:
#   O(t) = 1 − fatality_rate        (organisational capacity: case management quality)
#   R(t) = 1 − positivity_rate      (resilience: fraction of population still healthy)
#   I(t) = 1 / (Rt + eps)           (integration: how well interventions coordinate)
#   S(t) = vaccination_coverage     (symbolic stock: cumulated immune memory)
#   demand(t) = new_cases_norm      (environmental demand)
# --------------------------------------------------------------------------- #

def _generate_epidemic(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # SIR parameters
    beta0  = 0.25   # base transmission
    gamma  = 0.07   # recovery rate
    N_pop  = 1_000_000

    # Initial conditions
    I0 = 500 / N_pop
    S0 = 1.0 - I0
    R0 = 0.0

    S_comp = np.zeros(n)
    I_comp = np.zeros(n)
    R_comp = np.zeros(n)
    S_comp[0], I_comp[0], R_comp[0] = S0, I0, R0

    intervention_t = n // 3          # lockdown / intervention onset
    vaccine_t      = n // 2          # vaccination programme onset
    vacc_rate      = 0.004           # daily vaccination fraction

    vaccination_coverage = np.zeros(n)
    Rt_series = np.zeros(n)

    for t in range(1, n):
        # Effective beta with intervention
        if t < intervention_t:
            beta = beta0
        elif t < vaccine_t:
            beta = beta0 * 0.45   # NPI effect
        else:
            beta = beta0 * 0.30   # NPI + vaccine

        # SIR step (Euler)
        ds = -beta * S_comp[t-1] * I_comp[t-1]
        di =  beta * S_comp[t-1] * I_comp[t-1] - gamma * I_comp[t-1]
        dr =  gamma * I_comp[t-1]

        S_comp[t] = np.clip(S_comp[t-1] + ds + rng.normal(0, 2e-5), 0, 1)
        I_comp[t] = np.clip(I_comp[t-1] + di + rng.normal(0, 2e-5), 0, 1)
        R_comp[t] = np.clip(R_comp[t-1] + dr + rng.normal(0, 1e-5), 0, 1)

        Rt_series[t] = max(beta * S_comp[t] / gamma, 0)
        vaccination_coverage[t] = min(
            vaccination_coverage[t-1] + (vacc_rate if t >= vaccine_t else 0), 1.0
        )

    # Fatality rate (proxy for case management quality degradation)
    base_cfr = 0.012
    fatality_rate = np.clip(
        base_cfr * (1 + 3 * I_comp / I_comp.max() + rng.normal(0, 0.001, n)), 0, 1
    )

    positivity_rate = np.clip(I_comp * 8 + rng.normal(0, 0.01, n), 0, 1)
    new_cases = np.maximum(np.diff(R_comp, prepend=R_comp[0]) * N_pop, 0)

    def norm01(x: np.ndarray) -> np.ndarray:
        lo, hi = x.min(), x.max()
        return (x - lo) / (hi - lo + 1e-12)

    df = pd.DataFrame({
        "t":                    np.arange(n),
        "O":                    norm01(1.0 - fatality_rate),
        "R":                    norm01(1.0 - positivity_rate),
        "I":                    norm01(1.0 / (Rt_series + 0.1)),
        "S":                    vaccination_coverage,
        "demand":               norm01(new_cases),
        "Rt":                   Rt_series,
        "fatality_rate":        fatality_rate,
        "positivity_rate":      positivity_rate,
        "vaccination_coverage": vaccination_coverage,
        "new_cases_norm":       norm01(new_cases),
    })
    return df


_PROXY_SPEC_EPIDEMIC = {
    "dataset_id":    "bio_epidemic_synth",
    "sector":        "bio",
    "pilot":         "epidemic",
    "spec_version":  "1.0",
    "data_type":     "synthetic",
    "time_column":   "t",
    "time_mode":     "index",
    "normalization": "already_normalized",
    "columns": [
        {
            "oric_role":           "O",
            "source_column":       "O",
            "direction":           "positive",
            "fragility_score":     0.3,
            "fragility_note":      "Fatality rate can be under-reported in early epidemic phase",
            "manipulability_note": "Sensitive to case ascertainment policy changes",
            "description":         "1 − fatality_rate: organisational capacity to manage cases",
        },
        {
            "oric_role":           "R",
            "source_column":       "R",
            "direction":           "positive",
            "fragility_score":     0.4,
            "fragility_note":      "Positivity rate depends on test availability",
            "manipulability_note": "Can be artificially lowered by testing strategy changes",
            "description":         "1 − positivity_rate: system resilience (fraction non-infected)",
        },
        {
            "oric_role":           "I",
            "source_column":       "I",
            "direction":           "positive",
            "fragility_score":     0.35,
            "fragility_note":      "Rt estimation has model-specific uncertainty",
            "manipulability_note": "Rt can be affected by reporting delays",
            "description":         "1 / (Rt + ε): intervention integration (lower Rt = more coherent)",
        },
        {
            "oric_role":           "S",
            "source_column":       "S",
            "direction":           "positive",
            "fragility_score":     0.25,
            "fragility_note":      "Vaccination coverage assumes homogeneous uptake",
            "manipulability_note": "Coverage data can be delayed; does not capture waning immunity",
            "description":         "vaccination_coverage: cumulative symbolic stock (immune memory)",
        },
        {
            "oric_role":           "demand",
            "source_column":       "demand",
            "direction":           "positive",
            "fragility_score":     0.2,
            "fragility_note":      "New cases under-reported in high-incidence periods",
            "manipulability_note": "Reporting changes can create spurious demand spikes",
            "description":         "new_cases_norm: environmental demand on health system",
        },
    ],
}


# --------------------------------------------------------------------------- #
# Gene expression / cellular stress
# --------------------------------------------------------------------------- #
# ORI-C mapping:
#   O(t) = cell_viability          (organisation: fraction of viable cells)
#   R(t) = hsp_level               (resilience: heat-shock protein expression)
#   I(t) = transcription_coherence (integration: co-expression index)
#   S(t) = chaperone_density       (symbolic stock: cumulative molecular memory)
#   demand(t) = stress_intensity   (thermal/oxidative stress load)
# --------------------------------------------------------------------------- #

def _generate_geneexpr(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    stress_onset = n // 4
    recovery_t   = 3 * n // 4

    t_arr = np.arange(n)
    stress_intensity = np.zeros(n)
    stress_intensity[stress_onset:recovery_t] = np.linspace(0, 1, recovery_t - stress_onset)
    # Sharp stress peak then partial recovery
    stress_intensity[recovery_t:] = 0.35
    stress_intensity += rng.normal(0, 0.02, n)
    stress_intensity = np.clip(stress_intensity, 0, 1)

    # Cell viability degrades under stress, partial recovery
    cell_viability = np.zeros(n)
    cell_viability[0] = 0.97
    for t in range(1, n):
        degrade = 0.012 * stress_intensity[t]
        recover = 0.006 * (1 - stress_intensity[t]) * (1 - cell_viability[t-1])
        cell_viability[t] = np.clip(
            cell_viability[t-1] - degrade + recover + rng.normal(0, 0.003), 0, 1
        )

    # HSP level (resilience marker) peaks during stress
    hsp_base = 0.1
    hsp = hsp_base + 0.7 * stress_intensity + rng.normal(0, 0.03, n)
    hsp = np.clip(hsp, 0, 1)

    # Transcription coherence (integration): high at baseline, drops under severe stress
    coherence = np.zeros(n)
    coherence[0] = 0.85
    for t in range(1, n):
        drop = 0.015 * max(stress_intensity[t] - 0.5, 0)
        restore = 0.008 * (0.85 - coherence[t-1]) * (1 - stress_intensity[t])
        coherence[t] = np.clip(coherence[t-1] - drop + restore + rng.normal(0, 0.01), 0, 1)

    # Chaperone density (symbolic stock): cumulative, persistent
    chaperone = np.zeros(n)
    for t in range(1, n):
        induction = 0.03 * stress_intensity[t]
        decay     = 0.005 * chaperone[t-1]
        chaperone[t] = np.clip(chaperone[t-1] + induction - decay + rng.normal(0, 0.005), 0, 1)

    def norm01(x): lo, hi = x.min(), x.max(); return (x - lo) / (hi - lo + 1e-12)

    df = pd.DataFrame({
        "t":                    t_arr,
        "O":                    norm01(cell_viability),
        "R":                    norm01(hsp),
        "I":                    norm01(coherence),
        "S":                    norm01(chaperone),
        "demand":               norm01(stress_intensity),
        "cell_viability_raw":   cell_viability,
        "hsp_level_raw":        hsp,
        "coherence_raw":        coherence,
        "chaperone_density_raw": chaperone,
        "stress_intensity_raw": stress_intensity,
    })
    return df


_PROXY_SPEC_GENEEXPR = {
    "dataset_id":    "bio_geneexpr_synth",
    "sector":        "bio",
    "pilot":         "geneexpr",
    "spec_version":  "1.0",
    "data_type":     "synthetic",
    "time_column":   "t",
    "time_mode":     "index",
    "normalization": "already_normalized",
    "columns": [
        {
            "oric_role":           "O",
            "source_column":       "O",
            "direction":           "positive",
            "fragility_score":     0.40,
            "fragility_note":      "Viability assays vary across labs; trypan blue vs flow cytometry",
            "manipulability_note": "Depends on measurement protocol and cell line",
            "description":         "cell_viability: fraction of viable cells (organisation)",
        },
        {
            "oric_role":           "R",
            "source_column":       "R",
            "direction":           "positive",
            "fragility_score":     0.45,
            "fragility_note":      "HSP70 expression is stress-specific; may not generalise across stressors",
            "manipulability_note": "Basal HSP levels vary with passage number and culture conditions",
            "description":         "hsp_level: heat-shock protein expression (resilience response)",
        },
        {
            "oric_role":           "I",
            "source_column":       "I",
            "direction":           "positive",
            "fragility_score":     0.55,
            "fragility_note":      "Co-expression index depends on gene set selection",
            "manipulability_note": "Normalisation method strongly affects co-expression values",
            "description":         "transcription_coherence: gene co-expression index (integration)",
        },
        {
            "oric_role":           "S",
            "source_column":       "S",
            "direction":           "positive",
            "fragility_score":     0.35,
            "fragility_note":      "Chaperone density measured by proteomics; batch effects possible",
            "manipulability_note": "Protein turnover rates vary; absolute levels may drift",
            "description":         "chaperone_density: cumulative molecular memory (symbolic stock)",
        },
        {
            "oric_role":           "demand",
            "source_column":       "demand",
            "direction":           "positive",
            "fragility_score":     0.30,
            "fragility_note":      "Stress intensity requires calibration to specific stressor type",
            "manipulability_note": "Temperature/ROS measurements must be spatially consistent",
            "description":         "stress_intensity: thermal or oxidative stress load (demand)",
        },
    ],
}


# --------------------------------------------------------------------------- #
# Ecology: Lotka-Volterra with perturbation
# --------------------------------------------------------------------------- #
# ORI-C mapping:
#   O(t) = prey_norm               (organisation: food-web base)
#   R(t) = lv_stability_index      (resilience: prey/pred ratio stability)
#   I(t) = habitat_connectivity    (integration: spatial coherence)
#   S(t) = biodiversity_index      (symbolic stock: species richness, cumulative)
#   demand(t) = perturbation_norm  (habitat loss / disturbance)
# --------------------------------------------------------------------------- #

def _generate_ecology(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # Lotka-Volterra parameters
    alpha = 0.6    # prey growth
    beta  = 0.05   # predation rate
    delta = 0.025  # predator efficiency
    gamma = 0.4    # predator death

    x = np.zeros(n)   # prey
    y = np.zeros(n)   # predator
    x[0], y[0] = 10.0, 2.0

    perturb_t = n // 2
    for t in range(1, n):
        habitat_loss = 0.08 if t >= perturb_t else 0.0
        dx = alpha * x[t-1] - beta * x[t-1] * y[t-1] - habitat_loss * x[t-1]
        dy = delta * x[t-1] * y[t-1] - gamma * y[t-1]
        x[t] = max(x[t-1] + 0.01 * dx + rng.normal(0, 0.05), 0.01)
        y[t] = max(y[t-1] + 0.01 * dy + rng.normal(0, 0.02), 0.01)

    # Derived proxies
    prey_norm = x / (x.max() + 1e-9)
    pred_norm = y / (y.max() + 1e-9)

    # Stability index: inverse of coefficient of variation over rolling window
    stability = np.zeros(n)
    W = 15
    for t in range(W, n):
        window = x[t-W:t]
        cv = window.std() / (window.mean() + 1e-9)
        stability[t] = 1.0 / (1.0 + cv)
    stability[:W] = stability[W]

    # Habitat connectivity: decreases linearly after perturbation
    connectivity = np.ones(n)
    connectivity[perturb_t:] = np.linspace(1.0, 0.4, n - perturb_t)
    connectivity += rng.normal(0, 0.02, n)
    connectivity = np.clip(connectivity, 0, 1)

    # Biodiversity (symbolic stock): cumulative, persistent, degrades slowly post-collapse
    biodiversity = np.zeros(n)
    biodiversity[0] = 0.85
    for t in range(1, n):
        gain  = 0.002 * prey_norm[t] * connectivity[t]
        loss  = 0.005 * (1 - connectivity[t])
        biodiversity[t] = np.clip(biodiversity[t-1] + gain - loss + rng.normal(0, 0.003), 0, 1)

    # Perturbation signal
    perturbation = np.zeros(n)
    perturbation[perturb_t:] = np.linspace(0, 0.9, n - perturb_t) + rng.normal(0, 0.02, n - perturb_t)
    perturbation = np.clip(perturbation, 0, 1)

    def norm01(x): lo, hi = x.min(), x.max(); return (x - lo) / (hi - lo + 1e-12)

    df = pd.DataFrame({
        "t":              np.arange(n),
        "O":              norm01(prey_norm),
        "R":              norm01(stability),
        "I":              norm01(connectivity),
        "S":              norm01(biodiversity),
        "demand":         norm01(perturbation),
        "prey_raw":       x,
        "predator_raw":   y,
        "connectivity_raw": connectivity,
        "biodiversity_raw": biodiversity,
        "perturbation_raw": perturbation,
    })
    return df


_PROXY_SPEC_ECOLOGY = {
    "dataset_id":    "bio_ecology_synth",
    "sector":        "bio",
    "pilot":         "ecology",
    "spec_version":  "1.0",
    "data_type":     "synthetic",
    "time_column":   "t",
    "time_mode":     "index",
    "normalization": "already_normalized",
    "columns": [
        {
            "oric_role":           "O",
            "source_column":       "O",
            "direction":           "positive",
            "fragility_score":     0.35,
            "fragility_note":      "Prey count depends on survey method and spatial scale",
            "manipulability_note": "Abundance estimates have observation error; seasonal bias",
            "description":         "prey_norm: prey density (food-web organisation)",
        },
        {
            "oric_role":           "R",
            "source_column":       "R",
            "direction":           "positive",
            "fragility_score":     0.40,
            "fragility_note":      "Stability index is rolling-window sensitive",
            "manipulability_note": "Window choice affects index level",
            "description":         "lv_stability_index: inverse CV of prey (resilience)",
        },
        {
            "oric_role":           "I",
            "source_column":       "I",
            "direction":           "positive",
            "fragility_score":     0.50,
            "fragility_note":      "Connectivity indices are highly model-dependent",
            "manipulability_note": "Landscape fragmentation measures require spatial data",
            "description":         "habitat_connectivity: spatial coherence of the ecosystem (integration)",
        },
        {
            "oric_role":           "S",
            "source_column":       "S",
            "direction":           "positive",
            "fragility_score":     0.45,
            "fragility_note":      "Species richness underestimates true diversity; incomplete surveys",
            "manipulability_note": "Survey effort must be consistent across time points",
            "description":         "biodiversity_index: species richness / Shannon entropy (symbolic stock)",
        },
        {
            "oric_role":           "demand",
            "source_column":       "demand",
            "direction":           "positive",
            "fragility_score":     0.35,
            "fragility_note":      "Perturbation intensity is difficult to quantify precisely",
            "manipulability_note": "Composite perturbation index; weighting of components is subjective",
            "description":         "perturbation_norm: habitat loss / disturbance intensity (demand)",
        },
    ],
}


# --------------------------------------------------------------------------- #
# Dispatch and CLI
# --------------------------------------------------------------------------- #

_PILOTS = {
    "epidemic": (_generate_epidemic, _PROXY_SPEC_EPIDEMIC),
    "geneexpr": (_generate_geneexpr, _PROXY_SPEC_GENEEXPR),
    "ecology":  (_generate_ecology,  _PROXY_SPEC_ECOLOGY),
}


def generate(outdir: Path, seed: int, pilot_id: str, n: int = 250) -> None:
    """Public entry point called by sector_panel_runner."""
    outdir.mkdir(parents=True, exist_ok=True)
    if pilot_id not in _PILOTS:
        raise ValueError(f"Unknown pilot: '{pilot_id}'. Choose from {list(_PILOTS)}")
    gen_fn, spec = _PILOTS[pilot_id]
    df = gen_fn(n, seed)
    df.to_csv(outdir / "real.csv", index=False)
    with open(outdir / "proxy_spec.json", "w") as f:
        json.dump(spec, f, indent=2)
    print(f"[bio/generate_synth] pilot={pilot_id} → {outdir}  ({len(df)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate bio sector synthetic data")
    parser.add_argument("--pilot",  choices=list(_PILOTS), default="epidemic")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed",   type=int, default=42)
    parser.add_argument("--n",      type=int, default=250, help="Number of time steps")
    args = parser.parse_args()
    generate(Path(args.outdir), args.seed, args.pilot, args.n)


if __name__ == "__main__":
    main()
main
