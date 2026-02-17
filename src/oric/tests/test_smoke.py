import numpy as np
import pandas as pd

from oric.ori_core import compute_cap_projection, compute_sigma, compute_viability
from oric.symbolic import compute_stock_S, compute_order_C, detect_s_star_piecewise
from oric.prereg import PreregSpec


def test_smoke_core_and_symbolic():
    df = pd.DataFrame({
        "O": [0.8, 0.8, 0.8],
        "R": [0.7, 0.7, 0.7],
        "I": [0.6, 0.6, 0.6],
        "demande_env": [0.2, 0.4, 0.5],
        "survie": [0.9, 0.8, 0.7],
        "energie_nette": [0.9, 0.8, 0.7],
        "integrite": [0.9, 0.8, 0.7],
        "persistance": [0.9, 0.8, 0.7],
        "repertoire": [0.2, 0.3, 0.4],
        "codification": [0.2, 0.3, 0.4],
        "densite_transmission": [0.2, 0.3, 0.4],
        "fidelite": [0.2, 0.3, 0.4],
    })
    prereg = PreregSpec()
    cap = compute_cap_projection(df["O"], df["R"], df["I"], form=prereg.cap_form)
    sigma = compute_sigma(df["demande_env"], cap, form=prereg.sigma_form)
    v = compute_viability(df, prereg.omega_v)
    s = compute_stock_S(df, prereg.alpha_s)
    tmp = df.copy()
    tmp["V"] = v
    tmp["S"] = s
    c = compute_order_C(tmp)
    diag = detect_s_star_piecewise(s.to_numpy(), c.to_numpy())

    assert cap.shape[0] == 3
    assert sigma.min() >= 0
    assert 0 <= v.min() <= 1
    assert 0 <= s.min() <= 1
    assert "S_star" in diag and "improvement" in diag
