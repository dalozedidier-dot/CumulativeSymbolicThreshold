"""validate_proxy_spec.py — Validate a proxy_spec.json before launching a real data run.

Checks:
  1. Required top-level fields present (dataset_id, spec_version, time_mode, columns).
  2. time_mode is a known value; time_column present when time_mode='value'.
  3. Every column entry has valid oric_variable, direction, normalization, missing_strategy.
  4. The three core variables O, R, I are each mapped exactly once.
  5. [Optional] When --csv is provided: every source_column exists in the CSV header row.

Exit codes:
  0  — spec is valid (and CSV columns match if --csv was given)
  1  — one or more validation errors (printed to stderr)

Usage:
  python 04_Code/pipeline/validate_proxy_spec.py --spec <proxy_spec.json>
  python 04_Code/pipeline/validate_proxy_spec.py --spec <proxy_spec.json> --csv <data.csv>
#!/usr/bin/env python3
"""04_Code/pipeline/validate_proxy_spec.py

Lightweight validator for a real-data proxy specification JSON.

Goal: ensure the mapping spec is structurally valid and self-consistent,
so real-data runs are auditable and reproducible.

Accepted shapes:
- { "columns": [ { ... }, ... ] }
- { "proxies":  [ { ... }, ... ] }

Each entry must have at minimum:
- name: column name in the real CSV
- oric_variable: one of {"O","R","I","demand","S","C","Sigma","delta_C"} (extensible)
Optional but recommended:
- direction: "higher_is_risk" | "lower_is_risk" | "neutral"
- normalization: "none" | "minmax" | "robust_minmax" | "zscore" | ...
- missing: "error" | "ffill" | "bfill" | "drop" | "zero"

Exit code:
- 0 if valid
- 2 if invalid
main
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Allowed values (normative, fixed ex ante) ────────────────────────────────
_VALID_ORIC_VARS: frozenset[str] = frozenset({"O", "R", "I", "demand", "S"})
_REQUIRED_ORIC_VARS: frozenset[str] = frozenset({"O", "R", "I"})
_VALID_DIRECTIONS: frozenset[str] = frozenset({"positive", "negative"})
_VALID_NORMALIZATIONS: frozenset[str] = frozenset(
    {"none", "minmax", "robust_minmax", "inherit"}
)
_VALID_MISSING_STRATEGIES: frozenset[str] = frozenset(
    {"none", "forward_fill", "linear_interp", "zero"}
)
_VALID_TIME_MODES: frozenset[str] = frozenset({"index", "value"})
_REQUIRED_TOP_LEVEL: tuple[str, ...] = ("dataset_id", "spec_version", "time_mode", "columns")


