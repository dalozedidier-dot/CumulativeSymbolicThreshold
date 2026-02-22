"""CI check: per-test seeds must be distinct (no two tests share the same seed value).

Invariant (non-negotiable, ex ante fixed):
- _seed_offsets() defines a unique offset per test (0–7 sequential).
- No two tests may share the same base+offset value for the default base_seed.
- "distinct" ≠ "statistically independent" — independence is NOT claimed.

This test fails the CI if:
  1. Two tests share the same offset (collision in the offset table).
  2. The offset table does not cover exactly 8 tests.
  3. Any computed seed (base=1234) is duplicated.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure pipeline module is importable
_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from pipeline.run_all_tests import _seed_offsets


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_exactly_8_tests_defined() -> None:
    """The canonical suite has exactly 8 tests (T1–T8)."""
    offsets = _seed_offsets()
    assert len(offsets) == 8, (
        f"Expected 8 tests in _seed_offsets(), got {len(offsets)}. "
        f"Test IDs: {[d['test_id'] for d in offsets]}"
    )


def test_all_offsets_distinct() -> None:
    """All per-test offsets must be distinct (no two tests share an offset)."""
    offsets = _seed_offsets()
    offset_values = [d["offset"] for d in offsets]
    duplicates = [v for v in offset_values if offset_values.count(v) > 1]
    assert len(duplicates) == 0, (
        f"Non-unique offsets detected: {sorted(set(duplicates))}. "
        f"Full offset table: {[(d['test_id'], d['offset']) for d in offsets]}"
    )


def test_seeds_distinct_for_default_base() -> None:
    """Computed seeds must all be distinct for the default base_seed=1234."""
    base = 1234
    offsets = _seed_offsets()
    seeds = [base + d["offset"] for d in offsets]
    duplicates = [s for s in seeds if seeds.count(s) > 1]
    assert len(duplicates) == 0, (
        f"Non-unique seeds for base={base}: duplicated values {sorted(set(duplicates))}. "
        f"Full seed table: {[(d['test_id'], base + d['offset']) for d in offsets]}"
    )


def test_all_test_ids_present() -> None:
    """All canonical test IDs must appear in the offset table."""
    expected = {
        "T1_noyau_demand_shock",
        "T2_threshold_demo_on_dataset",
        "T3_robustness_on_dataset",
        "T4_symbolic_S_rich_vs_poor_on_C",
        "T5_symbolic_injection_effect_on_C",
        "T6_symbolic_cut_on_C",
        "T7_progressive_S_to_C_threshold",
        "T8_reinjection_recovery_on_C",
    }
    actual = {d["test_id"] for d in _seed_offsets()}
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"Missing test IDs from _seed_offsets(): {missing}"
    assert not extra, f"Unexpected test IDs in _seed_offsets(): {extra}"


def test_test_type_values_valid() -> None:
    """Every entry must have test_type in ('statistical', 'fixed_data')."""
    valid = {"statistical", "fixed_data"}
    for d in _seed_offsets():
        assert d["test_type"] in valid, (
            f"Invalid test_type '{d['test_type']}' for {d['test_id']}. "
            f"Must be one of {valid}."
        )
