"""effect_size.py — Effect size vs SESOI + achieved power for real-data reporting.

On real, under-/borderline-powered series, a p-value is the wrong thing to report:
a large N drives p toward 0 with no bearing on whether the effect is meaningful,
and an underpowered INDETERMINATE is *not* evidence of absence. The reporting rule
(see 02_Protocol addendum) is therefore:

    On real data, report the **effect size vs the SESOI** with a 99 % CI and the
    **achieved power** — never the p-value as the decision.

This module computes that triplet for the ORI-C order variable C (post-threshold
vs pre-threshold), using the frozen SESOI (`sesoi_c_robust_sd = 0.30` robust SDs)
and the frozen power gate (`power_gate_min = 0.70`).

Verdict tokens (decision is effect-vs-SESOI + power, never p):
  - UNDERPOWERED        : power to detect the SESOI < power_gate → indeterminate
  - EFFECT_EXCEEDS_SESOI: |standardised effect| ≥ SESOI and the 99 % CI lower
                          bound is also ≥ SESOI (robust to sampling)
  - EFFECT_BELOW_SESOI  : adequately powered but the effect is below the SESOI
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


def _robust_sd(x: np.ndarray) -> float:
    """Median absolute deviation scaled to a Gaussian SD estimate."""
    x = np.asarray(x, dtype=float)
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    return 1.4826 * mad


def cohens_d(pre: np.ndarray, post: np.ndarray) -> float:
    """Cohen's d with pooled standard deviation."""
    pre = np.asarray(pre, dtype=float)
    post = np.asarray(post, dtype=float)
    n1, n2 = pre.size, post.size
    if n1 < 2 or n2 < 2:
        return 0.0
    s1, s2 = float(np.var(pre, ddof=1)), float(np.var(post, ddof=1))
    pooled = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
    if pooled < 1e-12:
        return 0.0
    return float((np.mean(post) - np.mean(pre)) / pooled)


def hedges_g(pre: np.ndarray, post: np.ndarray) -> float:
    """Bias-corrected standardised mean difference (small-sample correction)."""
    d = cohens_d(pre, post)
    n = np.asarray(pre).size + np.asarray(post).size
    if n <= 2:
        return d
    correction = 1.0 - 3.0 / (4.0 * (n) - 9.0)
    return float(d * correction)


def achieved_power(d: float, n1: int, n2: int, alpha: float = 0.01) -> float:
    """Achieved power of a two-sided two-sample t-test for effect size ``d``."""
    from scipy.stats import nct, norm, t

    n1, n2 = int(n1), int(n2)
    if n1 < 2 or n2 < 2:
        return 0.0
    nu = n1 + n2 - 2
    ncp = float(d) * np.sqrt(n1 * n2 / (n1 + n2))
    tcrit = t.ppf(1 - alpha / 2.0, nu)
    power = float(1 - nct.cdf(tcrit, nu, ncp) + nct.cdf(-tcrit, nu, ncp))
    if not np.isfinite(power):
        # scipy's noncentral t can return NaN for large df; use the normal approx.
        zc = float(norm.ppf(1 - alpha / 2.0))
        power = float(1 - norm.cdf(zc - ncp) + norm.cdf(-zc - ncp))
    return float(np.clip(power, 0.0, 1.0))


@dataclass
class EffectSizeReport:
    n_pre: int
    n_post: int
    mean_pre: float
    mean_post: float
    raw_effect: float
    robust_sd: float
    sesoi_robust_sd: float          # SESOI in robust-SD units (frozen 0.30)
    standardised_effect: float      # raw_effect / robust_sd
    hedges_g: float
    ci_low: float                   # 99% bootstrap CI on standardised effect
    ci_high: float
    achieved_power_at_observed: float
    achieved_power_at_sesoi: float
    power_gate: float
    alpha: float
    ci_level: float
    verdict: str
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def effect_size_report(
    pre: np.ndarray,
    post: np.ndarray,
    *,
    sesoi_robust_sd: float = 0.30,
    alpha: float = 0.01,
    ci_level: float = 0.99,
    power_gate: float = 0.70,
    bootstrap_B: int = 2000,
    rng: np.random.Generator | None = None,
) -> EffectSizeReport:
    """Report the effect of ``post`` vs ``pre`` against the SESOI, with power.

    The p-value is deliberately not part of the decision. ``sesoi_robust_sd`` is
    expressed in robust-SD units (the frozen ORI-C convention).
    """
    rng = np.random.default_rng() if rng is None else rng
    pre = np.asarray(pre, dtype=float)
    post = np.asarray(post, dtype=float)
    n1, n2 = int(pre.size), int(post.size)

    combined = np.concatenate([pre, post]) if (n1 + n2) else np.array([0.0])
    rsd = _robust_sd(combined)
    rsd = rsd if rsd > 1e-12 else (float(np.std(combined)) or 1.0)

    raw_effect = float(np.mean(post) - np.mean(pre)) if (n1 and n2) else 0.0
    standardised = raw_effect / rsd
    g = hedges_g(pre, post)

    # Bootstrap CI on the standardised effect.
    if n1 >= 2 and n2 >= 2:
        boots = np.empty(int(bootstrap_B), dtype=float)
        for b in range(int(bootstrap_B)):
            rp = rng.choice(pre, size=n1, replace=True)
            rq = rng.choice(post, size=n2, replace=True)
            denom = _robust_sd(np.concatenate([rp, rq])) or rsd
            boots[b] = (np.mean(rq) - np.mean(rp)) / (denom if denom > 1e-12 else rsd)
        lo_q = (1 - ci_level) / 2.0
        ci_low = float(np.quantile(boots, lo_q))
        ci_high = float(np.quantile(boots, 1 - lo_q))
    else:
        ci_low = ci_high = standardised

    d_obs = cohens_d(pre, post)
    pow_obs = achieved_power(d_obs, n1, n2, alpha)
    pow_sesoi = achieved_power(sesoi_robust_sd, n1, n2, alpha)

    ci_excludes_sesoi = (
        np.sign(ci_low) == np.sign(ci_high)
        and min(abs(ci_low), abs(ci_high)) >= sesoi_robust_sd
    )
    if ci_excludes_sesoi:
        # Direct, power-independent evidence: the whole 99% CI lies beyond the SESOI.
        verdict = "EFFECT_EXCEEDS_SESOI"
        note = "The full 99% CI for the standardised effect lies beyond the SESOI."
    elif pow_sesoi < power_gate:
        verdict = "UNDERPOWERED"
        note = (f"99% CI does not exclude the SESOI and power to detect it is "
                f"{pow_sesoi:.2f} < gate {power_gate}; indeterminate, not absence of effect.")
    else:
        verdict = "EFFECT_BELOW_SESOI"
        note = "Adequately powered, but the effect's 99% CI does not exceed the SESOI."

    return EffectSizeReport(
        n_pre=n1, n_post=n2,
        mean_pre=float(np.mean(pre)) if n1 else 0.0,
        mean_post=float(np.mean(post)) if n2 else 0.0,
        raw_effect=raw_effect,
        robust_sd=float(rsd),
        sesoi_robust_sd=float(sesoi_robust_sd),
        standardised_effect=float(standardised),
        hedges_g=float(g),
        ci_low=ci_low, ci_high=ci_high,
        achieved_power_at_observed=float(pow_obs),
        achieved_power_at_sesoi=float(pow_sesoi),
        power_gate=float(power_gate),
        alpha=float(alpha), ci_level=float(ci_level),
        verdict=verdict, note=note,
    )
