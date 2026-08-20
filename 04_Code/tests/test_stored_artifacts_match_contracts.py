"""Stored evidence artifacts must not drift from their frozen contracts.

Governance rule (docs/EVIDENCE_LADDER.md): every rung claimed in the docs must be
backed by a committed artifact under ``05_Results/``, and that artifact must have
been produced under the *frozen* parameters of its contract — never a tuned
variant. These checks are cheap (pure JSON reads, no Monte-Carlo) and fail loudly
if an artifact is deleted, regenerated with off-contract parameters, or edited by
hand (manifest sha256 vs table file).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_RESULTS = _REPO / "05_Results"
_CONTRACTS = _REPO / "contracts"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Registered real-data A/B/C block (rung 5–6) ──────────────────────────────

def test_registered_block_artifact_exists():
    assert (_RESULTS / "registered_block" / "tables" / "registered_block.json").exists(), (
        "docs/EVIDENCE_LADDER.md claims a registered-block verdict; the artifact "
        "must be committed under 05_Results/registered_block/"
    )


def test_registered_block_matches_frozen_contract():
    contract = _load(_CONTRACTS / "REAL_DATA_REGISTRATION.json")
    result = _load(_RESULTS / "registered_block" / "tables" / "registered_block.json")
    assert result["criteria"] == contract["criteria"], (
        "registered-block artifact was not produced under the frozen criteria"
    )
    assert result["dated_hypothesis"]["t1"] == contract["dated_hypothesis"]["t1"]
    assert result["dated_hypothesis"]["t2"] == contract["dated_hypothesis"]["t2"]
    assert result["dataset_A"] == contract["dataset_A"]["id"]


def test_registered_block_manifest_integrity():
    manifest = _load(_RESULTS / "registered_block" / "manifest.json")
    tables = _RESULTS / "registered_block" / "tables" / "registered_block.json"
    assert manifest["json_sha256"] == _sha256(tables), "artifact edited after manifest"
    assert manifest["contract_sha256"] == _sha256(_CONTRACTS / "REAL_DATA_REGISTRATION.json"), (
        "contract changed since the stored run — rerun run_registered_block.py"
    )
    verdict = (_RESULTS / "registered_block" / "verdict.txt").read_text().strip()
    assert verdict == manifest["verdict"]
    assert verdict in {"REAL_BLOCK_CONFIRMED", "REAL_BLOCK_REJECTED", "REAL_BLOCK_INDETERMINATE"}


# ── Strong-negatives specificity battery (rung 7) ────────────────────────────

def test_strong_negatives_artifact_exists():
    assert (_RESULTS / "strong_negatives" / "tables" / "strong_negatives.json").exists(), (
        "docs/EVIDENCE_LADDER.md rung 7 claims a strong-negatives outcome; the "
        "artifact must be committed under 05_Results/strong_negatives/"
    )


def test_strong_negatives_matches_contract_shipped_result():
    contract = _load(_CONTRACTS / "STRONG_NEGATIVES_CRITERIA.json")
    result = _load(_RESULTS / "strong_negatives" / "tables" / "strong_negatives.json")
    fp = contract["frozen_params"]
    assert result["params"]["n"] == fp["n"]
    assert result["params"]["seed"] == fp["seed"]
    assert result["params"]["k"] == fp["k"]
    assert result["params"]["m"] == fp["m"]
    assert result["thresholds"] == {
        "fpr_max": contract["fpr_max"],
        "tpr_min": contract["tpr_min"],
    }
    shipped = contract["shipped_result"]
    assert result["verdict"] == shipped["verdict"]
    assert result["strong_negatives_fpr"] == shipped["strong_negatives_fpr"]
    assert result["raw_strong_negatives_fpr"] == shipped["raw_strong_negatives_fpr"]
    assert result["bifurcation_tpr"] == shipped["bifurcation_tpr"]


def test_strong_negatives_manifest_integrity():
    manifest = _load(_RESULTS / "strong_negatives" / "manifest.json")
    tables = _RESULTS / "strong_negatives" / "tables" / "strong_negatives.json"
    assert manifest["json_sha256"] == _sha256(tables), "artifact edited after manifest"
    verdict = (_RESULTS / "strong_negatives" / "verdict.txt").read_text().strip()
    assert verdict == manifest["verdict"]


# ── Pre-registered OOS prediction (rung 8) ───────────────────────────────────

def test_oos_confirmatory_artifact_uses_frozen_params():
    """The canonical 05_Results/oos_prediction/ run must be the lead=60 protocol."""
    contract = _load(_CONTRACTS / "OOS_PREREG.json")
    fp = contract["primary_synthetic"]["frozen_params"]
    result = _load(_RESULTS / "oos_prediction" / "tables" / "oos_prediction.json")
    assert result["lead"] == fp["lead"], (
        f"stored OOS artifact used lead={result['lead']} but the frozen prereg "
        f"requires lead={fp['lead']} (contracts/OOS_PREREG.json)"
    )
    assert result["n_replicates"] == fp["n_replicates"]
    assert result["n_surrogates"] == fp["n_surrogates"]
    assert result["alpha"] == fp["alpha"]
    assert result["seed_base"] == fp["seed_base"]
    assert result["verdict"] in set(contract["primary_synthetic"]["verdict_tokens"])


def test_oos_prefreeze_exploratory_run_preserved():
    """The pre-freeze lead=40 exploratory run is part of the honest audit trail."""
    contract = _load(_CONTRACTS / "OOS_PREREG.json")
    exploratory = contract["exploratory_outcome_before_freeze"]
    result = _load(
        _RESULTS
        / "oos_prediction"
        / "exploratory_lead40_prefreeze"
        / "tables"
        / "oos_prediction.json"
    )
    assert result["lead"] == 40
    assert round(result["confusion"]["bistable_tpr"], 4) == exploratory["bistable_tpr"]
    assert round(result["confusion"]["twin_fpr"], 4) == exploratory["twin_fpr"]
    assert round(result["fisher_exact_p_skill_above_chance"], 4) == exploratory["fisher_exact_p"]
    assert result["verdict"] == exploratory["verdict"]


# ── Endogenous full-statistical demonstration (rung 3) ───────────────────────
#
# This is the ONE artifact the README leans on for "the only stored
# full_statistical proof run with the obligatory triplet". It had no anti-drift
# check, and drifted: the stored copy carried an obsolete `joint_rule` claiming
# `power>=gate` was part of the PASS condition, while the runner had stopped
# imposing it (a 99 % CI beyond the SESOI is power-independent evidence). Read on
# its own the artifact was self-contradictory — passes=true with power 0.135
# against a stated gate of 0.70. These checks pin the rule to what the runner
# actually applies, so the two cannot silently diverge again.

def test_endogenous_full_statistical_artifact_exists():
    assert (_RESULTS / "endogenous_full_statistical" / "tables" / "full_statistical.json").exists(), (
        "docs/EVIDENCE_LADDER.md rung 3 claims a full_statistical demonstration; "
        "the artifact must be committed under 05_Results/endogenous_full_statistical/"
    )


def test_endogenous_full_statistical_manifest_integrity():
    base = _RESULTS / "endogenous_full_statistical"
    manifest = _load(base / "manifest.json")
    assert manifest["json_sha256"] == _sha256(base / "tables" / "full_statistical.json"), (
        "artifact edited after manifest"
    )
    assert (base / "verdict.txt").read_text().strip() == manifest["verdict"]


def test_endogenous_full_statistical_ran_at_full_statistical_N():
    result = _load(_RESULTS / "endogenous_full_statistical" / "tables" / "full_statistical.json")
    assert result["run_mode"] == "full_statistical"
    assert result["n_replicates"] >= 50, (
        "rung 3 requires N >= 50; a smaller run is rung 2 (indicative) at best"
    )


def test_endogenous_joint_rule_matches_the_conjuncts_actually_applied():
    """`passes` must follow from the rule the artifact itself states.

    The stored rule text is the artifact's own account of how it was judged. If it
    names a conjunct the verdict does not honour, the artifact misreports its own
    standard — which is exactly the drift this file exists to catch.
    """
    result = _load(_RESULTS / "endogenous_full_statistical" / "tables" / "full_statistical.json")
    rule = result["joint_rule"]
    triplet = result["triplet"]

    expected = (
        triplet["effect_verdict"] == "EFFECT_EXCEEDS_SESOI"
        and triplet["p_value_mann_whitney"] < 0.01
        and result["detection"]["twin_fpr"] <= result["detection"]["fpr_ceiling"]
    )
    assert result["passes"] is expected
    assert result["verdict"] == ("DEMONSTRATION_CONFIRMED" if expected else "DEMONSTRATION_NOT_CONFIRMED")

    # Power is reported for transparency, not imposed. The rule must say so
    # rather than list it as a conjunct it does not enforce.
    powered = triplet["achieved_power_at_sesoi"] >= triplet["power_gate"]
    if not powered:
        assert "power>=gate" not in rule.replace(" ", ""), (
            f"joint_rule claims power>=gate but achieved power is "
            f"{triplet['achieved_power_at_sesoi']:.3f} < {triplet['power_gate']} "
            f"while passes={result['passes']}"
        )
        assert "not re-imposed" in rule or "transparency" in rule, (
            "when the power gate is unmet the rule must state explicitly that "
            "power is reported but not imposed"
        )


# ── Test A — accumulation control (localized-transition gate) ────────────────
#
# Same blind spot as rung 3: cited by EVIDENTIARY_STATUS.md, never checked here.
# The committed copy had drifted to a pre-localized-gate run reporting
# accumulation_fpr = 1.0 / DOES_NOT_SEPARATE, directly contradicting the README's
# `accumulation_fpr = 0.0`. These checks pin the artifact to the gate the docs
# actually claim, and keep the legacy figure visible as raw_accumulation_fpr.

_ACC = _RESULTS / "falsification" / "accumulation_control"


def test_accumulation_control_artifact_exists():
    assert (_ACC / "tables" / "accumulation_control.json").exists(), (
        "EVIDENTIARY_STATUS.md cites 05_Results/falsification/accumulation_control/ "
        "as the Test A evidence; the artifact must be committed"
    )


def test_accumulation_control_manifest_integrity():
    manifest = _load(_ACC / "manifest.json")
    assert manifest["json_sha256"] == _sha256(_ACC / "tables" / "accumulation_control.json"), (
        "artifact edited after manifest"
    )
    assert (_ACC / "verdict.txt").read_text().strip() == (
        "SEPARATES" if manifest["separates"] else "DOES_NOT_SEPARATE"
    )


def test_accumulation_control_reports_the_localized_gate():
    """The artifact must be a localized-gate run, not a legacy bare-ΔC one.

    `raw_accumulation_fpr` is the tell: the older runner did not emit it, and its
    `detector_fired` was the bare sustained-ΔC hit that fires on every smooth
    accumulation.
    """
    result = _load(_ACC / "tables" / "accumulation_control.json")
    assert "raw_accumulation_fpr" in result, (
        "stored artifact predates the localized-transition gate — regenerate with "
        "04_Code/pipeline/run_accumulation_control.py under its frozen params"
    )
    assert result["accumulation_fpr"] <= result["accumulation_fpr_max"]
    assert result["separates"] is True
    assert result["refutes_current_form"] is False


def test_accumulation_control_keeps_the_legacy_detector_visible():
    """The bare-ΔC leak is the honest counterpart of the gate's success."""
    result = _load(_ACC / "tables" / "accumulation_control.json")
    assert result["raw_accumulation_fpr"] > result["accumulation_fpr"], (
        "the legacy detector leaked on smooth accumulations; if that is no longer "
        "recorded the audit trail behind the gate's improvement is gone"
    )


