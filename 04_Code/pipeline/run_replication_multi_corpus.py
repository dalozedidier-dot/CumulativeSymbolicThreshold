#!/usr/bin/env python3
"""run_replication_multi_corpus.py — Cross-corpus replication of ORI-C real-data validation.

Runs the real-data validation protocol on every eligible dataset in the
registry and produces a corpus-level aggregation report.

Usage
-----
  python 04_Code/pipeline/run_replication_multi_corpus.py \
    --registry 03_Data/real/registry/real_datasets.json \
    --outdir 05_Results/replication_multi_corpus \
    --fast

Only datasets whose ``eligible_for`` list contains at least one of the
tags in ``--eligible-tags`` (default: ``proof_run``) **and** whose
``n_rows >= n_min`` are included.  Use ``--eligible-tags smoke_ci`` to
run the smaller, faster set.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_registry(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("datasets", [])


def _is_eligible(ds: dict, tags: set[str]) -> bool:
    """A dataset is eligible if it has at least one matching tag and n_rows >= n_min."""
    ds_tags = set(ds.get("eligible_for", []))
    if not ds_tags & tags:
        return False
    n_rows = ds.get("n_rows", 0)
    n_min = ds.get("n_min", 0)
    return n_rows >= n_min


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-corpus replication runner for ORI-C")
    ap.add_argument(
        "--registry",
        default=str(_REPO_ROOT / "03_Data" / "real" / "registry" / "real_datasets.json"),
        help="Path to real_datasets.json registry",
    )
    ap.add_argument("--outdir", default="05_Results/replication_multi_corpus")
    ap.add_argument(
        "--eligible-tags",
        nargs="+",
        default=["proof_run"],
        help="Include datasets whose eligible_for contains at least one of these tags (default: proof_run)",
    )
    ap.add_argument("--fast", action="store_true", help="Pass --fast to the validation protocol")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true", help="List eligible datasets without running")
    args = ap.parse_args()

    registry_path = Path(args.registry)
    if not registry_path.exists():
        print(f"ERROR: registry not found: {registry_path}", file=sys.stderr)
        return 1

    datasets = _load_registry(registry_path)
    tags = set(args.eligible_tags)
    eligible = [ds for ds in datasets if _is_eligible(ds, tags)]

    print(f"Registry: {registry_path}")
    print(f"Eligible tags: {sorted(tags)}")
    print(f"Total datasets: {len(datasets)}, eligible: {len(eligible)}")
    print()

    if not eligible:
        print("No eligible datasets found. Try --eligible-tags smoke_ci")
        return 1

    for ds in eligible:
        flag = "[OK]" if ds.get("n_rows", 0) >= ds.get("n_min", 0) else "[SKIP n<n_min]"
        print(f"  {flag} {ds['dataset_id']:30s}  n={ds.get('n_rows', '?'):>5}  freq={ds.get('frequency', '?')}")

    if args.dry_run:
        print("\n--dry-run: stopping here.")
        return 0

    outdir_root = Path(args.outdir)
    outdir_root.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    protocol_script = str(_REPO_ROOT / "04_Code" / "pipeline" / "run_real_data_validation_protocol.py")

    for ds in eligible:
        ds_id = ds["dataset_id"]
        ds_path = _REPO_ROOT / ds["path"]
        ds_outdir = outdir_root / ds_id

        if not ds_path.exists():
            print(f"\nWARN: {ds_id} — file not found: {ds_path}, skipping")
            results.append({"dataset_id": ds_id, "verdict": "ERROR", "reason": "file_not_found"})
            continue

        cols = ds.get("oric_columns", {})
        cmd = [
            sys.executable, protocol_script,
            "--input", str(ds_path),
            "--outdir", str(ds_outdir),
            "--col-time", ds.get("time_column", "t"),
            "--time-mode", ds.get("time_mode", "index"),
            "--col-O", cols.get("O", "O"),
            "--col-R", cols.get("R", "R"),
            "--col-I", cols.get("I", "I"),
            "--seed", str(args.seed),
        ]
        if cols.get("demand"):
            cmd.extend(["--col-demand", cols["demand"]])
        if cols.get("S"):
            cmd.extend(["--col-S", cols["S"]])
        if not ds.get("pre_normalised", False):
            cmd.extend(["--normalize", "robust"])
        else:
            cmd.extend(["--normalize", "none"])
        if args.fast:
            cmd.append("--fast")

        print(f"\n{'=' * 78}")
        print(f"REPLICATION: {ds_id}")
        print(f"  path: {ds_path}")
        print(f"  cmd:  {' '.join(cmd)}")
        print(f"{'=' * 78}")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            verdict_file = ds_outdir / "verdict.txt"
            if verdict_file.exists():
                verdict = verdict_file.read_text(encoding="utf-8").strip()
            else:
                verdict = "ERROR"

            kpi_file = ds_outdir / "tables" / "validation_kpis.json"
            kpis = {}
            if kpi_file.exists():
                try:
                    kpis = json.loads(kpi_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            results.append({
                "dataset_id": ds_id,
                "label": ds.get("label", ds_id),
                "verdict": verdict,
                "n_rows": ds.get("n_rows"),
                "frequency": ds.get("frequency"),
                "geo_scope": ds.get("geo_scope"),
                "kpis": kpis,
                "returncode": proc.returncode,
            })

            status = "PASS" if verdict == "ACCEPT" else verdict
            print(f"\n  -> {ds_id}: {status}")

        except subprocess.TimeoutExpired:
            print(f"\n  -> {ds_id}: TIMEOUT (600s)")
            results.append({"dataset_id": ds_id, "verdict": "ERROR", "reason": "timeout"})
        except Exception as e:
            print(f"\n  -> {ds_id}: EXCEPTION: {e}")
            results.append({"dataset_id": ds_id, "verdict": "ERROR", "reason": str(e)})

    # ── Aggregation ──────────────────────────────────────────────────────────
    n_total = len(results)
    n_accept = sum(1 for r in results if r["verdict"] == "ACCEPT")
    n_reject = sum(1 for r in results if r["verdict"] == "REJECT")
    n_indeterminate = sum(1 for r in results if r["verdict"] == "INDETERMINATE")
    n_error = sum(1 for r in results if r["verdict"] == "ERROR")

    summary = {
        "replication_corpus_count": n_total,
        "n_accept": n_accept,
        "n_reject": n_reject,
        "n_indeterminate": n_indeterminate,
        "n_error": n_error,
        "accept_rate": n_accept / max(1, n_total),
        "eligible_tags": sorted(tags),
        "seed": args.seed,
        "fast_mode": args.fast,
        "per_dataset": results,
    }

    summary_path = outdir_root / "replication_multi_corpus_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print(f"\n{'=' * 78}")
    print("REPLICATION SUMMARY")
    print(f"{'=' * 78}")
    print(f"  Corpora tested : {n_total}")
    print(f"  ACCEPT         : {n_accept}")
    print(f"  REJECT         : {n_reject}")
    print(f"  INDETERMINATE  : {n_indeterminate}")
    print(f"  ERROR          : {n_error}")
    print(f"  Accept rate    : {n_accept}/{n_total} = {n_accept / max(1, n_total):.1%}")
    print(f"\nSummary written to: {summary_path}")

    return 0 if n_error == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
