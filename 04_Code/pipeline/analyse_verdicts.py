#!/usr/bin/env python3
"""
Applique les règles de décision (alpha, SESOI, gate) sur les sorties de run_oric_suite.py.

Entrées
- <suite_outdir>/tables/oric_suite_runs.csv

Sorties
- <suite_outdir>/verdicts/verdicts_local.csv
- <suite_outdir>/verdicts/verdicts_global.json
- <suite_outdir>/verdicts/diagnostics.md
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class DecisionSpec:
    alpha: float = 0.01
    ci_level: float = 0.99
    n_min: int = 50
    power_gate: float = 0.70

    sesoi_cap_rel: float = 0.10
    sesoi_v_rel: float = -0.10
    sesoi_c_mad: float = 0.30

    spearman_rho_min: float = -0.30


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def bootstrap_ci_diff(a: np.ndarray, b: np.ndarray, ci_level: float, n_boot: int = 4000, seed: int = 123) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n_a = len(a)
    n_b = len(b)
    if n_a < 2 or n_b < 2:
        return (float("nan"), float("nan"))

    diffs = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sa = rng.choice(a, size=n_a, replace=True)
        sb = rng.choice(b, size=n_b, replace=True)
        diffs[i] = float(np.mean(sb) - np.mean(sa))

    lo = float(np.quantile(diffs, (1.0 - ci_level) / 2.0))
    hi = float(np.quantile(diffs, 1.0 - (1.0 - ci_level) / 2.0))
    return lo, hi


def robust_mad(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    return mad if mad > 0 else float(np.std(x, ddof=1))


def power_gate_two_sample(a: np.ndarray, b: np.ndarray, alpha: float, target_delta: float, n_sim: int = 2500, seed: int = 7) -> float:
    """
    Puissance approximative au SESOI par Monte Carlo normal, Welch t-test.
    target_delta est une différence de moyennes attendue (b - a) sous H1.
    """
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)

    n_a = len(a)
    n_b = len(b)
    if n_a < 2 or n_b < 2:
        return float("nan")

    sd = float(np.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2.0))
    if sd <= 0:
        return float("nan")

    hits = 0
    for _ in range(n_sim):
        sa = rng.normal(0.0, sd, size=n_a)
        sb = rng.normal(target_delta, sd, size=n_b)
        p = stats.ttest_ind(sb, sa, equal_var=False).pvalue
        hits += int(p <= alpha)
    return float(hits / n_sim)


def verdict_from_triplet(p: float, ci: Tuple[float, float], effect: float, sesoi: float, power: float, alpha: float, power_gate: float, direction: str) -> str:
    """
    direction: 'pos' ou 'neg', sens attendu de l'effet (b - a).
    """
    lo, hi = ci
    if not np.isfinite(p) or not np.isfinite(lo) or not np.isfinite(hi) or not np.isfinite(effect) or not np.isfinite(power):
        return "INDETERMINATE"

    if power < power_gate:
        return "INDETERMINATE"

    ci_excludes_0 = (lo > 0.0) or (hi < 0.0)
    if not ci_excludes_0:
        return "INDETERMINATE"

    if p > alpha:
        return "INDETERMINATE"

    if direction == "pos":
        if effect >= sesoi:
            return "ACCEPT"
        if effect <= -abs(sesoi):
            return "REJECT"
        return "INDETERMINATE"

    if direction == "neg":
        if effect <= sesoi:
            return "ACCEPT"
        if effect >= abs(sesoi):
            return "REJECT"
        return "INDETERMINATE"

    return "INDETERMINATE"


def gate_condition(df: pd.DataFrame, spec: DecisionSpec) -> Dict[str, Any]:
    """Gate global basique sur le fichier runs."""
    required = ["test_id", "condition", "seed", "Cap_mean", "A_Sigma", "V_q05_post", "C_end"]
    missing = [c for c in required if c not in df.columns]
    fail = len(missing) > 0
    return {"gate_ok": not fail, "missing_columns": missing}


def test1_main_effect(df_t1: pd.DataFrame, factor: str, spec: DecisionSpec) -> Dict[str, Any]:
    """Compare niveau high vs low pour un facteur init_O/init_R/init_I."""
    if factor not in df_t1.columns:
        return {"test_id": f"T1_{factor}", "verdict": "INDETERMINATE", "reason": "missing factor"}

    # Identify low/high by unique values (expected 2 levels in suite)
    vals = sorted(df_t1[factor].unique().tolist())
    if len(vals) != 2:
        return {"test_id": f"T1_{factor}", "verdict": "INDETERMINATE", "reason": "not 2 levels"}
    low, high = vals[0], vals[1]

    a = df_t1.loc[df_t1[factor] == low, "Cap_mean"].to_numpy()
    b = df_t1.loc[df_t1[factor] == high, "Cap_mean"].to_numpy()

    N_a, N_b = len(a), len(b)
    if N_a < spec.n_min or N_b < spec.n_min:
        return {"test_id": f"T1_{factor}", "verdict": "INDETERMINATE", "reason": "N_min", "N_a": N_a, "N_b": N_b}

    diff = float(np.mean(b) - np.mean(a))
    rel = diff / float(np.mean(a)) if float(np.mean(a)) != 0 else float("nan")

    p = float(stats.ttest_ind(b, a, equal_var=False).pvalue)
    ci = bootstrap_ci_diff(a, b, ci_level=spec.ci_level)
    power = power_gate_two_sample(a, b, alpha=spec.alpha, target_delta=spec.sesoi_cap_rel * float(np.mean(a)))

    verdict = verdict_from_triplet(
        p=p,
        ci=ci,
        effect=rel,
        sesoi=spec.sesoi_cap_rel,
        power=power,
        alpha=spec.alpha,
        power_gate=spec.power_gate,
        direction="pos",
    )

    return {
        "test_id": f"T1_{factor}",
        "metric": "Cap_mean",
        "condition_a": f"{factor}={low}",
        "condition_b": f"{factor}={high}",
        "N_a": N_a,
        "N_b": N_b,
        "estimate": diff,
        "effect": rel,
        "sesoi": spec.sesoi_cap_rel,
        "p_value": p,
        "ci_low": ci[0],
        "ci_high": ci[1],
        "ci_level": spec.ci_level,
        "power_sesoi": power,
        "verdict": verdict,
    }


def test2_sigma_positive(df_t3: pd.DataFrame, spec: DecisionSpec) -> Dict[str, Any]:
    """Check opérationnel: overload>0 doit produire Sigma>0 (via frac_over)."""
    # Baseline = overload 0.00, Stress = overload 0.30 si dispo sinon max.
    df = df_t3.copy()
    df["overload"] = df["condition"].str.replace("T3_overload_", "", regex=False).astype(float)

    base = df.loc[df["overload"] == 0.0, "frac_over"].to_numpy()
    stress_over = 0.30 if (df["overload"] == 0.30).any() else float(df["overload"].max())
    stress = df.loc[df["overload"] == stress_over, "frac_over"].to_numpy()

    N_a, N_b = len(base), len(stress)
    if N_a < spec.n_min or N_b < spec.n_min:
        return {"test_id": "T2", "verdict": "INDETERMINATE", "reason": "N_min", "N_a": N_a, "N_b": N_b}

    diff = float(np.mean(stress) - np.mean(base))
    p = float(stats.mannwhitneyu(stress, base, alternative="greater").pvalue)
    ci = bootstrap_ci_diff(base, stress, ci_level=spec.ci_level)

    # SESOI: on exige une augmentation substantielle, ici 0.20 en proportion de temps en surcharge
    sesoi = 0.20
    power = power_gate_two_sample(base, stress, alpha=spec.alpha, target_delta=sesoi)

    verdict = verdict_from_triplet(
        p=p,
        ci=ci,
        effect=diff,
        sesoi=sesoi,
        power=power,
        alpha=spec.alpha,
        power_gate=spec.power_gate,
        direction="pos",
    )

    return {
        "test_id": "T2",
        "metric": "frac_over",
        "condition_a": f"overload=0.00",
        "condition_b": f"overload={stress_over:.2f}",
        "N_a": N_a,
        "N_b": N_b,
        "estimate": diff,
        "effect": diff,
        "sesoi": sesoi,
        "p_value": p,
        "ci_low": ci[0],
        "ci_high": ci[1],
        "ci_level": spec.ci_level,
        "power_sesoi": power,
        "verdict": verdict,
    }


def test3_v_degrades(df_t3: pd.DataFrame, spec: DecisionSpec) -> Dict[str, Any]:
    """V_q05_post doit diminuer quand A_Sigma augmente."""
    df = df_t3.copy()
    x = df["A_Sigma"].to_numpy(dtype=float)
    y = df["V_q05_post"].to_numpy(dtype=float)

    if len(df) < 2 * spec.n_min:
        return {"test_id": "T3", "verdict": "INDETERMINATE", "reason": "N_min_total", "N": int(len(df))}

    rho, p = stats.spearmanr(x, y)
    rho = float(rho)
    p = float(p)

    # Bootstrap CI for Spearman rho
    rng = np.random.default_rng(11)
    n_boot = 3000
    rhos = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, len(df), size=len(df))
        rhos[i] = float(stats.spearmanr(x[idx], y[idx]).statistic)
    lo = float(np.quantile(rhos, (1.0 - spec.ci_level) / 2.0))
    hi = float(np.quantile(rhos, 1.0 - (1.0 - spec.ci_level) / 2.0))

    # Effet complémentaire : chute relative de V au stress max vs baseline
    df["overload"] = df["condition"].str.replace("T3_overload_", "", regex=False).astype(float)
    base = df.loc[df["overload"] == 0.0, "V_q05_post"].to_numpy()
    stress_over = 0.40 if (df["overload"] == 0.40).any() else float(df["overload"].max())
    stress = df.loc[df["overload"] == stress_over, "V_q05_post"].to_numpy()

    rel_drop = float(np.mean(stress) - np.mean(base)) / float(np.mean(base)) if float(np.mean(base)) != 0 else float("nan")

    # p-value sur comparaison base vs stress (b - a = stress - base), attendu négatif
    p2 = float(stats.ttest_ind(stress, base, equal_var=False).pvalue)
    ci2 = bootstrap_ci_diff(base, stress, ci_level=spec.ci_level)
    power2 = power_gate_two_sample(base, stress, alpha=spec.alpha, target_delta=spec.sesoi_v_rel * float(np.mean(base)))

    # On exige les deux signaux : rho <= seuil et chute relative <= SESOI_V
    verdict_corr = "ACCEPT" if (p <= spec.alpha and hi < 0.0 and rho <= spec.spearman_rho_min) else "INDETERMINATE"
    verdict_drop = verdict_from_triplet(
        p=p2,
        ci=ci2,
        effect=rel_drop,
        sesoi=spec.sesoi_v_rel,
        power=power2,
        alpha=spec.alpha,
        power_gate=spec.power_gate,
        direction="neg",
    )
    verdict = "ACCEPT" if (verdict_corr == "ACCEPT" and verdict_drop == "ACCEPT") else ("REJECT" if verdict_drop == "REJECT" else "INDETERMINATE")

    return {
        "test_id": "T3",
        "metric": "V_q05_post",
        "condition_a": "overload=0.00",
        "condition_b": f"overload={stress_over:.2f}",
        "N_a": int(len(base)),
        "N_b": int(len(stress)),
        "estimate": float(np.mean(stress) - np.mean(base)),
        "effect": rel_drop,
        "sesoi": spec.sesoi_v_rel,
        "p_value": p2,
        "ci_low": ci2[0],
        "ci_high": ci2[1],
        "ci_level": spec.ci_level,
        "power_sesoi": power2,
        "spearman_rho": rho,
        "spearman_p": p,
        "spearman_ci_low": lo,
        "spearman_ci_high": hi,
        "verdict": verdict,
    }


def test4_symbolic_rich_poor(df_t4: pd.DataFrame, spec: DecisionSpec) -> Dict[str, Any]:
    rich = df_t4.loc[df_t4["condition"] == "T4_S_rich", "C_end"].to_numpy()
    poor = df_t4.loc[df_t4["condition"] == "T4_S_poor", "C_end"].to_numpy()

    N_a, N_b = len(poor), len(rich)
    if N_a < spec.n_min or N_b < spec.n_min:
        return {"test_id": "T4", "verdict": "INDETERMINATE", "reason": "N_min", "N_a": N_a, "N_b": N_b}

    diff = float(np.mean(rich) - np.mean(poor))
    mad = robust_mad(poor)
    eff = diff / mad if mad != 0 else float("nan")

    p = float(stats.ttest_ind(rich, poor, equal_var=False).pvalue)
    ci = bootstrap_ci_diff(poor, rich, ci_level=spec.ci_level)
    power = power_gate_two_sample(poor, rich, alpha=spec.alpha, target_delta=spec.sesoi_c_mad * mad)

    verdict = verdict_from_triplet(
        p=p,
        ci=ci,
        effect=eff,
        sesoi=spec.sesoi_c_mad,
        power=power,
        alpha=spec.alpha,
        power_gate=spec.power_gate,
        direction="pos",
    )

    return {
        "test_id": "T4",
        "metric": "C_end",
        "condition_a": "S_poor",
        "condition_b": "S_rich",
        "N_a": N_a,
        "N_b": N_b,
        "estimate": diff,
        "effect": eff,
        "sesoi": spec.sesoi_c_mad,
        "p_value": p,
        "ci_low": ci[0],
        "ci_high": ci[1],
        "ci_level": spec.ci_level,
        "power_sesoi": power,
        "verdict": verdict,
    }


def test7_symbolic_cut(df_all: pd.DataFrame, spec: DecisionSpec) -> Dict[str, Any]:
    cut = df_all.loc[df_all["condition"] == "T7_S_cut", "C_end"].to_numpy()
    rich = df_all.loc[df_all["condition"] == "T4_S_rich", "C_end"].to_numpy()

    N_a, N_b = len(rich), len(cut)
    if N_a < spec.n_min or N_b < spec.n_min:
        return {"test_id": "T7", "verdict": "INDETERMINATE", "reason": "N_min", "N_a": N_a, "N_b": N_b}

    diff = float(np.mean(cut) - np.mean(rich))  # attendu négatif
    mad = robust_mad(rich)
    eff = diff / mad if mad != 0 else float("nan")

    p = float(stats.ttest_ind(cut, rich, equal_var=False).pvalue)
    ci = bootstrap_ci_diff(rich, cut, ci_level=spec.ci_level)  # (b - a) = cut - rich
    power = power_gate_two_sample(rich, cut, alpha=spec.alpha, target_delta=(-spec.sesoi_c_mad) * mad)

    verdict = verdict_from_triplet(
        p=p,
        ci=ci,
        effect=eff,
        sesoi=-spec.sesoi_c_mad,
        power=power,
        alpha=spec.alpha,
        power_gate=spec.power_gate,
        direction="neg",
    )

    return {
        "test_id": "T7",
        "metric": "C_end",
        "condition_a": "S_rich",
        "condition_b": "S_cut",
        "N_a": N_a,
        "N_b": N_b,
        "estimate": diff,
        "effect": eff,
        "sesoi": -spec.sesoi_c_mad,
        "p_value": p,
        "ci_low": ci[0],
        "ci_high": ci[1],
        "ci_level": spec.ci_level,
        "power_sesoi": power,
        "verdict": verdict,
    }


def aggregate_global(local: Dict[str, str]) -> Dict[str, str]:
    noyau = "INDETERMINATE"
    if local.get("T1") == "ACCEPT" and local.get("T2") == "ACCEPT" and local.get("T3") == "ACCEPT":
        noyau = "ACCEPT"
    elif any(local.get(k) == "REJECT" for k in ["T1", "T2", "T3"]):
        noyau = "REJECT"

    symbolic = "INDETERMINATE"
    if local.get("T4") == "ACCEPT" and local.get("T7") == "ACCEPT" and not any(local.get(k) == "REJECT" for k in ["T4", "T7"]):
        symbolic = "ACCEPT"
    elif local.get("T4") in ["REJECT", "INDETERMINATE"] and local.get("T7") == "REJECT":
        symbolic = "REJECT"

    return {"noyau": noyau, "symbolic": symbolic}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite-outdir", default="05_Results/oric_suite")
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--n-min", type=int, default=50)
    args = ap.parse_args()

    spec = DecisionSpec(alpha=args.alpha, ci_level=1.0 - args.alpha, n_min=args.n_min)

    runs_path = os.path.join(args.suite_outdir, "tables", "oric_suite_runs.csv")
    if not os.path.exists(runs_path):
        raise SystemExit(f"Missing input: {runs_path}")

    df = pd.read_csv(runs_path)

    gate = gate_condition(df, spec)
    outdir = os.path.join(args.suite_outdir, "verdicts")
    ensure_dir(outdir)

    verdict_rows: List[Dict[str, Any]] = []

    if not gate["gate_ok"]:
        verdict_rows.append({"test_id": "GATE", "verdict": "INDETERMINATE", "reason": "missing_columns", "missing": ",".join(gate["missing_columns"])})
        local_map = {"T1": "INDETERMINATE", "T2": "INDETERMINATE", "T3": "INDETERMINATE", "T4": "INDETERMINATE", "T7": "INDETERMINATE"}
    else:
        df_t1 = df[df["test_id"] == "T1"].copy()
        df_t3 = df[df["test_id"] == "T3"].copy()
        df_t4 = df[df["test_id"] == "T4"].copy()

        t1_o = test1_main_effect(df_t1, "init_O", spec)
        t1_r = test1_main_effect(df_t1, "init_R", spec)
        t1_i = test1_main_effect(df_t1, "init_I", spec)
        verdict_rows.extend([t1_o, t1_r, t1_i])

        # Agrégation T1: ACCEPT si au moins 2 ACCEPT, REJECT si au moins 1 REJECT, sinon INDETERMINATE.
        t1_verdicts = [t1_o.get("verdict"), t1_r.get("verdict"), t1_i.get("verdict")]
        if t1_verdicts.count("ACCEPT") >= 2 and "REJECT" not in t1_verdicts:
            t1_global = "ACCEPT"
        elif "REJECT" in t1_verdicts:
            t1_global = "REJECT"
        else:
            t1_global = "INDETERMINATE"
        verdict_rows.append({"test_id": "T1", "metric": "Cap_mean", "verdict": t1_global})

        t2 = test2_sigma_positive(df_t3, spec)
        t3 = test3_v_degrades(df_t3, spec)
        t4 = test4_symbolic_rich_poor(df_t4, spec)
        t7 = test7_symbolic_cut(df, spec)
        verdict_rows.extend([t2, t3, t4, t7])

        local_map = {
            "T1": t1_global,
            "T2": t2.get("verdict", "INDETERMINATE"),
            "T3": t3.get("verdict", "INDETERMINATE"),
            "T4": t4.get("verdict", "INDETERMINATE"),
            "T7": t7.get("verdict", "INDETERMINATE"),
        }

    globals_ = aggregate_global(local_map)

    # Write local verdicts
    local_path = os.path.join(outdir, "verdicts_local.csv")
    pd.DataFrame(verdict_rows).to_csv(local_path, index=False)

    # Write global
    global_path = os.path.join(outdir, "verdicts_global.json")
    with open(global_path, "w", encoding="utf-8") as f:
        json.dump({"spec": spec.__dict__, "gate": gate, "local": local_map, "global": globals_}, f, indent=2)

    # Diagnostics
    diag_path = os.path.join(outdir, "diagnostics.md")
    with open(diag_path, "w", encoding="utf-8") as f:
        f.write("# Diagnostics decision rules\n\n")
        f.write(f"- Input: {runs_path}\n")
        f.write(f"- alpha: {spec.alpha}\n")
        f.write(f"- CI level: {spec.ci_level}\n")
        f.write(f"- N_min: {spec.n_min}\n")
        f.write(f"- Gate ok: {gate['gate_ok']}\n")
        if not gate["gate_ok"]:
            f.write(f"- Missing columns: {', '.join(gate['missing_columns'])}\n")
        f.write("\n## Verdicts globaux\n\n")
        f.write(f"- Noyau: {globals_['noyau']}\n")
        f.write(f"- Symbolique: {globals_['symbolic']}\n")
        f.write("\n## Verdicts locaux\n\n")
        for k, v in local_map.items():
            f.write(f"- {k}: {v}\n")

    print(f"Wrote: {local_path}")
    print(f"Wrote: {global_path}")
    print(f"Wrote: {diag_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
