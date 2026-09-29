"""T6-cut — does C collapse when the S channel is cut?

T6 claims the symbolic layer is not reducible to O, R, I.
This module operationalises that claim:

* intact  : original S
* cut     : S transformed by the declared cut_operator (zero / permute / delay / reset)
* sham    : Cap-layer permutation that must *not* be sufficient to kill C
            if S is a real channel

Single-series transformations are sensitivity diagnostics, not interventions.
Their verdict is always INDETERMINATE: C itself depends on S. No frozen
confirmatory parameters or aggregation rules are changed here.
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
    spec_sha256: str | None
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
    diagnostic_status: str = "computed"
    diagnostic_threshold: float = float("nan")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": "2.0",
            "evidence_scope": "single_series_sensitivity",
            "confirmatory_eligible": False,
            "diagnostic_status": self.diagnostic_status,
            "diagnostic_threshold": self.diagnostic_threshold,
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
        return {
            key: None if isinstance(value, float) and not np.isfinite(value) else value
            for key, value in payload.items()
        }


def _indeterminate(
    n: int, spec: SSpec | None, sesoi_c: float, reason: str,
) -> T6CutResult:
    return T6CutResult(
        spec_sha256=None, cut_operator=spec.cut_operator if spec else "none", n=n,
        c_intact=float("nan"), c_cut=float("nan"), c_sham=float("nan"),
        delta_cut=float("nan"), delta_sham=float("nan"), sesoi_c=sesoi_c,
        cut_collapses=False, sham_insufficient=False,
        verdict="INDETERMINATE", reason=reason, diagnostic_status="not_computed",
    )


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
        if not isinstance(k, int) or isinstance(k, bool) or k < 1:
            raise SSpecError("delay_steps must be a positive integer")
        if len(values):
            k = min(k, len(values))
            values = np.concatenate([np.full(k, values[0]), values[:-k]])
    elif spec.cut_operator == "reset_generation":
        raise SSpecError(
            "reset_generation requires observed generation boundaries and a reset model; "
            "centering S is not a transmission cut"
        )
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
    spec: SSpec | None = None,
    *,
    sesoi_c: float = 0.30,
    sham: str = "permute_v",
    seed: int = 0,
) -> T6CutResult:
    """Report numerical sensitivity only, never causal ACCEPT or REJECT.

    Missing/invalid evidence returns INDETERMINATE rather than manufacturing S
    or V. The descriptive threshold uses dispersion of the intact C trajectory,
    not S's units, and is not the confirmatory baseline SESOI.
    """
    if sham not in ALLOWED_SHAMS:
        raise SSpecError(f"sham must be one of {sorted(ALLOWED_SHAMS)}")
    if not np.isfinite(sesoi_c) or sesoi_c <= 0:
        raise ValueError("sesoi_c must be finite and positive")
    if spec is None:
        return _indeterminate(len(df), spec, sesoi_c, "missing SSpec")
    try:
        spec.validate()
        _require_columns(df, spec)
        if not df.columns.is_unique:
            raise SSpecError("duplicate column names")
        values = df[[spec.source_column, "V"]].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise SSpecError("S source and V must contain only finite values")
    except (SSpecError, TypeError, ValueError) as exc:
        return _indeterminate(len(df), spec, sesoi_c, str(exc))
    if len(df) < 10:
        return _indeterminate(len(df), spec, sesoi_c, "series shorter than 10")

    rng_cut = np.random.default_rng(seed)
    rng_sham = np.random.default_rng(seed + 1)

    intact = df.copy()
    intact["S"] = intact[spec.source_column].astype(float)
    intact["V"] = intact["V"].astype(float)

    cut_df = intact.copy()
    try:
        cut_df[spec.source_column] = apply_cut(intact["S"], spec, rng_cut)
        sham_df = apply_sham(intact, sham, rng_sham)
    except SSpecError as exc:
        return _indeterminate(len(df), spec, sesoi_c, str(exc))
    cut_df["S"] = cut_df[spec.source_column]

    if spec.source_column in sham_df.columns:
        sham_df["S"] = sham_df[spec.source_column]

    c_intact = _final_c(intact, "S")
    c_cut = _final_c(cut_df, "S")
    c_sham = _final_c(sham_df, "S")

    c_vals = compute_order_C(intact).to_numpy(dtype=float)
    if not np.isfinite([c_intact, c_cut, c_sham]).all():
        return _indeterminate(len(df), spec, sesoi_c, "non-finite C diagnostic")
    med = float(np.median(c_vals))
    mad = float(np.median(np.abs(c_vals - med)))
    threshold = sesoi_c * 1.4826 * mad if mad > 0 else float("nan")

    delta_cut = c_intact - c_cut
    delta_sham = c_intact - c_sham
    cut_collapses = bool(np.isfinite(threshold) and delta_cut >= threshold)
    sham_insufficient = bool(np.isfinite(threshold) and abs(delta_sham) < threshold)

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
        verdict="INDETERMINATE",
        reason=(
            "retrospective S transformation only: C depends on S by construction; "
            "independent intervention outcomes and confirmatory gates are required"
        ),
        diagnostic_threshold=threshold,
    )
