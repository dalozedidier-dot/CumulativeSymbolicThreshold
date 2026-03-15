"""integrity.py — Verdict alignment and integrity checking.

Ensures that summary.json, verdict.json, verdict.txt, and related artefacts
are mutually consistent.  Any desynchronisation is a framework defect.

Rules:
  1. summary.json["verdict"] must agree with verdict.txt
  2. If precheck_passed = false, summary cannot show ACCEPT
  3. verdict.json["verdict"] must match summary.json["protocol_verdict"]
  4. Detection rates in summary must be consistent with condition verdicts
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IntegrityCheck:
    """Result of an integrity check on a run directory."""
    path: str = ""
    passed: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.passed = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "passed": self.passed,
            "n_errors": len(self.errors),
            "n_warnings": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _read_json_safe(p: Path) -> dict | None:
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_text_safe(p: Path) -> str | None:
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def check_run_integrity(run_dir: Path) -> IntegrityCheck:
    """Check integrity of a single run directory.

    Expected structure:
      run_dir/
        verdict.txt
        tables/
          validation_summary.json   (or summary.json)
          verdict.json              (optional)
    """
    result = IntegrityCheck(path=str(run_dir))

    if not run_dir.exists():
        result.fail(f"Directory does not exist: {run_dir}")
        return result

    # Read artefacts
    verdict_txt = _read_text_safe(run_dir / "verdict.txt")
    tables_dir = run_dir / "tables"

    summary_json = (
        _read_json_safe(tables_dir / "validation_summary.json")
        or _read_json_safe(tables_dir / "summary.json")
    )
    verdict_json = _read_json_safe(tables_dir / "verdict.json")

    # Rule 0: verdict.txt must exist
    if verdict_txt is None:
        result.fail("verdict.txt missing")
    else:
        if verdict_txt not in ("ACCEPT", "REJECT", "INDETERMINATE"):
            result.fail(f"verdict.txt has invalid token: {verdict_txt!r}")

    # Rule 1: summary.json verdict must match verdict.txt
    if summary_json is not None and verdict_txt is not None:
        summary_verdict = (
            summary_json.get("protocol_verdict")
            or summary_json.get("verdict")
        )
        if summary_verdict is not None and summary_verdict != verdict_txt:
            result.fail(
                f"summary.json verdict={summary_verdict!r} != "
                f"verdict.txt={verdict_txt!r}"
            )

    # Rule 2: precheck_passed=false → cannot be ACCEPT
    if summary_json is not None:
        precheck = summary_json.get("precheck_passed")
        sv = summary_json.get("protocol_verdict") or summary_json.get("verdict")
        if precheck is False and sv == "ACCEPT":
            result.fail("summary shows ACCEPT but precheck_passed=false")

    # Rule 3: verdict.json must match
    if verdict_json is not None and verdict_txt is not None:
        vj_verdict = verdict_json.get("verdict")
        if vj_verdict is not None and vj_verdict != verdict_txt:
            result.fail(
                f"verdict.json verdict={vj_verdict!r} != "
                f"verdict.txt={verdict_txt!r}"
            )

    # Rule 4: detection rates consistency
    if summary_json is not None:
        datasets = summary_json.get("datasets", {})
        pv = summary_json.get("protocol_verdict")
        if pv == "ACCEPT":
            test_m = (datasets.get("test") or {}).get("metrics") or {}
            stable_m = (datasets.get("stable") or {}).get("metrics") or {}
            placebo_m = (datasets.get("placebo") or {}).get("metrics") or {}

            test_dr = test_m.get("detection_rate")
            stable_dr = stable_m.get("detection_rate")
            placebo_dr = placebo_m.get("detection_rate")

            # Test must be high, stable/placebo must be low
            if test_dr is not None and isinstance(test_dr, (int, float)):
                if test_dr < 0.50:
                    result.fail(
                        f"ACCEPT but test detection_rate={test_dr:.3f} < 0.50"
                    )
            if stable_dr is not None and isinstance(stable_dr, (int, float)):
                if stable_dr > 0.50:
                    result.fail(
                        f"ACCEPT but stable detection_rate={stable_dr:.3f} > 0.50"
                    )
            if placebo_dr is not None and isinstance(placebo_dr, (int, float)):
                if placebo_dr > 0.50:
                    result.fail(
                        f"ACCEPT but placebo detection_rate={placebo_dr:.3f} > 0.50"
                    )

    return result


def check_dual_proof_integrity(
    manifest_path: Path,
    final_status_path: Path | None = None,
) -> IntegrityCheck:
    """Check integrity between dual_proof_manifest.json and final_status.json.

    Rule: if final_status says COMPLETE but manifest has empty fields → error.
    """
    result = IntegrityCheck(path=str(manifest_path.parent))

    manifest = _read_json_safe(manifest_path)
    if manifest is None:
        result.fail(f"dual_proof_manifest.json missing or unreadable: {manifest_path}")
        return result

    # Check required fields not empty
    empty = manifest.get("empty_fields", [])
    status = manifest.get("dual_proof_status", "")
    if status == "DUAL_PROOF_COMPLETE" and empty:
        result.fail(
            f"dual_proof_status=COMPLETE but empty_fields={empty}"
        )

    # Check consistency with final_status
    if final_status_path is not None:
        fs = _read_json_safe(final_status_path)
        if fs is not None:
            fs_status = fs.get("framework_status")
            if fs_status == "COMPLETE" and status != "DUAL_PROOF_COMPLETE":
                result.fail(
                    f"final_status says COMPLETE but manifest says {status}"
                )
            if fs_status == "COMPLETE" and fs.get("n_empty", 0) > 0:
                result.fail(
                    f"final_status COMPLETE but n_empty={fs['n_empty']}"
                )

            # Verdict alignment
            for key_pair in [
                ("synthetic_verdict", "synthetic_global_verdict"),
                ("real_data_verdict", "fred_global_verdict"),
                ("validation_verdict", "validation_verdict"),
            ]:
                fs_val = fs.get(key_pair[0])
                m_val = manifest.get(key_pair[1])
                if fs_val is not None and m_val is not None and fs_val != m_val:
                    result.fail(
                        f"final_status.{key_pair[0]}={fs_val!r} != "
                        f"manifest.{key_pair[1]}={m_val!r}"
                    )

    return result


def check_all_integrity(
    run_dirs: list[Path],
    manifest_path: Path | None = None,
    final_status_path: Path | None = None,
) -> list[IntegrityCheck]:
    """Run all integrity checks. Returns a list of IntegrityCheck results."""
    results = []

    for d in run_dirs:
        results.append(check_run_integrity(d))

    if manifest_path is not None:
        results.append(
            check_dual_proof_integrity(manifest_path, final_status_path)
        )

    return results


def integrity_gate(checks: list[IntegrityCheck]) -> tuple[bool, list[str]]:
    """Gate function: returns (passed, error_messages).

    Used in CI to fail the build on any integrity violation.
    """
    all_errors = []
    for c in checks:
        for e in c.errors:
            all_errors.append(f"[{c.path}] {e}")
    return len(all_errors) == 0, all_errors
