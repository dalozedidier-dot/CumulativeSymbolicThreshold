#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Non-interpretative checks for stateprob bootstrap outputs.

Goal: assert presence of minimum audit artefacts without forcing interpretation.
Accepts that t* may be undefined (no threshold hit), so tstar tables may exist but be all NaN.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _latest_run_dir(out_root: Path) -> Path:
    runs = sorted((out_root / "runs").glob("*"))
    if not runs:
        raise FileNotFoundError(f"Aucun run trouvé sous: {out_root}/runs")
    return runs[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()

    out_root = Path(args.out_root)
    run_dir = _latest_run_dir(out_root)
    tables = run_dir / "tables"
    figs = run_dir / "figures"

    required_tables = ["ccl_timeseries.csv", "summary.json", "tstar_by_instance.csv", "bootstrap_tstar.csv"]
    missing = []
    for f in required_tables:
        if not (tables / f).exists():
            missing.append(str(tables / f))

    # At least one png
    pngs = list(figs.glob("*.png"))
    if not pngs:
        missing.append(str(figs / "*.png"))

    if missing:
        for m in missing:
            print(f"Artefact manquant: {m}", file=sys.stderr)
        return 1

    # summary must be valid json
    try:
        _ = json.loads((tables / "summary.json").read_text(encoding="utf-8"))
    except Exception as e:
        print(f"summary.json invalide: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
