"""accumulation_controls.py — The decisive negative control for ORI-C.

Why this exists
---------------
ORI-C's order variable is an integrator:

    C(t+1) = C(t) + β·S(t) − γ·V(t),

and S(t) itself accumulates from symbolic pressure. Any **monotone** driver
therefore yields a growing, "self-reinforcing" C(t), and the criterion
ΔC > μ + k·σ can fire from sheer accumulation rather than from a genuine phase
transition in the world. The existing T9 negative controls (white/pink/red
noise, random walk, sinusoid, Poisson, chaotic logistic map) are all stationary,
oscillatory, or chaotic — **none** is a smooth, saturating, monotone accumulation.
So they cannot separate ORI-C's stated hypothesis (it detects a *bifurcation*)
from its trivial rival (it is a *trend/accumulation* detector).

This module supplies the missing controls:

  Non-bifurcating accumulations (label 0 — ORI-C must NOT flag a transition)
    - logistic_growth        : saturating S-curve (growth, NOT the chaotic map)
    - gompertz               : asymmetric saturating growth
    - exponential_saturation : bounded exponential approach to an asymptote
    - linear_ramp            : noisy monotone linear trend (no saturation, no break)

  Genuine bifurcations (label 1 — ORI-C SHOULD flag a transition) — contrast set
    - sharp_regime_switch    : flat → steep localized jump → new flat level
    - delayed_bifurcation    : long quiescence then an abrupt transition

Falsification logic (frozen ex ante, see 02_Protocol addendum)
--------------------------------------------------------------
  * If ORI-C's detector fires a *sustained* crossing on the smooth
    non-bifurcating accumulations (i.e. false-positive rate above the frozen
    ceiling), the hypothesis is **refuted in its current form**: the detector
    cannot be distinguished from a trend detector.
  * If ORI-C rejects the smooth accumulations while still flagging the genuine
    bifurcations, that separation is the strongest single piece of evidence for
    the hypothesis.

The series here drive the ORI-C pipeline through ``demand`` (with stable O, R, I),
so the accumulation enters via Σ = max(0, demand − Cap) → S → C exactly as on
real data, exercising the real detector path (``auto_scale=True``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import numpy as np
import pandas as pd


AccumulationKind = Literal[
    "logistic_growth",
    "gompertz",
    "exponential_saturation",
    "linear_ramp",
    "sharp_regime_switch",
    "delayed_bifurcation",
]

# Smooth, monotone, single-curvature, no regime break → must read as NEGATIVE.
NON_BIFURCATING: tuple[AccumulationKind, ...] = (
    "logistic_growth",
    "gompertz",
    "exponential_saturation",
    "linear_ramp",
)
# Localized regime change → genuine transition, the positive contrast.
BIFURCATING: tuple[AccumulationKind, ...] = (
    "sharp_regime_switch",
    "delayed_bifurcation",
)


# ---------------------------------------------------------------------------
# Pure curve shapes (monotone, bounded unless noted), normalized to ~[lo, hi]
# ---------------------------------------------------------------------------

def logistic_growth(t: np.ndarray, lo: float, hi: float, midpoint: float, rate: float) -> np.ndarray:
    """Saturating S-curve in [lo, hi] with a single inflection at ``midpoint``."""
    return lo + (hi - lo) / (1.0 + np.exp(-rate * (t - midpoint)))


def gompertz(t: np.ndarray, lo: float, hi: float, b: float, c: float) -> np.ndarray:
    """Gompertz growth: asymmetric saturation, fast-then-slow, single curvature."""
    return lo + (hi - lo) * np.exp(-b * np.exp(-c * t))


def exponential_saturation(t: np.ndarray, lo: float, hi: float, rate: float) -> np.ndarray:
    """Bounded exponential approach to an asymptote (fastest rate at t=0)."""
    return hi - (hi - lo) * np.exp(-rate * t)


def linear_ramp(t: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Constant-rate monotone trend (no saturation, no break)."""
    n = t.size
    span = max(1, n - 1)
    return lo + (hi - lo) * (t / span)


def sharp_regime_switch(t: np.ndarray, lo: float, hi: float, switch_frac: float, sharpness: float) -> np.ndarray:
    """Flat at ``lo`` → steep localized jump → flat at ``hi`` (a genuine break)."""
    n = t.size
    mid = switch_frac * (n - 1)
    return lo + (hi - lo) / (1.0 + np.exp(-sharpness * (t - mid)))


# ---------------------------------------------------------------------------
# Series generators (t, O, R, I, demand)
# ---------------------------------------------------------------------------

