#!/usr/bin/env python3
"""Run real-data smoke matrix (one dataset per sector)."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    index = Path("data/real_datasets_index.csv")
    if not index.exists():
        print("ERROR: data/real_datasets_index.csv not found", file=sys.stderr)
        return 1

    seen: set[str] = set()
    errors: list[str] = []

    with index.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("smoke_candidate", "").strip().lower() != "yes":
                continue

            sector = row["sector"].strip()
            if sector in seen:
                continue
            seen.add(sector)

            dataset_id = row["dataset_id"]
            ds_path = Path(row["path"].strip())
            if not ds_path.exists():
                errors.append(f"MISSING dataset: {ds_path} ({sector})")
                continue

            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            run_dir = Path(f"_ci_out/real_smoke/{sector}/{dataset_id}/runs/{ts}")
            for sub in ("tables", "figures", "contracts"):
                (run_dir / sub).mkdir(parents=True, exist_ok=True)

            shutil.copy("contracts/POWER_CRITERIA.json", run_dir / "contracts/")
            shutil.copy("contracts/STABILITY_CRITERIA.json", run_dir / "contracts/")

            summary = {"dataset_id": dataset_id, "sector": sector, "run_mode": "smoke"}
            (run_dir / "tables" / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            (run_dir / "figures" / "smoke_placeholder.txt").write_text("smoke run\n", encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.make_manifest",
                    "--root",
                    str(run_dir),
                    "--out",
                    str(run_dir / "manifest.json"),
                ],
                check=True,
            )
            print(f"  OK  {sector}/{dataset_id} -> {run_dir}")

    if errors:
        print("\nErrors:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print(f"\nSmoke: {len(seen)} sectors checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

