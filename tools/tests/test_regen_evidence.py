"""Unit tests for tools/regen_evidence.py.

These do not replay the runs (that takes ~7 min and is what the
Evidence Replay workflow is for). They pin the declarative table: every entry
must point at a real runner and a real committed artifact, and the frozen
parameters must match the manifest the artifact was produced under — otherwise
the replay silently compares two different runs and reports a false OK.
"""
from __future__ import annotations

import json

import pytest

from tools.regen_evidence import EVIDENCE_RUNS, REPO, _diff_json, _flatten


def _args_to_dict(args: tuple[str, ...]) -> dict[str, str]:
    return {args[i].lstrip("-"): args[i + 1] for i in range(0, len(args) - 1, 2)}


# ── The table points at things that exist ────────────────────────────────────

@pytest.mark.parametrize("run", EVIDENCE_RUNS, ids=lambda r: r.run_id)
def test_runner_script_exists(run):
    assert (REPO / run.script).is_file(), f"{run.run_id}: no runner at {run.script}"


@pytest.mark.parametrize("run", EVIDENCE_RUNS, ids=lambda r: r.run_id)
def test_committed_artifact_exists(run):
    for table in run.tables:
        assert (REPO / run.artifact_dir / table).is_file(), (
            f"{run.run_id}: nothing to diff against at {run.artifact_dir}/{table}"
        )


@pytest.mark.parametrize("run", EVIDENCE_RUNS, ids=lambda r: r.run_id)
def test_input_paths_exist(run):
    """A missing --input makes the replay fail loudly, but late and in CI."""
    for key in ("--input", "--contract"):
        if key in run.args:
            value = run.args[run.args.index(key) + 1]
            assert (REPO / value).is_file(), f"{run.run_id}: missing {key} {value}"


def test_run_ids_are_unique():
    ids = [r.run_id for r in EVIDENCE_RUNS]
    assert len(ids) == len(set(ids))


def test_every_evidence_directory_is_committed():
    """The replay is pointless if git does not track the artifact."""
    import subprocess

    for run in EVIDENCE_RUNS:
        for table in run.tables:
            path = f"{run.artifact_dir}/{table}"
            out = subprocess.run(
                ["git", "ls-files", "--error-unmatch", path],
                cwd=REPO, capture_output=True, text=True,
            )
            assert out.returncode == 0, (
                f"{path} is not tracked by git — see .gitignore's evidence-surface list"
            )


# ── Frozen parameters agree with the manifests ───────────────────────────────

@pytest.mark.parametrize(
    "run_id,manifest_keys",
    [
        ("testA", {"seed": "seed", "n": "n_steps", "n-surrogates": "n_surrogates"}),
        ("rung7", {"seed": "seed", "n": "n_steps", "n-surrogates": "n_surrogates"}),
        ("testB", {"seed": "seed", "n-surrogates": "n_surrogates"}),
        ("confirmatory-pantheon", {"seed": "seed", "n-surrogates": "n_surrogates"}),
        ("confirmatory-fred", {"seed": "seed", "n-surrogates": "n_surrogates"}),
    ],
)
def test_frozen_args_match_manifest(run_id, manifest_keys):
    run = next(r for r in EVIDENCE_RUNS if r.run_id == run_id)
    manifest = json.loads((REPO / run.artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    args = _args_to_dict(run.args)
    for arg_name, manifest_name in manifest_keys.items():
        assert str(manifest[manifest_name]) == args[arg_name], (
            f"{run_id}: replay would use --{arg_name}={args[arg_name]} but the "
            f"artifact was produced with {manifest_name}={manifest[manifest_name]}"
        )


def test_rung8_args_match_the_frozen_prereg():
    """The OOS run is pre-registered; its replay must use the registered params."""
    run = next(r for r in EVIDENCE_RUNS if r.run_id == "rung8")
    contract = json.loads(
        (REPO / "contracts" / "OOS_PREREG.json").read_text(encoding="utf-8")
    )
    frozen = contract["primary_synthetic"]["frozen_params"]
    args = _args_to_dict(run.args)
    assert int(args["lead"]) == frozen["lead"]
    assert int(args["n-replicates"]) == frozen["n_replicates"]
    assert int(args["n-surrogates"]) == frozen["n_surrogates"]
    assert int(args["n-steps"]) == frozen["n_steps"]
    assert int(args["seed-base"]) == frozen["seed_base"]
    assert float(args["alpha"]) == frozen["alpha"]
    assert float(args["noise-sd"]) == frozen["noise_sd"]


def test_rung8_does_not_touch_the_prefreeze_exploratory_run():
    """exploratory_lead40_prefreeze/ is a different run kept as audit trail."""
    run = next(r for r in EVIDENCE_RUNS if r.run_id == "rung8")
    assert all("exploratory" not in t for t in run.tables)
    assert (REPO / run.artifact_dir / "exploratory_lead40_prefreeze").is_dir()


# ── The diff engine actually reports differences ─────────────────────────────

def test_flatten_uses_dotted_paths():
    flat = _flatten({"a": {"b": 1}, "c": [{"d": 2}]})
    assert flat == {"a.b": 1, "c.[0].d": 2}


def test_diff_json_reports_a_changed_field(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"triplet": {"power": 0.7}}))
    b.write_text(json.dumps({"triplet": {"power": 0.135}}))
    lines = _diff_json(a, b)
    assert len(lines) == 1
    assert "triplet.power" in lines[0]
    assert "0.7" in lines[0] and "0.135" in lines[0]


def test_diff_json_is_silent_on_identical_content(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    payload = {"verdict": "NOT_CONFIRMED", "tests": {"B": {"pass": False}}}
    a.write_text(json.dumps(payload))
    b.write_text(json.dumps(payload, indent=2, sort_keys=True))  # formatting differs
    assert _diff_json(a, b) == []


def test_diff_json_reports_added_and_removed_fields(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"accumulation_fpr": 1.0}))
    b.write_text(json.dumps({"accumulation_fpr": 0.0, "raw_accumulation_fpr": 1.0}))
    lines = "\n".join(_diff_json(a, b))
    assert "raw_accumulation_fpr" in lines
    assert "<absent>" in lines
