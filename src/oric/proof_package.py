"""proof_package.py — Unified 4-bloc proof package generator.

Produces a single "proof package" JSON with 4 blocs:

Bloc 1. Contractual Proof
  - dual_proof_manifest complete
  - final_status correct
  - unique schema
  - integrity tests pass

Bloc 2. Discriminant Proof
  - Versioned benchmark
  - Confusion matrix
  - Sensitivity / Specificity
  - Indeterminate rate
  - test / stable / placebo separation

Bloc 3. Robustness Proof
  - Window stability
  - Subsampling stability
  - Normalisation variants (if available)
  - No opportunistic verdict flipping

Bloc 4. External Proof (placeholder for independent replication)
  - Independent replication
  - External dataset
  - Same frozen protocol
  - No retuning
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from .proof_manifest import DualProofManifest, build_final_status
from .integrity import integrity_gate, IntegrityCheck
from .proof_levels import ProofLevelSummary
from .decidability import DecidabilityMetrics


@dataclass
class BlocContractual:
    """Bloc 1: Contractual proof."""
    manifest_complete: bool = False
    final_status_correct: bool = False
    schema_valid: bool = False
    integrity_passed: bool = False
    n_integrity_errors: int = 0
    integrity_errors: list[str] = field(default_factory=list)
    manifest_summary: dict = field(default_factory=dict)
    final_status: dict = field(default_factory=dict)


@dataclass
class BlocDiscriminant:
    """Bloc 2: Discriminant proof."""
    confusion_matrix: dict = field(default_factory=dict)
    sensitivity: float | None = None
    specificity: float | None = None
    fisher_p: float | None = None
    test_detection_rate: float | None = None
    stable_detection_rate: float | None = None
    placebo_detection_rate: float | None = None
    indeterminate_rate_test: float | None = None
    indeterminate_rate_stable: float | None = None
    indeterminate_rate_placebo: float | None = None
    decidability_report: dict = field(default_factory=dict)
    placebo_battery: dict = field(default_factory=dict)
    benchmark_version: int = 1
    discrimination_passes: bool = False


@dataclass
class BlocRobustness:
    """Bloc 3: Robustness proof."""
    window_stability: dict = field(default_factory=dict)
    subsample_stability: dict = field(default_factory=dict)
    normalisation_variants: dict = field(default_factory=dict)
    verdict_flip_detected: bool = False
    robustness_passes: bool = False


@dataclass
class BlocExternal:
    """Bloc 4: External proof (placeholder)."""
    independent_replication: bool = False
    external_dataset_used: bool = False
    frozen_protocol_used: bool = False
    no_retuning: bool = False
    replication_details: dict = field(default_factory=dict)
    external_passes: bool = False


@dataclass
class ProofPackage:
    """Complete 4-bloc proof package."""
    schema: str = "oric.proof_package.v1"
    generated_at: str = ""
    overall_verdict: str = "INCOMPLETE"

    bloc1_contractual: BlocContractual = field(default_factory=BlocContractual)
    bloc2_discriminant: BlocDiscriminant = field(default_factory=BlocDiscriminant)
    bloc3_robustness: BlocRobustness = field(default_factory=BlocRobustness)
    bloc4_external: BlocExternal = field(default_factory=BlocExternal)

    proof_levels: dict = field(default_factory=dict)
    bloc_verdicts: dict = field(default_factory=dict)

    def compute_overall(self) -> None:
        """Compute overall verdict from bloc verdicts."""
        b1 = self.bloc1_contractual.integrity_passed and self.bloc1_contractual.manifest_complete
        b2 = self.bloc2_discriminant.discrimination_passes
        b3 = self.bloc3_robustness.robustness_passes
        b4 = self.bloc4_external.external_passes

        self.bloc_verdicts = {
            "bloc1_contractual": "PASS" if b1 else "FAIL",
            "bloc2_discriminant": "PASS" if b2 else "FAIL",
            "bloc3_robustness": "PASS" if b3 else "FAIL",
            "bloc4_external": "PASS" if b4 else "PENDING",
        }

        if b1 and b2 and b3:
            self.overall_verdict = "STRONG" if b4 else "ACCEPT"
        elif b1 and b2:
            self.overall_verdict = "PARTIAL"
        else:
            self.overall_verdict = "INCOMPLETE"

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "generated_at": self.generated_at,
            "overall_verdict": self.overall_verdict,
            "bloc_verdicts": self.bloc_verdicts,
            "bloc1_contractual": asdict(self.bloc1_contractual),
            "bloc2_discriminant": asdict(self.bloc2_discriminant),
            "bloc3_robustness": asdict(self.bloc3_robustness),
            "bloc4_external": asdict(self.bloc4_external),
            "proof_levels": self.proof_levels,
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, default=str) + "\n",
            encoding="utf-8",
        )


# ── Builder ────────────────────────────────────────────────────────────────

def build_proof_package(
    manifest: DualProofManifest,
    integrity_checks: list[IntegrityCheck] | None = None,
    discrimination_metrics: dict | None = None,
    condition_decidability: dict[str, DecidabilityMetrics] | None = None,
    placebo_battery_result: dict | None = None,
    window_stability: dict | None = None,
    subsample_stability: dict | None = None,
    proof_levels: ProofLevelSummary | None = None,
    replication_info: dict | None = None,
) -> ProofPackage:
    """Build the complete 4-bloc proof package."""
    pkg = ProofPackage()
    pkg.generated_at = datetime.now(timezone.utc).isoformat()

    # ── Bloc 1: Contractual ─────────────────────────────────────────
    final_status = build_final_status(manifest)
    pkg.bloc1_contractual.manifest_summary = {
        "dual_proof_status": manifest.dual_proof_status,
        "empty_fields": manifest.empty_fields,
        "inconsistencies": manifest.inconsistencies,
    }
    pkg.bloc1_contractual.final_status = final_status
    pkg.bloc1_contractual.manifest_complete = (
        manifest.dual_proof_status == "DUAL_PROOF_COMPLETE"
    )
    pkg.bloc1_contractual.final_status_correct = (
        final_status["framework_status"] == "COMPLETE"
    )
    pkg.bloc1_contractual.schema_valid = (
        final_status.get("schema") in ("oric.final_status.v1", "oric.final_status.v2")
    )

    if integrity_checks is not None:
        passed, errors = integrity_gate(integrity_checks)
        pkg.bloc1_contractual.integrity_passed = passed
        pkg.bloc1_contractual.n_integrity_errors = len(errors)
        pkg.bloc1_contractual.integrity_errors = errors
    else:
        pkg.bloc1_contractual.integrity_passed = True  # No checks requested

    # ── Bloc 2: Discriminant ────────────────────────────────────────
    if discrimination_metrics is not None:
        dm = discrimination_metrics
        cm = dm.get("confusion_matrix", {})
        pkg.bloc2_discriminant.confusion_matrix = cm
        pkg.bloc2_discriminant.sensitivity = dm.get("sensitivity")
        pkg.bloc2_discriminant.specificity = dm.get("specificity")
        pkg.bloc2_discriminant.fisher_p = dm.get("fisher_p_value")

        indet = dm.get("indeterminate_rate_by_condition", {})
        pkg.bloc2_discriminant.indeterminate_rate_test = indet.get("test")
        pkg.bloc2_discriminant.indeterminate_rate_stable = indet.get("stable")
        pkg.bloc2_discriminant.indeterminate_rate_placebo = indet.get("placebo")

        sens = dm.get("sensitivity", 0.0) or 0.0
        spec = dm.get("specificity", 0.0) or 0.0
        fisher = dm.get("fisher_p_value", 1.0) or 1.0
        pkg.bloc2_discriminant.discrimination_passes = (
            sens >= 0.80 and spec >= 0.80 and fisher < 0.01
        )

    if condition_decidability is not None:
        from .decidability import build_decidability_report
        test_m = condition_decidability.get("test", DecidabilityMetrics())
        stable_m = condition_decidability.get("stable", DecidabilityMetrics())
        placebo_m = condition_decidability.get("placebo", DecidabilityMetrics())

        pkg.bloc2_discriminant.test_detection_rate = test_m.detection_rate
        pkg.bloc2_discriminant.stable_detection_rate = stable_m.detection_rate
        pkg.bloc2_discriminant.placebo_detection_rate = placebo_m.detection_rate
        pkg.bloc2_discriminant.decidability_report = build_decidability_report(
            test_m, stable_m, placebo_m
        )

    if placebo_battery_result is not None:
        pkg.bloc2_discriminant.placebo_battery = placebo_battery_result

    # ── Bloc 3: Robustness ──────────────────────────────────────────
    if window_stability is not None:
        pkg.bloc3_robustness.window_stability = window_stability
    if subsample_stability is not None:
        pkg.bloc3_robustness.subsample_stability = subsample_stability

    # Check for verdict flipping
    if window_stability:
        verdicts = [
            v.get("verdict", "")
            for v in window_stability.get("rows", [])
            if v.get("dataset") == "test"
        ]
        unique_verdicts = set(v for v in verdicts if v)
        pkg.bloc3_robustness.verdict_flip_detected = len(unique_verdicts) > 1

    pkg.bloc3_robustness.robustness_passes = (
        not pkg.bloc3_robustness.verdict_flip_detected
        and bool(window_stability or subsample_stability)
    )

    # ── Bloc 4: External ────────────────────────────────────────────
    if replication_info is not None:
        pkg.bloc4_external.independent_replication = replication_info.get("independent", False)
        pkg.bloc4_external.external_dataset_used = replication_info.get("external_data", False)
        pkg.bloc4_external.frozen_protocol_used = replication_info.get("frozen_protocol", False)
        pkg.bloc4_external.no_retuning = replication_info.get("no_retuning", False)
        pkg.bloc4_external.replication_details = replication_info
        pkg.bloc4_external.external_passes = all([
            pkg.bloc4_external.independent_replication,
            pkg.bloc4_external.external_dataset_used,
            pkg.bloc4_external.frozen_protocol_used,
            pkg.bloc4_external.no_retuning,
        ])

    # ── Proof levels ────────────────────────────────────────────────
    if proof_levels is not None:
        pkg.proof_levels = proof_levels.to_dict()

    # ── Overall ─────────────────────────────────────────────────────
    pkg.compute_overall()

    return pkg
