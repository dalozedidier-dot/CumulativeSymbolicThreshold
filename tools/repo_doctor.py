#!/usr/bin/env python3
"""Repository health-check utility.

Public API (used by tests):
    check_contracts()  -> list[tuple[str, str]]
    check_ci_metrics() -> list[tuple[str, str]]
    check_docs()       -> list[tuple[str, str]]
    run_all()          -> dict  {"passed": bool, "errors": list, "warnings": list}

Each check_*() function returns a list of (level, message) tuples where
level is one of "OK", "WARNING", "ERROR".
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# check_contracts
# ---------------------------------------------------------------------------

def check_contracts() -> list[tuple[str, str]]:
    """Validate contracts/POWER_CRITERIA.json and STABILITY_CRITERIA.json."""
    results: list[tuple[str, str]] = []
    contracts_dir = ROOT / "contracts"
    for name in ("POWER_CRITERIA.json", "STABILITY_CRITERIA.json"):
        p = contracts_dir / name
        if not p.exists():
            results.append(("ERROR", f"Missing contract file: {name}"))
            continue
        try:
            json.loads(p.read_text(encoding="utf-8"))
            results.append(("OK", f"Valid JSON: {name}"))
        except (json.JSONDecodeError, ValueError):
            results.append(("ERROR", f"Invalid JSON in {name}"))
    return results


# ---------------------------------------------------------------------------
# check_ci_metrics
# ---------------------------------------------------------------------------

def check_ci_metrics() -> list[tuple[str, str]]:
    """Validate ci_metrics/runs_index.csv structure and data quality."""
    results: list[tuple[str, str]] = []
    p = ROOT / "ci_metrics" / "runs_index.csv"
    if not p.exists():
        results.append(("ERROR", "Missing ci_metrics/runs_index.csv"))
        return results
    bad_mode = 0
    bad_hash = 0
    try:
        with p.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sector = (row.get("sector") or "").strip()
                run_mode = (row.get("run_mode") or "").strip()
                manifest_sha = (row.get("manifest_sha256") or "").strip()
                crit_sha = (row.get("stability_criteria_sha256") or "").strip()
                if sector.lower() == "unknown" or run_mode == "":
                    bad_mode += 1
                if manifest_sha == "" or crit_sha == "":
                    bad_hash += 1
        if bad_mode:
            results.append(("WARNING", f"ci_metrics/runs_index.csv: {bad_mode} rows with sector=unknown or run_mode empty"))
        else:
            results.append(("OK", "ci_metrics/runs_index.csv: sector/run_mode fields consistent"))
        if bad_hash:
            results.append(("WARNING", f"ci_metrics/runs_index.csv: {bad_hash} rows with manifest_sha256 or stability_criteria_sha256 empty"))
        else:
            results.append(("OK", "ci_metrics/runs_index.csv: hash fields consistent"))
    except Exception as e:
        results.append(("WARNING", f"Could not parse ci_metrics/runs_index.csv: {e}"))
    return results


# ---------------------------------------------------------------------------
# check_docs
# ---------------------------------------------------------------------------

def check_docs() -> list[tuple[str, str]]:
    """Validate docs/ORI_C_POINT_OF_TRUTH.md (canonical path)."""
    results: list[tuple[str, str]] = []
    canon_pot = ROOT / "docs" / "ORI_C_POINT_OF_TRUTH.md"
    if canon_pot.exists():
        results.append(("OK", "Canonical Point of Truth present: docs/ORI_C_POINT_OF_TRUTH.md"))
    else:
        results.append(("ERROR", "Missing canonical Point of Truth: docs/ORI_C_POINT_OF_TRUTH.md"))

    root_pot = ROOT / "ORIC_POINT_OF_TRUTH.md"
    if root_pot.exists():
        txt = root_pot.read_text(encoding="utf-8", errors="ignore").lower()
        if "redirect" in txt or "ori_c_point_of_truth.md" in txt:
            results.append(("OK", "ORIC_POINT_OF_TRUTH.md is an explicit redirect to docs/ORI_C_POINT_OF_TRUTH.md"))
        else:
            results.append(("WARNING", "ORIC_POINT_OF_TRUTH.md may duplicate docs/ORI_C_POINT_OF_TRUTH.md"))
    return results


# ---------------------------------------------------------------------------
# check_workflows
# ---------------------------------------------------------------------------

def check_workflows() -> list[tuple[str, str]]:
    """Validate presence of CI workflow files."""
    results: list[tuple[str, str]] = []
    required = [
        ".github/workflows/ci.yml",
        ".github/workflows/nightly.yml",
        ".github/workflows/qcc_canonical_full.yml",
        ".github/workflows/collector.yml",
        ".github/workflows/sector_pilots.yml",
    ]
    recommended = [
        "requirements-qcc-stateprob.txt",
    ]
    for rel in required:
        p = ROOT / rel
        if p.exists():
            results.append(("OK", f"Present: {rel}"))
        else:
            results.append(("ERROR", f"Missing required file: {rel}"))
    for rel in recommended:
        p = ROOT / rel
        alt = ROOT / "requirements" / rel
        if p.exists() or alt.exists():
            results.append(("OK", f"Present: {rel}"))
        else:
            results.append(("WARNING", f"Missing recommended file: {rel}"))
    return results


# ---------------------------------------------------------------------------
# run_all
# ---------------------------------------------------------------------------

def run_all() -> dict:
    """Run every check and return a structured report.

    Returns
    -------
    dict with keys:
        passed   : bool  – True when zero errors
        errors   : list[str]
        warnings : list[str]
    """
    all_results: list[tuple[str, str]] = []
    all_results.extend(check_contracts())
    all_results.extend(check_ci_metrics())
    all_results.extend(check_docs())
    all_results.extend(check_workflows())

    errors = [msg for lvl, msg in all_results if lvl == "ERROR"]
    warnings = [msg for lvl, msg in all_results if lvl == "WARNING"]
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> int:
    report = run_all()
    for lvl, msg in (
        check_contracts()
        + check_ci_metrics()
        + check_docs()
        + check_workflows()
    ):
        print(f"[{lvl}] {msg}")
    ok_count = sum(
        1 for lvl, _ in (
            check_contracts()
            + check_ci_metrics()
            + check_docs()
            + check_workflows()
        )
        if lvl == "OK"
    )
    n_err = len(report["errors"])
    n_warn = len(report["warnings"])
    print(f"SUMMARY: status={'FAIL' if n_err else 'PASS'} | ok={ok_count} warnings={n_warn} errors={n_err}")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
