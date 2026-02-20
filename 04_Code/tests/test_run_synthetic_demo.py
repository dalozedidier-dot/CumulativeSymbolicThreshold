import pandas as pd
import pytest

from pipeline.run_synthetic_demo import Weights, compute_V, detect_threshold


def test_compute_V_simple():
    df = pd.DataFrame(
        {
            "survie": [1.0],
            "energie_nette": [0.6],
            "integrite": [0.7],
            "persistance": [0.6],
        }
    )
    w = Weights()
    v = float(compute_V(df, w).iloc[0])
    assert v == pytest.approx(0.725)


def test_detect_threshold_basic():
    # 10 baseline zeros then 5 ones; baseline window kept in the zero-region,
    # so threshold == 0.0 and the first confirmed m=3 run starts at index 10.
    delta_C = pd.Series([0.0] * 10 + [1.0] * 5)
    idx, thr = detect_threshold(delta_C, k=2.0, m=3, baseline_n=8)
    assert thr == pytest.approx(0.0)
    assert idx == 10
