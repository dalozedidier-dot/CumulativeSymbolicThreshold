import json

import pandas as pd

from oric.cap_robustness import (
    CANONICAL_CAP_FORMS,
    CapRobustnessSpec,
    compute_cap_variants,
    summarize_cap_robustness,
)
from oric.ori_core import compute_cap_projection


def _df(n: int = 40) -> pd.DataFrame:
    x = [0.72 + 0.002 * i for i in range(n)]
    return pd.DataFrame(
        {
            "O": x,
            "R": [0.68 + 0.001 * i for i in range(n)],
            "I": [0.64 + 0.0015 * i for i in range(n)],
            "demande_env": [0.42 + 0.004 * i for i in range(n)],
        }
    )


def test_compute_cap_projection_min_form():
    s = pd.Series([0.8, 0.2])
    r = pd.Series([0.7, 0.9])
    i = pd.Series([0.6, 0.4])
    cap = compute_cap_projection(s, r, i, form="min")
    assert cap.tolist() == [0.6, 0.2]


def test_compute_cap_variants_contains_canonical_forms():
    caps = compute_cap_variants(_df(), forms=CANONICAL_CAP_FORMS)
    assert list(caps.columns) == list(CANONICAL_CAP_FORMS)
    assert caps.notna().all().all()


def test_cap_robustness_report_shape():
    report = summarize_cap_robustness(
        _df(),
        spec=CapRobustnessSpec(primary_form="product", forms=CANONICAL_CAP_FORMS),
    )
    assert report["primary_form"] == "product"
    assert report["verdict"] in {"CAP_ROBUST", "CAP_SPEC_SENSITIVE"}
    assert "forms_summary" in report
    assert "comparisons" in report
    assert set(report["forms_summary"]) == set(CANONICAL_CAP_FORMS)
    assert set(report["comparisons"]) == set(CANONICAL_CAP_FORMS) - {"product"}


def test_cap_robustness_json_serializable():
    report = summarize_cap_robustness(_df())
    dumped = json.dumps(report)
    assert "stable_across_specs" in dumped
