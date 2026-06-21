"""early_warning.py — Critical-slowing-down as the *primary* ORI-C detector.

Rationale (research axis 2)
---------------------------
The ΔC crossing statistic is, by construction, a property of an integrator: a
smooth monotone driver makes ΔC stay elevated and the gate fire, so the crossing
is largely the driver's own structure. Bifurcation theory predicts a different,
*falsifiable* signature that a trend cannot fake: as a dynamical system
approaches a fold, the dominant eigenvalue → 0, recovery from perturbations slows,
and the state's **lag-1 autocorrelation and variance rise** *before* the jump
(Scheffer et al. 2009, *Nature* 461:53; Dakos et al. 2012). A pure trend or a
smooth saturating accumulation has no weakening restoring force, so it shows no
such rise.

This module makes critical slowing down (CSD) the primary detector:

  1. detrend the series (Gaussian kernel) so the indicators measure fluctuation
     dynamics, not the trend itself — the step the bare ``early_warning_signal``
     in ``comparative_benchmark`` omits;
  2. compute rolling lag-1 autocorrelation and variance of the residuals;
  3. summarise each indicator's rising trend with Kendall's τ (a *statistic*);
  4. **decide** significance with :func:`csd_surrogate_test`, comparing the
     composite τ to a **trend-preserving** surrogate null — because the bare
     Kendall p-value is anticonservative under autocorrelation (a single
     white-noise run can show a large spurious τ). On clean trend+AR(1) nulls the
     surrogate test controls the false-positive rate at the nominal level.

For an honest pre-transition test, restrict the indicators to the data *before*
the transition (:func:`early_warning_before_jump`): the detector must warn from
the run-up alone, never from the jump itself.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats
from scipy.ndimage import gaussian_filter1d


# ---------------------------------------------------------------------------
# Detrending and rolling indicators
# ---------------------------------------------------------------------------

def gaussian_detrend(x: np.ndarray, bandwidth: float) -> np.ndarray:
    """Return residuals of ``x`` after subtracting a Gaussian-kernel trend.

    The trend is a Gaussian smooth (standard deviation ``bandwidth`` in samples)
    with reflecting edges — the standard CSD detrending that isolates short-term
    fluctuations from the slow drift without the edge bias of a naive weighted
    mean.
    """
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return x.copy()
    bw = max(1e-6, float(bandwidth))
    trend = gaussian_filter1d(x, sigma=bw, mode="reflect")
    return x - trend


def rolling_variance(x: np.ndarray, window: int) -> np.ndarray:
    """Variance in each trailing window of length ``window`` (vectorized)."""
    x = np.asarray(x, dtype=float)
    if x.size < window:
        return np.empty(0, dtype=float)
    w = np.lib.stride_tricks.sliding_window_view(x, window)
    return w.var(axis=1)


def rolling_autocorr1(x: np.ndarray, window: int) -> np.ndarray:
    """Lag-1 autocorrelation in each trailing window of length ``window`` (vectorized)."""
    x = np.asarray(x, dtype=float)
    if x.size < window or window < 3:
        return np.zeros(max(0, x.size - window + 1), dtype=float)
    w = np.lib.stride_tricks.sliding_window_view(x, window)
    a = w[:, :-1]
    b = w[:, 1:]
    a_c = a - a.mean(axis=1, keepdims=True)
    b_c = b - b.mean(axis=1, keepdims=True)
    cov = np.einsum("ij,ij->i", a_c, b_c)
    denom = np.sqrt(np.einsum("ij,ij->i", a_c, a_c) * np.einsum("ij,ij->i", b_c, b_c))
    out = np.zeros(w.shape[0], dtype=float)
    nz = denom > 1e-12
    out[nz] = cov[nz] / denom[nz]
    return out


def kendall_trend(y: np.ndarray) -> tuple[float, float]:
    """Kendall's τ (and p) of ``y`` against the time index. (0, 1) if degenerate."""
    y = np.asarray(y, dtype=float)
    if y.size < 3 or np.allclose(y, y[0]):
        return 0.0, 1.0
    tau, p = stats.kendalltau(np.arange(y.size), y)
    if not np.isfinite(tau):
        return 0.0, 1.0
    return float(tau), float(p)


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

