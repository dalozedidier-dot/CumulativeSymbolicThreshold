"""Backward-compatible console-script entry points for ORI-C.

These wrappers intentionally delegate to packaged functions only. They do not
load repository-local ``scripts/`` files, which makes them safe to test from an
installed wheel.
"""
from __future__ import annotations

from oric.cli import run_all, run_all_tests

__all__ = ["run_all", "run_all_tests"]
