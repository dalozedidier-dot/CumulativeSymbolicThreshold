"""registered_block.py — the frozen, pre-registered real-data A/B/C block.

This is the apparatus for the *one real rung* above "exploratory": a complete
real-data block whose every choice is frozen **before** the outcome is known
(see ``contracts/REAL_DATA_REGISTRATION.json`` and the matching pre-registration
in ``02_Protocol``).

Design (frozen)
---------------
  A  test    — a real series with a *dated* hypothesised transition window [t1,t2].
  B  stable  — the pre-onset segment of A (quiescent) + an independent external
               stable series. Expected: NO detection.
  C  placebo — a cyclic-shift surrogate of A (autocorrelation preserved, onset
               alignment destroyed). Expected: NO detection.

For every condition we run the ORI-C localized-transition gate and a panel of
classical baselines (CUSUM, a dependency-free PELT/AMOC change-point, an
early-warning-signal test, and a structural break). On A we additionally run an
IAAFT surrogate null and a pre-registered out-of-sample split (train < t*,
test >= t*). A single frozen aggregation rule turns all of this into one verdict
token. The honest expectation on a hard macro series (FRED) is **not** a
confirmation — that is the point of registering it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from oric.comparative_benchmark import (
    cusum_changepoint,
    early_warning_signal,
    structural_break,
)

# ── PELT / AMOC change-point (dependency-free; no `ruptures` needed) ──────────

def pelt_changepoint(series: np.ndarray, *, min_size: int = 10) -> dict:
    """At-most-one-change (AMOC) Gaussian change-point with a BIC penalty.

    The PELT family reduces, for a single change, to the split that maximally
    drops the Gaussian negative-log-likelihood cost ``n·log(var)``. A change is
    declared when that drop exceeds the BIC penalty ``2·log(n)`` (two extra
    parameters: a second mean and variance). Returns a MethodResult-shaped dict.
    """
    x = np.asarray(series, dtype=float)
    n = x.size

    def cost(seg: np.ndarray) -> float:
        if seg.size < 2:
            return 0.0
        var = float(np.var(seg))
        var = max(var, 1e-12)
        return float(seg.size * np.log(var))

    if n < 2 * min_size:
        return {"method": "pelt_changepoint", "detected": False,
                "detection_point": None, "statistic": 0.0, "notes": "series too short"}

    base = cost(x)
    best_tau, best_gain = None, 0.0
    for tau in range(min_size, n - min_size):
        gain = base - (cost(x[:tau]) + cost(x[tau:]))
        if gain > best_gain:
            best_gain, best_tau = gain, tau

    penalty = 2.0 * np.log(n)
    detected = bool(best_tau is not None and best_gain > penalty)
    return {
        "method": "pelt_changepoint",
        "detected": detected,
        "detection_point": int(best_tau) if (detected and best_tau is not None) else None,
        "statistic": float(best_gain),
        "notes": f"penalty={penalty:.2f}",
    }


# ── ORI-C localized detector on one (t,O,R,I,demand,S) frame ──────────────────

def _import_pipeline():
    try:
        from pipeline.ori_c_pipeline import ORICConfig, run_oric_from_observations  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover - layout-dependent
        from ori_c_pipeline import ORICConfig, run_oric_from_observations  # type: ignore
    return ORICConfig, run_oric_from_observations


def _first_sustained_index(dc: np.ndarray, threshold: float, m: int) -> int | None:
    """First index of the earliest run of >= m consecutive ΔC > threshold."""
    consec = 0
    for i, v in enumerate(np.asarray(dc, dtype=float)):
        if v > threshold:
            consec += 1
            if consec >= int(m):
                return i - int(m) + 1
        else:
            consec = 0
    return None


def oric_localized_detect(
    df: pd.DataFrame, *, k: float, m: int, baseline_n: int, seed: int,
    run_fn: Callable | None = None,
) -> dict:
    """Run ORI-C and return the localized-gate decision + the order series C."""
    from oric.surrogates import localized_transition_statistic, threshold_crossing_statistic

    ORICConfig, run_oric_from_observations = _import_pipeline()
    if run_fn is None:
        run_fn = run_oric_from_observations
    cfg = ORICConfig(seed=seed, n_steps=len(df), intervention="none",
                     k=k, m=m, baseline_n=baseline_n)
    out = run_fn(df, cfg)
    if "delta_C" not in out.columns:
        out = out.copy()
        out["delta_C"] = out["C"].diff().fillna(0.0)
    dc = out["delta_C"].to_numpy()
    loc = localized_transition_statistic(dc, k=k, m=m, baseline_n=baseline_n)
    cs = threshold_crossing_statistic(dc, k=k, m=m, baseline_n=baseline_n)
    point = _first_sustained_index(dc, cs.threshold, m) if loc.localized_hit else None
    return {
        "detected": bool(loc.localized_hit),
        "detection_point": (int(point) if point is not None else None),
        "crossing_rate": float(cs.crossing_rate),
        "max_run": int(cs.max_run),
        "C": out["C"].to_numpy(),
        "delta_C": dc,
        "_cfg": cfg,
        "_df": df,
    }


# ── Classical baseline panel on one series ────────────────────────────────────

def classical_panel(series: np.ndarray) -> dict:
    """Run the classical baselines and return {method: result-dict}."""
    x = np.asarray(series, dtype=float)
    out = {
        "cusum_changepoint": cusum_changepoint(x).to_dict(),
        "pelt_changepoint": pelt_changepoint(x),
        "early_warning_signal": early_warning_signal(x).to_dict(),
        "structural_break": structural_break(x).to_dict(),
    }
    return out


# ── Control construction (frozen) ─────────────────────────────────────────────

def derive_controls(df_A: pd.DataFrame, *, t1: int, shift_divisor: int = 3) -> dict:
    """Derive the stable (pre-onset) and placebo (cyclic-shift) controls of A."""
    n = len(df_A)
    t1 = max(5, min(int(t1), n - 1))
    stable = df_A.iloc[:t1].reset_index(drop=True).copy()
    shift = max(1, n // int(shift_divisor))
    idx = (np.arange(n) + shift) % n
    placebo = df_A.iloc[idx].reset_index(drop=True).copy()
    if "t" in placebo.columns:
        placebo["t"] = np.arange(n)
    return {"stable": stable, "placebo": placebo}


# ── Out-of-sample (train < t*, test >= t*) on the real order series ───────────

def oos_real_split(order_C: np.ndarray, t_star: int, *, n_surrogates: int,
                   alpha: float, seed: int) -> dict:
    """Pre-registered OOS: from the pre-t* run-up alone, does the localized CSD
    predictor flag a coming transition, and does it land after t*?"""
    from oric.oos_prediction import predict_transition

    C = np.asarray(order_C, dtype=float)
    t_star = int(t_star)
    if t_star < 20 or t_star >= len(C) - 5:
        return {"evaluable": False, "reason": "t_star outside a usable range"}
    pred = predict_transition(C[:t_star], n_surrogates=n_surrogates, alpha=alpha,
                              rng=np.random.default_rng(seed + 50_000))
    onset = getattr(pred, "predicted_onset", None)
    # Skill = predicted AND (no usable onset estimate OR onset is at/after t*-tolerance).
    forward = bool(pred.predicted and (onset is None or onset >= t_star - 12))
    return {
        "evaluable": True,
        "predicted": bool(pred.predicted),
        "predicted_onset": (int(onset) if onset is not None else None),
        "t_star": t_star,
        "directional_skill": forward,
    }


# ── Aggregate verdict (frozen rule) ───────────────────────────────────────────

@dataclass
class BlockCriteria:
    k: float = 2.5
    m: int = 3
    baseline_n: int = 50
    alpha: float = 0.01
    seed: int = 1234
    n_surrogates: int = 200
    onset_tolerance: int = 18          # months: detection must land near [t1,t2]
    shift_divisor: int = 3


def _within_window(point: int | None, t1: int, t2: int, tol: int) -> bool:
    return point is not None and (t1 - tol) <= point <= (t2 + tol)


def run_registered_block(
    contract: dict,
    datasets: dict[str, pd.DataFrame],
    *,
    fast: bool = False,
    run_fn: Callable | None = None,
) -> dict:
    """Execute the frozen A/B/C block and return a structured result + verdict.

    ``datasets`` maps roles to already-loaded frames: required "A" (test) and
    optional "external_stable". B (stable) and C (placebo) are derived from A.
    """
    cr = BlockCriteria(**contract.get("criteria", {}))
    if fast:
        cr.n_surrogates = min(cr.n_surrogates, 40)
    hyp = contract["dated_hypothesis"]
    t1, t2, t_star = int(hyp["t1"]), int(hyp["t2"]), int(hyp["t_star"])

    A = datasets["A"]

    # 1. ORI-C on A
    a = oric_localized_detect(A, k=cr.k, m=cr.m, baseline_n=cr.baseline_n, seed=cr.seed, run_fn=run_fn)
    a_detected = a["detected"]
    a_in_window = _within_window(a["detection_point"], t1, t2, cr.onset_tolerance)

    # 2. Controls B (stable + external) and C (placebo)
    ctrl = derive_controls(A, t1=t1, shift_divisor=cr.shift_divisor)
    b_stable = oric_localized_detect(ctrl["stable"], k=cr.k, m=cr.m, baseline_n=min(cr.baseline_n, max(10, t1 // 2)), seed=cr.seed, run_fn=run_fn)
    c_placebo = oric_localized_detect(ctrl["placebo"], k=cr.k, m=cr.m, baseline_n=cr.baseline_n, seed=cr.seed, run_fn=run_fn)
    b_external = None
    if "external_stable" in datasets:
        ext = datasets["external_stable"]
        b_external = oric_localized_detect(ext, k=cr.k, m=cr.m, baseline_n=min(cr.baseline_n, max(10, len(ext) // 3)), seed=cr.seed, run_fn=run_fn)

    b_silent = (not b_stable["detected"]) and (b_external is None or not b_external["detected"])
    c_silent = not c_placebo["detected"]

    # 3. Classical baselines (on ΔC) for A / B / C
    classical = {
        "A": classical_panel(a["delta_C"]),
        "B_stable": classical_panel(b_stable["delta_C"]),
        "C_placebo": classical_panel(c_placebo["delta_C"]),
    }

    def _n_classical_fire(panel: dict) -> int:
        return sum(1 for r in panel.values() if r.get("detected"))

    classical_false_on_controls = _n_classical_fire(classical["B_stable"]) + _n_classical_fire(classical["C_placebo"])

    # 4. IAAFT surrogate null on A
    from oric.surrogates import surrogate_null_test
    surr = surrogate_null_test(
        A, a["_cfg"], n_surrogates=cr.n_surrogates, statistic="crossing_rate",
        rng=np.random.default_rng(cr.seed + 11), run_fn=run_fn,
    )
    surrogate_significant = bool(surr.significant_at_01)

    # 5. OOS (train < t*, test >= t*)
    oos = oos_real_split(a["C"], t_star, n_surrogates=cr.n_surrogates, alpha=0.05, seed=cr.seed)

    # 6. Frozen aggregation rule → verdict
    reasons: list[str] = []
    if not a_detected:
        reasons.append("A: ORI-C did not fire a localized transition")
    elif not a_in_window:
        reasons.append(f"A: detection point {a['detection_point']} outside hypothesis window [{t1},{t2}]±{cr.onset_tolerance}")
    if not b_silent:
        reasons.append("B: a stable control fired (non-specific)")
    if not c_silent:
        reasons.append("C: placebo fired (non-specific)")
    if not surrogate_significant:
        reasons.append(f"A: crossing not significant vs IAAFT null (p={surr.p_value:.3f} >= {cr.alpha})")
    if not (oos.get("evaluable") and oos.get("directional_skill")):
        reasons.append("OOS: no pre-t* directional skill")

    decidable = a.get("crossing_rate") is not None
    if not decidable:
        verdict = "REAL_BLOCK_INDETERMINATE"
    elif reasons:
        verdict = "REAL_BLOCK_REJECTED"
    else:
        verdict = "REAL_BLOCK_CONFIRMED"

    return {
        "schema": "oric.registered_block.v1",
        "dataset_A": contract.get("dataset_A", {}).get("id", "A"),
        "dated_hypothesis": {"t1": t1, "t2": t2, "t_star": t_star,
                             "window_label": hyp.get("label", "")},
        "criteria": cr.__dict__,
        "A": {"detected": a_detected, "in_window": a_in_window,
              "detection_point": a["detection_point"], "crossing_rate": a["crossing_rate"]},
        "B_silent": b_silent, "C_silent": c_silent,
        "controls": {
            "stable_detected": b_stable["detected"],
            "external_stable_detected": (b_external["detected"] if b_external else None),
            "placebo_detected": c_placebo["detected"],
        },
        "surrogate": {"p_value": float(surr.p_value), "significant_at_01": surrogate_significant},
        "classical": classical,
        "classical_false_positives_on_controls": classical_false_on_controls,
        "oos": oos,
        "verdict": verdict,
        "reasons": reasons,
        "note": (
            "A frozen, pre-registered real-data block. A REJECTED/INDETERMINATE "
            "verdict is an honest negative reported at equal status to a positive."
        ),
    }
