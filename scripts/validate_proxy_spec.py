#!/usr/bin/env python3
"""scripts/validate_proxy_spec.py

Validate one or more proxy_spec.json files against the ORI-C proxy schema.

Schema (normative, inline)
--------------------------
Top-level required fields:
  dataset_id      str   — unique identifier for the dataset/pilot
  columns         list  — list of column specs (at least 3 for O, R, I)

Each column spec must have:
  source_column    str  — column name in the raw CSV
  oric_variable    str  — one of {O, R, I, demand, S}
  direction        str  — one of {positive, negative}
  normalization    str  — one of {robust_minmax, minmax, none, zscore}
  missing_strategy str  — one of {linear_interp, forward_fill, zero, backward_fill, constant}

Optional top-level fields:
  spec_version     str  — semantic version (e.g. "1.0")
  sector           str  — free-form sector name
  time_column      str  — name of the time column in the raw CSV
  time_mode        str  — one of {index, value}
  normalization_global str — global normalisation override
  notes            str  — free-form notes

Optional per-column fields:
  scale_lo         float | null — explicit lower bound for scaling
  scale_hi         float | null — explicit upper bound for scaling
  fragility_note   str   — audit note on data fragility
  manipulability_note str — audit note on potential manipulation

Constraints:
  - oric_variable ∈ {O, R, I, demand, S}  (no duplicates except demand)
  - Exactly one O, one R, one I column is required
  - At most one demand column and at most one S column
  - direction ∈ {positive, negative}
  - normalization ∈ {robust_minmax, minmax, none, zscore}
  - missing_strategy ∈ {linear_interp, forward_fill, zero, backward_fill, constant}
  - time_mode (if present) ∈ {index, value}

Exit codes:
  0 — all files valid
  1 — one or more files invalid
  2 — file not found or JSON parse error

Usage
-----
    # Validate all proxy specs in the repo
    python scripts/validate_proxy_spec.py 03_Data/real/*/pilot_*/proxy_spec.json

    # Validate a single file with verbose output
    python scripts/validate_proxy_spec.py --verbose 03_Data/real/economie/pilot_cpi/proxy_spec.json

    # CI-friendly: exit 1 on first error
    python scripts/validate_proxy_spec.py --strict 03_Data/real/**/*.json
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

# ── Normative allowed values ──────────────────────────────────────────────────

_ALLOWED_ORIC_VARIABLES = {"O", "R", "I", "demand", "S"}
_REQUIRED_VARIABLES = {"O", "R", "I"}
_ALLOWED_DIRECTIONS = {"positive", "negative"}
_ALLOWED_NORMALIZATIONS = {"robust_minmax", "minmax", "none", "zscore"}
_ALLOWED_MISSING_STRATEGIES = {"linear_interp", "forward_fill", "zero", "backward_fill", "constant"}
_ALLOWED_TIME_MODES = {"index", "value"}


# ── Validator ─────────────────────────────────────────────────────────────────

def _validate_column(col: dict, idx: int) -> list[str]:
    """Return list of error messages for a single column spec."""
    errs: list[str] = []
    prefix = f"columns[{idx}]"

    for field in ("source_column", "oric_variable", "direction", "normalization", "missing_strategy"):
        if field not in col:
            errs.append(f"{prefix}: missing required field '{field}'")
        elif not isinstance(col[field], str):
            errs.append(f"{prefix}.{field}: must be a string, got {type(col[field]).__name__}")

    oric_var = col.get("oric_variable", "")
    if oric_var and oric_var not in _ALLOWED_ORIC_VARIABLES:
        errs.append(f"{prefix}.oric_variable: '{oric_var}' not in allowed set {sorted(_ALLOWED_ORIC_VARIABLES)}")

    direction = col.get("direction", "")
    if direction and direction not in _ALLOWED_DIRECTIONS:
        errs.append(f"{prefix}.direction: '{direction}' not in {sorted(_ALLOWED_DIRECTIONS)}")

    norm = col.get("normalization", "")
    if norm and norm not in _ALLOWED_NORMALIZATIONS:
        errs.append(f"{prefix}.normalization: '{norm}' not in {sorted(_ALLOWED_NORMALIZATIONS)}")

    ms = col.get("missing_strategy", "")
    if ms and ms not in _ALLOWED_MISSING_STRATEGIES:
        errs.append(f"{prefix}.missing_strategy: '{ms}' not in {sorted(_ALLOWED_MISSING_STRATEGIES)}")

    for bound in ("scale_lo", "scale_hi"):
        if bound in col and col[bound] is not None and not isinstance(col[bound], (int, float)):
            errs.append(f"{prefix}.{bound}: must be numeric or null, got {type(col[bound]).__name__}")

    return errs


def validate(spec: dict) -> list[str]:
    """Return list of all validation errors for a proxy_spec dict."""
    errs: list[str] = []

    # Top-level required fields
    if "dataset_id" not in spec:
        errs.append("Missing required top-level field 'dataset_id'")
    elif not isinstance(spec["dataset_id"], str):
        errs.append("'dataset_id' must be a string")

    if "columns" not in spec:
        errs.append("Missing required top-level field 'columns'")
        return errs  # cannot continue without columns

    if not isinstance(spec["columns"], list):
        errs.append("'columns' must be a list")
        return errs

    if len(spec["columns"]) < 1:
        errs.append("'columns' must have at least one entry")

    # Validate each column
    oric_vars_seen: list[str] = []
    for i, col in enumerate(spec["columns"]):
        if not isinstance(col, dict):
            errs.append(f"columns[{i}]: must be an object, got {type(col).__name__}")
            continue
        errs.extend(_validate_column(col, i))
        ov = col.get("oric_variable", "")
        if ov:
            oric_vars_seen.append(ov)

    # ORI core completeness check
    missing_core = _REQUIRED_VARIABLES - set(oric_vars_seen)
    if missing_core:
        errs.append(f"Missing required oric_variable(s): {sorted(missing_core)} — O, R, I are all required")

    # Duplicate check (O, R, I must appear exactly once; demand and S at most once)
    for var in ("O", "R", "I", "S"):
        count = oric_vars_seen.count(var)
        if count > 1:
            errs.append(f"oric_variable '{var}' appears {count} times; must be unique")

    # Optional top-level fields with controlled vocabularies
    if "time_mode" in spec and spec["time_mode"] not in _ALLOWED_TIME_MODES:
        errs.append(f"'time_mode': '{spec['time_mode']}' not in {sorted(_ALLOWED_TIME_MODES)}")

    if "normalization_global" in spec and spec["normalization_global"] not in _ALLOWED_NORMALIZATIONS:
        errs.append(f"'normalization_global': '{spec['normalization_global']}' not in {sorted(_ALLOWED_NORMALIZATIONS)}")

    return errs


def validate_file(path: Path, verbose: bool = False) -> bool:
    """Validate a single proxy_spec.json. Returns True if valid."""
    if not path.exists():
        print(f"NOT FOUND  {path}")
        return False

    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"PARSE ERROR  {path}: {exc}")
        return False

    errs = validate(spec)
    if errs:
        print(f"INVALID  {path}  ({len(errs)} error(s))")
        for e in errs:
            print(f"  ERROR: {e}")
        return False

    if verbose:
        n_cols = len(spec.get("columns", []))
        oric_vars = [c.get("oric_variable", "?") for c in spec.get("columns", [])]
        print(f"OK  {path}  (dataset_id={spec.get('dataset_id')}  {n_cols} cols: {oric_vars})")
    else:
        print(f"OK  {path}")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Validate ORI-C proxy_spec.json files")
    ap.add_argument("files", nargs="+", help="Paths (or globs) to proxy_spec.json files")
    ap.add_argument("--verbose", "-v", action="store_true", help="Show column details for valid files")
    ap.add_argument("--strict", action="store_true", help="Abort on first invalid file")
    args = ap.parse_args()

    # Expand globs
    paths: list[Path] = []
    for pattern in args.files:
        expanded = glob.glob(pattern, recursive=True)
        if expanded:
            paths.extend(Path(p) for p in sorted(expanded))
        else:
            paths.append(Path(pattern))

    if not paths:
        print("No files found.", file=sys.stderr)
        return 2

    n_ok = 0
    n_fail = 0
    for p in paths:
        ok = validate_file(p, verbose=args.verbose)
        if ok:
            n_ok += 1
        else:
            n_fail += 1
            if args.strict:
                return 1

    print(f"\nResult: {n_ok} valid, {n_fail} invalid")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
