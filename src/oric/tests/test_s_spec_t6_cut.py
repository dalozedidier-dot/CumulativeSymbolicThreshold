from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oric.s_spec import SSpec, SSpecError
from oric.t6_cut import apply_cut, run_t6_cut

pytestmark = pytest.mark.smoke


def _valid_spec() -> SSpec:
    return SSpec(
        dataset_id="toy_lineage",
        kind="lineage",
        source_column="repertoire",
        copy_rule="descendant inherits parent repertoire unless cut",
        cut_rule="set inherited repertoire to 0 at generation boundary",
        cut_operator="zero",
    )


def test_sspec_rejects_cap_as_source():
    with pytest.raises(SSpecError):
        SSpec(
            dataset_id="bad",
            source_column="Cap",
            copy_rule="x",
            cut_rule="y",
        ).validate()


def test_sspec_requires_copy_and_cut():
    with pytest.raises(SSpecError):
        SSpec(dataset_id="bad", source_column="repertoire").validate()


def test_t6_cut_cannot_accept_a_mechanical_collapse():
    n = 80
    repertoire = np.linspace(0.1, 2.0, n)
    v = np.concatenate([np.zeros(20), np.linspace(0.0, 1.5, n - 20)])
    df = pd.DataFrame({"repertoire": repertoire, "V": v, "S": repertoire})
    result = run_t6_cut(df, _valid_spec(), seed=1)
    assert result.verdict == "INDETERMINATE"
    assert result.c_cut == 0
    assert result.to_dict()["confirmatory_eligible"] is False
    assert result.delta_cut >= 0


def test_t6_cut_rejects_when_s_is_irrelevant():
    n = 80
    rng = np.random.default_rng(0)
    repertoire = rng.normal(size=n)
    v = np.linspace(0.0, 2.0, n)
    df = pd.DataFrame({"repertoire": repertoire, "V": v, "S": repertoire})
    result = run_t6_cut(df, _valid_spec(), seed=2)
    assert result.verdict == "INDETERMINATE"


def _table() -> pd.DataFrame:
    return pd.DataFrame({"repertoire": np.arange(20.0), "V": np.arange(20.0), "Cap": 1.0})


def test_missing_and_invalid_spec_are_indeterminate():
    for spec in (None, replace(_valid_spec(), copy_rule="")):
        result = run_t6_cut(_table(), spec)
        assert result.verdict == "INDETERMINATE"
        assert result.diagnostic_status == "not_computed"
        assert result.to_dict()["c_intact"] is None
        json.dumps(result.to_dict(), allow_nan=False)


@pytest.mark.parametrize("column", ["repertoire", "V"])
@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf, "invalid"])
def test_bad_data_cannot_pass(column, value):
    df = _table().astype(object)
    df.loc[3, column] = value
    result = run_t6_cut(df, _valid_spec())
    assert result.diagnostic_status == "not_computed"
    assert result.verdict == "INDETERMINATE"


@pytest.mark.parametrize("column", ["repertoire", "V"])
def test_missing_column_is_indeterminate(column):
    assert run_t6_cut(_table().drop(columns=column), _valid_spec()).verdict == "INDETERMINATE"


def test_stale_s_is_replaced_by_declared_source_without_mutation():
    df = _table().assign(S=0.0)
    before = df.copy(deep=True)
    result = run_t6_cut(df, _valid_spec(), sham="permute_cap")
    assert result.c_intact == 19.0
    assert result.c_sham == result.c_intact
    assert result.verdict == "INDETERMINATE"
    pd.testing.assert_frame_equal(df, before)


def test_s_unit_change_does_not_change_diagnostic_threshold():
    df = _table()
    first = run_t6_cut(df, _valid_spec(), sham="permute_cap")
    df["repertoire"] *= 100
    second = run_t6_cut(df, _valid_spec(), sham="permute_cap")
    assert first.to_dict() == second.to_dict()


def test_reset_generation_does_not_fake_a_cut_by_centering():
    result = run_t6_cut(_table(), replace(_valid_spec(), cut_operator="reset_generation"))
    assert result.diagnostic_status == "not_computed"
    assert "generation boundaries" in result.reason


@pytest.mark.parametrize("delay", [1, 20, 100])
def test_delay_preserves_length_and_index(delay):
    s = _table()["repertoire"]
    cut = apply_cut(s, replace(_valid_spec(), cut_operator="delay", delay_steps=delay),
                    np.random.default_rng(0))
    assert len(cut) == len(s)
    assert cut.index.equals(s.index)
    assert (cut.iloc[:min(delay, len(s))] == s.iloc[0]).all()


def test_constant_c_has_no_invented_scale():
    result = run_t6_cut(_table().assign(V=1.0), _valid_spec())
    assert result.to_dict()["diagnostic_threshold"] is None
    assert not result.cut_collapses
    assert not result.sham_insufficient


def test_short_series_is_not_computed():
    assert run_t6_cut(_table().iloc[:9], _valid_spec()).diagnostic_status == "not_computed"


@pytest.mark.parametrize("column", [" Cap ", "v", "SIGMA", "o"])
def test_forbidden_source_aliases(column):
    with pytest.raises(SSpecError):
        replace(_valid_spec(), source_column=column).validate()


@pytest.mark.parametrize("mode", ["valid", "missing", "invalid", "no_v"])
def test_cli_writes_strict_json_and_never_manufactures_evidence(tmp_path, mode):
    root = Path(__file__).resolve().parents[3]
    table = _table()
    if mode == "no_v":
        table = table.drop(columns="V")
    csv = tmp_path / "table.csv"
    table.to_csv(csv, index=False)
    args = [sys.executable, str(root / "04_Code/sector/bio/run_t6_cut.py"),
            "--csv", str(csv), "--outdir", str(tmp_path)]
    if mode != "missing":
        spec_path = tmp_path / "spec.json"
        if mode == "invalid":
            spec_path.write_text("{broken", encoding="utf-8")
        else:
            _valid_spec().to_json_file(spec_path)
        args.extend(["--spec", str(spec_path)])
    completed = subprocess.run(args, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads((tmp_path / "t6_cut_verdict.json").read_text(encoding="utf-8"))
    assert payload["result"]["verdict"] == "INDETERMINATE"
    assert payload["result"]["diagnostic_status"] == (
        "computed" if mode == "valid" else "not_computed"
    )
    json.dumps(payload, allow_nan=False)
