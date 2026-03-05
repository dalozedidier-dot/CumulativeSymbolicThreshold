#!/usr/bin/env python3
"""repo_doctor.py — Health check for the CumulativeSymbolicThreshold repository.

Checks:
  1. Required top-level files exist (README, LICENSE, CHANGELOG, etc.)
  2. Frozen contracts are present and valid JSON
  3. ci_metrics/runs_index.csv exists and has expected columns
  4. ci_metrics: warn if any row has sector=unknown or empty run_mode
  5. docs/ canonical POINT_OF_TRUTH exists
  6. tools/ scripts are importable (syntax check via compileall)
  7. .github/workflows/ main workflows are present

Usage:
  python tools/repo_doctor.py            # full check, exit 0 if OK
  python tools/repo_doctor.py --json     # output JSON report
  python tools/repo_doctor.py --strict   # exit 1 on warnings too
"""
from __future__ import annotations

import argparse
import compileall
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).parent.parent.resolve()


# ── Check helpers ─────────────────────────────────────────────────────────────

def _err(msg: str) -> Tuple[str, str]:
    return ("ERROR", msg)


def _warn(msg: str) -> Tuple[str, str]:
    return ("WARNING", msg)


def _ok(msg: str) -> Tuple[str, str]:
    return ("OK", msg)


# ── Check 1: Required top-level files ────────────────────────────────────────

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "pyproject.toml",
    ".github/workflows/qcc_canonical_full.yml",
    ".github/workflows/collector.yml",
]

RECOMMENDED_FILES = [
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CITATION.cff",
    "docs/ORI_C_POINT_OF_TRUTH.md",
]


def check_required_files() -> List[Tuple[str, str]]:
    results = []
    for rel in REQUIRED_FILES:
        p = ROOT / rel
        if p.exists():
            results.append(_ok(f"Found required: {rel}"))
        else:
            results.append(_err(f"MISSING required file: {rel}"))
    for rel in RECOMMENDED_FILES:
        p = ROOT / rel
        if p.exists():
            results.append(_ok(f"Found recommended: {rel}"))
        else:
            results.append(_warn(f"Missing recommended file: {rel}"))
    return results


# ── Check 2: Contracts ───────────────────────────────────────────────────────

REQUIRED_CONTRACTS = [
    "contracts/POWER_CRITERIA.json",
    "contracts/STABILITY_CRITERIA.json",
]


def check_contracts() -> List[Tuple[str, str]]:
    results = []
    for rel in REQUIRED_CONTRACTS:
        p = ROOT / rel
        if not p.exists():
            results.append(_err(f"MISSING contract: {rel}"))
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                results.append(_err(f"Contract not a JSON object: {rel}"))
            else:
                results.append(_ok(f"Contract valid JSON: {rel}"))
        except Exception as e:
            results.append(_err(f"Contract invalid JSON: {rel}: {e}"))
    return results


# ── Check 3 & 4: ci_metrics ──────────────────────────────────────────────────

CI_METRICS_EXPECTED_COLUMNS = {
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
}


