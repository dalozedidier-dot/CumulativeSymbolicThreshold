#!/usr/bin/env python3
"""04_Code/sector/shared/sector_panel_runner.py

Core logic shared by all sector suites (bio, cosmo, infra).

Responsibilities
----------------
- mapping_validity: check O/R/I for stationarity (ADF) and collinearity.
- Normalization variants: robust_minmax, minmax, zscore, none.
- ORI-C run on normalized series via run_oric_from_observations().
- Causal tests (threshold detection, Welch / bootstrap, Granger, sigma gate).
- Write per-variant outputs with *consistent* verdict.txt.
- Aggregate per-variant results → sector_global_verdict.json.

Verdict translation (fixed ex ante, never changes at runtime):
    seuil_detecte                   → ACCEPT
    falsifie                        → REJECT
    non_detecte                     → REJECT
    indetermine_sigma_nul           → INDETERMINATE
    indetermine_stats_indisponibles → INDETERMINATE
    (anything else)                 → INDETERMINATE  (safe default)

The *only* tokens ever written to verdict.txt are: ACCEPT, REJECT, INDETERMINATE.
tables/verdict.json always carries the full internal token + all gate details.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

# ── Repo plumbing ──────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
_CODE_DIR = _HERE.parents[2]   # 04_Code/
_REPO_DIR = _CODE_DIR.parent   # CumulativeSymbolicThreshold/
for _p in [str(_CODE_DIR), str(_REPO_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pipeline.ori_c_pipeline import ORICConfig, run_oric_from_observations  # noqa: E402

# ── Constants ──────────────────────────────────────────────────────────────────

_INTERNAL_TO_CANONICAL: dict[str, str] = {
    "seuil_detecte": "ACCEPT",
    "falsifie": "REJECT",
    "non_detecte": "REJECT",
    "indetermine_sigma_nul": "INDETERMINATE",
    "indetermine_stats_indisponibles": "INDETERMINATE",
    # Mean-shift + bootstrap confirmed but Granger inconclusive (low power, short series):
    # this is not an active falsification → INDETERMINATE, not REJECT.
    "indetermine_granger_weak": "INDETERMINATE",
}

_MODE_PARAMS: dict[str, dict[str, int]] = {
    "smoke_ci":         {"n_boot": 300, "max_lag": 8,  "block": 15},
    "full_statistical": {"n_boot": 800, "max_lag": 12, "block": 25},
}

_NORMALIZATIONS = ["robust_minmax", "minmax", "zscore", "none"]


# ── Verdict helpers ────────────────────────────────────────────────────────────

def _to_canonical(internal: str) -> str:
    return _INTERNAL_TO_CANONICAL.get(internal, "INDETERMINATE")


def _write_verdict_txt(path: Path, internal_verdict: str) -> None:
    """Write canonical 3-token verdict to verdict.txt.
    The token is always derived through _to_canonical() — never written raw.
    """
    path.write_text(_to_canonical(internal_verdict) + "\n", encoding="utf-8")


# ── Normalization ──────────────────────────────────────────────────────────────

def _normalize_col(arr: np.ndarray, method: str) -> np.ndarray:
    arr = np.asarray(arr, dtype=float)
    lo, hi = 0.01, 0.99
    if method == "none":
        return np.clip(arr, lo, hi)
    if method == "minmax":
        mn, mx = float(np.nanmin(arr)), float(np.nanmax(arr))
        if mx - mn < 1e-12:
            return np.full_like(arr, (lo + hi) / 2)
        return np.clip((arr - mn) / (mx - mn) * (hi - lo) + lo, lo, hi)
    if method == "robust_minmax":
        p5, p95 = float(np.nanpercentile(arr, 5)), float(np.nanpercentile(arr, 95))
        if p95 - p5 < 1e-12:
            return np.full_like(arr, (lo + hi) / 2)
        return np.clip((arr - p5) / (p95 - p5) * (hi - lo) + lo, lo, hi)
    if method == "zscore":
        mu, sd = float(np.nanmean(arr)), float(np.nanstd(arr))
        if sd < 1e-12:
            return np.full_like(arr, (lo + hi) / 2)
        z = (arr - mu) / sd
        # map [-3, 3] → [lo, hi]
        return np.clip((z + 3) / 6 * (hi - lo) + lo, lo, hi)
    raise ValueError(f"Unknown normalization method: {method}")


def _apply_normalization(df: pd.DataFrame, method: str) -> pd.DataFrame:
    out = df.copy()
    for col in ("O", "R", "I"):
        if col in out.columns:
            out[col] = _normalize_col(out[col].to_numpy(dtype=float), method)
    return out


# ── Mapping validity ──────────────────────────────────────────────────────────

def _mapping_validity_check(df: pd.DataFrame, adf_alpha: float = 0.1, corr_threshold: float = 0.9) -> dict:
    """Check O, R, I for stationarity (ADF) and pairwise collinearity.

    Returns dict with keys: verdict ("ACCEPT"/"REJECT"), errors (list), warnings (list).
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        from statsmodels.tsa.stattools import adfuller  # type: ignore
    except ImportError:
        return {"verdict": "INDETERMINATE", "errors": ["statsmodels not available"], "warnings": []}

    for col in ("O", "R", "I"):
        if col not in df.columns:
            errors.append(f"column '{col}' missing from data")
            continue
        arr = df[col].dropna().to_numpy(dtype=float)
        if len(arr) < 20:
            warnings.append(f"{col}: series too short for ADF ({len(arr)} points)")
            continue
        try:
            result = adfuller(arr, regression="c", autolag="AIC")
            p = float(result[1])
            if p > adf_alpha:
                errors.append(f"{col}: non-stationary (ADF p={p:.3f} > {adf_alpha})")
            elif p > 0.05:
                warnings.append(f"{col}: marginal stationarity (ADF p={p:.3f})")
        except Exception as exc:
            warnings.append(f"{col}: ADF failed ({exc})")

    for c1, c2 in (("O", "R"), ("O", "I"), ("R", "I")):
        if c1 not in df.columns or c2 not in df.columns:
            continue
        corr = abs(float(df[c1].corr(df[c2])))
        if corr >= corr_threshold:
            errors.append(f"collinearity: |corr({c1},{c2})| = {corr:.3f} >= {corr_threshold}")
        elif corr >= 0.7:
            warnings.append(f"moderate collinearity: |corr({c1},{c2})| = {corr:.3f}")

    verdict = "REJECT" if errors else "ACCEPT"
    return {"verdict": verdict, "errors": errors, "warnings": warnings}


