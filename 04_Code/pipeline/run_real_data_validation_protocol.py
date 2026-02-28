#!/usr/bin/env python3
"""04_Code/pipeline/run_real_data_validation_protocol.py

Real-data validation protocol for ORI-C canonical real-data analysis.

Protocol design (Three-dataset × Two-stress-tests)
---------------------------------------------------
For a real dataset to be considered "robustly validated" three conditions must hold:

  C1. TRANSITION detected with stability >= STABILITY_MIN on the test dataset.
  C2. STABLE control (first PRE_FRAC of test rows) does NOT detect a threshold
      with rate >= STABLE_MIN (i.e. the detector is specific, not over-triggered).
  C3. PLACEBO (cyclic shift of the test series) does NOT detect a threshold
      with rate >= PLACEBO_MIN.

Two stress tests per dataset
-----------------------------
  A. Window sensitivity:  N_WINDOW_VARIANTS configurations of (pre_horizon, post_horizon).
     Tests that the verdict is robust to ±1 to ±2x changes in analysis window.
     Five default variants: narrow / medium / default / wide_pre / wide_post.

  B. Subsample stability: N_BOOT random draws of 80% of rows (maintaining temporal order).
     Tests that the verdict does not depend on the specific time points included.
     Stability = fraction of subsamples whose verdict agrees with the full-series verdict.

Dataset generation
------------------
  test       : the input CSV as-is (the "plausible transition" dataset)
  stable     : rows 0 .. floor(N * PRE_FRAC) — the pre-transition regime only
  placebo    : cyclic shift by N // SHIFT_DIVISOR rows — breaks temporal alignment while
               preserving within-series autocorrelation structure

Verdict tokens (canonical)
--------------------------
  ACCEPT         : C1+C2+C3 all satisfied at both stability and window levels
  REJECT         : C1 violated (transition not detected reliably) — principal hypothesis fails
  INDETERMINATE  : C1 ok but C2/C3 fail (detector may not be specific enough)

Run time notes
--------------
  Fast mode (--fast): N_WINDOW=3, N_BOOT=10 → ~60 subprocess calls total (~3-5 min)
  Full mode          : N_WINDOW=5, N_BOOT=30 → ~180 subprocess calls total (~10-15 min)

Outputs to <outdir>/
  tables/window_sensitivity.csv  — verdict for each (dataset_type, window_variant)
  tables/subsample_stability.csv — verdict for each (dataset_type, rep)
  tables/validation_summary.json — aggregate metrics + verdict
  tables/summary.csv             — one-row canonical summary
  verdict.txt                    — ACCEPT | REJECT | INDETERMINATE

Usage
-----
  # Full protocol on pilot CPI with correct column names
  python 04_Code/pipeline/run_real_data_validation_protocol.py \\
      --input 03_Data/real/economie/pilot_cpi/real.csv \\
      --outdir 05_Results/real_validation/pilot_cpi \\
      --col-O industrial_production_i15 \\
      --col-R berd_pc_gdp \\
      --col-I ict_spec_pc_ent_ge10 \\
      --col-demand env_tax_env_mio_eur \\
      --col-S solar_collector_ths_m2 \\
      --col-time year --time-mode value \\
      --normalize robust --seed 42

  # Fast mode (CI / quick iteration)
  python 04_Code/pipeline/run_real_data_validation_protocol.py \\
      --input 03_Data/real/fred_monthly/real.csv \\
      --outdir 05_Results/real_validation/fred_fast \\
      --col-time date --time-mode index \\
      --fast --seed 42
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

_CODE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]

# ── Protocol constants ────────────────────────────────────────────────────────

N_WINDOW_VARIANTS_FULL = 5
N_WINDOW_VARIANTS_FAST = 3
N_BOOT_FULL = 30
N_BOOT_FAST = 10
SAMPLE_FRAC = 0.80
PRE_FRAC = 0.50         # fraction of rows used for "stable" dataset
SHIFT_DIVISOR = 3        # placebo: cyclic shift by N // SHIFT_DIVISOR

STABILITY_MIN = 0.80     # C1: transition detection rate threshold
STABLE_MIN = 0.70        # C2: stable non-detection rate threshold
PLACEBO_MIN = 0.70       # C3: placebo non-detection rate threshold

# Default window configs: (pre_horizon, post_horizon, label)
_WINDOW_VARIANTS_FULL = [
    (20,  20,  "narrow"),
    (40,  40,  "medium"),
    (100, 100, "default"),
    (150, 60,  "wide_pre"),
    (60,  150, "wide_post"),
]
_WINDOW_VARIANTS_FAST = [
    (20,  20,  "narrow"),
    (60,  60,  "medium"),
    (100, 100, "default"),
]

# ── Dataset generation ────────────────────────────────────────────────────────

def _make_stable(df: pd.DataFrame) -> pd.DataFrame:
    """Return the pre-transition prefix: first PRE_FRAC of rows."""
    n = max(5, int(len(df) * PRE_FRAC))
    return df.iloc[:n].reset_index(drop=True)


def _make_placebo(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Cyclic shift: rows shifted by N // SHIFT_DIVISOR — breaks temporal alignment."""
    shift = max(1, len(df) // SHIFT_DIVISOR)
    return pd.concat([df.iloc[shift:], df.iloc[:shift]], ignore_index=True).reset_index(drop=True)


# ── Subprocess helpers ────────────────────────────────────────────────────────

def _run_demo(
    csv_path: Path,
    outdir: Path,
    col_O: str,
    col_R: str,
    col_I: str,
    col_demand: str,
    col_S: str,
    col_time: str,
    time_mode: str,
    normalize: str,
    control_mode: str,
    seed: int,
    baseline_n: int,
) -> bool:
    """Run run_real_data_demo.py. Returns True on success."""
    script = _REPO_ROOT / "04_Code" / "pipeline" / "run_real_data_demo.py"
    cmd = [
        sys.executable, str(script),
        "--input", str(csv_path),
        "--outdir", str(outdir),
        "--col-time", col_time,
        "--time-mode", time_mode,
        "--col-O", col_O,
        "--col-R", col_R,
        "--col-I", col_I,
        "--col-demand", col_demand,
        "--col-S", col_S,
        "--normalize", normalize,
        "--control-mode", control_mode,
        "--baseline-n", str(baseline_n),
        "--seed", str(seed),
    ]
    env = {"PYTHONPATH": str(_REPO_ROOT / "src"), "PATH": "/usr/bin:/usr/local/bin:/bin"}
    try:
        subprocess.run(
            cmd, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**__import__("os").environ, "PYTHONPATH": str(_REPO_ROOT / "src")},
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _run_causal(
    run_dir: Path,
    pre_horizon: int,
    post_horizon: int,
    lags: str,
    baseline_n: int,
    seed: int,
) -> dict:
    """Run tests_causaux.py on an existing run_dir. Return extracted metrics."""
    script = _REPO_ROOT / "04_Code" / "pipeline" / "tests_causaux.py"
    cmd = [
        sys.executable, str(script),
        "--run-dir", str(run_dir),
        "--pre-horizon", str(pre_horizon),
        "--post-horizon", str(post_horizon),
        "--lags", lags,
        "--baseline-n", str(baseline_n),
        "--seed", str(seed),
    ]
    try:
        subprocess.run(
            cmd, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**__import__("os").environ, "PYTHONPATH": str(_REPO_ROOT / "src")},
        )
    except subprocess.CalledProcessError:
        return {"verdict": "error", "ok_p_source": "", "p_welch": float("nan")}

    # Read result
    summary_csv = run_dir / "tables" / "causal_tests_summary.csv"
    verdict_json = run_dir / "tables" / "verdict.json"
    if verdict_json.exists():
        try:
            d = json.loads(verdict_json.read_text(encoding="utf-8"))
            return {
                "verdict": d.get("verdict", "unknown"),
                "ok_p_source": d.get("criteria", {}).get("ok_p_source", ""),
                "p_welch": float(d.get("p_value_mean_shift_C", float("nan"))),
                "p_mwu": float(d.get("p_value_mannwhitney_C", float("nan"))),
                "sigma_zero_post": bool(d.get("sigma_zero_post", False)),
                "sigma_gate_note": d.get("sigma_gate_note") or "",
            }
        except Exception:
            pass

    if summary_csv.exists():
        try:
            df = pd.read_csv(summary_csv)
            if len(df) > 0:
                return {
                    "verdict": str(df.iloc[0].get("verdict", "unknown")),
                    "ok_p_source": str(df.iloc[0].get("ok_p_source", "")),
                    "p_welch": float(df.iloc[0].get("p_value_mean_shift_C", float("nan"))),
                    "p_mwu": float("nan"),
                    "sigma_zero_post": False,
                    "sigma_gate_note": "",
                }
        except Exception:
            pass

    return {"verdict": "error", "ok_p_source": "", "p_welch": float("nan"),
            "p_mwu": float("nan"), "sigma_zero_post": False, "sigma_gate_note": ""}


