"""proof_levels.py — Three-level evidence classification with power class.

Level A — Canonical Demonstration:
  - Synthetic: full statistical support with confusion matrix
  - FRED canonical: validated with protocol (C1+C2+C3)
  - Validation protocol: sensitivity >= 0.80, specificity >= 0.80, Fisher p < 0.01

Level B — Conclusive Real Pilots:
  - Out-of-core real datasets with exploitable verdict
  - Series adequate (>= MIN_POINTS_PER_SEGMENT per segment)
  - Prechecks passed, causal tests available, verdict decidable (ACCEPT or REJECT)

Level C — Exploratory Pilots Under Precheck:
  - Signal or plausibility present but no canonical proof level
  - Blocked by power constraints, precheck failures, or insufficient depth
  - Requires explicit power_upgrade_path

Power classes (descriptive, non-decisional):
  - adequate: full bootstrap + stability battery possible
  - borderline: exploratory analysis only, preliminary results
  - underpowered: insufficient evidence, densification required
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal


ProofLevel = Literal["A", "B", "C"]
PowerClass = Literal["adequate", "borderline", "underpowered"]

# ── Thresholds ────────────────────────────────────────────────────────────

MIN_ROWS_CANONICAL = 200
MIN_ROWS_CONCLUSIVE = 60
MIN_PRECHECK_RATE = 0.60
MIN_POINTS_PER_SEGMENT = 60


# ── Power classification ──────────────────────────────────────────────────

def classify_power(
    n_rows: int,
    min_points_per_segment_met: bool = True,
) -> PowerClass:
    """Classify statistical power class from series characteristics.

    Power classes are descriptive, not decisional:
    - adequate: n >= 200 and min_points_per_segment met
    - borderline: n >= 60 and min_points_per_segment met
    - underpowered: below thresholds
    """
    if n_rows >= MIN_ROWS_CANONICAL and min_points_per_segment_met:
        return "adequate"
    elif n_rows >= MIN_ROWS_CONCLUSIVE and min_points_per_segment_met:
        return "borderline"
    else:
        return "underpowered"


# ── Dataset evidence ──────────────────────────────────────────────────────

@dataclass
class DatasetEvidence:
    """Evidence record for a single dataset."""
    dataset_id: str = ""
    level: ProofLevel = "C"
    power_class: PowerClass = "underpowered"
    category: str = ""  # finance, health, neuro, cosmo, bio, ai_tech, etc.
    n_rows: int = 0
    verdict: str = ""
    precheck_passed: bool = False
    causal_tests_passed: bool = False
    series_length_adequate: bool = False
    reason_for_level: str = ""

    # Level A specific
    sensitivity: float | None = None
    specificity: float | None = None
    confusion_matrix: dict | None = None

    # Level B specific
    computation_coherent: bool = False
    mapping_feasible: bool = False
    behaviour_compatible: bool = False

    # Level C specific
    signal_plausible: bool = False
    power_upgrade_path: str = ""
    cause_indetermination: str = ""

    # Common
    limitation_notes: list[str] = field(default_factory=list)
    overinterpretation_risk: str = ""  # very_low, low, medium, high

    def to_dict(self) -> dict:
        return asdict(self)


# ── Level classification rules ─────────────────────────────────────────────

def classify_evidence_level(
    dataset_id: str,
    n_rows: int,
    verdict: str,
    precheck_passed: bool,
    causal_tests_available: bool,
    sensitivity: float | None = None,
    specificity: float | None = None,
    decidable_fraction: float | None = None,
    category: str = "",
    min_points_per_segment_met: bool = True,
    signal_plausible: bool = True,
    power_upgrade_path: str = "",
) -> DatasetEvidence:
    """Classify a dataset's evidence level (A / B / C) and power class."""
    ev = DatasetEvidence(
        dataset_id=dataset_id,
        category=category,
        n_rows=n_rows,
        verdict=verdict,
        precheck_passed=precheck_passed,
    )

    ev.series_length_adequate = n_rows >= MIN_ROWS_CONCLUSIVE
    ev.causal_tests_passed = causal_tests_available and precheck_passed
    ev.power_class = classify_power(n_rows, min_points_per_segment_met)

    # ── Level A: Canonical ──────────────────────────────────────────
    is_level_a = (
        n_rows >= MIN_ROWS_CANONICAL
        and precheck_passed
        and ev.causal_tests_passed
        and verdict in ("ACCEPT", "REJECT")
    )

    if is_level_a and sensitivity is not None:
        ev.sensitivity = sensitivity
    if is_level_a and specificity is not None:
        ev.specificity = specificity

    # ── Level B: Conclusive real pilot ──────────────────────────────
    is_level_b = (
        not is_level_a
        and ev.series_length_adequate
        and precheck_passed
        and min_points_per_segment_met
        and verdict in ("ACCEPT", "REJECT")
    )

    if is_level_a:
        ev.level = "A"
        ev.reason_for_level = "Full canonical validation criteria met"
        ev.overinterpretation_risk = "very_low"
    elif is_level_b:
        ev.level = "B"
        ev.reason_for_level = "Conclusive real pilot with decidable verdict"
        ev.computation_coherent = True
        ev.mapping_feasible = True
        ev.behaviour_compatible = True
        if ev.power_class == "borderline":
            ev.overinterpretation_risk = "low"
            ev.limitation_notes.append(
                f"Series length {n_rows} below canonical threshold ({MIN_ROWS_CANONICAL}); "
                f"results exploitable but not at Level A rigour"
            )
        else:
            ev.overinterpretation_risk = "very_low"
    else:
        # ── Level C: Exploratory under precheck ─────────────────────
        ev.level = "C"
        ev.signal_plausible = signal_plausible
        ev.power_upgrade_path = power_upgrade_path

        reasons = []
        if not ev.series_length_adequate:
            reasons.append(f"series_too_short({n_rows}<{MIN_ROWS_CONCLUSIVE})")
        if not min_points_per_segment_met:
            reasons.append(
                f"min_points_per_segment_not_met(<{MIN_POINTS_PER_SEGMENT})"
            )
        if not precheck_passed:
            reasons.append("precheck_failed")
        if not ev.causal_tests_passed:
            reasons.append("causal_tests_unavailable")
        if verdict == "INDETERMINATE":
            reasons.append("verdict_indeterminate")
        ev.reason_for_level = "; ".join(reasons) or "does not meet Level B criteria"
        ev.cause_indetermination = ev.reason_for_level

        # Level C properties
        ev.computation_coherent = True
        ev.mapping_feasible = True
        ev.behaviour_compatible = verdict != "error"
        ev.overinterpretation_risk = (
            "high" if ev.power_class == "underpowered" else "medium"
        )

        if not ev.series_length_adequate:
            ev.limitation_notes.append(
                f"Series length {n_rows} insufficient for reliable ORI-C verdict"
            )
        if not min_points_per_segment_met:
            ev.limitation_notes.append(
                "Min points per segment not met; canonical prechecks fail"
            )
        if decidable_fraction is not None and decidable_fraction < MIN_PRECHECK_RATE:
            ev.limitation_notes.append(
                f"Decidable fraction {decidable_fraction:.2f} below threshold"
            )
        if power_upgrade_path:
            ev.limitation_notes.append(
                f"Power upgrade path: {power_upgrade_path}"
            )

    return ev


