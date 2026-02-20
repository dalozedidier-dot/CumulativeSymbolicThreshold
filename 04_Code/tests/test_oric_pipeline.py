import pandas as pd

from pipeline.ori_c_pipeline import ORICConfig, run_oric


def test_oric_runs_and_outputs_columns():
    df = run_oric(ORICConfig(seed=1, n_steps=20, intervention="none"))
    expected = {"t", "O", "R", "I", "demand", "Cap", "Sigma", "S", "C", "delta_C", "V", "intervention", "threshold_hit"}
    assert expected.issubset(set(df.columns))
    assert len(df) == 20


def test_symbolic_cut_reduces_post_C_vs_control():
    # symbolic_cut reduces S each step → less C_beta*S input → C accumulates slower.
    # V is independent of S (V depends on Sigma/Cap), so the causal effect of a
    # symbolic cut is visible on C, not on V.
    cfg_control = ORICConfig(seed=2, n_steps=100, intervention="none", intervention_point=70)
    cfg_cut = ORICConfig(seed=2, n_steps=100, intervention="symbolic_cut", intervention_point=70)

    df_control = run_oric(cfg_control)
    df_cut = run_oric(cfg_cut)

    C_post_control = float(df_control[(df_control["t"] >= 80) & (df_control["t"] <= 95)]["C"].mean())
    C_post_cut = float(df_cut[(df_cut["t"] >= 80) & (df_cut["t"] <= 95)]["C"].mean())

    assert C_post_cut < C_post_control
