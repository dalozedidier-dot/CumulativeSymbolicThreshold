#!/usr/bin/env python3
"""Verify audit invariants for a QCC run directory.

This script checks that a run_dir is self-contained and auditable:
  1. Required contracts are staged in runs/<ts>/contracts/
  2. Stability outputs exist in runs/<ts>/stability/
  3. Manifest exists and hashes contracts, tables, figures, stability outputs
  4. Checks read only from run_dir (no global paths)

The test: if you zip only runs/<ts>/, you have everything to audit.

Usage:
  python -m tools.verify_audit_invariants --run-dir runs/20260301_120000
  python -m tools.verify_audit_invariants --out-root _ci_out/brisbane_stateprob
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


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


# ── Invariant 1: contracts staged ────────────────────────────────────────────

REQUIRED_CONTRACTS = [
    "contracts/POWER_CRITERIA.json",
    "contracts/STABILITY_CRITERIA.json",
]

RECOMMENDED_CONTRACTS = [
    "contracts/mapping_cross_conditions.json",
    "contracts/input_inventory.csv",
]


def check_contracts(run_dir: Path) -> List[str]:
    """Return list of error messages for missing required contracts."""
    errors = []
    for rel in REQUIRED_CONTRACTS:
        p = run_dir / rel
        if not p.exists():
            errors.append(f"MISSING required contract: {rel}")
    return errors


# ── Invariant 2: stability outputs ───────────────────────────────────────────

REQUIRED_STABILITY = [
    "stability/stability_summary.json",
]


def check_stability(run_dir: Path, *, require_stability: bool = True) -> List[str]:
    """Return list of error messages for missing stability outputs."""
    errors = []
    if not require_stability:
        return errors
    for rel in REQUIRED_STABILITY:
        p = run_dir / rel
        if not p.exists():
            errors.append(f"MISSING stability output: {rel}")
    return errors


# ── Invariant 3: manifest hashes ─────────────────────────────────────────────

REQUIRED_HASH_CATEGORIES = ["contracts/", "tables/", "figures/", "stability/"]


def check_manifest(run_dir: Path) -> List[str]:
    """Check manifest.json exists, is valid, and covers required categories."""
    errors = []
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        errors.append("MISSING manifest.json in run directory")
        return errors

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"INVALID manifest.json: {e}")
        return errors

    # Extract file paths from manifest (support both v1 schema formats)
    file_paths: List[str] = []
    if "files" in manifest and isinstance(manifest["files"], list):
        file_paths = [f["path"] for f in manifest["files"] if "path" in f]
    elif "entries" in manifest and isinstance(manifest["entries"], dict):
        file_paths = list(manifest["entries"].keys())
    else:
        errors.append("manifest.json has no 'files' or 'entries' key")
        return errors

    # Check that each required category has at least one entry
    for category in REQUIRED_HASH_CATEGORIES:
        has_entry = any(p.startswith(category) for p in file_paths)
        if not has_entry:
            errors.append(f"manifest.json missing entries for category: {category}")

    # Verify sha256 hashes for a sample of files
    sample_size = min(5, len(file_paths))
    for rel_path in file_paths[:sample_size]:
        abs_path = run_dir / rel_path
        if not abs_path.exists():
            errors.append(f"manifest references missing file: {rel_path}")
            continue
        # Find the expected hash
        expected_hash = None
        if "files" in manifest and isinstance(manifest["files"], list):
            for f in manifest["files"]:
                if f.get("path") == rel_path:
                    expected_hash = f.get("sha256")
                    break
        elif "entries" in manifest:
            expected_hash = manifest["entries"].get(rel_path)

        if expected_hash:
            actual_hash = _sha256_file(abs_path)
            if actual_hash != expected_hash:
                errors.append(
                    f"hash mismatch for {rel_path}: "
                    f"manifest={expected_hash[:16]}... actual={actual_hash[:16]}..."
                )

    return errors


# ── Invariant 3b: stability_summary reflects contract ────────────────────────


def check_stability_reflects_contract(run_dir: Path) -> List[str]:
    """Verify stability_summary.json threshold matches STABILITY_CRITERIA.json.

    This ensures the stability battery ran with the *frozen* contract thresholds,
    not with ad-hoc values. Any mismatch is a hard fail.
    """
    errors = []
    criteria_path = run_dir / "contracts" / "STABILITY_CRITERIA.json"
    summary_path = run_dir / "stability" / "stability_summary.json"

    if not criteria_path.exists() or not summary_path.exists():
        # Dependencies already checked by earlier invariants; skip here.
        return errors

    try:
        criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Cannot parse STABILITY_CRITERIA.json: {e}")
        return errors

    try:
        ss = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Cannot parse stability_summary.json: {e}")
        return errors

    # Verify criteria sha recorded in stability_summary matches the staged file
    criteria_sha = _sha256_file(criteria_path)
    recorded_sha = ss.get("criteria_sha256", "")
    if recorded_sha and recorded_sha != criteria_sha:
        errors.append(
            f"stability_summary.json criteria_sha256 mismatch: "
            f"recorded={recorded_sha[:16]}... actual={criteria_sha[:16]}..."
        )

    # The threshold used in the battery must match the contract value
    expected_rv = criteria.get("max_relative_variation") or criteria.get(
        "relative_variation_max"
    )
    if expected_rv is not None:
        sc = ss.get("stability_check", {})
        rv_check = sc.get("checks", {}).get("relative_variation", {})
        used_threshold = rv_check.get("threshold")
        if used_threshold is not None:
            if abs(float(used_threshold) - float(expected_rv)) > 1e-9:
                errors.append(
                    f"Stability threshold mismatch — contract says {expected_rv}, "
                    f"battery used {used_threshold}. "
                    "Run the stability battery with --stability-criteria contracts/STABILITY_CRITERIA.json."
                )

    return errors


# ── Invariant 4: standardized outputs ────────────────────────────────────────

REQUIRED_OUTPUTS = [
    "tables/summary.json",
    "manifest.json",
]

RECOMMENDED_OUTPUTS = [
    "tables/timeseries.csv",
    "figures/",
]


def check_standard_outputs(run_dir: Path) -> List[str]:
    """Check that standardized output files exist."""
    errors = []
    for rel in REQUIRED_OUTPUTS:
        p = run_dir / rel
        if not p.exists():
            errors.append(f"MISSING required output: {rel}")
    return errors


# ── Main verification ────────────────────────────────────────────────────────


def verify(
    run_dir: Path,
    *,
    require_stability: bool = True,
    strict: bool = True,
) -> Dict[str, Any]:
    """Run all audit invariant checks.

    Returns a dict with check results. If strict=True, non-empty errors
    means the verification failed.
    """
    all_errors: List[str] = []
    all_warnings: List[str] = []

    # 1. Contracts
    contract_errors = check_contracts(run_dir)
    all_errors.extend(contract_errors)

    for rel in RECOMMENDED_CONTRACTS:
        if not (run_dir / rel).exists():
            all_warnings.append(f"RECOMMENDED contract missing: {rel}")

    # 2. Stability
    stability_errors = check_stability(run_dir, require_stability=require_stability)
    all_errors.extend(stability_errors)

    # 2b. Stability reflects contract (only meaningful in full mode)
    contract_reflect_errors: List[str] = []
    if require_stability:
        contract_reflect_errors = check_stability_reflects_contract(run_dir)
        all_errors.extend(contract_reflect_errors)

    # 3. Manifest
    manifest_errors = check_manifest(run_dir)
    all_errors.extend(manifest_errors)

    # 4. Standard outputs
    output_errors = check_standard_outputs(run_dir)
    all_errors.extend(output_errors)

    for rel in RECOMMENDED_OUTPUTS:
        p = run_dir / rel
        if rel.endswith("/"):
            if not p.exists() or not p.is_dir() or not any(p.iterdir()):
                all_warnings.append(f"RECOMMENDED output directory empty/missing: {rel}")
        elif not p.exists():
            all_warnings.append(f"RECOMMENDED output missing: {rel}")

    passed = len(all_errors) == 0
    return {
        "run_dir": str(run_dir),
        "passed": passed,
        "errors": all_errors,
        "warnings": all_warnings,
        "checks": {
            "contracts": len(contract_errors) == 0,
            "stability": len(stability_errors) == 0,
            "stability_reflects_contract": len(contract_reflect_errors) == 0 if require_stability else True,
            "manifest": len(manifest_errors) == 0,
            "standard_outputs": len(output_errors) == 0,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify audit invariants for a QCC run")
    ap.add_argument("--out-root", default="", help="Output root; selects latest run_dir")
    ap.add_argument("--run-dir", default="", help="Explicit run directory to verify")
    ap.add_argument("--no-stability", action="store_true", help="Skip stability requirement (scan-only mode)")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    args = ap.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir)
    elif args.out_root:
        run_dir = _find_latest_run_dir(Path(args.out_root))
    else:
        print("ERROR: provide --run-dir or --out-root", file=sys.stderr)
        return 1

    if not run_dir.exists():
        print(f"ERROR: run directory does not exist: {run_dir}", file=sys.stderr)
        return 1

    result = verify(run_dir, require_stability=not args.no_stability)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"\nAudit Invariants: {status}")
        print(f"Run dir: {result['run_dir']}")
        print()
        for check_name, check_pass in result["checks"].items():
            flag = "OK" if check_pass else "FAIL"
            print(f"  [{flag}] {check_name}")
        if result["errors"]:
            print(f"\nErrors ({len(result['errors'])}):")
            for e in result["errors"]:
                print(f"  - {e}")
        if result["warnings"]:
            print(f"\nWarnings ({len(result['warnings'])}):")
            for w in result["warnings"]:
                print(f"  - {w}")
        print()

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