def _stable_ori(n: int, rng: np.random.Generator, base: tuple[float, float, float] = (0.62, 0.66, 0.58),
                noise: float = 0.015) -> dict[str, np.ndarray]:
    """Stable O, R, I proxies (near-constant Cap), gentle stationary noise only.

    Crucially these carry **no** trend and **no** break, so all monotone /
    transition structure lives in ``demand`` — the test is clean.
    """
    return {
        "O": np.clip(base[0] + rng.normal(0, noise, n), 0.05, 0.95),
        "R": np.clip(base[1] + rng.normal(0, noise, n), 0.05, 0.95),
        "I": np.clip(base[2] + rng.normal(0, noise, n), 0.05, 0.95),
    }


def gen_accumulation(kind: AccumulationKind, n: int, seed: int, *, noise_frac: float = 0.02) -> pd.DataFrame:
    """Generate one (t, O, R, I, demand) control of the requested ``kind``.

    The ``demand`` driver spans a fixed dynamic range so that, after the
    pipeline's median auto-scaling of Cap, Σ = max(0, demand − Cap) turns on in
    the upper part of the trajectory — i.e. the accumulation/transition occurs
    on-series, exercising the detector.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=float)
    ori = _stable_ori(n, rng)

    lo, hi = 0.55, 1.55  # demand range (arbitrary units; pipeline auto-scales Cap)

    # Fair-design rule (frozen): every control is quiescent during the
    # baseline-estimation window and exhibits its monotone rise / regime change
    # in mid-series, so the *only* systematic difference between a non-bifurcating
    # accumulation and a genuine bifurcation is smoothness vs a localized break —
    # not the position of the change relative to the baseline. (linear_ramp is the
    # deliberate exception: a constant-rate global trend whose baseline already
    # contains the trend, i.e. the canonical "pure trend, no transition" case.)
    if kind == "logistic_growth":
        # Quiescent → accelerate → saturate; inflection mid-series (hardest case).
        d = logistic_growth(t, lo, hi, midpoint=0.55 * n, rate=12.0 / n)
    elif kind == "gompertz":
        # Inflection ≈ 0.5·n (b = e^{c·0.5n}, c = 8/n), quiescent through baseline.
        d = gompertz(t, lo, hi, b=float(np.exp(4.0)), c=8.0 / n)
    elif kind == "exponential_saturation":
        # Delayed bounded exponential: flat until 0.45·n, then decelerating approach.
        t_d = 0.45 * n
        d = np.where(t < t_d, lo, exponential_saturation(t - t_d, lo, hi, rate=8.0 / n))
    elif kind == "linear_ramp":
        # Constant-rate monotone global trend (baseline contains the same slope).
        d = linear_ramp(t, lo, hi)
    elif kind == "sharp_regime_switch":
        d = sharp_regime_switch(t, lo, hi, switch_frac=0.55, sharpness=60.0 / n)
    elif kind == "delayed_bifurcation":
        d = sharp_regime_switch(t, lo, hi, switch_frac=0.70, sharpness=80.0 / n)
    else:  # pragma: no cover - guarded by typing
        raise ValueError(f"unknown accumulation kind: {kind}")

    demand = d * (1.0 + rng.normal(0, noise_frac, n))
    return pd.DataFrame({"t": np.arange(n), **ori, "demand": demand})


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ControlEntry:
    name: str
    kind: AccumulationKind
    label: int          # 0 = non-bifurcating accumulation, 1 = genuine bifurcation
    df: pd.DataFrame

    @property
    def is_non_bifurcating(self) -> bool:
        return self.label == 0


def accumulation_control_catalogue(n: int, seed: int) -> list[ControlEntry]:
    """Build the full decisive-control catalogue (4 negatives + 2 positives)."""
    entries: list[ControlEntry] = []
    for i, kind in enumerate(NON_BIFURCATING):
        entries.append(ControlEntry(f"acc_{kind}", kind, 0, gen_accumulation(kind, n, seed + 100 + i)))
    for i, kind in enumerate(BIFURCATING):
        entries.append(ControlEntry(f"bif_{kind}", kind, 1, gen_accumulation(kind, n, seed + 200 + i)))
    return entries


# ---------------------------------------------------------------------------
# Decisive suite runner
# ---------------------------------------------------------------------------

@dataclass
class ControlOutcome:
    name: str
    kind: str
    label: int
    detector_fired: bool                # sustained ΔC > μ+k·σ for m steps
    crossing_rate: float
    max_run: int
    surrogate_p_rate: float | None      # IAAFT null p for the crossing rate
    surrogate_p_maxrun: float | None    # IAAFT null p for the longest sustained run
    surrogate_significant: bool | None  # any statistic significant at α=0.01

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "label": self.label,
            "detector_fired": self.detector_fired,
            "crossing_rate": round(self.crossing_rate, 6),
            "max_run": self.max_run,
            "surrogate_p_rate": (round(self.surrogate_p_rate, 6) if self.surrogate_p_rate is not None else None),
            "surrogate_p_maxrun": (round(self.surrogate_p_maxrun, 6) if self.surrogate_p_maxrun is not None else None),
            "surrogate_significant": self.surrogate_significant,
        }


def run_accumulation_control_suite(
    n: int = 220,
    seed: int = 1234,
    *,
    k: float = 2.5,
    m: int = 3,
    baseline_n: int = 30,
    n_surrogates: int = 0,
    run_fn: Callable | None = None,
) -> dict:
    """Run the decisive accumulation-vs-bifurcation discrimination.

    For every control we run the *real* ORI-C detector and record whether it
    fires a sustained threshold crossing. Optionally (``n_surrogates > 0``) we
    also attach the IAAFT surrogate-null p-value for the crossing rate.

    Returns a dict with per-control outcomes and the decisive metrics:
      - ``accumulation_fpr``: fraction of non-bifurcating accumulations that the
        detector (wrongly) flags as a sustained transition. **Lower is better;**
        a high value refutes the hypothesis in its current form.
      - ``bifurcation_tpr``: fraction of genuine bifurcations correctly flagged.
      - ``separates``: True iff every non-bifurcating accumulation is rejected
        AND every genuine bifurcation is flagged.
    """
    from oric.surrogates import threshold_crossing_statistic, surrogate_null_test  # local
    try:  # importable as pipeline.* (pytest / repo root on path) or flat (script dir on path)
        from pipeline.ori_c_pipeline import ORICConfig, run_oric_from_observations
    except ModuleNotFoundError:  # pragma: no cover - layout-dependent
        from ori_c_pipeline import ORICConfig, run_oric_from_observations  # type: ignore
    if run_fn is None:
        run_fn = run_oric_from_observations

    cfg = ORICConfig(seed=seed, n_steps=n, intervention="none", k=k, m=m, baseline_n=baseline_n)
    catalogue = accumulation_control_catalogue(n, seed)
    rng = np.random.default_rng(seed + 7)

    outcomes: list[ControlOutcome] = []
    for entry in catalogue:
        out = run_fn(entry.df, cfg)
        if "delta_C" not in out.columns:
            out = out.copy()
            out["delta_C"] = out["C"].diff().fillna(0.0)
        cs = threshold_crossing_statistic(out["delta_C"].to_numpy(), k=k, m=m, baseline_n=baseline_n)

        surr_p_rate: float | None = None
        surr_p_maxrun: float | None = None
        surr_sig: bool | None = None
        if n_surrogates and n_surrogates > 0:
            res_rate = surrogate_null_test(
                entry.df, cfg, n_surrogates=n_surrogates, statistic="crossing_rate",
                rng=rng, run_fn=run_fn,
            )
            res_run = surrogate_null_test(
                entry.df, cfg, n_surrogates=n_surrogates, statistic="max_run",
                rng=rng, run_fn=run_fn,
            )
            surr_p_rate = res_rate.p_value
            surr_p_maxrun = res_run.p_value
            surr_sig = bool(res_rate.significant_at_01 or res_run.significant_at_01)

        outcomes.append(ControlOutcome(
            name=entry.name, kind=entry.kind, label=entry.label,
            detector_fired=cs.sustained_hit, crossing_rate=cs.crossing_rate,
            max_run=cs.max_run, surrogate_p_rate=surr_p_rate,
            surrogate_p_maxrun=surr_p_maxrun, surrogate_significant=surr_sig,
        ))

    neg = [o for o in outcomes if o.label == 0]
    pos = [o for o in outcomes if o.label == 1]
    accumulation_fpr = (sum(o.detector_fired for o in neg) / len(neg)) if neg else 0.0
    bifurcation_tpr = (sum(o.detector_fired for o in pos) / len(pos)) if pos else 0.0
    separates = all(not o.detector_fired for o in neg) and all(o.detector_fired for o in pos)

    return {
        "schema": "oric.accumulation_control.v1",
        "params": {"n": n, "seed": seed, "k": k, "m": m, "baseline_n": baseline_n,
                   "n_surrogates": n_surrogates},
        "outcomes": [o.to_dict() for o in outcomes],
        "accumulation_fpr": round(accumulation_fpr, 4),
        "bifurcation_tpr": round(bifurcation_tpr, 4),
        "separates": bool(separates),
    }
