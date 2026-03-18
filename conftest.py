# conftest.py — Root pytest configuration.
#
# Canonical mode: pip install -e ".[dev]" (editable install makes src/oric
# importable without sys.path hacks). The sys.path insertion below is a
# fallback for environments where the editable install is not active.

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# run_bcm_test.py is a CLI runner (not a test suite) but its name matches
# pytest's *_test.py pattern and it imports an optional module (bcm_plasticity).
# Exclude it from collection to prevent spurious ImportErrors.
collect_ignore = [
    "04_Code/pipeline/run_bcm_test.py",
]
