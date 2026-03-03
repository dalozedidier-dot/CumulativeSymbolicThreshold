"""generate_synth.py — Synthetic data generator for the AI/Tech sector panel.

Two pilots:

  mlperf      : AI training efficiency over time (hardware + algorithmic progress)
  llm_scaling : LLM emergent capability scaling (Chinchilla/GPT-law calibrated)

ORI-C mappings:

  mlperf:
    O(t) = hardware_efficiency_norm    (organisation: compute efficiency)
    R(t) = reproducibility_norm        (resilience: benchmark reproducibility)
    I(t) = cross_arch_coherence_norm   (integration: hardware ecosystem alignment)
    S(t) = cumulative_efficiency_gain  (symbolic stock: algorithmic progress)
    demand(t) = compute_cost_norm      (external pressure: energy/compute cost)

  llm_scaling:
    O(t) = capability_breadth_norm     (organisation: tasks solved)
    R(t) = 1 − failure_rate_norm       (resilience: inverse failure rate)
    I(t) = benchmark_coherence_norm    (integration: cross-benchmark coherence)
    S(t) = cumulative_emergence_norm   (symbolic stock: emergent abilities)
    demand(t) = param_count_norm       (scaling pressure = exogenous driver)
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


# ── MLPerf synthetic ──────────────────────────────────────────────────────────

def _generate_mlperf(n: int, seed: int) -> pd.DataFrame:
    """Simulate AI training efficiency benchmark trajectory.

    Phase 1 (0 → n//3): hardware scaling — efficiency improves with compute
    Phase 2 (n//3 → 2n//3): algorithmic innovation — step-change improvements
    Phase 3 (2n//3 → end): integration phase — efficiency self-reinforcing across
                            hardware/software ecosystem (symbolic threshold test)

    Calibrated to MLPerf ImageNet results 2018–2024:
    - Training time ~halved every ~2 years (Moore-like)
    - Step-changes from algorithmic innovations (mixed precision, FlashAttention)
    """
    rng = np.random.default_rng(seed)

    # Training time to target accuracy (normalised, lower = better)
    # We invert to O = 1/training_time → higher = more efficient
    train_time = np.zeros(n)
    train_time[0] = 10.0  # baseline (hours, arbitrary units)

    t_algo = n // 3
    t_synergy = 2 * n // 3

    for t in range(1, n):
        if t < t_algo:
            # Hardware scaling: ~2% monthly improvement
            reduction = 0.02 + rng.normal(0, 0.005)
            train_time[t] = max(train_time[t-1] * (1 - reduction), 0.1)
        elif t < t_synergy:
            # Algorithmic innovations: step-changes + continued hardware
            step_change = 0.05 if rng.random() < 0.15 else 0.0  # 15% chance of breakthrough
            reduction = 0.025 + step_change + rng.normal(0, 0.006)
            train_time[t] = max(train_time[t-1] * (1 - reduction), 0.01)
        else:
            # Synergetic phase: hardware × software co-optimisation
            # efficiency gains accelerate (auto-reinforcing symbolic canal)
            progress = (t - t_synergy) / (n - t_synergy)
            reduction = 0.03 + 0.02 * progress + rng.normal(0, 0.006)
            if rng.random() < 0.25:  # more frequent breakthroughs
                reduction += 0.08
            train_time[t] = max(train_time[t-1] * (1 - reduction), 0.001)

    efficiency = 1.0 / (train_time + 1e-6)  # higher = more efficient

    # ── O: normalised efficiency ──────────────────────────────────────────────
    O = _robust_minmax(np.log1p(efficiency))

    # ── R: reproducibility proxy (rolling stability of efficiency gains) ──────
    log_eff = np.log1p(efficiency)
    gains = np.diff(log_eff, prepend=log_eff[0])
    roll_cv = (pd.Series(gains).rolling(12, min_periods=3).std() /
               (pd.Series(gains).rolling(12, min_periods=3).mean().abs() + 1e-9)).fillna(1.0).to_numpy()
    R = 1.0 - _robust_minmax(np.clip(roll_cv, 0, None))

    # ── I: cross-architecture coherence (simulated: multiple hardware lines) ──
    # Simulate GPU vs TPU efficiency ratio (ideally converges when ecosystems integrate)
    gpu_eff = efficiency * (1 + 0.1 * rng.normal(0, 1, n))
    tpu_eff = efficiency * (1 + 0.1 * rng.normal(0, 1, n))
    corr_win = np.zeros(n)
    w = 12
    for i in range(w, n):
        x, y = np.log1p(gpu_eff[i-w:i]), np.log1p(tpu_eff[i-w:i])
        if x.std() > 1e-10 and y.std() > 1e-10:
            corr_win[i] = float(np.corrcoef(x, y)[0, 1])
    I = _robust_minmax(np.clip(corr_win, 0, None))

    # ── S: cumulative algorithmic progress stock ───────────────────────────────
    progress_steps = np.clip(gains, 0, None)
    S = _cumsum_norm(progress_steps)

    # ── demand: compute cost pressure (inverse efficiency = cost proxy) ────────
    demand = _robust_minmax(np.log1p(train_time))

    return pd.DataFrame({
        "t":      np.arange(n),
        "O":      np.clip(O, 0, 1),
        "R":      np.clip(R, 0, 1),
        "I":      np.clip(I, 0, 1),
        "S":      np.clip(S, 0, 1),
        "demand": np.clip(demand, 0, 1),
    })


# ── LLM Scaling synthetic ──────────────────────────────────────────────────────

def _generate_llm_scaling(n: int, seed: int) -> pd.DataFrame:
    """Simulate LLM capability scaling with emergent ability threshold.

    Calibrated to published scaling laws:
    - Chinchilla (Hoffmann et al. 2022): compute-optimal scaling
    - GPT-3/4 (Brown et al. 2020, OpenAI 2023): emergent abilities

    Phase 1 (0 → n//3): sub-critical scaling — smooth capability improvement
    Phase 2 (n//3 → 2n//3): approaching threshold — S(t) auto-reinforcing
    Phase 3 (2n//3 → end): emergent regime — step-change in integration

    The symbolic threshold test: C(t) becomes self-reinforcing at the
    point where 'emergent abilities' appear (as documented in Wei et al. 2022).
    """
    rng = np.random.default_rng(seed)

    # Benchmark scores (0-100 normalised)
    # Representing MMLU / HellaSwag / BigBench-style aggregate
    capability = np.zeros(n)
    capability[0] = 25.0  # random baseline

    failure_rate  = np.zeros(n)
    failure_rate[0] = 0.75  # high failure rate at small scale

    # Number of benchmarks solved (capability breadth)
    tasks_solved = np.zeros(n)
    tasks_solved[0] = 3.0  # out of 100

    # Model parameter count proxy (log-scale, billions)
    log_params = np.linspace(8, 14, n)  # 3M → 1B parameters over series

    t_thresh = n // 3
    t_emerge = 2 * n // 3

    for t in range(1, n):
        # Scale-driven improvement (power law)
        scale_gain = 0.02 * (log_params[t] - log_params[t-1])

        if t < t_thresh:
            # Pre-threshold: smooth but slow improvement
            capability[t]   = min(capability[t-1] + scale_gain * 100 + rng.normal(0, 0.5), 100)
            failure_rate[t] = max(failure_rate[t-1] - 0.005 + rng.normal(0, 0.008), 0.1)
            tasks_solved[t] = min(tasks_solved[t-1] + 0.05 + rng.normal(0, 0.1), 30)

        elif t < t_emerge:
            # Approaching threshold: capability accelerates, integration grows
            capability[t]   = min(capability[t-1] + scale_gain * 200 + rng.normal(0, 0.8), 100)
            failure_rate[t] = max(failure_rate[t-1] - 0.012 + rng.normal(0, 0.008), 0.05)
            # Occasional emergent ability spikes
            emergence_spike = 5.0 if rng.random() < 0.15 else 0.0
            tasks_solved[t] = min(tasks_solved[t-1] + 0.3 + emergence_spike + rng.normal(0, 0.2), 80)

        else:
            # Post-threshold: self-reinforcing emergent capabilities
            # Integration of capabilities creates new capabilities (symbolic loop)
            synergy = 0.01 * tasks_solved[t-1] / 100.0
            capability[t]   = min(capability[t-1] + (scale_gain + synergy) * 200 + rng.normal(0, 0.5), 100)
            failure_rate[t] = max(failure_rate[t-1] - 0.015 + rng.normal(0, 0.006), 0.01)
            tasks_solved[t] = min(tasks_solved[t-1] + 0.8 + synergy * 10 + rng.normal(0, 0.3), 100)

    # ── O: capability breadth (fraction of benchmark tasks solved) ────────────
    O = _robust_minmax(tasks_solved)

    # ── R: 1 − failure rate ────────────────────────────────────────────────────
    R = 1.0 - _robust_minmax(failure_rate)

    # ── I: cross-benchmark coherence (rolling corr capability × tasks_solved) ─
    coh = np.zeros(n)
    w = 10
    for i in range(w, n):
        x, y = capability[i-w:i], tasks_solved[i-w:i]
        if x.std() > 1e-10 and y.std() > 1e-10:
            coh[i] = float(np.corrcoef(x, y)[0, 1])
    I = _robust_minmax(np.clip(coh, 0, None))

    # ── S: cumulative emergent abilities stock ─────────────────────────────────
    task_gains = np.clip(np.diff(tasks_solved, prepend=tasks_solved[0]), 0, None)
    S = _cumsum_norm(task_gains)

    # ── demand: parameter count (scaling pressure) ────────────────────────────
    demand = _robust_minmax(log_params)

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
        "sector":       "ai_tech",
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
                "fragility_note": f"{r} AI/Tech proxy.",
                "manipulability_note": "Benchmark or scaling law data."
            }
            for r in ["O", "R", "I", "demand", "S"]
        ],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def generate(outdir: Path, seed: int, pilot_id: str, n: int = 80) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    if pilot_id == "mlperf":
        df = _generate_mlperf(n, seed)
        spec = _proxy_spec("sector_ai_tech.pilot_mlperf.synth.v1")
    elif pilot_id == "llm_scaling":
        df = _generate_llm_scaling(n, seed)
        spec = _proxy_spec("sector_ai_tech.pilot_llm_scaling.synth.v1")
    else:
        raise ValueError(f"Unknown pilot_id: {pilot_id!r}")

    df.to_csv(outdir / "real.csv", index=False)
    (outdir / "proxy_spec.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True, choices=["mlperf", "llm_scaling"])
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n", type=int, default=80)
    args = parser.parse_args()
    generate(args.outdir, args.seed, args.pilot, args.n)
    print(f"Generated {args.n} rows for pilot={args.pilot} → {args.outdir}")
