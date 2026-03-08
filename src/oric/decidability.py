"""decidability.py — Decidability metrics and stable-condition diagnostics.

The core insight: stable runs don't fail because they detect falsely,
they fail because they are INDETERMINATE.  This module provides:

1. Decidability KPIs: explicit tracking of decidable_fraction,
   indeterminate_rate, and reason taxonomy
2. Adaptive prechecks for stable regime: relaxed min_unique_values
   since stable data is expected to have low C variance
3. Decidability improvement strategies

The phrase to aim for: "On stable, the protocol decides majority
NOT_DETECTED" — not just "stable is indeterminate".
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class DecidabilityMetrics:
    """Comprehensive decidability tracking for a condition."""
    condition: str = ""
    n_total: int = 0
    n_decidable: int = 0
    n_indeterminate: int = 0
    n_detected: int = 0
    n_not_detected: int = 0
    decidable_fraction: float = 0.0
    indeterminate_rate: float = 0.0
    detection_rate: float = 0.0
    non_detection_rate: float = 0.0

    # Reason taxonomy for indeterminate runs
    indeterminate_reasons: dict[str, int] = field(default_factory=dict)
    top_indeterminate_reason: str = ""

    # Diagnostic
    mean_c_variance: float | None = None
    mean_n_unique_c: float | None = None
    mean_series_length: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def compute_decidability(
    runs: list[dict],
    condition: str = "",
) -> DecidabilityMetrics:
    """Compute decidability metrics from a list of run result dicts.

    Each run dict should have:
      - verdict or classified_verdict: DETECTED/NOT_DETECTED/INDETERMINATE
      - precheck_reason (optional): why it was INDETERMINATE
      - var_reason (optional): additional reason
      - c_variance (optional): diagnostic
      - n_unique_c (optional): diagnostic
      - n_rows (optional): series length
    """
    m = DecidabilityMetrics(condition=condition)
    m.n_total = len(runs)

    reasons: list[str] = []

    for r in runs:
        v = (r.get("classified_verdict")
             or r.get("verdict", "INDETERMINATE")).upper().strip()

        if v == "DETECTED":
            m.n_detected += 1
        elif v == "NOT_DETECTED":
            m.n_not_detected += 1
        else:
            m.n_indeterminate += 1
            # Collect reason
            reason = (
                r.get("precheck_reason")
                or r.get("var_reason")
                or r.get("reason")
                or "unknown"
            )
            reasons.append(str(reason))

    m.n_decidable = m.n_detected + m.n_not_detected

    if m.n_total > 0:
        m.decidable_fraction = m.n_decidable / m.n_total
        m.indeterminate_rate = m.n_indeterminate / m.n_total

    if m.n_decidable > 0:
        m.detection_rate = m.n_detected / m.n_decidable
        m.non_detection_rate = m.n_not_detected / m.n_decidable

    # Reason taxonomy
    if reasons:
        reason_counts = Counter(reasons)
        m.indeterminate_reasons = dict(reason_counts.most_common())
        m.top_indeterminate_reason = reason_counts.most_common(1)[0][0]

    # Diagnostics
    c_vars = [r.get("c_variance") for r in runs
              if r.get("c_variance") is not None]
    if c_vars:
        m.mean_c_variance = sum(c_vars) / len(c_vars)

    n_uniques = [r.get("n_unique_c") for r in runs
                 if r.get("n_unique_c") is not None]
    if n_uniques:
        m.mean_n_unique_c = sum(n_uniques) / len(n_uniques)

    n_rows_list = [r.get("n_rows") for r in runs
                   if r.get("n_rows") is not None]
    if n_rows_list:
        m.mean_series_length = sum(n_rows_list) / len(n_rows_list)

    return m


# ── Adapted prechecks for stable regime ────────────────────────────────────

@dataclass(frozen=True)
class AdaptedPrechecks:
    """Prechecks adapted per regime.

    For stable data:
      - Lower min_unique_values_C (stable data has naturally low C variance)
      - Lower min_variance_C threshold
      - Allow longer window tolerance
    """
    min_points_per_segment: int = 60
    min_unique_values_C: int = 5
    max_nan_frac: float = 0.05
    min_variance_C: float = 1e-10

    @classmethod
    def for_regime(cls, regime: str, series_length: int = 0) -> "AdaptedPrechecks":
        """Return adapted prechecks for a given regime."""
        if regime == "stable":
            # Stable data: C is expected to be near-constant or zero
            # Relax unique values requirement but keep others strict
            return cls(
                min_points_per_segment=max(30, series_length // 5),
                min_unique_values_C=3,  # down from 5
                max_nan_frac=0.05,
                min_variance_C=1e-15,  # much lower: near-zero C is expected
            )
        elif regime == "placebo":
            return cls(
                min_points_per_segment=60,
                min_unique_values_C=4,
                max_nan_frac=0.05,
                min_variance_C=1e-12,
            )
        else:
            # Test regime: standard prechecks
            return cls()


def check_precheck(
    c_pre: Any,
    c_post: Any,
    prechecks: AdaptedPrechecks,
) -> tuple[bool, str | None]:
    """Run adapted prechecks on C arrays.

    Returns (passed, reason_if_failed).
    """
    import numpy as np

    c_pre = np.asarray(c_pre, dtype=float)
    c_post = np.asarray(c_post, dtype=float)

    # Min points
    if len(c_pre) < prechecks.min_points_per_segment:
        return False, f"precheck_failed:min_points_pre({len(c_pre)}<{prechecks.min_points_per_segment})"
    if len(c_post) < prechecks.min_points_per_segment:
        return False, f"precheck_failed:min_points_post({len(c_post)}<{prechecks.min_points_per_segment})"

    # NaN fraction
    for label, arr in [("pre", c_pre), ("post", c_post)]:
        nan_frac = np.isnan(arr).mean()
        if nan_frac > prechecks.max_nan_frac:
            return False, f"precheck_failed:nan_frac_{label}({nan_frac:.3f}>{prechecks.max_nan_frac})"

    # Min unique values
    for label, arr in [("pre", c_pre), ("post", c_post)]:
        clean = arr[~np.isnan(arr)]
        n_unique = len(np.unique(clean))
        if n_unique < prechecks.min_unique_values_C:
            return False, f"precheck_failed:min_unique_{label}({n_unique}<{prechecks.min_unique_values_C})"

    # Min variance
    for label, arr in [("pre", c_pre), ("post", c_post)]:
        clean = arr[~np.isnan(arr)]
        if len(clean) > 1:
            var = float(np.var(clean))
            if var < prechecks.min_variance_C:
                return False, f"precheck_failed:min_variance_{label}({var:.2e}<{prechecks.min_variance_C:.2e})"

    return True, None


# ── Decidability report ────────────────────────────────────────────────────

def build_decidability_report(
    test_metrics: DecidabilityMetrics,
    stable_metrics: DecidabilityMetrics,
    placebo_metrics: DecidabilityMetrics,
) -> dict:
    """Build a comprehensive decidability report."""
    all_metrics = {
        "test": test_metrics,
        "stable": stable_metrics,
        "placebo": placebo_metrics,
    }

    overall_decidable = sum(m.n_decidable for m in all_metrics.values())
    overall_total = sum(m.n_total for m in all_metrics.values())
    overall_indeterminate = sum(m.n_indeterminate for m in all_metrics.values())

    # Aggregate reasons
    all_reasons: dict[str, int] = {}
    for m in all_metrics.values():
        for reason, count in m.indeterminate_reasons.items():
            all_reasons[reason] = all_reasons.get(reason, 0) + count

    # Sort by frequency
    sorted_reasons = sorted(all_reasons.items(), key=lambda x: -x[1])

    report = {
        "overall": {
            "n_total": overall_total,
            "n_decidable": overall_decidable,
            "n_indeterminate": overall_indeterminate,
            "decidable_fraction": overall_decidable / overall_total if overall_total > 0 else 0.0,
            "indeterminate_rate": overall_indeterminate / overall_total if overall_total > 0 else 0.0,
        },
        "per_condition": {
            name: m.to_dict() for name, m in all_metrics.items()
        },
        "indeterminate_reason_taxonomy": dict(sorted_reasons),
        "recommendations": [],
    }

    # Generate recommendations
    if stable_metrics.decidable_fraction < 0.60:
        report["recommendations"].append(
            "stable decidability low: consider longer series, "
            "relaxed min_unique_values_C, or adapted prechecks for stable regime"
        )
    if placebo_metrics.detection_rate > 0.50 and placebo_metrics.n_decidable > 0:
        report["recommendations"].append(
            "placebo detection rate too high: consider alternative placebo "
            "strategies (phase_randomize, proxy_remap) or review detection "
            "sensitivity thresholds"
        )

    # Check the key phrase
    stable_decides_not_detected = (
        stable_metrics.decidable_fraction >= 0.60
        and stable_metrics.non_detection_rate >= 0.70
    )
    report["stable_decides_non_detection"] = stable_decides_not_detected
    report["key_phrase"] = (
        "stable: protocol decides majority NOT_DETECTED"
        if stable_decides_not_detected
        else "stable: insufficient decidability or too many false positives"
    )

    return report
