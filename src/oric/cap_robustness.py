from __future__ import annotations

from dataclasses import dataclass, asdict
import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

import numpy as np
import pandas as pd

from .ori_core import compute_cap_projection, compute_sigma


CANONICAL_CAP_FORMS: tuple[str, ...] = ("product", "geom_mean", "weighted_sum", "min")
DEFAULT_THRESHOLDS: dict[str, float] = {
    "min_spearman": 0.80,
    "max_frac_over_delta": 0.15,
    "max_total_sigma_rel_delta": 0.50,
    "min_topk_jaccard": 0.50,
}


@dataclass(frozen=True)
class CapRobustnessSpec:
    """Ex-ante robustness criteria for Cap(t) specification sensitivity."""

    primary_form: str = "product"
    forms: tuple[str, ...] = CANONICAL_CAP_FORMS
    min_spearman: float = DEFAULT_THRESHOLDS["min_spearman"]
    max_frac_over_delta: float = DEFAULT_THRESHOLDS["max_frac_over_delta"]
    max_total_sigma_rel_delta: float = DEFAULT_THRESHOLDS["max_total_sigma_rel_delta"]
    min_topk_jaccard: float = DEFAULT_THRESHOLDS["min_topk_jaccard"]
    topk_frac: float = 0.10

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["forms"] = list(self.forms)
        return d


def _safe_spearman(a: pd.Series, b: pd.Series) -> float | None:
    """Return Spearman correlation or None when both series are non-informative."""
    a = pd.Series(a, dtype=float)
    b = pd.Series(b, dtype=float)
    if len(a) != len(b):
        raise ValueError("series must have the same length")
    if len(a) == 0:
        return None
    if float(a.std(ddof=0)) == 0.0 and float(b.std(ddof=0)) == 0.0:
        return 1.0 if float(a.iloc[0]) == float(b.iloc[0]) else 0.0
    if float(a.std(ddof=0)) == 0.0 or float(b.std(ddof=0)) == 0.0:
        return 0.0
    val = a.corr(b, method="spearman")
    if pd.isna(val):
        return None
    return float(val)


def _topk_indices(x: pd.Series, frac: float) -> set[int]:
    x = pd.Series(x, dtype=float)
    if len(x) == 0:
        return set()
    k = max(1, int(np.ceil(len(x) * float(frac))))
    if float(x.max()) <= 0.0:
        return set()
    return set(map(int, x.nlargest(k).index))


def _jaccard(a: set[int], b: set[int]) -> float | None:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return float(len(a & b) / len(a | b))


def compute_cap_variants(
    df: pd.DataFrame,
    *,
    forms: Iterable[str] = CANONICAL_CAP_FORMS,
    o_col: str = "O",
    r_col: str = "R",
    i_col: str = "I",
) -> pd.DataFrame:
    """Compute Cap(t) for all declared structural-capacity specifications."""
    for col in (o_col, r_col, i_col):
        if col not in df.columns:
            raise KeyError(f"Missing required column: {col}")

    out = pd.DataFrame(index=df.index)
    for form in forms:
        out[form] = compute_cap_projection(df[o_col], df[r_col], df[i_col], form=form)
    return out


def summarize_cap_robustness(
    df: pd.DataFrame,
    *,
    demand_col: str = "demande_env",
    o_col: str = "O",
    r_col: str = "R",
    i_col: str = "I",
    spec: CapRobustnessSpec | None = None,
) -> dict[str, Any]:
    """Evaluate whether Sigma(t) and overload diagnostics survive Cap(t) alternatives.

    This does not prove a theoretical form for Cap(t). It operationalizes the
    methodological guardrail: structural conclusions should not depend entirely on a
    single capacity aggregation.
    """
    spec = spec or CapRobustnessSpec()
    if demand_col not in df.columns:
        raise KeyError(f"Missing required column: {demand_col}")
    if spec.primary_form not in spec.forms:
        raise ValueError("primary_form must be included in forms")

    caps = compute_cap_variants(df, forms=spec.forms, o_col=o_col, r_col=r_col, i_col=i_col)
    sigmas = pd.DataFrame(index=df.index)
    for form in spec.forms:
        sigmas[form] = compute_sigma(df[demand_col], caps[form])

    primary = sigmas[spec.primary_form]
    primary_total = float(primary.sum())
    primary_frac_over = float((primary > 0).mean())
    primary_top = _topk_indices(primary, spec.topk_frac)

    forms_summary: dict[str, dict[str, float]] = {}
    comparisons: dict[str, dict[str, float | None | bool]] = {}

    for form in spec.forms:
        s = sigmas[form]
        forms_summary[form] = {
            "cap_mean": float(caps[form].mean()),
            "cap_min": float(caps[form].min()),
            "cap_max": float(caps[form].max()),
            "total_sigma": float(s.sum()),
            "frac_over": float((s > 0).mean()),
        }
        if form == spec.primary_form:
            continue
        total = float(s.sum())
        frac_over = float((s > 0).mean())
        rel_delta = abs(total - primary_total) / max(abs(primary_total), 1e-12)
        frac_delta = abs(frac_over - primary_frac_over)
        spear = _safe_spearman(primary, s)
        jac = _jaccard(primary_top, _topk_indices(s, spec.topk_frac))

        passes = (
            (spear is not None and spear >= spec.min_spearman)
            and frac_delta <= spec.max_frac_over_delta
            and rel_delta <= spec.max_total_sigma_rel_delta
            and (jac is not None and jac >= spec.min_topk_jaccard)
        )
        comparisons[form] = {
            "sigma_spearman_vs_primary": spear,
            "frac_over_delta_vs_primary": frac_delta,
            "total_sigma_rel_delta_vs_primary": rel_delta,
            "topk_jaccard_vs_primary": jac,
            "passes_thresholds": bool(passes),
        }

    stable = bool(comparisons) and all(bool(v["passes_thresholds"]) for v in comparisons.values())
    verdict = "CAP_ROBUST" if stable else "CAP_SPEC_SENSITIVE"

    return {
        "spec": spec.to_dict(),
        "primary_form": spec.primary_form,
        "forms_summary": forms_summary,
        "comparisons": comparisons,
        "stable_across_specs": stable,
        "verdict": verdict,
        "interpretation": (
            "Structural results pass the declared Cap(t) robustness gate."
            if stable
            else "Structural results remain sensitive to at least one declared Cap(t) specification."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run ORI-C Cap(t) robustness diagnostics.")
    ap.add_argument("--input", required=True, type=Path, help="CSV with O, R, I and demand columns.")
    ap.add_argument("--output", required=True, type=Path, help="Output JSON report path.")
    ap.add_argument("--demand-col", default="demande_env")
    ap.add_argument("--o-col", default="O")
    ap.add_argument("--r-col", default="R")
    ap.add_argument("--i-col", default="I")
    ap.add_argument("--primary-form", default="product")
    ap.add_argument(
        "--forms",
        default=",".join(CANONICAL_CAP_FORMS),
        help="Comma-separated Cap(t) forms declared ex ante.",
    )
    args = ap.parse_args(argv)

    df = pd.read_csv(args.input)
    forms = tuple(x.strip() for x in args.forms.split(",") if x.strip())
    report = summarize_cap_robustness(
        df,
        demand_col=args.demand_col,
        o_col=args.o_col,
        r_col=args.r_col,
        i_col=args.i_col,
        spec=CapRobustnessSpec(primary_form=args.primary_form, forms=forms),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
