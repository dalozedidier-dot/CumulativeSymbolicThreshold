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

from .accumulation_controls import (
    BIFURCATING,
    NON_BIFURCATING,
    accumulation_control_catalogue,
    gen_accumulation,
    run_accumulation_control_suite,
)
from .cap_robustness import CapRobustnessSpec, compute_cap_variants, summarize_cap_robustness
from .ci_maturity import CIMaturityTracker, CIRunRecord, MaturityReport
from .comparative_benchmark import (
    BenchmarkComparison,
    MethodResult,
    anomaly_zscore,
    cusum_changepoint,
    early_warning_signal,
    run_all_benchmarks,
    run_benchmark_on_series,
    run_pilot_benchmark,
    structural_break,
)
from .confirmatory import run_confirmatory_suite
from .decidability import AdaptedPrechecks, DecidabilityMetrics, compute_decidability
from .decision import WELCH_NAN_FALLBACK_POLICY, DecisionResult, hierarchical_verdict
from .early_warning import (
    EarlyWarningResult,
    composite_csd_statistic,
    csd_surrogate_test,
    early_warning,
    early_warning_before_jump,
    find_jump,
    gaussian_detrend,
    kendall_trend,
    rolling_autocorr1,
    rolling_variance,
)
from .effect_size import (
    EffectSizeReport,
    achieved_power,
    cohens_d,
    effect_size_report,
    hedges_g,
)
from .endogenous import (
    EndogenousConfig,
    bistable_window,
    drive_from_sigma,
    equilibria,
    fold_approach,
    hysteresis_sweep,
    make_ramp,
    matched_fold_pair,
    run_endogenous,
    simulate,
)
from .frozen_params import FROZEN_PARAMS, FrozenValidationParams, load_frozen_params
from .integrity import (
    IntegrityCheck,
    check_all_integrity,
    check_dual_proof_integrity,
    check_run_integrity,
    integrity_gate,
)
from .logger import ExperimentLogger
from .multiverse import (
    Specification,
    apply_specification,
    run_multiverse,
    specification_grid,
)
from .oos_prediction import (
    PredictionScore,
    TransitionPrediction,
    predict_transition,
    score_prediction,
)
from .ori_core import compute_cap_projection, compute_sigma, compute_viability, summarize_run
from .ori_core_v2 import (
    ModelV2Config,
    compare_all_variants,
    compute_C_trajectory,
    detect_threshold,
    run_variant_on_dataframe,
)
from .placebo import (
    PlaceboBatteryResult,
    PlaceboSpec,
    evaluate_placebo_battery,
    generate_placebo,
    generate_placebo_battery,
)
from .prereg import PreregSpec
from .proof_levels import (
    PowerClass,
    build_proof_level_summary,
    classify_evidence_level,
    classify_power,
)
from .proof_manifest import (
    DualProofManifest,
    FinalGateError,
    _apply_synthetic_fallback,
    build_dual_proof_manifest,
    build_final_status,
    read_proof_dimensions,
)
from .proof_package import ProofPackage, build_proof_package
from .proxy_spec import ColumnSpec, ProxySpec
from .randomization import RandomizationEngine
from .surrogates import (
    CrossingStatistic,
    SeriesSurrogateResult,
    SurrogateNullResult,
    iaaft_surrogate,
    iaaft_surrogates,
    series_surrogate_test,
    surrogate_null_test,
    threshold_crossing_statistic,
    trend_preserving_surrogate,
)
from .symbolic import compute_order_C, compute_stock_S, detect_s_star_piecewise

__all__ = [
    # Core computations
    "CapRobustnessSpec",
    "compute_cap_projection",
    "compute_cap_variants",
    "summarize_cap_robustness",
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
    # Surrogates & null distribution
    "iaaft_surrogate",
    "iaaft_surrogates",
    "threshold_crossing_statistic",
    "surrogate_null_test",
    "CrossingStatistic",
    "SurrogateNullResult",
    # Harder nulls: trend-preserving surrogate + generic series test
    "trend_preserving_surrogate",
    "series_surrogate_test",
    "SeriesSurrogateResult",
    # Accumulation controls (trend-vs-transition discrimination)
    "gen_accumulation",
    "accumulation_control_catalogue",
    "run_accumulation_control_suite",
    "NON_BIFURCATING",
    "BIFURCATING",
    # Multiverse / specification curve
    "Specification",
    "specification_grid",
    "apply_specification",
    "run_multiverse",
    # Effect size vs SESOI + power
    "cohens_d",
    "hedges_g",
    "achieved_power",
    "effect_size_report",
    "EffectSizeReport",
    # Joint confirmatory verdict
    "run_confirmatory_suite",
    # Endogenous bistable model (genuine saddle-node + hysteresis)
    "EndogenousConfig",
    "equilibria",
    "bistable_window",
    "simulate",
    "run_endogenous",
    "drive_from_sigma",
    "make_ramp",
    "fold_approach",
    "matched_fold_pair",
    "hysteresis_sweep",
    # Critical-slowing-down early-warning detector (primary)
    "EarlyWarningResult",
    "early_warning",
    "early_warning_before_jump",
    "composite_csd_statistic",
    "csd_surrogate_test",
    "gaussian_detrend",
    "rolling_autocorr1",
    "rolling_variance",
    "kendall_trend",
    "find_jump",
    # Out-of-sample directional prediction
    "TransitionPrediction",
    "PredictionScore",
    "predict_transition",
    "score_prediction",
    # Utilities
    "RandomizationEngine",
    "ExperimentLogger",
    "CIRunRecord",
    "MaturityReport",
    "CIMaturityTracker",
]
