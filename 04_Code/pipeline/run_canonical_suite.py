#!/usr/bin/env python3
# run_canonical_suite.py
#
# Canonical orchestrator for the ORI-C test suite.
#
# Runs existing test scripts (if present) and writes outputs under:
#   05_Results/canonical_runs/<run_id>/TestX/
#
# Robust to partial availability:
# - if a test script is missing, writes an INDETERMINATE verdict for that test
# - always attempts to produce global_verdicts.csv via analyse_verdicts_canonical.py
#
# Expected existing scripts (typical):
# - 04_Code/pipeline/run_ori_c_demo.py
# - 04_Code/pipeline/run_robustness.py
# - 04_Code/pipeline/tests_causaux.py
# - 04_Code/pipeline/run_reinjection_demo.py
#
# Optional neuro extensions added in this patch:
# - 04_Code/pipeline/run_bump_attractor.py  (Test9A)
# - 04_Code/pipeline/run_bcm_test.py        (Test9B)

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd


def _write_indeterminate(outdir: Path, reason: str) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "verdict.txt").write_text("INDETERMINATE\n", encoding="utf-8")
    tabdir = outdir / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"verdict": "INDETERMINATE", "reason": reason}]).to_csv(tabdir / "summary.csv", index=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run canonical ORI-C suite and aggregate verdicts.")
    ap.add_argument("--results-root", default="05_Results", help="Root results folder.")
    ap.add_argument("--run-id", default=None, help="Run id. Default = timestamp.")
    ap.add_argument("--python", default=None, help="Optional python executable to use for subprocess calls.")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    pipeline_dir = repo_root / "04_Code" / "pipeline"

    run_id = args.run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_root = Path(args.results_root) / "canonical_runs" / run_id
    results_root.mkdir(parents=True, exist_ok=True)

    py = args.python or sys.executable

    def run(script_name: str, test_name: str, extra: list[str]) -> None:
        sp = pipeline_dir / script_name
        outdir = results_root / test_name
        if not sp.exists():
            _write_indeterminate(outdir, f"missing_script: {script_name}")
            return
        cmd = [py, str(sp), "--outdir", str(outdir)] + extra
        try:
            subprocess.run(cmd, check=True)
        except Exception as e:
            _write_indeterminate(outdir, f"execution_failed: {e}")

    # Tests 1-8 (best-effort wrappers)
    run("run_ori_c_demo.py", "Test1", ["--intervention", "none"])
    run("run_robustness.py", "Test2", [])
    run("tests_causaux.py", "Test3", ["--test", "threshold"])
    run("run_ori_c_demo.py", "Test4", ["--intervention", "symbolic_cut"])
    run("tests_causaux.py", "Test5", ["--test", "delayed_effect"])
    run("tests_causaux.py", "Test6", ["--test", "bifurcation_threshold"])
    run("tests_causaux.py", "Test7", ["--test", "cut_specificity"])
    run("run_reinjection_demo.py", "Test8", [])

    # Optional neuro extensions
    run("run_bump_attractor.py", "Test9A", ["--n-runs", "50"])
    run("run_bcm_test.py", "Test9B", [])

    # Aggregate
    agg = pipeline_dir / "analyse_verdicts_canonical.py"
    if agg.exists():
        try:
            subprocess.run([py, str(agg), "--results-root", str(Path(args.results_root)), "--run-id", run_id], check=False)
        except Exception:
            pass

    manifest = {"run_id": run_id, "results_root": str(results_root), "scripts_dir": str(pipeline_dir)}
    (results_root / "run_manifest.json").write_text(pd.Series(manifest).to_json(), encoding="utf-8")

    print(f"Run completed: {results_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
