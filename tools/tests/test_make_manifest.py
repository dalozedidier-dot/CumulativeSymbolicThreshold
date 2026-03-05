"""Unit tests for tools/make_manifest.py."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.make_manifest import build_manifest, sha256_file


# ── sha256_file ───────────────────────────────────────────────────────────────


def test_sha256_file_known_content(tmp_path):
    f = tmp_path / "data.bin"
    data = b"hello world"
    f.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    assert sha256_file(f) == expected


def test_sha256_file_empty(tmp_path):
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")
    expected = hashlib.sha256(b"").hexdigest()
    assert sha256_file(f) == expected


def test_sha256_file_consistent(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("consistent content", encoding="utf-8")
    h1 = sha256_file(f)
    h2 = sha256_file(f)
    assert h1 == h2


# ── build_manifest ────────────────────────────────────────────────────────────


def test_build_manifest_lists_all_files(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("aaa")
    (root / "b.txt").write_text("bbb")

    result = build_manifest(root, exclude_names=set())
    assert "a.txt" in result["entries"]
    assert "b.txt" in result["entries"]


def test_build_manifest_excludes_names(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "manifest.json").write_text("{}")
    (root / "data.txt").write_text("data")

    result = build_manifest(root, exclude_names={"manifest.json"})
    assert "manifest.json" not in result["entries"]
    assert "data.txt" in result["entries"]


def test_build_manifest_hashes_correct(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    data = b"check this hash"
    f = root / "file.bin"
    f.write_bytes(data)

    result = build_manifest(root, exclude_names=set())
    expected_hash = hashlib.sha256(data).hexdigest()
    assert result["entries"]["file.bin"] == expected_hash


def test_build_manifest_subdirectories(tmp_path):
    root = tmp_path / "root"
    sub = root / "sub"
    sub.mkdir(parents=True)
    (sub / "nested.txt").write_text("nested")

    result = build_manifest(root, exclude_names=set())
    assert "sub/nested.txt" in result["entries"]


def test_build_manifest_empty_dir(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    result = build_manifest(root, exclude_names=set())
    assert result["entries"] == {}


def test_build_manifest_root_field(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    result = build_manifest(root, exclude_names=set())
    assert "root" in result
    assert str(root) == result["root"]


def test_build_manifest_multiple_excludes(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "manifest.json").write_text("{}")
    (root / "skip.tmp").write_text("temp")
    (root / "keep.txt").write_text("keep")

    result = build_manifest(root, exclude_names={"manifest.json", "skip.tmp"})
    assert "manifest.json" not in result["entries"]
    assert "skip.tmp" not in result["entries"]
    assert "keep.txt" in result["entries"]


def test_build_manifest_returns_sorted_entries(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    for name in ["z.txt", "a.txt", "m.txt"]:
        (root / name).write_text(name)

    result = build_manifest(root, exclude_names=set())
    keys = list(result["entries"].keys())
    assert keys == sorted(keys)
