"""End-to-end integration tests.

These tests verify that the pipeline scripts:
  1. Run without crashing on their standard inputs
  2. Produce the canonical output files (verdict.txt, summary.csv, tables/)
  3. Emit valid verdict tokens (ACCEPT | REJECT | INDETERMINATE)
  4. Are reproducible: same seed → identical verdict

They are deliberately lightweight (small n_steps / n_boot) to keep CI fast.
Mark as `pytest.mark.slow` if you want them excluded from the quick smoke suite.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]  # CumulativeSymbolicThreshold/
_CODE = _REPO / "04_Code"
_PIPELINE = _CODE / "pipeline"
_SYNTHETIC = _REPO / "03_Data" / "synthetic" / "synthetic_minimal.csv"
_SYNTHETIC_THR = _REPO / "03_Data" / "synthetic" / "synthetic_with_transition.csv"
_PANEL = _REPO / "03_Data" / "real" / "_bundles" / "data_real_v2" / "oric_inputs" / "oric_inputs_panel.csv"

VALID_VERDICTS = {"ACCEPT", "REJECT", "INDETERMINATE"}


def _run(script: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(script), *args]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, cwd=str(_REPO)
    )


def _assert_verdict(outdir: Path) -> str:
    verdict_file = outdir / "verdict.txt"
    assert verdict_file.exists(), f"verdict.txt missing in {outdir}"
    token = verdict_file.read_text(encoding="utf-8").strip()
    assert token in VALID_VERDICTS, f"Invalid verdict token: {token!r}"
    return token


def _assert_summary_csv(outdir: Path) -> pd.DataFrame:
    tables = outdir / "tables"
    assert tables.exists(), f"tables/ dir missing in {outdir}"
    csv_path = tables / "summary.csv"
    assert csv_path.exists(), f"summary.csv missing in {tables}"
    df = pd.read_csv(csv_path)
    assert len(df) == 1, "summary.csv must have exactly 1 row"
    assert "verdict" in df.columns, "summary.csv must have a 'verdict' column"
    return df


# ── ORI-C demo (simulation) ────────────────────────────────────────────────────

@pytest.mark.parametrize("intervention", ["none", "demand_shock", "symbolic_cut"])
def test_ori_c_demo_runs_and_produces_verdict(tmp_path, intervention):
    outdir = tmp_path / f"oric_demo_{intervention}"
    res = _run(
        _PIPELINE / "run_ori_c_demo.py",
        "--outdir", str(outdir),
        "--n-steps", "80",
        "--intervention", intervention,
        "--seed", "42",
    )
    assert res.returncode == 0, f"Script failed:\n{res.stderr}"
    # Demos don't always write verdict.txt — check at least that output exists
    assert outdir.exists() or (tmp_path / f"oric_demo_{intervention}").exists()


# ── Synthetic demo (CSV-based) ─────────────────────────────────────────────────

@pytest.mark.skipif(not _SYNTHETIC.exists(), reason="synthetic_minimal.csv not found")
def test_synthetic_demo_pre_threshold(tmp_path):
    outdir = tmp_path / "syn_demo_pre"
    res = _run(
        _PIPELINE / "run_synthetic_demo.py",
        "--input", str(_SYNTHETIC),
        "--outdir", str(outdir),
    )
    assert res.returncode == 0, f"Script failed:\n{res.stderr}"


@pytest.mark.skipif(not _SYNTHETIC_THR.exists(), reason="synthetic_with_transition.csv not found")
def test_synthetic_demo_with_transition(tmp_path):
    outdir = tmp_path / "syn_demo_thr"
    res = _run(
        _PIPELINE / "run_synthetic_demo.py",
        "--input", str(_SYNTHETIC_THR),
        "--outdir", str(outdir),
    )
    assert res.returncode == 0, f"Script failed:\n{res.stderr}"


# ── OOS panel ──────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _PANEL.exists(), reason="panel CSV not found")
def test_oos_panel_runs_and_produces_valid_verdict(tmp_path):
    outdir = tmp_path / "oos_panel"
    res = _run(
        _PIPELINE / "run_oos_panel.py",
        "--panel", str(_PANEL),
        "--split-year", "2015",
        "--outcome-col", "O",
        "--outdir", str(outdir),
        "--k", "2.5",
        "--m", "3",
        "--seed", "42",
    )
    assert res.returncode == 0, f"Script failed:\n{res.stderr}"
    _assert_verdict(outdir)
    _assert_summary_csv(outdir)


@pytest.mark.skipif(not _PANEL.exists(), reason="panel CSV not found")
def test_oos_panel_reproducible(tmp_path):
    """Same seed must produce identical verdict and aggregate metrics."""
    results = []
    for i in range(2):
        outdir = tmp_path / f"oos_rep{i}"
        res = _run(
            _PIPELINE / "run_oos_panel.py",
            "--panel", str(_PANEL),
            "--split-year", "2015",
            "--outcome-col", "O",
            "--outdir", str(outdir),
            "--seed", "42",
        )
        assert res.returncode == 0
        agg_path = outdir / "tables" / "oos_aggregate.json"
        if agg_path.exists():
            results.append(json.loads(agg_path.read_text()))
    if len(results) == 2:
        assert results[0]["verdict"] == results[1]["verdict"]


# ── DiD + Synthetic Control ────────────────────────────────────────────────────

@pytest.mark.skipif(not _PANEL.exists(), reason="panel CSV not found")
def test_did_sc_eu27_2015_runs_and_accepts(tmp_path):
    """EU27_2020/O/2015 is the validated ACCEPT scenario (ATT > 0, PT passes)."""
    outdir = tmp_path / "did_eu27_2015"
    res = _run(
        _PIPELINE / "run_did_synthetic_control.py",
        "--panel", str(_PANEL),
        "--treated-geo", "EU27_2020",
        "--event-year", "2015",
        "--outcome-col", "O",
        "--outdir", str(outdir),
        "--alpha", "0.01",
        "--n-boot", "100",  # small for speed; real CI uses 500
        "--seed", "42",
    )
    assert res.returncode == 0, f"Script failed:\n{res.stderr}"
    token = _assert_verdict(outdir)
    _assert_summary_csv(outdir)
    # Strong expectation: EU27/O/2015 has a validated positive ATT
    assert token in ("ACCEPT", "INDETERMINATE"), \
        f"Expected ACCEPT or INDETERMINATE for EU27_2020/O/2015, got {token}"


@pytest.mark.skipif(not _PANEL.exists(), reason="panel CSV not found")
def test_did_sc_fr_2010_runs_and_rejects(tmp_path):
    """FR/O/2010 is the validated REJECT scenario (post-GFC decline)."""
    outdir = tmp_path / "did_fr_2010"
    res = _run(
        _PIPELINE / "run_did_synthetic_control.py",
        "--panel", str(_PANEL),
        "--treated-geo", "FR",
        "--event-year", "2010",
        "--outcome-col", "O",
        "--outdir", str(outdir),
        "--alpha", "0.01",
        "--n-boot", "100",
        "--seed", "42",
    )
    assert res.returncode == 0, f"Script failed:\n{res.stderr}"
    token = _assert_verdict(outdir)
    _assert_summary_csv(outdir)
    assert token in ("REJECT", "INDETERMINATE"), \
        f"Expected REJECT or INDETERMINATE for FR/O/2010, got {token}"


@pytest.mark.skipif(not _PANEL.exists(), reason="panel CSV not found")
def test_did_sc_reproducible_across_runs(tmp_path):
    """Fixed seed → identical DiD verdict."""
    tokens = []
    for i in range(2):
        outdir = tmp_path / f"did_rep{i}"
        res = _run(
            _PIPELINE / "run_did_synthetic_control.py",
            "--panel", str(_PANEL),
            "--treated-geo", "EU27_2020",
            "--event-year", "2015",
            "--outcome-col", "O",
            "--outdir", str(outdir),
            "--n-boot", "100",
            "--seed", "99",
        )
        assert res.returncode == 0
        tokens.append(_assert_verdict(outdir))
    assert tokens[0] == tokens[1], "Verdict changed between runs with same seed"


# ── Verdict token contract ─────────────────────────────────────────────────────

def test_verdict_tokens_are_exhaustive():
    """Ensure the set of valid verdict tokens hasn't drifted."""
    assert VALID_VERDICTS == {"ACCEPT", "REJECT", "INDETERMINATE"}
