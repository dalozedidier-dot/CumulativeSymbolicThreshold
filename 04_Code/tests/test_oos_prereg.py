"""The pre-registered OOS prediction must not silently drift from the code.

These are cheap consistency checks (no Monte-Carlo), so they live in the *full*
tier, not the heavy *scientific* tier: they guarantee that the frozen
pre-registration (`contracts/OOS_PREREG.json` + the human prereg) stays in lockstep
with `oric.frozen_params` and the runner's emitted verdict tokens.
"""
from __future__ import annotations

import json
from pathlib import Path

from oric.frozen_params import FROZEN_PARAMS

_REPO = Path(__file__).resolve().parents[2]
_CONTRACT = _REPO / "contracts" / "OOS_PREREG.json"
_PREREG_MD = _REPO / "02_Protocol" / "PREREG_OOS_2026-06_LOCALIZED_TRANSITION.md"


def _contract() -> dict:
    return json.loads(_CONTRACT.read_text(encoding="utf-8"))


def test_contract_exists_and_is_frozen():
    c = _contract()
    assert c["schema"] == "oric.oos_prereg.v1"
    assert c["status"] == "FROZEN"
    assert c["freeze_date"] == "2026-06-22"


def test_frozen_params_match_code():
    fp = _contract()["primary_synthetic"]["frozen_params"]
    assert fp["seed_base"] == FROZEN_PARAMS.seed_base
    assert fp["n_replicates"] == FROZEN_PARAMS.n_replicates


def test_verdict_tokens_match_runner():
    """Tokens in the contract must be exactly those the runner can emit."""
    tokens = set(_contract()["primary_synthetic"]["verdict_tokens"])
    assert tokens == {"OOS_SKILL_DEMONSTRATED", "OOS_SKILL_INCONCLUSIVE"}


def test_decision_rule_is_specific_not_a_crossing():
    c = _contract()
    # The whole point: predict a LOCALIZED regime change, explicitly NOT 'C rises'.
    what = c["what_is_predicted"].lower()
    assert "localized" in what
    assert "not 'c keeps rising'" in what
    # The predictor is the trend-preserving CSD surrogate null (a localized test).
    assert "surrogate" in c["predictor"]["name"].lower()
    assert "slowing down" in c["predictor"]["statistic"].lower()


def test_human_prereg_present_and_linked():
    assert _PREREG_MD.exists()
    text = _PREREG_MD.read_text(encoding="utf-8")
    assert "contracts/OOS_PREREG.json" in text
    assert "REGISTERED_PENDING" in text or "registered, pending" in text.lower()


def test_secondary_real_data_split_is_frozen():
    sec = _contract()["secondary_real_data"]
    assert sec["status"] == "REGISTERED_PENDING"
    assert "fred_monthly" in sec["dataset"]
    assert "train" in sec["split"] and "test" in sec["split"]
