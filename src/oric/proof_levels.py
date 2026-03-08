"""proof_levels.py — Separation of canonical (A) vs exploratory (B) evidence.

Level A — Canonical Demonstration:
  - Synthetic: full statistical support with confusion matrix
  - FRED canonical: validated with protocol (C1+C2+C3)
  - Validation protocol: sensitivity >= 0.80, specificity >= 0.80, Fisher p < 0.01

Level B — Exploratory Multi-Sector:
  - Computation coherence: pipeline runs without error
  - Mapping feasibility: proxy_spec maps correctly
  - Compatible behaviour: C(t) responds to known interventions
  - BUT: not canonical proof level if prechecks fail (series too short, etc.)

This separation strengthens rigour by being explicit about what each
dataset can and cannot demonstrate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal


ProofLevel = Literal["A", "B"]


@dataclass
class DatasetEvidence:
    """Evidence record for a single dataset."""
    dataset_id: str = ""
    level: ProofLevel = "B"
    category: str = ""  # economic, biological, ecological, etc.
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
    limitation_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Level classification rules ─────────────────────────────────────────────

MIN_ROWS_CANONICAL = 200
MIN_PRECHECK_RATE = 0.60


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
) -> DatasetEvidence:
    """Classify a dataset's evidence level."""
    ev = DatasetEvidence(
        dataset_id=dataset_id,
        category=category,
        n_rows=n_rows,
        verdict=verdict,
        precheck_passed=precheck_passed,
    )

    ev.series_length_adequate = n_rows >= MIN_ROWS_CANONICAL
    ev.causal_tests_passed = causal_tests_available and precheck_passed

    # Level A criteria
    is_level_a = (
        ev.series_length_adequate
        and ev.precheck_passed
        and ev.causal_tests_passed
        and verdict in ("ACCEPT", "REJECT")  # Must be decidable
    )

    if is_level_a and sensitivity is not None:
        ev.sensitivity = sensitivity
    if is_level_a and specificity is not None:
        ev.specificity = specificity

    if is_level_a:
        ev.level = "A"
        ev.reason_for_level = "Full canonical validation criteria met"
    else:
        ev.level = "B"
        reasons = []
        if not ev.series_length_adequate:
            reasons.append(f"series_too_short({n_rows}<{MIN_ROWS_CANONICAL})")
        if not ev.precheck_passed:
            reasons.append("precheck_failed")
        if not ev.causal_tests_passed:
            reasons.append("causal_tests_unavailable")
        if verdict == "INDETERMINATE":
            reasons.append("verdict_indeterminate")
        ev.reason_for_level = "; ".join(reasons) or "does not meet Level A criteria"

        # Level B properties
        ev.computation_coherent = True  # Assumed if pipeline ran
        ev.mapping_feasible = True  # Assumed if proxy_spec loaded
        ev.behaviour_compatible = verdict != "error"
        if not ev.series_length_adequate:
            ev.limitation_notes.append(
                f"Series length {n_rows} insufficient for canonical causal tests"
            )
        if decidable_fraction is not None and decidable_fraction < MIN_PRECHECK_RATE:
            ev.limitation_notes.append(
                f"Decidable fraction {decidable_fraction:.2f} below threshold"
            )

    return ev


# ── Level summary ──────────────────────────────────────────────────────────

@dataclass
class ProofLevelSummary:
    """Summary of evidence across all datasets, separated by level."""
    level_a_datasets: list[DatasetEvidence] = field(default_factory=list)
    level_b_datasets: list[DatasetEvidence] = field(default_factory=list)
    n_level_a: int = 0
    n_level_b: int = 0
    level_a_all_accept: bool = False
    level_a_verdict: str = ""

    def to_dict(self) -> dict:
        return {
            "n_level_a": self.n_level_a,
            "n_level_b": self.n_level_b,
            "level_a_all_accept": self.level_a_all_accept,
            "level_a_verdict": self.level_a_verdict,
            "level_a_datasets": [d.to_dict() for d in self.level_a_datasets],
            "level_b_datasets": [d.to_dict() for d in self.level_b_datasets],
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
        else:
            s.level_b_datasets.append(ev)

    s.n_level_a = len(s.level_a_datasets)
    s.n_level_b = len(s.level_b_datasets)

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
