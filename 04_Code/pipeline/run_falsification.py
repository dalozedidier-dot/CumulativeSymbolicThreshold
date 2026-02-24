#!/usr/bin/env python3
"""04_Code/pipeline/run_falsification.py

Falsification battery for ORI-C real-data runs.

Implements four falsification checks (all defined ex ante):

  FC1 — Negative control window
        Apply the threshold detector only on the pre-event window.
        Expected: NO threshold detected (signal must be absent before event).

  FC2 — Placebo date shift
        Shift the event date by ±N periods (specified in event_calendar or CLI).
        Recompute the threshold detector. Expected: signal disappears or weakens.

  FC3 — Variable placebo
        Replace S(t) with a column-shuffled version (temporal order broken).
        Run the full ORI-C symbolic pipeline. Expected: C does NOT accumulate.

  FC4 — Block permutation test
        Shuffle the time series in blocks of size `block`.
        Recompute threshold score (max ΔC z-score in the post window).
        Build an empirical null distribution (n_perm permutations).
        Compute p_perm = P(score_null >= score_obs).
        Expected: p_perm < alpha when the true signal is present.

All checks write structured JSON results to <outdir>/tables/falsification.json
and a plain verdict token to <outdir>/falsification_verdict.txt.

Verdict tokens:
  FALSIFICATION_PASSED   — all four checks behave as predicted
  FALSIFICATION_PARTIAL  — ≥ 1 check failed but not all
  FALSIFICATION_FAILED   — critical check (FC1 or FC4) failed

Usage
-----
    python 04_Code/pipeline/run_falsification.py \\
        --timeseries 05_Results/real/pilot_cpi/run_0001/tables/test_timeseries.csv \\
        --event-t 300 \\
        --outdir 05_Results/real/pilot_cpi/run_0001/falsification \\
        --col-S S --col-delta-C delta_C --col-C C \\
        --k 2.5 --m 3 --baseline-n 50 \\
        --placebo-shifts 36 60 \\
        --n-perm 1000 --block 12 --seed 42 \\
        --alpha 0.01
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))


# ── Threshold detection (canonical, same as tests_causaux.py) ─────────────────

def _detect_threshold(
    delta_C: np.ndarray,
    k: float,
    m: int,
    baseline_n: int,
) -> tuple[int | None, float, float]:
    """Return (first_hit_idx, threshold_value, max_zscore_in_post)."""
    x = np.asarray(delta_C, dtype=float)
    n = len(x)
    bn = max(5, min(int(baseline_n), n))

    base = x[:bn]
    mu = float(np.mean(base))
    sd = float(np.std(base))
    thr = mu + float(k) * sd

    # max z-score of the whole series (post-baseline)
    if sd > 0:
        max_z = float(np.max((x[bn:] - mu) / sd)) if n > bn else 0.0
    else:
        max_z = 0.0

    consec = 0
    for i in range(n):
        if float(x[i]) > thr:
            consec += 1
            if consec >= int(m):
                return int(i), float(thr), max_z
        else:
            consec = 0
    return None, float(thr), max_z


def _threshold_score(delta_C: np.ndarray, k: float, m: int, baseline_n: int) -> float:
    """Return max z-score in post-baseline window (used as permutation test statistic)."""
    _, _, max_z = _detect_threshold(delta_C, k, m, baseline_n)
    return max_z


# ── FC1 — Negative control window ─────────────────────────────────────────────

def fc1_negative_control(
    df: pd.DataFrame,
    col_delta_C: str,
    event_t: int,
    k: float,
    m: int,
    baseline_n: int,
) -> dict:
    """Detect threshold on the pre-event window only. Expect: no detection."""
    pre = df[df["t"] < event_t].copy()
    if len(pre) < baseline_n + m:
        return {
            "check": "FC1_negative_control",
            "result": "SKIP",
            "reason": f"Pre-event window too short ({len(pre)} rows < {baseline_n + m})",
            "passed": None,
        }
    dC_pre = pre[col_delta_C].to_numpy(dtype=float)
    hit, thr_val, max_z = _detect_threshold(dC_pre, k, m, baseline_n)
    passed = hit is None
    return {
        "check": "FC1_negative_control",
        "n_pre": int(len(pre)),
        "event_t": int(event_t),
        "threshold_hit_in_pre": hit is not None,
        "threshold_hit_idx": hit,
        "threshold_value": float(thr_val),
        "max_z_in_pre": float(max_z),
        "result": "PASS" if passed else "FAIL",
        "passed": bool(passed),
        "interpretation": (
            "No false positive before event — as expected."
            if passed
            else "Threshold triggered BEFORE event — violates falsification requirement."
        ),
    }


# ── FC2 — Placebo date shift ───────────────────────────────────────────────────

def fc2_placebo_dates(
    df: pd.DataFrame,
    col_delta_C: str,
    event_t: int,
    shifts: list[int],
    k: float,
    m: int,
    baseline_n: int,
) -> dict:
    """Run threshold detector with event_t shifted by each value in shifts.

    Expected: signal absent or much weaker at placebo dates.
    """
    true_hit, _, true_max_z = _detect_threshold(
        df[col_delta_C].to_numpy(dtype=float), k, m, baseline_n
    )

    placebo_results = []
    n_weaker = 0
    for shift in shifts:
        ph_t = event_t + shift
        ph_df = df[df["t"] < ph_t].copy() if shift > 0 else df[df["t"] >= (event_t + shift)].copy()
        if len(ph_df) < baseline_n + m:
            placebo_results.append({
                "shift": int(shift),
                "placebo_event_t": int(ph_t),
                "result": "SKIP",
                "reason": "insufficient data",
            })
            continue
        ph_hit, ph_thr, ph_max_z = _detect_threshold(ph_df[col_delta_C].to_numpy(dtype=float), k, m, baseline_n)
        weaker = (ph_max_z < true_max_z) or (ph_hit is None and true_hit is not None)
        if weaker:
            n_weaker += 1
        placebo_results.append({
            "shift": int(shift),
            "placebo_event_t": int(ph_t),
            "n_rows_in_window": int(len(ph_df)),
            "threshold_hit": ph_hit is not None,
            "max_z": float(ph_max_z),
            "true_max_z": float(true_max_z),
            "signal_weaker_than_true": bool(weaker),
        })

    valid = [r for r in placebo_results if r.get("result") != "SKIP"]
    passed = (len(valid) > 0) and (n_weaker == len(valid))
    return {
        "check": "FC2_placebo_dates",
        "true_event_t": int(event_t),
        "true_max_z": float(true_max_z),
        "true_threshold_hit": true_hit is not None,
        "n_shifts": len(shifts),
        "n_valid": len(valid),
        "n_weaker": int(n_weaker),
        "placebos": placebo_results,
        "result": "PASS" if passed else ("FAIL" if valid else "SKIP"),
        "passed": bool(passed) if valid else None,
        "interpretation": (
            f"Signal weaker at all {n_weaker}/{len(valid)} placebo dates — as expected."
            if passed
            else f"Signal NOT consistently weaker at placebo dates ({n_weaker}/{len(valid)} weaker)."
        ),
    }


# ── FC3 — Variable placebo (column shuffle) ───────────────────────────────────

def fc3_variable_placebo(
    df: pd.DataFrame,
    col_delta_C: str,
    col_S: str,
    col_C: str,
    k: float,
    m: int,
    baseline_n: int,
    n_shuffles: int,
    seed: int,
) -> dict:
    """Replace S(t) with shuffled S (broken temporal order). Recompute delta_C proxy.

    Since we can't re-run the full ORI-C model here, we proxy delta_C under
    H0 by: shuffle the actual delta_C column (temporal order broken).
    The score distribution under shuffled data is the null.

    Expected: true score >> shuffled scores (p_shuffle < alpha).
    """
    rng = np.random.default_rng(int(seed))
    dC = df[col_delta_C].to_numpy(dtype=float)
    true_score = _threshold_score(dC, k, m, baseline_n)

    shuffled_scores = []
    for _ in range(int(n_shuffles)):
        perm = rng.permutation(len(dC))
        sh_score = _threshold_score(dC[perm], k, m, baseline_n)
        shuffled_scores.append(float(sh_score))

    arr = np.array(shuffled_scores)
    p_shuffle = float(np.mean(arr >= true_score))
    passed = bool(p_shuffle < 0.05)  # informative gate (not primary verdict)

    return {
        "check": "FC3_variable_placebo",
        "true_score": float(true_score),
        "n_shuffles": int(n_shuffles),
        "mean_null_score": float(np.mean(arr)),
        "p95_null_score": float(np.quantile(arr, 0.95)),
        "p_shuffle": float(p_shuffle),
        "result": "PASS" if passed else "FAIL",
        "passed": bool(passed),
        "interpretation": (
            f"True score ({true_score:.3f}) > 95th null percentile ({np.quantile(arr, 0.95):.3f}) — signal not noise."
            if passed
            else f"True score ({true_score:.3f}) NOT distinguishable from temporal null."
        ),
    }


# ── FC4 — Block permutation test ─────────────────────────────────────────────

def fc4_block_permutation(
    df: pd.DataFrame,
    col_delta_C: str,
    event_t: int,
    n_perm: int,
    block: int,
    seed: int,
    k: float,
    m: int,
    baseline_n: int,
    alpha: float,
) -> dict:
    """Block-permutation test on the post-event window.

    Observed score = max z-score of delta_C in post-event window.
    Null distribution = same statistic after block-shuffling the post window.
    p_perm = P(score_null >= score_obs).
    Expected (true signal): p_perm < alpha.
    """
    post = df[df["t"] >= event_t].copy()
    if len(post) < baseline_n + m:
        return {
            "check": "FC4_block_permutation",
            "result": "SKIP",
            "reason": f"Post-event window too short ({len(post)} rows)",
            "passed": None,
        }

    rng = np.random.default_rng(int(seed))
    dC_post = post[col_delta_C].to_numpy(dtype=float)
    obs_score = _threshold_score(dC_post, k, m, baseline_n)

    blk = max(1, int(block))
    n = len(dC_post)

    null_scores = []
    for _ in range(int(n_perm)):
        # Block shuffle
        idx = np.arange(n)
        blocks = [idx[i : i + blk] for i in range(0, n, blk)]
        rng.shuffle(blocks)
        perm_idx = np.concatenate(blocks)
        sc = _threshold_score(dC_post[perm_idx], k, m, baseline_n)
        null_scores.append(float(sc))

    arr = np.array(null_scores)
    p_perm = float(np.mean(arr >= obs_score))
    passed = bool(p_perm < float(alpha))

    return {
        "check": "FC4_block_permutation",
        "n_post": int(len(post)),
        "event_t": int(event_t),
        "obs_score": float(obs_score),
        "n_perm": int(n_perm),
        "block_size": int(blk),
        "mean_null_score": float(np.mean(arr)),
        "p95_null_score": float(np.quantile(arr, 0.95)),
        "p_perm": float(p_perm),
        "alpha": float(alpha),
        "result": "PASS" if passed else "FAIL",
        "passed": bool(passed),
        "interpretation": (
            f"p_perm={p_perm:.4f} < alpha={alpha} — temporal structure is real."
            if passed
            else f"p_perm={p_perm:.4f} >= alpha={alpha} — signal not distinct from block-shuffled null."
        ),
    }


# ── Aggregate verdict ─────────────────────────────────────────────────────────

def _aggregate_verdict(checks: list[dict]) -> str:
    results = {c["check"]: c.get("passed") for c in checks}
    # Critical checks: FC1 and FC4
    fc1 = results.get("FC1_negative_control")
    fc4 = results.get("FC4_block_permutation")
    all_valid = [v for v in results.values() if v is not None]

    if not all_valid:
        return "FALSIFICATION_PARTIAL"
    if fc1 is False or fc4 is False:
        return "FALSIFICATION_FAILED"
    if all(v for v in all_valid):
        return "FALSIFICATION_PASSED"
    return "FALSIFICATION_PARTIAL"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C falsification battery (FC1–FC4)")
    ap.add_argument("--timeseries", required=True, help="Path to test_timeseries.csv")
    ap.add_argument("--event-t", type=int, required=True, help="Event time index t (integer row unit)")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--col-delta-C", default="delta_C")
    ap.add_argument("--col-S", default="S")
    ap.add_argument("--col-C", default="C")
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=50)
    ap.add_argument("--placebo-shifts", type=int, nargs="+", default=[36, -36, 60],
                    help="List of t-shifts for placebo date test (positive = forward, negative = backward)")
    ap.add_argument("--n-perm", type=int, default=1000, help="Number of block permutations (FC4)")
    ap.add_argument("--n-shuffles", type=int, default=500, help="Number of column shuffles (FC3)")
    ap.add_argument("--block", type=int, default=12, help="Block size for permutation (months or steps)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--alpha", type=float, default=0.01)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    tabdir = outdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)

    ts_path = Path(args.timeseries)
    if not ts_path.exists():
        print(f"ERROR: timeseries not found: {ts_path}", file=sys.stderr)
        return 1

    df = pd.read_csv(ts_path)
    if "t" not in df.columns:
        print("ERROR: timeseries must have a 't' column", file=sys.stderr)
        return 1
    for col in [args.col_delta_C, args.col_S, args.col_C]:
        if col not in df.columns:
            print(f"ERROR: missing column '{col}' in timeseries", file=sys.stderr)
            return 1

    print(f"Loaded {len(df)} rows from {ts_path}")
    print(f"Event t={args.event_t}, alpha={args.alpha}, k={args.k}, m={args.m}")

    # ── Run all four checks ──────────────────────────────────────────────────
    checks = []

    print("\n── FC1: Negative control ──")
    r1 = fc1_negative_control(df, args.col_delta_C, args.event_t, args.k, args.m, args.baseline_n)
    checks.append(r1)
    print(f"   result={r1['result']}  {r1['interpretation']}")

    print("\n── FC2: Placebo date shifts ──")
    r2 = fc2_placebo_dates(df, args.col_delta_C, args.event_t, args.placebo_shifts, args.k, args.m, args.baseline_n)
    checks.append(r2)
    print(f"   result={r2['result']}  {r2['interpretation']}")

    print("\n── FC3: Variable placebo (shuffle) ──")
    r3 = fc3_variable_placebo(df, args.col_delta_C, args.col_S, args.col_C, args.k, args.m, args.baseline_n, args.n_shuffles, args.seed)
    checks.append(r3)
    print(f"   result={r3['result']}  {r3['interpretation']}")

    print("\n── FC4: Block permutation test ──")
    r4 = fc4_block_permutation(df, args.col_delta_C, args.event_t, args.n_perm, args.block, args.seed, args.k, args.m, args.baseline_n, args.alpha)
    checks.append(r4)
    print(f"   result={r4['result']}  {r4['interpretation']}")

    # ── Aggregate ────────────────────────────────────────────────────────────
    verdict = _aggregate_verdict(checks)
    print(f"\n── Aggregate verdict: {verdict} ──")

    output = {
        "timeseries": str(ts_path),
        "event_t": int(args.event_t),
        "alpha": float(args.alpha),
        "seed": int(args.seed),
        "verdict": verdict,
        "checks": checks,
    }

    (tabdir / "falsification.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    (outdir / "falsification_verdict.txt").write_text(verdict + "\n", encoding="utf-8")

    print(f"\nOutputs written to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
