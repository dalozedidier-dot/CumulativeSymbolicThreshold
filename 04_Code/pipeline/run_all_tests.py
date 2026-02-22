#!/usr/bin/env python3
# 04_Code/pipeline/run_all_tests.py
"""Canonical suite runner for ORI-C (T1–T8).

Design rule (minimal, cadre intact)
- Noyau ORI: when asserting an effect on V, force a regime with Sigma>0 (demand_shock).
- Symbolique: when Sigma is near 0, do not expect V to move. Focus on C and S.

This runner
- creates a timestamped run directory under --outdir
- runs each test into a dedicated subfolder
- writes global_summary.csv + manifest.json (with full seed table and run_mode)

SEED STRATEGY (accurate description, non-negotiable)
- All per-test seeds are deterministic OFFSETS of the single --seed base (default 1234).
- Seeds are NOT statistically independent between tests; they share the same PRNG lineage.
- The offset values are fixed ex ante in the source:
    T1 seed = base      (offset 0)
    T2 seed = base      (offset 0)
    T3 seed = base      (offset 0)
    T4 seed = base      (offset 0)
    T5 seed = base + 17
    T6 seed = base + 3
    T7 seed = base + 99
    T8 seed = base + 5
- The manifest.json writes the exact seed per test automatically; do NOT declare seeds manually.

RUN MODE
- Tests using --n-runs 1 (T1, T6) are single-simulation deterministic runs (smoke).
- Tests using --n N (T4, T5, T7) run N independent paired/unpaired simulations
  (independent seeds within each test via per-condition offset).
- A run where any test uses n_runs=1 is classified "smoke_ci", not "full_statistical".
- "smoke_ci" output does not satisfy the triplet requirement (p + CI + SESOI + power gate)
  of DECISION_RULES v1/v2. Do not claim "full empirical support" for smoke_ci runs.

Expected scripts
- 04_Code/pipeline/run_ori_c_demo.py
- 04_Code/pipeline/run_synthetic_demo.py
- 04_Code/pipeline/run_robustness.py
- 04_Code/pipeline/run_reinjection_demo.py
- 04_Code/pipeline/run_symbolic_T4_s_rich_poor.py
- 04_Code/pipeline/run_symbolic_T5_injection.py
- 04_Code/pipeline/run_symbolic_T7_progressive_sweep.py
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _run_script(script_path: Path, outdir: Path, extra_args: List[str], log_path: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(script_path), "--outdir", str(outdir)] + extra_args
    with log_path.open("w", encoding="utf-8") as f:
        f.write("CMD: " + " ".join(cmd) + "\n")
        f.flush()
        subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT)


def _maybe_summary_json(test_dir: Path) -> Optional[Path]:
    cand = test_dir / "tables" / "summary.json"
    if cand.exists():
        return cand
    cand2 = test_dir / "tables" / "summary_all.json"
    return cand2 if cand2.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=str, default="03_Data/synthetic/synthetic_with_transition.csv")
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
    n_symbolic = 20 if args.fast else 60
    n_sweep = 12 if args.fast else 40

    t_steps = 220 if args.fast else 260
    t0 = int(t_steps * 0.35)

    tests: List[Dict] = []

    # Seed offsets are fixed ex ante — do NOT change post-observation.
    # All seeds are deterministic offsets of args.seed (base).
    # They are NOT statistically independent between tests.
    _seed = args.seed  # base seed (default 1234)

    # ------------------------
    # T1 Noyau ORI: demand shock -> Sigma>0 -> V changes
    # n_runs=1 → smoke run (single deterministic simulation, not a statistical sample)
    # ------------------------
    tests.append(
        {
            "id": "T1_noyau_demand_shock",
            "script": scripts_dir / "run_ori_c_demo.py",
            "seed_used": _seed,           # = base + 0
            "seed_formula": "base+0",
            "n_runs_used": 1,
            "args": [
                "--seed-base", str(_seed),
                "--n-runs", "1",
                "--n-steps", str(t_steps),
                "--t0", str(t0),
                "--intervention", "demand_shock",
                "--intervention-duration", str(int(t_steps * 0.4)),
                "--sigma-star", "0",
                "--tau", "0",
            ],
        }
    )

    # ------------------------
    # T2 Threshold demo on a dataset that contains a transition
    # n_runs=1 (fixed dataset, deterministic threshold detection)
    # ------------------------
    tests.append(
        {
            "id": "T2_threshold_demo_on_dataset",
            "script": scripts_dir / "run_synthetic_demo.py",
            "seed_used": _seed,           # = base + 0
            "seed_formula": "base+0",
            "n_runs_used": 1,
            "args": ["--input", str(in_path), "--seed", str(_seed)],
        }
    )

    # ------------------------
    # T3 Robustness on the same dataset
    # n_runs=1 (fixed dataset, robustness sweep)
    # ------------------------
    tests.append(
        {
            "id": "T3_robustness_on_dataset",
            "script": scripts_dir / "run_robustness.py",
            "seed_used": _seed,           # = base + 0
            "seed_formula": "base+0",
            "n_runs_used": 1,
            "args": ["--input", str(in_path), "--seed", str(_seed)],
        }
    )

    # ------------------------
    # T4 Symbolic: S rich vs poor on C
    # n_symbolic independent paired runs (within-test independent seeds via per-condition offset)
    # ------------------------
    tests.append(
        {
            "id": "T4_symbolic_S_rich_vs_poor_on_C",
            "script": scripts_dir / "run_symbolic_T4_s_rich_poor.py",
            "seed_used": _seed,           # = base + 0
            "seed_formula": "base+0",
            "n_runs_used": n_symbolic,
            "args": ["--n", str(n_symbolic), "--seed", str(_seed), "--t-steps", str(t_steps)],
        }
    )

    # ------------------------
    # T5 Symbolic injection effect on C
    # Offset +17 to avoid T1-T4 seed collision at the base level
    # n_symbolic independent paired runs (within-test independent seeds via per-condition offset)
    # ------------------------
    _seed_t5 = _seed + 17
    tests.append(
        {
            "id": "T5_symbolic_injection_effect_on_C",
            "script": scripts_dir / "run_symbolic_T5_injection.py",
            "seed_used": _seed_t5,        # = base + 17
            "seed_formula": "base+17",
            "n_runs_used": n_symbolic,
            "args": [
                "--n", str(n_symbolic),
                "--seed", str(_seed_t5),
                "--t-steps", str(t_steps),
                "--t0", str(int(t_steps * 0.45)),
            ],
        }
    )

    # ------------------------
    # T6 Symbolic cut on C (via ORI-C)
    # n_runs=1 → smoke run
    # ------------------------
    _seed_t6 = _seed + 3
    tests.append(
        {
            "id": "T6_symbolic_cut_on_C",
            "script": scripts_dir / "run_ori_c_demo.py",
            "seed_used": _seed_t6,        # = base + 3
            "seed_formula": "base+3",
            "n_runs_used": 1,
            "args": [
                "--seed-base", str(_seed_t6),
                "--n-runs", "1",
                "--n-steps", str(t_steps),
                "--t0", str(int(t_steps * 0.45)),
                "--intervention", "symbolic_cut",
                "--intervention-duration", str(int(t_steps * 0.25)),
                "--sigma-star", "0",
                "--tau", "0",
            ],
        }
    )

    # ------------------------
    # T7 Progressive sweep -> threshold detection on C_end(S)
    # Offset +99 (large gap to avoid seed proximity to T1-T6)
    # n_sweep independent runs (one run per S0 value)
    # ------------------------
    _seed_t7 = _seed + 99
    tests.append(
        {
            "id": "T7_progressive_S_to_C_threshold",
            "script": scripts_dir / "run_symbolic_T7_progressive_sweep.py",
            "seed_used": _seed_t7,        # = base + 99
            "seed_formula": "base+99",
            "n_runs_used": n_sweep,
            "args": ["--n", str(n_sweep), "--seed", str(_seed_t7), "--t-steps", str(t_steps)],
        }
    )

    # ------------------------
    # T8 Reinjection recovery on C
    # n_runs=1 → smoke run
    # NOTE: T8 definition changed in v1.1 (dose-response → reinjection recovery).
    #       Not in DECISION_RULES v1/v2 aggregation (covers T1-T7 only).
    # ------------------------
    _seed_t8 = _seed + 5
    tests.append(
        {
            "id": "T8_reinjection_recovery_on_C",
            "script": scripts_dir / "run_reinjection_demo.py",
            "seed_used": _seed_t8,        # = base + 5
            "seed_formula": "base+5",
            "n_runs_used": 1,
            "args": [
                "--seed", str(_seed_t8),
                "--n-steps", str(t_steps),
                "--intervention-point", str(int(t_steps * 0.35)),
                "--reinjection-point", str(int(t_steps * 0.65)),
            ],
        }
    )

    # Determine run_mode before execution.
    # run_mode="smoke_ci"         : any test uses n_runs=1 (pipeline execution check only)
    # run_mode="full_statistical" : all tests use n_runs >= N_min (50)
    # IMPORTANT: smoke_ci output does NOT satisfy DECISION_RULES v1/v2 triplet requirement
    #            (p + CI 99% + SESOI + power gate). Do not claim "full empirical support"
    #            or "full support" for smoke_ci runs.
    n_runs_all = [t.get("n_runs_used", 1) for t in tests]
    run_mode = "smoke_ci" if any(n == 1 for n in n_runs_all) else "full_statistical"

    # Seed table (auto-derived — exhaustive, not manually declared)
    seed_table = [
        {
            "test_id": t["id"],
            "seed": t.get("seed_used", args.seed),
            "seed_formula": t.get("seed_formula", "base+0"),
            "n_runs": t.get("n_runs_used", 1),
        }
        for t in tests
    ]
    seed_strategy = (
        "deterministic_offset: all per-test seeds = base_seed + fixed_offset (ex ante). "
        "Seeds are NOT statistically independent between tests. "
        f"base_seed={args.seed}. "
        "Seeds are independent within T4/T5 (per-condition offset inside each script)."
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
                "seed": t.get("seed_used", args.seed),
                "seed_formula": t.get("seed_formula", "base+0"),
                "n_runs": t.get("n_runs_used", 1),
            }
        )

    # Write global summary (CSV)
    summary_path = run_dir / "global_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["test_id", "script", "outdir", "summary_json", "seed", "seed_formula", "n_runs"],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Write seed_table.csv (correctif 6.1: auto-derived, exhaustive, not manual)
    seed_csv_path = run_dir / "seed_table.csv"
    with seed_csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["test_id", "seed", "seed_formula", "n_runs"])
        w.writeheader()
        for row in seed_table:
            w.writerow(row)

    # Write manifest.json (full audit trail)
    manifest = {
        "base_seed": args.seed,
        "seed_strategy": seed_strategy,
        "run_mode": run_mode,
        "run_mode_note": (
            "smoke_ci: n_runs=1 for some tests — pipeline execution check only. "
            "Does NOT satisfy DECISION_RULES v1/v2 full statistical requirements."
            if run_mode == "smoke_ci"
            else "full_statistical: all tests run with N >= N_min simulations."
        ),
        "seed_table": seed_table,
        "tests": rows,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