def _is_detected(verdict: str) -> bool:
    return verdict == "seuil_detecte"


def _is_not_detected(verdict: str) -> bool:
    return verdict in ("non_detecte", "indetermine_sigma_nul", "INDETERMINATE")


# ── Protocol phases ───────────────────────────────────────────────────────────

def _phase_window_sensitivity(
    df: pd.DataFrame,
    dataset_label: str,
    tmpdir: Path,
    window_variants: list[tuple[int, int, str]],
    col_O: str, col_R: str, col_I: str, col_demand: str, col_S: str,
    col_time: str, time_mode: str, normalize: str, control_mode: str,
    lags: str, baseline_n: int, seed: int,
    verbose: bool,
) -> list[dict]:
    """Run demo once on full series, then run causal tests with each window config."""
    rows: list[dict] = []

    # Persist dataset to temp CSV
    csv_path = tmpdir / f"ds_{dataset_label}_full.csv"
    df.to_csv(csv_path, index=False)

    # Single demo run for the full series
    demo_dir = tmpdir / f"demo_{dataset_label}_full"
    demo_dir.mkdir(parents=True, exist_ok=True)
    ok = _run_demo(
        csv_path, demo_dir, col_O, col_R, col_I, col_demand, col_S,
        col_time, time_mode, normalize, control_mode, seed, baseline_n,
    )
    if not ok:
        if verbose:
            print(f"  [{dataset_label}] demo run FAILED on full series")
        return [{"dataset": dataset_label, "window": v[2], "pre": v[0], "post": v[1],
                 "verdict": "error"} for v in window_variants]

    for pre, post, label in window_variants:
        result = _run_causal(demo_dir, pre, post, lags, baseline_n, seed)
        row = {
            "dataset": dataset_label,
            "window": label,
            "pre_horizon": int(pre),
            "post_horizon": int(post),
            "verdict": result["verdict"],
            "ok_p_source": result.get("ok_p_source", ""),
            "sigma_zero_post": result.get("sigma_zero_post", False),
        }
        rows.append(row)
        if verbose:
            print(f"  [{dataset_label}] window={label:12s} pre={pre:4d} post={post:4d} → {result['verdict']}")

    return rows


