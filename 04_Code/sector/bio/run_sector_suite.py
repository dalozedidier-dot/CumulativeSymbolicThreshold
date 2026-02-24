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
