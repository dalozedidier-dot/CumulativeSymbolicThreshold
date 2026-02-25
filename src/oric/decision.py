"""decision.py — nan-safe hierarchical verdict computation for real-data runs.

Decision hierarchy (preregistered, fixed ex ante, never changed post-observation):

  Priority 1 — Welch t-test p-value (parametric, if finite)
  Priority 2 — Block bootstrap CI excludes zero (if CI finite and p_welch is NaN)
  Priority 3 — Mann-Whitney U p-value (non-parametric, if MWU p is finite)
  Priority 4 — INDETERMINATE (all statistics unavailable)

Triplet logic (α = 0.01, fixed):
  ok_p    : p_effective <= alpha  (from the highest-priority available source)
  ok_ci   : bootstrap CI lower bound > 0  (CI excludes zero, positive direction)
  ok_sesoi: bootstrap mean diff >= sesoi_threshold

  verdict_triplet = ok_p AND ok_ci AND ok_sesoi
  indeterminate   = p_source == "unavailable"

This module is pure Python + math, no external dependencies.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

# ── Normative Welch-NaN fallback policy ──────────────────────────────────────
# Locked ex ante. Must NOT be changed post-observation.
#
# When the Welch t-test p-value is NaN (series too short, zero variance, or
# other numerical failure) the decision procedure MUST fall back in this order:
#
#   1. Block bootstrap CI (non-parametric, direction-sensitive):
#        If the 95% CI lower bound > 0, the effect is positive with high
#        confidence. p_source = "bootstrap_fallback", p_effective = alpha/2
#        (conservative sentinel — the real decision gate is ci_excludes_zero).
#
#   2. Mann-Whitney U (non-parametric, rank-based, one-tailed post > pre):
#        Used only when bootstrap CI is also unavailable (NaN bounds).
#        p_source = "mannwhitney_fallback".
#
#   3. INDETERMINATE:
#        Only reached when ALL of Welch, bootstrap CI, and MWU are unavailable.
#        p_source = "unavailable", indeterminate = True.
#        The run is preserved in the audit log but contributes no verdict signal.
#
# Rationale for bootstrap-before-MWU:
#   - The bootstrap CI is direction-sensitive (tests positive shift), which is
#     the causal claim. MWU tests rank ordering without directionality.
#   - Both are valid; bootstrap is the preferred non-parametric fallback because
#     it directly answers the question asked by the triplet criterion.
#
# This constant documents the canonical order. All callers (tests_causaux.py,
# future pipeline scripts) must implement the same cascade.
WELCH_NAN_FALLBACK_POLICY: tuple[str, ...] = (
    "welch",               # Priority 1 — parametric, if finite
    "bootstrap_fallback",  # Priority 2 — CI excludes zero (direction-sensitive)
    "mannwhitney_fallback",# Priority 3 — rank-based non-parametric
    "unavailable",         # Priority 4 — INDETERMINATE, never a hard failure
)
#
# The tuple above is the single source of truth for p_source values across the
# codebase. Do not introduce new p_source strings without updating this constant.
# ─────────────────────────────────────────────────────────────────────────────

PSource = Literal["welch", "bootstrap_fallback", "mannwhitney_fallback", "unavailable"]


@dataclass
class DecisionResult:
    """Complete output of the hierarchical nan-safe decision procedure."""

    p_effective: float       # The p-value used in the decision (NaN if unavailable)
    p_source: PSource        # Which statistical test supplied p_effective
    ci_lo: float             # Bootstrap 95/99% CI lower bound (NaN if unavailable)
    ci_hi: float             # Bootstrap 95/99% CI upper bound (NaN if unavailable)
    boot_mid: float          # Bootstrap mean difference (NaN if unavailable)
    ci_excludes_zero: bool   # CI lower bound > 0  (positive direction assumed)
    sesoi_ok: bool           # boot_mid >= sesoi_threshold
    ok_p: bool               # p_effective <= alpha
    ok_ci: bool              # ci_excludes_zero
    ok_sesoi: bool           # sesoi_ok
    verdict_triplet: bool    # ok_p AND ok_ci AND ok_sesoi
    indeterminate: bool      # True when p_source == "unavailable"

    def to_dict(self) -> dict:
        return {
            "p_effective": self.p_effective,
            "p_source": self.p_source,
            "ci_lo": self.ci_lo,
            "ci_hi": self.ci_hi,
            "boot_mid": self.boot_mid,
            "ci_excludes_zero": self.ci_excludes_zero,
            "sesoi_ok": self.sesoi_ok,
            "ok_p": self.ok_p,
            "ok_ci": self.ok_ci,
            "ok_sesoi": self.ok_sesoi,
            "verdict_triplet": self.verdict_triplet,
            "indeterminate": self.indeterminate,
        }


def hierarchical_verdict(
    p_welch: float,
    boot_lo: float,
    boot_hi: float,
    boot_mid: float,
    mw_p: float,
    alpha: float,
    sesoi_threshold: float,
) -> DecisionResult:
    """Apply the preregistered nan-safe decision hierarchy.

    Parameters
    ----------
    p_welch          : Welch t-test p-value (may be NaN — short series, equal variance failure)
    boot_lo          : Block bootstrap CI lower bound (may be NaN — too few observations)
    boot_hi          : Block bootstrap CI upper bound (may be NaN)
    boot_mid         : Block bootstrap mean difference (may be NaN)
    mw_p             : Mann-Whitney U p-value (may be NaN — fallback non-parametric)
    alpha            : Significance level — must be 0.01 (non-negotiable per PreregSpec)
    sesoi_threshold  : Smallest effect size of interest (in boot_mid units, e.g. 0.30 * MAD)

    Returns
    -------
    DecisionResult with all derived boolean fields and the p_source provenance tag.
    """
    # ── CI evaluation ──────────────────────────────────────────────────────────
    ci_excludes_zero = bool(
        math.isfinite(boot_lo) and math.isfinite(boot_hi) and boot_lo > 0.0
    )
    sesoi_ok = bool(math.isfinite(boot_mid) and boot_mid >= sesoi_threshold)

    # ── Hierarchical p-value selection ─────────────────────────────────────────
    if math.isfinite(p_welch):
        p_eff: float = p_welch
        p_src: PSource = "welch"
        indeterminate = False

    elif ci_excludes_zero:
        # Bootstrap CI excludes zero ↔ boot p < ~0.025; use as fallback.
        # We record alpha/2 as a conservative p_effective for logging purposes only.
        # The actual decision gate is ci_excludes_zero, not p_eff.
        p_eff = alpha / 2.0
        p_src = "bootstrap_fallback"
        indeterminate = False

    elif math.isfinite(mw_p):
        p_eff = mw_p
        p_src = "mannwhitney_fallback"
        indeterminate = False

    else:
        p_eff = float("nan")
        p_src = "unavailable"
        indeterminate = True

    # ── Boolean gates ──────────────────────────────────────────────────────────
    if indeterminate:
        ok_p = False
    elif p_src == "bootstrap_fallback":
        # Decision already encoded in ci_excludes_zero
        ok_p = ci_excludes_zero
    else:
        ok_p = bool(math.isfinite(p_eff) and p_eff <= alpha)

    ok_ci = ci_excludes_zero
    ok_sesoi = sesoi_ok
    triplet = bool(ok_p and ok_ci and ok_sesoi)

    return DecisionResult(
        p_effective=p_eff,
        p_source=p_src,
        ci_lo=boot_lo,
        ci_hi=boot_hi,
        boot_mid=boot_mid,
        ci_excludes_zero=ci_excludes_zero,
        sesoi_ok=sesoi_ok,
        ok_p=ok_p,
        ok_ci=ok_ci,
        ok_sesoi=ok_sesoi,
        verdict_triplet=triplet,
        indeterminate=indeterminate,
    )
