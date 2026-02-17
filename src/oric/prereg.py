from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PreregSpec:
    """Pre-registration specification for ORI-C runs.

    This object is designed to be serialized into JSON for auditability.
    All fields are intended to be declared ex ante.
    """

    alpha: float = 0.01
    ci_level: float = 0.99
    n_min: int = 50

    sesoi_cap_rel: float = 0.10
    sesoi_v_rel: float = -0.10
    sesoi_c_robust_sd: float = 0.30

    # Windows and thresholds
    window_W: int = 20
    window_mu: int = 10
    k_sigma: float = 2.5
    m_consecutive: int = 3

    # Weight vectors
    omega_v: tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25)
    alpha_s: tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25)

    # Functional forms identifiers (for audit trail)
    cap_form: str = "product"
    sigma_form: str = "relu_diff"
    v_form: str = "weighted_mean"
    s_form: str = "weighted_mean"

    # Power estimation
    power_bootstrap_B: int = 500
    power_gate_min: float = 0.70
    power_target: float = 0.80

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        if not (0 < self.alpha < 1):
            raise ValueError("alpha must be in (0, 1)")
        if not (0 < self.ci_level < 1):
            raise ValueError("ci_level must be in (0, 1)")
        if self.n_min <= 0:
            raise ValueError("n_min must be positive")
        if self.window_W <= 0 or self.window_mu <= 0:
            raise ValueError("windows must be positive")
        if self.m_consecutive <= 0:
            raise ValueError("m_consecutive must be positive")
        if len(self.omega_v) != 4 or len(self.alpha_s) != 4:
            raise ValueError("omega_v and alpha_s must have length 4")
