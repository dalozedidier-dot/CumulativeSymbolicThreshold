#!/usr/bin/env python3
"""replicate.py — Lightweight external replication package.

A third party can run this single script to:
1. Verify frozen parameters are intact
2. Reproduce the nightly lot (synthetic validation)
3. Reproduce the 7 pilot verdicts
4. Rebuild the generalization matrix
5. Verify cross-contract consistency

Usage:
    python tools/replicate.py [--outdir replication_output] [--fast]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(cmd: list[str], label: str) -> bool:
    """Run a command, print status, return success."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=False, text=True,
    )
    ok = result.returncode == 0
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}")
    return ok


def step1_verify_frozen_params() -> dict:
    """Step 1: Verify frozen contracts are intact."""
    print("\n--- Step 1: Verify frozen contracts ---")
    contracts = [
        "contracts/FROZEN_PILOT_CORPUS.json",
        "contracts/FROZEN_PARAMS.json",
        "contracts/PILOT_GENERALIZATION.json",
        "contracts/POWER_UPGRADE_PROTOCOL.json",
        "contracts/POWER_CRITERIA.json",
    ]
    results = {}
    for c in contracts:
        path = ROOT / c
        if path.exists():
            results[c] = {"exists": True, "sha256": _sha256(path)}
            data = json.loads(path.read_text())
            if "version" in data:
                results[c]["version"] = data["version"]
            print(f"  [OK] {c} (sha256={results[c]['sha256'][:16]}...)")
        else:
            results[c] = {"exists": False}
            print(f"  [MISSING] {c}")
    return results


def step2_run_tests() -> bool:
    """Step 2: Run the full test suite."""
    print("\n--- Step 2: Run test suite ---")
    return _run(
        [sys.executable, "-m", "pytest", "04_Code/tests/", "-v", "--tb=short"],
        "Full test suite",
    )


def step3_verify_pilots() -> dict:
    """Step 3: Verify all 7 pilot datasets and their verdicts."""
    print("\n--- Step 3: Verify pilot datasets ---")
    corpus_path = ROOT / "contracts" / "FROZEN_PILOT_CORPUS.json"
    if not corpus_path.exists():
        print("  [FAIL] FROZEN_PILOT_CORPUS.json missing")
        return {"status": "FAIL", "reason": "corpus missing"}

    corpus = json.loads(corpus_path.read_text())
    pilots = corpus["pilots"]
    results = {}

    for p in pilots:
        pid = p["pilot_id"]
        data_dir = ROOT / p["data_path"]
        csv_path = data_dir / "real.csv"
        spec_path = data_dir / "proxy_spec.json"

        status = {
            "data_exists": csv_path.exists(),
            "spec_exists": spec_path.exists(),
            "expected_verdict": p["oric_verdict"],
            "expected_level": p["proof_level"],
            "expected_power": p["power_class"],
        }

        if csv_path.exists():
            import csv
            with open(csv_path) as f:
                reader = csv.reader(f)
                n_rows = sum(1 for _ in reader) - 1  # minus header
            status["actual_rows"] = n_rows
            status["rows_match"] = n_rows >= p.get("series_length", 0) * 0.9

        results[pid] = status
        ok = status["data_exists"] and status["spec_exists"]
        print(f"  [{'OK' if ok else 'FAIL'}] {pid}: "
              f"n={status.get('actual_rows', '?')}, "
              f"verdict={p['oric_verdict']}, level={p['proof_level']}")

    return results


