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
"""

from __future__ import annotations

import argparse
import json
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
