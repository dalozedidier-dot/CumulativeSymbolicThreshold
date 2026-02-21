#!/usr/bin/env python3
"""04_Code/pipeline/run_real_data_canonical_suite.py

Canonical T1–T8 suite on real observed data.

Runs in two stages per dataset:
  1. run_real_data_demo.py  → ORI-C timeseries + control (no_symbolic)
  2. tests_causaux.py       → causal verdict (Granger, VAR, bootstrap, cointegration)

Then maps the outputs to the 8 canonical tests:

  T1 – ORI core: Cap = O*R*I non-trivial, Sigma > 0, V responds to Sigma
  T2 – Threshold detection on delta_C (k=2.5, m=3)
  T3 – Robustness: threshold detection stable under normalize variant (robust vs minmax)
  T4 – S-rich → higher C than S-poor  (Granger S→delta_C significant)
  T5 – S injection effect on C         (bootstrap CI_low > 0 AND p < alpha)
  T6 – Symbolic dimension non-trivial  (cointegration C–S significant)
  T7 – Progressive S → tipping point   (VAR S→delta_C significant)
  T8 – C > 0 post-threshold, stable    (C_positive_frac_post > 0.5, C_mean_post > pre)

Output (canonical convention):
  <outdir>/
    tables/summary.csv          one-row per T, verdict column
    tables/global_summary.json  machine-readable aggregate
    verdict.txt                 ACCEPT | REJECT | INDETERMINATE
    figures/                    (forwarded from sub-runs)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        f.write("CMD: " + " ".join(cmd) + "\n\n")
        f.flush()
        rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT)
    return rc


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _load_csv_col(path: Path, col: str) -> np.ndarray:
    if not path.exists():
        return np.array([])
    df = pd.read_csv(path)
    if col not in df.columns:
        return np.array([])
    return df[col].to_numpy(dtype=float)


# ---------------------------------------------------------------------------
# T1: ORI core validation from the raw timeseries
# ---------------------------------------------------------------------------

def _t1_verdict(ts_path: Path) -> tuple[str, dict]:
    if not ts_path.exists():
        return "INDETERMINATE", {"reason": "test_timeseries.csv absent"}
    df = pd.read_csv(ts_path)
    details: dict = {}

    cap_ok = False
    sigma_ok = False
    v_ok = False

    if "Cap" in df.columns:
        cap_std = float(df["Cap"].std())
        cap_ok = cap_std > 1e-9
        details["Cap_std"] = cap_std
    else:
        details["Cap_std"] = None

    if "Sigma" in df.columns:
        sigma_max = float(df["Sigma"].max())
        sigma_ok = sigma_max > 0.0
        details["Sigma_max"] = sigma_max
    else:
        details["Sigma_max"] = None

    if "V" in df.columns:
        v_std = float(df["V"].std())
        v_ok = v_std > 1e-9
        details["V_std"] = v_std
    else:
        details["V_std"] = None

    if cap_ok and sigma_ok and v_ok:
        return "ACCEPT", details
    if cap_ok or sigma_ok:
        return "INDETERMINATE", details
    return "REJECT", details


# ---------------------------------------------------------------------------
# T3: robustness – run a second normalize variant, check threshold stability
# ---------------------------------------------------------------------------

def _t3_verdict(
    run1_thr: bool,
    run2_thr: bool,
) -> tuple[str, dict]:
    """T3 robustness: ACCEPT if both variants detect threshold (stable),
    REJECT if one detects and the other does not (fragile = falsified),
    INDETERMINATE if neither detects (no threshold to assess robustness on)."""
    details = {"normalize_robust_thr": run1_thr, "normalize_minmax_thr": run2_thr}
    if run1_thr and run2_thr:
        return "ACCEPT", details
    if run1_thr != run2_thr:
        return "REJECT", details
    # Neither detected — not a robustness failure, just no threshold
    return "INDETERMINATE", details


# ---------------------------------------------------------------------------
# T2/T4–T8: derived from tests_causaux verdict.json
# ---------------------------------------------------------------------------

def _map_causal_verdicts(
    causal: dict,
    demo_summary: dict,
    alpha: float,
) -> dict[str, tuple[str, dict]]:
    """Map causal report keys → T2,T4,T5,T6,T7,T8 individual verdicts."""

    results: dict[str, tuple[str, dict]] = {}

    # T2: threshold detection
    has_thr = bool(causal.get("threshold_hit_t") is not None)
    no_fp = bool(causal.get("no_false_positives_pre", True))
    results["T2"] = (
        "ACCEPT" if (has_thr and no_fp) else ("REJECT" if (has_thr and not no_fp) else "INDETERMINATE"),
        {"threshold_hit_t": causal.get("threshold_hit_t"), "no_fp": no_fp},
    )

    # T4: Granger S → delta_C
    g_p = causal.get("min_granger_S_to_deltaC_p", float("nan"))
    if not isinstance(g_p, float):
        g_p = float("nan")
    results["T4"] = (
        "ACCEPT" if (np.isfinite(g_p) and g_p <= alpha) else "INDETERMINATE",
        {"min_granger_S_to_deltaC_p": g_p},
    )

    # T5: bootstrap CI + p-value mean shift on C
    boot_lo = causal.get("boot_ci_low_C", float("nan"))
    if not isinstance(boot_lo, float):
        boot_lo = float("nan")
    ok_boot = bool(np.isfinite(boot_lo) and boot_lo > 0.0)
    ok_p_raw = causal.get("criteria", {}).get("ok_p", False)
    results["T5"] = (
        "ACCEPT" if (ok_boot and ok_p_raw) else ("INDETERMINATE" if (ok_boot or ok_p_raw) else "REJECT"),
        {"boot_ci_low_C": boot_lo, "ok_p": ok_p_raw},
    )

    # T6: cointegration C–S significant → symbolic dimension non-trivial
    coint_p = causal.get("cointegration_p", float("nan"))
    if not isinstance(coint_p, float):
        coint_p = float("nan")
    results["T6"] = (
        "ACCEPT" if (np.isfinite(coint_p) and coint_p <= alpha) else "INDETERMINATE",
        {"cointegration_p": coint_p},
    )

    # T7: VAR S → delta_C
    var_p = causal.get("var_S_to_deltaC_p", float("nan"))
    if not isinstance(var_p, float):
        var_p = float("nan")
    results["T7"] = (
        "ACCEPT" if (np.isfinite(var_p) and var_p <= alpha) else "INDETERMINATE",
        {"var_S_to_deltaC_p": var_p},
    )

    # T8: C stable positive post-threshold
    c_pos_frac = causal.get("C_positive_frac_post", float("nan"))
    if not isinstance(c_pos_frac, float):
        c_pos_frac = float("nan")
    c_mean_pre = causal.get("C_mean_pre", float("nan"))
    c_mean_post = causal.get("C_mean_post", float("nan"))
    if not isinstance(c_mean_pre, float):
        c_mean_pre = float("nan")
    if not isinstance(c_mean_post, float):
        c_mean_post = float("nan")
    ok_frac = bool(np.isfinite(c_pos_frac) and c_pos_frac > 0.5)
    ok_level = bool(np.isfinite(c_mean_pre) and np.isfinite(c_mean_post) and c_mean_post > c_mean_pre)
    results["T8"] = (
        "ACCEPT" if (ok_frac and ok_level) else ("INDETERMINATE" if (ok_frac or ok_level) else "REJECT"),
        {"C_positive_frac_post": c_pos_frac, "C_mean_pre": c_mean_pre, "C_mean_post": c_mean_post},
    )

    return results


# ---------------------------------------------------------------------------
# Aggregate verdict
# ---------------------------------------------------------------------------

def _global_verdict(t_verdicts: dict[str, str]) -> str:
    vals = list(t_verdicts.values())
    n_accept = vals.count("ACCEPT")
    n_reject = vals.count("REJECT")
    # Hard falsification: ≥ 2 REJECT → REJECT
    if n_reject >= 2:
        return "REJECT"
    # Strong confirmation: ≥ 6 ACCEPT out of 8 and 0 REJECT
    if n_accept >= 6 and n_reject == 0:
        return "ACCEPT"
    return "INDETERMINATE"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run canonical T1–T8 suite on real observed data."
    )
    ap.add_argument("--input", required=True, help="Real data CSV")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--col-time", default="t")
    ap.add_argument(
        "--time-mode",
        default="index",
        choices=["index", "value"],
    )
    ap.add_argument("--col-O", default="O")
    ap.add_argument("--col-R", default="R")
    ap.add_argument("--col-I", default="I")
    ap.add_argument("--col-demand", default="demand")
    ap.add_argument("--col-S", default="S")
    ap.add_argument("--normalize", default="robust", choices=["none", "minmax", "robust"])
    ap.add_argument("--auto-scale", action="store_true",
                    help="Align cap_scale to demand median (recommended when observed demand is provided)")
    ap.add_argument("--cap-scale", type=float, default=1000.0)
    ap.add_argument("--demand-to-cap-ratio", type=float, default=0.90)
    ap.add_argument("--sigma-star", type=float, default=0.0)
    ap.add_argument("--tau", type=float, default=500.0)
    ap.add_argument("--sigma-to-S-alpha", type=float, default=0.0008)
    ap.add_argument("--S0", type=float, default=0.20)
    ap.add_argument("--C-beta", type=float, default=0.40)
    ap.add_argument("--C-gamma", type=float, default=0.12)
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=50)
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--lags", type=str, default="1-10")
    ap.add_argument("--pre-horizon", type=int, default=250)
    ap.add_argument("--post-horizon", type=int, default=250)
    ap.add_argument("--c-mean-post-min", type=float, default=0.1)
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERREUR: dataset introuvable: {input_path}", file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parents[2]
    scripts = root / "04_Code" / "pipeline"
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tabdir = outdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)
    logdir = outdir / "logs"
    logdir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Shared column args for run_real_data_demo.py
    # ------------------------------------------------------------------
    col_args = [
        "--col-time", args.col_time,
        "--time-mode", args.time_mode,
        "--col-O", args.col_O,
        "--col-R", args.col_R,
        "--col-I", args.col_I,
        "--col-demand", args.col_demand,
        "--col-S", args.col_S,
        *(["--auto-scale"] if args.auto_scale else []),
        "--cap-scale", str(args.cap_scale),
        "--demand-to-cap-ratio", str(args.demand_to_cap_ratio),
        "--sigma-star", str(args.sigma_star),
        "--tau", str(args.tau),
        "--sigma-to-S-alpha", str(args.sigma_to_S_alpha),
        "--S0", str(args.S0),
        "--C-beta", str(args.C_beta),
        "--C-gamma", str(args.C_gamma),
        "--k", str(args.k),
        "--m", str(args.m),
        "--baseline-n", str(args.baseline_n),
    ]

    causal_args = [
        "--alpha", str(args.alpha),
        "--lags", args.lags,
        "--pre-horizon", str(args.pre_horizon),
        "--post-horizon", str(args.post_horizon),
        "--c-mean-post-min", str(args.c_mean_post_min),
        "--k", str(args.k),
        "--m", str(args.m),
        "--baseline-n", str(args.baseline_n),
    ]

    py = sys.executable
    demo_script = str(scripts / "run_real_data_demo.py")
    causal_script = str(scripts / "tests_causaux.py")

    # ------------------------------------------------------------------
    # Run 1 (main): normalize=robust, control=no_symbolic
    # ------------------------------------------------------------------
    run1_dir = outdir / "run1_robust"
    _run(
        [py, demo_script,
         "--input", str(input_path),
         "--outdir", str(run1_dir),
         "--normalize", args.normalize,
         "--control-mode", "no_symbolic"] + col_args,
        logdir / "run1_demo.log",
    )
    _run(
        [py, causal_script,
         "--run-dir", str(run1_dir)] + causal_args,
        logdir / "run1_causal.log",
    )

    # ------------------------------------------------------------------
    # Run 2 (T3 robustness): alternate normalize
    # ------------------------------------------------------------------
    alt_norm = "minmax" if args.normalize == "robust" else "robust"
    run2_dir = outdir / f"run2_{alt_norm}"
    _run(
        [py, demo_script,
         "--input", str(input_path),
         "--outdir", str(run2_dir),
         "--normalize", alt_norm,
         "--control-mode", "no_symbolic"] + col_args,
        logdir / "run2_demo.log",
    )
    _run(
        [py, causal_script,
         "--run-dir", str(run2_dir)] + causal_args,
        logdir / "run2_causal.log",
    )

    # ------------------------------------------------------------------
    # Load results
    # ------------------------------------------------------------------
    ts1 = run1_dir / "tables" / "test_timeseries.csv"
    causal1 = _load_json(run1_dir / "tables" / "verdict.json")
    demo1_summary = _load_json(run1_dir / "tables" / "summary.json")

    causal2 = _load_json(run2_dir / "tables" / "verdict.json")

    # ------------------------------------------------------------------
    # T1
    # ------------------------------------------------------------------
    t1_v, t1_d = _t1_verdict(ts1)

    # ------------------------------------------------------------------
    # T3 robustness
    # ------------------------------------------------------------------
    run1_thr = causal1.get("threshold_hit_t") is not None
    run2_thr = causal2.get("threshold_hit_t") is not None
    t3_v, t3_d = _t3_verdict(run1_thr, run2_thr)

    # ------------------------------------------------------------------
    # T2, T4–T8 from causal run1
    # ------------------------------------------------------------------
    causal_verdicts = _map_causal_verdicts(causal1, demo1_summary, float(args.alpha))

    # ------------------------------------------------------------------
    # Assemble full T1–T8 table
    # ------------------------------------------------------------------
    all_t: dict[str, tuple[str, dict]] = {
        "T1_ori_core": (t1_v, t1_d),
        "T2_threshold_detection": causal_verdicts["T2"],
        "T3_robustness": (t3_v, t3_d),
        "T4_granger_S_to_C": causal_verdicts["T4"],
        "T5_injection_mean_shift": causal_verdicts["T5"],
        "T6_cointegration_C_S": causal_verdicts["T6"],
        "T7_var_S_to_C": causal_verdicts["T7"],
        "T8_C_stable_post": causal_verdicts["T8"],
    }

    t_verdicts_simple = {k: v for k, (v, _) in all_t.items()}
    global_v = _global_verdict(t_verdicts_simple)

    # ------------------------------------------------------------------
    # Write outputs (canonical convention)
    # ------------------------------------------------------------------
    rows = []
    for test_id, (v, details) in all_t.items():
        row = {"test_id": test_id, "verdict": v}
        row.update({k: str(val) for k, val in details.items()})
        rows.append(row)

    pd.DataFrame(rows).to_csv(tabdir / "summary.csv", index=False)

    global_summary = {
        "input_csv": str(input_path),
        "global_verdict": global_v,
        "alpha": float(args.alpha),
        "tests": {k: {"verdict": v, "details": d} for k, (v, d) in all_t.items()},
    }
    (tabdir / "global_summary.json").write_text(
        json.dumps(global_summary, indent=2, default=str), encoding="utf-8"
    )

    (outdir / "verdict.txt").write_text(global_v, encoding="utf-8")

    # Print compact summary
    print(f"\n{'='*60}")
    print(f"ORI-C Real Data Canonical Suite — {input_path.name}")
    print(f"{'='*60}")
    for test_id, v in t_verdicts_simple.items():
        mark = "✓" if v == "ACCEPT" else ("✗" if v == "REJECT" else "?")
        print(f"  {mark} {test_id:<40} {v}")
    print(f"{'='*60}")
    print(f"  GLOBAL VERDICT: {global_v}")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
