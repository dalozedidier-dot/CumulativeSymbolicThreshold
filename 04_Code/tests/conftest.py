# conftest.py — Test-local pytest configuration for 04_Code/tests.
#
# Canonical mode: pip install -e ".[dev]" from the repository root.
# The sys.path insertion below is a fallback for environments where
# the editable install is not active.

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
