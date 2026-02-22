#!/usr/bin/env python3
# 04_Code/pipeline/analyse_verdicts_canonical.py
"""Run-mode-aware aggregator for canonical T1–T8 verdicts.

Reads a run directory produced by run_all_tests.py:
  <run_dir>/manifest.json                → run_mode, seed_table
  <run_dir>/T1_noyau_demand_shock/verdict.txt
  <run_dir>/T2_threshold_demo_on_dataset/verdict.txt
  ... (T1–T8)

Decision tree (ex ante, immutable):
  - Core ORI (T1,T2,T3):     ACCEPT if all three ACCEPT or T3 INDETERMINATE (low power)
  - Symbolic (T4,T5,T6,T7):  ACCEPT if T4 ACCEPT AND at least one of T5/T6/T7 ACCEPT
  - Global:                  ACCEPT if core AND symbolic both ACCEPT

Full-validation gate (Option B — machine-enforced):
  For each STATISTICAL test (T1, T4, T5, T6, T7, T8), the aggregator reads the
  test's verdict.json / summary.json and verifies:
    1. All four triplet booleans present AND True:
         p_ok, ci_ok, sesoi_ok, power_ok
    2. N ≥ 50 per condition (or exempt if bootstrap B is the N, e.g. T7)
  "full_statistical_support" is emitted ONLY when:
    run_mode == "full_statistical"  AND  all_gates_passed == True
  Any other combination produces a non-ACCEPT support_level.

Support vocabulary (controlled, exhaustive):
  full_statistical_support        → run_mode=full_statistical + global ACCEPT + gates passed
  full_statistical_gates_failed   → run_mode=full_statistical + global ACCEPT + ≥1 gate failed
  smoke_ci_accept                 → run_mode=smoke_ci + global ACCEPT (pipeline check only)
  rejected                        → global REJECT (any run_mode)
  inconclusive                    → global INDETERMINATE (any run_mode)

Forbidden labels (NEVER valid in any report):
  "full support", "full empirical support"
  These are editorial claims, not calculated outputs.

Outputs:
  <run_dir>/global_verdicts.csv      — core / symbolic / global verdict tokens
  <run_dir>/global_verdict.json      — full audit trail with gate results
  <run_dir>/global_verdict.txt       — single token: ACCEPT / REJECT / INDETERMINATE
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import pandas as pd


VALID = {"ACCEPT", "REJECT", "INDETERMINATE"}

# Maps canonical run_all_tests.py directory prefixes → test number keys
_DIR_TO_KEY: dict[str, str] = {
    "T1_noyau_demand_shock":           "T1",
    "T2_threshold_demo_on_dataset":    "T2",
    "T3_robustness_on_dataset":        "T3",
    "T4_symbolic_S_rich_vs_poor_on_C": "T4",
    "T5_symbolic_injection_effect_on_C":"T5",
    "T6_symbolic_cut_on_C":            "T6",
    "T7_progressive_S_to_C_threshold": "T7",
    "T8_reinjection_recovery_on_C":    "T8",
}

# Statistical tests that require a verified triplet + N check.
# T2/T3 are fixed_data: single CSV run, no n_runs requirement, no triplet.
_STATISTICAL_TEST_KEYS: frozenset[str] = frozenset({"T1", "T4", "T5", "T6", "T7", "T8"})

# Minimum runs per condition for statistical validity (protocol N_min = 50).
_N_MIN: int = 50

# Tests where the "N" concept is bootstrap resamples B (hardcoded ≥500), not run count.
# These are exempt from the n_runs ≥ N_MIN check (B >> N_MIN by construction).
_N_CHECK_EXEMPT: frozenset[str] = frozenset({"T7"})

# Labels that are NEVER valid in any report derived from a run produced by this pipeline.
_FORBIDDEN_ALWAYS: list[str] = [
    "full support",
    "full empirical support",
]


# ---------------------------------------------------------------------------
# Helpers — verdict reading
# ---------------------------------------------------------------------------

def _read_verdict(path: Path) -> str:
    if not path.exists():
        return "INDETERMINATE"
    v = path.read_text(encoding="utf-8").strip().upper()
    return v if v in VALID else "INDETERMINATE"


def _read_verdicts(run_dir: Path) -> dict[str, str]:
    """Read verdict.txt for each canonical test directory."""
    verdicts: dict[str, str] = {}
    for dir_name, key in _DIR_TO_KEY.items():
        vpath = run_dir / dir_name / "verdict.txt"
        verdicts[key] = _read_verdict(vpath)
    return verdicts


def _read_manifest(run_dir: Path) -> dict:
    mpath = run_dir / "manifest.json"
    if mpath.exists():
        return json.loads(mpath.read_text(encoding="utf-8"))
    return {}


# ---------------------------------------------------------------------------
# Full-validation gate (Option B)
# ---------------------------------------------------------------------------

def _load_verdict_json(test_dir: Path) -> dict:
    """Load and merge verdict.json + summary.json from a test's tables/ subdirectory.

    Both files are read and merged so that keys present in either file are available
    to the gate checker.  summary.json keys overwrite verdict.json keys on conflict
    (summary.json is typically richer for statistical tests).
    """
    merged: dict = {}
    for fname in ("verdict.json", "summary.json"):
        p = test_dir / "tables" / fname
        if p.exists():
            try:
                merged.update(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
    return merged


def _n_from_json(data: dict, test_key: str) -> int:
    """Extract the run/sample count from a verdict.json for N gate checking.

    Field names differ by test:
      T1, T6 → "n_runs_total"  (run_ori_c_demo.py multi-run path)
      T4, T5 → "n"             (n scenarios per condition)
      T8     → "n_runs"        (run_reinjection_demo.py)
      T7     → exempt (bootstrap B=500 >> N_MIN by construction)
    """
    if test_key in _N_CHECK_EXEMPT:
        return _N_MIN  # always passes; B >> N_MIN
    for field in ("n_runs_total", "n_runs", "n"):
        val = data.get(field)
        if isinstance(val, (int, float)) and val > 0:
            return int(val)
    return 0


def _verify_triplet_gate(run_dir: Path, test_key: str) -> dict:
    """Verify that a statistical test's verdict.json contains a passing full triplet.

    Returns a dict with keys:
      test, has_triplet, p_ok, ci_ok, sesoi_ok, power_ok,
      n_runs, n_runs_ok, passed, reason (if failed)
    """
    key_to_dir = {v: k for k, v in _DIR_TO_KEY.items()}
    dir_name = key_to_dir.get(test_key, test_key)
    test_dir = run_dir / dir_name

    data = _load_verdict_json(test_dir)
    if not data:
        return {
            "test": test_key,
            "has_triplet": False,
            "p_ok": False,
            "ci_ok": False,
            "sesoi_ok": False,
            "power_ok": False,
            "n_runs": 0,
            "n_runs_ok": False,
            "passed": False,
            "reason": "verdict.json / summary.json absent or unreadable",
        }

    triplet_keys = ("p_ok", "ci_ok", "sesoi_ok", "power_ok")
    has_triplet = all(k in data for k in triplet_keys)
    p_ok     = bool(data.get("p_ok",     False))
    ci_ok    = bool(data.get("ci_ok",    False))
    sesoi_ok = bool(data.get("sesoi_ok", False))
    power_ok = bool(data.get("power_ok", False))
    n_runs   = _n_from_json(data, test_key)
    n_runs_ok = n_runs >= _N_MIN

    passed = has_triplet and p_ok and ci_ok and sesoi_ok and power_ok and n_runs_ok

    result: dict = {
        "test": test_key,
        "has_triplet": has_triplet,
        "p_ok": p_ok,
        "ci_ok": ci_ok,
        "sesoi_ok": sesoi_ok,
        "power_ok": power_ok,
        "n_runs": n_runs,
        "n_runs_ok": n_runs_ok,
        "passed": passed,
    }
    if not passed:
        reasons = []
        if not has_triplet:
            missing = [k for k in triplet_keys if k not in data]
            reasons.append(f"triplet keys missing: {missing}")
        else:
            if not p_ok:
                reasons.append("p_ok=False")
            if not ci_ok:
                reasons.append("ci_ok=False")
            if not sesoi_ok:
                reasons.append("sesoi_ok=False")
            if not power_ok:
                reasons.append("power_ok=False")
        if not n_runs_ok:
            reasons.append(f"n_runs={n_runs} < N_MIN={_N_MIN}")
        result["reason"] = "; ".join(reasons) if reasons else "unknown"
    return result


def _run_full_validation_gate(run_dir: Path) -> dict:
    """Run full-validation gate for all statistical tests.

    Returns:
      gate_passed   — True iff ALL statistical tests pass their triplet + N gate
      n_statistical — number of statistical tests checked
      n_passed      — number that passed
      failed_tests  — list of test keys that failed
      tests         — per-test gate result dicts
    """
    results: dict[str, dict] = {}
    for test_key in sorted(_STATISTICAL_TEST_KEYS):
        results[test_key] = _verify_triplet_gate(run_dir, test_key)

    failed = [k for k, r in results.items() if not r["passed"]]
    return {
        "gate_passed": len(failed) == 0,
        "n_statistical": len(_STATISTICAL_TEST_KEYS),
        "n_passed": len(_STATISTICAL_TEST_KEYS) - len(failed),
        "failed_tests": failed,
        "n_min_required": _N_MIN,
        "tests": results,
    }


# ---------------------------------------------------------------------------
# Decision tree (ex ante, immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AggregateConfig:
    allow_indeterminate_t3: bool = True  # T3 INDETERMINATE + T1/T2 ACCEPT → core ACCEPT


def aggregate_core(v: Dict[str, str], cfg: AggregateConfig) -> str:
    t1, t2, t3 = v.get("T1", "INDETERMINATE"), v.get("T2", "INDETERMINATE"), v.get("T3", "INDETERMINATE")
    if "REJECT" in (t1, t2, t3):
        return "REJECT"
    if t1 == "ACCEPT" and t2 == "ACCEPT" and t3 == "ACCEPT":
        return "ACCEPT"
    if cfg.allow_indeterminate_t3 and t1 == "ACCEPT" and t2 == "ACCEPT" and t3 == "INDETERMINATE":
        return "ACCEPT"
    return "INDETERMINATE"


def aggregate_symbolic(v: Dict[str, str]) -> str:
    t4, t5 = v.get("T4", "INDETERMINATE"), v.get("T5", "INDETERMINATE")
    t6, t7 = v.get("T6", "INDETERMINATE"), v.get("T7", "INDETERMINATE")
    if "REJECT" in (t4, t5, t6, t7):
        return "REJECT"
    if t4 == "ACCEPT" and "ACCEPT" in (t5, t6, t7):
        return "ACCEPT"
    return "INDETERMINATE"


def aggregate_global(core: str, symbolic: str) -> str:
    if core == "REJECT" or symbolic == "REJECT":
        return "REJECT"
    if core == "ACCEPT" and symbolic == "ACCEPT":
        return "ACCEPT"
    return "INDETERMINATE"


# ---------------------------------------------------------------------------
# Support level — controlled vocabulary (Option B gate enforced)
# ---------------------------------------------------------------------------

def _support_level(global_v: str, run_mode: str, gate_passed: bool) -> str:
    """Controlled vocabulary for support level.

    'full_statistical_support' requires ALL three conditions simultaneously:
      1. run_mode == 'full_statistical'   (n≥50 declared at launch)
      2. gate_passed == True             (triplet verified mechanically by this aggregator)
      3. global verdict == 'ACCEPT'

    'full support' / 'full empirical support' are NEVER valid labels in any report.
    Use only the tokens returned by this function.
    """
    if global_v == "ACCEPT":
        if run_mode == "full_statistical":
            if gate_passed:
                return "full_statistical_support"
            return "full_statistical_gates_failed"   # n≥50 declared but triplet incomplete
        return "smoke_ci_accept"   # pipeline check; NOT a full protocol validation
    if global_v == "REJECT":
        return "rejected"
    return "inconclusive"


def _forbidden_labels(support: str) -> list[str]:
    """Labels that are NEVER valid in any report derived from this run."""
    base = list(_FORBIDDEN_ALWAYS)
    if support != "full_statistical_support":
        base.append("full_statistical_support")
    return base


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate canonical T1–T8 verdicts (run_mode-aware, full-validation gate).")
    ap.add_argument("--run-dir", required=True,
                    help="Run directory produced by run_all_tests.py (contains manifest.json and T*/ subdirs).")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        raise SystemExit(f"--run-dir does not exist: {run_dir}")

    manifest = _read_manifest(run_dir)
    run_mode = manifest.get("run_mode", "unknown")
    base_seed = manifest.get("base_seed", None)
    seed_table = manifest.get("seed_table", [])

    verdicts = _read_verdicts(run_dir)
    core = aggregate_core(verdicts, AggregateConfig())
    symbolic = aggregate_symbolic(verdicts)
    global_v = aggregate_global(core, symbolic)

    # Full-validation gate (Option B): mechanical verification of triplet + N
    gate = _run_full_validation_gate(run_dir)
    support = _support_level(global_v, run_mode, gate["gate_passed"])
    forbidden = _forbidden_labels(support)

    # Write global_verdicts.csv
    rows = [
        {"level": "core",     "verdict": core},
        {"level": "symbolic", "verdict": symbolic},
        {"level": "global",   "verdict": global_v},
    ]
    out_csv = run_dir / "global_verdicts.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False)

    # Write global_verdict.json (full audit trail)
    out_json = {
        "run_mode": run_mode,
        "base_seed": base_seed,
        "verdicts": verdicts,
        "core": core,
        "symbolic": symbolic,
        "global": global_v,
        "support_level": support,
        "support_level_note": (
            "'full_statistical_support' requires: (1) run_mode=full_statistical, "
            "(2) gate_passed=True (triplet: p_ok+ci_ok+sesoi_ok+power_ok all True, "
            f"n_runs>={_N_MIN} per condition), (3) global verdict=ACCEPT. "
            "Do NOT replace this label with 'full support' or 'full empirical support' — "
            "those phrases are editorial claims, not calculated outputs."
        ),
        "forbidden_report_labels": forbidden,
        "full_validation_gate": gate,
        "seed_table": seed_table,
    }
    (run_dir / "global_verdict.json").write_text(json.dumps(out_json, indent=2), encoding="utf-8")

    # Write global_verdict.txt (canonical single token)
    (run_dir / "global_verdict.txt").write_text(global_v + "\n", encoding="utf-8")

    # Print compact summary
    print(f"\n{'='*65}")
    print(f"ORI-C Canonical Suite — {run_dir.name}")
    print(f"run_mode: {run_mode}   gate_passed: {gate['gate_passed']}")
    print(f"{'='*65}")
    for tk, v in verdicts.items():
        mark = "✓" if v == "ACCEPT" else ("✗" if v == "REJECT" else "?")
        gate_info = ""
        if tk in _STATISTICAL_TEST_KEYS:
            tg = gate["tests"].get(tk, {})
            gate_info = " [gate✓]" if tg.get("passed") else f" [gate✗: {tg.get('reason', '?')}]"
        print(f"  {mark} {tk}: {v}{gate_info}")
    print(f"{'='*65}")
    print(f"  CORE (T1+T2+T3):        {core}")
    print(f"  SYMBOLIC (T4+T5+T6+T7): {symbolic}")
    print(f"  GLOBAL VERDICT:         {global_v}")
    print(f"  SUPPORT LEVEL:          {support}")
    if forbidden:
        print(f"  FORBIDDEN LABELS:       {forbidden}")
    print(f"{'='*65}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
