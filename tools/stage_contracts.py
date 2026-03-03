#!/usr/bin/env python3
"""Stage all audit contracts into a QCC run directory.

This is the single entry point for contract staging. It copies the frozen
contract files into runs/<ts>/contracts/ so that the run directory is
self-contained and auditable.

Required contracts (fail-fast if any is missing):
  - POWER_CRITERIA.json
  - STABILITY_CRITERIA.json
  - mapping file (mapping*.json)
  - input_inventory.csv (generated from dataset scan)

Usage:
  python -m tools.stage_contracts \
      --out-root _ci_out/brisbane_stateprob \
      --power-criteria contracts/POWER_CRITERIA.json \
      --stability-criteria contracts/STABILITY_CRITERIA.json \
      --mapping contracts/mapping_cross_conditions.json \
      --input-inventory /path/to/input_inventory.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_latest_run_dir(out_root: Path) -> Path:
    runs_dir = out_root / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError(f"runs directory not found: {runs_dir}")
    run_dirs = sorted([p for p in runs_dir.iterdir() if p.is_dir()])
    if not run_dirs:
        raise FileNotFoundError(f"no run directories found under: {runs_dir}")
    return run_dirs[-1]


def stage_contracts(
    run_dir: Path,
    *,
    power_criteria: Path,
    stability_criteria: Path,
    mapping: Optional[Path] = None,
    input_inventory: Optional[Path] = None,
    extra_files: Optional[List[Path]] = None,
    fail_fast: bool = True,
) -> Dict[str, Any]:
    """Stage contract files into run_dir/contracts/.

    Returns a dict with staged paths and sha256 hashes.
    Raises SystemExit if fail_fast=True and a required file is missing.
    """
    contracts_dir = run_dir / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)

    required: Dict[str, Optional[Path]] = {
        "POWER_CRITERIA.json": power_criteria,
        "STABILITY_CRITERIA.json": stability_criteria,
    }

    optional: Dict[str, Optional[Path]] = {}
    if mapping is not None:
        # Use a canonical name for mapping files
        optional["mapping_cross_conditions.json"] = mapping
    if input_inventory is not None:
        optional["input_inventory.csv"] = input_inventory

    staged: Dict[str, Any] = {}
    errors: List[str] = []

    # Stage required files
    for dst_name, src_path in required.items():
        if src_path is None or not src_path.exists():
            msg = f"MISSING required contract: {dst_name} (source: {src_path})"
            errors.append(msg)
            continue
        dst = contracts_dir / dst_name
        shutil.copy2(src_path, dst)
        staged[dst_name] = {
            "source": str(src_path),
            "staged": str(dst),
            "sha256": _sha256_file(dst),
        }

    # Stage optional files
    for dst_name, src_path in optional.items():
        if src_path is None or not src_path.exists():
            continue
        dst = contracts_dir / dst_name
        shutil.copy2(src_path, dst)
        staged[dst_name] = {
            "source": str(src_path),
            "staged": str(dst),
            "sha256": _sha256_file(dst),
        }

    # Stage extra files
    if extra_files:
        for ef in extra_files:
            if ef.exists():
                dst = contracts_dir / ef.name
                shutil.copy2(ef, dst)
                staged[ef.name] = {
                    "source": str(ef),
                    "staged": str(dst),
                    "sha256": _sha256_file(dst),
                }

    if errors and fail_fast:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(
            f"Contract staging failed: {len(errors)} required contract(s) missing. "
            "Zero fallback — fix the missing files before proceeding."
        )

    return {
        "run_dir": str(run_dir),
        "contracts_dir": str(contracts_dir),
        "staged": staged,
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage audit contracts into run directory")
    ap.add_argument("--out-root", required=True, help="Output root containing runs/<ts>/")
    ap.add_argument("--run-dir", default="", help="Explicit run dir; if empty, uses latest")
    ap.add_argument("--power-criteria", default="contracts/POWER_CRITERIA.json")
    ap.add_argument("--stability-criteria", default="contracts/STABILITY_CRITERIA.json")
    ap.add_argument("--mapping", default="", help="Mapping JSON file (optional)")
    ap.add_argument("--input-inventory", default="", help="Input inventory CSV (optional)")
    ap.add_argument("--extra", nargs="*", default=[], help="Extra files to stage")
    ap.add_argument("--no-fail-fast", action="store_true", help="Warn instead of failing on missing contracts")
    args = ap.parse_args()

    out_root = Path(args.out_root)
    run_dir = Path(args.run_dir) if args.run_dir else _find_latest_run_dir(out_root)

    result = stage_contracts(
        run_dir,
        power_criteria=Path(args.power_criteria),
        stability_criteria=Path(args.stability_criteria),
        mapping=Path(args.mapping) if args.mapping else None,
        input_inventory=Path(args.input_inventory) if args.input_inventory else None,
        extra_files=[Path(p) for p in args.extra] if args.extra else None,
        fail_fast=not args.no_fail_fast,
    )

    print(json.dumps({"ok": True, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
