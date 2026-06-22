# conftest.py — Root pytest configuration.
#
# Canonical mode: pip install -e ".[dev]" (editable install makes src/oric
# importable without sys.path hacks). The sys.path insertion below is a
# fallback for environments where the editable install is not active.

import sys
from pathlib import Path

import pytest

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


# ── Test tiers (see docs/TESTING.md) ──────────────────────────────────────────
# Centralised taxonomy: rather than scatter `pytestmark` across ~15 files, the
# tier of each test is derived from its module name here. Tiers drive
# `make test-smoke | test-full | test-scientific` and the CI jobs.
#
#   smoke       — minimal, fast confidence check (imports + core pipeline)
#   scientific  — heavy statistical proofs (N>=50, surrogates, multiverse, OOS,
#                 causal inference, real-data onset). Excluded from `test-full`.
#   (untiered)  — ordinary unit/integration tests; the bulk of the suite.
#
# NOTE: this only LABELS tests. The coverage gate (CI unit_tests) still runs the
# whole suite, so tiering never lowers measured coverage.
_SMOKE_MODULES = {
    "test_smoke",            # src/oric core import + summarize_run
    "test_oric_pipeline",    # end-to-end core ORI-C pipeline (fast)
    "test_proof_infrastructure",  # proof-package / manifest plumbing
}
_SCIENTIFIC_MODULES = {
    "test_oos_prediction",
    "test_oos_panel",
    "test_scientific_validation",
    "test_scientific_validation_protocol",
    "test_accumulation_controls",
    "test_endogenous_full_statistical",
    "test_validation_protocol_reference_benchmark",
    "test_surrogates",
    "test_multiverse",
    "test_confirmatory",
    "test_early_warning",
    "test_real_data_transition",
    "test_did_sc",
    "test_pilot_generalization",
    "test_power_upgrade_protocol",
    "test_strong_negatives",
}


def pytest_collection_modifyitems(config, items):
    """Tag each collected test with its tier marker based on its module name."""
    for item in items:
        stem = Path(str(item.fspath)).stem
        if stem in _SMOKE_MODULES:
            item.add_marker(pytest.mark.smoke)
        if stem in _SCIENTIFIC_MODULES:
            item.add_marker(pytest.mark.scientific)
