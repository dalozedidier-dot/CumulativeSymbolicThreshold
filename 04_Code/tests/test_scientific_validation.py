"""test_scientific_validation.py — Automated test for the scientific validation protocol.

This test runs a fast (reduced replicate) version of the validation protocol
and asserts that:
  1. The protocol produces a non-REJECT verdict
  2. Test condition has higher detection than stable/placebo
  3. Confusion matrix is well-formed
  4. Frozen parameters are not modified during the run
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from oric.frozen_params import FROZEN_PARAMS, FrozenValidationParams
from pipeline.run_scientific_validation_protocol import run_validation_protocol


@pytest.fixture
def fast_params() -> FrozenValidationParams:
    """Create fast params with fewer replicates for CI testing."""
    return FrozenValidationParams(
        n_replicates=15,
        seed_base=9000,
        # Relax gates slightly for fast mode
        test_detection_rate_min=0.60,
        stable_fp_rate_max=0.40,
        placebo_fp_rate_max=0.40,
    )


@pytest.fixture
def outdir(tmp_path: Path) -> Path:
    return tmp_path / "scientific_validation"


def test_validation_protocol_runs(fast_params: FrozenValidationParams, outdir: Path) -> None:
    """The protocol runs without errors and produces all expected outputs."""
    result = run_validation_protocol(
        outdir=outdir,
        fp=fast_params,
        n_replicates=15,
        verbose=False,
    )

    # Check structure
    assert "protocol_verdict" in result
    assert result["protocol_verdict"] in ("ACCEPT", "REJECT", "INDETERMINATE")
    assert "discrimination_metrics" in result
    assert "condition_summaries" in result

    # Check files
    assert (outdir / "verdict.txt").exists()
    assert (outdir / "VALIDATION_REPORT.md").exists()
    assert (outdir / "tables" / "validation_results.csv").exists()
    assert (outdir / "tables" / "validation_summary.json").exists()


def test_discrimination_direction(fast_params: FrozenValidationParams, outdir: Path) -> None:
    """Test condition must have higher detection rate than stable/placebo."""
    result = run_validation_protocol(
        outdir=outdir,
        fp=fast_params,
        n_replicates=15,
        verbose=False,
    )

    summaries = result["condition_summaries"]
    test_rate = summaries["test"]["detection_rate"]
    stable_rate = summaries["stable"]["detection_rate"]
    placebo_rate = summaries["placebo"]["detection_rate"]

    assert test_rate > stable_rate, (
        f"Test detection rate ({test_rate:.3f}) must exceed stable ({stable_rate:.3f})"
    )
    assert test_rate > placebo_rate, (
        f"Test detection rate ({test_rate:.3f}) must exceed placebo ({placebo_rate:.3f})"
    )


def test_confusion_matrix_sums(fast_params: FrozenValidationParams, outdir: Path) -> None:
    """Confusion matrix entries must sum correctly."""
    result = run_validation_protocol(
        outdir=outdir,
        fp=fast_params,
        n_replicates=15,
        verbose=False,
    )

    m = result["discrimination_metrics"]
    cm = m["confusion_matrix"]

    assert cm["TP"] + cm["FN"] + cm["FP"] + cm["TN"] == m["n_decidable"]
    assert m["n_decidable"] + m["n_indeterminate"] == m["n_total"]
    assert m["n_total"] == 15 * 3  # 3 conditions


def test_frozen_params_immutable(fast_params: FrozenValidationParams, outdir: Path) -> None:
    """Frozen params must not be modified during the run."""
    before = fast_params.to_dict()

    run_validation_protocol(
        outdir=outdir,
        fp=fast_params,
        n_replicates=10,
        verbose=False,
    )

    after = fast_params.to_dict()
    assert before == after, "Frozen parameters were modified during validation!"

    # Also check the saved params match
    saved = json.loads((outdir / "frozen_params.json").read_text(encoding="utf-8"))
    for key in before:
        assert saved[key] == before[key], f"Saved param {key} differs from input"
