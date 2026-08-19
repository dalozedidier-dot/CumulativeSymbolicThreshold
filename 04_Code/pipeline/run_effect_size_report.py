#!/usr/bin/env python3
"""run_effect_size_report.py — Effect size vs SESOI + power for a real pilot.

Reports the ORI-C order variable C post-threshold vs pre-threshold as an
effect-size-vs-SESOI decision with a 99% CI and achieved power — the correct way
to report a borderline-powered real-data result (never the p-value).

Usage
  python 04_Code/pipeline/run_effect_size_report.py \
    --input 03_Data/sector_cosmo/real/pilot_pantheon_sn/real_densified.csv \
    --outdir 05_Results/effect_size/pantheon_sn
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_HERE))

from ori_c_pipeline import ORICConfig, _detect_threshold, run_oric_from_observations  # noqa: E402

from oric.effect_size import effect_size_report  # noqa: E402
from oric.frozen_params import FROZEN_PARAMS  # noqa: E402


def _load(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    missing = [c for c in ("O", "R", "I") if c not in df.columns]
    if missing:
        raise SystemExit(f"input {input_csv} missing required columns: {missing}")
    if "t" not in df.columns:
        df.insert(0, "t", np.arange(len(df)))
    return df


def _pre_post(C: np.ndarray, thr_idx: int | None, win: int) -> tuple[np.ndarray, np.ndarray, str]:
    """Pre/post windows of C around the threshold, or first/last 40% if no hit."""
    n = C.size
    if thr_idx is not None and 0 < thr_idx < n:
        pre = C[max(0, thr_idx - win):thr_idx]
        post = C[thr_idx:min(n, thr_idx + win)]
        return pre, post, f"around detected threshold @ idx {thr_idx} (±{win})"
    cut = int(0.40 * n)
    return C[:cut], C[n - cut:], "first vs last 40% (no sustained threshold detected)"


def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C effect-size vs SESOI + power report")
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=30)
    args = ap.parse_args()

    out = Path(args.outdir)
    (out / "tables").mkdir(parents=True, exist_ok=True)

    df = _load(Path(args.input))
    cfg = ORICConfig(seed=args.seed, n_steps=len(df), intervention="none",
                     k=args.k, m=args.m, baseline_n=args.baseline_n)
    run = run_oric_from_observations(df, cfg)
    C = run["C"].to_numpy()
    thr_idx, _ = _detect_threshold(run["delta_C"], cfg.k, cfg.m, cfg.baseline_n)

    win = max(args.baseline_n, len(df) // 4)
    pre, post, split_desc = _pre_post(C, thr_idx, win)

    rep = effect_size_report(
        pre, post,
        sesoi_robust_sd=FROZEN_PARAMS.sesoi_c_robust_sd,
        alpha=FROZEN_PARAMS.alpha,
        ci_level=FROZEN_PARAMS.ci_level,
        power_gate=FROZEN_PARAMS.power_gate_min,
        rng=np.random.default_rng(args.seed),
    )
    payload = rep.to_dict()
    payload["input"] = str(args.input)
    payload["n_rows"] = int(len(df))
    payload["split"] = split_desc
    payload["threshold_detected"] = bool(thr_idx is not None)

    with open(out / "tables" / "effect_size.json", "w") as f:
        json.dump(payload, f, indent=2)
    (out / "verdict.txt").write_text(rep.verdict)

    print(f"\n[EFFECT] {args.input}  ({split_desc})")
    print(f"  standardised effect = {rep.standardised_effect:+.3f} robust-SD "
          f"(99% CI [{rep.ci_low:+.3f}, {rep.ci_high:+.3f}])  SESOI = {rep.sesoi_robust_sd}")
    print(f"  Hedges g = {rep.hedges_g:+.3f}")
    print(f"  power@observed = {rep.achieved_power_at_observed:.2f}  "
          f"power@SESOI = {rep.achieved_power_at_sesoi:.2f}  gate = {rep.power_gate}")
    print(f"  VERDICT = {rep.verdict}  ({rep.note})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
