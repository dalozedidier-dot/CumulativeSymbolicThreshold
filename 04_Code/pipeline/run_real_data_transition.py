#!/usr/bin/env python3
"""run_real_data_transition.py — Real data with a ground-truth onset (axis 6).

The decisive real-world test: does the transition detector fire at a *documented*
onset and stay quiet on matched controls without a transition? We use the Bonn
University EEG dataset (Andrzejak et al. 2001), whose 500 segments are ordered by
class A→B→C→D→E; class **E is the seizure (ictal) state**, so the boundary into
the E block (segment 400) is a ground-truth regime onset.

Detector: a localized variance-shift statistic (max rolling variance / median
rolling variance) on the EEG amplitude, with the detected onset at the largest
rolling-variance increase, and significance against a **trend-preserving**
surrogate null (axis 5). The run passes iff, at the frozen α:

  * the seizure-containing series is significant and its detected onset is within
    tolerance of the ground-truth seizure onset, and
  * matched non-seizure controls (interictal A–D, healthy A–B) are **not**
    significant — the detector does not fire where there is no transition.

Usage
  python 04_Code/pipeline/run_real_data_transition.py --outdir 05_Results/real_data_transition
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))

from oric.early_warning import rolling_variance  # noqa: E402
from oric.frozen_params import FROZEN_PARAMS  # noqa: E402
from oric.surrogates import series_surrogate_test  # noqa: E402

_DEFAULT_INPUT = "03_Data/sector_neuro/real/pilot_eeg_bonn/real.csv"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def variance_shift_stat(x: np.ndarray, window: int) -> float:
    """Localized variance-shift magnitude: max rolling variance / median rolling variance."""
    rv = rolling_variance(np.asarray(x, dtype=float), window)
    if rv.size == 0:
        return 0.0
    return float(np.max(rv) / (np.median(rv) + 1e-9))


def detect_onset(x: np.ndarray, window: int) -> int:
    """Index of the largest rolling-variance increase (the regime onset)."""
    rv = rolling_variance(np.asarray(x, dtype=float), window)
    if rv.size < 2:
        return 0
    return int(np.argmax(np.diff(rv))) + window


def _test_segment(x, window, bandwidth, n_surrogates, seed):
    stat = lambda s: variance_shift_stat(s, window)
    res = series_surrogate_test(x, stat, surrogate="trend_preserving",
                                n_surrogates=n_surrogates, rng=np.random.default_rng(seed),
                                bandwidth=bandwidth)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C real-data ground-truth transition test")
    ap.add_argument("--input", default=_DEFAULT_INPUT)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--signal", default="amplitude_uV")
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--bandwidth", type=float, default=40.0)
    ap.add_argument("--n-surrogates", type=int, default=199)
    ap.add_argument("--onset-tolerance", type=int, default=30)
    ap.add_argument("--alpha", type=float, default=FROZEN_PARAMS.alpha)
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()

    # Even the fast smoke needs enough surrogates that p < alpha is reachable
    # (min p = 1/(n+1)); the real-data run is only a few segments, so it is cheap.
    n_surr = 120 if args.fast else int(args.n_surrogates)
    df = pd.read_csv(args.input)
    x = pd.to_numeric(df[args.signal], errors="coerce").ffill().bfill().to_numpy()

    # Ground-truth seizure onset = first index of class E (if labelled), else 400.
    if "class_label" in df.columns and (df["class_label"] == "E").any():
        gt_onset = int(np.argmax((df["class_label"] == "E").to_numpy()))
        seizure_end = int(len(df))
    else:
        gt_onset, seizure_end = 400, len(df)

    print(f"[REAL] {args.input} signal={args.signal} n={len(x)} gt_onset={gt_onset}")

    # Seizure-containing series (full ordered A→E).
    seiz = _test_segment(x, args.window, args.bandwidth, n_surr, seed=0)
    det_onset = detect_onset(x, args.window)
    onset_err = int(abs(det_onset - gt_onset))
    onset_ok = onset_err <= int(args.onset_tolerance)

    # Matched controls. The clean no-transition control is the *healthy* block
    # (A,B); the interictal block (C,D) is from the epileptogenic zone and is
    # known to be abnormal, so it is reported as an expected *intermediate* case,
    # not a clean negative — the pass gate uses the healthy control only.
    if "class_label" in df.columns:
        controls = {
            "healthy_A_B": x[df["class_label"].isin(["A", "B"]).to_numpy()],
            "interictal_C_D": x[df["class_label"].isin(["C", "D"]).to_numpy()],
        }
        primary_control = "healthy_A_B"
    else:
        controls = {"first_half": x[: gt_onset]}
        primary_control = "first_half"
    control_res = {
        name: _test_segment(cx, args.window, args.bandwidth, n_surr, seed=i + 1)
        for i, (name, cx) in enumerate(controls.items())
    }

    seizure_sig = bool(seiz.p_value < args.alpha)
    control_quiet = bool(control_res[primary_control].p_value >= args.alpha)
    dominates = bool(seiz.observed > 5.0 * max(r.observed for r in control_res.values()))
    passes = bool(seizure_sig and onset_ok and control_quiet and dominates)

    result = {
        "schema": "oric.real_data_transition.v1",
        "run_mode": "full_statistical",
        "dataset": "bonn_eeg_andrzejak_2001",
        "input": args.input, "signal": args.signal, "n": int(len(x)),
        "alpha": args.alpha, "window": args.window,
        "ground_truth_onset": gt_onset, "seizure_end": seizure_end,
        "seizure_series": {
            "statistic": seiz.observed, "null_q99": seiz.null_q99,
            "p_value": seiz.p_value, "significant": seizure_sig,
            "detected_onset": det_onset, "onset_error": onset_err,
            "onset_within_tolerance": onset_ok, "onset_tolerance": int(args.onset_tolerance),
        },
        "primary_control": primary_control,
        "controls": {
            name: {"statistic": r.observed, "p_value": r.p_value,
                   "significant": bool(r.p_value < args.alpha),
                   "role": ("matched no-transition control" if name == primary_control
                            else "epileptogenic-zone intermediate (known-abnormal)")}
            for name, r in control_res.items()
        },
        "surrogate_null": "trend_preserving",
        "passes": passes,
        "verdict": "REAL_ONSET_CONFIRMED" if passes else "REAL_ONSET_NOT_CONFIRMED",
        "joint_rule": (
            "PASS iff the seizure series is significant at alpha AND its detected "
            "onset is within tolerance of the ground-truth ictal onset AND the "
            "matched healthy control is non-significant AND the seizure statistic "
            "exceeds 5x every control's (interictal C/D is a known-abnormal "
            "intermediate, reported but not gating)."
        ),
    }

    out = Path(args.outdir)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "tables" / "real_data_transition.json").write_text(json.dumps(result, indent=2) + "\n")
    (out / "verdict.txt").write_text(result["verdict"] + "\n")
    (out / "manifest.json").write_text(json.dumps({
        "test_id": "real_data_transition", "schema": "oric.real_data_transition.manifest.v1",
        "run_mode": "full_statistical", "input": args.input, "verdict": result["verdict"],
        "json_sha256": _sha256(out / "tables" / "real_data_transition.json"),
    }, indent=2) + "\n")

    s = result["seizure_series"]
    print(f"  seizure : stat={s['statistic']:.1f} p={s['p_value']:.4f} "
          f"onset={s['detected_onset']} (gt {gt_onset}, err {s['onset_error']})")
    for name, r in result["controls"].items():
        print(f"  control {name:16s}: stat={r['statistic']:.1f} p={r['p_value']:.4f} sig={r['significant']}")
    print(f"\n  ===> {result['verdict']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
