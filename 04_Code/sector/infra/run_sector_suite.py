#!/usr/bin/env python3
"""04_Code/sector/infra/run_sector_suite.py

Entry point for the infrastructure sector suite.

Usage
-----
    python 04_Code/sector/infra/run_sector_suite.py \
        --pilot-id grid \
        --outdir _sector_infra_out/grid \
        --seed 1234 \
        --mode smoke_ci
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_SECTOR_INFRA = _HERE.parent
_SECTOR_ROOT = _SECTOR_INFRA.parent
_CODE_DIR = _SECTOR_ROOT.parent
_REPO_DIR = _CODE_DIR.parent

for _p in [str(_CODE_DIR), str(_REPO_DIR), str(_SECTOR_ROOT / "shared")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import generate_synth as _gen              # noqa: E402
from sector_panel_runner import run_sector_pilot  # noqa: E402

_N_STEPS_BY_MODE = {"smoke_ci": 200, "full_statistical": 350}
_VALID_PILOTS = {"grid", "traffic", "finance"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Infra sector ORI-C suite")
    ap.add_argument("--pilot-id", required=True, choices=sorted(_VALID_PILOTS))
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--mode", default="smoke_ci", choices=["smoke_ci", "full_statistical"])
    args = ap.parse_args()

    n_steps = _N_STEPS_BY_MODE[args.mode]
    df = _gen.generate(pilot_id=args.pilot_id, seed=args.seed, n_steps=n_steps)

    pilot_id = f"infra-{args.pilot_id}-{args.seed % 100:02d}"
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    result = run_sector_pilot(
        df_raw=df,
        pilot_id=pilot_id,
        outdir=outdir,
        seed=args.seed,
        mode=args.mode,
    )

    print(f"[infra/{args.pilot_id}] global_verdict={result['global_verdict']}", flush=True)
    if result.get("not_robust_reason"):
        print(f"  reason: {result['not_robust_reason']}", flush=True)

    return 0 if result["global_verdict"] in ("ACCEPT", "INDETERMINATE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