@dataclass
class EarlyWarningResult:
    """Descriptive critical-slowing-down indicators for one series.

    This is a *statistic*, not a verdict: the Kendall-τ p-values assume
    independent indicator samples and are anticonservative under autocorrelation,
    so they must not be used as a stand-alone detection gate (a single white-noise
    realization can show a large spurious τ). Use :func:`csd_surrogate_test` for
    an inferential decision with calibrated false-positive control.
    """
    tau_ar1: float
    p_ar1: float
    tau_var: float
    p_var: float
    composite_tau: float          # mean of the two τ's (ranking score)
    n: int
    window: int
    bandwidth: float

    def to_dict(self) -> dict:
        return {
            "tau_ar1": round(self.tau_ar1, 6), "p_ar1": round(self.p_ar1, 6),
            "tau_var": round(self.tau_var, 6), "p_var": round(self.p_var, 6),
            "composite_tau": round(self.composite_tau, 6),
            "n": self.n, "window": self.window, "bandwidth": round(self.bandwidth, 4),
        }


def early_warning(
    x: np.ndarray,
    *,
    window: int | None = None,
    bandwidth: float | None = None,
    detrend: bool = True,
) -> EarlyWarningResult:
    """Compute the critical-slowing-down indicators (rising AR(1) and variance).

    Returns the Kendall-τ trend of the rolling lag-1 autocorrelation and variance
    of the detrended series, plus their mean ``composite_tau``. Descriptive only —
    see :func:`csd_surrogate_test` for the inferential test.
    """
    x = np.asarray(x, dtype=float)
    x = np.where(np.isfinite(x), x, 0.0)
    n = x.size
    win = int(window) if window is not None else max(10, n // 5)
    bw = float(bandwidth) if bandwidth is not None else max(2.0, n / 10.0)

    if n < 2 * win + 2:
        return EarlyWarningResult(0.0, 1.0, 0.0, 1.0, 0.0, n, win, bw)

    resid = gaussian_detrend(x, bw) if detrend else x
    ar1 = rolling_autocorr1(resid, win)
    var = rolling_variance(resid, win)
    tau_ar1, p_ar1 = kendall_trend(ar1)
    tau_var, p_var = kendall_trend(var)

    return EarlyWarningResult(
        tau_ar1=tau_ar1, p_ar1=p_ar1, tau_var=tau_var, p_var=p_var,
        composite_tau=0.5 * (tau_ar1 + tau_var), n=n, window=win, bandwidth=bw,
    )


def composite_csd_statistic(
    x: np.ndarray, *, window: int, bandwidth: float, detrend: bool = True
) -> float:
    """Scalar critical-slowing-down statistic: mean of the AR(1) and variance τ's."""
    return early_warning(x, window=window, bandwidth=bandwidth, detrend=detrend).composite_tau


def csd_surrogate_test(
    x: np.ndarray,
    *,
    window: int | None = None,
    bandwidth: float | None = None,
    detrend: bool = True,
    n_surrogates: int = 200,
    rng: np.random.Generator | None = None,
    n_iter: int = 100,
):
    """Rigorous CSD detector: test the composite CSD statistic against a
    **trend-preserving** surrogate null.

    The bare Kendall-τ p-value is anticonservative on autocorrelated indicator
    series, so significance is assessed against surrogates that keep the trend
    and the residual spectrum but destroy critical slowing down. On clean
    trend+AR(1) nulls this controls the false-positive rate at the nominal level;
    a bistable fold approach beats it, a smooth accumulation does not.

    Returns a :class:`oric.surrogates.SeriesSurrogateResult`.
    """
    from oric.surrogates import series_surrogate_test

    x = np.asarray(x, dtype=float)
    n = x.size
    win = int(window) if window is not None else max(10, n // 4)
    bw = float(bandwidth) if bandwidth is not None else max(2.0, n / 14.0)

    def stat(s: np.ndarray) -> float:
        return composite_csd_statistic(s, window=win, bandwidth=bw, detrend=detrend)

    return series_surrogate_test(
        x, stat, surrogate="trend_preserving", n_surrogates=n_surrogates,
        rng=rng, bandwidth=bw, n_iter=n_iter, statistic_name="csd_composite_tau",
    )


def find_jump(x: np.ndarray) -> int:
    """Index of the largest single-step increase in ``x`` (the transition)."""
    x = np.asarray(x, dtype=float)
    if x.size < 2:
        return 0
    return int(np.argmax(np.diff(x)) + 1)


def early_warning_before_jump(
    x: np.ndarray,
    *,
    jump_index: int | None = None,
    margin: int = 2,
    **kwargs,
) -> EarlyWarningResult:
    """Run :func:`early_warning` on the pre-transition segment only.

    The transition (``jump_index`` or the largest single-step rise) and a small
    ``margin`` are excluded, so the warning must come from the run-up alone.
    """
    x = np.asarray(x, dtype=float)
    j = int(jump_index) if jump_index is not None else find_jump(x)
    cut = max(0, j - int(margin))
    return early_warning(x[:cut] if cut >= 4 else x, **kwargs)
