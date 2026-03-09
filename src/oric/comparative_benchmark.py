"""comparative_benchmark.py — Compare ORI-C against baseline methods.

Runs four competing approaches on the same pilot data:
1. Changepoint detection (CUSUM-based)
2. Structural break test (Chow-like F-statistic)
3. Anomaly / novelty detection (rolling z-score)
4. Early warning signal (increasing variance + autocorrelation)

The goal is NOT to "win everywhere" but to situate ORI-C:
- Where it is better
- Where it is complementary
- Where it is more demanding but cleaner
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats


# ── Method results ─────────────────────────────────────────────────────────

MethodName = Literal[
    "oric", "cusum_changepoint", "structural_break", "anomaly_zscore", "early_warning"
]


@dataclass
class MethodResult:
    """Result from a single detection method on one dataset."""
    method: MethodName
    detected: bool
    detection_point: int | None = None
    statistic: float | None = None
    p_value: float | None = None
    confidence: str = ""  # high, medium, low
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkComparison:
    """Full comparison of ORI-C vs baselines on one pilot."""
    pilot_id: str
    series_length: int
    methods: list[MethodResult] = field(default_factory=list)
    oric_advantage: str = ""
    oric_limitation: str = ""
    complementarity_notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["methods"] = [m.to_dict() for m in self.methods]
        return d


# ── Baseline methods ──────────────────────────────────────────────────────

def cusum_changepoint(series: np.ndarray) -> MethodResult:
    """CUSUM-based changepoint detection.

    Detects shift in mean using cumulative sum of deviations.
    """
    n = len(series)
    if n < 10:
        return MethodResult(
            method="cusum_changepoint", detected=False,
            notes="Series too short",
        )

    mean = np.mean(series)
    cumsum = np.cumsum(series - mean)
    S_diff = np.max(cumsum) - np.min(cumsum)

    # Bootstrap null distribution (simplified)
    rng = np.random.default_rng(42)
    n_boot = 200
    null_stats = np.zeros(n_boot)
    for i in range(n_boot):
        perm = rng.permutation(series)
        cs = np.cumsum(perm - mean)
        null_stats[i] = np.max(cs) - np.min(cs)

    p_value = float(np.mean(null_stats >= S_diff))
    detected = p_value < 0.05
    detection_point = int(np.argmax(cumsum)) if detected else None

    return MethodResult(
        method="cusum_changepoint",
        detected=detected,
        detection_point=detection_point,
        statistic=float(S_diff),
        p_value=p_value,
        confidence="high" if p_value < 0.01 else ("medium" if p_value < 0.05 else "low"),
    )


def structural_break(series: np.ndarray) -> MethodResult:
    """Chow-like structural break test.

    Tests all candidate breakpoints and returns the one with
    the highest F-statistic for a difference in means.
    """
    n = len(series)
    min_seg = max(10, n // 10)

    if n < 2 * min_seg:
        return MethodResult(
            method="structural_break", detected=False,
            notes="Series too short for structural break test",
        )

    best_f = 0.0
    best_t = -1

    for t in range(min_seg, n - min_seg):
        pre = series[:t]
        post = series[t:]
        stat_val, p = stats.ttest_ind(pre, post, equal_var=False)
        f = stat_val ** 2
        if f > best_f:
            best_f = f
            best_t = t

    # Use Bonferroni-corrected significance
    n_tests = n - 2 * min_seg
    if n_tests <= 0:
        return MethodResult(
            method="structural_break", detected=False,
            notes="Not enough candidate breakpoints",
        )

    # Get p-value at best breakpoint
    pre = series[:best_t]
    post = series[best_t:]
    _, p_raw = stats.ttest_ind(pre, post, equal_var=False)
    p_corrected = min(float(p_raw) * n_tests, 1.0)

    return MethodResult(
        method="structural_break",
        detected=p_corrected < 0.05,
        detection_point=int(best_t),
        statistic=float(best_f),
        p_value=p_corrected,
        confidence="high" if p_corrected < 0.01 else (
            "medium" if p_corrected < 0.05 else "low"
        ),
    )


def anomaly_zscore(series: np.ndarray, window: int = 20) -> MethodResult:
    """Rolling z-score anomaly detection.

    Flags points where the z-score relative to a rolling window
    exceeds a threshold.
    """
    n = len(series)
    if n < window + 5:
        return MethodResult(
            method="anomaly_zscore", detected=False,
            notes="Series too short for rolling z-score",
        )

    zscores = np.zeros(n)
    for i in range(window, n):
        w = series[i - window:i]
        mu = np.mean(w)
        sigma = np.std(w)
        if sigma > 1e-10:
            zscores[i] = abs((series[i] - mu) / sigma)

    max_z = float(np.max(zscores))
    max_idx = int(np.argmax(zscores))

    # Threshold: z > 3 is anomalous
    detected = max_z > 3.0
    n_anomalous = int(np.sum(zscores > 3.0))

    return MethodResult(
        method="anomaly_zscore",
        detected=detected,
        detection_point=max_idx if detected else None,
        statistic=max_z,
        p_value=None,
        confidence="high" if max_z > 4.0 else ("medium" if max_z > 3.0 else "low"),
        notes=f"n_anomalous_points={n_anomalous}, window={window}",
    )


def early_warning_signal(series: np.ndarray, window: int = 20) -> MethodResult:
    """Early warning signal: increasing variance + autocorrelation.

    Classical critical slowing down indicators:
    - Rising variance in rolling window
    - Rising lag-1 autocorrelation
    """
    n = len(series)
    if n < 2 * window:
        return MethodResult(
            method="early_warning", detected=False,
            notes="Series too short for EWS analysis",
        )

    # Rolling variance
    variances = []
    autocorrs = []
    for i in range(window, n):
        w = series[i - window:i]
        variances.append(np.var(w))
        if len(w) > 1:
            ac = np.corrcoef(w[:-1], w[1:])[0, 1] if np.std(w) > 1e-10 else 0.0
            autocorrs.append(ac)
        else:
            autocorrs.append(0.0)

    variances = np.array(variances)
    autocorrs = np.array(autocorrs)

    # Kendall tau for trend detection
    t_idx = np.arange(len(variances))
    tau_var, p_var = stats.kendalltau(t_idx, variances)
    tau_ac, p_ac = stats.kendalltau(t_idx, autocorrs)

    # EWS detected if both variance and autocorrelation show positive trend
    ews_detected = (tau_var > 0.1 and p_var < 0.05) or (tau_ac > 0.1 and p_ac < 0.05)

    # Find approximate transition point (max variance increase rate)
    if len(variances) > 1:
        var_diff = np.diff(variances)
        detection_point = int(np.argmax(var_diff) + window)
    else:
        detection_point = None

    return MethodResult(
        method="early_warning",
        detected=ews_detected,
        detection_point=detection_point if ews_detected else None,
        statistic=float(tau_var),
        p_value=float(p_var),
        confidence="high" if (tau_var > 0.3 and p_var < 0.01) else (
            "medium" if ews_detected else "low"
        ),
        notes=f"tau_variance={tau_var:.3f}(p={p_var:.3f}), tau_autocorr={tau_ac:.3f}(p={p_ac:.3f})",
    )


# ── Benchmark runner ──────────────────────────────────────────────────────

def run_benchmark_on_series(
    pilot_id: str,
    series: np.ndarray,
    oric_verdict: str = "UNKNOWN",
    oric_detection_point: int | None = None,
) -> BenchmarkComparison:
    """Run all baseline methods and compare with ORI-C verdict."""
    n = len(series)

    # ORI-C result (from existing pipeline)
    oric_result = MethodResult(
        method="oric",
        detected=oric_verdict == "ACCEPT",
        detection_point=oric_detection_point,
        confidence="high" if oric_verdict == "ACCEPT" else "low",
        notes=f"verdict={oric_verdict}",
    )

    # Run baselines
    cusum = cusum_changepoint(series)
    sb = structural_break(series)
    anom = anomaly_zscore(series)
    ews = early_warning_signal(series)

    methods = [oric_result, cusum, sb, anom, ews]
    n_detected = sum(1 for m in methods if m.detected)
    baseline_detected = sum(1 for m in methods[1:] if m.detected)

    # Comparative analysis
    if oric_result.detected and baseline_detected == 0:
        advantage = "ORI-C detects signal missed by all baselines"
        limitation = ""
    elif oric_result.detected and baseline_detected > 0:
        advantage = f"ORI-C agrees with {baseline_detected}/4 baselines"
        limitation = ""
    elif not oric_result.detected and baseline_detected > 0:
        advantage = ""
        limitation = f"Baselines detect ({baseline_detected}/4) but ORI-C does not (possible underpowered or false positive in baselines)"
    else:
        advantage = ""
        limitation = "No method detects a clear signal"

    comp_notes = []
    if cusum.detected and not oric_result.detected:
        comp_notes.append("CUSUM is less conservative but may have higher false positive rate")
    if ews.detected:
        comp_notes.append("EWS provides complementary pre-transition warning")

    return BenchmarkComparison(
        pilot_id=pilot_id,
        series_length=n,
        methods=methods,
        oric_advantage=advantage,
        oric_limitation=limitation,
        complementarity_notes="; ".join(comp_notes),
    )


def run_pilot_benchmark(
    pilot_id: str,
    csv_path: Path,
    signal_column: str = "S",
    oric_verdict: str = "UNKNOWN",
) -> BenchmarkComparison:
    """Run comparative benchmark on a pilot dataset from CSV."""
    df = pd.read_csv(csv_path)
    if signal_column in df.columns:
        series = df[signal_column].values.astype(float)
    elif "O" in df.columns:
        # Fallback: use O as primary signal
        series = df["O"].values.astype(float)
    else:
        raise ValueError(f"No signal column found in {csv_path}")

    # Drop NaN
    series = series[~np.isnan(series)]

    return run_benchmark_on_series(
        pilot_id=pilot_id,
        series=series,
        oric_verdict=oric_verdict,
    )


def run_all_benchmarks(
    outdir: Path,
    pilots: list[dict] | None = None,
) -> dict:
    """Run benchmarks on all configured pilots."""
    if pilots is None:
        pilots = [
            {"pilot_id": "sector_neuro.pilot_eeg_bonn",
             "csv": "03_Data/sector_neuro/real/pilot_eeg_bonn/real.csv",
             "verdict": "ACCEPT"},
            {"pilot_id": "sector_finance.pilot_btc",
             "csv": "03_Data/sector_finance/real/pilot_btc/real.csv",
             "verdict": "ACCEPT"},
            {"pilot_id": "sector_cosmo.pilot_solar",
             "csv": "03_Data/sector_cosmo/real/pilot_solar/real.csv",
             "verdict": "ACCEPT"},
            {"pilot_id": "sector_health.pilot_covid_excess_mortality",
             "csv": "03_Data/sector_health/real/pilot_covid_excess_mortality/real.csv",
             "verdict": "ACCEPT"},
            {"pilot_id": "sector_ai_tech.pilot_llm_scaling",
             "csv": "03_Data/sector_ai_tech/real/pilot_llm_scaling/real.csv",
             "verdict": "INDETERMINATE"},
            {"pilot_id": "sector_cosmo.pilot_pantheon_sn",
             "csv": "03_Data/sector_cosmo/real/pilot_pantheon_sn/real.csv",
             "verdict": "INDETERMINATE"},
            {"pilot_id": "sector_bio.pilot_pbdb_marine",
             "csv": "03_Data/sector_bio/real/pilot_pbdb_marine/real.csv",
             "verdict": "INDETERMINATE"},
        ]

    root = Path(__file__).resolve().parents[2]
    outdir.mkdir(parents=True, exist_ok=True)
    results = []

    for p in pilots:
        csv_path = root / p["csv"]
        if not csv_path.exists():
            continue
        comp = run_pilot_benchmark(
            pilot_id=p["pilot_id"],
            csv_path=csv_path,
            oric_verdict=p["verdict"],
        )
        results.append(comp.to_dict())

    summary = {
        "schema": "oric.comparative_benchmark.v1",
        "total_pilots": len(results),
        "methods": ["oric", "cusum_changepoint", "structural_break", "anomaly_zscore", "early_warning"],
        "results": results,
    }

    (outdir / "comparative_benchmark.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    return summary