def _phase_subsample_stability(
    df: pd.DataFrame,
    dataset_label: str,
    tmpdir: Path,
    n_boot: int,
    default_pre: int,
    default_post: int,
    col_O: str, col_R: str, col_I: str, col_demand: str, col_S: str,
    col_time: str, time_mode: str, normalize: str, control_mode: str,
    lags: str, baseline_n: int, base_seed: int,
    verbose: bool,
    pre_horizon: int | None = None,
    post_horizon: int | None = None,
    sample_frac: float = 0.8,
) -> list[dict]:
    """Run n_boot subsamples of 80% rows. Returns per-rep verdict rows."""
    rows: list[dict] = []
    rng = np.random.default_rng(base_seed)
    if pre_horizon is not None:
        default_pre = int(pre_horizon)
    if post_horizon is not None:
        default_post = int(post_horizon)
    n = len(df)
    sf = float(sample_frac)
    sf = 0.8 if not (0.05 <= sf <= 0.95) else sf
    n_sample = max(5, int(n * sf))

    for rep in range(n_boot):
        sub_seed = int(base_seed + 1000 + rep)
        # Sample n_sample indices without replacement, maintain temporal order
        idx = np.sort(rng.choice(n, size=n_sample, replace=False))
        df_sub = df.iloc[idx].reset_index(drop=True)

        # Write sub to temp
        csv_path = tmpdir / f"ds_{dataset_label}_sub{rep:03d}.csv"
        df_sub.to_csv(csv_path, index=False)

        # Demo run on subsample
        demo_dir = tmpdir / f"demo_{dataset_label}_sub{rep:03d}"
        demo_dir.mkdir(parents=True, exist_ok=True)
        ok = _run_demo(
            csv_path, demo_dir, col_O, col_R, col_I, col_demand, col_S,
            col_time, time_mode, normalize, control_mode, sub_seed, baseline_n,
        )
        if not ok:
            rows.append({"dataset": dataset_label, "rep": rep, "n_rows": n_sample,
                         "verdict": "error", "ok_p_source": ""})
            continue

        result = _run_causal(demo_dir, default_pre, default_post, lags, baseline_n, sub_seed)
        rows.append({
            "dataset": dataset_label,
            "rep": int(rep),
            "n_rows": int(n_sample),
            "verdict": result["verdict"],
            "ok_p_source": result.get("ok_p_source", ""),
            "sigma_zero_post": result.get("sigma_zero_post", False),
        })
        if verbose:
            print(f"  [{dataset_label}] sub {rep:3d}/{n_boot-1}  n={n_sample}  → {result['verdict']}")

    return rows


