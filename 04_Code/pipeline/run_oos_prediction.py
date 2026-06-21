#!/usr/bin/env python3
"""run_oos_prediction.py — Out-of-sample directional prediction skill (axis 3).

Honest replacement for the trend-confounded T3. For each of N matched
(bistable, linear-twin) replicates we observe only the run-up *before* the
transition (up to ``jump − lead``), predict from that window alone whether a
localized regime change is coming (trend-preserving CSD surrogate null, not
"C keeps rising"), and score against the held-out truth. The twin has no
transition, so it tests the false-alarm rate.

We report the confusion matrix (TPR over bistable, FPR over twin) and a one-sided
Fisher exact test that the predictor has skill above chance. Per-trajectory CSD
prediction is known to be modest-power with short lead time (Boettiger & Hastings
2012); the verdict here is whether the *directional skill* is positive and
specific, not whether every single transition is caught.

Usage
  python 04_Code/pipeline/run_oos_prediction.py \
    --outdir 05_Results/oos_prediction --n-replicates 50 --lead 60
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))

from oric.early_warning import find_jump  # noqa: E402
from oric.endogenous import EndogenousConfig, matched_fold_pair  # noqa: E402
from oric.frozen_params import FROZEN_PARAMS  # noqa: E402
from oric.oos_prediction import predict_transition, score_prediction  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C out-of-sample transition prediction")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--n-replicates", type=int, default=FROZEN_PARAMS.n_replicates)
    ap.add_argument("--n-surrogates", type=int, default=99)
    ap.add_argument("--n-steps", type=int, default=1500)
    ap.add_argument("--noise-sd", type=float, default=0.05)
    ap.add_argument("--lead", type=int, default=60, help="hold-out lead before the jump")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--seed-base", type=int, default=FROZEN_PARAMS.seed_base)
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()

    N = 10 if args.fast else int(args.n_replicates)
    n_surr = 25 if args.fast else int(args.n_surrogates)
    cfg = EndogenousConfig(noise_sd=float(args.noise_sd))

    print(f"[OOS] N={N} steps={args.n_steps} lead={args.lead} surrogates={n_surr}")
    tp = fp = valid = 0
    timing_errors: list[int] = []
    for i in range(N):
        seed = int(args.seed_base) + i
        db, dt = matched_fold_pair(cfg, n=int(args.n_steps), cross=True, seed=seed)
        Cb, Ct = db["C"].to_numpy(), dt["C"].to_numpy()
        jb = find_jump(Cb)
        t_obs = jb - int(args.lead)
        if t_obs < int(args.n_steps) // 4:          # need enough run-up to observe
            continue
        valid += 1
        pb = predict_transition(Cb[:t_obs], n_surrogates=n_surr, alpha=args.alpha,
                                rng=np.random.default_rng(seed + 30_000))
        pt = predict_transition(Ct[:t_obs], n_surrogates=n_surr, alpha=args.alpha,
                                rng=np.random.default_rng(seed + 40_000))
        sb = score_prediction(pb, jb, timing_tolerance=500)
        st = score_prediction(pt, None)
        tp += sb.outcome == "hit"
        fp += st.outcome == "false_alarm"
        if sb.outcome == "hit" and sb.timing_error is not None:
            timing_errors.append(sb.timing_error)
        if (i + 1) % 10 == 0:
            print(f"  ... {i + 1}/{N}")

    tpr = tp / valid if valid else 0.0
    fpr = fp / valid if valid else 0.0
    _, fisher_p = stats.fisher_exact([[tp, valid - tp], [fp, valid - fp]], alternative="greater")
    skill = bool(fisher_p < 0.05 and tpr > fpr)

    result = {
        "schema": "oric.oos_prediction.v1",
        "run_mode": "full_statistical",
        "model": "endogenous_bistable",
        "n_replicates": N, "n_valid": valid, "n_surrogates": n_surr,
        "lead": int(args.lead), "alpha": args.alpha, "seed_base": int(args.seed_base),
        "predictor": "trend_preserving_csd_surrogate_null (localized regime change, not 'C rises')",
        "confusion": {
            "bistable_tpr": tpr, "twin_fpr": fpr,
            "n_hits": int(tp), "n_false_alarms": int(fp),
        },
        "fisher_exact_p_skill_above_chance": float(fisher_p),
        "median_timing_error": (float(np.median(timing_errors)) if timing_errors else None),
        "has_directional_skill": skill,
        "verdict": "OOS_SKILL_DEMONSTRATED" if skill else "OOS_SKILL_INCONCLUSIVE",
        "note": (
            "Per-trajectory CSD prediction is modest-power with short lead "
            "(Boettiger & Hastings 2012); the claim is positive, specific "
            "directional skill, not catching every transition."
        ),
    }

    out = Path(args.outdir)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "tables" / "oos_prediction.json").write_text(json.dumps(result, indent=2) + "\n")
    (out / "verdict.txt").write_text(result["verdict"] + "\n")
    (out / "manifest.json").write_text(json.dumps({
        "test_id": "oos_prediction", "schema": "oric.oos_prediction.manifest.v1",
        "run_mode": "full_statistical", "n_replicates": N, "lead": int(args.lead),
        "verdict": result["verdict"],
        "json_sha256": _sha256(out / "tables" / "oos_prediction.json"),
    }, indent=2) + "\n")

    print(f"\n  TPR (bistable) / FPR (twin) : {tpr:.2f} / {fpr:.2f}  (n_valid={valid})")
    print(f"  Fisher exact p (skill>chance): {fisher_p:.4f}")
    print(f"\n  ===> {result['verdict']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
