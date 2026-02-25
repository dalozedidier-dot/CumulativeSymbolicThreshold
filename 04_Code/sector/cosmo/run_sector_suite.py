#!/usr/bin/env python3
"""04_Code/sector/cosmo/run_sector_suite.py

Entry point for the cosmology/astrophysics sector suite.

Usage
-----
    python 04_Code/sector/cosmo/run_sector_suite.py \
        --pilot-id solar \
        --outdir _sector_cosmo_out/solar \
        --seed 1234 \
        --mode smoke_ci
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_SECTOR_COSMO = _HERE.parent
_SECTOR_ROOT = _SECTOR_COSMO.parent
_CODE_DIR = _SECTOR_ROOT.parent
_REPO_DIR = _CODE_DIR.parent

for _p in [str(_CODE_DIR), str(_REPO_DIR), str(_SECTOR_ROOT / "shared")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import generate_synth as _gen              # noqa: E402
from sector_panel_runner import run_sector_pilot  # noqa: E402

_N_STEPS_BY_MODE = {"smoke_ci": 200, "full_statistical": 350}
_VALID_PILOTS = {"solar", "stellar", "transient"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Cosmo sector ORI-C suite")
    ap.add_argument("--pilot-id", required=True, choices=sorted(_VALID_PILOTS))
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--mode", default="smoke_ci", choices=["smoke_ci", "full_statistical"])
    args = ap.parse_args()

    n_steps = _N_STEPS_BY_MODE[args.mode]
    df = _gen.generate(pilot_id=args.pilot_id, seed=args.seed, n_steps=n_steps)

    pilot_id = f"cosmo-{args.pilot_id}-{args.seed % 100:02d}"
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    result = run_sector_pilot(
        df_raw=df,
        pilot_id=pilot_id,
        outdir=outdir,
        seed=args.seed,
        mode=args.mode,
    )

    print(f"[cosmo/{args.pilot_id}] global_verdict={result['global_verdict']}", flush=True)
    if result.get("not_robust_reason"):
        print(f"  reason: {result['not_robust_reason']}", flush=True)

    return 0 if result["global_verdict"] in ("ACCEPT", "INDETERMINATE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""run_sector_suite.py — Cosmo sector panel suite runner.

Pilots:
  solar     : Solar activity cycle (sunspot, F10.7, Kp) + geomagnetic storm
  stellar   : Stellar photometric variability (Kepler-like) + instrument change
  transient : Astrophysical transient rate (ZTF-like) + survey downtime

Key feature: instrument change / survey gap is treated as a U(t) symbolic cut.
This is the standard Cosmo perturbation (equivalent to vaccination cut in bio).
T6 tests C(t) drop during the gap window.

Usage:
  python 04_Code/sector/cosmo/run_sector_suite.py \\
      --pilot-id solar \\
      --outdir 05_Results/sector_cosmo/run_001 \\
      --seed 1234 --mode smoke_ci

  # With real CSV:
  python 04_Code/sector/cosmo/run_sector_suite.py \\
      --pilot-id solar \\
      --real-csv 03_Data/sector_cosmo/real/pilot_solar/real.csv \\
      --outdir 05_Results/sector_cosmo/real_run_001

Output mirrors bio sector: pilot_<id>/real/, robustness/, sector_global_verdict.json
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "04_Code" / "sector" / "shared"))

from sector_panel_runner import SectorConfig, make_parser, run_sector_panel
from generate_synth import generate as cosmo_generate


SECTOR_CONFIG = SectorConfig(
    sector_id     = "cosmo",
    pilot_ids     = ["solar", "stellar", "transient"],
    default_pilot = "solar",
    data_root     = "03_Data/sector_cosmo",
    code_root     = "04_Code/sector/cosmo",
    default_seed      = 1234,
    default_alpha     = "0.01",
    default_lags      = "1-5",
    default_normalize = "robust_minmax",
    robustness_variants = [
        {
            "name":         "window_short",
            "pre_horizon":  40,
            "post_horizon": 40,
            "normalize":    "robust_minmax",
        },
        {
            "name":         "window_medium",
            "pre_horizon":  80,
            "post_horizon": 80,
            "normalize":    "robust_minmax",
        },
        {
            "name":         "norm_minmax",
            "pre_horizon":  80,
            "post_horizon": 80,
            "normalize":    "minmax",
        },
        {
            "name":         "resample_80",
            "pre_horizon":  80,
            "post_horizon": 80,
            "normalize":    "robust_minmax",
        },
    ],
)


def main() -> None:
    parser = make_parser(SECTOR_CONFIG.sector_id, SECTOR_CONFIG.default_pilot)
    args   = parser.parse_args()

    def synth_generator(outdir: Path, seed: int, pilot_id: str) -> None:
        cosmo_generate(outdir, seed, pilot_id, n=300)

    rc = run_sector_panel(
        config          = SECTOR_CONFIG,
        args            = args,
        repo_root       = _REPO_ROOT,
        synth_generator = synth_generator,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()
main
