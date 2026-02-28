#!/usr/bin/env python3
# 04_Code/pipeline/run_all_tests.py
"""Canonical suite runner for ORI-C (T1–T9).

Design rule (minimal, cadre intact)
- Noyau ORI: when asserting an effect on V, force a regime with Sigma>0 (demand_shock).
- Symbolique: when Sigma is near 0, do not expect V to move. Focus on C and S.

This runner
- creates a timestamped run directory under --outdir
- runs each test into a dedicated subfolder
- writes global_summary.csv + seed_table.csv + manifest.json (full audit trail)
- calls analyse_verdicts_canonical.py to produce a run_mode-aware global verdict

SEED STRATEGY (accurate, non-negotiable)
- Each test receives a DISTINCT seed = base_seed + unique_offset (offsets 0–8, ex ante fixed).
- "distinct" = no two tests share the same seed numeric value.
- "independent" is NOT asserted: seeds share the same PRNG lineage (offsets of one base).
  Statistical independence of RNG streams is NOT claimed.
- Offsets are fixed here and verified by 04_Code/tests/test_seed_uniqueness.py (CI check).
- base_seed default = 1234; change via --seed.

  Offset table (ex ante, immutable):
    T1  seed = base + 0   (default 1234)
    T2  seed = base + 1   (default 1235)
    T3  seed = base + 2   (default 1236)
    T4  seed = base + 3   (default 1237)
    T5  seed = base + 4   (default 1238)
    T6  seed = base + 5   (default 1239)
    T7  seed = base + 6   (default 1240)
    T8  seed = base + 7   (default 1241)
    T9  seed = base + 8   (default 1242)

  Invariant: len(unique(offsets)) == 9. Verified by CI test.

RUN MODE
- Statistical tests (T1,T4,T5,T6,T7,T8): require N >= N_min=50 for "full_statistical".
- Fixed-data tests (T2,T3): operate on a fixed CSV; n_runs=1 is inherent, not smoke.
- Proof-only test (T9): not part of run_mode classification.
- run_mode="full_statistical" when all statistical tests have n_runs >= 50 (non-fast).
- run_mode="smoke_ci"         when any statistical test has n_runs < 50 (--fast).

Expected scripts
- 04_Code/pipeline/run_ori_c_demo.py
- 04_Code/pipeline/run_synthetic_demo.py
- 04_Code/pipeline/run_robustness.py
- 04_Code/pipeline/run_reinjection_demo.py
- 04_Code/pipeline/run_symbolic_T4_s_rich_poor.py
- 04_Code/pipeline/run_symbolic_T5_injection.py
- 04_Code/pipeline/run_symbolic_T7_progressive_sweep.py
- 04_Code/pipeline/run_T9_cross_domain.py
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


def _seed_offsets() -> list[dict]:
    """Return the fixed per-test seed offsets (ex ante, immutable).

    Keys are part of CI contract and must match test_seed_uniqueness.py:
      - test_id
      - offset
      - test_type in {"statistical","fixed_data","proof_only"}
    """
    return [
        {"test_id": "T1_noyau_demand_shock", "offset": 0, "test_type": "statistical"},
        {"test_id": "T2_threshold_demo_on_dataset", "offset": 1, "test_type": "fixed_data"},
        {"test_id": "T3_robustness_on_dataset", "offset": 2, "test_type": "fixed_data"},
        {"test_id": "T4_symbolic_S_rich_vs_poor_on_C", "offset": 3, "test_type": "statistical"},
        {"test_id": "T5_symbolic_injection_effect_on_C", "offset": 4, "test_type": "statistical"},
        {"test_id": "T6_symbolic_cut_on_C", "offset": 5, "test_type": "statistical"},
        {"test_id": "T7_progressive_S_to_C_threshold", "offset": 6, "test_type": "statistical"},
        {"test_id": "T8_reinjection_recovery_on_C", "offset": 7, "test_type": "statistical"},
        {"test_id": "T9_cross_domain", "offset": 8, "test_type": "proof_only"},
    ]


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
    ap.add_argument(
        "--n-runs-min",
        type=int,
        default=None,
        help=(
            "Minimum n_runs for all statistical tests. "
            "If any test would use fewer runs than this value, abort with an error. "
            "Use --n-runs-min 50 to enforce full_statistical mode unconditionally. "
            "Incompatible with --fast (which intentionally uses n=20)."
        ),
    )
    args = ap.parse_args()

    if args.fast and args.n_runs_min is not None:
        print(
            "ERROR: --fast and --n-runs-min are mutually exclusive. "
            "--fast intentionally runs with n=20 (smoke_ci). "
            "Remove --fast to enforce full_statistical mode.",
            file=sys.stderr,
        )
        return 1

    root = Path(__file__).resolve().parents[2]
    out_root = root / args.outdir
    out_root.mkdir(parents=True, exist_ok=True)

    run_dir = out_root / _ts()
    run_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = root / "04_Code" / "pipeline"
    in_path = root / args.input

    # Defaults tuned for CI runtimes.
    n_symbolic = 20 if args.fast else 60
    n_sweep = 15 if args.fast else 50

    t_steps = 220 if args.fast else 260
    t0 = int(t_steps * 0.35)

    tests: List[Dict] = []

    base_seed = args.seed
    offsets = {d["test_id"]: d for d in _seed_offsets()}

    def seed_for(test_id: str) -> int:
        return base_seed + offsets[test_id]["offset"]

    def seed_formula(test_id: str) -> str:
        return f"base+{offsets[test_id]['offset']}"

    def test_type(test_id: str) -> str:
        return offsets[test_id]["test_type"]

    # T1
    tests.append(
        {
            "id": "T1_noyau_demand_shock",
            "script": scripts_dir / "run_ori_c_demo.py",
            "seed_used": seed_for("T1_noyau_demand_shock"),
            "seed_formula": seed_formula("T1_noyau_demand_shock"),
            "n_runs_used": n_symbolic,
            "test_type": test_type("T1_noyau_demand_shock"),
            "args": [
                "--seed-base",
                str(seed_for("T1_noyau_demand_shock")),
                "--n-runs",
                str(n_symbolic),
                "--n-steps",
                str(t_steps),
                "--t0",
                str(t0),
                "--intervention",
                "demand_shock",
                "--intervention-duration",
                str(int(t_steps * 0.4)),
                "--sigma-star",
                "0",
                "--tau",
                "0",
            ],
        }
    )

    # T2
    tests.append(
        {
            "id": "T2_threshold_demo_on_dataset",
            "script": scripts_dir / "run_synthetic_demo.py",
            "seed_used": seed_for("T2_threshold_demo_on_dataset"),
            "seed_formula": seed_formula("T2_threshold_demo_on_dataset"),
            "n_runs_used": 1,
            "test_type": test_type("T2_threshold_demo_on_dataset"),
            "args": ["--input", str(in_path), "--seed", str(seed_for("T2_threshold_demo_on_dataset"))],
        }
    )

    # T3
    tests.append(
        {
            "id": "T3_robustness_on_dataset",
            "script": scripts_dir / "run_robustness.py",
            "seed_used": seed_for("T3_robustness_on_dataset"),
            "seed_formula": seed_formula("T3_robustness_on_dataset"),
            "n_runs_used": 1,
            "test_type": test_type("T3_robustness_on_dataset"),
            "args": ["--input", str(in_path), "--seed", str(seed_for("T3_robustness_on_dataset"))],
        }
    )

    # T4
    tests.append(
        {
            "id": "T4_symbolic_S_rich_vs_poor_on_C",
            "script": scripts_dir / "run_symbolic_T4_s_rich_poor.py",
            "seed_used": seed_for("T4_symbolic_S_rich_vs_poor_on_C"),
            "seed_formula": seed_formula("T4_symbolic_S_rich_vs_poor_on_C"),
            "n_runs_used": n_symbolic,
            "test_type": test_type("T4_symbolic_S_rich_vs_poor_on_C"),
            "args": [
                "--n",
                str(n_symbolic),
                "--seed",
                str(seed_for("T4_symbolic_S_rich_vs_poor_on_C")),
                "--t-steps",
                str(t_steps),
            ],
        }
    )

    # T5
    tests.append(
        {
            "id": "T5_symbolic_injection_effect_on_C",
            "script": scripts_dir / "run_symbolic_T5_injection.py",
            "seed_used": seed_for("T5_symbolic_injection_effect_on_C"),
            "seed_formula": seed_formula("T5_symbolic_injection_effect_on_C"),
            "n_runs_used": n_symbolic,
            "test_type": test_type("T5_symbolic_injection_effect_on_C"),
            "args": [
                "--n",
                str(n_symbolic),
                "--seed",
                str(seed_for("T5_symbolic_injection_effect_on_C")),
                "--t-steps",
                str(t_steps),
                "--t0",
                str(int(t_steps * 0.45)),
            ],
        }
    )

    # T6
    tests.append(
        {
            "id": "T6_symbolic_cut_on_C",
            "script": scripts_dir / "run_ori_c_demo.py",
            "seed_used": seed_for("T6_symbolic_cut_on_C"),
            "seed_formula": seed_formula("T6_symbolic_cut_on_C"),
            "n_runs_used": n_symbolic,
            "test_type": test_type("T6_symbolic_cut_on_C"),
            "args": [
                "--seed-base",
                str(seed_for("T6_symbolic_cut_on_C")),
                "--n-runs",
                str(n_symbolic),
                "--n-steps",
                str(t_steps),
                "--t0",
                str(int(t_steps * 0.45)),
                "--intervention",
                "symbolic_cut",
                "--intervention-duration",
                str(int(t_steps * 0.25)),
                "--sigma-star",
                "0",
                "--tau",
                "0",
            ],
        }
    )

    # T7
    tests.append(
        {
            "id": "T7_progressive_S_to_C_threshold",
            "script": scripts_dir / "run_symbolic_T7_progressive_sweep.py",
            "seed_used": seed_for("T7_progressive_S_to_C_threshold"),
            "seed_formula": seed_formula("T7_progressive_S_to_C_threshold"),
            "n_runs_used": n_sweep,
            "test_type": test_type("T7_progressive_S_to_C_threshold"),
            "args": [
                "--n",
                str(n_sweep),
                "--seed",
                str(seed_for("T7_progressive_S_to_C_threshold")),
                "--t-steps",
                str(t_steps),
            ],
        }
    )

    # T8
    tests.append(
        {
            "id": "T8_reinjection_recovery_on_C",
            "script": scripts_dir / "run_reinjection_demo.py",
            "seed_used": seed_for("T8_reinjection_recovery_on_C"),
            "seed_formula": seed_formula("T8_reinjection_recovery_on_C"),
            "n_runs_used": n_symbolic,
            "test_type": test_type("T8_reinjection_recovery_on_C"),
            "args": [
                "--seed",
                str(seed_for("T8_reinjection_recovery_on_C")),
                "--n-runs",
                str(n_symbolic),
                "--n-steps",
                str(t_steps),
                "--intervention-point",
                str(int(t_steps * 0.35)),
                "--reinjection-point",
                str(int(t_steps * 0.65)),
            ],
        }
    )

    # T9 proof-only
    if not args.fast:
        tests.append(
            {
                "id": "T9_cross_domain",
                "script": scripts_dir / "run_T9_cross_domain.py",
                "seed_used": seed_for("T9_cross_domain"),
                "seed_formula": seed_formula("T9_cross_domain"),
                "n_runs_used": 1,
                "test_type": test_type("T9_cross_domain"),
                "args": ["--seed", str(seed_for("T9_cross_domain"))],
            }
        )
    else:
        print("[ORI-C] smoke_ci: skip T9_cross_domain (proof-only).")

    # Determine run_mode before execution.
    N_MIN = 50
    statistical_tests = [t for t in tests if t.get("test_type") == "statistical"]
    stat_n_runs = [int(t.get("n_runs_used", 1)) for t in statistical_tests]
    run_mode = "smoke_ci" if any(n < N_MIN for n in stat_n_runs) else "full_statistical"

    if args.n_runs_min is not None:
        violators = [
            (t["id"], int(t["n_runs_used"]))
            for t in statistical_tests
            if int(t["n_runs_used"]) < int(args.n_runs_min)
        ]
        if violators:
            print(
                f"ERROR: --n-runs-min={args.n_runs_min} violated by {len(violators)} statistical test(s):",
                file=sys.stderr,
            )
            for tid, n in violators:
                print(f"  {tid}: n_runs_used={n} < {args.n_runs_min}", file=sys.stderr)
            print(
                "Aborting. Remove --n-runs-min or increase n to satisfy the constraint.",
                file=sys.stderr,
            )
            return 1
        print(
            f"n-runs-min guard satisfied: all {len(statistical_tests)} statistical tests use n >= {args.n_runs_min}"
        )

    seed_table = [
        {
            "test_id": t["id"],
            "seed": t.get("seed_used", args.seed),
            "seed_formula": t.get("seed_formula", "base+0"),
            "n_runs": int(t.get("n_runs_used", 1)),
            "test_type": t.get("test_type", "statistical"),
        }
        for t in tests
    ]
    seed_strategy = (
        "deterministic_offset: all per-test seeds = base_seed + fixed_offset (ex ante). "
        "Seeds are NOT statistically independent between tests. "
        f"base_seed={args.seed}. "
        "Seeds are independent within T4/T5 (per-condition offset inside each script)."
    )

    rows = []
    for t in tests:
        test_dir = run_dir / t["id"]
        log_dir = test_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "run.log"

        _run_script(t["script"], test_dir, t["args"], log_path)

        sj = _maybe_summary_json(test_dir)
        vt = test_dir / "verdict.txt"
        verdict_token = vt.read_text(encoding="utf-8").strip() if vt.exists() else ""
        rows.append(
            {
                "test_id": t["id"],
                "script": str(t["script"].relative_to(root)),
                "outdir": str(test_dir.relative_to(root)),
                "summary_json": str(sj.relative_to(root)) if sj else "",
                "seed": t.get("seed_used", args.seed),
                "seed_formula": t.get("seed_formula", "base+0"),
                "n_runs": int(t.get("n_runs_used", 1)),
                "test_type": t.get("test_type", "statistical"),
                "verdict": verdict_token,
            }
        )

    summary_path = run_dir / "global_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "test_id",
                "script",
                "outdir",
                "summary_json",
                "seed",
                "seed_formula",
                "n_runs",
                "test_type",
                "verdict",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)

    seed_csv_path = run_dir / "seed_table.csv"
    with seed_csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["test_id", "seed", "seed_formula", "n_runs", "test_type"])
        w.writeheader()
        for row in seed_table:
            w.writerow(row)

    manifest = {
        "base_seed": args.seed,
        "seed_strategy": seed_strategy,
        "run_mode": run_mode,
        "run_mode_note": (
            "smoke_ci: some statistical tests use n < 50. Pipeline execution check only."
            if run_mode == "smoke_ci"
            else "full_statistical: all statistical tests run with n >= 50."
        ),
        "seed_table": seed_table,
        "tests": rows,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    aggregator = scripts_dir / "analyse_verdicts_canonical.py"
    if aggregator.exists():
        agg_log = run_dir / "aggregator.log"
        cmd = [sys.executable, str(aggregator), "--run-dir", str(run_dir)]
        try:
            with agg_log.open("w", encoding="utf-8") as f:
                f.write("CMD: " + " ".join(cmd) + "\n")
                f.flush()
                subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.STDOUT)
        except Exception as exc:  # noqa: BLE001
            agg_log.write_text(f"Aggregator error: {exc}\n", encoding="utf-8")

    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
