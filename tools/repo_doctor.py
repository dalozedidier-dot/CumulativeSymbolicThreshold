#!/usr/bin/env python3
"""Repository health-check utility.

Public API (used by tests):
    check_contracts()  -> list[tuple[str, str]]
    check_ci_metrics() -> list[tuple[str, str]]
    check_docs()       -> list[tuple[str, str]]
    run_all()          -> dict  {"passed": bool, "errors": list, "warnings": list}

The doctor is deliberately conservative: it checks repository hygiene, not
scientific validity. It should catch stale workflow names, executable YAML files
left in `.github/workflows_disabled/`, and malformed CI metrics history.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ACTIVE_WORKFLOWS = [
    ".github/workflows/ci_smoke.yml",
    ".github/workflows/nightly_full_proof.yml",
    ".github/workflows/diagnostic_cap_robustness.yml",
    ".github/workflows/real_data_sector_pilots.yml",
    ".github/workflows/qcc_stateprob_full.yml",
    ".github/workflows/release_replication_bundle.yml",
    ".github/workflows/integrity_archive_portability.yml",
    ".github/workflows/metrics_collector.yml",
]

LEGACY_WORKFLOWS = [
    ".github/workflows/ci.yml",
    ".github/workflows/nightly.yml",
    ".github/workflows/cap_robustness.yml",
    ".github/workflows/archive_portability.yml",
    ".github/workflows/collector.yml",
    ".github/workflows/qcc_canonical_full.yml",
    ".github/workflows/replication_bundle.yml",
    ".github/workflows/sector_pilots.yml",
]

CI_METRICS_FIELDS = [
    "github_run_id",
    "run_dir_name",
    "dataset_id",
    "sector",
    "run_mode",
    "evidence_strength",
    "all_pass",
    "manifest_sha256",
    "stability_criteria_sha256",
    "commit_sha",
    "workflow_source",
]

HEX64_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
VALID_RUN_MODES = {"smoke", "smoke_ci", "full", "full_statistical", "diagnostic", "pilot", "release", "maintenance", "integrity", "unknown"}


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

def _is_blank_or_hex64(value: str) -> bool:
    return value == "" or bool(HEX64_RE.fullmatch(value))


def check_ci_metrics() -> list[tuple[str, str]]:
    """Validate ci_metrics/runs_index.csv structure and data quality."""
    results: list[tuple[str, str]] = []
    p = ROOT / "ci_metrics" / "runs_index.csv"
    if not p.exists():
        results.append(("ERROR", "Missing ci_metrics/runs_index.csv"))
        return results

    try:
        with p.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            if fields != CI_METRICS_FIELDS:
                results.append(("ERROR", "ci_metrics/runs_index.csv: schema does not match canonical fields"))
                return results

            bad_mode = 0
            bad_hash = 0
            bad_commit = 0
            bad_run_id = 0
            row_count = 0
            for row in reader:
                row_count += 1
                run_id = (row.get("github_run_id") or "").strip()
                sector = (row.get("sector") or "").strip()
                run_mode = (row.get("run_mode") or "").strip()
                manifest_sha = (row.get("manifest_sha256") or "").strip()
                crit_sha = (row.get("stability_criteria_sha256") or "").strip()
                commit_sha = (row.get("commit_sha") or "").strip()

                if run_id and not run_id.isdigit():
                    bad_run_id += 1
                if sector.lower() == "unknown" or run_mode == "" or run_mode not in VALID_RUN_MODES:
                    bad_mode += 1
                if not _is_blank_or_hex64(manifest_sha) or not _is_blank_or_hex64(crit_sha):
                    bad_hash += 1
                if commit_sha and not SHA_RE.fullmatch(commit_sha):
                    bad_commit += 1

        if row_count == 0:
            results.append(("OK", "ci_metrics/runs_index.csv: canonical schema present; no rows yet"))
            return results
        if bad_run_id:
            results.append(("WARNING", f"ci_metrics/runs_index.csv: {bad_run_id} rows with non-numeric github_run_id"))
        if bad_mode:
            results.append(("WARNING", f"ci_metrics/runs_index.csv: {bad_mode} rows with sector=unknown or invalid run_mode"))
        else:
            results.append(("OK", "ci_metrics/runs_index.csv: sector/run_mode fields consistent"))
        if bad_hash:
            results.append(("WARNING", f"ci_metrics/runs_index.csv: {bad_hash} rows with malformed hash fields"))
        else:
            results.append(("OK", "ci_metrics/runs_index.csv: hash fields consistent"))
        if bad_commit:
            results.append(("WARNING", f"ci_metrics/runs_index.csv: {bad_commit} rows with malformed commit_sha"))
        else:
            results.append(("OK", "ci_metrics/runs_index.csv: commit_sha fields consistent"))
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
    """Validate the active GitHub Actions surface."""
    results: list[tuple[str, str]] = []
    for rel in ACTIVE_WORKFLOWS:
        p = ROOT / rel
        if p.exists():
            results.append(("OK", f"Present: {rel}"))
        else:
            results.append(("ERROR", f"Missing required workflow: {rel}"))

    for rel in LEGACY_WORKFLOWS:
        p = ROOT / rel
        if p.exists():
            results.append(("ERROR", f"Legacy workflow still active: {rel}"))

    disabled_dir = ROOT / ".github" / "workflows_disabled"
    disabled_yml = []
    if disabled_dir.exists():
        disabled_yml = sorted(disabled_dir.glob("*.yml")) + sorted(disabled_dir.glob("*.yaml"))
    if disabled_yml:
        names = ", ".join(p.name for p in disabled_yml[:8])
        suffix = "..." if len(disabled_yml) > 8 else ""
        results.append(("ERROR", f"Executable YAML files remain in workflows_disabled: {names}{suffix}"))
    else:
        results.append(("OK", "No executable YAML files in .github/workflows_disabled/"))

    recommended = ["requirements-qcc-stateprob.txt"]
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
    """Run every check and return a structured report."""
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
    sections = check_contracts() + check_ci_metrics() + check_docs() + check_workflows()
    report = {
        "errors": [msg for lvl, msg in sections if lvl == "ERROR"],
        "warnings": [msg for lvl, msg in sections if lvl == "WARNING"],
    }
    for lvl, msg in sections:
        print(f"[{lvl}] {msg}")
    ok_count = sum(1 for lvl, _ in sections if lvl == "OK")
    n_err = len(report["errors"])
    n_warn = len(report["warnings"])
    print(f"SUMMARY: status={'FAIL' if n_err else 'PASS'} | ok={ok_count} warnings={n_warn} errors={n_err}")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
