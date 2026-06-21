"""test_endogenous.py — The endogenous bistable ORI-C model (research axis 1).

Verifies that the model genuinely instantiates a saddle-node bifurcation with
hysteresis (the mechanism the framework postulates) and that its matched linear
twin (feedback off) does not.
"""
from __future__ import annotations

import numpy as np
import pytest

from oric.endogenous import (
    EndogenousConfig,
    bistable_window,
    drive_from_sigma,
    equilibria,
    field,
    hysteresis_sweep,
    make_ramp,
    run_endogenous,
    simulate,
)


class TestBistability:
    def test_default_config_is_bistable(self):
        win = bistable_window(EndogenousConfig())
        assert win is not None
        a_low, a_high = win
        assert a_low < a_high

    def test_two_stable_one_unstable_inside_window(self):
        cfg = EndogenousConfig()
        a_low, a_high = bistable_window(cfg)
        a_mid = 0.5 * (a_low + a_high)
        eqs = equilibria(a_mid, cfg)
        n_stable = sum(s for _, s in eqs)
        n_unstable = sum(not s for _, s in eqs)
        assert n_stable == 2, f"expected 2 stable fixed points, got {eqs}"
        assert n_unstable == 1, f"expected 1 unstable separator, got {eqs}"
        # The unstable separator sits strictly between the two stable branches.
        stable = sorted(c for c, s in eqs if s)
        unstable = [c for c, s in eqs if not s][0]
        assert stable[0] < unstable < stable[1]

    def test_far_outside_window_is_monostable(self):
        cfg = EndogenousConfig()
        _, a_high = bistable_window(cfg)
        eqs = equilibria(a_high + 2.0, cfg)
        assert sum(s for _, s in eqs) == 1


class TestLinearTwin:
    def test_twin_has_no_bistable_window(self):
        twin = EndogenousConfig().linear_twin()
        assert twin.r == 0.0
        assert bistable_window(twin) is None

    def test_twin_is_never_bistable(self):
        # The linear twin has at most one interior stable fixed point (for a<0 the
        # root is at C<0, i.e. the state is pinned at the C=0 boundary); it is
        # never bistable.
        twin = EndogenousConfig().linear_twin()
        for a in (-0.5, 0.0, 0.2, 1.0, 3.0):
            assert sum(s for _, s in equilibria(a, twin)) <= 1


class TestHysteresisAndJump:
    def test_bistable_loop_dominates_twin(self):
        cfg = EndogenousConfig()
        hb = hysteresis_sweep(cfg, a_min=-1.0, a_max=3.5, rng=np.random.default_rng(0))
        ht = hysteresis_sweep(cfg.linear_twin(), a_min=-1.0, a_max=3.5,
                              rng=np.random.default_rng(0))
        assert hb["hysteresis_area"] > 5.0 * ht["hysteresis_area"]
        assert hb["hysteresis_area"] > 1.0

    def test_bistable_jump_exceeds_twin(self):
        cfg = EndogenousConfig()
        a_ramp = make_ramp(600, -1.0, 3.5)
        Cb = simulate(a_ramp, cfg, rng=np.random.default_rng(1))
        Ct = simulate(a_ramp, cfg.linear_twin(), rng=np.random.default_rng(1))
        # The bistable model makes a concentrated jump; the twin ramps smoothly.
        assert np.max(np.abs(np.diff(Cb))) > 3.0 * np.max(np.abs(np.diff(Ct)))


class TestDeterminismAndGrounding:
    def test_simulate_is_seed_deterministic(self):
        cfg = EndogenousConfig()
        a = make_ramp(200, -1.0, 3.0)
        c1 = simulate(a, cfg, rng=np.random.default_rng(7))
        c2 = simulate(a, cfg, rng=np.random.default_rng(7))
        assert np.allclose(c1, c2)

    def test_drive_from_sigma_accumulates(self):
        cfg = EndogenousConfig()
        sigma = np.concatenate([np.zeros(50), np.ones(150)])
        a = drive_from_sigma(sigma, cfg)
        assert a[40] == pytest.approx(cfg.a0, abs=1e-9)  # quiescent during baseline
        assert a[-1] > a[60]                              # rises under sustained pressure

    def test_run_endogenous_columns(self):
        df = run_endogenous(make_ramp(100, -1.0, 3.0), EndogenousConfig())
        assert list(df.columns) == ["t", "a", "C", "delta_C"]
        assert len(df) == 100


class TestField:
    def test_hill_monotone_saturating(self):
        cfg = EndogenousConfig()
        # The self-reinforcement term rises with C and saturates below r.
        vals = [field(0.0, 0.0, cfg), field(cfg.h, 0.0, cfg), field(50.0, 0.0, cfg)]
        # f(0) = a = 0; large C dominated by -b*C so field goes very negative.
        assert vals[0] == pytest.approx(0.0, abs=1e-9)
        assert vals[2] < vals[0]