# ── Aggregate stability metrics ───────────────────────────────────────────────

def _stability_metrics(
    rows: list[dict],
    expected_detected: bool,
) -> dict:
    """Compute stability metrics for a list of per-rep rows."""
    verdicts = [r["verdict"] for r in rows if r.get("verdict", "error") != "error"]
    n_valid = len(verdicts)
    if n_valid == 0:
        return {"n_valid": 0, "n_error": len(rows), "detection_rate": float("nan"),
                "non_detection_rate": float("nan"), "modal_verdict": "error",
                "stability_fraction": float("nan")}

    detected = [v for v in verdicts if _is_detected(v)]
    not_detected = [v for v in verdicts if _is_not_detected(v)]
    from collections import Counter
    modal_verdict = Counter(verdicts).most_common(1)[0][0]
    modal_count = Counter(verdicts)[modal_verdict]

    det_rate = len(detected) / n_valid
    non_det_rate = len(not_detected) / n_valid
    stability = modal_count / n_valid

    return {
        "n_valid": int(n_valid),
        "n_error": int(len(rows) - n_valid),
        "detection_rate": float(det_rate),
        "non_detection_rate": float(non_det_rate),
        "modal_verdict": modal_verdict,
        "stability_fraction": float(stability),
        "verdict_counts": dict(Counter(verdicts)),
    }


# ── Protocol verdict ──────────────────────────────────────────────────────────

