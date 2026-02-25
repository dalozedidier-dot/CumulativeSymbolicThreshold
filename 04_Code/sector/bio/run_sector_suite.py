#!/usr/bin/env python3
"""04_Code/sector/bio/run_sector_suite.py

Entry point for the biology sector suite.

Usage
-----
    python 04_Code/sector/bio/run_sector_suite.py \
        --pilot-id epidemic \
        --outdir _sector_bio_out/epidemic \
        --seed 1234 \
        --mode smoke_ci

Modes
-----
    smoke_ci          Fast CI (n_steps=150, n_boot=200, max_lag=5)
    full_statistical  Thorough (n_steps=300, n_boot=800, max_lag=10)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo and 04_Code are importable
_HERE = Path(__file__).resolve()
_SECTOR_BIO = _HERE.parent
_SECTOR_ROOT = _SECTOR_BIO.parent          # 04_Code/sector/
_CODE_DIR = _SECTOR_ROOT.parent            # 04_Code/
_REPO_DIR = _CODE_DIR.parent               # CumulativeSymbolicThreshold/

for _p in [str(_CODE_DIR), str(_REPO_DIR), str(_SECTOR_ROOT / "shared")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import generate_synth as _gen              # noqa: E402 (local, 04_Code/sector/bio/)
from sector_panel_runner import run_sector_pilot  # noqa: E402

_N_STEPS_BY_MODE = {"smoke_ci": 200, "full_statistical": 350}

_VALID_PILOTS = {"epidemic", "geneexpr", "ecology"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Bio sector ORI-C suite")
    ap.add_argument("--pilot-id", required=True, choices=sorted(_VALID_PILOTS))
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--mode", default="smoke_ci", choices=["smoke_ci", "full_statistical"])
    args = ap.parse_args()

    n_steps = _N_STEPS_BY_MODE[args.mode]
    df = _gen.generate(pilot_id=args.pilot_id, seed=args.seed, n_steps=n_steps)

    pilot_id = f"bio-{args.pilot_id}-{args.seed % 100:02d}"
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    result = run_sector_pilot(
        df_raw=df,
        pilot_id=pilot_id,
        outdir=outdir,
        seed=args.seed,
        mode=args.mode,
    )

    print(f"[bio/{args.pilot_id}] global_verdict={result['global_verdict']}", flush=True)
    if result.get("not_robust_reason"):
        print(f"  reason: {result['not_robust_reason']}", flush=True)

    return 0 if result["global_verdict"] in ("ACCEPT", "INDETERMINATE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
