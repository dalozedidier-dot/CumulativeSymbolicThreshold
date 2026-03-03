#!/usr/bin/env python3
"""Scan-only mode: inventory + diagnostics + manifest, no t* or stability.

Use this for datasets where density/power is uncertain (e.g. surveys,
social media). The scan produces:
  - input inventory with sha256 hashes
  - power diagnostic (point counts, depth coverage)
  - density hint and recommendation
  - manifest.json

If power_diagnostic shows medium+ is possible, promote to full stability.

Usage:
  python -m tools.run_scan_only \
      --dataset data/survey/eurobarometer/... \
      --dataset-id eurobarometer_99 \
      --sector survey \
      --out-root _ci_out/scan_eurobarometer
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _scan_csv(path: Path) -> Dict[str, Any]:
    """Quick scan of a CSV file for row/column counts."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            rows = sum(1 for _ in reader)
        return {
            "file": str(path),
            "rows": rows,
            "cols": len(header) if header else 0,
            "columns": header or [],
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    except Exception as e:
        return {"file": str(path), "error": str(e)}


def _power_diagnostic(
    total_points: int,
    n_distinct_depths: int,
    instances_count: int,
    power_criteria_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Evaluate power level from point counts."""
    # Default thresholds
    thresholds = {
        "high": {"total_points": 200, "depth_distinct_total": 10, "instances_count": 20},
        "medium": {"total_points": 60, "depth_distinct_total": 6, "instances_count": 8},
    }

    if power_criteria_path and power_criteria_path.exists():
        criteria = json.loads(power_criteria_path.read_text(encoding="utf-8"))
        thresholds = criteria.get("thresholds", thresholds)

    level = "low"
    for lvl in ["high", "medium"]:
        t = thresholds[lvl]
        if (
            total_points >= t["total_points"]
            and n_distinct_depths >= t["depth_distinct_total"]
            and instances_count >= t["instances_count"]
        ):
            level = lvl
            break

    recommendation = {
        "high": "Sufficient for full stability battery. Promote to full mode.",
        "medium": "Sufficient for exploratory analysis. Consider full stability with caveats.",
        "low": "Insufficient power. Densification needed before stability analysis.",
    }

    return {
        "evidence_strength": level,
        "total_points": total_points,
        "n_distinct_depths": n_distinct_depths,
        "instances_count": instances_count,
        "thresholds": thresholds,
        "recommendation": recommendation[level],
    }


def run_scan(
    dataset_path: Path,
    *,
    dataset_id: str,
    sector: str,
    out_root: Path,
    power_criteria: Optional[Path] = None,
) -> Path:
    """Run scan-only analysis. Returns the run_dir."""
    run_dir = out_root / "runs" / _now_tag()
    tables_dir = run_dir / "tables"
    contracts_dir = run_dir / "contracts"
    figures_dir = run_dir / "figures"

    for d in (tables_dir, contracts_dir, figures_dir):
        d.mkdir(parents=True, exist_ok=True)

    # ── Input inventory ──────────────────────────────────────────────────
    inventory: List[Dict[str, Any]] = []
    if dataset_path.is_file():
        scan = _scan_csv(dataset_path)
        inventory.append(scan)
    elif dataset_path.is_dir():
        for f in sorted(dataset_path.rglob("*.csv")):
            inventory.append(_scan_csv(f))
        for f in sorted(dataset_path.rglob("*.xlsx")):
            inventory.append({
                "file": str(f),
                "sha256": _sha256_file(f),
                "size_bytes": f.stat().st_size,
            })
    else:
        print(f"WARNING: dataset path not found: {dataset_path}", file=sys.stderr)

    # Write inventory CSV
    inv_path = contracts_dir / "input_inventory.csv"
    with open(inv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "rows", "cols", "sha256", "size_bytes"])
        writer.writeheader()
        for item in inventory:
            writer.writerow({
                "file": item.get("file", ""),
                "rows": item.get("rows", ""),
                "cols": item.get("cols", ""),
                "sha256": item.get("sha256", ""),
                "size_bytes": item.get("size_bytes", ""),
            })

    # ── Stage contracts ──────────────────────────────────────────────────
    if power_criteria and power_criteria.exists():
        (contracts_dir / "POWER_CRITERIA.json").write_bytes(power_criteria.read_bytes())

    stab_path = Path("contracts/STABILITY_CRITERIA.json")
    if stab_path.exists():
        (contracts_dir / "STABILITY_CRITERIA.json").write_bytes(stab_path.read_bytes())

    # ── Power diagnostic ─────────────────────────────────────────────────
    total_rows = sum(item.get("rows", 0) for item in inventory if isinstance(item.get("rows"), int))
    n_files = len(inventory)
    # Rough heuristic for "distinct depths" — use number of files as proxy
    diag = _power_diagnostic(
        total_points=total_rows,
        n_distinct_depths=n_files,
        instances_count=n_files,
        power_criteria_path=power_criteria,
    )

    # ── Summary ──────────────────────────────────────────────────────────
    summary: Dict[str, Any] = {
        "dataset_id": dataset_id,
        "sector": sector,
        "run_mode": "scan_only",
        "dataset_path": str(dataset_path),
        "n_files_scanned": n_files,
        "total_rows": total_rows,
        "evidence_strength": diag["evidence_strength"],
        "power_diagnostic": diag,
        "inventory_detail": inventory,
        "recommendation": diag["recommendation"],
    }
    (tables_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── Placeholder figures ──────────────────────────────────────────────
    (figures_dir / "scan_placeholder.txt").write_text(
        f"Scan-only mode for {dataset_id} ({sector}). No figures generated.\n"
        f"Total rows: {total_rows}, Files: {n_files}, Power: {diag['evidence_strength']}\n"
    )

    # ── Manifest ─────────────────────────────────────────────────────────
    from tools.make_manifest import build_manifest
    manifest = build_manifest(run_dir, exclude_names={"manifest.json"})
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Scan complete: {run_dir}")
    print(f"  Power: {diag['evidence_strength']} ({total_rows} points, {n_files} files)")
    print(f"  Recommendation: {diag['recommendation']}")

    return run_dir


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan-only mode: inventory + diagnostics")
    ap.add_argument("--dataset", required=True, help="Path to dataset file or directory")
    ap.add_argument("--dataset-id", required=True, help="Dataset identifier")
    ap.add_argument("--sector", required=True, help="Sector name")
    ap.add_argument("--out-root", required=True, help="Output root directory")
    ap.add_argument("--power-criteria", default="contracts/POWER_CRITERIA.json")
    args = ap.parse_args()

    run_dir = run_scan(
        Path(args.dataset),
        dataset_id=args.dataset_id,
        sector=args.sector,
        out_root=Path(args.out_root),
        power_criteria=Path(args.power_criteria),
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
