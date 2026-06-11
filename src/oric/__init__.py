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
- comparative_benchmark: multi-method benchmark (CUSUM, Bai-Perron, EWS, z-score)
- ci_maturity: CI run maturity tracker and classification
- ori_core_v2: alternative capacity/order model variants (V1-V4)
- frozen_params: ex-ante frozen decision parameters (α=0.01, k=2.5, m=3)
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
from .integrity import (
    IntegrityCheck, check_run_integrity, check_dual_proof_integrity,
    check_all_integrity, integrity_gate,
)
from .placebo import (
    PlaceboSpec, PlaceboBatteryResult,
    generate_placebo, generate_placebo_battery, evaluate_placebo_battery,
)
from .decidability import DecidabilityMetrics, compute_decidability, AdaptedPrechecks
from .proof_levels import (
    classify_evidence_level, build_proof_level_summary,
    classify_power, PowerClass,
)
from .proof_package import build_proof_package, ProofPackage
from .comparative_benchmark import (
    MethodResult, BenchmarkComparison,
    cusum_changepoint, structural_break, anomaly_zscore, early_warning_signal,
    run_benchmark_on_series, run_pilot_benchmark, run_all_benchmarks,
)
from .ci_maturity import CIRunRecord, MaturityReport, CIMaturityTracker
from .ori_core_v2 import (
    ModelV2Config, compute_C_trajectory, detect_threshold,
    run_variant_on_dataframe, compare_all_variants,
)
from .frozen_params import FrozenValidationParams, FROZEN_PARAMS, load_frozen_params

__all__ = [
    # Core computations
    "compute_cap_projection",
    "compute_sigma",
    "compute_viability",
    "summarize_run",
    "compute_stock_S",
    "compute_order_C",
    "detect_s_star_piecewise",
    # Model variants
    "ModelV2Config",
    "compute_C_trajectory",
    "detect_threshold",
    "run_variant_on_dataframe",
    "compare_all_variants",
    # Data & specs
    "ProxySpec",
    "ColumnSpec",
    "PreregSpec",
    "FrozenValidationParams",
    "FROZEN_PARAMS",
    "load_frozen_params",
    # Decision engine
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
    "IntegrityCheck",
    "check_run_integrity",
    "check_dual_proof_integrity",
    "check_all_integrity",
    "integrity_gate",
    # Placebo battery
    "PlaceboSpec",
    "PlaceboBatteryResult",
    "generate_placebo",
    "generate_placebo_battery",
    "evaluate_placebo_battery",
    # Decidability & levels
    "DecidabilityMetrics",
    "compute_decidability",
    "AdaptedPrechecks",
    "classify_evidence_level",
    "build_proof_level_summary",
    "classify_power",
    "PowerClass",
    "build_proof_package",
    "ProofPackage",
    # Benchmarking
    "MethodResult",
    "BenchmarkComparison",
    "cusum_changepoint",
    "structural_break",
    "anomaly_zscore",
    "early_warning_signal",
    "run_benchmark_on_series",
    "run_pilot_benchmark",
    "run_all_benchmarks",
    # Utilities
    "RandomizationEngine",
    "ExperimentLogger",
    "CIRunRecord",
    "MaturityReport",
    "CIMaturityTracker",
]
