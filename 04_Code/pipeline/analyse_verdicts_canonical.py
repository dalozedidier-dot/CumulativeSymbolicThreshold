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

Support vocabulary (controlled):
  run_mode = "full_statistical" → "full_statistical_support" when global ACCEPT
  run_mode = "smoke_ci"         → "smoke_ci_accept" when global ACCEPT (pipeline check only)
  Any REJECT                    → "rejected"
  Any INDETERMINATE at global   → "inconclusive"

Outputs:
  <run_dir>/global_verdicts.csv   — core / symbolic / global verdict tokens
  <run_dir>/global_verdict.json   — run_mode + support_level + all per-test verdicts
  <run_dir>/global_verdict.txt    — single token: ACCEPT / REJECT / INDETERMINATE
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


def _support_level(global_v: str, run_mode: str) -> str:
    """Controlled vocabulary for support level. Only 'full_statistical_support'
    is output when run_mode == 'full_statistical' AND global verdict is ACCEPT.
    'full support' / 'full empirical support' are NEVER emitted here.
    """
    if global_v == "ACCEPT":
        if run_mode == "full_statistical":
            return "full_statistical_support"
        return "smoke_ci_accept"   # pipeline check passed; NOT a full protocol validation
    if global_v == "REJECT":
        return "rejected"
    return "inconclusive"


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate canonical T1–T8 verdicts (run_mode-aware).")
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
    support = _support_level(global_v, run_mode)

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
            "'full_statistical_support' requires run_mode=full_statistical AND all "
            "statistical tests ACCEPT with fully-conformant verdict.json (triplet satisfied). "
            "Do NOT replace this label with 'full support' or 'full empirical support' — those "
            "phrases are editorial claims, not calculated outputs."
        ),
        "seed_table": seed_table,
    }
    (run_dir / "global_verdict.json").write_text(json.dumps(out_json, indent=2), encoding="utf-8")

    # Write global_verdict.txt (canonical single token)
    (run_dir / "global_verdict.txt").write_text(global_v + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
