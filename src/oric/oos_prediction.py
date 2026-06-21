"""oos_prediction.py — Pre-registered out-of-sample directional prediction (axis 3).

The repository's T3 is INDETERMINATE and, as ``docs/EVIDENTIARY_STATUS.md`` §4
notes, a naive out-of-sample *crossing* prediction inherits the trend confound:
predicting "C keeps rising" is trivially satisfied by any integrator. The honest
OOS test must instead predict a **localized regime change** from the early-warning
signal, on data held out before the transition, and be scored against the actual
onset — and it must *not* fire when there is no transition.

Protocol
--------
Given a series, split at ``train_end`` (strictly before any transition). From the
training portion alone:

  1. decide whether a transition is coming, via the trend-preserving CSD surrogate
     null (:func:`oric.early_warning.csd_surrogate_test`) — significant ⇒ predict
     a transition;
  2. estimate its *timing* by extrapolating the rolling lag-1 autocorrelation
     (which → 1 at a fold) to a high target, giving a predicted onset index.

The prediction is then scored against the held-out truth as a hit, miss,
false alarm, or correct rejection. A genuine bistable approach should yield hits;
its linear twin (no transition) should yield correct rejections.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .early_warning import (
    csd_surrogate_test,
    gaussian_detrend,
    kendall_trend,
    rolling_autocorr1,
)


@dataclass
class TransitionPrediction:
    predicted: bool
    p_value: float
    composite_tau: float
    ar1_slope: float
    ar1_intercept: float
    predicted_onset: int | None
    train_end: int
    ar1_target: float

    def to_dict(self) -> dict:
        return asdict(self)


def predict_transition(
    x_train: np.ndarray,
    *,
    window: int | None = None,
    bandwidth: float | None = None,
    n_surrogates: int = 199,
    alpha: float = 0.05,
    ar1_target: float = 0.95,
    rng: np.random.Generator | None = None,
) -> TransitionPrediction:
    """Predict (yes/no + approximate onset) an upcoming transition from training data.

    The yes/no decision is the trend-preserving CSD surrogate null at level
    ``alpha``; the onset estimate linearly extrapolates the rolling AR(1) to
    ``ar1_target`` (returns ``None`` if AR(1) is not rising).
    """
    x_train = np.asarray(x_train, dtype=float)
    n = x_train.size
    win = int(window) if window is not None else max(10, n // 4)
    bw = float(bandwidth) if bandwidth is not None else max(2.0, n / 14.0)

    res = csd_surrogate_test(x_train, window=win, bandwidth=bw,
                             n_surrogates=n_surrogates, rng=rng)
    predicted = bool(res.p_value < alpha)

    # Timing: extrapolate rolling AR(1) (which rises toward 1 at a fold).
    resid = gaussian_detrend(x_train, bw)
    ar1 = rolling_autocorr1(resid, win)
    predicted_onset: int | None = None
    slope = intercept = 0.0
    if ar1.size >= 3:
        t_idx = np.arange(ar1.size, dtype=float)
        slope, intercept = np.polyfit(t_idx, ar1, 1)
        tau_ar1, _ = kendall_trend(ar1)
        if predicted and slope > 1e-6 and tau_ar1 > 0:
            t_hit = (ar1_target - intercept) / slope          # index within the AR(1) series
            onset = int(round(t_hit)) + (win - 1)             # map back to series index
            predicted_onset = max(n, onset)                   # must be in the held-out future

    return TransitionPrediction(
        predicted=predicted, p_value=res.p_value, composite_tau=res.observed,
        ar1_slope=float(slope), ar1_intercept=float(intercept),
        predicted_onset=predicted_onset, train_end=n, ar1_target=ar1_target,
    )


@dataclass
class PredictionScore:
    outcome: str                 # hit | miss | false_alarm | correct_rejection
    predicted: bool
    has_transition: bool
    timing_error: int | None     # |predicted_onset − actual_onset| when both defined

    def to_dict(self) -> dict:
        return asdict(self)


def score_prediction(
    pred: TransitionPrediction,
    actual_onset: int | None,
    *,
    timing_tolerance: int = 150,
) -> PredictionScore:
    """Score a prediction against held-out truth.

    ``actual_onset`` is the true transition index, or ``None`` if the held-out
    series has no transition. A prediction is a *hit* only if a transition is
    both predicted and real; if a timing estimate exists it must fall within
    ``timing_tolerance`` of the truth.
    """
    has_transition = actual_onset is not None
    timing_error: int | None = None
    if pred.predicted and has_transition:
        if pred.predicted_onset is not None:
            timing_error = int(abs(pred.predicted_onset - int(actual_onset)))
            outcome = "hit" if timing_error <= int(timing_tolerance) else "miss"
        else:
            outcome = "hit"  # correct direction, no timing estimate
    elif pred.predicted and not has_transition:
        outcome = "false_alarm"
    elif not pred.predicted and has_transition:
        outcome = "miss"
    else:
        outcome = "correct_rejection"
    return PredictionScore(
        outcome=outcome, predicted=pred.predicted, has_transition=has_transition,
        timing_error=timing_error,
    )
