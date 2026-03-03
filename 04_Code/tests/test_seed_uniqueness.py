"""CI check: per-test seeds must be distinct (no two tests share the same seed value).

Invariant (non-negotiable, ex ante fixed):
- _seed_offsets() defines a unique offset per test (0–8 sequential).
- No two tests may share the same base+offset value for the same base_seed.
- _seed_offsets() is defined in 04_Code/pipeline/run_all_tests.py and imported here.

Also checks:
- Expected canonical test IDs are present.
- test_type values are valid.

Allowed test_type values:
- statistical
- fixed_data
- proof_only
"""

from __future__ import annotations

from typing import Set

from pipeline.run_all_tests import _seed_offsets


def test_offsets_unique_and_sequential() -> None:
    """Offsets must be unique and cover 0..8."""
    offsets = [d["offset"] for d in _seed_offsets()]
    assert len(offsets) == 9, f"Expected 9 offsets, got {len(offsets)}: {offsets}"
    assert len(set(offsets)) == 9, f"Offsets must be unique: {offsets}"
    assert set(offsets) == set(range(9)), (
        f"Offsets must be exactly 0..8, got: {sorted(set(offsets))}"
    )


def test_seeds_distinct_for_any_base() -> None:
    """For any base_seed, base+offset seeds are distinct because offsets are distinct."""
    base_seed = 1234
    seeds = [base_seed + d["offset"] for d in _seed_offsets()]
    assert len(seeds) == len(set(seeds)), f"Seeds must be distinct, got duplicates: {seeds}"


def test_expected_test_ids_present() -> None:
    expected: Set[str] = {
        "T1_noyau_demand_shock",
        "T2_threshold_demo_on_dataset",
        "T3_robustness_on_dataset",
        "T4_symbolic_S_rich_vs_poor_on_C",
        "T5_symbolic_injection_effect_on_C",
        "T6_symbolic_cut_on_C",
        "T7_progressive_S_to_C_threshold",
        "T8_reinjection_recovery_on_C",
        "T9_cross_domain",
    }
    actual = {d["test_id"] for d in _seed_offsets()}
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"Missing test IDs from _seed_offsets(): {missing}"
    assert not extra, f"Unexpected test IDs in _seed_offsets(): {extra}"


def test_test_type_values_valid() -> None:
    """Every entry must have test_type in ('statistical','fixed_data','proof_only')."""
    valid = {"statistical", "fixed_data", "proof_only"}
    for d in _seed_offsets():
        assert d["test_type"] in valid, (
            f"Invalid test_type '{d['test_type']}' for {d['test_id']}. "
            f"Must be one of {valid}."
        )
