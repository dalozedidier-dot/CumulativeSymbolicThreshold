"""surrogates.py — IAAFT surrogates and a null distribution for threshold crossing.

Motivation
----------
A raw statement such as "176/250 steps exceed the threshold ΔC > μ + k·σ" has no
evidential value without a null law: an autocorrelated or trending series will
cross a baseline-estimated threshold *mechanically*, simply because ΔC inherits
the spectrum/autocorrelation of its drivers. ORI-C's order variable is an
integrator,

    C(t+1) = C(t) + β·S(t) − γ·V(t),

so any persistent driver produces a non-trivial crossing rate even with no real
phase transition.

This module supplies the missing null distribution. Given a real series, we:

  1. run the ORI-C detector to obtain the observed crossing statistic;
  2. generate IAAFT surrogates of the *input* drivers (O, R, I, demand) that
     preserve, per channel, the amplitude distribution **and** the power spectrum
     (hence the full linear autocorrelation), while destroying nonlinear and
     cross-channel phase structure;
  3. re-run the *same* detector on each surrogate;
  4. report an empirical one-sided p-value
         p = (1 + #{stat_surrogate ≥ stat_observed}) / (n_surrogates + 1).

If the observed crossing rate is not significantly above the surrogate null, the
threshold crossing is explained by the linear (spectral) structure of the inputs
alone — i.e. ORI-C would be acting as a trend detector, not a transition
detector.

IAAFT
-----
Iterative Amplitude Adjusted Fourier Transform (Schreiber & Schmitz, 1996,
*Phys. Rev. Lett.* 77, 635). Unlike a single FFT phase randomization (which only
preserves the spectrum and an *approximate* marginal), IAAFT iterates between
the spectrum constraint and the exact rank/amplitude constraint, so the surrogate
has the original sample values to machine precision and a spectrum that matches
to within the convergence tolerance.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Sequence

import numpy as np
from scipy.ndimage import gaussian_filter1d


# ---------------------------------------------------------------------------
# IAAFT
# ---------------------------------------------------------------------------

def iaaft_surrogate(
    x: np.ndarray,
    *,
    n_iter: int = 100,
    rng: np.random.Generator | None = None,
    atol: float = 1e-8,
) -> np.ndarray:
    """Return one IAAFT surrogate of a 1-D series.

    The surrogate preserves:
      - the exact sample (amplitude) distribution of ``x`` (a permutation of it);
      - the power spectrum of ``x`` to within the iteration tolerance.

    Parameters
    ----------
    x : array
        Input series. NaNs are replaced by the series mean before processing.
    n_iter : int
        Maximum number of spectrum/amplitude reconciliation iterations.
    rng : np.random.Generator
        Source of randomness (the initial shuffle). Use a seeded generator for
        reproducibility.
    atol : float
        Convergence tolerance: stop when the rank ordering no longer changes.
    """
    rng = np.random.default_rng() if rng is None else rng
    x = np.asarray(x, dtype=float).copy()
    n = x.size
    if n < 4:
        return x.copy()

    if np.any(~np.isfinite(x)):
        x = np.where(np.isfinite(x), x, np.nanmean(x[np.isfinite(x)]) if np.any(np.isfinite(x)) else 0.0)

    if np.std(x) < atol:
        # Degenerate constant series: any permutation is identical.
        return x.copy()

    sorted_x = np.sort(x)
    target_amp = np.abs(np.fft.rfft(x))

    # Start from a random permutation of the data.
    r = rng.permutation(x)
    prev_ranks = None

    for _ in range(int(n_iter)):
        # (1) Impose the target power spectrum, keep current phases.
        phases = np.angle(np.fft.rfft(r))
        s = np.fft.irfft(target_amp * np.exp(1j * phases), n=n)
        # (2) Impose the exact amplitude distribution by rank matching.
        ranks = np.argsort(np.argsort(s))
        r = sorted_x[ranks]
        if prev_ranks is not None and np.array_equal(ranks, prev_ranks):
            break
        prev_ranks = ranks

    return r


def iaaft_surrogates(
    x: np.ndarray,
    n_surrogates: int,
    *,
    n_iter: int = 100,
    rng: np.random.Generator | None = None,
) -> list[np.ndarray]:
    """Generate ``n_surrogates`` independent IAAFT surrogates of ``x``."""
    rng = np.random.default_rng() if rng is None else rng
    return [iaaft_surrogate(x, n_iter=n_iter, rng=rng) for _ in range(int(n_surrogates))]


# ---------------------------------------------------------------------------
# Trend-preserving surrogate (harder null — research axis 5)
# ---------------------------------------------------------------------------

def trend_preserving_surrogate(
    x: np.ndarray,
    *,
    bandwidth: float,
    rng: np.random.Generator | None = None,
    n_iter: int = 100,
) -> np.ndarray:
    """Return a surrogate that **keeps the smooth trend** but scrambles the residual.

    A plain IAAFT surrogate of a trending series destroys the trend, so a test
    against it confounds "has a trend" with "has a transition". This surrogate
    instead decomposes ``x = trend + residual`` (Gaussian smooth of width
    ``bandwidth``), IAAFT-randomizes only the residual, and re-adds the original
    trend:

        surrogate = trend(x) + IAAFT(x − trend(x)).

    It therefore preserves the slow drift **and** the residual's amplitude
    distribution and power spectrum (its linear autocorrelation), while
    destroying the *time-localization* of the fluctuations — i.e. it removes
    critical slowing down and any localized rupture. A statistic that beats this
    null isolates the localized transition from the trend (Schreiber & Schmitz
    1996 for the residual surrogate; the trend split follows the standard
    early-warning detrending of Dakos et al. 2012).
    """
    x = np.asarray(x, dtype=float)
    trend = gaussian_filter1d(x, sigma=max(1e-6, float(bandwidth)), mode="reflect")
    resid = x - trend
    return trend + iaaft_surrogate(resid, n_iter=n_iter, rng=rng)


# ---------------------------------------------------------------------------
# General surrogate null test for a 1-D statistic (research axes 2 & 5)
# ---------------------------------------------------------------------------

@dataclass
class SeriesSurrogateResult:
    """Result of a generic one-sided surrogate null test on a 1-D series statistic."""
    statistic: str
    observed: float
    null_mean: float
    null_std: float
    null_q95: float
    null_q99: float
    p_value: float
    n_surrogates: int
    surrogate_kind: str
    significant_at_05: bool
    significant_at_01: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _make_series_surrogate(x, kind, rng, *, bandwidth, n_iter):
    if callable(kind):
        return np.asarray(kind(x, rng), dtype=float)
    if kind == "iaaft":
        return iaaft_surrogate(x, n_iter=n_iter, rng=rng)
    if kind == "trend_preserving":
        bw = bandwidth if bandwidth is not None else max(2.0, x.size / 10.0)
        return trend_preserving_surrogate(x, bandwidth=bw, rng=rng, n_iter=n_iter)
    raise ValueError(f"unknown surrogate kind: {kind!r}")


def series_surrogate_test(
    x: np.ndarray,
    statistic_fn: Callable[[np.ndarray], float],
    *,
    surrogate: str | Callable = "trend_preserving",
    n_surrogates: int = 200,
    rng: np.random.Generator | None = None,
    bandwidth: float | None = None,
    n_iter: int = 100,
    statistic_name: str = "statistic",
) -> SeriesSurrogateResult:
    """One-sided upper-tail surrogate null test for an arbitrary series statistic.

    ``statistic_fn`` maps a 1-D array to a scalar (e.g. the composite CSD trend).
    ``surrogate`` is ``"trend_preserving"``, ``"iaaft"``, or a callable
    ``(x, rng) -> surrogate``. Returns the empirical p-value
    ``p = (1 + #{stat_surr ≥ stat_obs}) / (n_surrogates + 1)``.
    """
    x = np.asarray(x, dtype=float)
    x = np.where(np.isfinite(x), x, 0.0)
    rng = np.random.default_rng() if rng is None else rng
    observed = float(statistic_fn(x))
    null = np.empty(int(n_surrogates), dtype=float)
    for j in range(int(n_surrogates)):
        surr = _make_series_surrogate(x, surrogate, rng, bandwidth=bandwidth, n_iter=n_iter)
        null[j] = float(statistic_fn(surr))
    n_ge = int(np.count_nonzero(null >= observed))
    p_value = (1 + n_ge) / (int(n_surrogates) + 1)
    kind_name = surrogate if isinstance(surrogate, str) else getattr(surrogate, "__name__", "callable")
    return SeriesSurrogateResult(
        statistic=statistic_name, observed=observed,
        null_mean=float(np.mean(null)), null_std=float(np.std(null)),
        null_q95=float(np.quantile(null, 0.95)), null_q99=float(np.quantile(null, 0.99)),
        p_value=float(p_value), n_surrogates=int(n_surrogates), surrogate_kind=kind_name,
        significant_at_05=bool(p_value < 0.05), significant_at_01=bool(p_value < 0.01),
    )


# ---------------------------------------------------------------------------
# Threshold-crossing statistic
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CrossingStatistic:
    """Crossing statistics for a ΔC series against a baseline-estimated threshold."""
    threshold: float
    baseline_mu: float
    baseline_sigma: float
    n_steps: int
    n_crossings: int
    crossing_rate: float
    max_run: int
    sustained_hit: bool  # True iff max_run >= m

    def to_dict(self) -> dict:
        return asdict(self)


def threshold_crossing_statistic(
    delta_C: Sequence[float] | np.ndarray,
    *,
    k: float = 2.5,
    m: int = 3,
    baseline_n: int = 30,
) -> CrossingStatistic:
    """Compute crossing statistics for ΔC > μ + k·σ.

    ``μ`` and ``σ`` are estimated on the first ``baseline_n`` points (the
    pre-registered ORI-C convention, mirroring ``ori_c_pipeline._detect_threshold``).
    """
    x = np.asarray(delta_C, dtype=float)
    x = np.where(np.isfinite(x), x, 0.0)
    n = int(x.size)
    if n == 0:
        return CrossingStatistic(0.0, 0.0, 0.0, 0, 0, 0.0, 0, False)

    bn = max(5, min(int(baseline_n), n))
    baseline = x[:bn]
    mu = float(np.mean(baseline))
    sd = float(np.std(baseline))  # population std (ddof=0), matches detector
    thr = mu + float(k) * sd

    above = x > thr
    n_cross = int(np.count_nonzero(above))

    # Longest run of consecutive crossings.
    max_run = 0
    run = 0
    for flag in above:
        if flag:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0

    return CrossingStatistic(
        threshold=thr,
        baseline_mu=mu,
        baseline_sigma=sd,
        n_steps=n,
        n_crossings=n_cross,
        crossing_rate=n_cross / n,
        max_run=int(max_run),
        sustained_hit=bool(max_run >= int(m)),
    )




@dataclass(frozen=True)
class LocalizedTransitionStatistic:
    """Localized-transition diagnostic built on top of ΔC.

    The raw ORI-C detector asks whether ΔC crosses a baseline threshold for m
    consecutive steps. That is necessary but not sufficient: a smooth
    accumulation can keep ΔC elevated for a long interval and therefore look
    like a sustained transition.

    This diagnostic adds a localization gate. It asks whether the positive
    acceleration of smoothed ΔC is concentrated in a short time window. A true
    regime transition should concentrate the change; a smooth trend should
    spread it across many steps.
    """

    crossing: CrossingStatistic
    smoothing_window: int
    acceleration_window: int
    acceleration_concentration: float
    acceleration_peak_fraction: float
    min_concentration: float
    localized_hit: bool

    def to_dict(self) -> dict:
        return {
            "crossing": self.crossing.to_dict(),
            "smoothing_window": self.smoothing_window,
            "acceleration_window": self.acceleration_window,
            "acceleration_concentration": self.acceleration_concentration,
            "acceleration_peak_fraction": self.acceleration_peak_fraction,
            "min_concentration": self.min_concentration,
            "localized_hit": self.localized_hit,
        }


def _rolling_median(x: np.ndarray, window: int) -> np.ndarray:
    """Small dependency-free centered rolling median."""
    n = int(x.size)
    if n == 0:
        return x.copy()
    w = max(1, int(window))
    if w % 2 == 0:
        w += 1
    half = w // 2
    out = np.empty(n, dtype=float)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out[i] = float(np.median(x[lo:hi]))
    return out


def localized_transition_statistic(
    delta_C: Sequence[float] | np.ndarray,
    *,
    k: float = 2.5,
    m: int = 3,
    baseline_n: int = 30,
    smoothing_window: int | None = None,
    acceleration_window: int | None = None,
    min_concentration: float = 0.45,
) -> LocalizedTransitionStatistic:
    """Return a sustained-crossing plus localization statistic for ΔC.

    The statistic intentionally remains conservative. It first requires the
    pre-existing sustained threshold crossing, then requires a localized burst
    in the first difference of smoothed ΔC. This rejects broad smooth trends
    that keep ΔC high for a long time but do not contain a concentrated change
    in regime.
    """
    x = np.asarray(delta_C, dtype=float)
    x = np.where(np.isfinite(x), x, 0.0)
    n = int(x.size)
    crossing = threshold_crossing_statistic(x, k=k, m=m, baseline_n=baseline_n)

    if n < 8:
        return LocalizedTransitionStatistic(
            crossing=crossing,
            smoothing_window=max(1, n),
            acceleration_window=max(1, n - 1),
            acceleration_concentration=0.0,
            acceleration_peak_fraction=0.0,
            min_concentration=float(min_concentration),
            localized_hit=False,
        )

    smooth_w = (
        int(smoothing_window) if smoothing_window is not None else max(5, round(n * 0.05))
    )
    if smooth_w % 2 == 0:
        smooth_w += 1
    acc_w = (
        int(acceleration_window)
        if acceleration_window is not None
        else max(5, round(n * 0.045))
    )

    smoothed = _rolling_median(x, smooth_w)
    acceleration = np.diff(smoothed)
    positive_acceleration = np.maximum(acceleration, 0.0)
    total = float(np.sum(positive_acceleration))

    if total <= 1e-12:
        concentration = 0.0
        peak_fraction = 0.0
    else:
        aw = max(1, min(int(acc_w), positive_acceleration.size))
        if positive_acceleration.size >= aw:
            window_sums = np.convolve(positive_acceleration, np.ones(aw), mode="valid")
            concentration = float(np.max(window_sums) / total)
        else:  # pragma: no cover - guarded above, kept for safety
            concentration = 1.0
        peak_fraction = float(np.max(positive_acceleration) / total)

    localized_hit = bool(crossing.sustained_hit and concentration >= float(min_concentration))
    return LocalizedTransitionStatistic(
        crossing=crossing,
        smoothing_window=int(smooth_w),
        acceleration_window=int(acc_w),
        acceleration_concentration=round(concentration, 6),
        acceleration_peak_fraction=round(peak_fraction, 6),
        min_concentration=float(min_concentration),
        localized_hit=localized_hit,
    )


# ---------------------------------------------------------------------------
# Surrogate null test on the ORI-C detector
# ---------------------------------------------------------------------------

@dataclass
class SurrogateNullResult:
    """Result of the IAAFT surrogate null test for threshold crossing."""
    statistic: str               # "crossing_rate" or "max_run"
    observed: float
    null_mean: float
    null_std: float
    null_q95: float
    null_q99: float
    null_max: float
    p_value: float               # one-sided upper-tail empirical p
    n_surrogates: int
    surrogate_columns: list[str]
    k: float
    m: int
    baseline_n: int
    significant_at_01: bool
    observed_crossing: dict      # full observed CrossingStatistic
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def surrogate_null_test(
    df_obs,
    cfg,
    *,
    n_surrogates: int = 200,
    statistic: str = "crossing_rate",
    surrogate_columns: Sequence[str] = ("O", "R", "I", "demand"),
    rng: np.random.Generator | None = None,
    n_iter: int = 100,
    run_fn=None,
):
    """IAAFT surrogate null test for the ORI-C threshold-crossing rate.

    Parameters
    ----------
    df_obs : pandas.DataFrame
        Observed series with at least t, O, R, I (and optionally demand, S).
    cfg : ORICConfig
        Detector configuration (supplies k, m, baseline_n).
    n_surrogates : int
        Number of IAAFT surrogates.
    statistic : {"crossing_rate", "max_run"}
        Statistic compared between the real series and the surrogate null.
    surrogate_columns : sequence of str
        Input channels to IAAFT-randomize independently. Each present column is
        surrogated; missing columns are skipped.
    rng : np.random.Generator
        Seeded generator for reproducibility.
    run_fn : callable
        Function (df, cfg) -> DataFrame with a ``delta_C`` column. Defaults to
        ``ori_c_pipeline.run_oric_from_observations`` (imported lazily to keep
        this module dependency-light).

    Returns
    -------
    SurrogateNullResult
    """
    if run_fn is None:
        try:  # pipeline.* (pytest / repo root) or flat (script dir) layout
            from pipeline.ori_c_pipeline import run_oric_from_observations as run_fn  # type: ignore
        except ModuleNotFoundError:  # pragma: no cover - layout-dependent
            from ori_c_pipeline import run_oric_from_observations as run_fn  # type: ignore

    rng = np.random.default_rng() if rng is None else rng
    df = df_obs.copy().reset_index(drop=True)

    k = float(getattr(cfg, "k", 2.5))
    m = int(getattr(cfg, "m", 3))
    baseline_n = int(getattr(cfg, "baseline_n", 30))

    cols = [c for c in surrogate_columns if c in df.columns]
    if not cols:
        raise ValueError(
            f"None of surrogate_columns={list(surrogate_columns)} present in df "
            f"(columns: {list(df.columns)})"
        )

    def _stat_from_df(d) -> tuple[float, CrossingStatistic]:
        out = run_fn(d, cfg)
        if "delta_C" not in out.columns:
            out = out.copy()
            out["delta_C"] = out["C"].diff().fillna(0.0)
        cs = threshold_crossing_statistic(
            out["delta_C"].to_numpy(), k=k, m=m, baseline_n=baseline_n
        )
        value = cs.crossing_rate if statistic == "crossing_rate" else float(cs.max_run)
        return value, cs

    observed_value, observed_cs = _stat_from_df(df)

    null_values = np.empty(int(n_surrogates), dtype=float)
    for j in range(int(n_surrogates)):
        surr = df.copy()
        for c in cols:
            surr[c] = iaaft_surrogate(df[c].to_numpy(dtype=float), n_iter=n_iter, rng=rng)
        null_values[j], _ = _stat_from_df(surr)

    # One-sided upper-tail empirical p-value (add-one for unbiasedness).
    n_ge = int(np.count_nonzero(null_values >= observed_value))
    p_value = (1 + n_ge) / (int(n_surrogates) + 1)

    return SurrogateNullResult(
        statistic=statistic,
        observed=float(observed_value),
        null_mean=float(np.mean(null_values)),
        null_std=float(np.std(null_values)),
        null_q95=float(np.quantile(null_values, 0.95)),
        null_q99=float(np.quantile(null_values, 0.99)),
        null_max=float(np.max(null_values)),
        p_value=float(p_value),
        n_surrogates=int(n_surrogates),
        surrogate_columns=cols,
        k=k,
        m=m,
        baseline_n=baseline_n,
        significant_at_01=bool(p_value < 0.01),
        observed_crossing=observed_cs.to_dict(),
        notes=(
            "IAAFT surrogates preserve per-channel amplitude distribution and power "
            "spectrum; p is the one-sided upper-tail probability that a spectrally "
            "matched surrogate reaches the observed crossing statistic."
        ),
    )
