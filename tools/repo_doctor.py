#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OK = 0
WARNS = 0
ERRS = 0

def ok(msg: str) -> None:
    global OK
    OK += 1
    print(f"[OK] {msg}")

def warn(msg: str) -> None:
    global WARNS
    WARNS += 1
    print(f"[WARN] {msg}")

def err(msg: str) -> None:
    global ERRS
    ERRS += 1
    print(f"[ERR] {msg}")

def check_file(rel: str, required: bool = True) -> None:
    p = ROOT / rel
    if p.exists():
        ok(f"Present: {rel}")
    else:
        if required:
            err(f"Missing required file: {rel}")
        else:
            warn(f"Missing recommended file: {rel}")

def check_point_of_truth() -> None:
    root_pot = ROOT / "ORIC_POINT_OF_TRUTH.md"
    canon_pot = ROOT / "ORI_C_POINT_OF_TRUTH.md"
    if canon_pot.exists():
        ok("Canonical Point of Truth present: ORI_C_POINT_OF_TRUTH.md")
    else:
        err("Missing canonical Point of Truth: ORI_C_POINT_OF_TRUTH.md")
    if root_pot.exists():
        txt = root_pot.read_text(encoding="utf-8", errors="ignore").lower()
        if "redirect" in txt and "ori_c_point_of_truth.md" in txt:
            ok("ORIC_POINT_OF_TRUTH.md is an explicit redirect")
        else:
            warn("ORIC_POINT_OF_TRUTH.md may duplicate ORI_C_POINT_OF_TRUTH.md")
    else:
        ok("No legacy Point of Truth alias at root")

def check_ci_metrics() -> None:
    p = ROOT / "ci_metrics" / "runs_index.csv"
    if not p.exists():
        warn("ci_metrics/runs_index.csv absent")
        return
    bad_mode = 0
    bad_hash = 0
    try:
        with p.open("r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                sector = (row.get("sector") or "").strip()
                run_mode = (row.get("run_mode") or "").strip()
                manifest_sha = (row.get("manifest_sha256") or "").strip()
                crit_sha = (row.get("stability_criteria_sha256") or "").strip()
                if sector.lower() == "unknown" or run_mode == "":
                    bad_mode += 1
                if manifest_sha == "" or crit_sha == "":
                    bad_hash += 1
        if bad_mode:
            warn(f"ci_metrics/runs_index.csv: {bad_mode} rows with sector=unknown or run_mode empty")
        else:
            ok("ci_metrics/runs_index.csv: sector/run_mode fields look consistent")
        if bad_hash:
            warn(f"ci_metrics/runs_index.csv: {bad_hash} rows with manifest_sha256 or stability_criteria_sha256 empty")
        else:
            ok("ci_metrics/runs_index.csv: hash fields look consistent")
    except Exception as e:
        warn(f"Could not parse ci_metrics/runs_index.csv: {e}")

def main() -> int:
    # Required workflows for current strategy
    required = [
        ".github/workflows/ci.yml",
        ".github/workflows/nightly.yml",
        ".github/workflows/qcc_canonical_full.yml",
        ".github/workflows/qcc_real_data_smoke.yml",
        ".github/workflows/real_data_smoke.yml",
        ".github/workflows/real_data_matrix.yml",
    ]
    recommended = [
        ".github/workflows/real_data_canonical_T1_T8.yml",
        ".github/workflows/qcc_polaron_real_smoke.yml",
        ".github/workflows/symbolic_suite.yml",
        ".github/workflows/t9_diagnostics.yml",
    ]
    for rel in required:
        check_file(rel, required=True)
    for rel in recommended:
        check_file(rel, required=False)

    # Requirements sanity
    if (ROOT / "requirements-qcc-stateprob.txt").exists() or (ROOT / "requirements" / "requirements-qcc-stateprob.txt").exists():
        ok("QCC requirements path present")
    else:
        err("Missing QCC requirements file")

    check_point_of_truth()
    check_ci_metrics()

    print(f"SUMMARY: status={'FAIL' if ERRS else 'PASS'} | ok={OK} warnings={WARNS} errors={ERRS}")
    return 1 if ERRS else 0

if __name__ == "__main__":
    sys.exit(main())