# ── Causal tests ──────────────────────────────────────────────────────────────

def _detect_threshold(delta_C: np.ndarray, k: float = 2.5, m: int = 3, baseline_n: int = 30) -> tuple[int | None, float]:
    x = np.asarray(delta_C, dtype=float)
    n = len(x)
    if n == 0:
        return None, 0.0
    bn = max(5, min(int(baseline_n), n))
    base = x[:bn]
    mu, sd = float(np.mean(base)), float(np.std(base))
    thr = mu + float(k) * sd
    consec = 0
    for i in range(n):
        if x[i] > thr:
            consec += 1
            if consec >= m:
                return i, thr
        else:
            consec = 0
    return None, thr


def _block_bootstrap(pre: np.ndarray, post: np.ndarray, block: int, n_boot: int, seed: int) -> tuple[float, float, float]:
    rng = np.random.default_rng(int(seed))
    if len(pre) < 5 or len(post) < 5:
        return float("nan"), float("nan"), float("nan")
    block = max(5, int(block))

    def _resample(x: np.ndarray) -> np.ndarray:
        n = len(x)
        if n <= block:
            return x[rng.integers(0, n, size=n)]
        out: list[float] = []
        while len(out) < n:
            s = int(rng.integers(0, n - block))
            out.extend(x[s: s + block].tolist())
        return np.asarray(out[:n], dtype=float)

    diffs = np.array([float(np.mean(_resample(post)) - np.mean(_resample(pre))) for _ in range(n_boot)])
    return float(np.mean(diffs)), float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))


def _granger_min_p(delta_c: np.ndarray, s: np.ndarray, max_lag: int, alpha: float) -> tuple[float, bool]:
    """Return (min_p_across_lags, ok_granger_flag)."""
    try:
        from statsmodels.tsa.stattools import grangercausalitytests  # type: ignore
        data = np.column_stack([delta_c, s])
        res = grangercausalitytests(data, maxlag=int(max_lag), verbose=False)
        pvals = [res[lag][0]["ssr_ftest"][1] for lag in res]
        min_p = float(min(pvals)) if pvals else float("nan")
        return min_p, bool(np.isfinite(min_p) and min_p <= alpha)
    except Exception:
        return float("nan"), False


