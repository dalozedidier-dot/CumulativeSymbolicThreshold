"""Regression tests for run_all_tests path serialization."""
from __future__ import annotations

from pipeline.run_all_tests import _display_path


def test_display_path_accepts_paths_inside_repo(tmp_path):
    root = tmp_path / "repo"
    target = root / "05_Results" / "run"
    assert _display_path(target, root) == "05_Results/run"


def test_display_path_accepts_absolute_paths_outside_repo(tmp_path):
    root = tmp_path / "repo"
    external = tmp_path / "external" / "run"
    assert _display_path(external, root) == str(external)
