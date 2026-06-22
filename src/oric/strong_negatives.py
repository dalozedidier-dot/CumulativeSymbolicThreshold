"""strong_negatives.py — a real battery of *strong* negatives for ORI-C.

Specificity is the other half of the proof. A detector that fires on genuine
bifurcations is worthless unless it stays *silent* on the processes that most
easily fool a trend/threshold detector. This module assembles the hardest such
negatives — the cases where ORI-C **must say NO** — and measures the
localized-transition gate's false-positive rate against them, while checking on a
positive contrast set that the gate has not simply gone dead.

Why these are "strong"
----------------------
ORI-C's order variable is an integrator, ``C(t+1) = C(t) + β·S − γ·V``. The
adversarial negatives below are exactly the ones an integrator + a
"sustained ΔC > μ+k·σ" rule tends to false-positive on:

  Smooth monotone accumulations (no break) — reused from ``accumulation_controls``
    logistic_growth · gompertz · exponential_saturation · linear_ramp

  Stochastic non-transition traps
    random_walk        — a UNIT-ROOT process: the classic spurious-trend trap
    ar1_red_noise      — strong autocorrelation (φ=0.9), no regime change
    brownian_drift     — random walk plus a small constant drift
    pink_noise         — 1/f long-memory noise
    white_noise        — stationary sanity check

  Structured deterministic non-transition
    sinusoid           — a smooth oscillation (rises, but no localized break)
    sawtooth           — repeated ramps (many "rises", still no single regime change)

Positive contrast (must fire) — reused
    sharp_regime_switch · delayed_bifurcation

Verdict (frozen ex ante; see ``contracts/STRONG_NEGATIVES_CRITERIA.json``)
--------------------------------------------------------------------------
  STRONG_NEGATIVES_CLEAN        localized FPR ≤ fpr_max AND bifurcation TPR ≥ tpr_min
  STRONG_NEGATIVES_LEAK         localized FPR > fpr_max  (specificity refuted)
  STRONG_NEGATIVES_INSENSITIVE  bifurcation TPR < tpr_min (detector is dead — vacuous)

The honest target is CLEAN; a LEAK is reported at equal status (it would mean the
gate cannot be distinguished from a trend detector on adversarial nulls).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import numpy as np
import pandas as pd

from oric.accumulation_controls import NON_BIFURCATING, BIFURCATING, gen_accumulation

# Frozen acceptance thresholds (mirrored in the JSON contract).
FPR_MAX: float = 0.10        # strong negatives may fire on at most 10 % of the battery
TPR_MIN: float = 0.50        # the positive contrast must still fire on >= 50 %

StrongNegativeKind = Literal[
    "random_walk",
    "ar1_red_noise",
    "brownian_drift",
    "pink_noise",
    "white_noise",
    "sinusoid",
    "sawtooth",
]

STOCHASTIC_NEGATIVES: tuple[StrongNegativeKind, ...] = (
    "random_walk",
    "ar1_red_noise",
    "brownian_drift",
    "pink_noise",
    "white_noise",
)
STRUCTURED_NEGATIVES: tuple[StrongNegativeKind, ...] = (
    "sinusoid",
    "sawtooth",
)

_DEMAND_LO, _DEMAND_HI = 0.55, 1.55  # same dynamic range as accumulation_controls


def _stable_ori(n: int, rng: np.random.Generator,
                base: tuple[float, float, float] = (0.62, 0.66, 0.58),
                noise: float = 0.015) -> dict[str, np.ndarray]:
    """Stable O, R, I proxies (near-constant Cap), stationary noise only."""
    return {
        "O": np.clip(base[0] + rng.normal(0, noise, n), 0.05, 0.95),
        "R": np.clip(base[1] + rng.normal(0, noise, n), 0.05, 0.95),
        "I": np.clip(base[2] + rng.normal(0, noise, n), 0.05, 0.95),
    }


def _scale_to_demand(x: np.ndarray) -> np.ndarray:
    """Min-max scale an arbitrary process into the demand range [lo, hi]."""
    lo_x, hi_x = float(np.min(x)), float(np.max(x))
    if hi_x - lo_x < 1e-12:
        return np.full_like(x, 0.5 * (_DEMAND_LO + _DEMAND_HI))
    z = (x - lo_x) / (hi_x - lo_x)
    return _DEMAND_LO + (_DEMAND_HI - _DEMAND_LO) * z


def _pink_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    """1/f (pink) noise via spectral shaping of white noise."""
    white = rng.normal(0, 1, n)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n)
    freqs[0] = freqs[1] if n > 1 else 1.0
    spec = spec / np.sqrt(freqs)            # 1/sqrt(f) amplitude → 1/f power
    return np.fft.irfft(spec, n=n)


def gen_strong_negative(kind: StrongNegativeKind, n: int, seed: int) -> pd.DataFrame:
    """Generate one (t, O, R, I, demand) strong-negative control of ``kind``.

    The non-transition structure lives entirely in ``demand`` (O, R, I are
    stable), so the series exercises the real detector path via
    Σ = max(0, demand − Cap) exactly like a real series.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=float)

    if kind == "random_walk":
        x = np.cumsum(rng.normal(0, 1, n))
    elif kind == "ar1_red_noise":
        phi = 0.9
        x = np.empty(n)
        x[0] = rng.normal(0, 1)
        for i in range(1, n):
            x[i] = phi * x[i - 1] + rng.normal(0, 1)
    elif kind == "brownian_drift":
        x = np.cumsum(rng.normal(0, 1, n)) + 0.15 * t
    elif kind == "pink_noise":
        x = np.cumsum(_pink_noise(n, rng) * 0.0) + _pink_noise(n, rng)
    elif kind == "white_noise":
        x = rng.normal(0, 1, n)
    elif kind == "sinusoid":
        x = np.sin(2.0 * np.pi * t / (n / 3.0)) + 0.05 * rng.normal(0, 1, n)
    elif kind == "sawtooth":
        period = max(8, n // 5)
        x = (t % period) / period + 0.03 * rng.normal(0, 1, n)
    else:  # pragma: no cover - guarded by typing
        raise ValueError(f"unknown strong-negative kind: {kind}")

    demand = _scale_to_demand(np.asarray(x, dtype=float))
    return pd.DataFrame({"t": np.arange(n), **_stable_ori(n, rng), "demand": demand})


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NegativeEntry:
    name: str
    kind: str
    family: str          # "smooth" | "stochastic" | "structured" | "bifurcation"
    label: int           # 0 = strong negative (must NOT fire), 1 = positive contrast
    df: pd.DataFrame


def strong_negatives_catalogue(n: int, seed: int) -> list[NegativeEntry]:
    """Build the full strong-negatives battery (negatives) + positive contrast."""
    entries: list[NegativeEntry] = []
    # Smooth accumulations (reuse the decisive trend-vs-transition negatives).
    for i, acc_kind in enumerate(NON_BIFURCATING):
        entries.append(NegativeEntry(f"smooth_{acc_kind}", acc_kind, "smooth", 0,
                                     gen_accumulation(acc_kind, n, seed + 300 + i)))
    # Stochastic traps.
    for i, sn_kind in enumerate(STOCHASTIC_NEGATIVES):
        entries.append(NegativeEntry(f"stoch_{sn_kind}", sn_kind, "stochastic", 0,
                                     gen_strong_negative(sn_kind, n, seed + 400 + i)))
    # Structured deterministic non-transition.
    for i, st_kind in enumerate(STRUCTURED_NEGATIVES):
        entries.append(NegativeEntry(f"struct_{st_kind}", st_kind, "structured", 0,
                                     gen_strong_negative(st_kind, n, seed + 500 + i)))
    # Positive contrast (must fire).
    for i, bif_kind in enumerate(BIFURCATING):
        entries.append(NegativeEntry(f"bif_{bif_kind}", bif_kind, "bifurcation", 1,
                                     gen_accumulation(bif_kind, n, seed + 600 + i)))
    return entries


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

@dataclass
class NegativeOutcome:
    name: str
    kind: str
    family: str
    label: int
    detector_fired: bool            # localized transition gate
    raw_detector_fired: bool        # bare sustained ΔC > μ+k·σ for m steps
    crossing_rate: float
    max_run: int
    surrogate_p: float | None       # IAAFT null p for the crossing rate (optional)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "family": self.family,
            "label": self.label,
            "detector_fired": self.detector_fired,
            "raw_detector_fired": self.raw_detector_fired,
            "crossing_rate": round(self.crossing_rate, 6),
            "max_run": self.max_run,
            "surrogate_p": (round(self.surrogate_p, 6) if self.surrogate_p is not None else None),
        }


