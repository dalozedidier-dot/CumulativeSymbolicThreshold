"""Console-script entry points for the oric package.

These thin wrappers delegate to the scripts in scripts/ so that
``pip install -e .`` makes ``oric-run-all`` and ``oric-run-tests``
available on PATH.
"""
from __future__ import annotations

import runpy
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent


def run_all() -> None:
    """Entry point for ``oric-run-all``."""
    runpy.run_path(str(_ROOT / "scripts" / "run_all.py"), run_name="__main__")


def run_all_tests() -> None:
    """Entry point for ``oric-run-tests``."""
    runpy.run_path(str(_ROOT / "scripts" / "run_all_tests.py"), run_name="__main__")
