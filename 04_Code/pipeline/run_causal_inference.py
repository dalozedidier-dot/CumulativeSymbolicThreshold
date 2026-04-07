#!/usr/bin/env python3
"""04_Code/pipeline/run_causal_inference.py

Reinforced causal inference: CCM, Transfer Entropy, Natural Experiments, DAG tests.

Usage:
  python 04_Code/pipeline/run_causal_inference.py --all --outdir 05_Results/causal_inference/
  python 04_Code/pipeline/run_causal_inference.py --help
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

SEED = 8000


# ── 1. Convergent Cross Mapping (CCM) ────────────────────────────────────

def _delay_embed(x: np.ndarray, E: int, tau: int = 1) -> np.ndarray:
    """Create delay embedding matrix of dimension E with lag tau."""
    n = len(x)
    m = n - (E - 1) * tau
    if m < E + 1:
        return np.empty((0, E))
    embed = np.zeros((m, E))
    for d in range(E):
        embed[:, d] = x[d * tau: d * tau + m]
    return embed


def _ccm_predict(x: np.ndarray, y: np.ndarray, E: int, tau: int = 1,
                 lib_sizes: list[int] | None = None) -> list[tuple[int, float]]:
    """Convergent Cross Mapping: does X causally influence Y?

    Uses shadow manifold of Y to predict X. If prediction improves
    with library size L, suggests X -> Y causality.
    """
    n = len(x)
    if n < 20:
        return []

    Mx = _delay_embed(x, E, tau)
    My = _delay_embed(y, E, tau)
    m = min(len(Mx), len(My))
    if m < E + 2:
        return []
    Mx = Mx[:m]
    My = My[:m]
    x_short = x[(E - 1) * tau: (E - 1) * tau + m]

    if lib_sizes is None:
        lib_sizes = [max(E + 2, m // 5), max(E + 2, m // 2), m]
        lib_sizes = sorted(set([min(ls, m) for ls in lib_sizes]))

    rng = np.random.default_rng(SEED)
    results = []

    for L in lib_sizes:
        if L < E + 2 or L > m:
            continue
        # Subsample library
        idx = rng.choice(m, size=L, replace=False)
        My_lib = My[idx]
        x_lib = x_short[idx]

        # For each point in library, find E+1 nearest neighbors in My
        preds = []
        actuals = []
        for i in range(L):
            dists = np.sqrt(np.sum((My_lib - My_lib[i]) ** 2, axis=1))
            dists[i] = np.inf  # exclude self
            nn = np.argsort(dists)[:E + 1]
            d_nn = dists[nn]
            d_nn = np.maximum(d_nn, 1e-12)
            w = np.exp(-d_nn / max(d_nn[0], 1e-12))
            w = w / max(w.sum(), 1e-12)
            pred = np.dot(w, x_lib[nn])
            preds.append(pred)
            actuals.append(x_lib[i])

        preds = np.array(preds)
        actuals = np.array(actuals)
        if np.std(preds) > 1e-12 and np.std(actuals) > 1e-12:
            rho = float(np.corrcoef(preds, actuals)[0, 1])
        else:
            rho = 0.0
        results.append((L, rho))

    return results


def test_ccm(S: np.ndarray, C: np.ndarray) -> dict:
    """Test CCM in both directions: S xmap C and C xmap S."""
    best_E = 2
    results_SC = []
    results_CS = []

    for E in range(2, 6):
        sc = _ccm_predict(S, C, E)
        cs = _ccm_predict(C, S, E)
        if sc:
            results_SC.append((E, sc))
        if cs:
            results_CS.append((E, cs))

    # Pick best E by max correlation at largest L
    def _best_result(res_list):
        best_rho = -1
        best = []
        for E, res in res_list:
            if res and res[-1][1] > best_rho:
                best_rho = res[-1][1]
                best = res
        return best, best_rho

    sc_best, sc_rho = _best_result(results_SC)
    cs_best, cs_rho = _best_result(results_CS)

    # Convergence: does correlation increase with L?
    def _is_convergent(res):
        if len(res) < 2:
            return False
        rhos = [r[1] for r in res]
        return rhos[-1] > rhos[0] + 0.05

    return {
        "ccm_S_xmap_C_rho": float(sc_rho) if np.isfinite(sc_rho) else 0.0,
        "ccm_C_xmap_S_rho": float(cs_rho) if np.isfinite(cs_rho) else 0.0,
        "ccm_S_causes_C_convergent": _is_convergent(sc_best),
        "ccm_C_causes_S_convergent": _is_convergent(cs_best),
        "ccm_direction": "S->C" if sc_rho > cs_rho + 0.1 else (
            "C->S" if cs_rho > sc_rho + 0.1 else "bidirectional/unclear"),
    }


# ── 2. Transfer Entropy ──────────────────────────────────────────────────

def _discretize(x: np.ndarray, n_bins: int = 5) -> np.ndarray:
    """Adaptive binning discretization."""
    try:
        bins = np.quantile(x[np.isfinite(x)], np.linspace(0, 1, n_bins + 1))
        bins = np.unique(bins)
        if len(bins) < 2:
            return np.zeros_like(x, dtype=int)
        return np.clip(np.digitize(x, bins[1:-1]), 0, len(bins) - 2)
    except Exception:
        return np.zeros_like(x, dtype=int)


def _transfer_entropy(source: np.ndarray, target: np.ndarray,
                      lag: int = 1, n_bins: int = 5) -> float:
    """Compute transfer entropy TE(source -> target) using histograms."""
    n = len(source)
    if n < lag + 10:
        return 0.0

    s_d = _discretize(source, n_bins)
    t_d = _discretize(target, n_bins)

    # TE = H(T_future | T_past) - H(T_future | T_past, S_past)
    # Using joint entropy estimation
    t_past = t_d[:-lag]
    t_future = t_d[lag:]
    s_past = s_d[:-lag]
    m = len(t_past)

    # Joint counts
    from collections import Counter
    joint_tps = Counter(zip(t_past, s_past))
    joint_tp = Counter(t_past)
    joint_tps_tf = Counter(zip(t_past, s_past, t_future))
    joint_tp_tf = Counter(zip(t_past, t_future))

    te = 0.0
    for (tp, sp, tf), count in joint_tps_tf.items():
        p_tp_sp_tf = count / m
        p_tf_given_tp_sp = count / max(joint_tps[(tp, sp)], 1)
        p_tf_given_tp = joint_tp_tf[(tp, tf)] / max(joint_tp[tp], 1)
        if p_tf_given_tp_sp > 0 and p_tf_given_tp > 0:
            te += p_tp_sp_tf * np.log2(p_tf_given_tp_sp / p_tf_given_tp)

    return float(te)


def test_transfer_entropy(S: np.ndarray, C: np.ndarray,
                          n_shuffles: int = 500) -> dict:
    """Compute TE in both directions with permutation significance test."""
    rng = np.random.default_rng(SEED)

    te_s_to_c = _transfer_entropy(S, C)
    te_c_to_s = _transfer_entropy(C, S)

    # Permutation test for significance
    null_sc = np.zeros(n_shuffles)
    null_cs = np.zeros(n_shuffles)
    for i in range(n_shuffles):
        S_shuf = rng.permutation(S)
        C_shuf = rng.permutation(C)
        null_sc[i] = _transfer_entropy(S_shuf, C)
        null_cs[i] = _transfer_entropy(C, S_shuf)

    p_sc = float(np.mean(null_sc >= te_s_to_c))
    p_cs = float(np.mean(null_cs >= te_c_to_s))

    return {
        "te_S_to_C": float(te_s_to_c),
        "te_C_to_S": float(te_c_to_s),
        "te_S_to_C_p": p_sc,
        "te_C_to_S_p": p_cs,
        "te_S_to_C_significant": p_sc < 0.01,
        "te_C_to_S_significant": p_cs < 0.01,
        "te_direction": "S->C" if (p_sc < 0.01 and te_s_to_c > te_c_to_s) else (
            "C->S" if (p_cs < 0.01 and te_c_to_s > te_s_to_c) else "unclear"),
    }


# ── 3. Natural Experiment / Diff-in-Diff ─────────────────────────────────

# NBER recession dates (month-level, start dates)
NBER_RECESSIONS = [
    ("1990-07", "1991-03"),
    ("2001-03", "2001-11"),
    ("2007-12", "2009-06"),
    ("2020-02", "2020-04"),
]


def test_natural_experiment(df: pd.DataFrame, dataset_id: str) -> dict:
    """Diff-in-diff around exogenous shocks."""
    result = {"applicable": False, "events_tested": 0}

    if "S" not in df.columns or "C" not in df.columns:
        # Try to compute C from available data
        if "S" in df.columns:
            C = np.nancumsum(pd.to_numeric(df["S"], errors="coerce").fillna(0).values) * 0.4
            df = df.copy()
            df["C"] = C
        else:
            return result

    n = len(df)

    # Detect if this is a FRED-like dataset with year/month
    has_dates = "year" in df.columns and "month" in df.columns

    if has_dates:
        # Use NBER recession dates
        events = []
        for start, end in NBER_RECESSIONS:
            sy, sm = int(start[:4]), int(start[5:7])
            ey, em = int(end[:4]), int(end[5:7])
            # Find index
            mask = (df["year"] * 100 + df["month"]) >= sy * 100 + sm
            mask2 = (df["year"] * 100 + df["month"]) <= ey * 100 + em
            idx = df.index[mask & mask2]
            if len(idx) >= 2:
                events.append((int(idx[0]), int(idx[-1]), start))
    else:
        # Use structural breaks as pseudo-events
        mid = n // 2
        events = [(mid, min(mid + n // 10, n - 1), "midpoint")]

    if not events:
        return result

    result["applicable"] = True
    result["events_tested"] = len(events)
    did_results = []

    for event_start, event_end, label in events:
        pre_window = max(0, event_start - 24)
        post_window = min(n, event_end + 24)

        C = df["C"].values.astype(float)
        S = df["S"].values.astype(float)

        C_pre = C[pre_window:event_start]
        C_post = C[event_end:post_window]
        S_pre = S[pre_window:event_start]
        S_post = S[event_end:post_window]

        if len(C_pre) < 5 or len(C_post) < 5:
            continue

        # DiD: compare C change where S maintained vs S cut
        delta_C = np.mean(C_post) - np.mean(C_pre)
        delta_S = np.mean(S_post) - np.mean(S_pre)

        # Simple test: is the C shift significant?
        t_stat, p_val = stats.ttest_ind(C_post, C_pre, equal_var=False)

        did_results.append({
            "event": label,
            "delta_C": float(delta_C),
            "delta_S": float(delta_S),
            "t_stat": float(t_stat) if np.isfinite(t_stat) else None,
            "p_value": float(p_val) if np.isfinite(p_val) else None,
            "significant": float(p_val) < 0.01 if np.isfinite(p_val) else False,
        })

    result["did_results"] = did_results
    return result


# ── 4. DAG conditional independence tests ─────────────────────────────────

def _partial_corr(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple[float, float]:
    """Partial correlation of x and y controlling for z."""
    n = len(x)
    if n < 10 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return 0.0, 1.0

    # Residualize x and y on z
    try:
        z_mat = z.reshape(-1, 1) if z.ndim == 1 else z
        from numpy.linalg import lstsq
        beta_x, _, _, _ = lstsq(np.column_stack([z_mat, np.ones(n)]), x, rcond=None)
        beta_y, _, _, _ = lstsq(np.column_stack([z_mat, np.ones(n)]), y, rcond=None)
        res_x = x - np.column_stack([z_mat, np.ones(n)]) @ beta_x
        res_y = y - np.column_stack([z_mat, np.ones(n)]) @ beta_y

        if np.std(res_x) < 1e-12 or np.std(res_y) < 1e-12:
            return 0.0, 1.0

        r = float(np.corrcoef(res_x, res_y)[0, 1])
        # Fisher z-transform for p-value
        z_val = 0.5 * np.log((1 + r) / max(1 - r, 1e-12))
        se = 1.0 / np.sqrt(max(n - 3 - z_mat.shape[1], 1))
        p = 2 * (1 - stats.norm.cdf(abs(z_val) / se))
        return float(r), float(p)
    except Exception:
        return 0.0, 1.0


def test_dag_implications(df: pd.DataFrame) -> dict:
    """Test conditional independence implications of the ORI-C DAG.

    DAG: O->Cap, R->Cap, I->Cap, Cap->Sigma, D->Sigma, Sigma->V, S->C, C->deltaC
    Implication: S _|_ O | Cap  (S independent of O given Cap)
    """
    result = {"tests": []}

    available = {c: pd.to_numeric(df[c], errors="coerce").fillna(0).values
                 for c in ["O", "R", "I", "S", "demand"] if c in df.columns}

    if len(available) < 4:
        result["note"] = "Insufficient columns for DAG tests"
        return result

    O = available.get("O", np.zeros(len(df)))
    R = available.get("R", np.zeros(len(df)))
    I = available.get("I", np.zeros(len(df)))
    S = available.get("S", np.zeros(len(df)))
    demand = available.get("demand", np.zeros(len(df)))

    Cap = O * R * I

    # Test 1: S _|_ O | Cap
    r, p = _partial_corr(S, O, Cap)
    result["tests"].append({
        "implication": "S _|_ O | Cap",
        "partial_corr": float(r), "p_value": float(p),
        "independent": float(p) > 0.05,
        "interpretation": "S is independent of O given Cap (expected)" if p > 0.05
            else "S is NOT independent of O given Cap (DAG violation)",
    })

    # Test 2: S _|_ R | Cap
    r, p = _partial_corr(S, R, Cap)
    result["tests"].append({
        "implication": "S _|_ R | Cap",
        "partial_corr": float(r), "p_value": float(p),
        "independent": float(p) > 0.05,
    })

    # Test 3: S _|_ I | Cap
    r, p = _partial_corr(S, I, Cap)
    result["tests"].append({
        "implication": "S _|_ I | Cap",
        "partial_corr": float(r), "p_value": float(p),
        "independent": float(p) > 0.05,
    })

    # Test 4: O _|_ demand | Cap (O independent of demand given Cap)
    r, p = _partial_corr(O, demand, Cap)
    result["tests"].append({
        "implication": "O _|_ demand | Cap",
        "partial_corr": float(r), "p_value": float(p),
        "independent": float(p) > 0.05,
    })

    n_pass = sum(1 for t in result["tests"] if t.get("independent", False))
    result["n_tests"] = len(result["tests"])
    result["n_pass"] = n_pass
    result["dag_consistent"] = n_pass >= len(result["tests"]) // 2

    return result


# ── Main pipeline ─────────────────────────────────────────────────────────

def _discover_datasets(root: Path) -> list[Path]:
    datasets = []
    for p in sorted(root.rglob("real.csv")):
        if (p.parent / "proxy_spec.json").exists():
            datasets.append(p.parent)
    return datasets


def analyze_dataset(ds_dir: Path, outdir: Path) -> dict:
    """Run all causal inference tests on one dataset."""
    csv_path = ds_dir / "real.csv"
    df = pd.read_csv(csv_path)
    ds_id = ds_dir.name
    ds_out = outdir / ds_id
    ds_out.mkdir(parents=True, exist_ok=True)

    result = {"dataset_id": ds_id, "n": len(df)}

    # Prepare S and C
    S = np.zeros(len(df))
    if "S" in df.columns:
        S = pd.to_numeric(df["S"], errors="coerce").fillna(0).values
    C = np.nancumsum(S) * 0.4  # approximate C from S if not available
    if "C" in df.columns:
        C = pd.to_numeric(df["C"], errors="coerce").fillna(0).values

    # 1. CCM
    try:
        result["ccm"] = test_ccm(S, C)
    except Exception as e:
        result["ccm"] = {"error": str(e)}

    # 2. Transfer Entropy
    try:
        result["transfer_entropy"] = test_transfer_entropy(S, C, n_shuffles=500)
    except Exception as e:
        result["transfer_entropy"] = {"error": str(e)}

    # 3. Natural experiments
    try:
        result["natural_experiment"] = test_natural_experiment(df, ds_id)
    except Exception as e:
        result["natural_experiment"] = {"error": str(e)}

    # 4. DAG tests
    try:
        result["dag"] = test_dag_implications(df)
    except Exception as e:
        result["dag"] = {"error": str(e)}

    # Save per-dataset results
    (ds_out / "causal_results.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Reinforced causal inference")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dataset", type=str, default=None)
    ap.add_argument("--outdir", default="05_Results/causal_inference/")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.dataset:
        datasets = [Path(args.dataset)]
    elif args.all:
        datasets = _discover_datasets(_REPO / "03_Data")
    else:
        ap.print_help()
        return 1

    print(f"Found {len(datasets)} datasets")

    all_results = []
    for i, ds in enumerate(datasets):
        print(f"[{i+1}/{len(datasets)}] {ds.name}...")
        try:
            result = analyze_dataset(ds, outdir)
            all_results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Generate summary report
    lines = ["# Causal Inference Report\n\n"]
    lines.append(f"Datasets analyzed: {len(all_results)}\n\n")

    lines.append("## Summary Table\n\n")
    lines.append("| Dataset | N | CCM Direction | TE Direction | DAG Consistent | DiD Events |\n")
    lines.append("|---------|---|---------------|--------------|----------------|------------|\n")

    for r in all_results:
        ccm_dir = r.get("ccm", {}).get("ccm_direction", "?")
        te_dir = r.get("transfer_entropy", {}).get("te_direction", "?")
        dag_ok = r.get("dag", {}).get("dag_consistent", "?")
        did_n = r.get("natural_experiment", {}).get("events_tested", 0)
        lines.append(f"| {r['dataset_id']} | {r['n']} | {ccm_dir} | {te_dir} | {dag_ok} | {did_n} |\n")

    lines.append("\n## Method Details\n\n")
    lines.append("### CCM (Convergent Cross Mapping)\n")
    lines.append("Tests nonlinear causal coupling via attractor reconstruction.\n\n")
    lines.append("### Transfer Entropy\n")
    lines.append("Non-parametric information-theoretic causality with permutation test (500 shuffles).\n\n")
    lines.append("### Natural Experiments\n")
    lines.append("DiD around NBER recessions (FRED) or structural midpoints.\n\n")
    lines.append("### DAG Conditional Independence\n")
    lines.append("Tests implications: S _|_ O|Cap, S _|_ R|Cap, S _|_ I|Cap, O _|_ demand|Cap\n")

    (outdir / "causal_report.md").write_text("".join(lines), encoding="utf-8")
    (outdir / "causal_results_all.json").write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8")

    print(f"\nDone. Results in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