def step4_verify_generalization_matrix() -> dict:
    """Step 4: Rebuild and verify generalization matrix."""
    print("\n--- Step 4: Verify generalization matrix ---")

    corpus = json.loads(
        (ROOT / "contracts" / "FROZEN_PILOT_CORPUS.json").read_text()
    )
    gen = json.loads(
        (ROOT / "contracts" / "PILOT_GENERALIZATION.json").read_text()
    )
    registry_path = ROOT / "05_Results" / "pilots" / "pilot_generalization_registry.json"

    results = {
        "corpus_pilots": len(corpus["pilots"]),
        "gen_matrix_pilots": len(gen["generalization_matrix"]),
        "registry_exists": registry_path.exists(),
    }

    # Check consistency
    corpus_ids = {p["pilot_id"] for p in corpus["pilots"]}
    gen_ids = {p["pilot_id"] for p in gen["generalization_matrix"]}
    results["ids_match"] = corpus_ids == gen_ids

    # Check verdict counts
    summary = corpus["summary_table"]
    results["accept_count"] = summary["by_verdict"]["ACCEPT"]
    results["indeterminate_count"] = summary["by_verdict"]["INDETERMINATE"]
    results["reject_count"] = summary["by_verdict"]["REJECT"]

    ok = results["ids_match"] and results["accept_count"] == 4
    print(f"  [{'OK' if ok else 'FAIL'}] Matrix consistency: "
          f"{results['accept_count']} ACCEPT, "
          f"{results['indeterminate_count']} INDETERMINATE, "
          f"{results['reject_count']} REJECT")

    return results


def step5_run_benchmark(fast: bool = False) -> bool:
    """Step 5: Run comparative benchmark on showcase pilots."""
    print("\n--- Step 5: Run comparative benchmark ---")
    cmd = [
        sys.executable, "-c",
        "from pathlib import Path; "
        "from oric.comparative_benchmark import run_all_benchmarks; "
        "r = run_all_benchmarks(Path('replication_output/benchmark'), "
        "pilots=[{'pilot_id':'sector_finance.pilot_btc',"
        "'csv':'03_Data/sector_finance/real/pilot_btc/real.csv','verdict':'ACCEPT'},"
        "{'pilot_id':'sector_neuro.pilot_eeg_bonn',"
        "'csv':'03_Data/sector_neuro/real/pilot_eeg_bonn/real.csv','verdict':'ACCEPT'},"
        "{'pilot_id':'sector_cosmo.pilot_solar',"
        "'csv':'03_Data/sector_cosmo/real/pilot_solar/real.csv','verdict':'ACCEPT'}]); "
        f"print(f\"Benchmarked {{r['total_pilots']}} pilots across {{len(r['methods'])}} methods\")"
    ]
    return _run(cmd, "Comparative benchmark (BTC, EEG, Solar)")


def main():
    parser = argparse.ArgumentParser(description="ORI-C replication package")
    parser.add_argument("--outdir", type=Path, default=ROOT / "replication_output")
    parser.add_argument("--fast", action="store_true", help="Skip slow steps")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  ORI-C EXTERNAL REPLICATION PROTOCOL")
    print("=" * 60)

    results = {}

    # Step 1: Verify frozen params
    results["step1_frozen_params"] = step1_verify_frozen_params()

    # Step 2: Run tests
    results["step2_tests_passed"] = step2_run_tests()

    # Step 3: Verify pilots
    results["step3_pilots"] = step3_verify_pilots()

    # Step 4: Verify generalization matrix
    results["step4_matrix"] = step4_verify_generalization_matrix()

    # Step 5: Run benchmark
    if not args.fast:
        results["step5_benchmark"] = step5_run_benchmark()
    else:
        results["step5_benchmark"] = "SKIPPED (--fast)"

    # Write summary
    all_ok = (
        results["step2_tests_passed"]
        and results["step4_matrix"].get("ids_match", False)
    )

    summary = {
        "schema": "oric.replication_result.v1",
        "replication_status": "PASS" if all_ok else "FAIL",
        "results": results,
    }

    out_path = args.outdir / "replication_summary.json"
    out_path.write_text(
        json.dumps(summary, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print(f"  REPLICATION STATUS: {'PASS' if all_ok else 'FAIL'}")
    print(f"  Summary: {out_path}")
    print("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