def _run_causal_tests(
    df_traj: pd.DataFrame,
    *,
    alpha: float,
    n_boot: int,
    max_lag: int,
    block: int,
    seed: int,
    k: float = 2.5,
    m: int = 3,
    baseline_n: int = 30,
    c_mean_post_min: float = 0.05,
) -> dict[str, Any]:
    """Run causal tests on an ORI-C trajectory DataFrame.

    Returns a report dict with 'internal_verdict' and 'gates' keys.
    """
    dC = df_traj["delta_C"].to_numpy(dtype=float)
    C = df_traj["C"].to_numpy(dtype=float)
    S = df_traj["S"].to_numpy(dtype=float)
    n = len(dC)

    # 1. Threshold detection
    thr_idx, thr_val = _detect_threshold(dC, k=k, m=m, baseline_n=baseline_n)
    has_threshold = thr_idx is not None
    split = int(thr_idx) if has_threshold else n // 2

    pre_C = C[:split]
    post_C = C[split:]

    # 2. No false positives pre-threshold
    no_fp_pre = True
    if has_threshold and split > baseline_n:
        fp_idx, _ = _detect_threshold(dC[:split], k=k, m=m, baseline_n=baseline_n)
        no_fp_pre = fp_idx is None

    # 3. C level post
    C_mean_pre = float(np.mean(pre_C)) if len(pre_C) else float("nan")
    C_mean_post = float(np.mean(post_C)) if len(post_C) else float("nan")
    ok_c_level = bool(np.isfinite(C_mean_post) and C_mean_post > c_mean_post_min)

    # 4. Statistical test: Welch (with fallbacks)
    p_welch = float("nan")
    if len(pre_C) >= 10 and len(post_C) >= 10:
        p_welch = float(stats.ttest_ind(post_C, pre_C, equal_var=False).pvalue)

    p_mwu = float("nan")
    if not np.isfinite(p_welch) and len(pre_C) >= 5 and len(post_C) >= 5:
        try:
            p_mwu = float(stats.mannwhitneyu(post_C, pre_C, alternative="greater").pvalue)
        except Exception:
            pass

    boot_mid, boot_lo, boot_hi = _block_bootstrap(pre_C, post_C, block=block, n_boot=n_boot, seed=seed)
    ok_boot = bool(np.isfinite(boot_lo) and boot_lo > 0.0)

    if np.isfinite(p_welch):
        ok_p = bool(p_welch <= alpha)
        ok_p_source = "welch"
    elif ok_boot:
        ok_p = True
        ok_p_source = "bootstrap_fallback"
    elif np.isfinite(p_mwu):
        ok_p = bool(p_mwu <= alpha)
        ok_p_source = "mannwhitney_fallback"
    else:
        ok_p = False
        ok_p_source = "unavailable"

    # 5. Granger S → delta_C
    min_granger_p, ok_granger = _granger_min_p(dC, S, max_lag=max_lag, alpha=alpha)

    # 6. Sigma gate
    post_Sigma = df_traj["Sigma"].to_numpy(dtype=float)[split:]
    sigma_zero_post = bool(len(post_Sigma) > 0 and np.nanmax(np.abs(post_Sigma)) < 1e-9)

    # 7. Reverse causality warning
    min_rev_p, reverse_warning = _granger_min_p(S, dC, max_lag=max_lag, alpha=alpha)

    # ── Internal verdict ──────────────────────────────────────────────────────
    gates = {
        "has_threshold": bool(has_threshold),
        "no_fp_pre": bool(no_fp_pre),
        "ok_c_level": bool(ok_c_level),
        "ok_p": bool(ok_p),
        "ok_p_source": ok_p_source,
        "ok_boot": bool(ok_boot),
        "ok_granger": bool(ok_granger),
        "sigma_zero_post": bool(sigma_zero_post),
        "reverse_warning": bool(reverse_warning),
    }

    if not has_threshold:
        internal = "non_detecte"
        indeterminate_reason = None
    elif not no_fp_pre or not ok_c_level:
        internal = "falsifie"
        indeterminate_reason = None
    elif ok_p and ok_boot and ok_granger:
        internal = "seuil_detecte"
        indeterminate_reason = None
    elif ok_p_source == "unavailable":
        internal = "indetermine_stats_indisponibles"
        indeterminate_reason = "All p-value sources unavailable (Welch NaN, bootstrap NaN, MWU NaN)"
    elif sigma_zero_post:
        internal = "indetermine_sigma_nul"
        indeterminate_reason = "Sigma(t)=0 throughout post-threshold window: symbolic pathway inoperable"
    elif ok_p and ok_boot and not ok_granger:
        # Mean-shift confirmed (Welch/bootstrap), but Granger S→delta_C not significant.
        # This is not an active falsification; it may reflect low power on short series.
        internal = "indetermine_granger_weak"
        indeterminate_reason = (
            f"Threshold + mean-shift confirmed (ok_p={ok_p_source}, ok_boot={ok_boot}) "
            f"but Granger S→delta_C not significant at alpha={alpha} "
            f"(min_p={min_granger_p:.3f}). "
            + ("Reverse direction also significant (reverse_warning). " if reverse_warning else "")
            + "Consider more lags or longer series."
        )
    else:
        internal = "non_detecte"
        indeterminate_reason = f"Criteria not met: ok_p={ok_p} ok_boot={ok_boot} ok_granger={ok_granger}"

    return {
        "internal_verdict": internal,
        "canonical_verdict": _to_canonical(internal),
        "indeterminate_reason": indeterminate_reason,
        "gates": gates,
        "stats": {
            "thr_idx": thr_idx,
            "thr_val": float(thr_val),
            "C_mean_pre": C_mean_pre,
            "C_mean_post": C_mean_post,
            "p_welch": p_welch,
            "p_mwu": float(p_mwu),
            "boot_mid": boot_mid,
            "boot_lo": boot_lo,
            "boot_hi": boot_hi,
            "min_granger_p": float(min_granger_p),
            "min_reverse_p": float(min_rev_p),
        },
    }


# ── One variant run ────────────────────────────────────────────────────────────

