"""ORI-C canonical package.

This package provides:
- ORI core computations: O, R, I, Cap, Sigma, V
- Symbolic layer computations: S, C, regimes, cut U
- Randomization and logging utilities for reproducible experiments
- ProxySpec: versioned, hashable ex-ante proxy mapping for real-data runs
- decision: nan-safe hierarchical verdict (Welch → bootstrap → Mann-Whitney)
- proof_manifest: dual proof manifest builder with schema validation
- integrity: verdict alignment and integrity checking
- placebo: versioned placebo battery (5 strategies)
- decidability: decidability metrics and stable-condition diagnostics
- proof_levels: Level A (canonical) vs Level B (exploratory) separation
- proof_package: unified 4-bloc proof package generator
"""

from .prereg import PreregSpec
from .randomization import RandomizationEngine
from .logger import ExperimentLogger
from .ori_core import compute_cap_projection, compute_sigma, compute_viability, summarize_run
from .symbolic import compute_stock_S, compute_order_C, detect_s_star_piecewise
from .proxy_spec import ProxySpec, ColumnSpec
from .decision import DecisionResult, hierarchical_verdict, WELCH_NAN_FALLBACK_POLICY
from .proof_manifest import (
    DualProofManifest, build_dual_proof_manifest, build_final_status,
    read_proof_dimensions, FinalGateError, _apply_synthetic_fallback,
)
from .integrity import check_run_integrity, check_dual_proof_integrity, integrity_gate
from .placebo import generate_placebo, generate_placebo_battery, evaluate_placebo_battery
from .decidability import DecidabilityMetrics, compute_decidability, AdaptedPrechecks
from .proof_levels import classify_evidence_level, build_proof_level_summary
from .proof_package import build_proof_package, ProofPackage

__all__ = [
    "PreregSpec",
    "RandomizationEngine",
    "ExperimentLogger",
    "compute_cap_projection",
    "compute_sigma",
    "compute_viability",
    "summarize_run",
    "compute_stock_S",
    "compute_order_C",
    "detect_s_star_piecewise",
    "ProxySpec",
    "ColumnSpec",
    "DecisionResult",
    "hierarchical_verdict",
    "WELCH_NAN_FALLBACK_POLICY",
    # Proof infrastructure
    "DualProofManifest",
    "build_dual_proof_manifest",
    "build_final_status",
    "read_proof_dimensions",
    "FinalGateError",
    "_apply_synthetic_fallback",
    "check_run_integrity",
    "check_dual_proof_integrity",
    "integrity_gate",
    "generate_placebo",
    "generate_placebo_battery",
    "evaluate_placebo_battery",
    "DecidabilityMetrics",
    "compute_decidability",
    "AdaptedPrechecks",
    "classify_evidence_level",
    "build_proof_level_summary",
    "build_proof_package",
    "ProofPackage",
]
