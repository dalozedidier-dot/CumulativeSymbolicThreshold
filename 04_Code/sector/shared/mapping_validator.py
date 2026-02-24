"""mapping_validator.py — Proxy mapping validity gate for sector panels.

Emits a structured verdict: ACCEPT / REJECT / INDETERMINATE
with per-check details, independent of the T1-T8 canonical suite.

Hard gates (→ REJECT):
  - Missing required ORI columns in CSV
  - O/R/I proxies pairwise |r| ≥ 0.90  (near-collapse of independence)
  - Zero or near-zero variance in any ORI proxy (< 1e-6)
  - proxy_spec.json missing required schema fields

Soft gates (→ INDETERMINATE if any fail, ACCEPT otherwise):
  - |r| ∈ [0.75, 0.90) between any ORI pair  (borderline independence)
  - Any proxy declared with high fragility_score > 0.7
  - Any proxy non-stationary (ADF p > 0.10)  [informative only, never REJECT]

Validity note (in output, not in verdict):
  - Direction annotations present for all mapped columns
  - manipulability_note present for each column
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
CORR_HARD_REJECT = 0.90     # |r| >= this → REJECT
CORR_SOFT_WARN   = 0.75     # |r| >= this → soft warning
VAR_MIN          = 1e-6     # variance below → REJECT
FRAGILITY_WARN   = 0.70     # fragility_score above → soft warning
N_MIN            = 20       # minimum rows for any statistical check
ADF_PVALUE_WARN  = 0.10     # ADF p > this → non-stationarity warning

REQUIRED_SPEC_KEYS = ["dataset_id", "sector", "spec_version", "columns"]
REQUIRED_COL_KEYS  = ["oric_role", "source_column", "direction"]
ORI_ROLES          = {"O", "R", "I"}


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #

def _validate_schema(spec: dict) -> list[str]:
    """Return list of schema error messages (empty = ok)."""
    errors: list[str] = []
    for k in REQUIRED_SPEC_KEYS:
        if k not in spec:
            errors.append(f"missing required spec key: '{k}'")
    if "columns" in spec:
        for i, col in enumerate(spec["columns"]):
            for k in REQUIRED_COL_KEYS:
                if k not in col:
                    errors.append(f"column[{i}] missing required key: '{k}'")
            role = col.get("oric_role", "")
            if role not in {"O", "R", "I", "S", "demand", "time"}:
                errors.append(f"column[{i}] unknown oric_role: '{role}'")
    return errors


# --------------------------------------------------------------------------- #
# Column checks
# --------------------------------------------------------------------------- #

def _extract_ori_columns(spec: dict, df: pd.DataFrame) -> tuple[dict[str, str], list[str]]:
    """Return {oric_role: source_column} for O/R/I, plus missing-column errors."""
    mapping: dict[str, str] = {}
    errors: list[str] = []
    for col in spec.get("columns", []):
        role = col.get("oric_role", "")
        src  = col.get("source_column", "")
        if role in ORI_ROLES:
            mapping[role] = src
            if src not in df.columns:
                errors.append(f"source_column '{src}' for role '{role}' not found in CSV")
    for role in ORI_ROLES:
        if role not in mapping:
            errors.append(f"no column mapped to required ORI role '{role}'")
    return mapping, errors


def _variance_check(mapping: dict[str, str], df: pd.DataFrame) -> list[str]:
    """Return REJECT-level error messages for zero/near-zero variance."""
    errors: list[str] = []
    for role, src in mapping.items():
        if src in df.columns:
            var = float(df[src].var(skipna=True))
            if not math.isfinite(var) or var < VAR_MIN:
                errors.append(
                    f"proxy '{src}' (role {role}) has near-zero variance ({var:.2e}) — "
                    "proxy is uninformative"
                )
    return errors


def _independence_check(
    mapping: dict[str, str], df: pd.DataFrame
) -> tuple[list[str], list[str]]:
    """
    Returns (hard_errors, soft_warnings) for pairwise ORI correlation.
    hard_errors → REJECT. soft_warnings → INDETERMINATE.
    """
    hard: list[str] = []
    soft: list[str] = []
    roles = [r for r in ["O", "R", "I"] if r in mapping and mapping[r] in df.columns]
    for i in range(len(roles)):
        for j in range(i + 1, len(roles)):
            r_i, r_j = roles[i], roles[j]
            s_i, s_j = mapping[r_i], mapping[r_j]
            ser_i = df[s_i].dropna()
            ser_j = df[s_j].dropna()
            n = min(len(ser_i), len(ser_j))
            if n < N_MIN:
                soft.append(
                    f"too few observations ({n}) to compute {r_i}/{r_j} correlation"
                )
                continue
            corr = float(np.corrcoef(ser_i.values[:n], ser_j.values[:n])[0, 1])
            abs_corr = abs(corr)
            if abs_corr >= CORR_HARD_REJECT:
                hard.append(
                    f"|r({r_i},{r_j})| = {abs_corr:.3f} ≥ {CORR_HARD_REJECT} — "
                    "proxies are near-collinear; ORI independence assumption violated"
                )
            elif abs_corr >= CORR_SOFT_WARN:
                soft.append(
                    f"|r({r_i},{r_j})| = {abs_corr:.3f} ∈ [{CORR_SOFT_WARN}, {CORR_HARD_REJECT}) — "
                    "borderline independence; interpret with caution"
                )
    return hard, soft


def _fragility_check(spec: dict) -> list[str]:
    """Return soft warnings for high fragility_score or missing manipulability_note."""
    warnings: list[str] = []
    for col in spec.get("columns", []):
        src = col.get("source_column", "?")
        score = col.get("fragility_score")
        if score is not None and float(score) > FRAGILITY_WARN:
            warnings.append(
                f"proxy '{src}' has fragility_score={score:.2f} > {FRAGILITY_WARN} — "
                "proxy may be subject to reporting artefacts"
            )
        if not col.get("manipulability_note"):
            warnings.append(
                f"proxy '{src}' is missing manipulability_note — "
                "required for sector panel audit"
            )
    return warnings


def _adf_check(mapping: dict[str, str], df: pd.DataFrame) -> list[str]:
    """Return informative non-stationarity warnings (never REJECT)."""
    warnings: list[str] = []
    try:
        from statsmodels.tsa.stattools import adfuller
    except ImportError:
        return ["statsmodels not available — skipping ADF stationarity check"]
    for role, src in mapping.items():
        if src not in df.columns:
            continue
        series = df[src].dropna()
        if len(series) < N_MIN:
            continue
        try:
            p = adfuller(series.values, autolag="AIC")[1]
            if p > ADF_PVALUE_WARN:
                warnings.append(
                    f"proxy '{src}' (role {role}): ADF p={p:.3f} > {ADF_PVALUE_WARN} — "
                    "non-stationary series; use normalized/differenced proxies"
                )
        except Exception as exc:
            warnings.append(f"proxy '{src}': ADF failed ({exc})")
    return warnings


def _direction_check(spec: dict) -> list[str]:
    """Return annotation completeness notes (informative only)."""
    notes: list[str] = []
    for col in spec.get("columns", []):
        src = col.get("source_column", "?")
        if col.get("direction") not in ("positive", "negative"):
            notes.append(
                f"proxy '{src}' has non-standard direction='{col.get('direction')}'; "
                "expected 'positive' or 'negative'"
            )
    return notes


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #

def validate_mapping(
    spec_path: str | Path,
    csv_path: str | Path,
) -> dict[str, Any]:
    """
    Run full mapping validity check.

    Returns a dict:
      {
        "verdict": "ACCEPT" | "REJECT" | "INDETERMINATE",
        "hard_errors": [...],
        "soft_warnings": [...],
        "info_notes": [...],
        "spec_dataset_id": ...,
        "spec_version": ...,
        "n_rows": ...,
        "correlation_table": {(role_i, role_j): corr, ...}
      }
    """
    result: dict[str, Any] = {
        "verdict":           "ACCEPT",
        "hard_errors":       [],
        "soft_warnings":     [],
        "info_notes":        [],
        "spec_dataset_id":   None,
        "spec_version":      None,
        "n_rows":            0,
        "correlation_table": {},
    }

    # 1. Load spec
    try:
        with open(spec_path) as f:
            spec = json.load(f)
    except Exception as exc:
        result["hard_errors"].append(f"Cannot load proxy_spec.json: {exc}")
        result["verdict"] = "REJECT"
        return result

    result["spec_dataset_id"] = spec.get("dataset_id")
    result["spec_version"]    = spec.get("spec_version")

    # 2. Schema check
    schema_errors = _validate_schema(spec)
    result["hard_errors"].extend(schema_errors)

    # 3. Load CSV
    try:
        df = pd.read_csv(csv_path)
        result["n_rows"] = len(df)
    except Exception as exc:
        result["hard_errors"].append(f"Cannot load CSV: {exc}")
        result["verdict"] = "REJECT"
        return result

    # 4. Extract ORI mapping + column existence
    mapping, col_errors = _extract_ori_columns(spec, df)
    result["hard_errors"].extend(col_errors)

    if mapping and not col_errors:
        # 5. Variance
        result["hard_errors"].extend(_variance_check(mapping, df))

        # 6. Independence
        hard_corr, soft_corr = _independence_check(mapping, df)
        result["hard_errors"].extend(hard_corr)
        result["soft_warnings"].extend(soft_corr)

        # Build correlation table for output
        roles = [r for r in ["O", "R", "I"] if r in mapping and mapping[r] in df.columns]
        for i in range(len(roles)):
            for j in range(i + 1, len(roles)):
                r_i, r_j = roles[i], roles[j]
                s_i, s_j = mapping[r_i], mapping[r_j]
                n = min(len(df[s_i].dropna()), len(df[s_j].dropna()))
                if n >= N_MIN:
                    corr = float(np.corrcoef(
                        df[s_i].dropna().values[:n],
                        df[s_j].dropna().values[:n],
                    )[0, 1])
                    result["correlation_table"][f"{r_i}_{r_j}"] = round(corr, 4)

        # 7. Non-stationarity (informative)
        result["soft_warnings"].extend(_adf_check(mapping, df))

    # 8. Fragility + manipulability
    result["soft_warnings"].extend(_fragility_check(spec))

    # 9. Direction annotation (informative)
    result["info_notes"].extend(_direction_check(spec))

    # 10. Compute verdict
    if result["hard_errors"]:
        result["verdict"] = "REJECT"
    elif result["soft_warnings"]:
        result["verdict"] = "INDETERMINATE"
    else:
        result["verdict"] = "ACCEPT"

    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Validate ORI-C sector proxy mapping")
    parser.add_argument("--spec", required=True, help="Path to proxy_spec.json")
    parser.add_argument("--csv",  required=True, help="Path to real.csv")
    parser.add_argument("--out",  default=None,  help="Write JSON result to this path")
    args = parser.parse_args()

    result = validate_mapping(args.spec, args.csv)

    # Pretty print
    verdict = result["verdict"]
    marker  = {"ACCEPT": "✓", "REJECT": "✗", "INDETERMINATE": "?"}.get(verdict, "?")
    print(f"\n[mapping_validator] {marker} {verdict}")
    print(f"  dataset_id : {result['spec_dataset_id']}")
    print(f"  spec_version: {result['spec_version']}")
    print(f"  n_rows     : {result['n_rows']}")
    if result["correlation_table"]:
        print("  correlations:", result["correlation_table"])
    if result["hard_errors"]:
        print("  HARD ERRORS:")
        for e in result["hard_errors"]:
            print(f"    ✗ {e}")
    if result["soft_warnings"]:
        print("  SOFT WARNINGS:")
        for w in result["soft_warnings"]:
            print(f"    ! {w}")
    if result["info_notes"]:
        print("  NOTES:")
        for n in result["info_notes"]:
            print(f"    • {n}")
    print()

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"[mapping_validator] result written to {out_path}")

    import sys
    sys.exit(0 if verdict != "REJECT" else 1)


if __name__ == "__main__":
    main()
