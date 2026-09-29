from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from oric.s_spec import SSpec, SSpecError
from oric.t6_cut import run_t6_cut


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


def test_t6_cut_accepts_when_c_depends_on_s():
    n = 80
    repertoire = np.linspace(0.1, 2.0, n)
    v = np.concatenate([np.zeros(20), np.linspace(0.0, 1.5, n - 20)])
    df = pd.DataFrame({"repertoire": repertoire, "V": v, "S": repertoire})
    result = run_t6_cut(df, _valid_spec(), seed=1)
    assert result.verdict in {"ACCEPT", "INDETERMINATE"}
    assert result.delta_cut >= 0


def test_t6_cut_rejects_when_s_is_irrelevant():
    n = 80
    rng = np.random.default_rng(0)
    repertoire = rng.normal(size=n)
    v = np.linspace(0.0, 2.0, n)
    df = pd.DataFrame({"repertoire": repertoire, "V": v, "S": repertoire})
    result = run_t6_cut(df, _valid_spec(), seed=2)
    assert result.verdict in {"REJECT", "INDETERMINATE"}
