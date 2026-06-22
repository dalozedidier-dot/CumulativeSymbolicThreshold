"""Integrity + scope guards for data_pack_manifest.json.

These run in CI (the `tools` test path), so a stale hash, a missing reference
file, or an unlisted new frozen file fails the build — and the manifest can never
silently drift from the bytes on disk again.
"""
from __future__ import annotations

import json

import tools.build_data_pack_manifest as bdpm
import tools.verify_data_pack as vdp


def _committed() -> dict:
    return json.loads(bdpm.MANIFEST.read_text(encoding="utf-8"))


def test_committed_manifest_verifies_clean():
    assert vdp.verify() == []


def test_builder_is_idempotent_with_committed():
    fresh = bdpm.build()
    assert bdpm._normalized(fresh) == bdpm._normalized(_committed())


def test_schema_is_v2_and_lists_frozen_dirs():
    m = _committed()
    assert m["schema"] == "oric.data_pack_manifest.v2"
    assert m["frozen_dirs"] == bdpm.FROZEN_DIRS
    assert m["n_entries"] == len(m["entries"])


def test_scope_excludes_regenerable_extracted_bundles():
    """The frozen manifest must NOT list regenerable extracted-bundle content."""
    m = _committed()
    assert not any(e["path"].startswith("data/bundles_extracted/") for e in m["entries"])
    # …but it MUST pin the source zips those derive from.
    assert any(e["path"].startswith("data/bundles/") and e["path"].endswith(".zip")
               for e in m["entries"])


def test_every_entry_has_sha256_and_bytes():
    for e in _committed()["entries"]:
        assert isinstance(e["path"], str) and e["path"]
        assert isinstance(e["sha256"], str) and len(e["sha256"]) == 64
        assert isinstance(e["bytes"], int) and e["bytes"] >= 0


def test_verify_detects_tampering(tmp_path, monkeypatch):
    fake = tmp_path / "manifest.json"
    fake.write_text(json.dumps({
        "schema": "oric.data_pack_manifest.v2",
        "frozen_dirs": [],  # skip completeness, exercise the hash/bytes path
        "entries": [{"path": "data/finance/^spx_m.csv", "sha256": "0" * 64, "bytes": 1}],
    }))
    monkeypatch.setattr(vdp, "MANIFEST", fake)
    errors = vdp.verify()
    assert any(("SHA256 mismatch" in e) or ("BYTES mismatch" in e) for e in errors)


def test_builder_falls_back_without_git(monkeypatch):
    """The data-pack builder must work from source archives without .git."""

    import subprocess

    def fail_git() -> list[str]:
        raise subprocess.CalledProcessError(128, ["git", "ls-files"])

    monkeypatch.setattr(bdpm, "_git_tracked_files", fail_git)
    monkeypatch.setattr(bdpm, "_filesystem_files", lambda: ["data/finance/^spx_m.csv"])

    fresh = bdpm.build(generated_utc="2000-01-01T00:00:00+00:00")
    assert fresh["n_entries"] == 1
    assert fresh["entries"][0]["path"] == "data/finance/^spx_m.csv"
    assert fresh["entries"][0]["bytes"] > 0