def _protocol_verdict(
    test_metrics: dict,
    stable_metrics: dict,
    placebo_metrics: dict,
    test_window_rows: list[dict],
    stable_window_rows: list[dict],
    placebo_window_rows: list[dict],
) -> tuple[str, dict]:
    """Apply the three-condition protocol verdict rule."""
    notes: dict = {}

    # C1: transition detection stability
    c1_det_rate = test_metrics.get("detection_rate", float("nan"))
    c1_window_det = sum(1 for r in test_window_rows if _is_detected(r.get("verdict", "")))
    c1_window_n = len(test_window_rows) or 1
    c1_window_frac = c1_window_det / c1_window_n
    c1_ok = (
        isinstance(c1_det_rate, float) and c1_det_rate >= STABILITY_MIN
        and c1_window_frac >= STABILITY_MIN
    )
    notes["C1_transition"] = {
        "subsample_det_rate": float(c1_det_rate) if isinstance(c1_det_rate, float) else None,
        "window_det_frac": float(c1_window_frac),
        "passed": bool(c1_ok),
        "threshold": STABILITY_MIN,
    }

    # C2: stable non-detection
    c2_non_det_rate = stable_metrics.get("non_detection_rate", float("nan"))
    c2_window_non_det = sum(1 for r in stable_window_rows if _is_not_detected(r.get("verdict", "")))
    c2_window_frac = c2_window_non_det / (len(stable_window_rows) or 1)
    c2_ok = (
        isinstance(c2_non_det_rate, float) and c2_non_det_rate >= STABLE_MIN
        and c2_window_frac >= STABLE_MIN
    )
    notes["C2_stable"] = {
        "subsample_non_det_rate": float(c2_non_det_rate) if isinstance(c2_non_det_rate, float) else None,
        "window_non_det_frac": float(c2_window_frac),
        "passed": bool(c2_ok),
        "threshold": STABLE_MIN,
    }

    # C3: placebo non-detection
    c3_non_det_rate = placebo_metrics.get("non_detection_rate", float("nan"))
    c3_window_non_det = sum(1 for r in placebo_window_rows if _is_not_detected(r.get("verdict", "")))
    c3_window_frac = c3_window_non_det / (len(placebo_window_rows) or 1)
    c3_ok = (
        isinstance(c3_non_det_rate, float) and c3_non_det_rate >= PLACEBO_MIN
        and c3_window_frac >= PLACEBO_MIN
    )
    notes["C3_placebo"] = {
        "subsample_non_det_rate": float(c3_non_det_rate) if isinstance(c3_non_det_rate, float) else None,
        "window_non_det_frac": float(c3_window_frac),
        "passed": bool(c3_ok),
        "threshold": PLACEBO_MIN,
    }

    if not c1_ok:
        verdict = "REJECT"
        notes["reason"] = "C1 failed: transition not detected with sufficient stability"
    elif c1_ok and c2_ok and c3_ok:
        verdict = "ACCEPT"
        notes["reason"] = "C1+C2+C3 all passed: transition detected, stable and placebo not detected"
    else:
        verdict = "INDETERMINATE"
        failed = [k for k, v in {"C2": c2_ok, "C3": c3_ok}.items() if not v]
        notes["reason"] = f"C1 passed but {failed} failed: detector may not be specific enough"

    return verdict, notes


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="ORI-C real-data validation protocol: 3 datasets × window sensitivity × subsampling"
    )
    ap.add_argument("--input", required=True, help="Input CSV (single transition dataset).")
    ap.add_argument(
        "--inputs",
        nargs="*",
        default=None,
        help=(
            "Optional additional input CSVs. If provided, the protocol is run for each input and an "
            "aggregate verdict is emitted (ACCEPT if any dataset ACCEPTs)."
        ),
    )
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--col-time", default="t")
    ap.add_argument("--time-mode", default="index", choices=["index", "value"])
    ap.add_argument("--col-O", default="O")
    ap.add_argument("--col-R", default="R")
    ap.add_argument("--col-I", default="I")
    ap.add_argument("--col-demand", default="demand")
    ap.add_argument("--col-S", default="S")
    ap.add_argument("--normalize", default="robust", choices=["none", "minmax", "robust"])
    ap.add_argument("--control-mode", default="same", choices=["same", "no_symbolic"])
    ap.add_argument("--baseline-n", type=int, default=20)
    ap.add_argument("--lags", default="1-5")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--fast",
        action="store_true",
        help=f"Fast mode: {N_WINDOW_VARIANTS_FAST} window variants, {N_BOOT_FAST} subsamples (default: {N_WINDOW_VARIANTS_FULL}/{N_BOOT_FULL})",
    )
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    # Resolve input list (unique, ordered)
    inputs: list[str] = []
    for p in [args.input] + (args.inputs or []):
        if p and p not in inputs:
            inputs.append(p)

    outdir_root = Path(args.outdir)
    outdir_root.mkdir(parents=True, exist_ok=True)

    # Common protocol configuration
    n_window = N_WINDOW_VARIANTS_FAST if args.fast else N_WINDOW_VARIANTS_FULL
    n_boot = N_BOOT_FAST if args.fast else N_BOOT_FULL
    window_variants = (_WINDOW_VARIANTS_FAST if args.fast else _WINDOW_VARIANTS_FULL)

    print(
        f"Protocol mode: {'fast' if args.fast else 'full'}  "
        f"(N_window={n_window}, N_boot={n_boot}, sample_frac={SAMPLE_FRAC})"
    )
    print(f"Inputs ({len(inputs)}):")
    for p in inputs:
        print(f"  - {p}")

    aggregate_rows: list[dict] = []
    best_row: dict | None = None

    for inp in inputs:
        inp_path = Path(inp)
        # Make a stable subdir name
        stem = inp_path.stem.replace(" ", "_")
        subdir = outdir_root / stem
        tabdir = subdir / "tables"
        figdir = subdir / "figures"
        tabdir.mkdir(parents=True, exist_ok=True)
        figdir.mkdir(parents=True, exist_ok=True)

        print("\n" + "=" * 78)
        print(f"Running protocol on: {inp}")
        print(f"Output dir: {subdir}")
        print("=" * 78)

        df_test = pd.read_csv(inp_path)
        df_stable = _make_stable(df_test)
        df_placebo = _make_placebo(df_test, args.seed)

        print(f"Dataset sizes: test={len(df_test)}  stable={len(df_stable)}  placebo={len(df_placebo)}")

        datasets = [
            ("test", df_test),
            ("stable", df_stable),
            ("placebo", df_placebo),
        ]

        all_window_rows: list[dict] = []
        all_subsample_rows: list[dict] = []

        with tempfile.TemporaryDirectory(prefix="oric_val_") as tmpstr:
            tmpdir = Path(tmpstr)

            for ds_label, df_ds in datasets:
                print(f"\n── Dataset: {ds_label} (n={len(df_ds)}) ──")

                # Phase A: window sensitivity
                print(f"  Phase A: window sensitivity ({n_window} variants) ...")
                wrows = _phase_window_sensitivity(
                    df_ds,
                    ds_label,
                    tmpdir,
                    window_variants,
                    args.col_O,
                    args.col_R,
                    args.col_I,
                    args.col_demand,
                    args.col_S,
                    args.col_time,
                    args.time_mode,
                    args.normalize,
                    args.control_mode,
                    args.baseline_n,
                    args.lags,
                    args.seed,
                )
                all_window_rows.extend(wrows)

                # Phase B: subsample stability (fixed default window)
                print(f"  Phase B: subsample stability (n_boot={n_boot}) ...")
                srows = _phase_subsample_stability(
                    df_ds,
                    ds_label,
                    tmpdir,
                    pre_horizon=60,
                    post_horizon=60,
                    n_boot=n_boot,
                    sample_frac=SAMPLE_FRAC,
                    col_O=args.col_O,
                    col_R=args.col_R,
                    col_I=args.col_I,
                    col_demand=args.col_demand,
                    col_S=args.col_S,
                    col_time=args.col_time,
                    time_mode=args.time_mode,
                    normalize=args.normalize,
                    control_mode=args.control_mode,
                    baseline_n=args.baseline_n,
                    lags=args.lags,
                    seed=args.seed,
                )
                all_subsample_rows.extend(srows)

        # Write raw protocol tables
        dfw = pd.DataFrame(all_window_rows)
        dfs = pd.DataFrame(all_subsample_rows)
        dfw.to_csv(tabdir / "window_sensitivity.csv", index=False)
        dfs.to_csv(tabdir / "subsample_stability.csv", index=False)

        summary = _summarise_protocol(dfw, dfs)
        (tabdir / "validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        verdict = summary.get("protocol_verdict", "UNKNOWN")
        det_rate = float(summary.get("test_det_rate", 0.0) or 0.0)
        stable_rate = float(summary.get("stable_det_rate", 0.0) or 0.0)
        placebo_rate = float(summary.get("placebo_det_rate", 0.0) or 0.0)
        modal = summary.get("test_modal", "")

        (subdir / "verdict.txt").write_text(f"{verdict}\n", encoding="utf-8")

        row = {
            "input": str(inp_path),
            "stem": stem,
            "protocol_verdict": verdict,
            "test_det_rate": det_rate,
            "stable_det_rate": stable_rate,
            "placebo_det_rate": placebo_rate,
            "test_modal": modal,
            "n_test": int(len(df_test)),
        }
        aggregate_rows.append(row)

        # Best row = highest det_rate among ACCEPT; else highest det_rate overall
        if best_row is None:
            best_row = row
        else:
            def _rank(r: dict) -> tuple:
                return (
                    1 if r["protocol_verdict"] == "ACCEPT" else 0,
                    r["test_det_rate"],
                    -r["stable_det_rate"],
                    -r["placebo_det_rate"],
                )
            if _rank(row) > _rank(best_row):
                best_row = row

        print(f"Protocol verdict for {stem}: {verdict}  (det_rate={det_rate:.3f}, modal={modal})")

    # Aggregate verdict
    dfagg = pd.DataFrame(aggregate_rows)
    dfagg.to_csv(outdir_root / "tables" / "aggregate_inputs.csv", index=False) if len(dfagg) else None

    any_accept = any(r["protocol_verdict"] == "ACCEPT" for r in aggregate_rows)
    overall_verdict = "ACCEPT" if any_accept else "REJECT"

    outdir_root.joinpath("tables").mkdir(parents=True, exist_ok=True)
    outdir_root.joinpath("figures").mkdir(parents=True, exist_ok=True)

    overall = {
        "protocol_verdict": overall_verdict,
        "n_inputs": len(inputs),
        "any_accept": any_accept,
        "best_input": (best_row or {}).get("input"),
        "best_stem": (best_row or {}).get("stem"),
        "best_test_det_rate": (best_row or {}).get("test_det_rate"),
        "inputs": aggregate_rows,
    }
    (outdir_root / "tables" / "validation_summary.json").write_text(json.dumps(overall, indent=2), encoding="utf-8")
    (outdir_root / "verdict.txt").write_text(f"{overall_verdict}\n", encoding="utf-8")
    if best_row:
        (outdir_root / "best_input.txt").write_text(f"{best_row['input']}\n", encoding="utf-8")

    print("\n" + "=" * 78)
    print(f"OVERALL PROTOCOL VERDICT: {overall_verdict}")
    if best_row:
        print(f"Best input: {best_row['input']}  (verdict={best_row['protocol_verdict']}, det_rate={best_row['test_det_rate']:.3f})")
    print("=" * 78)

    return 0 if overall_verdict == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
