"""Fail-fast guard: require STABILITY_CRITERIA.json to be staged into the run directory.

Use this before running the stability battery to prevent silent fallback to defaults.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _find_latest_run_dir(out_root: Path) -> Path:
    runs_dir = out_root / "runs"
    if not runs_dir.exists():
        raise FileNotFoundError(f"runs directory not found: {runs_dir}")
    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not run_dirs:
        raise FileNotFoundError(f"no run directories found under: {runs_dir}")
    run_dirs.sort(key=lambda p: p.name)
    return run_dirs[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--run-dir", default="")
    args = ap.parse_args()

    out_root = Path(args.out_root)
    run_dir = Path(args.run_dir) if args.run_dir else _find_latest_run_dir(out_root)

    criteria = run_dir / "contracts" / "STABILITY_CRITERIA.json"
    if not criteria.exists():
        raise SystemExit(
            f"ERROR: missing staged stability criteria at {criteria}. "
            "Stage it before stability battery to avoid non-deterministic defaults."
        )

    print(json.dumps({"ok": True, "run_dir": str(run_dir), "criteria": str(criteria)}, indent=2))


if __name__ == "__main__":
    main()
