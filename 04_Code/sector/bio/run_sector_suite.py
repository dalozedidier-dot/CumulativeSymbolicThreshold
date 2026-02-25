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
"""run_sector_suite.py — Bio sector panel suite runner.

Pilots:
  epidemic  : SIR-like epidemic / contagion
  geneexpr  : cellular stress / heat-shock gene expression
  ecology   : Lotka-Volterra predator-prey with habitat perturbation

Usage:
  python 04_Code/sector/bio/run_sector_suite.py \\
      --pilot-id epidemic \\
      --outdir 05_Results/sector_bio/run_001 \\
      --seed 1234 \\
      --mode smoke_ci

  # With real CSV (real-data mode):
  python 04_Code/sector/bio/run_sector_suite.py \\
      --pilot-id epidemic \\
      --real-csv 03_Data/sector_bio/real/pilot_epidemic/real.csv \\
      --outdir 05_Results/sector_bio/real_run_001 \\
      --seed 1234

Output:
  05_Results/sector_bio/run_001/
    pilot_epidemic/
      synth_data/real.csv
      synth_data/proxy_spec.json
      pilot_data/mapping_validity.json
      real/verdict.json
      robustness/variant_*/
      sector_global_verdict.json
"""
from __future__ import annotations

import sys
from pathlib import Path

# Resolve repo root and add shared panel runner to path
_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent.parent          # 04_Code/sector/bio/ → repo root
sys.path.insert(0, str(_REPO_ROOT / "04_Code" / "sector" / "shared"))

from sector_panel_runner import SectorConfig, make_parser, run_sector_panel
from generate_synth import generate as bio_generate


SECTOR_CONFIG = SectorConfig(
    sector_id     = "bio",
    pilot_ids     = ["epidemic", "geneexpr", "ecology"],
    default_pilot = "epidemic",
    data_root     = "03_Data/sector_bio",
    code_root     = "04_Code/sector/bio",
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
            "name":           "resample_80",
            "pre_horizon":    80,
            "post_horizon":   80,
            "normalize":      "robust_minmax",
            "resample_frac":  0.80,
        },
    ],
)


def main() -> None:
    parser = make_parser(SECTOR_CONFIG.sector_id, SECTOR_CONFIG.default_pilot)
    args   = parser.parse_args()

    # Wrap generate so sector_panel_runner can call it without knowing the sector
    def synth_generator(outdir: Path, seed: int, pilot_id: str) -> None:
        bio_generate(outdir, seed, pilot_id, n=250)

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
