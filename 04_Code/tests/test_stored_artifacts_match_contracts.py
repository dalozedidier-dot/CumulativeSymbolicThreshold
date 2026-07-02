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
