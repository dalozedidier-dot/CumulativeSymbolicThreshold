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

Verdict classification (tri-state)
-----------------------------------
  Each inner run result is classified into one of three states:
    DETECTED       : binary_detected=True  OR verdict ∈ {seuil_detecte, …}
    NOT_DETECTED   : binary_detected=False OR verdict ∈ {non_detecte, falsifie, …}
    INDETERMINATE  : verdict starts with indetermine_, sigma_zero_post=True, or p NaN

  Rates are computed on decidable runs only (DETECTED + NOT_DETECTED):
    detection_rate     = n_detected / n_decidable
    non_detection_rate = n_not_detected / n_decidable
    indeterminate_rate = n_indeterminate / total

Protocol verdict tokens (canonical)
------------------------------------
  INDETERMINATE  : any condition has < N_DECIDABLE_MIN decidable runs
  REJECT         : enough decidable but C1 fails (transition not detected reliably)
  ACCEPT         : C1+C2+C3 all satisfied at both stability and window levels
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
N_WINDOW_VARIANTS_FAST = 4
N_BOOT_FULL = 30
N_BOOT_FAST = 15
SAMPLE_FRAC = 0.80
PRE_FRAC = 0.50         # fraction of rows used for "stable" dataset
SHIFT_DIVISOR = 3        # placebo: cyclic shift by N // SHIFT_DIVISOR

STABILITY_MIN = 0.80     # C1: transition detection rate threshold
STABLE_MIN = 0.70        # C2: stable non-detection rate threshold
PLACEBO_MIN = 0.70       # C3: placebo non-detection rate threshold
N_DECIDABLE_MIN = 3      # minimum decidable runs to issue ACCEPT/REJECT

