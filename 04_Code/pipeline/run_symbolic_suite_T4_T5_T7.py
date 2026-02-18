#!/usr/bin/env python3
"""
run_symbolic_suite_T4_T5_T7.py

Purpose
- Add the missing symbolic tests T4, T5, T7 in a minimal, testable way.
- Do NOT change the ORI-C framework. These tests only exercise the symbolic layer (S -> C).

Outputs (under --outdir)
- tables/
  - T4_results.csv
  - T5_results.csv
  - T7_results.csv
  - symbolic_suite_summary.csv
- figures/
  - T4_scatter_S_vs_C.png
  - T5_C_timecourse_injection.png
  - T7_piecewise_threshold_S_star.png
- verdict.txt (ACCEPT / REJECT / INDETERMINATE per test + global for the suite)

Notes
- This is a synthetic harness. It is designed to prove that the test logic is executable and falsifiable.
- For later, you can plug in empirical generators, but keep the decision rules identical.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


@dataclass(frozen=True)
class DecisionRules:
    alpha: float = 0.01

    # T4: correlation S -> C
    t4_corr_threshold: float = 0.80

    # T5: deferred effect minimum (difference in mean C after horizon)
    t5_effect_min: float = 0.30

    # T7: piecewise vs linear BIC improvement
    t7_delta_bic_min: float = 10.0

    # Generic gate
    min_reps: int = 30


def ensure_dirs(outdir: Path) -> Tuple[Path, Path]:
    figs = outdir / "figures"
    tabs = outdir / "tables"
    figs.mkdir(parents=True, exist_ok=True)
    tabs.mkdir(parents=True, exist_ok=True)
    return figs, tabs


def bic_from_rss(rss: float, n: int, k: int) -> float:
    rss = max(rss, 1e-12)
    return n * math.log(rss / n) + k * math.log(n)


def fit_linear(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, float]:
    # y = a + b x
    X = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    rss = float(np.sum((y - yhat) ** 2))
    return beta, rss


def fit_hinge_grid(x: np.ndarray, y: np.ndarray, grid: np.ndarray) -> Tuple[Dict, float]:
    """
    Fit y = a + b x + c max(0, x - s_star)
    Scan s_star on grid and pick the best BIC.
    """
    best = {"s_star": None, "beta": None, "rss": None, "bic": None}
    n = len(x)
    for s_star in grid:
        h = np.maximum(0.0, x - s_star)
        X = np.column_stack([np.ones_like(x), x, h])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        yhat = X @ beta
        rss = float(np.sum((y - yhat) ** 2))
        bic = bic_from_rss(rss=rss, n=n, k=3)
        if best["bic"] is None or bic < best["bic"]:
            best = {"s_star": float(s_star), "beta": beta, "rss": rss, "bic": bic}
    return best, float(best["bic"])


def verdict_from_bool(success: bool) -> str:
    return "ACCEPT" if success else "REJECT"


def run_T4(seed: int, reps: int) -> pd.DataFrame:
    """
    T4: Controlled variation of S -> variation in C attributable to S.
    """
    rng = np.random.default_rng(seed)
    rows = []
    t = np.arange(200)

    for rep in range(reps):
        amp = rng.uniform(0.5, 2.0)
        S = np.sin(t / 12.0) * amp + rng.normal(0, 0.05, size=len(t))
        C = 0.6 * S + rng.normal(0, 0.10, size=len(t))
        corr = float(np.corrcoef(S, C)[0, 1])
        rows.append({"rep": rep, "amp": amp, "corr": corr})

    return pd.DataFrame(rows)


def run_T5(seed: int, reps: int, t0: int, horizon: int) -> pd.DataFrame:
    """
    T5: Symbolic injection at t0, delayed effect measured at horizon.
    """
    rng = np.random.default_rng(seed)
    rows = []
    t = np.arange(200)

    for rep in range(reps):
        noise_ctl = rng.normal(0, 0.05, size=len(t))
        noise_inj = rng.normal(0, 0.05, size=len(t))
        base = np.zeros_like(t, dtype=float)

        C_ctl = base + noise_ctl
        C_inj = base + noise_inj

        if horizon < len(t):
            C_inj[horizon:] += 0.5

        delta = float(np.mean(C_inj[horizon:]) - np.mean(C_ctl[horizon:]))
        rows.append({"rep": rep, "t0": t0, "horizon": horizon, "delta_post": delta})

    return pd.DataFrame(rows)


def run_T7(seed: int, n_levels: int = 21) -> pd.DataFrame:
    """
    T7: Progressive variation of S level, detect a stable tipping point S* in C_end.
    """
    rng = np.random.default_rng(seed)
    S_levels = np.linspace(0.0, 2.0, n_levels)
    true_s_star = 1.05

    C_end = []
    for s in S_levels:
        if s <= true_s_star:
            c = 0.05 * s
        else:
            c = 0.40 + 0.35 * (s - true_s_star)
        c += rng.normal(0, 0.03)
        C_end.append(float(c))

    return pd.DataFrame({"S_level": S_levels, "C_end": C_end})


def analyze_T4(df: pd.DataFrame, rules: DecisionRules) -> Dict:
    mean_corr = float(df["corr"].mean())
    success = mean_corr >= rules.t4_corr_threshold
    return {
        "test": "T4",
        "metric": "mean_corr",
        "value": mean_corr,
        "threshold": rules.t4_corr_threshold,
        "success": success,
        "verdict": verdict_from_bool(success),
    }


def analyze_T5(df: pd.DataFrame, rules: DecisionRules) -> Dict:
    mean_delta = float(df["delta_post"].mean())
    success = mean_delta >= rules.t5_effect_min
    return {
        "test": "T5",
        "metric": "mean_delta_post",
        "value": mean_delta,
        "threshold": rules.t5_effect_min,
        "success": success,
        "verdict": verdict_from_bool(success),
    }


def analyze_T7(df: pd.DataFrame, rules: DecisionRules) -> Dict:
    x = df["S_level"].to_numpy()
    y = df["C_end"].to_numpy()

    _, rss_lin = fit_linear(x, y)
    bic_lin = bic_from_rss(rss=rss_lin, n=len(x), k=2)

    grid = np.linspace(float(x.min()) + 0.05, float(x.max()) - 0.05, 40)
    best, bic_hinge = fit_hinge_grid(x, y, grid=grid)

    delta_bic = bic_lin - bic_hinge
    s_star = float(best["s_star"])
    post = y[x >= s_star]
    post_std = float(np.std(post)) if len(post) > 3 else float("inf")
    stable = post_std <= 0.12

    success = (delta_bic >= rules.t7_delta_bic_min) and stable

    return {
        "test": "T7",
        "metric": "delta_BIC",
        "value": float(delta_bic),
        "threshold": rules.t7_delta_bic_min,
        "s_star_hat": s_star,
        "post_std": post_std,
        "stable": stable,
        "success": success,
        "verdict": verdict_from_bool(success),
    }


def plot_T4(df: pd.DataFrame, outpath: Path) -> None:
    plt.figure(figsize=(9, 5))
    plt.scatter(df["amp"], df["corr"])
    plt.xlabel("S amplitude (run-level)")
    plt.ylabel("corr(S, C)")
    plt.title("T4: Controlled S -> C attribution (per replicate)")
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()


def plot_T5(outpath: Path, t0: int, horizon: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    t = np.arange(200)
    C_ctl = rng.normal(0, 0.05, size=len(t))
    C_inj = rng.normal(0, 0.05, size=len(t))
    if horizon < len(t):
        C_inj[horizon:] += 0.5

    plt.figure(figsize=(10, 5))
    plt.plot(t, C_ctl, label="Control")
    plt.plot(t, C_inj, label="Injection (delayed)")
    plt.axvline(x=t0, linestyle="--", label="t0")
    plt.axvline(x=horizon, linestyle="--", label="horizon")
    plt.xlabel("t")
    plt.ylabel("C(t)")
    plt.title("T5: Symbolic injection with delayed effect")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()


def plot_T7(df: pd.DataFrame, analysis: Dict, outpath: Path) -> None:
    x = df["S_level"].to_numpy()
    y = df["C_end"].to_numpy()
    s_star = float(analysis["s_star_hat"])

    h = np.maximum(0.0, x - s_star)
    X = np.column_stack([np.ones_like(x), x, h])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta

    plt.figure(figsize=(9, 5))
    plt.scatter(x, y, label="data")
    plt.plot(x, yhat, label="hinge fit")
    plt.axvline(x=s_star, linestyle="--", label=f"S*={s_star:.2f}")
    plt.xlabel("S level")
    plt.ylabel("C_end")
    plt.title("T7: Progressive S sweep and detected S* (piecewise)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath, dpi=160)
    plt.close()


def suite_verdict(per_test: List[Dict]) -> str:
    ok = all(t["verdict"] == "ACCEPT" for t in per_test)
    return "ACCEPT" if ok else "INDETERMINATE"


def write_verdict(outdir: Path, per_test: List[Dict], global_verdict: str) -> None:
    lines = []
    for t in per_test:
        lines.append(f'{t["test"]}: {t["verdict"]} ({t["metric"]}={t["value"]:.4g}, thr={t["threshold"]})')
    lines.append(f"GLOBAL: {global_verdict}")
    (outdir / "verdict.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reps", type=int, default=50)
    ap.add_argument("--t0", type=int, default=50)
    ap.add_argument("--horizon", type=int, default=90)
    ap.add_argument("--t4_corr_threshold", type=float, default=0.80)
    ap.add_argument("--t5_effect_min", type=float, default=0.30)
    ap.add_argument("--t7_delta_bic_min", type=float, default=10.0)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    figs, tabs = ensure_dirs(outdir)

    rules = DecisionRules(
        t4_corr_threshold=args.t4_corr_threshold,
        t5_effect_min=args.t5_effect_min,
        t7_delta_bic_min=args.t7_delta_bic_min,
        min_reps=30,
    )

    if args.reps < rules.min_reps:
        raise SystemExit(f"reps must be >= {rules.min_reps}")

    df_t4 = run_T4(seed=args.seed, reps=args.reps)
    df_t5 = run_T5(seed=args.seed, reps=args.reps, t0=args.t0, horizon=args.horizon)
    df_t7 = run_T7(seed=args.seed)

    a4 = analyze_T4(df_t4, rules)
    a5 = analyze_T5(df_t5, rules)
    a7 = analyze_T7(df_t7, rules)

    per_test = [a4, a5, a7]
    global_v = suite_verdict(per_test)

    df_t4.to_csv(tabs / "T4_results.csv", index=False)
    df_t5.to_csv(tabs / "T5_results.csv", index=False)
    df_t7.to_csv(tabs / "T7_results.csv", index=False)
    pd.DataFrame(per_test).to_csv(tabs / "symbolic_suite_summary.csv", index=False)

    plot_T4(df_t4, figs / "T4_scatter_S_vs_C.png")
    plot_T5(figs / "T5_C_timecourse_injection.png", t0=args.t0, horizon=args.horizon, seed=args.seed)
    plot_T7(df_t7, a7, figs / "T7_piecewise_threshold_S_star.png")

    write_verdict(outdir, per_test, global_v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
