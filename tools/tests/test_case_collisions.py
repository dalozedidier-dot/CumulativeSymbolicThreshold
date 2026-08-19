"""CI guard: no two tracked files may differ only in case.

Prevents regressions like docs/INDEX.md vs docs/index.md, which break checkouts
on case-insensitive filesystems (macOS / Windows).
"""
from __future__ import annotations

from tools.check_case_collisions import find_case_collisions, tracked_files


def test_find_case_collisions_detects_and_groups():
    paths = ["docs/INDEX.md", "docs/index.md", "src/a.py", "src/A.py", "unique.txt"]
    groups = find_case_collisions(paths)
    assert ["docs/INDEX.md", "docs/index.md"] in groups
    assert ["src/A.py", "src/a.py"] in groups
    assert all(len(g) > 1 for g in groups)
    # A unique path never appears in a collision group.
    assert not any("unique.txt" in g for g in groups)


def test_find_case_collisions_clean_when_unique():
    assert find_case_collisions(["a/b.py", "a/c.py", "d/e.md"]) == []


def test_repository_has_no_case_collisions():
    """The live repository must be free of case-insensitive path collisions."""
    collisions = find_case_collisions(tracked_files())
    assert collisions == [], f"Case-insensitive path collisions found: {collisions}"


def test_tracked_files_falls_back_without_git(monkeypatch):
    """Source archives without .git must still be checkable."""

    import subprocess

    import tools.check_case_collisions as ccc

    def fail_git() -> list[str]:
        raise subprocess.CalledProcessError(128, ["git", "ls-files"])

    monkeypatch.setattr(ccc, "_git_tracked_files", fail_git)
    monkeypatch.setattr(ccc, "_filesystem_files", lambda: ["README.md", "docs/index.md"])

    assert ccc.tracked_files() == ["README.md", "docs/index.md"]