def test_accumulation_control_ran_at_frozen_params():
    manifest = _load(_ACC / "manifest.json")
    params = _load(_ACC / "tables" / "accumulation_control.json")["params"]
    assert manifest["fast_mode"] is False, "a --fast smoke run is not evidence"
    assert params["seed"] == manifest["seed"]
    assert params["n"] == manifest["n_steps"]
    assert params["n_surrogates"] == manifest["n_surrogates"]


# ── Test B — surrogate null, and the joint confirmatory verdicts ─────────────

def test_surrogate_null_artifact_matches_the_confirmatory_test_b():
    """The standalone Test B artifact and the confirmatory suite must agree.

    Two files record the same number; if they diverge, one of them is stale and
    the reported `limiting_factor` can no longer be trusted.
    """
    surrogate = _load(_RESULTS / "surrogate_null" / "pantheon_sn" / "tables" / "surrogate_null.json")
    confirmatory = _load(_RESULTS / "confirmatory" / "pantheon_sn" / "tables" / "confirmatory.json")
    test_b = confirmatory["tests"]["B_surrogate_null"]
    assert surrogate["p_value"] == test_b["p_value"]
    assert surrogate["observed"] == test_b["observed"]
    assert surrogate["significant_at_01"] is test_b["pass"]


def test_surrogate_null_manifest_integrity():
    base = _RESULTS / "surrogate_null" / "pantheon_sn"
    manifest = _load(base / "manifest.json")
    assert manifest["json_sha256"] == _sha256(base / "tables" / "surrogate_null.json")
    assert (base / "verdict.txt").read_text().strip() == (
        "SIGNIFICANT" if manifest["significant_at_01"] else "NOT_SIGNIFICANT"
    )