# ── Level summary ──────────────────────────────────────────────────────────

@dataclass
class ProofLevelSummary:
    """Summary of evidence across all datasets, separated by level."""
    level_a_datasets: list[DatasetEvidence] = field(default_factory=list)
    level_b_datasets: list[DatasetEvidence] = field(default_factory=list)
    level_c_datasets: list[DatasetEvidence] = field(default_factory=list)
    n_level_a: int = 0
    n_level_b: int = 0
    n_level_c: int = 0
    level_a_all_accept: bool = False
    level_a_verdict: str = ""

    # Power distribution
    n_adequate: int = 0
    n_borderline: int = 0
    n_underpowered: int = 0

    def to_dict(self) -> dict:
        return {
            "n_level_a": self.n_level_a,
            "n_level_b": self.n_level_b,
            "n_level_c": self.n_level_c,
            "level_a_all_accept": self.level_a_all_accept,
            "level_a_verdict": self.level_a_verdict,
            "power_distribution": {
                "adequate": self.n_adequate,
                "borderline": self.n_borderline,
                "underpowered": self.n_underpowered,
            },
            "level_a_datasets": [d.to_dict() for d in self.level_a_datasets],
            "level_b_datasets": [d.to_dict() for d in self.level_b_datasets],
            "level_c_datasets": [d.to_dict() for d in self.level_c_datasets],
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, default=str) + "\n",
            encoding="utf-8",
        )


def build_proof_level_summary(
    evidences: list[DatasetEvidence],
) -> ProofLevelSummary:
    """Build a summary from a list of dataset evidences."""
    s = ProofLevelSummary()
    for ev in evidences:
        if ev.level == "A":
            s.level_a_datasets.append(ev)
        elif ev.level == "B":
            s.level_b_datasets.append(ev)
        else:
            s.level_c_datasets.append(ev)

        # Power distribution
        if ev.power_class == "adequate":
            s.n_adequate += 1
        elif ev.power_class == "borderline":
            s.n_borderline += 1
        else:
            s.n_underpowered += 1

    s.n_level_a = len(s.level_a_datasets)
    s.n_level_b = len(s.level_b_datasets)
    s.n_level_c = len(s.level_c_datasets)

    if s.level_a_datasets:
        s.level_a_all_accept = all(
            d.verdict == "ACCEPT" for d in s.level_a_datasets
        )
        if s.level_a_all_accept:
            s.level_a_verdict = "ACCEPT"
        elif any(d.verdict == "REJECT" for d in s.level_a_datasets):
            s.level_a_verdict = "REJECT"
        else:
            s.level_a_verdict = "INDETERMINATE"
    else:
        s.level_a_verdict = "NO_CANONICAL_DATA"

    return s
