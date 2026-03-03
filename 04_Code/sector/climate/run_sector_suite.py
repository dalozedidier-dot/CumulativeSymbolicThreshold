"""run_sector_suite.py — Climate sector panel suite runner.

Pilots:
  co2_mauna_loa : NOAA Mauna Loa monthly CO₂ concentration (1958–present)
  gistemp       : NASA GISS global surface temperature anomalies (1880–present)

Usage:
  python 04_Code/sector/climate/run_sector_suite.py \\
      --pilot-id co2_mauna_loa \\
      --outdir 05_Results/sector_climate/run_001 \\
      --seed 1234 \\
      --mode smoke_ci

  # With real CSV (real-data mode):
  python 04_Code/sector/climate/run_sector_suite.py \\
      --pilot-id co2_mauna_loa \\
      --real-csv 03_Data/sector_climate/real/pilot_co2_mauna_loa/real.csv \\
      --outdir 05_Results/sector_climate/real_run_001 \\
      --seed 1234

Output mirrors the bio sector layout:
  <outdir>/pilot_<pilot_id>/
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

_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "04_Code" / "sector" / "shared"))

from sector_panel_runner import SectorConfig, make_parser, run_sector_panel
from generate_synth import generate as climate_generate


SECTOR_CONFIG = SectorConfig(
    sector_id     = "climate",
    pilot_ids     = ["co2_mauna_loa", "gistemp"],
    default_pilot = "co2_mauna_loa",
    data_root     = "03_Data/sector_climate",
    code_root     = "04_Code/sector/climate",
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


def main() -> int:
    parser = make_parser(SECTOR_CONFIG.sector_id, SECTOR_CONFIG.default_pilot)
    args   = parser.parse_args()

    def synth_generator(outdir: Path, seed: int, pilot_id: str) -> None:
        climate_generate(outdir, seed, pilot_id, n=300)

    return run_sector_panel(
        config          = SECTOR_CONFIG,
        args            = args,
        repo_root       = _REPO_ROOT,
        synth_generator = synth_generator,
    )


if __name__ == "__main__":
    sys.exit(main())
