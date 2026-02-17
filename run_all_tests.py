#!/usr/bin/env python3
"""
Convenience entrypoint.

Usage:
  python run_all_tests.py

This delegates to 04_Code/pipeline/run_all_tests.py
"""
from __future__ import annotations

import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "04_Code" / "pipeline" / "run_all_tests.py"), run_name="__main__")
