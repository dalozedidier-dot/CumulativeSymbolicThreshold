#!/usr/bin/env python3
"""audit_artifact_consistency.py — Nightly artifact consistency checker.

Detects contradictions between pipeline artefacts before publication or
archiving.  Designed to run as a CI job or standalone script.

Checks performed:
  1. dual_proof_manifest.json vs final_status.json
  2. summary.json vs verdict.json (per run directory)
  3. synthetic consistency with dual proof
  4. FRED consistency with dual proof
  5. No forbidden empty fields in final manifests

Usage:
  python tools/audit_artifact_consistency.py --bundle-dir <path> [--output <path>]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ── Data structures ───────────────────────────────────────────────────────

@dataclass
class AuditFinding:
    check: str
    severity: str  # "error" or "warning"
    message: str
    path: str = ""

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
        }


@dataclass
class AuditReport:
    status: str = "PASS"
    n_errors: int = 0
    n_warnings: int = 0
    findings: list[AuditFinding] = field(default_factory=list)

    def add(self, finding: AuditFinding) -> None:
        self.findings.append(finding)
        if finding.severity == "error":
            self.n_errors += 1
            self.status = "FAIL"
        else:
            self.n_warnings += 1

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "n_errors": self.n_errors,
            "n_warnings": self.n_warnings,
            "findings": [f.to_dict() for f in self.findings],
        }


# ── Helpers ───────────────────────────────────────────────────────────────

def _read_json(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


# ── Checks ────────────────────────────────────────────────────────────────

def check_manifest_vs_final_status(
    bundle_dir: Path, report: AuditReport
) -> None:
    """Check 1: dual_proof_manifest.json ↔ final_status.json."""
    manifest_path = bundle_dir / "dual_proof_manifest.json"
    final_path = bundle_dir / "final_status.json"

    manifest = _read_json(manifest_path)
    final = _read_json(final_path)

    if manifest is None:
        report.add(AuditFinding(
            "manifest_exists", "error",
            "dual_proof_manifest.json missing or unreadable",
            str(manifest_path),
        ))
        return

    if final is None:
        report.add(AuditFinding(
            "final_status_exists", "error",
            "final_status.json missing or unreadable",
            str(final_path),
        ))
        return

    # Status consistency
    m_status = manifest.get("dual_proof_status")
    f_status = final.get("framework_status")

    if f_status == "COMPLETE" and m_status != "DUAL_PROOF_COMPLETE":
        report.add(AuditFinding(
            "manifest_final_status_alignment", "error",
            f"final_status=COMPLETE but manifest={m_status}",
            str(bundle_dir),
        ))

    if f_status == "COMPLETE" and final.get("n_empty", 0) > 0:
        report.add(AuditFinding(
            "complete_but_empty", "error",
            f"final_status=COMPLETE but n_empty={final['n_empty']}",
            str(bundle_dir),
        ))

    # Verdict alignment
    dim_pairs = [
        ("synthetic_verdict", "synthetic_global_verdict"),
        ("real_data_verdict", "fred_global_verdict"),
        ("validation_verdict", "validation_verdict"),
    ]
    for f_key, m_key in dim_pairs:
        f_val = final.get(f_key)
        m_val = manifest.get(m_key)
        if f_val is not None and m_val is not None and f_val != m_val:
            report.add(AuditFinding(
                "verdict_alignment", "error",
                f"final_status.{f_key}={f_val!r} != manifest.{m_key}={m_val!r}",
                str(bundle_dir),
            ))


def check_summary_vs_verdict(run_dir: Path, report: AuditReport) -> None:
    """Check 2: summary.json vs verdict.json per run directory."""
    tables = run_dir / "tables"
    s_path = tables / "summary.json"
    v_path = tables / "verdict.json"
    v_txt = run_dir / "verdict.txt"

    summary = _read_json(s_path)
    verdict_j = _read_json(v_path)

    if summary is None:
        return  # Not all dirs have summary

    s_verdict = summary.get("protocol_verdict") or summary.get("verdict")

    # Check vs verdict.json
    if verdict_j is not None:
        v_verdict = verdict_j.get("verdict")
        if s_verdict is not None and v_verdict is not None and s_verdict != v_verdict:
            report.add(AuditFinding(
                "summary_vs_verdict_json", "error",
                f"summary.verdict={s_verdict!r} != verdict.json.verdict={v_verdict!r}",
                str(run_dir),
            ))

        # Precheck check
        if verdict_j.get("precheck_passed") is False and s_verdict == "ACCEPT":
            report.add(AuditFinding(
                "precheck_accept_conflict", "error",
                "summary shows ACCEPT but precheck_passed=false in verdict.json",
                str(run_dir),
            ))

    # Check vs verdict.txt
    if v_txt.exists():
        try:
            txt_val = v_txt.read_text(encoding="utf-8").strip()
        except OSError:
            txt_val = ""
        if s_verdict is not None and txt_val and s_verdict != txt_val:
            report.add(AuditFinding(
                "summary_vs_verdict_txt", "warning",
                f"summary.verdict={s_verdict!r} != verdict.txt={txt_val!r}",
                str(run_dir),
            ))


def check_synthetic_consistency(
    bundle_dir: Path, report: AuditReport
) -> None:
    """Check 3: synthetic dimension consistency with dual proof."""
    manifest = _read_json(bundle_dir / "dual_proof_manifest.json")
    if manifest is None:
        return

    gate = manifest.get("synthetic_gate_passed")
    verdict = manifest.get("synthetic_global_verdict")
    support = manifest.get("synthetic_support_level")

    if gate is True and _is_empty(verdict):
        report.add(AuditFinding(
            "synthetic_gate_verdict", "error",
            "synthetic.gate_passed=true but global_verdict is empty",
            str(bundle_dir),
        ))

    if gate is True and _is_empty(support):
        report.add(AuditFinding(
            "synthetic_gate_support", "error",
            "synthetic.gate_passed=true but support_level is empty",
            str(bundle_dir),
        ))

    if verdict == "ACCEPT" and gate is not True:
        report.add(AuditFinding(
            "synthetic_accept_gate", "error",
            "synthetic.global_verdict=ACCEPT but gate_passed is not true",
            str(bundle_dir),
        ))


def check_fred_consistency(bundle_dir: Path, report: AuditReport) -> None:
    """Check 4: FRED dimension consistency."""
    manifest = _read_json(bundle_dir / "dual_proof_manifest.json")
    if manifest is None:
        return

    verdict = manifest.get("fred_global_verdict")
    support = manifest.get("fred_support_level")

    if verdict == "ACCEPT" and _is_empty(support):
        report.add(AuditFinding(
            "fred_accept_support", "error",
            "fred.global_verdict=ACCEPT but support_level is empty",
            str(bundle_dir),
        ))


def check_forbidden_empty_fields(
    bundle_dir: Path, report: AuditReport
) -> None:
    """Check 5: No forbidden empty fields in final manifests."""
    manifest = _read_json(bundle_dir / "dual_proof_manifest.json")
    if manifest is None:
        return

    # If status is COMPLETE, no field should be empty
    if manifest.get("dual_proof_status") == "DUAL_PROOF_COMPLETE":
        empty_list = manifest.get("empty_fields", [])
        if empty_list:
            report.add(AuditFinding(
                "complete_empty_fields", "error",
                f"DUAL_PROOF_COMPLETE but empty_fields={empty_list}",
                str(bundle_dir),
            ))

        incon = manifest.get("inconsistencies", [])
        if incon:
            report.add(AuditFinding(
                "complete_inconsistencies", "error",
                f"DUAL_PROOF_COMPLETE but inconsistencies={incon}",
                str(bundle_dir),
            ))


# ── Main audit runner ─────────────────────────────────────────────────────

def run_audit(
    bundle_dir: Path,
    run_dirs: list[Path] | None = None,
) -> AuditReport:
    """Run all consistency checks on a bundle directory.

    Args:
        bundle_dir: Root directory containing dual_proof_manifest.json
                    and final_status.json
        run_dirs:   Optional list of individual run directories to check
                    for summary/verdict alignment.  If None, auto-discovers
                    directories containing verdict.txt.
    """
    report = AuditReport()

    check_manifest_vs_final_status(bundle_dir, report)
    check_synthetic_consistency(bundle_dir, report)
    check_fred_consistency(bundle_dir, report)
    check_forbidden_empty_fields(bundle_dir, report)

    # Auto-discover run directories if not provided
    if run_dirs is None:
        run_dirs = []
        for vt in bundle_dir.rglob("verdict.txt"):
            run_dirs.append(vt.parent)

    for rd in run_dirs:
        check_summary_vs_verdict(rd, report)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit artifact consistency across pipeline outputs"
    )
    parser.add_argument("--bundle-dir", required=True,
                        help="Root directory containing manifests and run outputs")
    parser.add_argument("--output", default=None,
                        help="Path for artifact_consistency_report.json (default: <bundle>/artifact_consistency_report.json)")
    args = parser.parse_args()

    bundle = Path(args.bundle_dir)
    if not bundle.exists():
        print(f"ERROR: bundle directory does not exist: {bundle}")
        return 1

    report = run_audit(bundle)

    out_path = Path(args.output) if args.output else bundle / "artifact_consistency_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8"
    )

    print(f"Audit result: {report.status}")
    print(f"  Errors:   {report.n_errors}")
    print(f"  Warnings: {report.n_warnings}")
    if report.findings:
        for f in report.findings:
            print(f"  [{f.severity}] {f.check}: {f.message}")
    print(f"  Report: {out_path}")

    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
