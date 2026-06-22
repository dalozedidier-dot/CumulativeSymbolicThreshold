#!/usr/bin/env python3
"""check_case_collisions.py - guard against case-insensitive path collisions.

Two tracked files whose paths differ only in case, for example ``docs/INDEX.md``
and ``docs/index.md``, cannot coexist safely on a case-insensitive filesystem.

The preferred source of truth is ``git ls-files``. When this project is checked
from a source archive, a Zenodo bundle, or any directory without ``.git/``, the
module falls back to a conservative filesystem walk so the guard still works.

Public API used by tests:
    tracked_files()                 -> list[str]
    find_case_collisions(paths)     -> list[list[str]]

CLI:
    python -m tools.check_case_collisions
"""
from __future__ import annotations

import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "replication_output",
    "_ci_out",
    "_collected_artifacts",
    "data/bundles_extracted",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def _is_under_excluded_dir(rel: Path) -> bool:
    rel_posix = rel.as_posix()
    parts = set(rel.parts)
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    return any(rel_posix == d or rel_posix.startswith(d + "/") for d in EXCLUDED_DIRS)


def _git_tracked_files() -> list[str]:
    """Return repo-relative paths from git, or raise if git metadata is absent."""
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def _filesystem_files() -> list[str]:
    """Return repo-relative paths by walking the tree when ``.git`` is absent."""
    files: list[str] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if _is_under_excluded_dir(rel):
            continue
        if p.suffix in EXCLUDED_SUFFIXES:
            continue
        files.append(rel.as_posix())
    return sorted(files)


def tracked_files() -> list[str]:
    """Return repo-relative paths of tracked or archive-visible source files.

    In a normal checkout, this uses ``git ls-files``. In a source archive without
    git metadata, it falls back to a filesystem walk that excludes generated
    directories and caches. This keeps the check useful for external reviewers.
    """
    try:
        return _git_tracked_files()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _filesystem_files()


def find_case_collisions(paths: list[str]) -> list[list[str]]:
    """Return groups of paths that collide when compared case-insensitively."""
    buckets: dict[str, set[str]] = defaultdict(set)
    for p in paths:
        buckets[p.lower()].add(p)
    collisions = [sorted(v) for v in buckets.values() if len(v) > 1]
    return sorted(collisions)


def main() -> int:
    collisions = find_case_collisions(tracked_files())
    if not collisions:
        print("OK: no case-insensitive path collisions.")
        return 0
    print(f"ERROR: {len(collisions)} case-insensitive path collision(s):", file=sys.stderr)
    for group in collisions:
        print("  - " + "  <->  ".join(group), file=sys.stderr)
    print(
        "\nTwo files differing only in case break case-insensitive checkouts "
        "on macOS and Windows. Keep one canonical spelling.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
