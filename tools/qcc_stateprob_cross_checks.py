#!/usr/bin/env python3
"""
Non-interpretive checks for QCC StateProb Cross-Conditions outputs.

Robust to two layouts:
A) out_root/runs/<timestamp>/...   (preferred)
B) out_root/...                   (legacy: outputs written directly under out_root)

This script never infers meaning; it only validates presence + manifest consistency.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable


REQUIRED_RELATIVE = [
    "tables/summary.json",
    "tables/inventory.csv",
    "tables/recommendations.json",
    "tables/ccl_points.csv",
    "tables/ccl_by_shots.csv",
    "tables/tstar_by_shots.csv",
    "tables/bootstrap_tstar_by_shots.csv",
    "contracts/mapping_cross_conditions.json",
    "manifest.json",
    "figures/ccl_vs_axis_by_shots.png",
    "figures/tstar_hist.png",
]

def _latest_run_dir(out_root: Path) -> Path | None:
    runs_dir = out_root / "runs"
    if runs_dir.exists() and runs_dir.is_dir():
        subdirs = [p for p in runs_dir.iterdir() if p.is_dir()]
        if not subdirs:
            return None
        # lexicographic works for YYYYMMDD_HHMMSS
        return sorted(subdirs)[-1]
    return None

def _resolve_run_dir(out_root: Path) -> Path:
    run_dir = _latest_run_dir(out_root)
    if run_dir is not None:
        return run_dir
    # Legacy fallback: outputs written directly under out_root
    # Accept only if it looks like a run directory (has tables/ and manifest.json).
    if (out_root / "tables").exists() and (out_root / "manifest.json").exists():
        return out_root
    raise SystemExit(f"No runs directory: {out_root/'runs'} and legacy layout not detected under {out_root}")

def _load_manifest(run_dir: Path) -> dict:
    p = run_dir / "manifest.json"
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def _manifest_has(manifest: dict, relpath: str) -> bool:
    # Support either {"files": [{"path": ..., "sha256": ...}, ...]} or {"files": {path: sha256, ...}}
    files = manifest.get("files")
    if isinstance(files, dict):
        return relpath in files
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict) and item.get("path") == relpath:
                return True
    return False

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True, help="Output root directory (contains runs/ or is a run dir).")
    args = ap.parse_args()

    out_root = Path(args.out_root).resolve()
    if not out_root.exists():
        raise SystemExit(f"out-root does not exist: {out_root}")

    run_dir = _resolve_run_dir(out_root)

    missing = [rp for rp in REQUIRED_RELATIVE if not (run_dir / rp).exists()]
    if missing:
        raise SystemExit(f"Missing required outputs in {run_dir}: {missing}")

    manifest = _load_manifest(run_dir)
    missing_in_manifest = [rp for rp in REQUIRED_RELATIVE if not _manifest_has(manifest, rp)]
    if missing_in_manifest:
        raise SystemExit(f"Manifest missing entries: {missing_in_manifest}")

    print(f"OK: outputs + manifest validated in {run_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
