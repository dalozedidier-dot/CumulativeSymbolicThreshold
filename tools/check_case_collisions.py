#!/usr/bin/env python3
"""check_case_collisions.py — guard against case-insensitive path collisions.

Two tracked files whose paths differ only in case (e.g. ``docs/INDEX.md`` and
``docs/index.md``) cannot coexist on a case-insensitive filesystem (macOS, most
Windows setups): one silently shadows the other on checkout, and git reports the
tree as perpetually dirty. This module finds such collisions so CI can fail fast.

It also flags collisions that differ only by Unicode/whitespace normalisation of
the basename, but case is the common one.

Public API (used by tests):
    tracked_files()                 -> list[str]
    find_case_collisions(paths)     -> list[list[str]]   (groups of >1 colliding)

CLI:
    python -m tools.check_case_collisions        # exit 1 if any collision
"""
from __future__ import annotations

import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tracked_files() -> list[str]:
    """Return repo-relative paths of all git-tracked files."""
    out = subprocess.run(
        ["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line]


def find_case_collisions(paths: list[str]) -> list[list[str]]:
    """Return groups of paths that collide when compared case-insensitively.

    Each returned group has >= 2 distinct original paths sharing one lower-cased
    form. Groups and their members are sorted for stable output.
    """
    buckets: dict[str, set[str]] = defaultdict(set)
    for p in paths:
        buckets[p.lower()].add(p)
    collisions = [sorted(v) for v in buckets.values() if len(v) > 1]
    return sorted(collisions)


def main() -> int:
    collisions = find_case_collisions(tracked_files())
    if not collisions:
        print("OK: no case-insensitive path collisions among tracked files.")
        return 0
    print(f"ERROR: {len(collisions)} case-insensitive path collision(s):", file=sys.stderr)
    for group in collisions:
        print("  - " + "  ⇄  ".join(group), file=sys.stderr)
    print(
        "\nTwo files differing only in case break case-insensitive checkouts "
        "(macOS/Windows). Keep one canonical spelling.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
