"""proof_manifest.py — Dual proof manifest builder and validator.

Builds dual_proof_manifest.json from real pipeline artefacts (never from
in-memory state).  The manifest is the single source of truth for the
"proof status" of the framework.

Contract (from contracts/DUAL_PROOF_CONTRACT.json):
  synthetic:
    - gate_passed, global_verdict, support_level, n_statistical_passed
  real_data_fred:
    - global_verdict, support_level
  real_data_validation_protocol:
    - verdict, test_detection_rate, best_input

A field is EMPTY if it is None, "", or missing.  If any required field is
empty while the corresponding source artefact exists, the manifest is
INCONSISTENT, and dual_proof_status = "DUAL_PROOF_INCOMPLETE".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[2]


# ── Schema ──────────────────────────────────────────────────────────────────

MANIFEST_SCHEMA_VERSION = 1

_REQUIRED_SYNTHETIC = ("gate_passed", "global_verdict", "support_level",
                       "n_statistical_passed")
_REQUIRED_FRED = ("global_verdict", "support_level")
_REQUIRED_VALIDATION = ("verdict", "test_detection_rate", "best_input")


def _is_empty(v: Any) -> bool:
    """A value is empty if None, empty string, or NaN float."""
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    if isinstance(v, float) and v != v:
        return True
    return False


@dataclass
class DualProofManifest:
    """Canonical dual proof manifest."""
    schema_version: int = MANIFEST_SCHEMA_VERSION
    dual_proof_status: str = "DUAL_PROOF_INCOMPLETE"

    # Synthetic block
    synthetic_gate_passed: bool | None = None
    synthetic_global_verdict: str | None = None
    synthetic_support_level: str | None = None
    synthetic_n_statistical_passed: int | None = None
    synthetic_source_path: str | None = None

    # Real data (FRED canonical)
    fred_global_verdict: str | None = None
    fred_support_level: str | None = None
    fred_source_path: str | None = None

    # Validation protocol
    validation_verdict: str | None = None
    validation_test_detection_rate: float | None = None
    validation_best_input: str | None = None
    validation_source_path: str | None = None

    # Discrimination metrics
    validation_sensitivity: float | None = None
    validation_specificity: float | None = None
    validation_fisher_p: float | None = None

    # Integrity
    empty_fields: list[str] = field(default_factory=list)
    inconsistencies: list[str] = field(default_factory=list)

    def check_completeness(self) -> None:
        """Re-evaluate dual_proof_status based on field completeness."""
        self.empty_fields = []
        self.inconsistencies = []

        # Check synthetic fields
        syn_vals = {
            "synthetic.gate_passed": self.synthetic_gate_passed,
            "synthetic.global_verdict": self.synthetic_global_verdict,
            "synthetic.support_level": self.synthetic_support_level,
            "synthetic.n_statistical_passed": self.synthetic_n_statistical_passed,
        }
        for k, v in syn_vals.items():
            if _is_empty(v):
                self.empty_fields.append(k)

        # Check FRED fields
        fred_vals = {
            "real_data_fred.global_verdict": self.fred_global_verdict,
            "real_data_fred.support_level": self.fred_support_level,
        }
        for k, v in fred_vals.items():
            if _is_empty(v):
                self.empty_fields.append(k)

        # Check validation fields
        val_vals = {
            "validation.verdict": self.validation_verdict,
            "validation.test_detection_rate": self.validation_test_detection_rate,
            "validation.best_input": self.validation_best_input,
        }
        for k, v in val_vals.items():
            if _is_empty(v):
                self.empty_fields.append(k)

        # Cross-checks
        if (self.synthetic_global_verdict == "ACCEPT"
                and self.synthetic_gate_passed is not True):
            self.inconsistencies.append(
                "synthetic ACCEPT but gate_passed is not True"
            )

        if (self.validation_verdict == "ACCEPT"
                and self.validation_sensitivity is not None
                and self.validation_sensitivity < 0.80):
            self.inconsistencies.append(
                f"validation ACCEPT but sensitivity={self.validation_sensitivity:.3f} < 0.80"
            )

        if (self.validation_verdict == "ACCEPT"
                and self.validation_specificity is not None
                and self.validation_specificity < 0.80):
            self.inconsistencies.append(
                f"validation ACCEPT but specificity={self.validation_specificity:.3f} < 0.80"
            )

        # Status
        if not self.empty_fields and not self.inconsistencies:
            all_accept = (
                self.synthetic_global_verdict == "ACCEPT"
                and self.fred_global_verdict == "ACCEPT"
                and self.validation_verdict == "ACCEPT"
            )
            self.dual_proof_status = (
                "DUAL_PROOF_COMPLETE" if all_accept
                else "DUAL_PROOF_INCOMPLETE"
            )
        else:
            self.dual_proof_status = "DUAL_PROOF_INCOMPLETE"

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, default=str) + "\n",
            encoding="utf-8",
        )


# ── Builder: reads from disk artefacts ─────────────────────────────────────

def _read_json(p: Path) -> dict | None:
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def build_dual_proof_manifest(
    synthetic_dir: Path | None = None,
    fred_dir: Path | None = None,
    validation_dir: Path | None = None,
) -> DualProofManifest:
    """Build a DualProofManifest by reading pipeline output artefacts.

    Each directory is optional.  If provided, the builder reads the
    canonical JSON files and extracts the required fields.  Empty or
    missing fields are flagged.
    """
    m = DualProofManifest()

    # ── Synthetic ────────────────────────────────────────────────────
    if synthetic_dir is not None:
        m.synthetic_source_path = str(synthetic_dir)
        summary = _read_json(synthetic_dir / "tables" / "validation_summary.json")
        if summary is not None:
            m.synthetic_gate_passed = summary.get("gate_passed")
            m.synthetic_global_verdict = summary.get("protocol_verdict") or summary.get("global_verdict")
            m.synthetic_support_level = summary.get("support_level")
            m.synthetic_n_statistical_passed = summary.get("n_statistical_passed")

            # Try from verdict_details
            vd = summary.get("verdict_details", {})
            if m.synthetic_global_verdict is None:
                m.synthetic_global_verdict = vd.get("protocol_verdict")
            if m.synthetic_gate_passed is None:
                sens = vd.get("sensitivity")
                spec = vd.get("specificity")
                if sens is not None and spec is not None:
                    m.synthetic_gate_passed = (
                        sens >= 0.80 and spec >= 0.80
                    )
            if m.synthetic_support_level is None:
                if m.synthetic_global_verdict == "ACCEPT":
                    m.synthetic_support_level = "full_statistical_support"
                elif m.synthetic_global_verdict == "REJECT":
                    m.synthetic_support_level = "rejected"
                else:
                    m.synthetic_support_level = "indeterminate"
            if m.synthetic_n_statistical_passed is None:
                dm = summary.get("discrimination_metrics", {})
                cm = dm.get("confusion_matrix", {})
                tp = cm.get("TP")
                tn = cm.get("TN")
                if tp is not None and tn is not None:
                    m.synthetic_n_statistical_passed = tp + tn

    # ── FRED real data ──────────────────────────────────────────────
    if fred_dir is not None:
        m.fred_source_path = str(fred_dir)
        summary = _read_json(fred_dir / "tables" / "validation_summary.json")
        verdict_txt = fred_dir / "verdict.txt"
        if summary is not None:
            m.fred_global_verdict = summary.get("protocol_verdict")
            m.fred_support_level = summary.get("support_level")
            if m.fred_support_level is None:
                if m.fred_global_verdict == "ACCEPT":
                    m.fred_support_level = "full_statistical_support"
                elif m.fred_global_verdict == "REJECT":
                    m.fred_support_level = "rejected"
                else:
                    m.fred_support_level = "indeterminate"
        elif verdict_txt.exists():
            v = verdict_txt.read_text(encoding="utf-8").strip()
            m.fred_global_verdict = v

    # ── Validation protocol ─────────────────────────────────────────
    if validation_dir is not None:
        m.validation_source_path = str(validation_dir)
        summary = _read_json(validation_dir / "tables" / "validation_summary.json")
        if summary is not None:
            m.validation_verdict = summary.get("protocol_verdict")
            m.validation_best_input = summary.get("best_input") or summary.get("best_stem")

            # Test detection rate
            tm = summary.get("test_metrics") or {}
            m.validation_test_detection_rate = _safe_float(
                summary.get("test_det_rate") or tm.get("detection_rate")
            )

            # Discrimination metrics
            dm = summary.get("discrimination_metrics") or summary.get("verdict_details") or {}
            m.validation_sensitivity = _safe_float(dm.get("sensitivity"))
            m.validation_specificity = _safe_float(dm.get("specificity"))
            m.validation_fisher_p = _safe_float(dm.get("fisher_p_value") or dm.get("fisher_p"))

    m.check_completeness()
    return m


# ── Final status builder ───────────────────────────────────────────────────

FINAL_STATUS_SCHEMA = {
    "schema": "oric.final_status.v1",
    "required_fields": [
        "framework_status",
        "dual_proof_status",
        "synthetic_verdict",
        "real_data_verdict",
        "validation_verdict",
        "sensitivity",
        "specificity",
        "empty_fields",
        "inconsistencies",
    ],
}


def build_final_status(manifest: DualProofManifest) -> dict:
    """Build final_status.json from a completed manifest.

    The final status is the SINGLE authoritative output that summarises
    the entire framework state.  It is derived mechanically from the
    manifest — never from in-memory pipeline state.
    """
    all_accept = (
        manifest.synthetic_global_verdict == "ACCEPT"
        and manifest.fred_global_verdict == "ACCEPT"
        and manifest.validation_verdict == "ACCEPT"
    )
    no_empty = len(manifest.empty_fields) == 0
    no_inconsistencies = len(manifest.inconsistencies) == 0

    if all_accept and no_empty and no_inconsistencies:
        framework_status = "COMPLETE"
    elif manifest.dual_proof_status == "DUAL_PROOF_INCOMPLETE":
        framework_status = "INCOMPLETE"
    else:
        framework_status = "INCOMPLETE"

    return {
        "schema": "oric.final_status.v1",
        "framework_status": framework_status,
        "dual_proof_status": manifest.dual_proof_status,
        "synthetic_verdict": manifest.synthetic_global_verdict,
        "real_data_verdict": manifest.fred_global_verdict,
        "validation_verdict": manifest.validation_verdict,
        "sensitivity": manifest.validation_sensitivity,
        "specificity": manifest.validation_specificity,
        "fisher_p": manifest.validation_fisher_p,
        "test_detection_rate": manifest.validation_test_detection_rate,
        "empty_fields": manifest.empty_fields,
        "inconsistencies": manifest.inconsistencies,
        "n_empty": len(manifest.empty_fields),
        "n_inconsistencies": len(manifest.inconsistencies),
    }