def validate_spec(spec_path: Path, csv_path: Path | None = None) -> list[str]:
    """Validate a proxy_spec JSON file.  Returns a list of error strings (empty = OK)."""
    errors: list[str] = []

    if not spec_path.exists():
        return [f"spec file not found: {spec_path}"]

    try:
        raw: dict = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON in {spec_path}: {exc}"]

    if not isinstance(raw, dict):
        return ["spec root must be a JSON object"]

    # ── 1. Required top-level fields ──────────────────────────────────────────
    for field in _REQUIRED_TOP_LEVEL:
        if field not in raw:
            errors.append(f"missing required field: '{field}'")

    if errors:
        # Cannot proceed with structural validation
        return errors

    # ── 2. time_mode ──────────────────────────────────────────────────────────
    time_mode = raw.get("time_mode", "")
    if time_mode not in _VALID_TIME_MODES:
        errors.append(
            f"invalid time_mode '{time_mode}': must be one of {sorted(_VALID_TIME_MODES)}"
        )
    if time_mode == "value" and not raw.get("time_column"):
        errors.append("time_mode='value' requires 'time_column' to be non-empty")

    # ── 3. columns list ───────────────────────────────────────────────────────
    columns = raw.get("columns", [])
    if not isinstance(columns, list) or len(columns) == 0:
        errors.append("'columns' must be a non-empty array")
        return errors

    mapped_vars: list[str] = []
    source_columns: list[str] = []

    for i, col in enumerate(columns):
        tag = f"columns[{i}]"
        if not isinstance(col, dict):
            errors.append(f"{tag}: must be a JSON object")
            continue

        src = col.get("source_column", "")
        if not src:
            errors.append(f"{tag}: 'source_column' is empty or missing")
        else:
            source_columns.append(src)

        ov = col.get("oric_variable", "")
        if ov not in _VALID_ORIC_VARS:
            errors.append(
                f"{tag}: invalid oric_variable '{ov}': must be one of {sorted(_VALID_ORIC_VARS)}"
            )
        else:
            mapped_vars.append(ov)

        direction = col.get("direction", "")
        if direction not in _VALID_DIRECTIONS:
            errors.append(
                f"{tag}: invalid direction '{direction}': must be one of {sorted(_VALID_DIRECTIONS)}"
            )

        norm = col.get("normalization", "none")
        if norm not in _VALID_NORMALIZATIONS:
            errors.append(
                f"{tag}: invalid normalization '{norm}': must be one of {sorted(_VALID_NORMALIZATIONS)}"
            )

        ms = col.get("missing_strategy", "none")
        if ms not in _VALID_MISSING_STRATEGIES:
            errors.append(
                f"{tag}: invalid missing_strategy '{ms}': must be one of {sorted(_VALID_MISSING_STRATEGIES)}"
            )

    # ── 4. Core variable coverage (O, R, I each exactly once) ────────────────
    missing_core = _REQUIRED_ORIC_VARS - set(mapped_vars)
    if missing_core:
        errors.append(
            f"missing required oric_variable mapping(s): {sorted(missing_core)}"
        )
    for core_var in _REQUIRED_ORIC_VARS:
        count = mapped_vars.count(core_var)
        if count > 1:
            errors.append(
                f"oric_variable '{core_var}' mapped {count} times — must appear exactly once"
            )

    # ── 5. Optional CSV header check ─────────────────────────────────────────
    if csv_path is not None:
        if not csv_path.exists():
            errors.append(f"--csv file not found: {csv_path}")
        else:
            import csv as _csv

            try:
                with csv_path.open(newline="", encoding="utf-8") as fh:
                    reader = _csv.reader(fh)
                    try:
                        csv_headers: list[str] = [h.strip() for h in next(reader)]
                    except StopIteration:
                        errors.append(f"CSV file is empty: {csv_path}")
                        return errors
            except Exception as exc:  # noqa: BLE001
                errors.append(f"could not read CSV header from {csv_path}: {exc}")
                return errors

            for i, col in enumerate(columns):
                src = col.get("source_column", "")
                if src and src not in csv_headers:
                    ov = col.get("oric_variable", "?")
                    errors.append(
                        f"columns[{i}]: source_column '{src}' (-> {ov}) not found "
                        f"in CSV headers {csv_headers}"
                    )

    return errors


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Validate a proxy_spec.json before launching an ORI-C real data run. "
            "Exits 0 on success, 1 on any validation error."
        )
    )
    ap.add_argument("--spec", required=True, help="Path to proxy_spec.json")
    ap.add_argument(
        "--csv",
        default=None,
        help="Optional path to the CSV data file — verifies source_column headers exist",
    )
    args = ap.parse_args()

    spec_path = Path(args.spec)
    csv_path = Path(args.csv) if args.csv else None

    errors = validate_spec(spec_path, csv_path)

    if errors:
        print(
            f"[validate_proxy_spec] FAIL — {len(errors)} error(s) in '{spec_path}':",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(spec_path.read_text(encoding="utf-8"))
    dataset_id = raw.get("dataset_id", "(unknown)")
    spec_version = raw.get("spec_version", "?")
    n_cols = len(raw.get("columns", []))
    csv_note = f", CSV headers checked against '{csv_path}'" if csv_path else ""
    print(
        f"[validate_proxy_spec] OK — dataset_id='{dataset_id}' "
        f"spec_version={spec_version}, {n_cols} column mapping(s) valid{csv_note}."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_ORIC = {
    "O",
    "R",
    "I",
    "demand",
    "S",
    "C",
    "Sigma",
    "delta_C",
}


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"Cannot read JSON: {path} ({e})")


def _get_items(spec: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    if isinstance(spec.get("columns"), list):
        return "columns", list(spec["columns"])
    if isinstance(spec.get("proxies"), list):
        return "proxies", list(spec["proxies"])
    raise SystemExit("Invalid spec: expected top-level key 'columns' or 'proxies' as a list.")


def _validate_item(i: int, item: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    if not isinstance(item, dict):
        return [f"Item #{i} is not an object/dict."]

    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        errs.append(f"Item #{i}: missing/invalid 'name' (CSV column name).")

    v = item.get("oric_variable")
    if not isinstance(v, str) or not v.strip():
        errs.append(f"Item #{i}: missing/invalid 'oric_variable'.")
    else:
        # Allow extensibility, but warn if outside known set.
        if v not in ALLOWED_ORIC:
            errs.append(f"Item #{i}: 'oric_variable'={v!r} not in known set {sorted(ALLOWED_ORIC)}.")

    return errs


def validate(path: Path) -> List[str]:
    spec = _load_json(path)
    _, items = _get_items(spec)

    errs: List[str] = []
    seen: set[str] = set()
    for i, item in enumerate(items):
        errs.extend(_validate_item(i, item))
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            n = item["name"].strip()
            if n:
                if n in seen:
                    errs.append(f"Duplicate column name in spec: {n!r}")
                seen.add(n)

    return errs


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True, help="Path to proxy_spec.json")
    args = p.parse_args()

    path = Path(args.spec)
    if not path.exists():
        print(f"ERROR: missing file: {path}")
        return 2

    errs = validate(path)
    if errs:
        print("INVALID proxy spec:")
        for e in errs:
            print(f"- {e}")
        return 2

    print("OK: proxy spec is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
main
