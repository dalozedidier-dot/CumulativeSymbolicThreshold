#!/usr/bin/env python3
"""04_Code/pipeline/run_ori_c_demo.py

ORI-C demo runner.

What it does
- Runs a control trajectory (intervention="none") and a test trajectory (chosen intervention)
- Supports multi-runs (replicates) with reproducible seeds
- Writes timeseries, per-run summaries, and figures for S(t), V(t), C(t), delta_C(t)
- Provides simple persistence metrics for the cumulative threshold condition C(t) > 0

Outputs (single run)
- <outdir>/tables/control_timeseries.csv
- <outdir>/tables/test_timeseries.csv
- <outdir>/tables/summary.csv
- <outdir>/tables/summary.json
- <outdir>/figures/s_t.png
- <outdir>/figures/v_t.png
- <outdir>/figures/c_t.png
- <outdir>/figures/delta_c_t.png
- <outdir>/figures/csd_s_acf1.png (optional)
- <outdir>/figures/csd_s_var.png (optional)

Outputs (multi-run)
- <outdir>/run_0001/ ...
- <outdir>/tables/summary_all.csv
- <outdir>/tables/summary_all.json
- <outdir>/index.md

Example
python 04_Code/pipeline/run_ori_c_demo.py \
  --outdir 05_Results/threshold_validation/demo_001 \
  --n-runs 12 --seed-base 1000 --n-steps 2600 --t0 900 \
  --intervention demand_shock --sigma-star 150 --tau 600 \
  --demand-noise 0.05 --ori-trend 0.0005 --intervention-duration 250
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

# Ensure 04_Code is on sys.path so `import pipeline.*` works when scripts are executed directly.
_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import argparse
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

from pipeline.ori_c_pipeline import ORICConfig, run_oric


def _mkdirs(outdir: Path) -> tuple[Path, Path]:
    tabdir = outdir / "tables"
    figdir = outdir / "figures"
    tabdir.mkdir(parents=True, exist_ok=True)
    figdir.mkdir(parents=True, exist_ok=True)
    return tabdir, figdir


def _rolling_acf1(x: np.ndarray, window: int) -> np.ndarray:
    if window < 5:
        window = 5
    out = np.full(len(x), np.nan, dtype=float)
    for i in range(window, len(x) + 1):
        seg = x[i - window : i]
        if np.std(seg) < 1e-12:
            out[i - 1] = 0.0
            continue
        out[i - 1] = float(np.corrcoef(seg[:-1], seg[1:])[0, 1])
    return out


def _rolling_var(x: np.ndarray, window: int) -> np.ndarray:
    if window < 5:
        window = 5
    out = np.full(len(x), np.nan, dtype=float)
    for i in range(window, len(x) + 1):
        seg = x[i - window : i]
        out[i - 1] = float(np.var(seg))
    return out


def _plot_series(df_c: pd.DataFrame, df_t: pd.DataFrame, col: str, t0: int, outpath: Path, title: str) -> None:
    plt.figure(figsize=(10, 5))
    plt.plot(df_c["t"], df_c[col], label="control")
    plt.plot(df_t["t"], df_t[col], label="test")
    plt.axvline(x=int(t0), linestyle="--", label="t0")
    plt.xlabel("t")
    plt.ylabel(col)
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()


def _plot_delta_c(df_c: pd.DataFrame, df_t: pd.DataFrame, t0: int, thr_val: float, thr_idx: int | None, outpath: Path) -> None:
    plt.figure(figsize=(10, 5))
    plt.plot(df_c["t"], df_c["delta_C"], label="control")
    plt.plot(df_t["t"], df_t["delta_C"], label="test")
    plt.axhline(y=float(thr_val), linestyle=":", label="threshold")
    plt.axvline(x=int(t0), linestyle="--", label="t0")
    if thr_idx is not None:
        t_hit = float(df_t.loc[int(thr_idx), "t"])
        plt.axvline(x=t_hit, linestyle=":", label="threshold_hit")
    plt.xlabel("t")
    plt.ylabel("delta_C")
    plt.title("delta_C(t) with threshold")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()


def _first_crossing_time(x: np.ndarray, thr: float = 0.0) -> int | None:
    for i, v in enumerate(x):
        if float(v) > float(thr):
            return int(i)
    return None


def _window_mask(t: pd.Series, start: int, end: int) -> pd.Series:
    return (t >= int(start)) & (t < int(end))


def summarize_threshold(
    df_test: pd.DataFrame,
    t0: int,
    delta: int,
    T: int,
) -> dict:
    t = df_test["t"]
    c = df_test["C"].to_numpy(dtype=float)

    pre_start = max(0, int(t0) - int(delta))
    pre_end = int(t0)
    post_start = int(t0)
    post_end = min(int(df_test["t"].max()) + 1, int(t0) + int(T))

    pre = df_test[_window_mask(t, pre_start, pre_end)]
    post = df_test[_window_mask(t, post_start, post_end)]

    C_mean_pre = float(pre["C"].mean()) if len(pre) else float("nan")
    C_mean_post = float(post["C"].mean()) if len(post) else float("nan")

    # Persistence metrics post
    post_c = post["C"].to_numpy(dtype=float) if len(post) else np.array([], dtype=float)
    C_positive_frac_post = float(np.mean(post_c > 0.0)) if len(post_c) else float("nan")
    C_min_post = float(np.min(post_c)) if len(post_c) else float("nan")

    cross_idx = _first_crossing_time(c, thr=0.0)
    cross_t = None if cross_idx is None else int(df_test.loc[int(cross_idx), "t"])

    # Threshold hit from detector
    thr_idx = None
    if "threshold_hit" in df_test.columns and bool((df_test["threshold_hit"] > 0).any()):
        thr_idx = int(df_test.index[df_test["threshold_hit"] > 0][0])

    thr_t = None if thr_idx is None else int(df_test.loc[int(thr_idx), "t"])
    thr_val = float(df_test["threshold_value"].iloc[0]) if "threshold_value" in df_test.columns else float("nan")

    return {
        "t0": int(t0),
        "delta": int(delta),
        "T": int(T),
        "C_mean_pre": C_mean_pre,
        "C_mean_post": C_mean_post,
        "C_mean_post_minus_pre": float(C_mean_post - C_mean_pre) if np.isfinite(C_mean_pre) and np.isfinite(C_mean_post) else float("nan"),
        "C_positive_frac_post": C_positive_frac_post,
        "C_min_post": C_min_post,
        "C_cross_t": cross_t,
        "threshold_hit_t": thr_t,
        "threshold_value": thr_val,
    }




def compute_verdict_from_summary(summary: dict) -> dict:
    """Compute a binary verdict for ORI-C demo runs.

    The meaning of ACCEPT depends on the intervention.
    - For symbolic_cut, ACCEPT means C collapses (mostly non-positive post) and the effect is negative and significant.
    - For other interventions, ACCEPT means a persistent positive C post and a significant positive effect on C.
    """

    intervention = str(summary.get("intervention", ""))

    C_mean_post = float(summary.get("C_mean_post", float("nan")))
    C_positive_frac_post = float(summary.get("C_positive_frac_post", float("nan")))
    effect_C_post_mean = float(summary.get("effect_C_post_mean", float("nan")))
    p_value_C_post_mean = float(summary.get("p_value_C_post_mean", float("nan")))
    threshold_hit_t = summary.get("threshold_hit_t", None)

    if intervention in {"none", "control"}:
        return {
            "verdict": "INDETERMINATE",
            "rationale": "No intervention. No binary claim is asserted.",
            "key_metrics": {
                "C_mean_post": C_mean_post,
                "C_positive_frac_post": C_positive_frac_post,
                "effect_C_post_mean": effect_C_post_mean,
                "p_value_C_post_mean": p_value_C_post_mean,
                "threshold_hit_t": threshold_hit_t,
            },
        }

    if intervention == "symbolic_cut":
        ok = (
            (C_positive_frac_post <= 0.10)
            and (C_mean_post < 0.0)
            and (effect_C_post_mean < -0.10)
            and (p_value_C_post_mean < 0.01)
        )
        return {
            "verdict": "ACCEPT" if ok else "REJECT",
            "rationale": (
                "Symbolic cut should suppress C. ACCEPT requires post C mostly non-positive, "
                "and a negative significant effect on C versus control."
            ),
            "key_metrics": {
                "C_mean_post": C_mean_post,
                "C_positive_frac_post": C_positive_frac_post,
                "effect_C_post_mean": effect_C_post_mean,
                "p_value_C_post_mean": p_value_C_post_mean,
                "threshold_hit_t": threshold_hit_t,
            },
        }

    ok = (
        ((threshold_hit_t is not None) or (C_positive_frac_post >= 0.50))
        and (C_mean_post > 0.10)
        and (effect_C_post_mean > 0.10)
        and (p_value_C_post_mean < 0.01)
    )
    return {
        "verdict": "ACCEPT" if ok else "REJECT",
        "rationale": (
            "Seuil cumulatif détecté si C devient positivement persistant post, avec un effet positif "
            "significatif sur C versus contrôle."
        ),
        "key_metrics": {
            "C_mean_post": C_mean_post,
            "C_positive_frac_post": C_positive_frac_post,
            "effect_C_post_mean": effect_C_post_mean,
            "p_value_C_post_mean": p_value_C_post_mean,
            "threshold_hit_t": threshold_hit_t,
        },
    }

def _aggregate_runs(
    effects: "np.ndarray",
    intervention: str,
    seed_base: int,
    alpha: float = 0.01,
    ci_level: float = 0.99,
    sesoi_c_robust_sd: float = 0.30,
    power_bootstrap_B: int = 500,
    power_gate_min: float = 0.70,
) -> dict:
    """Between-run statistical aggregation (triplet: p + CI + SESOI + power gate).

    Protocol-mandated test per DECISION_RULES v1/v2 and PreregSpec.
    Direction is determined by intervention:
      - "symbolic_cut" → H1: mean_effect < 0 (negative expected)
      - all others     → H1: mean_effect > 0 (positive expected)
    """
    n = len(effects)
    if n < 2:
        return {
            "n_valid": n,
            "verdict": "INDETERMINATE",
            "rationale": f"Too few valid runs (n={n}) for statistical test. Need n>=2.",
        }

    direction = "negative" if intervention == "symbolic_cut" else "positive"

    mean_eff = float(np.mean(effects))
    mad_eff = float(stats.median_abs_deviation(effects, scale=1.0))
    std_eff = float(np.std(effects, ddof=1))
    se_eff = std_eff / np.sqrt(n)

    t_res = stats.ttest_1samp(effects, 0.0)
    t_stat = float(t_res.statistic)
    p_two = float(t_res.pvalue)

    if direction == "positive":
        p_one = p_two / 2.0 if t_stat > 0 else 1.0 - p_two / 2.0
    else:
        p_one = p_two / 2.0 if t_stat < 0 else 1.0 - p_two / 2.0

    ci_alpha = 1.0 - ci_level
    ci_low, ci_high = float("nan"), float("nan")
    if se_eff > 0:
        ci_low, ci_high = stats.t.interval(ci_level, df=n - 1, loc=mean_eff, scale=se_eff)

    sesoi = sesoi_c_robust_sd * mad_eff

    p_ok = p_one < alpha
    if direction == "positive":
        ci_ok = float(ci_low) > 0.0 if np.isfinite(ci_low) else False
        sesoi_ok = mean_eff > sesoi
    else:
        ci_ok = float(ci_high) < 0.0 if np.isfinite(ci_high) else False
        sesoi_ok = abs(mean_eff) > sesoi

    # Bootstrap power estimate (B=500, seed-controlled)
    rng = np.random.default_rng(int(seed_base))
    rejections = 0
    for _ in range(int(power_bootstrap_B)):
        sample = rng.choice(effects, size=n, replace=True)
        t_b, p_b = stats.ttest_1samp(sample, 0.0)
        t_b = float(t_b)
        p_b = float(p_b)
        if direction == "positive":
            p_use = p_b / 2.0 if t_b > 0 else 1.0 - p_b / 2.0
        else:
            p_use = p_b / 2.0 if t_b < 0 else 1.0 - p_b / 2.0
        if p_use < alpha:
            rejections += 1
    power_est = rejections / power_bootstrap_B
    power_ok = power_est >= power_gate_min

    if not power_ok:
        verdict = "INDETERMINATE"
        rationale = (
            f"Power gate: estimated_power={power_est:.3f} < {power_gate_min}. "
            "Inconclusive — increase N or effect size."
        )
    elif p_ok and ci_ok and sesoi_ok:
        verdict = "ACCEPT"
        rationale = (
            f"Triplet satisfied: p_one={p_one:.4f}<{alpha}, "
            f"CI{int(ci_level*100)}%=[{ci_low:.4f},{ci_high:.4f}] excludes 0 "
            f"(direction={direction}), effect={mean_eff:.4f}>SESOI={sesoi:.4f}."
        )
    else:
        verdict = "REJECT"
        reasons = []
        if not p_ok:
            reasons.append(f"p_one={p_one:.4f}>={alpha}")
        if not ci_ok:
            reasons.append(f"CI does not exclude 0 (direction={direction})")
        if not sesoi_ok:
            reasons.append(f"|effect|={abs(mean_eff):.4f}<=SESOI={sesoi:.4f}")
        rationale = "Triplet failed: " + "; ".join(reasons)

    return {
        "n_valid": n,
        "intervention": intervention,
        "direction": direction,
        "mean_effect": mean_eff,
        "mad_effect": mad_eff,
        "std_effect": std_eff,
        "se_effect": se_eff,
        "t_stat": t_stat,
        "p_one_sided": p_one,
        f"ci_{int(ci_level*100)}_low": float(ci_low),
        f"ci_{int(ci_level*100)}_high": float(ci_high),
        "sesoi": sesoi,
        "p_ok": bool(p_ok),
        "ci_ok": bool(ci_ok),
        "sesoi_ok": bool(sesoi_ok),
        "power_estimate": power_est,
        "power_ok": bool(power_ok),
        "verdict": verdict,
        "rationale": rationale,
    }


def run_one(
    *,
    outdir: Path,
    seed: int,
    cfg_control: ORICConfig,
    cfg_test: ORICConfig,
    delta: int,
    T: int,
    csd_window: int,
    write_csd: bool,
) -> dict:
    tabdir, figdir = _mkdirs(outdir)

    df_c = run_oric(cfg_control)
    df_t = run_oric(cfg_test)

    # Persist series
    df_c.to_csv(tabdir / "control_timeseries.csv", index=False)
    df_t.to_csv(tabdir / "test_timeseries.csv", index=False)

    # Per-run summary
    thr = summarize_threshold(df_t, t0=int(cfg_test.intervention_point), delta=int(delta), T=int(T))

    # Effect on C in post window
    t0 = int(cfg_test.intervention_point)
    post_mask = df_t["t"] >= t0
    eff_C = float(df_t.loc[post_mask, "C"].mean() - df_c.loc[post_mask, "C"].mean())
    p_C = float(
        stats.ttest_ind(
            df_t.loc[post_mask, "C"].to_numpy(dtype=float),
            df_c.loc[post_mask, "C"].to_numpy(dtype=float),
            equal_var=False,
        ).pvalue
    )

    summary = {
        "seed": int(seed),
        "intervention": str(cfg_test.intervention),
        "effect_C_post_mean": eff_C,
        "p_value_C_post_mean": p_C,
        **thr,
        "cfg_control": asdict(cfg_control),
        "cfg_test": asdict(cfg_test),
    }

    pd.DataFrame([{
        "seed": int(seed),
        "intervention": str(cfg_test.intervention),
        "effect_C_post_mean": eff_C,
        "p_value_C_post_mean": p_C,
        **{k: v for k, v in thr.items()},
    }]).to_csv(tabdir / "summary.csv", index=False)

    (tabdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    verdict = compute_verdict_from_summary(summary)
    (tabdir / "verdict.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")


    # Figures
    _plot_series(df_c, df_t, "S", t0, figdir / "s_t.png", "S(t) control vs test")
    _plot_series(df_c, df_t, "V", t0, figdir / "v_t.png", "V(t) control vs test")
    _plot_series(df_c, df_t, "C", t0, figdir / "c_t.png", "C(t) control vs test")

    thr_idx = None
    if "threshold_hit" in df_t.columns and bool((df_t["threshold_hit"] > 0).any()):
        thr_idx = int(df_t.index[df_t["threshold_hit"] > 0][0])
    thr_val = float(df_t["threshold_value"].iloc[0]) if "threshold_value" in df_t.columns else float("nan")
    _plot_delta_c(df_c, df_t, t0, thr_val, thr_idx, figdir / "delta_c_t.png")

    # Critical slowing down diagnostics (simple)
    if write_csd:
        s = df_t["S"].to_numpy(dtype=float)
        acf1 = _rolling_acf1(s, window=int(csd_window))
        var = _rolling_var(s, window=int(csd_window))

        plt.figure(figsize=(10, 5))
        plt.plot(df_t["t"], acf1, label="rolling_acf1(S)")
        plt.axvline(x=int(t0), linestyle="--", label="t0")
        plt.xlabel("t")
        plt.ylabel("acf1")
        plt.title("Critical slowing down proxy: rolling ACF(1) of S")
        plt.legend()
        plt.tight_layout()
        plt.savefig(figdir / "csd_s_acf1.png", dpi=160)
        plt.close()

        plt.figure(figsize=(10, 5))
        plt.plot(df_t["t"], var, label="rolling_var(S)")
        plt.axvline(x=int(t0), linestyle="--", label="t0")
        plt.xlabel("t")
        plt.ylabel("var")
        plt.title("Critical slowing down proxy: rolling variance of S")
        plt.legend()
        plt.tight_layout()
        plt.savefig(figdir / "csd_s_var.png", dpi=160)
        plt.close()

    return summary


def _write_index_md(outdir: Path, df_all: pd.DataFrame) -> None:
    lines = []
    lines.append("# Threshold validation suite index")
    lines.append("")

    cols = [
        "seed",
        "intervention",
        "sigma_star",
        "tau",
        "demand_noise",
        "ori_trend",
        "threshold_hit_t",
        "C_mean_post",
        "C_positive_frac_post",
        "effect_C_post_mean",
        "p_value_C_post_mean",
    ]

    # top by persistence then by C_mean_post
    df2 = df_all.copy()
    if "C_positive_frac_post" in df2.columns:
        df2 = df2.sort_values(["C_positive_frac_post", "C_mean_post"], ascending=[False, False])

    lines.append("Top runs (sorted by C_positive_frac_post, then C_mean_post).")
    lines.append("")

    # markdown table
    head = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    lines.append(head)
    lines.append(sep)
    for _, r in df2.head(12).iterrows():
        row = []
        for c in cols:
            if c not in r.index:
                row.append("")
                continue
            v = r[c]
            if isinstance(v, float):
                row.append(f"{v:.4g}")
            else:
                row.append(str(v))
        lines.append("| " + " | ".join(row) + " |")

    (outdir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)

    ap.add_argument("--n-runs", type=int, default=1)
    ap.add_argument("--seed-base", type=int, default=42)

    ap.add_argument("--n-steps", type=int, default=260)
    ap.add_argument("--t0", type=int, default=80)

    ap.add_argument(
        "--intervention",
        default="demand_shock",
        choices=[
            "none",
            "demand_shock",
            "capacity_hit",
            "symbolic_cut",
            "symbolic_injection",
            "symbolic_cut_then_inject",
        ],
    )

    ap.add_argument("--intervention-duration", type=int, default=0)
    ap.add_argument("--reinjection-point", type=int, default=120)

    ap.add_argument("--cap-scale", type=float, default=1000.0)

    ap.add_argument("--demand-noise", type=float, default=0.03)
    ap.add_argument("--ori-drift", type=float, default=0.002)
    ap.add_argument("--ori-trend", type=float, default=0.0)

    ap.add_argument("--sigma-star", type=float, default=0.0)
    ap.add_argument("--tau", type=float, default=0.0, help="If >0, sets S_decay = 1/tau")
    ap.add_argument("--s-decay", type=float, default=0.002, help="Used if tau <= 0")
    ap.add_argument("--sigma-to-s-alpha", type=float, default=0.0008)

    ap.add_argument("--C-beta", type=float, default=0.40)
    ap.add_argument("--C-gamma", type=float, default=0.12)

    ap.add_argument("--demand-shock-factor", type=float, default=1.25)
    ap.add_argument("--capacity-hit-factor", type=float, default=0.85)
    ap.add_argument("--symbolic-cut-factor", type=float, default=0.20)
    ap.add_argument("--symbolic-injection-add", type=float, default=0.25)

    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=30)

    ap.add_argument("--delta", type=int, default=200, help="Pre window length for metrics")
    ap.add_argument("--T", type=int, default=400, help="Post window length for metrics")

    ap.add_argument("--csd-window", type=int, default=80)
    ap.add_argument("--no-csd", action="store_true")

    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Derive S_decay
    if float(args.tau) > 0.0:
        s_decay = 1.0 / float(args.tau)
    else:
        s_decay = float(args.s_decay)

    cfg_common = ORICConfig(
        seed=int(args.seed_base),
        n_steps=int(args.n_steps),
        intervention_point=int(args.t0),
        reinjection_point=int(args.reinjection_point),
        intervention_duration=int(args.intervention_duration),
        k=float(args.k),
        m=int(args.m),
        baseline_n=int(args.baseline_n),
        cap_scale=float(args.cap_scale),
        demand_noise=float(args.demand_noise),
        ori_drift=float(args.ori_drift),
        ori_trend=float(args.ori_trend),
        sigma_star=float(args.sigma_star),
        sigma_to_S_alpha=float(args.sigma_to_s_alpha),
        S_decay=float(s_decay),
        C_beta=float(args.C_beta),
        C_gamma=float(args.C_gamma),
        demand_shock_factor=float(args.demand_shock_factor),
        capacity_hit_factor=float(args.capacity_hit_factor),
        symbolic_cut_factor=float(args.symbolic_cut_factor),
        symbolic_injection_add=float(args.symbolic_injection_add),
    )

    # Prepare control and test templates
    cfg_control_tmpl = ORICConfig(**{**asdict(cfg_common), "intervention": "none"})
    cfg_test_tmpl = ORICConfig(**{**asdict(cfg_common), "intervention": str(args.intervention)})

    n_runs = int(args.n_runs)

    summaries = []
    if n_runs <= 1:
        summary = run_one(
            outdir=outdir,
            seed=int(args.seed_base),
            cfg_control=cfg_control_tmpl,
            cfg_test=cfg_test_tmpl,
            delta=int(args.delta),
            T=int(args.T),
            csd_window=int(args.csd_window),
            write_csd=not bool(args.no_csd),
        )
        summaries.append(summary)
        # Write verdict.txt (canonical output convention)
        tabdir_s = outdir / "tables"
        vj = tabdir_s / "verdict.json"
        if vj.exists():
            vdata = json.loads(vj.read_text(encoding="utf-8"))
            (outdir / "verdict.txt").write_text(str(vdata.get("verdict", "INDETERMINATE")), encoding="utf-8")
    else:
        for i in range(n_runs):
            seed = int(args.seed_base) + i
            sub = outdir / f"run_{i+1:04d}"
            cfg_control = ORICConfig(**{**asdict(cfg_control_tmpl), "seed": seed})
            cfg_test = ORICConfig(**{**asdict(cfg_test_tmpl), "seed": seed})

            summary = run_one(
                outdir=sub,
                seed=seed,
                cfg_control=cfg_control,
                cfg_test=cfg_test,
                delta=int(args.delta),
                T=int(args.T),
                csd_window=int(args.csd_window),
                write_csd=not bool(args.no_csd),
            )

            # flatten a few key params to ease aggregation
            summary_flat = {
                **{k: v for k, v in summary.items() if k not in {"cfg_control", "cfg_test"}},
                "sigma_star": float(cfg_test.sigma_star),
                "tau": float(args.tau) if float(args.tau) > 0.0 else (1.0 / float(cfg_test.S_decay) if cfg_test.S_decay > 0 else 0.0),
                "demand_noise": float(cfg_test.demand_noise),
                "ori_trend": float(cfg_test.ori_trend),
                "intervention_duration": int(cfg_test.intervention_duration),
                "run_dir": str(sub.name),
            }
            summaries.append(summary_flat)

        df_all = pd.DataFrame(summaries)
        tabdir, _ = _mkdirs(outdir)
        df_all.to_csv(tabdir / "summary_all.csv", index=False)

        # Between-run statistical aggregation (triplet: p + CI99% + SESOI + power gate)
        # This is the protocol-mandated test (DECISION_RULES v1/v2, PreregSpec defaults).
        effects_raw = df_all["effect_C_post_mean"].dropna().to_numpy(dtype=float)
        agg = _aggregate_runs(
            effects=effects_raw,
            intervention=str(args.intervention),
            seed_base=int(args.seed_base),
            alpha=0.01,
            ci_level=0.99,
            sesoi_c_robust_sd=0.30,
            power_bootstrap_B=500,
            power_gate_min=0.70,
        )
        agg["n_runs_total"] = int(n_runs)
        agg["seed_base"] = int(args.seed_base)
        agg["S_decay"] = float(s_decay)
        agg["delta"] = int(args.delta)
        agg["T_window"] = int(args.T)

        # Write aggregate summary.json (canonical, overwrites run-level placeholder)
        (tabdir / "summary.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
        (tabdir / "summary_all.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
        (tabdir / "verdict.json").write_text(
            json.dumps({"verdict": agg["verdict"], "rationale": agg.get("rationale", "")}, indent=2),
            encoding="utf-8",
        )
        # canonical verdict.txt
        (outdir / "verdict.txt").write_text(agg["verdict"], encoding="utf-8")

        _write_index_md(outdir, df_all)

    # Print a small JSON for CLI usability
    print(json.dumps({"outdir": str(outdir), "n_runs": int(n_runs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
