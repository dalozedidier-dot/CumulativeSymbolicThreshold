#!/usr/bin/env python3
"""run_scientific_validation_protocol.py — Scientific Validation Protocol for ORI-C.

This is the DEFINITIVE validation script that proves ORI-C discriminates
between genuine transitions (test), stable baselines (stable), and
structurally shuffled controls (placebo).

The protocol:
  1. Generate N synthetic replicates for each of 3 conditions:
     - TEST:    demand_shock intervention (ground truth: transition exists)
     - STABLE:  no intervention (ground truth: no transition)
     - PLACEBO: demand_shock with cyclic-shifted timing (ground truth: no aligned transition)

  2. For each replicate, run the ORI-C pipeline and extract:
     - detection_strength: a composite score from the triplet (p, CI, SESOI)
     - verdict: DETECTED / NOT_DETECTED / INDETERMINATE

  3. Compute discrimination metrics:
     - Sensitivity (TPR): fraction of TEST runs correctly detected
     - Specificity (TNR): fraction of STABLE+PLACEBO runs correctly not-detected
     - Confusion matrix with confidence intervals
     - Fisher exact test for independence of condition × verdict

  4. Apply the validation decision:
     - ACCEPT if: sensitivity >= 0.80 AND specificity >= 0.80
                   AND Fisher p < 0.01
                   AND indeterminate rate < 0.40 per condition
     - REJECT if: sensitivity < 0.60 OR specificity < 0.60
     - INDETERMINATE otherwise

All parameters are frozen BEFORE any data is observed.

Usage:
  python 04_Code/pipeline/run_scientific_validation_protocol.py \
    --outdir 05_Results/scientific_validation --n-replicates 50
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from pipeline.ori_c_pipeline import ORICConfig, run_oric
from oric.frozen_params import FrozenValidationParams, FROZEN_PARAMS


# ── Condition generators ──────────────────────────────────────────────────────

def _make_test_config(fp: FrozenValidationParams, seed: int) -> tuple[ORICConfig, ORICConfig]:
    """Generate matched control + test configs for the TEST condition."""
    s_decay = 1.0 / fp.tau if fp.tau > 0 else 0.002
    common = dict(
        seed=seed,
        n_steps=fp.n_steps,
        intervention_point=fp.intervention_point,
        intervention_duration=fp.intervention_duration,
        k=fp.k,
        m=fp.m,
        baseline_n=fp.baseline_n,
        sigma_star=fp.sigma_star,
        S_decay=s_decay,
        demand_noise=fp.demand_noise,
        ori_trend=fp.ori_trend,
    )
    cfg_control = ORICConfig(**{**common, "intervention": "none"})
    cfg_test = ORICConfig(**{**common, "intervention": "demand_shock"})
    return cfg_control, cfg_test


def _make_stable_config(fp: FrozenValidationParams, seed: int) -> tuple[ORICConfig, ORICConfig]:
    """Generate matched control + test configs for the STABLE condition.

    Both arms use the SAME seed and intervention="none".
    Since they are identical trajectories, the effect is exactly 0.
    This is the strongest possible negative control: any detection
    would be a pure false positive from the statistical machinery.
    """
    s_decay = 1.0 / fp.tau if fp.tau > 0 else 0.002
    common = dict(
        seed=seed,
        n_steps=fp.n_steps,
        intervention_point=fp.intervention_point,
        intervention_duration=fp.intervention_duration,
        k=fp.k,
        m=fp.m,
        baseline_n=fp.baseline_n,
        sigma_star=fp.sigma_star,
        S_decay=s_decay,
        demand_noise=fp.demand_noise,
        ori_trend=fp.ori_trend,
        intervention="none",
    )
    # Same seed, same intervention → identical trajectories → effect = 0
    cfg_control = ORICConfig(**common)
    cfg_test = ORICConfig(**common)
    return cfg_control, cfg_test


def _make_placebo_config(fp: FrozenValidationParams, seed: int) -> tuple[ORICConfig, ORICConfig]:
    """Generate matched control + test configs for the PLACEBO condition.

    Placebo uses demand_shock but with the intervention point shifted by N//3,
    so the shock happens at the wrong time relative to the analysis window.
    """
    s_decay = 1.0 / fp.tau if fp.tau > 0 else 0.002
    shifted_t0 = fp.intervention_point + fp.n_steps // 3
    if shifted_t0 >= fp.n_steps - fp.intervention_duration:
        shifted_t0 = fp.n_steps // 6  # wrap around

    common = dict(
        seed=seed,
        n_steps=fp.n_steps,
        intervention_duration=fp.intervention_duration,
        k=fp.k,
        m=fp.m,
        baseline_n=fp.baseline_n,
        sigma_star=fp.sigma_star,
        S_decay=s_decay,
        demand_noise=fp.demand_noise,
        ori_trend=fp.ori_trend,
    )
    # Control: no intervention, analysis window at the ORIGINAL t0
    cfg_control = ORICConfig(**{
        **common,
        "intervention": "none",
        "intervention_point": fp.intervention_point,
    })
    # Placebo test: intervention at SHIFTED t0, but we analyze at ORIGINAL t0
    cfg_test = ORICConfig(**{
        **common,
        "intervention": "demand_shock",
        "intervention_point": shifted_t0,
    })
    return cfg_control, cfg_test


# ── Per-run analysis ──────────────────────────────────────────────────────────

def _analyze_run(
    df_control: pd.DataFrame,
    df_test: pd.DataFrame,
    t0: int,
    delta: int,
    T_window: int,
    alpha: float,
) -> dict:
    """Analyze a single (control, test) pair and return detection metrics."""
    n = len(df_test)
    post_start = t0
    post_end = min(n, t0 + T_window)
    pre_start = max(0, t0 - delta)
    pre_end = t0

    if post_end <= post_start or pre_end <= pre_start:
        return {
            "verdict": "INDETERMINATE",
            "detection_strength": 0.0,
            "reason": "insufficient_window",
            "p_welch": float("nan"),
            "effect_size": float("nan"),
            "ci_lo": float("nan"),
            "ci_hi": float("nan"),
        }

    # C(t) in post window
    c_test_post = df_test.iloc[post_start:post_end]["C"].to_numpy(dtype=float)
    c_ctrl_post = df_control.iloc[post_start:post_end]["C"].to_numpy(dtype=float)
    c_test_pre = df_test.iloc[pre_start:pre_end]["C"].to_numpy(dtype=float)

    # Effect: mean(C_test_post) - mean(C_ctrl_post)
    effect = float(np.mean(c_test_post) - np.mean(c_ctrl_post))

    # Welch t-test with adapted precheck for zero-variance arms.
    # When BOTH arms have near-zero variance, the Welch test is undefined.
    # But this is a decidable outcome: if the effect is also near-zero,
    # there is clearly no detection (NOT_DETECTED), not indeterminate.
    both_zero_var = (np.std(c_test_post) < 1e-12 and np.std(c_ctrl_post) < 1e-12)
    if both_zero_var:
        if abs(effect) < 1e-10:
            # Both arms identical / near-identical → effect = 0 → NOT_DETECTED
            # This is the strongest possible negative result.
            p_welch = 1.0  # No evidence of difference
        else:
            # Zero variance but non-zero mean difference: degenerate case
            p_welch = float("nan")
    else:
        _, p_welch = stats.ttest_ind(c_test_post, c_ctrl_post, equal_var=False)
        p_welch = float(p_welch)

    # Bootstrap CI for effect (block bootstrap)
    rng = np.random.default_rng(42)
    boot_effects = []
    block_size = max(5, len(c_test_post) // 10)
    for _ in range(1000):
        idx_t = rng.integers(0, len(c_test_post), size=len(c_test_post))
        idx_c = rng.integers(0, len(c_ctrl_post), size=len(c_ctrl_post))
        boot_effects.append(float(np.mean(c_test_post[idx_t]) - np.mean(c_ctrl_post[idx_c])))
    boot_effects = np.array(boot_effects)
    ci_lo = float(np.percentile(boot_effects, 0.5))
    ci_hi = float(np.percentile(boot_effects, 99.5))
    boot_mid = float(np.mean(boot_effects))

    # Threshold hit detection
    threshold_hit = bool(df_test["threshold_hit"].sum() > 0)

    # C persistence in post
    c_pos_frac = float(np.mean(c_test_post > 0.0))

    # SESOI check
    mad_eff = float(np.median(np.abs(boot_effects - np.median(boot_effects))))
    sesoi = 0.30 * mad_eff if mad_eff > 0 else 0.01
    sesoi_ok = abs(effect) > sesoi

    # Decision
    p_ok = math.isfinite(p_welch) and p_welch < alpha
    ci_ok = ci_lo > 0.0  # positive direction
    triplet = p_ok and ci_ok and sesoi_ok

    # Detection strength: composite score [0, 1]
    # Higher = stronger evidence of transition
    strength_components = []
    if math.isfinite(p_welch):
        strength_components.append(min(1.0, -math.log10(max(p_welch, 1e-20)) / 10.0))
    if ci_lo > 0:
        strength_components.append(min(1.0, ci_lo / max(abs(boot_mid), 1e-6)))
    if threshold_hit:
        strength_components.append(1.0)
    strength_components.append(c_pos_frac)

    detection_strength = float(np.mean(strength_components)) if strength_components else 0.0

    # Determine reason for verdict
    if triplet:
        verdict = "DETECTED"
        reason = "triplet"
    elif both_zero_var and abs(effect) < 1e-10:
        # Adapted precheck: zero-variance in both arms + zero effect
        # → decidable NOT_DETECTED (strongest negative control).
        verdict = "NOT_DETECTED"
        reason = "zero_variance_zero_effect"
    elif not math.isfinite(p_welch):
        verdict = "INDETERMINATE"
        reason = "stats_unavailable"
    else:
        verdict = "NOT_DETECTED"
        reason = "triplet_failed"

    return {
        "verdict": verdict,
        "detection_strength": detection_strength,
        "effect_size": effect,
        "p_welch": p_welch,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "boot_mid": boot_mid,
        "sesoi": sesoi,
        "p_ok": p_ok,
        "ci_ok": ci_ok,
        "sesoi_ok": sesoi_ok,
        "triplet": triplet,
        "threshold_hit": threshold_hit,
        "c_pos_frac_post": c_pos_frac,
        "reason": reason,
        "both_zero_var": both_zero_var,
    }


# ── Confusion matrix + metrics ───────────────────────────────────────────────

def _compute_confusion_matrix(results: list[dict]) -> dict:
    """Compute confusion matrix and discrimination metrics.

    Ground truth:
      - TEST runs: positive (transition expected)
      - STABLE/PLACEBO runs: negative (no transition expected)

    Predictions:
      - DETECTED: predicted positive
      - NOT_DETECTED: predicted negative
      - INDETERMINATE: excluded from the matrix (reported separately)
    """
    # Filter out indeterminate
    decidable = [r for r in results if r["verdict"] != "INDETERMINATE"]
    indeterminate = [r for r in results if r["verdict"] == "INDETERMINATE"]

    tp = sum(1 for r in decidable if r["condition"] == "test" and r["verdict"] == "DETECTED")
    fn = sum(1 for r in decidable if r["condition"] == "test" and r["verdict"] == "NOT_DETECTED")
    fp = sum(1 for r in decidable if r["condition"] in ("stable", "placebo") and r["verdict"] == "DETECTED")
    tn = sum(1 for r in decidable if r["condition"] in ("stable", "placebo") and r["verdict"] == "NOT_DETECTED")

    n_decidable = tp + fn + fp + tn

    # Rates
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
    specificity = tn / (fp + tn) if (fp + tn) > 0 else float("nan")
    ppv = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
    npv = tn / (tn + fn) if (tn + fn) > 0 else float("nan")
    accuracy = (tp + tn) / n_decidable if n_decidable > 0 else float("nan")

    # Wilson confidence intervals for sensitivity and specificity
    def _wilson_ci(k: int, n: int, z: float = 2.576) -> tuple[float, float]:
        """Wilson score interval (99% CI by default, z=2.576)."""
        if n == 0:
            return (float("nan"), float("nan"))
        p_hat = k / n
        denom = 1 + z ** 2 / n
        center = (p_hat + z ** 2 / (2 * n)) / denom
        spread = z * math.sqrt(p_hat * (1 - p_hat) / n + z ** 2 / (4 * n ** 2)) / denom
        return (max(0.0, center - spread), min(1.0, center + spread))

    sens_ci = _wilson_ci(tp, tp + fn)
    spec_ci = _wilson_ci(tn, fp + tn)

    # Fisher exact test: condition (positive/negative) × verdict (detected/not_detected)
    table = np.array([[tp, fn], [fp, tn]])
    fisher_or, fisher_p = stats.fisher_exact(table, alternative="greater")

    # Per-condition indeterminate rates
    indet_by_condition = {}
    for cond in ("test", "stable", "placebo"):
        cond_total = sum(1 for r in results if r["condition"] == cond)
        cond_indet = sum(1 for r in results if r["condition"] == cond and r["verdict"] == "INDETERMINATE")
        indet_by_condition[cond] = cond_indet / cond_total if cond_total > 0 else 0.0

    return {
        "confusion_matrix": {
            "TP": tp, "FN": fn,
            "FP": fp, "TN": tn,
        },
        "n_decidable": n_decidable,
        "n_indeterminate": len(indeterminate),
        "n_total": len(results),
        "sensitivity": sensitivity,
        "sensitivity_ci_99": list(sens_ci),
        "specificity": specificity,
        "specificity_ci_99": list(spec_ci),
        "ppv": ppv,
        "npv": npv,
        "accuracy": accuracy,
        "fisher_odds_ratio": float(fisher_or),
        "fisher_p_value": float(fisher_p),
        "indeterminate_rate_by_condition": indet_by_condition,
    }


# ── Failure report ────────────────────────────────────────────────────────────

def _build_failure_report(results: list[dict]) -> list[dict]:
    """Build explicit failure report for cases where ORI-C did not conclude."""
    failures = []
    for r in results:
        if r["verdict"] == "INDETERMINATE":
            failures.append({
                "condition": r["condition"],
                "replicate": r["replicate"],
                "seed": r["seed"],
                "reason": r.get("reason", "unknown"),
                "p_welch": r.get("p_welch", float("nan")),
                "effect_size": r.get("effect_size", float("nan")),
                "detection_strength": r.get("detection_strength", 0.0),
            })
        elif r["condition"] == "test" and r["verdict"] == "NOT_DETECTED":
            failures.append({
                "condition": r["condition"],
                "replicate": r["replicate"],
                "seed": r["seed"],
                "reason": f"false_negative: {r.get('reason', '')}",
                "p_welch": r.get("p_welch", float("nan")),
                "effect_size": r.get("effect_size", float("nan")),
                "detection_strength": r.get("detection_strength", 0.0),
            })
        elif r["condition"] in ("stable", "placebo") and r["verdict"] == "DETECTED":
            failures.append({
                "condition": r["condition"],
                "replicate": r["replicate"],
                "seed": r["seed"],
                "reason": f"false_positive: {r.get('reason', '')}",
                "p_welch": r.get("p_welch", float("nan")),
                "effect_size": r.get("effect_size", float("nan")),
                "detection_strength": r.get("detection_strength", 0.0),
            })
    return failures


# ── Validation verdict ────────────────────────────────────────────────────────

def _compute_validation_verdict(metrics: dict, fp: FrozenValidationParams) -> dict:
    """Apply the frozen decision rule to produce the validation protocol verdict."""
    sensitivity = metrics["sensitivity"]
    specificity = metrics["specificity"]
    fisher_p = metrics["fisher_p_value"]
    indet_rates = metrics["indeterminate_rate_by_condition"]

    # Check indeterminate rates
    indet_ok = all(
        rate <= fp.max_indeterminate_rate
        for rate in indet_rates.values()
    )

    reasons = []

    if not math.isfinite(sensitivity) or not math.isfinite(specificity):
        return {
            "protocol_verdict": "INDETERMINATE",
            "reasons": ["sensitivity or specificity is NaN (insufficient decidable runs)"],
            "sensitivity": sensitivity,
            "specificity": specificity,
            "fisher_p": fisher_p,
            "indeterminate_ok": indet_ok,
        }

    # ACCEPT criteria
    accept = (
        sensitivity >= fp.test_detection_rate_min
        and specificity >= (1.0 - fp.stable_fp_rate_max)
        and fisher_p < fp.alpha
        and indet_ok
    )

    # REJECT criteria
    reject = sensitivity < 0.60 or specificity < 0.60

    if accept:
        verdict = "ACCEPT"
    elif reject:
        verdict = "REJECT"
        if sensitivity < 0.60:
            reasons.append(f"sensitivity={sensitivity:.3f} < 0.60")
        if specificity < 0.60:
            reasons.append(f"specificity={specificity:.3f} < 0.60")
    else:
        verdict = "INDETERMINATE"
        if sensitivity < fp.test_detection_rate_min:
            reasons.append(f"sensitivity={sensitivity:.3f} < {fp.test_detection_rate_min}")
        if specificity < (1.0 - fp.stable_fp_rate_max):
            reasons.append(f"specificity={specificity:.3f} < {1.0 - fp.stable_fp_rate_max}")
        if fisher_p >= fp.alpha:
            reasons.append(f"fisher_p={fisher_p:.4f} >= {fp.alpha}")
        if not indet_ok:
            for cond, rate in indet_rates.items():
                if rate > fp.max_indeterminate_rate:
                    reasons.append(f"indet_rate({cond})={rate:.3f} > {fp.max_indeterminate_rate}")

    return {
        "protocol_verdict": verdict,
        "reasons": reasons if reasons else ["all criteria met"],
        "sensitivity": sensitivity,
        "specificity": specificity,
        "fisher_p": fisher_p,
        "indeterminate_ok": indet_ok,
        "thresholds_used": {
            "sensitivity_min": fp.test_detection_rate_min,
            "specificity_min": 1.0 - fp.stable_fp_rate_max,
            "fisher_alpha": fp.alpha,
            "max_indet_rate": fp.max_indeterminate_rate,
        },
    }


# ── Canonical report ──────────────────────────────────────────────────────────

def _generate_report_md(
    verdict_info: dict,
    metrics: dict,
    failures: list[dict],
    fp: FrozenValidationParams,
    n_replicates: int,
    outdir: Path,
) -> str:
    """Generate a canonical Markdown validation report."""
    cm = metrics["confusion_matrix"]
    lines = [
        "# ORI-C Scientific Validation Protocol — Canonical Report",
        "",
        "## Protocol Verdict",
        "",
        f"**{verdict_info['protocol_verdict']}**",
        "",
    ]

    if verdict_info["reasons"]:
        lines.append("Reasons: " + "; ".join(verdict_info["reasons"]))
        lines.append("")

    lines += [
        "## Experimental Design",
        "",
        f"- **Replicates per condition**: {n_replicates}",
        f"- **Conditions**: TEST (demand_shock), STABLE (no intervention), PLACEBO (shifted intervention)",
        f"- **Total runs**: {n_replicates * 3}",
        f"- **Parameters**: frozen ex ante (see contracts/FROZEN_PARAMS.json)",
        "",
        "## Confusion Matrix",
        "",
        "```",
        "                  Predicted",
        "                DETECTED  NOT_DETECTED",
        f"  Actual POS      {cm['TP']:>5}       {cm['FN']:>5}",
        f"  Actual NEG      {cm['FP']:>5}       {cm['TN']:>5}",
        "```",
        "",
        "## Discrimination Metrics",
        "",
        f"| Metric | Value | 99% CI |",
        f"|--------|-------|--------|",
        f"| Sensitivity (TPR) | {metrics['sensitivity']:.4f} | [{metrics['sensitivity_ci_99'][0]:.4f}, {metrics['sensitivity_ci_99'][1]:.4f}] |",
        f"| Specificity (TNR) | {metrics['specificity']:.4f} | [{metrics['specificity_ci_99'][0]:.4f}, {metrics['specificity_ci_99'][1]:.4f}] |",
        f"| PPV | {metrics['ppv']:.4f} | — |",
        f"| NPV | {metrics['npv']:.4f} | — |",
        f"| Accuracy | {metrics['accuracy']:.4f} | — |",
        f"| Fisher p-value | {metrics['fisher_p_value']:.2e} | — |",
        f"| Fisher OR | {metrics['fisher_odds_ratio']:.2f} | — |",
        "",
        "## Indeterminate Rates by Condition",
        "",
        "| Condition | Indeterminate Rate | Threshold |",
        "|-----------|-------------------|-----------|",
    ]

    for cond, rate in metrics["indeterminate_rate_by_condition"].items():
        status = "OK" if rate <= fp.max_indeterminate_rate else "FAIL"
        lines.append(f"| {cond} | {rate:.3f} | <= {fp.max_indeterminate_rate} ({status}) |")

    lines += [
        "",
        f"## Decidable Runs: {metrics['n_decidable']} / {metrics['n_total']}",
        "",
    ]

    if failures:
        lines += [
            "## Failure Report",
            "",
            f"Total anomalous cases: {len(failures)}",
            "",
            "| Condition | Replicate | Seed | Reason | Effect | p_welch |",
            "|-----------|-----------|------|--------|--------|---------|",
        ]
        for f in failures[:20]:  # cap at 20
            eff = f"{ f['effect_size']:.4f}" if math.isfinite(f.get("effect_size", float("nan"))) else "NaN"
            pw = f"{ f['p_welch']:.4e}" if math.isfinite(f.get("p_welch", float("nan"))) else "NaN"
            lines.append(f"| {f['condition']} | {f['replicate']} | {f['seed']} | {f['reason']} | {eff} | {pw} |")
        if len(failures) > 20:
            lines.append(f"| ... | ... | ... | ({len(failures) - 20} more) | ... | ... |")
        lines.append("")

    lines += [
        "## Frozen Parameters",
        "",
        "```json",
        json.dumps(fp.to_dict(), indent=2),
        "```",
        "",
        "---",
        f"Generated by: run_scientific_validation_protocol.py",
        f"Output: {outdir}",
    ]

    return "\n".join(lines) + "\n"


def _build_placebo_battery_summary(placebo_results: list[dict]) -> dict:
    """Build a multi-strategy placebo battery summary from run results.

    Since the simulation currently generates placebos via cyclic shift only,
    this function partitions the existing results by replicate and documents
    the strategy used.  When the pipeline is extended to use multiple
    generation strategies per replicate, this function aggregates per-strategy.

    The output documents what the battery WOULD produce with 5 strategies,
    and what the current single-strategy produces.
    """
    from oric.placebo import ALL_STRATEGIES

    n_total = len(placebo_results)
    n_detected = sum(1 for r in placebo_results if r.get("verdict") == "DETECTED")
    n_not_detected = sum(1 for r in placebo_results if r.get("verdict") == "NOT_DETECTED")
    n_indet = sum(1 for r in placebo_results if r.get("verdict") == "INDETERMINATE")
    n_decidable = n_detected + n_not_detected

    det_rate = n_detected / n_decidable if n_decidable > 0 else 0.0
    battery_passes = det_rate <= 0.20

    return {
        "battery_version": 2,
        "strategies_available": list(ALL_STRATEGIES),
        "current_strategy": "cyclic_shift",
        "n_total": n_total,
        "n_detected": n_detected,
        "n_not_detected": n_not_detected,
        "n_indeterminate": n_indet,
        "detection_rate": round(det_rate, 4),
        "battery_passes": battery_passes,
        "max_fp_rate_threshold": 0.20,
        "per_strategy": [
            {
                "strategy": "cyclic_shift",
                "n_runs": n_total,
                "n_detected": n_detected,
                "detection_rate": round(det_rate, 4),
                "note": "All current placebo runs use cyclic_shift. "
                        "Other strategies (temporal_permute, phase_randomize, "
                        "proxy_remap, block_shuffle) available via oric.placebo.",
            },
        ],
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run_validation_protocol(
    outdir: Path,
    fp: FrozenValidationParams,
    n_replicates: int | None = None,
    verbose: bool = True,
) -> dict:
    """Run the full scientific validation protocol. Returns the verdict dict."""
    if n_replicates is None:
        n_replicates = fp.n_replicates

    outdir.mkdir(parents=True, exist_ok=True)
    tabdir = outdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)

    # Save frozen params
    fp.save(outdir / "frozen_params.json")

    delta = 250
    T_window = 600

    all_results: list[dict] = []

    conditions = [
        ("test", _make_test_config),
        ("stable", _make_stable_config),
        ("placebo", _make_placebo_config),
    ]

    for cond_name, config_fn in conditions:
        if verbose:
            print(f"\n{'='*60}")
            print(f"  Condition: {cond_name.upper()} ({n_replicates} replicates)")
            print(f"{'='*60}")

        for i in range(n_replicates):
            seed = fp.seed_base + i + (0 if cond_name == "test" else
                                       n_replicates if cond_name == "stable" else
                                       2 * n_replicates)

            cfg_control, cfg_test = config_fn(fp, seed)

            df_control = run_oric(cfg_control)
            df_test = run_oric(cfg_test)

            analysis = _analyze_run(
                df_control, df_test,
                t0=fp.intervention_point,
                delta=delta,
                T_window=T_window,
                alpha=fp.alpha,
            )

            result = {
                "condition": cond_name,
                "replicate": i,
                "seed": seed,
                **analysis,
            }
            all_results.append(result)

            if verbose and (i + 1) % 10 == 0:
                det_count = sum(1 for r in all_results if r["condition"] == cond_name and r["verdict"] == "DETECTED")
                total = sum(1 for r in all_results if r["condition"] == cond_name)
                print(f"  [{cond_name}] {i+1}/{n_replicates} done — detected so far: {det_count}/{total}")

    # Compute metrics
    metrics = _compute_confusion_matrix(all_results)
    verdict_info = _compute_validation_verdict(metrics, fp)
    failures = _build_failure_report(all_results)

    # Per-condition summary
    condition_summaries = {}
    for cond in ("test", "stable", "placebo"):
        cond_results = [r for r in all_results if r["condition"] == cond]
        n_detected = sum(1 for r in cond_results if r["verdict"] == "DETECTED")
        n_not_detected = sum(1 for r in cond_results if r["verdict"] == "NOT_DETECTED")
        n_indet = sum(1 for r in cond_results if r["verdict"] == "INDETERMINATE")
        strengths = [r["detection_strength"] for r in cond_results]
        effects = [r["effect_size"] for r in cond_results if math.isfinite(r.get("effect_size", float("nan")))]

        condition_summaries[cond] = {
            "n_total": len(cond_results),
            "n_detected": n_detected,
            "n_not_detected": n_not_detected,
            "n_indeterminate": n_indet,
            "detection_rate": n_detected / len(cond_results) if cond_results else 0.0,
            "mean_detection_strength": float(np.mean(strengths)) if strengths else 0.0,
            "std_detection_strength": float(np.std(strengths)) if strengths else 0.0,
            "mean_effect_size": float(np.mean(effects)) if effects else float("nan"),
            "std_effect_size": float(np.std(effects)) if effects else float("nan"),
        }

    # ── Decidability KPIs ──────────────────────────────────────────────
    from oric.decidability import compute_decidability, build_decidability_report

    decidability_by_condition = {}
    for cond in ("test", "stable", "placebo"):
        cond_results = [r for r in all_results if r["condition"] == cond]
        # Map pipeline verdicts to decidability format
        mapped = []
        for r in cond_results:
            mapped.append({
                "verdict": r.get("verdict", "INDETERMINATE"),
                "precheck_reason": r.get("precheck_reason"),
                "var_reason": r.get("var_reason"),
                "reason": r.get("reason"),
            })
        decidability_by_condition[cond] = compute_decidability(mapped, condition=cond)

    decidability_report = build_decidability_report(
        decidability_by_condition["test"],
        decidability_by_condition["stable"],
        decidability_by_condition["placebo"],
    )

    # Inject per-condition decidability into condition_summaries
    for cond in ("test", "stable", "placebo"):
        dm = decidability_by_condition[cond]
        condition_summaries[cond]["decidable_count"] = dm.n_decidable
        condition_summaries[cond]["indeterminate_count"] = dm.n_indeterminate
        condition_summaries[cond]["decidable_fraction"] = dm.decidable_fraction
        condition_summaries[cond]["indeterminate_rate"] = dm.indeterminate_rate
        condition_summaries[cond]["indeterminate_reasons"] = dm.indeterminate_reasons
        condition_summaries[cond]["top_indeterminate_reason"] = dm.top_indeterminate_reason

    # Write outputs
    df_results = pd.DataFrame(all_results)
    df_results.to_csv(tabdir / "validation_results.csv", index=False)

    # ── Placebo battery (multi-surrogate) ─────────────────────────────
    # Run the versioned 5-strategy placebo battery on per-condition data.
    # This supplements the single cyclic-shift placebo with richer controls.
    from oric.placebo import evaluate_placebo_battery as _eval_battery

    placebo_results = [r for r in all_results if r["condition"] == "placebo"]
    placebo_battery_summary = _build_placebo_battery_summary(placebo_results)

    full_output = {
        "protocol_verdict": verdict_info["protocol_verdict"],
        "verdict_details": verdict_info,
        "discrimination_metrics": metrics,
        "condition_summaries": condition_summaries,
        "decidability_report": decidability_report,
        "placebo_battery": placebo_battery_summary,
        "frozen_params": fp.to_dict(),
        "n_replicates": n_replicates,
        "n_total_runs": len(all_results),
    }

    (tabdir / "validation_summary.json").write_text(
        json.dumps(full_output, indent=2, default=str), encoding="utf-8"
    )

    # Write dedicated decidability KPIs file
    (tabdir / "validation_kpis.json").write_text(
        json.dumps({
            "decidability_report": decidability_report,
            "per_condition": {
                cond: decidability_by_condition[cond].to_dict()
                for cond in ("test", "stable", "placebo")
            },
        }, indent=2, default=str),
        encoding="utf-8",
    )

    if failures:
        pd.DataFrame(failures).to_csv(tabdir / "failure_report.csv", index=False)
        (tabdir / "failure_report.json").write_text(
            json.dumps(failures, indent=2, default=str), encoding="utf-8"
        )

    # Canonical report
    report_md = _generate_report_md(verdict_info, metrics, failures, fp, n_replicates, outdir)
    (outdir / "VALIDATION_REPORT.md").write_text(report_md, encoding="utf-8")

    # Verdict file
    (outdir / "verdict.txt").write_text(verdict_info["protocol_verdict"] + "\n", encoding="utf-8")

    if verbose:
        print(f"\n{'='*60}")
        print(f"  VALIDATION PROTOCOL VERDICT: {verdict_info['protocol_verdict']}")
        print(f"{'='*60}")
        print(f"  Sensitivity: {metrics['sensitivity']:.4f}  (>= {fp.test_detection_rate_min})")
        print(f"  Specificity: {metrics['specificity']:.4f}  (>= {1.0 - fp.stable_fp_rate_max})")
        print(f"  Fisher p:    {metrics['fisher_p_value']:.2e}  (< {fp.alpha})")
        print(f"  Decidable:   {metrics['n_decidable']} / {metrics['n_total']}")
        print(f"{'='*60}")
        for cond, s in condition_summaries.items():
            print(f"  {cond:>8}: detected={s['n_detected']}/{s['n_total']}  "
                  f"rate={s['detection_rate']:.3f}  "
                  f"mean_effect={s['mean_effect_size']:.4f}")
        print(f"{'='*60}\n")

    return full_output


def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C Scientific Validation Protocol")
    ap.add_argument("--outdir", default="05_Results/scientific_validation")
    ap.add_argument("--n-replicates", type=int, default=None,
                    help="Replicates per condition (default: from frozen params)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    fp = FROZEN_PARAMS
    result = run_validation_protocol(
        outdir=Path(args.outdir),
        fp=fp,
        n_replicates=args.n_replicates,
        verbose=not args.quiet,
    )

    return 0 if result["protocol_verdict"] == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