def _verdict(strong_negatives_fpr: float, bifurcation_tpr: float) -> str:
    if bifurcation_tpr < TPR_MIN:
        return "STRONG_NEGATIVES_INSENSITIVE"
    if strong_negatives_fpr > FPR_MAX:
        return "STRONG_NEGATIVES_LEAK"
    return "STRONG_NEGATIVES_CLEAN"


def run_strong_negatives_suite(
    n: int = 220,
    seed: int = 1234,
    *,
    k: float = 2.5,
    m: int = 3,
    baseline_n: int = 30,
    n_surrogates: int = 0,
    run_fn: Callable | None = None,
) -> dict:
    """Run the strong-negatives battery through the real ORI-C detector.

    Returns a dict with per-entry outcomes and the decisive metrics:
      - ``strong_negatives_fpr``  : localized-gate fire rate over the negatives
                                    (LOWER is better; the headline specificity).
      - ``raw_strong_negatives_fpr`` : same for the bare sustained-crossing gate
                                    (expected high — shows what the localized gate
                                    must suppress).
      - ``bifurcation_tpr``       : localized-gate fire rate over the positive
                                    contrast (sensitivity guard).
      - ``verdict``               : STRONG_NEGATIVES_CLEAN / _LEAK / _INSENSITIVE.
    """
    from oric.surrogates import (  # local import (layout-tolerant, like accumulation_controls)
        localized_transition_statistic,
        surrogate_null_test,
        threshold_crossing_statistic,
    )
    try:
        from pipeline.ori_c_pipeline import ORICConfig, run_oric_from_observations  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover - layout-dependent
        from ori_c_pipeline import ORICConfig, run_oric_from_observations  # type: ignore
    if run_fn is None:
        run_fn = run_oric_from_observations

    cfg = ORICConfig(seed=seed, n_steps=n, intervention="none", k=k, m=m, baseline_n=baseline_n)
    catalogue = strong_negatives_catalogue(n, seed)
    rng = np.random.default_rng(seed + 9)

    outcomes: list[NegativeOutcome] = []
    for entry in catalogue:
        out = run_fn(entry.df, cfg)
        if "delta_C" not in out.columns:
            out = out.copy()
            out["delta_C"] = out["C"].diff().fillna(0.0)
        dc = out["delta_C"].to_numpy()
        cs = threshold_crossing_statistic(dc, k=k, m=m, baseline_n=baseline_n)
        loc = localized_transition_statistic(dc, k=k, m=m, baseline_n=baseline_n)

        surr_p: float | None = None
        if n_surrogates and n_surrogates > 0:
            res = surrogate_null_test(
                entry.df, cfg, n_surrogates=n_surrogates, statistic="crossing_rate",
                rng=rng, run_fn=run_fn,
            )
            surr_p = res.p_value

        outcomes.append(NegativeOutcome(
            name=entry.name, kind=entry.kind, family=entry.family, label=entry.label,
            detector_fired=loc.localized_hit, raw_detector_fired=cs.sustained_hit,
            crossing_rate=cs.crossing_rate, max_run=cs.max_run, surrogate_p=surr_p,
        ))

    neg = [o for o in outcomes if o.label == 0]
    pos = [o for o in outcomes if o.label == 1]
    strong_negatives_fpr = (sum(o.detector_fired for o in neg) / len(neg)) if neg else 0.0
    raw_fpr = (sum(o.raw_detector_fired for o in neg) / len(neg)) if neg else 0.0
    bifurcation_tpr = (sum(o.detector_fired for o in pos) / len(pos)) if pos else 0.0

    # Per-family false-positive breakdown (diagnostic).
    families = sorted({o.family for o in neg})
    by_family = {
        fam: round(
            sum(o.detector_fired for o in neg if o.family == fam)
            / max(1, sum(1 for o in neg if o.family == fam)),
            4,
        )
        for fam in families
    }

    verdict = _verdict(strong_negatives_fpr, bifurcation_tpr)
    return {
        "schema": "oric.strong_negatives.v1",
        "params": {"n": n, "seed": seed, "k": k, "m": m, "baseline_n": baseline_n,
                   "n_surrogates": n_surrogates},
        "thresholds": {"fpr_max": FPR_MAX, "tpr_min": TPR_MIN},
        "n_negatives": len(neg),
        "n_positives": len(pos),
        "strong_negatives_fpr": round(strong_negatives_fpr, 4),
        "raw_strong_negatives_fpr": round(raw_fpr, 4),
        "bifurcation_tpr": round(bifurcation_tpr, 4),
        "fpr_by_family": by_family,
        "verdict": verdict,
        "outcomes": [o.to_dict() for o in outcomes],
        "note": (
            "detector_fired is the conservative localized transition gate; "
            "raw_detector_fired is the bare sustained ΔC crossing kept for audit. "
            "A LEAK (localized FPR > fpr_max) is an honest negative reported at "
            "equal status to CLEAN."
        ),
    }
