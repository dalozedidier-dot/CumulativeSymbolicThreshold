#!/usr/bin/env python3
"""
ORI-C canonical decision protocol runner.

Input:
- runs_summary.csv produced by run_canonical_suite.py, or an equivalent table.

Outputs:
- verdicts_local.csv
- verdicts_global.json
- diagnostics.md

This script implements the normative logic described in:
- 02_Protocol/DECISION_RULES_v2.md
"""
from __future__ import annotations

import sys
from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from oric import PreregSpec


def robust_sd_mad(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    return 1.4826 * mad if mad > 0 else float(np.std(x, ddof=0))


def ci_mean_bootstrap(x: np.ndarray, ci_level: float, B: int, seed: int = 123) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n == 0:
        return float("nan"), float("nan")
    means = []
    for _ in range(B):
        samp = rng.choice(x, size=n, replace=True)
        means.append(float(np.mean(samp)))
    lo = float(np.quantile(means, (1 - ci_level) / 2))
    hi = float(np.quantile(means, 1 - (1 - ci_level) / 2))
    return lo, hi


def quality_gate(df: pd.DataFrame, prereg: PreregSpec) -> Tuple[bool, Dict[str, str]]:
    notes: Dict[str, str] = {}
    if "failed" in df.columns:
        fail_rate = float(df["failed"].fillna(0).mean())
    else:
        fail_rate = 0.0
    notes["failure_rate"] = f"{fail_rate:.3f}"
    if fail_rate >= 0.05:
        notes["gate"] = "FAIL: technical failure rate >= 5%"
        return False, notes

    required = ["V_q05", "A_sigma", "frac_over", "C_end", "S_star_improvement"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        notes["gate"] = f"FAIL: missing columns {missing}"
        return False, notes

    n_valid = int(len(df))
    notes["n_valid"] = str(n_valid)
    if n_valid < prereg.n_min:
        notes["gate"] = f"FAIL: n_valid < n_min ({n_valid} < {prereg.n_min})"
        return False, notes

    notes["gate"] = "PASS"
    return True, notes


def local_verdict(
    effect: float,
    sesoi: float,
    p: float,
    ci_lo: float,
    ci_hi: float,
    power: float,
    prereg: PreregSpec,
    direction: str,
) -> str:
    if power < prereg.power_gate_min:
        return "INDETERMINATE"
    if p > prereg.alpha:
        return "INDETERMINATE"

    if direction == "pos":
        if effect >= sesoi and ci_lo >= 0:
            return "ACCEPT"
        if effect <= -abs(sesoi) and ci_hi <= 0:
            return "REJECT"

    if direction == "neg":
        if effect <= sesoi and ci_hi <= 0:
            return "ACCEPT"
        if effect >= abs(sesoi) and ci_lo >= 0:
            return "REJECT"

    return "INDETERMINATE"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="Path to runs_summary.csv")
    ap.add_argument("--outdir", required=True, help="Output directory for verdicts")
    args = ap.parse_args()

    prereg = PreregSpec()
    prereg.validate()

    runs = pd.read_csv(args.runs)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    ok, gate_notes = quality_gate(runs, prereg)

    diagnostics_md = outdir / "diagnostics.md"
    with diagnostics_md.open("w", encoding="utf-8") as f:
        f.write("# Diagnostics

")
        for k, v in gate_notes.items():
            f.write(f"- {k}: {v}
")

    if not ok:
        verdicts_local = pd.DataFrame(
            [
                {
                    "test": "GLOBAL_GATE",
                    "verdict": "INDETERMINATE",
                    "reason": gate_notes.get("gate", "gate failed"),
                }
            ]
        )
        verdicts_local.to_csv(outdir / "verdicts_local.csv", index=False)
        (outdir / "verdicts_global.json").write_text(
            json.dumps(
                {
                    "ori_core": "INDETERMINATE",
                    "symbolic_layer": "INDETERMINATE",
                    "gate": gate_notes,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 0

    # Minimal local test for this canonical suite.
    # Test 6 uses the piecewise improvement diagnostic on S_star_improvement.
    x = runs["S_star_improvement"].to_numpy(dtype=float)
    effect = float(np.mean(x))
    ci_lo, ci_hi = ci_mean_bootstrap(x, prereg.ci_level, B=prereg.power_bootstrap_B)
    p = float(stats.ttest_1samp(x, 0.0).pvalue)

    # SESOI for S_star improvement is fixed here for the minimal suite.
    # If you want a different SESOI, declare it ex ante and encode it in PreregSpec.
    sesoi_impr = 0.20

    # Power estimate placeholder for the minimal suite.
    # In the full suite, implement bootstrap power for one-sample tests.
    power = 0.80 if abs(effect) >= sesoi_impr else 0.50

    verdict6 = local_verdict(
        effect=effect,
        sesoi=sesoi_impr,
        p=p,
        ci_lo=ci_lo,
        ci_hi=ci_hi,
        power=power,
        prereg=prereg,
        direction="pos",
    )

    verdicts = [
        {
            "test": "T6_S_star_piecewise",
            "effect_mean": effect,
            "ci_lo": ci_lo,
            "ci_hi": ci_hi,
            "p": p,
            "sesoi": sesoi_impr,
            "power_est": power,
            "verdict": verdict6,
        }
    ]

    pd.DataFrame(verdicts).to_csv(outdir / "verdicts_local.csv", index=False)

    ori_core = "INDETERMINATE"
    if verdict6 == "ACCEPT":
        symbolic_layer = "ACCEPT"
    elif verdict6 == "REJECT":
        symbolic_layer = "REJECT"
    else:
        symbolic_layer = "INDETERMINATE"

    (outdir / "verdicts_global.json").write_text(
        json.dumps(
            {
                "ori_core": ori_core,
                "symbolic_layer": symbolic_layer,
                "gate": gate_notes,
                "local": {row["test"]: row["verdict"] for row in verdicts},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