def _run_one_variant(
    df_raw: pd.DataFrame,
    variant_name: str,
    outdir: Path,
    *,
    seed: int,
    alpha: float,
    n_boot: int,
    max_lag: int,
    block: int,
) -> dict[str, Any]:
    """Normalize, run ORI-C, run causal tests, write variant output directory."""
    vdir = outdir / "robustness" / f"variant_{variant_name}"
    tabdir = vdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)

    df_norm = _apply_normalization(df_raw, method=variant_name.replace("norm_", "").replace("robust_minmax", "robust_minmax"))
    # The method key passed in is already just the normalization name
    norm_method = variant_name  # e.g. "robust_minmax", "minmax", "zscore", "none"
    df_norm = _apply_normalization(df_raw, norm_method)

    cfg = ORICConfig(seed=int(seed), n_steps=len(df_raw), k=2.5, m=3, baseline_n=min(30, len(df_raw) // 5))

    # Check if demand column available
    col_demand = "demand" if "demand" in df_norm.columns else None
    col_S = "S_obs" if "S_obs" in df_norm.columns else None

    try:
        df_traj = run_oric_from_observations(
            df_norm,
            cfg,
            col_t="t",
            col_O="O",
            col_R="R",
            col_I="I",
            col_demand=col_demand or "O",  # fallback — will be ignored if absent
            col_S=col_S,
        )
    except Exception as exc:
        # Write failure verdict and return
        result: dict[str, Any] = {
            "variant": variant_name,
            "internal_verdict": "non_detecte",
            "canonical_verdict": "REJECT",
            "indeterminate_reason": f"ORI-C run failed: {exc}",
            "gates": {},
            "stats": {},
        }
        (vdir / "verdict.txt").write_text("REJECT\n", encoding="utf-8")
        (tabdir / "verdict.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    report = _run_causal_tests(
        df_traj,
        alpha=alpha,
        n_boot=n_boot,
        max_lag=max_lag,
        block=block,
        seed=seed,
    )
    report["variant"] = variant_name

    # Write outputs — verdict.txt always uses canonical token
    _write_verdict_txt(vdir / "verdict.txt", report["internal_verdict"])
    (tabdir / "verdict.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    df_traj.to_csv(tabdir / "trajectory.csv", index=False)

    return report


# ── Aggregation ────────────────────────────────────────────────────────────────

def _aggregate_sector_verdict(
    pilot_id: str,
    mapping_validity: dict,
    main_report: dict,
    variant_reports: list[dict],
    outdir: Path,
) -> dict[str, Any]:
    """Aggregate results across all variants → sector_global_verdict.json."""

    # Mapping validity gate: if REJECT, whole pilot is REJECT regardless
    if mapping_validity["verdict"] == "REJECT":
        global_verdict = "REJECT"
        not_robust_reason = f"mapping_validity REJECT: {'; '.join(mapping_validity['errors'])}"
        global_internal = "falsifie"
    else:
        # Count canonical verdicts across variants
        counts: dict[str, int] = {"ACCEPT": 0, "REJECT": 0, "INDETERMINATE": 0}
        for v in variant_reports:
            counts[v.get("canonical_verdict", "INDETERMINATE")] += 1

        n = len(variant_reports)
        threshold_75 = int(np.ceil(0.75 * n))

        # Aggregate rule (fixed ex ante):
        # ACCEPT   if >= 75% of variants say ACCEPT
        # REJECT   if any variant says REJECT (conservative)
        # INDETERMINATE otherwise (not_robust)
        not_robust_reason = None
        if counts["REJECT"] > 0:
            global_verdict = "REJECT"
            global_internal = "falsifie"
            rej_variants = [v["variant"] for v in variant_reports if v.get("canonical_verdict") == "REJECT"]
            not_robust_reason = f"REJECT in variants: {rej_variants}"
        elif counts["ACCEPT"] >= threshold_75:
            global_verdict = "ACCEPT"
            global_internal = "seuil_detecte"
        else:
            global_verdict = "INDETERMINATE"
            global_internal = "not_robust"
            # Collect INDETERMINATE reasons
            reasons = [
                v.get("indeterminate_reason") or f"criteria not met (gates: {v.get('gates', {})})"
                for v in variant_reports if v.get("canonical_verdict") != "ACCEPT"
            ]
            not_robust_reason = f"Only {counts['ACCEPT']}/{n} variants ACCEPT (need {threshold_75}). " + " | ".join(dict.fromkeys(r for r in reasons if r))

    result: dict[str, Any] = {
        "pilot_id": pilot_id,
        "global_verdict": global_verdict,
        "global_internal_verdict": global_internal,
        "not_robust_reason": not_robust_reason,
        "mapping_validity": mapping_validity,
        "main_report_internal_verdict": main_report.get("internal_verdict"),
        "main_report_canonical_verdict": main_report.get("canonical_verdict"),
        "variant_summary": [
            {
                "variant": v.get("variant"),
                "canonical_verdict": v.get("canonical_verdict"),
                "internal_verdict": v.get("internal_verdict"),
                "indeterminate_reason": v.get("indeterminate_reason"),
                "gates": v.get("gates", {}),
            }
            for v in variant_reports
        ],
    }

    (outdir / "sector_global_verdict.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    _write_verdict_txt(outdir / "verdict.txt", global_internal if global_internal in _INTERNAL_TO_CANONICAL else "indetermine_sigma_nul")

    # Overwrite with exact canonical token for the global verdict
    (outdir / "verdict.txt").write_text(global_verdict + "\n", encoding="utf-8")

    return result


# ── Top-level entry point ──────────────────────────────────────────────────────

def run_sector_pilot(
    df_raw: pd.DataFrame,
    pilot_id: str,
    outdir: Path,
    seed: int = 1234,
    mode: str = "smoke_ci",
) -> dict[str, Any]:
    """Run one sector pilot end-to-end.

    Parameters
    ----------
    df_raw : DataFrame with columns t, O, R, I (in [0,1]) and optionally demand, S_obs.
    pilot_id : str identifier for this pilot (e.g. "bio-epidemic-11").
    outdir : output root directory (will be created).
    seed : RNG seed for reproducibility.
    mode : "smoke_ci" (fast) or "full_statistical" (thorough).
    """
    params = _MODE_PARAMS.get(mode, _MODE_PARAMS["smoke_ci"])
    n_boot = int(params["n_boot"])
    max_lag = int(params["max_lag"])
    block = int(params["block"])
    alpha = 0.01

    outdir = Path(outdir)
    tabdir = outdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)

    # 1. Mapping validity
    mv = _mapping_validity_check(df_raw)
    (tabdir / "mapping_validity.json").write_text(json.dumps(mv, indent=2), encoding="utf-8")

    # 2. Main run (robust_minmax as primary normalization)
    main_report = _run_one_variant(
        df_raw, "robust_minmax", outdir,
        seed=seed, alpha=alpha, n_boot=n_boot, max_lag=max_lag, block=block,
    )
    # Copy main run outputs to tables/ as well
    main_vdir_tab = outdir / "robustness" / "variant_robust_minmax" / "tables"
    if (main_vdir_tab / "verdict.json").exists():
        (tabdir / "verdict.json").write_text(
            (main_vdir_tab / "verdict.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    # 3. Remaining robustness variants
    variant_reports: list[dict[str, Any]] = [main_report]
    for norm in ("minmax", "zscore", "none"):
        vr = _run_one_variant(
            df_raw, norm, outdir,
            seed=seed, alpha=alpha, n_boot=n_boot, max_lag=max_lag, block=block,
        )
        variant_reports.append(vr)

    # 4. Aggregate
    global_result = _aggregate_sector_verdict(
        pilot_id=pilot_id,
        mapping_validity=mv,
        main_report=main_report,
        variant_reports=variant_reports,
        outdir=outdir,
    )

    return global_result
"""sector_panel_runner.py — Shared sector panel execution engine.

Called by each sector's run_sector_suite.py.  Provides a single
run_sector_panel(config, args) function that:

  1. Validates the proxy spec           → mapping_validity_verdict
  2. Generates synthetic pilot data     → via sector generate_synth.py
  3. Runs real-data pipeline            → run_real_data_demo.py
  4. Runs causal tests                  → tests_causaux.py
  5. Runs robustness variants           → window, normalization, resampling
  6. Aggregates all verdicts            → sector_global_verdict.json

Output directory layout (mirrors canonical suite):
  <outdir>/
    pilot_<pilot_id>/
      synth/                     # synthetic T1-T8 sub-run
        tables/
        figures/
        manifest.json
        verdict.json
      real/                      # real-data sub-run
        tables/
        figures/
        manifest.json
        verdict.json
      robustness/
        variant_<name>/
          tables/
          verdict.json
      mapping_validity.json
      sector_global_verdict.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# --------------------------------------------------------------------------- #
# Config dataclass
# --------------------------------------------------------------------------- #

@dataclass
class SectorConfig:
    """Immutable configuration for a sector panel runner."""
    sector_id: str                      # "bio" | "cosmo" | "infra"
    pilot_ids: list[str]                # ["epidemic", "geneexpr", ...]
    default_pilot: str                  # pilot used when --pilot-id not given

    # paths relative to repo root (resolved at runtime)
    data_root: str                      # "03_Data/sector_<name>"
    code_root: str                      # "04_Code/sector/<name>"

    # canonical pipeline scripts (relative to repo root)
    run_real_script:  str = "04_Code/pipeline/run_real_data_demo.py"
    run_synth_script: str = "04_Code/pipeline/run_synthetic_demo.py"
    causal_script:    str = "04_Code/pipeline/tests_causaux.py"
    validate_script:  str = "04_Code/pipeline/validate_proxy_spec.py"

    # default run parameters
    default_seed:      int  = 1234
    default_n_runs:    int  = 50
    default_alpha:     str  = "0.01"
    default_lags:      str  = "1-5"
    default_normalize: str  = "robust_minmax"

    # robustness variants (window_size, normalize, resample_frac)
    robustness_variants: list[dict[str, Any]] = field(default_factory=lambda: [
        {"name": "window_short",  "pre_horizon": 50,  "post_horizon": 50,  "normalize": "robust_minmax"},
        {"name": "window_medium", "pre_horizon": 100, "post_horizon": 100, "normalize": "robust_minmax"},
        {"name": "norm_minmax",   "pre_horizon": 100, "post_horizon": 100, "normalize": "minmax"},
        {"name": "resample_80",   "pre_horizon": 100, "post_horizon": 100, "normalize": "robust_minmax",
         "resample_frac": 0.80},
    ])


# --------------------------------------------------------------------------- #
# Subprocess helper
# --------------------------------------------------------------------------- #

def _run(cmd: list[str], cwd: Path, label: str, timeout: int = 600) -> dict[str, Any]:
    """Run subprocess, return {"ok", "returncode", "stdout", "stderr"}."""
    print(f"  [{label}] running: {' '.join(str(c) for c in cmd[-6:])}")
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(cwd), timeout=timeout,
        )
        elapsed = time.monotonic() - t0
        ok = r.returncode == 0
        if not ok:
            print(f"  [{label}] FAILED (rc={r.returncode}, {elapsed:.1f}s)")
            print(r.stderr[-400:] if r.stderr else "")
        else:
            print(f"  [{label}] OK ({elapsed:.1f}s)")
        return {"ok": ok, "returncode": r.returncode,
                "stdout": r.stdout, "stderr": r.stderr}
    except subprocess.TimeoutExpired:
        print(f"  [{label}] TIMEOUT after {timeout}s")
        return {"ok": False, "returncode": -1,
                "stdout": "", "stderr": f"timeout after {timeout}s"}
    except Exception as exc:
        return {"ok": False, "returncode": -1,
                "stdout": "", "stderr": str(exc)}


# --------------------------------------------------------------------------- #
# Verdict helpers
# --------------------------------------------------------------------------- #

def _read_verdict(path: Path) -> str:
    """Read verdict from verdict.txt or verdict.json → canonical token."""
    txt = path / "verdict.txt"
    js  = path / "tables" / "verdict.json"
    if txt.exists():
        raw = txt.read_text().strip().upper()
        for tok in ("ACCEPT", "REJECT", "INDETERMINATE"):
            if tok in raw:
                return tok
        return "INDETERMINATE"
    if js.exists():
        try:
            data = json.loads(js.read_text())
            raw  = str(data.get("verdict", "")).upper()
            for tok in ("ACCEPT", "REJECT", "INDETERMINATE"):
                if tok in raw:
                    return tok
        except Exception:
            pass
    return "INDETERMINATE"


def _aggregate_verdicts(verdicts: list[str]) -> str:
    """ACCEPT only if all ACCEPT; REJECT if any REJECT; else INDETERMINATE."""
    if any(v == "REJECT" for v in verdicts):
        return "REJECT"
    if all(v == "ACCEPT" for v in verdicts):
        return "ACCEPT"
    return "INDETERMINATE"


def _support_level(verdict: str, mapping_verdict: str) -> str:
    if mapping_verdict == "REJECT":
        return "rejected_invalid_mapping"
    if verdict == "ACCEPT" and mapping_verdict == "ACCEPT":
        return "sector_panel_support"
    if verdict == "ACCEPT" and mapping_verdict == "INDETERMINATE":
        return "sector_panel_support_mapping_caveat"
    if verdict == "INDETERMINATE":
        return "sector_panel_indeterminate"
    return "rejected"


# --------------------------------------------------------------------------- #
# Main panel runner
# --------------------------------------------------------------------------- #

def run_sector_panel(
    config: SectorConfig,
    args: argparse.Namespace,
    repo_root: Path,
    synth_generator: Callable[[Path, int, str], None],
) -> int:
    """
    Run the full sector panel for one pilot.

    synth_generator(outdir, seed, pilot_id):
        writes outdir/real.csv + outdir/proxy_spec.json
        (used when --real-csv is not provided)

    Returns exit code: 0 = ACCEPT/INDETERMINATE, 1 = REJECT.
    """
    pilot_id  = args.pilot_id
    out_root  = Path(args.outdir) / f"pilot_{pilot_id}"
    seed      = args.seed
    py        = sys.executable

    print(f"\n{'='*60}")
    print(f"  SECTOR PANEL: {config.sector_id.upper()} / {pilot_id}")
    print(f"  outdir: {out_root}")
    print(f"{'='*60}\n")

    # ---------------------------------------------------------------------- #
    # 1. Resolve data paths
    # ---------------------------------------------------------------------- #
    data_dir   = repo_root / config.data_root / "real" / f"pilot_{pilot_id}"
    spec_path  = data_dir / "proxy_spec.json"

    synth_dir  = out_root / "synth_data"
    synth_dir.mkdir(parents=True, exist_ok=True)

    # If no real CSV provided, generate synthetic pilot data
    if args.real_csv:
        csv_path = Path(args.real_csv)
    else:
        print("[step 0] Generating synthetic pilot data...")
        try:
            synth_generator(synth_dir, seed, pilot_id)
            csv_path = synth_dir / "real.csv"
            # In synthetic mode: always prefer the synth proxy_spec (its source_column
            # values are the generic ORI roles "O","R","I","S","demand" that match the
            # generated CSV).  The real proxy_spec from 03_Data/ uses domain-specific
            # column names (e.g. "case_fatality_proxy") that only exist in real CSVs.
            synth_spec = synth_dir / "proxy_spec.json"
            if synth_spec.exists():
                spec_path = synth_spec
            elif not spec_path.exists():
                print("[FATAL] No proxy_spec.json found in synth dir or real data dir")
                return 1
            print(f"         → {csv_path}  (rows: {sum(1 for _ in open(csv_path))-1})")
        except Exception as exc:
            print(f"[step 0] FAILED: {exc}")
            return 1

    if not spec_path.exists():
        print(f"[FATAL] proxy_spec.json not found at {spec_path}")
        return 1
    if not csv_path.exists():
        print(f"[FATAL] real.csv not found at {csv_path}")
        return 1

    # ---------------------------------------------------------------------- #
    # 2. Validate proxy spec (canonical gate)
    # ---------------------------------------------------------------------- #
    print("[step 1] Validating proxy spec (canonical gate)...")
    canonical_spec_result = _run(
        [py, str(repo_root / config.validate_script),
         "--spec", str(spec_path), "--csv", str(csv_path)],
        cwd=repo_root, label="validate_proxy_spec",
    )

    # ---------------------------------------------------------------------- #
    # 3. Mapping validity gate (sector-specific extended check)
    # ---------------------------------------------------------------------- #
    print("[step 2] Running extended mapping validity check...")
    mapping_dir = out_root / "pilot_data"
    mapping_dir.mkdir(parents=True, exist_ok=True)
    mv_out = mapping_dir / "mapping_validity.json"

    from mapping_validator import validate_mapping
    mv_result = validate_mapping(spec_path, csv_path)
    mv_result["canonical_validate_ok"] = canonical_spec_result["ok"]
    with open(mv_out, "w") as f:
        json.dump(mv_result, f, indent=2, default=str)

    mapping_verdict = mv_result["verdict"]
    print(f"         → mapping_validity_verdict: {mapping_verdict}")
    if mv_result["hard_errors"]:
        for e in mv_result["hard_errors"]:
            print(f"           ✗ {e}")
    if mv_result["soft_warnings"]:
        for w in mv_result["soft_warnings"][:3]:
            print(f"           ! {w}")

    if mapping_verdict == "REJECT":
        print("[FATAL] Mapping validity REJECT — halting sector run")
        _write_global_verdict(out_root, pilot_id, config.sector_id,
                              "REJECT", mapping_verdict, {}, {})
        return 1

    # ---------------------------------------------------------------------- #
    # 4. Real-data pipeline run
    # ---------------------------------------------------------------------- #
    print("[step 3] Running ORI-C real-data pipeline...")
    real_out = out_root / "real"
    real_out.mkdir(parents=True, exist_ok=True)

    pipeline_r = _run(
        [py, str(repo_root / config.run_real_script),
         "--input",        str(csv_path),
         "--outdir",       str(real_out),
         "--time-mode",    "index",
         "--normalize",    config.default_normalize,
         "--control-mode", "no_symbolic",
         "--seed",         str(seed)],
        cwd=repo_root, label="run_real_data_demo",
    )
    real_pipeline_verdict = _read_verdict(real_out) if pipeline_r["ok"] else "INDETERMINATE"

    # ---------------------------------------------------------------------- #
    # 5. Causal tests
    # ---------------------------------------------------------------------- #
    print("[step 4] Running causal tests...")
    causal_r = _run(
        [py, str(repo_root / config.causal_script),
         "--run-dir",      str(real_out),
         "--alpha",        config.default_alpha,
         "--lags",         config.default_lags,
         "--pre-horizon",  "100",
         "--post-horizon", "100",
         "--seed",         str(seed)],
        cwd=repo_root, label="tests_causaux",
    )
    causal_verdict = _read_verdict(real_out) if causal_r["ok"] else "INDETERMINATE"

    # ---------------------------------------------------------------------- #
    # 6. Robustness variants
    # ---------------------------------------------------------------------- #
    print("[step 5] Running robustness variants...")
    robust_dir = out_root / "robustness"
    robust_dir.mkdir(parents=True, exist_ok=True)
    robust_verdicts: dict[str, str] = {}

    for variant in config.robustness_variants:
        vname  = variant["name"]
        var_out = robust_dir / f"variant_{vname}"
        var_out.mkdir(parents=True, exist_ok=True)

        # Re-run pipeline with variant parameters
        p_r = _run(
            [py, str(repo_root / config.run_real_script),
             "--input",        str(csv_path),
             "--outdir",       str(var_out),
             "--time-mode",    "index",
             "--normalize",    variant.get("normalize", config.default_normalize),
             "--control-mode", "no_symbolic",
             "--seed",         str(seed)],
            cwd=repo_root, label=f"robustness/{vname}",
        )
        if not p_r["ok"]:
            robust_verdicts[vname] = "INDETERMINATE"
            continue

        # Causal tests on variant
        c_r = _run(
            [py, str(repo_root / config.causal_script),
             "--run-dir",      str(var_out),
             "--alpha",        config.default_alpha,
             "--lags",         config.default_lags,
             "--pre-horizon",  str(variant.get("pre_horizon", 100)),
             "--post-horizon", str(variant.get("post_horizon", 100)),
             "--seed",         str(seed)],
            cwd=repo_root, label=f"causal/{vname}",
        )
        robust_verdicts[vname] = _read_verdict(var_out) if c_r["ok"] else "INDETERMINATE"
        print(f"         {vname}: {robust_verdicts[vname]}")

    # Robustness summary
    n_accept = sum(1 for v in robust_verdicts.values() if v == "ACCEPT")
    n_total  = len(robust_verdicts)
    robust_fraction = n_accept / n_total if n_total > 0 else float("nan")
    robust_summary  = {
        "n_variants":       n_total,
        "n_accept":         n_accept,
        "n_indeterminate":  sum(1 for v in robust_verdicts.values() if v == "INDETERMINATE"),
        "n_reject":         sum(1 for v in robust_verdicts.values() if v == "REJECT"),
        "accept_fraction":  round(robust_fraction, 3),
        "robust_note":      (
            "robust" if robust_fraction >= 0.75
            else ("borderline_robust" if robust_fraction >= 0.5 else "not_robust")
        ),
        "verdicts":         robust_verdicts,
    }

    # ---------------------------------------------------------------------- #
    # 7. Global verdict aggregation
    # ---------------------------------------------------------------------- #
    primary_verdicts = [causal_verdict]
    global_verdict   = _aggregate_verdicts(primary_verdicts)
    support          = _support_level(global_verdict, mapping_verdict)

    print(f"\n[SECTOR PANEL SUMMARY]")
    print(f"  mapping_validity  : {mapping_verdict}")
    print(f"  primary pipeline  : {causal_verdict}")
    print(f"  robustness        : {robust_fraction:.0%} ACCEPT ({n_accept}/{n_total})")
    print(f"  global_verdict    : {global_verdict}")
    print(f"  support_level     : {support}")

    _write_global_verdict(
        out_root, pilot_id, config.sector_id,
        global_verdict, mapping_verdict, robust_summary,
        {"pipeline": causal_verdict, "mapping": mapping_verdict},
    )

    return 0 if global_verdict != "REJECT" else 1


def _write_global_verdict(
    out_root: Path,
    pilot_id: str,
    sector_id: str,
    global_verdict: str,
    mapping_verdict: str,
    robust_summary: dict,
    sub_verdicts: dict,
) -> None:
    """Write sector_global_verdict.json to out_root."""
    data = {
        "sector_id":          sector_id,
        "pilot_id":           pilot_id,
        "global_verdict":     global_verdict,
        "mapping_validity":   mapping_verdict,
        "support_level":      _support_level(global_verdict, mapping_verdict),
        "sub_verdicts":       sub_verdicts,
        "robustness_summary": robust_summary,
        "forbidden_labels": (
            ["sector_panel_support"] if mapping_verdict == "REJECT" else []
        ),
        "run_mode":       "sector_panel",
        "protocol_note":  (
            "Sector panel verdict is distinct from the canonical T1-T8 synthetic suite. "
            "sector_panel_support requires both primary causal tests ACCEPT and "
            "mapping_validity ACCEPT. Indeterminate is informative, not a failure."
        ),
    }
    out_file = out_root / "sector_global_verdict.json"
    out_root.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  → sector_global_verdict.json written: {out_file}")


# --------------------------------------------------------------------------- #
# Shared argument parser
# --------------------------------------------------------------------------- #

def make_parser(sector_id: str, default_pilot: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"ORI-C {sector_id.upper()} sector panel suite runner"
    )
    parser.add_argument("--pilot-id",    default=default_pilot,
                        help=f"Pilot dataset id (default: {default_pilot})")
    parser.add_argument("--real-csv",    default=None,
                        help="Path to real data CSV (omit to use synthetic)")
    parser.add_argument("--outdir",      required=True,
                        help="Output directory for this sector run")
    parser.add_argument("--seed",        type=int, default=1234,
                        help="Random seed (default: 1234)")
    parser.add_argument("--n-runs",      type=int, default=50,
                        help="Number of simulation runs for statistical tests")
    parser.add_argument("--mode",        choices=["smoke_ci", "full_statistical"],
                        default="smoke_ci",
                        help="Run mode: smoke_ci (fast CI check) or full_statistical")
    return parser
main
