"""T6-cut — does C collapse when the S channel is cut?

T6 claims the symbolic layer is not reducible to O, R, I.
This module operationalises that claim:

* intact  : original S
* cut     : S transformed by the declared cut_operator (zero / permute / delay / reset)
* sham    : Cap-layer permutation that must *not* be sufficient to kill C
            if S is a real channel

Decision uses the existing SESOI_C = +0.30 robust SD from DECISION_RULES_v2.
This file does not change frozen parameters.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .s_spec import SSpec, SSpecError
from .symbolic import compute_order_C

ALLOWED_SHAMS = frozenset({"permute_cap", "permute_v"})


@dataclass(frozen=True)
class T6CutResult:
    spec_sha256: str
    cut_operator: str
    n: int
    c_intact: float
    c_cut: float
    c_sham: float
    delta_cut: float
    delta_sham: float
    sesoi_c: float
    cut_collapses: bool
    sham_insufficient: bool
    verdict: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_sha256": self.spec_sha256,
            "cut_operator": self.cut_operator,
            "n": self.n,
            "c_intact": self.c_intact,
            "c_cut": self.c_cut,
            "c_sham": self.c_sham,
            "delta_cut": self.delta_cut,
            "delta_sham": self.delta_sham,
            "sesoi_c": self.sesoi_c,
            "cut_collapses": self.cut_collapses,
            "sham_insufficient": self.sham_insufficient,
            "verdict": self.verdict,
            "reason": self.reason,
        }


def _require_columns(df: pd.DataFrame, spec: SSpec) -> None:
    if spec.source_column not in df.columns:
        raise SSpecError(f"missing S column {spec.source_column!r}")
    if "V" not in df.columns:
        raise SSpecError("df must include V for compute_order_C")


def apply_cut(s: pd.Series, spec: SSpec, rng: np.random.Generator) -> pd.Series:
    values = s.to_numpy(dtype=float, copy=True)
    if spec.cut_operator == "zero":
        values[:] = 0.0
    elif spec.cut_operator == "permute":
        rng.shuffle(values)
    elif spec.cut_operator == "delay":
        k = spec.delay_steps
        if len(values):
            values = np.concatenate([np.full(k, values[0]), values[:-k]])
    elif spec.cut_operator == "reset_generation":
        values = values - np.nanmean(values)
    else:
        raise SSpecError(f"unknown cut_operator {spec.cut_operator!r}")
    return pd.Series(values, index=s.index, name=s.name)


def apply_sham(df: pd.DataFrame, sham: str, rng: np.random.Generator) -> pd.DataFrame:
    out = df.copy()
    if sham == "permute_v":
        if "V" not in out.columns:
            raise SSpecError("sham permute_v requires column V")
        vals = out["V"].to_numpy(dtype=float, copy=True)
        rng.shuffle(vals)
        out["V"] = vals
        return out
    if sham == "permute_cap":
        target = "Cap" if "Cap" in out.columns else None
        if target is None:
            for name in ("O", "R", "I"):
                if name in out.columns:
                    target = name
                    break
        if target is None:
            raise SSpecError("sham permute_cap requires Cap or O/R/I")
        vals = out[target].to_numpy(dtype=float, copy=True)
        rng.shuffle(vals)
        out[target] = vals
        return out
    raise SSpecError(f"sham must be one of {sorted(ALLOWED_SHAMS)}")


def _final_c(df: pd.DataFrame, s_col: str) -> float:
    work = df.copy()
    if "S" not in work.columns or s_col != "S":
        work["S"] = work[s_col]
    c = compute_order_C(work)
    if len(c) == 0:
        return float("nan")
    return float(c.iloc[-1])


def run_t6_cut(
    df: pd.DataFrame,
    spec: SSpec,
    *,
    sesoi_c: float = 0.30,
    sham: str = "permute_v",
    seed: int = 0,
) -> T6CutResult:
    """Compare intact vs cut vs sham. Does not write frozen params."""
    spec.validate()
    _require_columns(df, spec)
    if sham not in ALLOWED_SHAMS:
        raise SSpecError(f"sham must be one of {sorted(ALLOWED_SHAMS)}")

    rng_cut = np.random.default_rng(seed)
    rng_sham = np.random.default_rng(seed + 1)

    intact = df.copy()
    if "S" not in intact.columns:
        intact["S"] = intact[spec.source_column]

    cut_df = intact.copy()
    cut_df[spec.source_column] = apply_cut(intact[spec.source_column], spec, rng_cut)
    cut_df["S"] = cut_df[spec.source_column]

    sham_df = apply_sham(intact, sham, rng_sham)
    if spec.source_column in sham_df.columns:
        sham_df["S"] = sham_df[spec.source_column]

    c_intact = _final_c(intact, "S")
    c_cut = _final_c(cut_df, "S")
    c_sham = _final_c(sham_df, "S")

    s_vals = intact["S"].to_numpy(dtype=float)
    med = float(np.nanmedian(s_vals))
    mad = float(np.nanmedian(np.abs(s_vals - med)))
    robust_sd = 1.4826 * mad if mad > 0 else 1.0
    threshold = sesoi_c * robust_sd
    if not np.isfinite(threshold) or threshold == 0:
        threshold = sesoi_c

    delta_cut = c_intact - c_cut
    delta_sham = c_intact - c_sham
    cut_collapses = bool(np.isfinite(delta_cut) and delta_cut >= threshold)
    sham_insufficient = bool(np.isfinite(delta_sham) and delta_sham < threshold)

    if len(intact) < 10:
        verdict, reason = "INDETERMINATE", "series shorter than 10"
    elif not np.isfinite(c_intact):
        verdict, reason = "INDETERMINATE", "C intact is not finite"
    elif cut_collapses and sham_insufficient:
        verdict, reason = "ACCEPT", "C collapses under S cut and not under Cap/V sham"
    elif (not cut_collapses) and np.isfinite(delta_cut):
        verdict, reason = "REJECT", "C does not collapse under declared S cut"
    else:
        verdict, reason = "INDETERMINATE", "cut or sham contrast not separable at SESOI_C"

    return T6CutResult(
        spec_sha256=spec.sha256(),
        cut_operator=spec.cut_operator,
        n=int(len(intact)),
        c_intact=c_intact,
        c_cut=c_cut,
        c_sham=c_sham,
        delta_cut=float(delta_cut),
        delta_sham=float(delta_sham),
        sesoi_c=sesoi_c,
        cut_collapses=cut_collapses,
        sham_insufficient=sham_insufficient,
        verdict=verdict,
        reason=reason,
    )
