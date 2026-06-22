#!/usr/bin/env python3
# 04_Code/pipeline/run_all_tests.py

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
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


def _run_script(
    script_path: Path,
    outdir: Path,
    extra_args: List[str],
    log_path: Path,
    *,
    timeout_seconds: int | None = None,
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(script_path), "--outdir", str(outdir)] + extra_args
    with log_path.open("w", encoding="utf-8") as f:
        f.write("CMD: " + " ".join(cmd) + "\n")
        f.flush()
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            f.write(f"\nTIMEOUT: step exceeded {timeout_seconds}s\n")
            f.flush()
            raise




def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"WARNING: ignoring invalid {name}={raw!r}; using {default}", file=sys.stderr)
        return default


def _write_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()

def _maybe_summary_json(test_dir: Path) -> Optional[Path]:
    cand = test_dir / "tables" / "summary.json"
    if cand.exists():
        return cand
    cand2 = test_dir / "tables" / "summary_all.json"
    return cand2 if cand2.exists() else None



def _display_path(path: Path, root: Path) -> str:
    """Return a stable path for manifests without failing on absolute outdirs."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)

def _github_trace() -> dict:
    """Best-effort GitHub Actions trace. Safe outside CI."""
    return {
        "github_workflow": os.environ.get("GITHUB_WORKFLOW"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_number": os.environ.get("GITHUB_RUN_NUMBER"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "github_ref": os.environ.get("GITHUB_REF"),
        "github_repository": os.environ.get("GITHUB_REPOSITORY"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=str, default="03_Data/synthetic/synthetic_with_transition.csv")
    ap.add_argument("--outdir", type=str, default="05_Results/canonical_tests")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--fast", action="store_true", help="smaller n for CI quick runs")
    ap.add_argument(
        "--n-runs-smoke",
        type=int,
        default=_env_int("ORIC_SMOKE_N_RUNS", 20),
        help="n_runs for symbolic statistical tests in --fast mode (default: 20; env ORIC_SMOKE_N_RUNS)",
    )
    ap.add_argument(
        "--n-sweep-smoke",
        type=int,
        default=_env_int("ORIC_SMOKE_N_SWEEP", 15),
        help="n for T7 sweep in --fast mode (default: 15; env ORIC_SMOKE_N_SWEEP)",
    )
    ap.add_argument(
        "--n-steps-smoke",
        type=int,
        default=_env_int("ORIC_SMOKE_N_STEPS", 220),
        help="time steps for --fast mode (default: 220; env ORIC_SMOKE_N_STEPS)",
    )
    ap.add_argument(
        "--step-timeout-seconds",
        type=int,
        default=_env_int("ORIC_STEP_TIMEOUT_SECONDS", 0),
        help="per-step subprocess timeout; 0 disables (env ORIC_STEP_TIMEOUT_SECONDS)",
    )
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
            "--fast intentionally runs smoke_ci with configurable small n. "
            "Remove --fast to enforce full_statistical mode.",
            file=sys.stderr,
        )
        return 1

    if args.fast:
        for name in ("n_runs_smoke", "n_sweep_smoke", "n_steps_smoke"):
            if int(getattr(args, name)) < 1:
                print(f"ERROR: --{name.replace('_', '-')} must be >= 1", file=sys.stderr)
                return 1
    if args.step_timeout_seconds < 0:
        print("ERROR: --step-timeout-seconds must be >= 0", file=sys.stderr)
        return 1
    step_timeout = args.step_timeout_seconds or None

    root = Path(__file__).resolve().parents[2]
    out_root = root / args.outdir
    out_root.mkdir(parents=True, exist_ok=True)

    run_dir = out_root / _ts()
    run_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = root / "04_Code" / "pipeline"
    in_path = root / args.input

    n_symbolic = int(args.n_runs_smoke) if args.fast else 60
    n_sweep = int(args.n_sweep_smoke) if args.fast else 50

    t_steps = int(args.n_steps_smoke) if args.fast else 260
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
        f"base_seed={args.seed}."
    )

    n_tests = len(tests)
    suite_t0 = time.monotonic()
    print(
        f"[ORI-C] run_mode={run_mode} | {n_tests} test(s) | base_seed={args.seed} | "
        f"run_dir={_display_path(run_dir, root)} | "
        f"step_timeout={step_timeout or 'disabled'}",
        flush=True,
    )

    progress_path = run_dir / "progress.jsonl"
    rows = []
    for i, t in enumerate(tests, start=1):
        test_dir = run_dir / t["id"]
        log_dir = test_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "run.log"

        # ── Step-by-step progress logging (timestamped, flushed for CI tee) ──
        step_t0 = time.monotonic()
        print(
            f"[ORI-C][step {i}/{n_tests}] {t['id']} "
            f"({t.get('test_type', '?')}, seed={t.get('seed_used', args.seed)}, "
            f"n_runs={t.get('n_runs_used', 1)}) - running ...",
            flush=True,
        )
        _write_jsonl(progress_path, {
            "event": "start",
            "step": i,
            "n_steps": n_tests,
            "test_id": t["id"],
            "seed": t.get("seed_used", args.seed),
            "n_runs": int(t.get("n_runs_used", 1)),
            "time_utc": datetime.now(timezone.utc).isoformat(),
        })

        step_status = "ok"
        if t.get("test_type") == "proof_only":
            # proof_only tests (e.g. T9) exit 1 when verdict = REJECT; this is
            # by design and must NOT abort the suite (the aggregator only reads
            # T1–T8 and T9 is never a blocking gate for the global verdict).
            try:
                _run_script(t["script"], test_dir, t["args"], log_path, timeout_seconds=step_timeout)
            except subprocess.CalledProcessError as exc:
                step_status = f"proof_only_exit_{exc.returncode}"
                print(
                    f"[WARNING] {t['id']} (proof_only) exited {exc.returncode}. "
                    "Verdict captured in test dir; not blocking the suite."
                )
        else:
            _run_script(t["script"], test_dir, t["args"], log_path, timeout_seconds=step_timeout)

        sj = _maybe_summary_json(test_dir)
        vt = test_dir / "verdict.txt"
        verdict_token = vt.read_text(encoding="utf-8").strip() if vt.exists() else ""

        step_dt = time.monotonic() - step_t0
        print(
            f"[ORI-C][step {i}/{n_tests}] {t['id']} done in {step_dt:.1f}s "
            f"-> verdict={verdict_token or '(none)'} [{step_status}] "
            f"(log: {_display_path(log_path, root)})",
            flush=True,
        )
        _write_jsonl(progress_path, {
            "event": "done",
            "step": i,
            "n_steps": n_tests,
            "test_id": t["id"],
            "status": step_status,
            "duration_seconds": round(step_dt, 3),
            "verdict": verdict_token,
            "log": _display_path(log_path, root),
            "time_utc": datetime.now(timezone.utc).isoformat(),
        })
        rows.append(
            {
                "test_id": t["id"],
                "script": _display_path(t["script"], root),
                "outdir": _display_path(test_dir, root),
                "summary_json": _display_path(sj, root) if sj else "",
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
        "trace": _github_trace(),
        "seed_table": seed_table,
        "progress_jsonl": _display_path(progress_path, root),
        "tests": rows,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        f"[ORI-C] aggregating verdicts ({sum(1 for r in rows if r['verdict'])}/"
        f"{n_tests} tests produced a verdict.txt) …",
        flush=True,
    )
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

    print(
        f"[ORI-C] suite complete in {time.monotonic() - suite_t0:.1f}s "
        f"(run_mode={run_mode}). Machine-readable run_dir on the next line:",
        flush=True,
    )
    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