@pytest.mark.parametrize("series", ["pantheon_sn", "fred_monthly"])
def test_confirmatory_manifest_integrity(series):
    base = _RESULTS / "confirmatory" / series
    manifest = _load(base / "manifest.json")
    assert manifest["json_sha256"] == _sha256(base / "tables" / "confirmatory.json")
    assert (base / "verdict.txt").read_text().strip() == manifest["verdict"]


@pytest.mark.parametrize("series", ["pantheon_sn", "fred_monthly"])
def test_confirmatory_verdict_follows_the_joint_rule(series):
    """CONFIRMED iff A and B and C and D all pass — no partial credit."""
    result = _load(_RESULTS / "confirmatory" / series / "tables" / "confirmatory.json")
    passes = {name: t["pass"] for name, t in result["tests"].items()}
    assert result["confirmed"] is all(passes.values())
    assert result["verdict"] == ("CONFIRMED" if all(passes.values()) else "NOT_CONFIRMED")
    assert sorted(result["failing_tests"]) == sorted(n for n, ok in passes.items() if not ok)


@pytest.mark.parametrize("series", ["pantheon_sn", "fred_monthly"])
def test_confirmatory_limiting_factor_is_a_failing_test(series):
    """`limiting_factor` is what the roadmap is read off — it must be real."""
    result = _load(_RESULTS / "confirmatory" / series / "tables" / "confirmatory.json")
    if result["confirmed"]:
        return
    assert result["limiting_factor"] in result["failing_tests"]


def test_confirmatory_and_manifest_agree_on_what_fails():
    for series in ("pantheon_sn", "fred_monthly"):
        base = _RESULTS / "confirmatory" / series
        manifest = _load(base / "manifest.json")
        result = _load(base / "tables" / "confirmatory.json")
        assert sorted(manifest["failing_tests"]) == sorted(result["failing_tests"])
        assert manifest["verdict"] == result["verdict"]