# Default window configs: (pre_horizon, post_horizon, label)
# Post-window >= 100 ensures enough data points for Mann-Whitney fallback
# when sigma_zero_post=True (avoids systematic INDETERMINATE on short windows).
_WINDOW_VARIANTS_FULL = [
    (30,  30,  "narrow"),
    (60,  60,  "medium"),
    (100, 100, "default"),
    (150, 100, "wide_pre"),
    (100, 150, "wide_post"),
]
_WINDOW_VARIANTS_FAST = [
    (30,  30,  "narrow"),
    (60,  60,  "medium"),
    (100, 100, "default"),
    (100, 150, "wide_post"),
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


_DETECTED_TOKENS = frozenset({"seuil_detecte", "accept", "detected", "threshold_hit"})
_NOT_DETECTED_TOKENS = frozenset({"non_detecte", "reject", "falsifie"})
_INDETERMINATE_PREFIXES = ("indetermine_",)


def _classify_verdict(result: dict) -> str:
    """Classify a single run result into DETECTED / NOT_DETECTED / INDETERMINATE.

    Rules (applied in order):
      DETECTED        : binary_detected is True  OR  verdict ∈ _DETECTED_TOKENS
      NOT_DETECTED    : binary_detected is False  OR  verdict ∈ _NOT_DETECTED_TOKENS
      INDETERMINATE   : verdict starts with "indetermine_"
                        OR sigma_zero_post is True
                        OR verdict is "error" / "unknown"
    """
    verdict = str(result.get("verdict", "")).lower().strip()
    binary = result.get("binary_detected")
    sigma_zero = result.get("sigma_zero_post", False)

    # Indeterminate conditions (checked first to avoid misclassifying sigma-zero)
    if sigma_zero:
        return "INDETERMINATE"
    if any(verdict.startswith(p) for p in _INDETERMINATE_PREFIXES):
        return "INDETERMINATE"
    if verdict in ("error", "unknown", ""):
        return "INDETERMINATE"

    # Explicit binary flag takes precedence
    if binary is True:
        return "DETECTED"
    if binary is False:
        return "NOT_DETECTED"

    # Fall back to token matching
    if verdict in _DETECTED_TOKENS:
        return "DETECTED"
    if verdict in _NOT_DETECTED_TOKENS:
        return "NOT_DETECTED"

    return "INDETERMINATE"


def _is_detected(verdict: str) -> bool:
    """Legacy helper — kept for backward compatibility with row-level dicts."""
    return verdict.lower().strip() in _DETECTED_TOKENS


def _is_not_detected(verdict: str) -> bool:
    return verdict.lower().strip() in _NOT_DETECTED_TOKENS


# ── Protocol phases ───────────────────────────────────────────────────────────

def _phase_window_sensitivity(
    df: pd.DataFrame,
    dataset_label: str,
    tmpdir: Path,
    window_variants: list[tuple[int, int, str]],
    col_O: str, col_R: str, col_I: str, col_demand: str, col_S: str,
    col_time: str, time_mode: str, normalize: str, control_mode: str,
    lags: str, baseline_n: int, seed: int,
    verbose: bool = False,
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
    """Compute stability metrics using tri-state classification.

    States
    ------
    DETECTED       : binary_detected=True or verdict in {seuil_detecte, …}
    NOT_DETECTED   : binary_detected=False or verdict in {non_detecte, falsifie, …}
    INDETERMINATE  : verdict starts with indetermine_, sigma_zero_post=True, or p NaN

    Rates
    -----
    detection_rate     = n_detected / (n_detected + n_not_detected)   (decidable only)
    non_detection_rate = n_not_detected / (n_detected + n_not_detected)
    indeterminate_rate = n_indeterminate / total
    """
    from collections import Counter

    classes = [_classify_verdict(r) for r in rows]
    total = len(classes)
    counts = Counter(classes)
    n_det = counts.get("DETECTED", 0)
    n_not = counts.get("NOT_DETECTED", 0)
    n_ind = counts.get("INDETERMINATE", 0)
    n_decidable = n_det + n_not

    if total == 0:
        return {"n_valid": 0, "n_error": 0, "n_decidable": 0,
                "n_detected": 0, "n_not_detected": 0, "n_indeterminate": 0,
                "detection_rate": float("nan"), "non_detection_rate": float("nan"),
                "indeterminate_rate": float("nan"), "modal_verdict": "error",
                "stability_fraction": float("nan"), "verdict_counts": {}}

    det_rate = n_det / n_decidable if n_decidable > 0 else float("nan")
    non_det_rate = n_not / n_decidable if n_decidable > 0 else float("nan")
    ind_rate = n_ind / total

    modal_class = counts.most_common(1)[0][0]
    modal_count = counts[modal_class]
    stability = modal_count / total

    return {
        "n_valid": int(total),
        "n_error": 0,
        "n_decidable": int(n_decidable),
        "n_detected": int(n_det),
        "n_not_detected": int(n_not),
        "n_indeterminate": int(n_ind),
        "detection_rate": float(det_rate),
        "non_detection_rate": float(non_det_rate),
        "indeterminate_rate": float(ind_rate),
        "modal_verdict": modal_class,
        "stability_fraction": float(stability),
        "verdict_counts": dict(counts),
    }


# ── Protocol verdict ──────────────────────────────────────────────────────────

def _window_class_counts(rows: list[dict]) -> tuple[int, int, int]:
    """Classify window rows and return (n_detected, n_not_detected, n_indeterminate)."""
    classes = [_classify_verdict(r) for r in rows]
    from collections import Counter
    c = Counter(classes)
    return c.get("DETECTED", 0), c.get("NOT_DETECTED", 0), c.get("INDETERMINATE", 0)


def _protocol_verdict(
    test_metrics: dict,
    stable_metrics: dict,
    placebo_metrics: dict,
    test_window_rows: list[dict],
    stable_window_rows: list[dict],
    placebo_window_rows: list[dict],
) -> tuple[str, dict]:
    """Apply the three-condition protocol verdict rule with tri-state classification.

    Decidability gate
    -----------------
    Each condition requires at least N_DECIDABLE_MIN decidable runs (DETECTED +
    NOT_DETECTED).  If any condition falls below, the overall verdict is
    INDETERMINATE (not enough decidable cases to judge).

    Rates are computed on decidable runs only:
      detection_rate     = n_detected / n_decidable
      non_detection_rate = n_not_detected / n_decidable
    """
    notes: dict = {}

    # ── C1: transition detection stability ──────────────────────────────
    c1_det_rate = test_metrics.get("detection_rate", float("nan"))
    c1_decidable = test_metrics.get("n_decidable", 0)
    c1_ind_rate = test_metrics.get("indeterminate_rate", 0.0)

    w1_det, w1_not, w1_ind = _window_class_counts(test_window_rows)
    w1_decidable = w1_det + w1_not
    c1_window_frac = w1_det / w1_decidable if w1_decidable > 0 else float("nan")

    c1_enough = c1_decidable >= N_DECIDABLE_MIN and w1_decidable >= 1
    c1_ok = (
        c1_enough
        and isinstance(c1_det_rate, float) and c1_det_rate >= STABILITY_MIN
        and isinstance(c1_window_frac, float) and c1_window_frac >= STABILITY_MIN
    )
    notes["C1_transition"] = {
        "subsample_det_rate": _safe_float(c1_det_rate),
        "subsample_n_decidable": int(c1_decidable),
        "subsample_indeterminate_rate": _safe_float(c1_ind_rate),
        "window_det_frac": _safe_float(c1_window_frac),
        "window_n_decidable": int(w1_decidable),
        "window_n_indeterminate": int(w1_ind),
        "enough_decidable": bool(c1_enough),
        "passed": bool(c1_ok),
        "threshold": STABILITY_MIN,
    }

    # ── C2: stable non-detection ────────────────────────────────────────
    c2_non_det_rate = stable_metrics.get("non_detection_rate", float("nan"))
    c2_decidable = stable_metrics.get("n_decidable", 0)
    c2_ind_rate = stable_metrics.get("indeterminate_rate", 0.0)

    w2_det, w2_not, w2_ind = _window_class_counts(stable_window_rows)
    w2_decidable = w2_det + w2_not
    c2_window_frac = w2_not / w2_decidable if w2_decidable > 0 else float("nan")

    c2_enough = c2_decidable >= N_DECIDABLE_MIN and w2_decidable >= 1
    c2_ok = (
        c2_enough
        and isinstance(c2_non_det_rate, float) and c2_non_det_rate >= STABLE_MIN
        and isinstance(c2_window_frac, float) and c2_window_frac >= STABLE_MIN
    )
    notes["C2_stable"] = {
        "subsample_non_det_rate": _safe_float(c2_non_det_rate),
        "subsample_n_decidable": int(c2_decidable),
        "subsample_indeterminate_rate": _safe_float(c2_ind_rate),
        "window_non_det_frac": _safe_float(c2_window_frac),
        "window_n_decidable": int(w2_decidable),
        "window_n_indeterminate": int(w2_ind),
        "enough_decidable": bool(c2_enough),
        "passed": bool(c2_ok),
        "threshold": STABLE_MIN,
    }

    # ── C3: placebo non-detection ───────────────────────────────────────
    c3_non_det_rate = placebo_metrics.get("non_detection_rate", float("nan"))
    c3_decidable = placebo_metrics.get("n_decidable", 0)
    c3_ind_rate = placebo_metrics.get("indeterminate_rate", 0.0)

    w3_det, w3_not, w3_ind = _window_class_counts(placebo_window_rows)
    w3_decidable = w3_det + w3_not
    c3_window_frac = w3_not / w3_decidable if w3_decidable > 0 else float("nan")

    c3_enough = c3_decidable >= N_DECIDABLE_MIN and w3_decidable >= 1
    c3_ok = (
        c3_enough
        and isinstance(c3_non_det_rate, float) and c3_non_det_rate >= PLACEBO_MIN
        and isinstance(c3_window_frac, float) and c3_window_frac >= PLACEBO_MIN
    )
    notes["C3_placebo"] = {
        "subsample_non_det_rate": _safe_float(c3_non_det_rate),
        "subsample_n_decidable": int(c3_decidable),
        "subsample_indeterminate_rate": _safe_float(c3_ind_rate),
        "window_non_det_frac": _safe_float(c3_window_frac),
        "window_n_decidable": int(w3_decidable),
        "window_n_indeterminate": int(w3_ind),
        "enough_decidable": bool(c3_enough),
        "passed": bool(c3_ok),
        "threshold": PLACEBO_MIN,
    }

    # ── Decidability gate ───────────────────────────────────────────────
    if not (c1_enough and c2_enough and c3_enough):
        insufficient = [k for k, e in {"C1": c1_enough, "C2": c2_enough, "C3": c3_enough}.items() if not e]
        verdict = "INDETERMINATE"
        notes["reason"] = (
            f"Not enough decidable runs for {insufficient} "
            f"(need >= {N_DECIDABLE_MIN} decidable per condition)"
        )
    elif not c1_ok:
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


def _safe_float(v: object) -> float | None:
    """Return v as float, or None if NaN / not a number."""
    try:
        f = float(v)  # type: ignore[arg-type]
        return None if (f != f) else f  # NaN check
    except (TypeError, ValueError):
        return None


def _json_dumps_safe(obj: object, **kwargs: object) -> str:
    """json.dumps that converts NaN/Inf to None (valid JSON)."""
    import math

    def _sanitize(o: object) -> object:
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        if isinstance(o, dict):
            return {k: _sanitize(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_sanitize(v) for v in o]
        return o

    return json.dumps(_sanitize(obj), **kwargs)  # type: ignore[arg-type]


# ── Summarise protocol ────────────────────────────────────────────────────────

def _summarise_protocol(dfw: pd.DataFrame, dfs: pd.DataFrame) -> dict:
    """Build a summary dict from window-sensitivity and subsample-stability tables.

    Parameters
    ----------
    dfw : DataFrame with columns [dataset, window, verdict, …]
    dfs : DataFrame with columns [dataset, rep, verdict, …]

    Returns
    -------
    dict with keys: protocol_verdict, test_det_rate, stable_det_rate,
    placebo_det_rate, test_modal, test_metrics, stable_metrics, placebo_metrics,
    notes.
    """
    def _rows_for(df: pd.DataFrame, label: str) -> list[dict]:
        if df.empty:
            return []
        mask = df["dataset"] == label
        return df.loc[mask].to_dict(orient="records")

    test_window_rows = _rows_for(dfw, "test")
    stable_window_rows = _rows_for(dfw, "stable")
    placebo_window_rows = _rows_for(dfw, "placebo")

    test_sub_rows = _rows_for(dfs, "test")
    stable_sub_rows = _rows_for(dfs, "stable")
    placebo_sub_rows = _rows_for(dfs, "placebo")

    test_metrics = _stability_metrics(test_sub_rows, expected_detected=True)
    stable_metrics = _stability_metrics(stable_sub_rows, expected_detected=False)
    placebo_metrics = _stability_metrics(placebo_sub_rows, expected_detected=False)

    verdict, notes = _protocol_verdict(
        test_metrics, stable_metrics, placebo_metrics,
        test_window_rows, stable_window_rows, placebo_window_rows,
    )

    return {
        "protocol_verdict": verdict,
        "test_det_rate": test_metrics.get("detection_rate", 0.0),
        "stable_det_rate": stable_metrics.get("detection_rate", 0.0),
        "placebo_det_rate": placebo_metrics.get("detection_rate", 0.0),
        "test_modal": test_metrics.get("modal_verdict", ""),
        "test_metrics": test_metrics,
        "stable_metrics": stable_metrics,
        "placebo_metrics": placebo_metrics,
        "notes": notes,
    }


# ── Main ──────────────────────────────────────────────────────────────────────



# ── Protocol summary ─────────────────────────────────────────────────────────

def _summarise_protocol(dfw: "pd.DataFrame", dfs: "pd.DataFrame") -> dict:
    """
    Build a stable JSON summary for the validation protocol.

    Inputs:
    - dfw: window_sensitivity.csv as DataFrame (must contain a dataset label column)
    - dfs: subsample_stability.csv as DataFrame (must contain a dataset label column)

    The protocol is strictly mechanical:
    - test should be detected stably
    - stable and placebo should be non-detected stably
    """
    # Accept either dataset or dataset_type to avoid schema drift
    if "dataset_type" in dfw.columns and "dataset" not in dfw.columns:
        dfw = dfw.rename(columns={"dataset_type": "dataset"})
    if "dataset_type" in dfs.columns and "dataset" not in dfs.columns:
        dfs = dfs.rename(columns={"dataset_type": "dataset"})

    required_w = {"dataset", "window", "pre_horizon", "post_horizon", "verdict"}
    required_s = {"dataset", "rep", "n_rows", "verdict"}

    missing_w = sorted(required_w - set(dfw.columns))
    missing_s = sorted(required_s - set(dfs.columns))
    if missing_w:
        raise ValueError(f"window_sensitivity missing columns: {missing_w}")
    if missing_s:
        raise ValueError(f"subsample_stability missing columns: {missing_s}")

    def rows_for(df, label: str) -> list[dict]:
        sub = df.loc[df["dataset"] == label]
        return sub.to_dict(orient="records")

    test_window_rows = rows_for(dfw, "test")
    stable_window_rows = rows_for(dfw, "stable")
    placebo_window_rows = rows_for(dfw, "placebo")

    test_sub_rows = rows_for(dfs, "test")
    stable_sub_rows = rows_for(dfs, "stable")
    placebo_sub_rows = rows_for(dfs, "placebo")

    test_metrics = _stability_metrics(test_sub_rows, expected_detected=True)
    stable_metrics = _stability_metrics(stable_sub_rows, expected_detected=False)
    placebo_metrics = _stability_metrics(placebo_sub_rows, expected_detected=False)

    protocol_verdict, protocol_notes = _protocol_verdict(
        test_metrics,
        stable_metrics,
        placebo_metrics,
        test_window_rows,
        stable_window_rows,
        placebo_window_rows,
    )

    return {
        "protocol_verdict": protocol_verdict,
        "schema_version": 1,
        "datasets": {
            "test": {
                "n_window_rows": int(len(test_window_rows)),
                "n_subsample_rows": int(len(test_sub_rows)),
                "metrics": test_metrics,
            },
            "stable": {
                "n_window_rows": int(len(stable_window_rows)),
                "n_subsample_rows": int(len(stable_sub_rows)),
                "metrics": stable_metrics,
            },
            "placebo": {
                "n_window_rows": int(len(placebo_window_rows)),
                "n_subsample_rows": int(len(placebo_sub_rows)),
                "metrics": placebo_metrics,
            },
        },
        "protocol_notes": protocol_notes,
    }

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
                    args.lags,
                    args.baseline_n,
                    args.seed,
                    verbose=args.verbose,
                )
                all_window_rows.extend(wrows)

                # Phase B: subsample stability (fixed default window)
                print(f"  Phase B: subsample stability (n_boot={n_boot}) ...")
                srows = _phase_subsample_stability(
                    df_ds,
                    ds_label,
                    tmpdir,
                    n_boot=n_boot,
                    default_pre=100,
                    default_post=100,
                    col_O=args.col_O,
                    col_R=args.col_R,
                    col_I=args.col_I,
                    col_demand=args.col_demand,
                    col_S=args.col_S,
                    col_time=args.col_time,
                    time_mode=args.time_mode,
                    normalize=args.normalize,
                    control_mode=args.control_mode,
                    lags=args.lags,
                    baseline_n=args.baseline_n,
                    base_seed=args.seed,
                    verbose=args.verbose,
                    sample_frac=SAMPLE_FRAC,
                )
                all_subsample_rows.extend(srows)

        # Write raw protocol tables
        dfw = pd.DataFrame(all_window_rows)
        dfs = pd.DataFrame(all_subsample_rows)
        dfw.to_csv(tabdir / "window_sensitivity.csv", index=False)
        dfs.to_csv(tabdir / "subsample_stability.csv", index=False)

        summary = _summarise_protocol(dfw, dfs)
        (tabdir / "validation_summary.json").write_text(_json_dumps_safe(summary, indent=2), encoding="utf-8")

        verdict = summary.get("protocol_verdict", "UNKNOWN")
        def _rate(v: object) -> float:
            try:
                f = float(v)  # type: ignore[arg-type]
                return 0.0 if f != f else f  # NaN → 0.0
            except (TypeError, ValueError):
                return 0.0

        det_rate = _rate(summary.get("test_det_rate"))
        stable_rate = _rate(summary.get("stable_det_rate"))
        placebo_rate = _rate(summary.get("placebo_det_rate"))
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
    any_indeterminate = any(r["protocol_verdict"] == "INDETERMINATE" for r in aggregate_rows)
    if any_accept:
        overall_verdict = "ACCEPT"
    elif any_indeterminate:
        overall_verdict = "INDETERMINATE"
    else:
        overall_verdict = "REJECT"

    outdir_root.joinpath("tables").mkdir(parents=True, exist_ok=True)
    outdir_root.joinpath("figures").mkdir(parents=True, exist_ok=True)

    # Provide test_metrics at top level for CI extraction compatibility
    best_det_rate = (best_row or {}).get("test_det_rate", 0.0)
    overall = {
        "protocol_verdict": overall_verdict,
        "n_inputs": len(inputs),
        "any_accept": any_accept,
        "any_indeterminate": any_indeterminate,
        "best_input": (best_row or {}).get("input"),
        "best_stem": (best_row or {}).get("stem"),
        "best_test_det_rate": best_det_rate,
        "test_metrics": {"detection_rate": best_det_rate},
        "inputs": aggregate_rows,
    }
    (outdir_root / "tables" / "validation_summary.json").write_text(_json_dumps_safe(overall, indent=2), encoding="utf-8")
    (outdir_root / "verdict.txt").write_text(f"{overall_verdict}\n", encoding="utf-8")
    if best_row:
        (outdir_root / "best_input.txt").write_text(f"{best_row['input']}\n", encoding="utf-8")

    print("\n" + "=" * 78)
    print(f"OVERALL PROTOCOL VERDICT: {overall_verdict}")
    if best_row:
        print(f"Best input: {best_row['input']}  (verdict={best_row['protocol_verdict']}, det_rate={best_row['test_det_rate']:.3f})")
    print("=" * 78)

    # Verdict (ACCEPT/REJECT/INDETERMINATE) is a scientific outcome, not an error.
    # The CI workflow reads verdict.txt for gating decisions; exit 0 always.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
