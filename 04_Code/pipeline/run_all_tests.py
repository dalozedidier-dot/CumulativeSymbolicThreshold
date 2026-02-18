#!/usr/bin/env python3
# 04_Code/pipeline/run_all_tests.py
"""
Canonical test runner for ORI-C.

Design rule (minimal, cadre intact):
- Noyau ORI: when asserting an effect on V, force a regime with Σ>0 (e.g. demand_shock).
- Symbolique: when Σ≈0, do not expect V to move. Test symbolique on C (and related "reinvention" proxies),
  and only test V under symbolique if Σ>0 is intentionally enforced.

This runner:
- creates a timestamped run directory under --outdir
- runs a set of scripts (subtests) into subfolders
- writes a global_summary.csv that points to each subtest summary.json (when available)

Expected repo scripts (already present):
- 04_Code/pipeline/run_ori_c_demo.py
- 04_Code/pipeline/run_synthetic_demo.py
- 04_Code/pipeline/run_robustness.py
- 04_Code/pipeline/run_reinjection_demo.py

New symbolic scripts (added by patch v21):
- 04_Code/pipeline/run_symbolic_T4_s_rich_poor.py
- 04_Code/pipeline/run_symbolic_T5_injection.py
- 04_Code/pipeline/run_symbolic_T7_progressive_sweep.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _run_script(script_path: Path, outdir: Path, extra_args: List[str], log_path: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(script_path), "--outdir", str(outdir)] + extra_args
    with log_path.open("w", encoding="utf-8") as f:
        f.write("CMD: " + " ".join(cmd) + "\n")
        f.flush()
        subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT)


def _maybe_summary_json(test_dir: Path) -> Optional[Path]:
    cand = test_dir / "tables" / "summary.json"
    return cand if cand.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=str, default="03_Data/synthetic_with_transition.csv")
    ap.add_argument("--outdir", type=str, default="05_Results/canonical_tests")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--fast", action="store_true", help="smaller n for CI quick runs")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    out_root = root / args.outdir
    out_root.mkdir(parents=True, exist_ok=True)

    run_dir = out_root / _ts()
    run_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = root / "04_Code" / "pipeline"
    in_path = root / args.input

    # Defaults tuned for CI runtimes
    n_symbolic = 25 if args.fast else 60
    n_sweep = 20 if args.fast else 40
    t_steps = 220 if args.fast else 260

    tests: List[Dict] = []

    # ------------------------
    # Noyau ORI (Σ>0 enforced)
    # ------------------------
    tests.append(
        {
            "id": "T1_noyau_demand_shock_on_V",
            "script": scripts_dir / "run_ori_c_demo.py",
            "args": [
                "--seed",
                str(args.seed),
                "--t",
                str(t_steps),
                "--demand_shock",
                "0.20",
                "--label",
                "demand_shock",
            ],
        }
    )

    # ------------------------
    # Threshold detection + robustness should use a dataset that contains a transition
    # ------------------------
    tests.append(
        {
            "id": "T2_threshold_demo_on_transition_dataset",
            "script": scripts_dir / "run_synthetic_demo.py",
            "args": ["--input", str(in_path), "--seed", str(args.seed)],
        }
    )
    tests.append(
        {
            "id": "T3_robustness_on_transition_dataset",
            "script": scripts_dir / "run_robustness.py",
            "args": ["--input", str(in_path), "--seed", str(args.seed)],
        }
    )

    # ------------------------
    # Symbolique (Σ not required) : focus on C
    # ------------------------
    tests.append(
        {
            "id": "T4_symbolic_S_rich_vs_poor_on_C",
            "script": scripts_dir / "run_symbolic_T4_s_rich_poor.py",
            "args": ["--n", str(n_symbolic), "--seed", str(args.seed), "--t-steps", str(t_steps)],
        }
    )
    tests.append(
        {
            "id": "T5_symbolic_injection_effect_on_C",
            "script": scripts_dir / "run_symbolic_T5_injection.py",
            "args": [
                "--n",
                str(n_symbolic),
                "--seed",
                str(args.seed + 17),
                "--t-steps",
                str(t_steps),
                "--t0",
                str(int(t_steps * 0.45)),
            ],
        }
    )

    # Existing repo symbolic cut test (kept)
    tests.append(
        {
            "id": "T6_symbolic_cut_on_C",
            "script": scripts_dir / "run_ori_c_demo.py",
            "args": [
                "--seed",
                str(args.seed + 3),
                "--t",
                str(t_steps),
                "--symbolic_cut",
                "1",
                "--cut_start",
                str(int(t_steps * 0.45)),
                "--label",
                "symbolic_cut",
            ],
        }
    )

    # Progressive sweep -> threshold detection on C_end(S)
    tests.append(
        {
            "id": "T7_progressive_S_to_C_threshold",
            "script": scripts_dir / "run_symbolic_T7_progressive_sweep.py",
            "args": ["--n", str(n_sweep), "--seed", str(args.seed + 99), "--t-steps", str(t_steps)],
        }
    )

    # Reinjection demo (existing repo script, kept)
    tests.append(
        {
            "id": "T8_reinjection_recovery_on_C",
            "script": scripts_dir / "run_reinjection_demo.py",
            "args": ["--seed", str(args.seed + 5), "--t", str(t_steps)],
        }
    )

    # Run
    rows = []
    for t in tests:
        test_dir = run_dir / t["id"]
        log_dir = test_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "run.log"

        _run_script(t["script"], test_dir, t["args"], log_path)

        sj = _maybe_summary_json(test_dir)
        rows.append(
            {
                "test_id": t["id"],
                "script": str(t["script"].relative_to(root)),
                "outdir": str(test_dir.relative_to(root)),
                "summary_json": str(sj.relative_to(root)) if sj else "",
                "log": str(log_path.relative_to(root)),
            }
        )

    # Global index
    import pandas as pd  # local import to keep runner import-light

    df = pd.DataFrame(rows)
    df.to_csv(run_dir / "global_summary.csv", index=False)

    print(f"All tests completed. Run dir: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
