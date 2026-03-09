"""Tests for the 7 real-data sector pilot datasets.

Validates:
  1. proxy_spec.json structure (schema + required ORI-C variables)
  2. real.csv integrity (no NaN in ORI-C columns, values in [0,1], minimum rows)
  3. Column consistency between proxy_spec and CSV headers
  4. Per-dataset invariants (e.g. COVID has 4 countries, EEG has 500 segments)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_REPO = Path(__file__).resolve().parents[2]
_DATA = _REPO / "03_Data"

# ── Dataset registry ────────────────────────────────────────────────────────

PILOTS = [
    {
        "id": "solar",
        "sector": "sector_cosmo",
        "pilot": "pilot_solar",
        "min_rows": 200,
        "oric_cols": ["O", "R", "I", "demand", "S"],
    },
    {
        "id": "llm_scaling",
        "sector": "sector_ai_tech",
        "pilot": "pilot_llm_scaling",
        "min_rows": 50,
        "oric_cols": ["O", "R", "I", "demand", "S"],
    },
    {
        "id": "btc",
        "sector": "sector_finance",
        "pilot": "pilot_btc",
        "min_rows": 100,
        "oric_cols": ["O", "R", "I", "demand", "S"],
    },
    {
        "id": "pbdb_marine",
        "sector": "sector_bio",
        "pilot": "pilot_pbdb_marine",
        "min_rows": 80,
        "oric_cols": ["O", "R", "I", "demand", "S"],
    },
    {
        "id": "eeg_bonn",
        "sector": "sector_neuro",
        "pilot": "pilot_eeg_bonn",
        "min_rows": 400,
        "oric_cols": ["O", "R", "I", "demand", "S"],
    },
    {
        "id": "pantheon_sn",
        "sector": "sector_cosmo",
        "pilot": "pilot_pantheon_sn",
        "min_rows": 80,
        "oric_cols": ["O", "R", "I", "demand", "S"],
    },
    {
        "id": "covid",
        "sector": "sector_health",
        "pilot": "pilot_covid_excess_mortality",
        "min_rows": 150,
        "oric_cols": ["O", "R", "I", "demand", "S"],
    },
]


def _data_dir(pilot: dict) -> Path:
    return _DATA / pilot["sector"] / "real" / pilot["pilot"]


def _pilot_ids():
    return [p["id"] for p in PILOTS]


def _get_pilot(pilot_id: str) -> dict:
    return next(p for p in PILOTS if p["id"] == pilot_id)


# ── proxy_spec.json validation ──────────────────────────────────────────────

@pytest.mark.parametrize("pilot_id", _pilot_ids())
def test_proxy_spec_exists(pilot_id):
    pilot = _get_pilot(pilot_id)
    spec_path = _data_dir(pilot) / "proxy_spec.json"
    assert spec_path.exists(), f"proxy_spec.json missing for {pilot_id}"


@pytest.mark.parametrize("pilot_id", _pilot_ids())
def test_proxy_spec_valid_json(pilot_id):
    pilot = _get_pilot(pilot_id)
    spec_path = _data_dir(pilot) / "proxy_spec.json"
    if not spec_path.exists():
        pytest.skip("proxy_spec.json not found")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert "dataset_id" in spec, "Missing dataset_id"
    assert "columns" in spec, "Missing columns"
    assert isinstance(spec["columns"], list), "columns must be a list"
    assert len(spec["columns"]) >= 3, "Need at least O, R, I columns"


@pytest.mark.parametrize("pilot_id", _pilot_ids())
def test_proxy_spec_has_ori_variables(pilot_id):
    """Each proxy_spec must declare O, R, I via oric_variable or oric_role."""
    pilot = _get_pilot(pilot_id)
    spec_path = _data_dir(pilot) / "proxy_spec.json"
    if not spec_path.exists():
        pytest.skip("proxy_spec.json not found")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    oric_vars = set()
    for col in spec.get("columns", []):
        var = col.get("oric_variable") or col.get("oric_role")
        if var:
            oric_vars.add(var)

    for required in ("O", "R", "I"):
        assert required in oric_vars, f"Missing ORI-C variable: {required}"


# ── real.csv validation ─────────────────────────────────────────────────────

@pytest.mark.parametrize("pilot_id", _pilot_ids())
def test_csv_exists(pilot_id):
    pilot = _get_pilot(pilot_id)
    csv_path = _data_dir(pilot) / "real.csv"
    assert csv_path.exists(), f"real.csv missing for {pilot_id}"


@pytest.mark.parametrize("pilot_id", _pilot_ids())
def test_csv_minimum_rows(pilot_id):
    pilot = _get_pilot(pilot_id)
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path)
    assert len(df) >= pilot["min_rows"], \
        f"{pilot_id}: expected >= {pilot['min_rows']} rows, got {len(df)}"


@pytest.mark.parametrize("pilot_id", _pilot_ids())
def test_csv_has_oric_columns(pilot_id):
    pilot = _get_pilot(pilot_id)
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path, nrows=0)
    for col in pilot["oric_cols"]:
        assert col in df.columns, f"{pilot_id}: missing column '{col}'"


@pytest.mark.parametrize("pilot_id", _pilot_ids())
def test_csv_no_nan_in_oric_columns(pilot_id):
    pilot = _get_pilot(pilot_id)
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path)
    for col in pilot["oric_cols"]:
        if col not in df.columns:
            continue
        nan_count = df[col].isna().sum()
        assert nan_count == 0, \
            f"{pilot_id}.{col}: {nan_count} NaN values found"


@pytest.mark.parametrize("pilot_id", _pilot_ids())
def test_csv_oric_values_in_unit_interval(pilot_id):
    """O, R, I, demand, S must be in [0, 1]."""
    pilot = _get_pilot(pilot_id)
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path)
    for col in pilot["oric_cols"]:
        if col not in df.columns:
            continue
        vals = df[col].values
        assert np.all(vals >= -1e-9), \
            f"{pilot_id}.{col}: min={vals.min():.6f} < 0"
        assert np.all(vals <= 1.0 + 1e-9), \
            f"{pilot_id}.{col}: max={vals.max():.6f} > 1"


# ── Per-dataset specific invariants ─────────────────────────────────────────

def test_covid_has_four_countries():
    """COVID dataset must contain FR, IT, US, BE."""
    pilot = _get_pilot("covid")
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path)
    assert "country" in df.columns, "COVID dataset missing 'country' column"
    countries = set(df["country"].unique())
    expected = {"FR", "IT", "US", "BE"}
    assert expected.issubset(countries), \
        f"Expected countries {expected}, got {countries}"


def test_eeg_has_500_segments():
    """EEG Bonn dataset must have exactly 500 segments (100 per class)."""
    pilot = _get_pilot("eeg_bonn")
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path)
    assert len(df) == 500, f"EEG: expected 500 rows, got {len(df)}"
    if "class_label" in df.columns:
        assert df["class_label"].nunique() == 5, \
            "EEG: expected 5 class labels (A-E)"


def test_pbdb_covers_phanerozoic():
    """PBDB dataset should span the full Phanerozoic (>400 Myr range)."""
    pilot = _get_pilot("pbdb_marine")
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path)
    if "Ma" in df.columns:
        time_range = df["Ma"].max() - df["Ma"].min()
        assert time_range > 400, \
            f"PBDB: time range {time_range:.0f} Myr too short for Phanerozoic"


def test_pantheon_redshift_range():
    """Pantheon+ SN dataset should cover z from ~0 to > 1.5."""
    pilot = _get_pilot("pantheon_sn")
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path)
    if "z" in df.columns:
        assert df["z"].max() > 1.5, \
            f"Pantheon: max z={df['z'].max():.2f}, expected > 1.5"
        assert df["z"].min() < 0.05, \
            f"Pantheon: min z={df['z'].min():.2f}, expected < 0.05"


def test_solar_minimum_coverage():
    """Solar dataset should cover at least 2 solar cycles (~22 years)."""
    pilot = _get_pilot("solar")
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path)
    # With monthly data, 22 years = 264 months
    assert len(df) >= 264, \
        f"Solar: {len(df)} rows < 264 (22 years of monthly data)"


def test_btc_monotonic_time():
    """BTC time index should be monotonically increasing."""
    pilot = _get_pilot("btc")
    csv_path = _data_dir(pilot) / "real.csv"
    if not csv_path.exists():
        pytest.skip("real.csv not found")
    df = pd.read_csv(csv_path)
    if "t" in df.columns:
        diffs = np.diff(df["t"].values)
        assert np.all(diffs > 0), "BTC: time index not monotonically increasing"
