"""frozen_params.py — Frozen parameter registry for ORI-C validation.

Once calibrated on synthetic data, these parameters are NEVER adjusted
to match real-data outcomes. Any change requires a versioned contract update.

This module is the single source of truth for all frozen parameters
used in the validation protocol.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class FrozenValidationParams:
    """Immutable parameter set for ORI-C validation protocol."""

    # --- Decision thresholds (from VALIDATION_SPECIFICITY) ---
    alpha: float = 0.01
    sesoi_c_robust_sd: float = 0.30
    ci_level: float = 0.99

    # --- Contrast criterion (calibrated on synthetic) ---
    contrast_margin: float = 0.10
    contrast_Q_test: float = 0.80

    # --- Specificity gates ---
    test_detection_rate_min: float = 0.80
    stable_fp_rate_max: float = 0.20
    placebo_fp_rate_max: float = 0.20

    # --- Decidability ---
    min_decidable_per_condition: int = 6
    max_indeterminate_rate: float = 0.40

    # --- ORI-C simulation defaults ---
    n_steps: int = 2600
    intervention_point: int = 900
    intervention_duration: int = 250
    k: float = 2.5
    m: int = 3
    baseline_n: int = 50
    sigma_star: float = 120.0
    tau: float = 600.0
    demand_noise: float = 0.05
    ori_trend: float = 0.0005

    # --- Replication seeds (contractual, never changed) ---
    seed_base: int = 7000
    n_replicates: int = 50

    # --- Power ---
    power_bootstrap_B: int = 500
    power_gate_min: float = 0.70

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8"
        )


# Singleton — the one true parameter set
FROZEN_PARAMS = FrozenValidationParams()


def load_frozen_params(path: Path | None = None) -> FrozenValidationParams:
    """Load frozen params from file, or return the compiled defaults."""
    if path is None:
        path = _REPO_ROOT / "contracts" / "FROZEN_PARAMS.json"
    if not path.exists():
        return FROZEN_PARAMS
    data = json.loads(path.read_text(encoding="utf-8"))
    return FrozenValidationParams(**{
        k: v for k, v in data.items()
        if k in FrozenValidationParams.__dataclass_fields__
    })
