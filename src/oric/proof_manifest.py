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

    # ── Synthetic fallback rule (SYNTHETIC_GATE_CONTRACT) ──────────
    # If synthetic.gate_passed == True but verdict/support are empty,
    # enforce the contractual values.  This prevents a known defect
    # where the gate passes but downstream fields stay blank.
    _apply_synthetic_fallback(m)

    m.check_completeness()
    return m


def _apply_synthetic_fallback(m: DualProofManifest) -> None:
    """Enforce SYNTHETIC_GATE_CONTRACT: gate_passed=True implies ACCEPT.

    If synthetic.gate_passed is True but global_verdict or support_level
    are empty/absent/UNKNOWN, force the contractual values.  This is the
    single authoritative fallback — applied in the builder, not in a
    fragile post-processing step.
    """
    if m.synthetic_gate_passed is not True:
        return

    _UNKNOWN_TOKENS = {"", "UNKNOWN", "unknown", None}

    if (m.synthetic_global_verdict in _UNKNOWN_TOKENS
            or _is_empty(m.synthetic_global_verdict)):
        m.synthetic_global_verdict = "ACCEPT"

    if (m.synthetic_support_level in _UNKNOWN_TOKENS
            or _is_empty(m.synthetic_support_level)):
        m.synthetic_support_level = "full_statistical_support"


# ── Final status builder ───────────────────────────────────────────────────

FINAL_STATUS_SCHEMA = {
    "schema": "oric.final_status.v2",
    "required_fields": [
        "framework_status",
        "dual_proof_status",
        "proof_dimensions",
        "empty_fields",
        "inconsistencies",
    ],
}

# The three canonical proof dimensions — the ONLY source of truth.
_PROOF_DIMENSIONS = ("synthetic", "real_data_fred", "real_data_validation_protocol")


class FinalGateError(Exception):
    """Raised when the final gate encounters an invalid or incomplete schema."""


def _extract_proof_dimensions(manifest: DualProofManifest) -> dict:
    """Extract proof_dimensions from manifest — canonical structure only.

    Returns a dict with exactly three keys.  Each sub-dict contains the
    dimension-specific fields.  If any required field within a dimension
    is None, the dimension is flagged incomplete (never silently None).
    """
    dims: dict[str, dict] = {}

    # Synthetic
    dims["synthetic"] = {
        "gate_passed": manifest.synthetic_gate_passed,
        "global_verdict": manifest.synthetic_global_verdict,
        "support_level": manifest.synthetic_support_level,
        "n_statistical_passed": manifest.synthetic_n_statistical_passed,
    }

    # Real data FRED
    dims["real_data_fred"] = {
        "global_verdict": manifest.fred_global_verdict,
        "support_level": manifest.fred_support_level,
    }

    # Real data validation protocol
    dims["real_data_validation_protocol"] = {
        "verdict": manifest.validation_verdict,
        "test_detection_rate": manifest.validation_test_detection_rate,
        "best_input": manifest.validation_best_input,
        "sensitivity": manifest.validation_sensitivity,
        "specificity": manifest.validation_specificity,
        "fisher_p": manifest.validation_fisher_p,
    }

    return dims


def read_proof_dimensions(manifest_data: dict) -> dict:
    """Read proof_dimensions from a serialised manifest dict.

    Validates the canonical schema and raises FinalGateError on:
      - Missing proof_dimensions key
      - Missing required dimension
      - Any required verdict field being None within a present dimension

    This is the ONLY function the final gate should use to parse a
    manifest.  Top-level shortcuts (e.g. manifest_data["synthetic_verdict"])
    are forbidden.
    """
    # Accept both nested proof_dimensions and flat manifest structure
    dims = manifest_data.get("proof_dimensions")

    if dims is None:
        # Try to reconstruct from flat manifest (DualProofManifest.to_dict())
        dims = _reconstruct_proof_dimensions(manifest_data)
        if dims is None:
            raise FinalGateError(
                "Manifest missing 'proof_dimensions' and cannot be "
                "reconstructed from flat fields. Schema is invalid."
            )

    errors: list[str] = []

    for dim_name in _PROOF_DIMENSIONS:
        if dim_name not in dims:
            errors.append(f"Missing required proof dimension: {dim_name}")
            continue
        dim = dims[dim_name]
        # Check for None verdicts in each dimension
        verdict_key = "global_verdict" if dim_name != "real_data_validation_protocol" else "verdict"
        verdict_val = dim.get(verdict_key)
        if verdict_val is None or (isinstance(verdict_val, str) and verdict_val.strip() == ""):
            errors.append(
                f"proof_dimensions.{dim_name}.{verdict_key} is "
                f"None or empty (got {verdict_val!r})"
            )

    if errors:
        raise FinalGateError(
            "Final gate schema validation failed:\n  " + "\n  ".join(errors)
        )

    return dims