def check_ci_metrics() -> List[Tuple[str, str]]:
    results = []
    runs_index = ROOT / "ci_metrics" / "runs_index.csv"
    if not runs_index.exists():
        results.append(_err("ci_metrics/runs_index.csv not found"))
        return results

    try:
        with open(runs_index, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = set(reader.fieldnames or [])
    except Exception as e:
        results.append(_err(f"Cannot read ci_metrics/runs_index.csv: {e}"))
        return results

    missing_cols = CI_METRICS_EXPECTED_COLUMNS - fieldnames
    if missing_cols:
        results.append(_err(f"runs_index.csv missing columns: {sorted(missing_cols)}"))
    else:
        results.append(_ok("runs_index.csv has all expected columns"))

    dirty_rows = [
        (i + 2, r.get("github_run_id", "?"))
        for i, r in enumerate(rows)
        if r.get("sector", "") in ("", "unknown") or not r.get("run_mode", "").strip()
    ]
    if dirty_rows:
        detail = ", ".join(f"line {ln} (run {rid})" for ln, rid in dirty_rows[:5])
        results.append(
            _warn(
                f"{len(dirty_rows)} row(s) have sector=unknown or empty run_mode: {detail}"
            )
        )
    else:
        results.append(_ok("All runs_index.csv rows have sector and run_mode set"))

    # Check for non-empty sha fields
    missing_sha_rows = [
        (i + 2, r.get("github_run_id", "?"))
        for i, r in enumerate(rows)
        if not r.get("manifest_sha256", "").strip()
        or not r.get("stability_criteria_sha256", "").strip()
    ]
    if missing_sha_rows:
        detail = ", ".join(f"line {ln}" for ln, _ in missing_sha_rows[:5])
        results.append(
            _warn(
                f"{len(missing_sha_rows)} row(s) have empty manifest_sha256 or stability_criteria_sha256: {detail}"
            )
        )
    else:
        results.append(_ok("All runs_index.csv rows have manifest_sha256 and stability_criteria_sha256"))

    results.append(_ok(f"runs_index.csv: {len(rows)} row(s) total"))
    return results


# ── Check 5: docs / point of truth ───────────────────────────────────────────

def check_docs() -> List[Tuple[str, str]]:
    results = []
    pot = ROOT / "docs" / "ORI_C_POINT_OF_TRUTH.md"
    if pot.exists():
        results.append(_ok("docs/ORI_C_POINT_OF_TRUTH.md present"))
    else:
        results.append(_err("docs/ORI_C_POINT_OF_TRUTH.md MISSING"))

    # Warn if root ORIC_POINT_OF_TRUTH.md is not a redirect stub
    root_pot = ROOT / "ORIC_POINT_OF_TRUTH.md"
    if root_pot.exists():
        content = root_pot.read_text(encoding="utf-8")
        if "alias" in content.lower() or "redirect" in content.lower():
            results.append(_ok("ORIC_POINT_OF_TRUTH.md is a redirect stub (OK)"))
        else:
            results.append(
                _warn(
                    "ORIC_POINT_OF_TRUTH.md exists but doesn't look like a redirect — "
                    "may duplicate docs/ORI_C_POINT_OF_TRUTH.md"
                )
            )
    return results


# ── Check 6: tools/ syntax ───────────────────────────────────────────────────

def check_tools_syntax() -> List[Tuple[str, str]]:
    results = []
    tools_dir = ROOT / "tools"
    if not tools_dir.exists():
        results.append(_err("tools/ directory not found"))
        return results

    # Redirect compileall output to capture errors
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    ok = compileall.compile_dir(
        str(tools_dir),
        quiet=2,
        force=True,
        legacy=False,
    )
    sys.stdout = old_stdout
    output = buf.getvalue()

    if ok:
        py_files = list(tools_dir.glob("*.py"))
        results.append(_ok(f"tools/ syntax OK ({len(py_files)} .py files)"))
    else:
        results.append(_err(f"tools/ has syntax errors:\n{output}"))
    return results


# ── Check 7: main workflows ──────────────────────────────────────────────────

REQUIRED_WORKFLOWS = [
    ".github/workflows/qcc_canonical_full.yml",
    ".github/workflows/collector.yml",
    ".github/workflows/ci.yml",
]

RECOMMENDED_WORKFLOWS = [
    ".github/workflows/qcc_real_data_smoke.yml",
    ".github/workflows/real_data_smoke.yml",
]


def check_workflows() -> List[Tuple[str, str]]:
    results = []
    for rel in REQUIRED_WORKFLOWS:
        p = ROOT / rel
        if p.exists():
            results.append(_ok(f"Workflow present: {rel}"))
        else:
            results.append(_err(f"MISSING required workflow: {rel}"))
    for rel in RECOMMENDED_WORKFLOWS:
        p = ROOT / rel
        if p.exists():
            results.append(_ok(f"Workflow present: {rel}"))
        else:
            results.append(_warn(f"Missing recommended workflow: {rel}"))
    return results


# ── Main ─────────────────────────────────────────────────────────────────────

CHECKS = [
    ("required_files", check_required_files),
    ("contracts", check_contracts),
    ("ci_metrics", check_ci_metrics),
    ("docs", check_docs),
    ("tools_syntax", check_tools_syntax),
    ("workflows", check_workflows),
]


def run_all() -> Dict[str, Any]:
    report: Dict[str, Any] = {"checks": {}, "errors": [], "warnings": [], "ok_count": 0}

    for name, fn in CHECKS:
        items = fn()
        report["checks"][name] = items
        for level, msg in items:
            if level == "ERROR":
                report["errors"].append(f"[{name}] {msg}")
            elif level == "WARNING":
                report["warnings"].append(f"[{name}] {msg}")
            else:
                report["ok_count"] += 1

    report["passed"] = len(report["errors"]) == 0
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Repository health check")
    ap.add_argument("--json", action="store_true", help="Output JSON report")
    ap.add_argument("--strict", action="store_true", help="Exit 1 on warnings too")
    args = ap.parse_args()

    report = run_all()

    if args.json:
        # Serialize the checks dict (list of tuples → list of dicts)
        serializable = {
            "passed": report["passed"],
            "ok_count": report["ok_count"],
            "errors": report["errors"],
            "warnings": report["warnings"],
            "checks": {
                name: [{"level": lvl, "msg": msg} for lvl, msg in items]
                for name, items in report["checks"].items()
            },
        }
        print(json.dumps(serializable, indent=2))
    else:
        print("\n=== repo_doctor ===\n")
        for name, items in report["checks"].items():
            print(f"  [{name}]")
            for level, msg in items:
                prefix = "  ✓" if level == "OK" else ("  ⚠" if level == "WARNING" else "  ✗")
                print(f"  {prefix} {msg}")
            print()

        if report["errors"]:
            print(f"ERRORS ({len(report['errors'])}):")
            for e in report["errors"]:
                print(f"  ✗ {e}")
            print()

        if report["warnings"]:
            print(f"Warnings ({len(report['warnings'])}):")
            for w in report["warnings"]:
                print(f"  ⚠ {w}")
            print()

        status = "PASS" if report["passed"] else "FAIL"
        print(f"Result: {status}  ({report['ok_count']} OK, {len(report['warnings'])} warnings, {len(report['errors'])} errors)")

    if not report["passed"]:
        return 1
    if args.strict and report["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""Repo doctor (ORI-C)

But : vérifier rapidement que l'arbo, les points de vérité et les invariants CI sont cohérents.
Sortie : 0 si OK, 1 si warnings, 2 si erreurs.

Ce script ne modifie rien. Il sert de check local et peut être branché en CI si souhaité.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ERRORS = 0
WARNS = 0

def err(msg: str) -> None:
    global ERRORS
    ERRORS += 1
    print(f"[ERR] {msg}")

def warn(msg: str) -> None:
    global WARNS
    WARNS += 1
    print(f"[WARN] {msg}")

def ok(msg: str) -> None:
    print(f"[OK] {msg}")

def main() -> int:
    # Point of truth
    pot = ROOT / "docs" / "ORI_C_POINT_OF_TRUTH.md"
    if not pot.exists():
        err("docs/ORI_C_POINT_OF_TRUTH.md manquant (point de vérité attendu).")
    else:
        ok("Point de vérité présent.")

    # Root redirect file optional
    pot_root = ROOT / "ORIC_POINT_OF_TRUTH.md"
    if pot_root.exists():
        warn("ORIC_POINT_OF_TRUTH.md en racine présent. Doit être un redirect de compatibilité (pas une 2e vérité).")

    # Data duplication note
    if (ROOT/"03_Data").exists() and (ROOT/"data").exists():
        ok("03_Data/ et data/ coexistent. Vérifier docs/REPO_LAYOUT.md pour règles de vérité.")

    # Requirements path sanity
    req_qcc_root = ROOT / "requirements-qcc-stateprob.txt"
    req_qcc_alt = ROOT / "requirements" / "requirements-qcc-stateprob.txt"
    if not req_qcc_root.exists() and not req_qcc_alt.exists():
        err("Requirements QCC stateprob introuvables (requirements-qcc-stateprob.txt ou requirements/requirements-qcc-stateprob.txt).")
    else:
        ok("Requirements QCC stateprob présents (au moins un chemin).")

    # CI metrics directory
    if not (ROOT/"ci_metrics").exists():
        warn("ci_metrics/ absent. Normal si collector pas encore exécuté.")
    else:
        ok("ci_metrics/ présent.")

    if ERRORS:
        return 2
    if WARNS:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
main
