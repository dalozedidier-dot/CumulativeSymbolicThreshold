"""Stage stability criteria into a QCC run directory and (optionally) fail if missing.

Purpose:
- Make the stability criteria *deterministic* and *auditable* by copying
  contracts/STABILITY_CRITERIA.json into runs/<timestamp>/contracts/
- Optionally record the sha256 in tables/summary.json for traceability.

This script is intentionally mechanical: it does not recompute metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_latest_run_dir(out_root: Path) -> Path:
    runs_dir = out_root / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError(f"runs directory not found: {runs_dir}")
    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not run_dirs:
        raise FileNotFoundError(f"no run directories found under: {runs_dir}")
    # lexical sort works with YYYYMMDD_HHMMSS
    run_dirs.sort(key=lambda p: p.name)
    return run_dirs[-1]


def stage(criteria_path: Path, run_dir: Path, *, record_in_summary: bool = True) -> Dict[str, Any]:
    if not criteria_path.exists():
        raise FileNotFoundError(f"criteria file not found: {criteria_path}")

    contracts_dir = run_dir / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)

    dst = contracts_dir / "STABILITY_CRITERIA.json"
    dst.write_bytes(criteria_path.read_bytes())

    sha = _sha256_file(dst)

    info: Dict[str, Any] = {
        "staged_path": str(dst),
        "sha256": sha,
    }

    if record_in_summary:
        summary_path = run_dir / "tables" / "summary.json"
        if summary_path.exists():
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            # record at root, non-invasive
            data["stability_criteria"] = {
                "path": "contracts/STABILITY_CRITERIA.json",
                "sha256": sha,
            }
            summary_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            info["summary_updated"] = True
        else:
            info["summary_updated"] = False

    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True, help="Output root, e.g. _ci_out/qcc_stateprob_full")
    ap.add_argument("--run-dir", default="", help="Optional explicit run dir; if empty, uses latest under out-root/runs/")
    ap.add_argument("--criteria-path", default="contracts/STABILITY_CRITERIA.json", help="Repo criteria file path")
    ap.add_argument("--no-summary", action="store_true", help="Do not write sha256 into tables/summary.json")
    args = ap.parse_args()

    out_root = Path(args.out_root)
    run_dir = Path(args.run_dir) if args.run_dir else _find_latest_run_dir(out_root)
    criteria_path = Path(args.criteria_path)

    info = stage(criteria_path, run_dir, record_in_summary=not args.no_summary)
    print(json.dumps({"ok": True, "run_dir": str(run_dir), **info}, indent=2))


if __name__ == "__main__":
    main()