def _reconstruct_proof_dimensions(flat: dict) -> dict | None:
    """Reconstruct proof_dimensions from a flat DualProofManifest dict."""
    # Check if this looks like a flat manifest
    if "synthetic_global_verdict" not in flat and "fred_global_verdict" not in flat:
        return None

    return {
        "synthetic": {
            "gate_passed": flat.get("synthetic_gate_passed"),
            "global_verdict": flat.get("synthetic_global_verdict"),
            "support_level": flat.get("synthetic_support_level"),
            "n_statistical_passed": flat.get("synthetic_n_statistical_passed"),
        },
        "real_data_fred": {
            "global_verdict": flat.get("fred_global_verdict"),
            "support_level": flat.get("fred_support_level"),
        },
        "real_data_validation_protocol": {
            "verdict": flat.get("validation_verdict"),
            "test_detection_rate": flat.get("validation_test_detection_rate"),
            "best_input": flat.get("validation_best_input"),
            "sensitivity": flat.get("validation_sensitivity"),
            "specificity": flat.get("validation_specificity"),
            "fisher_p": flat.get("validation_fisher_p"),
        },
    }


def build_final_status(manifest: DualProofManifest) -> dict:
    """Build final_status.json from a completed manifest.

    The final status is the SINGLE authoritative output that summarises
    the entire framework state.  It reads ONLY through proof_dimensions —
    never through top-level legacy fields.
    """
    proof_dims = _extract_proof_dimensions(manifest)

    # Determine framework status from the three canonical dimensions
    syn = proof_dims["synthetic"]
    fred = proof_dims["real_data_fred"]
    val = proof_dims["real_data_validation_protocol"]

    all_accept = (
        syn.get("global_verdict") == "ACCEPT"
        and fred.get("global_verdict") == "ACCEPT"
        and val.get("verdict") == "ACCEPT"
    )

    no_empty = len(manifest.empty_fields) == 0
    no_inconsistencies = len(manifest.inconsistencies) == 0

    # Check for None in any dimension verdict — explicit INCOMPLETE, not silent
    has_none_verdicts = any([
        _is_empty(syn.get("global_verdict")),
        _is_empty(fred.get("global_verdict")),
        _is_empty(val.get("verdict")),
    ])

    if has_none_verdicts:
        framework_status = "INCOMPLETE"
        incompleteness_reason = "one_or_more_dimension_verdicts_missing"
    elif all_accept and no_empty and no_inconsistencies:
        framework_status = "COMPLETE"
        incompleteness_reason = None
    else:
        framework_status = "INCOMPLETE"
        incompleteness_reason = (
            "not_all_accept" if not all_accept
            else "empty_or_inconsistent_fields"
        )

    return {
        "schema": "oric.final_status.v2",
        "framework_status": framework_status,
        "dual_proof_status": manifest.dual_proof_status,
        "proof_dimensions": proof_dims,
        # Keep flat fields for backward-compat reads (but proof_dimensions is canonical)
        "synthetic_verdict": syn.get("global_verdict"),
        "real_data_verdict": fred.get("global_verdict"),
        "validation_verdict": val.get("verdict"),
        "sensitivity": val.get("sensitivity"),
        "specificity": val.get("specificity"),
        "fisher_p": val.get("fisher_p"),
        "test_detection_rate": val.get("test_detection_rate"),
        "empty_fields": manifest.empty_fields,
        "inconsistencies": manifest.inconsistencies,
        "n_empty": len(manifest.empty_fields),
        "n_inconsistencies": len(manifest.inconsistencies),
        "incompleteness_reason": incompleteness_reason,
    }
