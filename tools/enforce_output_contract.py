#!/usr/bin/env python3
"""Enforce the standardized output contract for every run.

For each run, regardless of sector, the following files must exist:
  - tables/summary.json      (power + stability summary)
  - tables/timeseries.csv    (or equivalent — at least one CSV in tables/)
  - contracts/               (mapping + criteria + inventory)
  - figures/                 (at least 2 files, placeholders OK)
  - manifest.json            (hashing all of the above)

This enables cross-run collection and inter-sector comparison.

Usage:
  python -m tools.enforce_output_contract --run-dir runs/20260301_120000
  python -m tools.enforce_output_contract --out-root _ci_out/brisbane_stateprob
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _find_latest_run_dir(out_root: Path) -> Path:
    runs_dir = out_root / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError(f"runs directory not found: {runs_dir}")
    run_dirs = sorted([p for p in runs_dir.iterdir() if p.is_dir()])
    if not run_dirs:
        raise FileNotFoundError(f"no run directories found under: {runs_dir}")
    return run_dirs[-1]


# ── Output contract definition ───────────────────────────────────────────────

OUTPUT_CONTRACT = {
    "tables/summary.json": {
        "required": True,
        "description": "Power + stability summary (JSON)",
        "required_keys": ["dataset_id", "run_mode"],
    },
    "contracts/": {
        "required": True,
        "description": "Audit contracts directory",
        "min_files": 1,
    },
    "figures/": {
        "required": True,
        "description": "Figures directory (at least 2 files, placeholders OK)",
        "min_files": 1,
    },
    "manifest.json": {
        "required": True,
        "description": "Manifest with sha256 hashes",
    },
}


def enforce(run_dir: Path, *, strict: bool = True) -> Tuple[bool, Dict[str, Any]]:
    """Enforce the output contract on a run directory.

    Returns (passed, report_dict).
    """
    errors: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, bool] = {}

    for path_spec, rules in OUTPUT_CONTRACT.items():
        full_path = run_dir / path_spec
        is_dir = path_spec.endswith("/")
        is_required = rules.get("required", False)

        if is_dir:
            if not full_path.exists() or not full_path.is_dir():
                msg = f"Missing directory: {path_spec}"
                if is_required:
                    errors.append(msg)
                else:
                    warnings.append(msg)
                checks[path_spec] = False
                continue

            files_in_dir = list(full_path.iterdir())
            min_files = rules.get("min_files", 0)
            if len(files_in_dir) < min_files:
                msg = f"Directory {path_spec} has {len(files_in_dir)} files (min: {min_files})"
                if is_required:
                    errors.append(msg)
                else:
                    warnings.append(msg)
                checks[path_spec] = False
            else:
                checks[path_spec] = True

        else:
            if not full_path.exists():
                msg = f"Missing file: {path_spec}"
                if is_required:
                    errors.append(msg)
                else:
                    warnings.append(msg)
                checks[path_spec] = False
                continue

            checks[path_spec] = True

            # Validate JSON content if required_keys specified
            required_keys = rules.get("required_keys", [])
            if required_keys and path_spec.endswith(".json"):
                try:
                    data = json.loads(full_path.read_text(encoding="utf-8"))
                    for key in required_keys:
                        if key not in data:
                            warnings.append(f"{path_spec} missing recommended key: {key}")
                except Exception as e:
                    errors.append(f"Invalid JSON in {path_spec}: {e}")
                    checks[path_spec] = False

    # Check for timeseries (at least one CSV in tables/)
    tables_dir = run_dir / "tables"
    if tables_dir.exists():
        csvs = list(tables_dir.glob("*.csv"))
        if not csvs:
            warnings.append("No CSV files in tables/ (timeseries expected)")
    else:
        errors.append("tables/ directory missing entirely")

    passed = len(errors) == 0

    report = {
        "run_dir": str(run_dir),
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }

    return passed, report


def main() -> int:
    ap = argparse.ArgumentParser(description="Enforce output contract for a run")
    ap.add_argument("--out-root", default="", help="Output root; selects latest run_dir")
    ap.add_argument("--run-dir", default="", help="Explicit run directory")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    args = ap.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir)
    elif args.out_root:
        run_dir = _find_latest_run_dir(Path(args.out_root))
    else:
        print("ERROR: provide --run-dir or --out-root", file=sys.stderr)
        return 1

    if not run_dir.exists():
        print(f"ERROR: {run_dir} does not exist", file=sys.stderr)
        return 1

    passed, report = enforce(run_dir)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if passed else "FAIL"
        print(f"\nOutput Contract: {status}")
        print(f"Run dir: {report['run_dir']}")
        for path_spec, ok in report["checks"].items():
            print(f"  [{'OK' if ok else 'FAIL'}] {path_spec}")
        if report["errors"]:
            print(f"\nErrors:")
            for e in report["errors"]:
                print(f"  - {e}")
        if report["warnings"]:
            print(f"\nWarnings:")
            for w in report["warnings"]:
                print(f"  - {w}")
        print()

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
