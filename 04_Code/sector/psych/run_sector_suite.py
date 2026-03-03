"""run_sector_suite.py — Psych sector panel suite runner.

Pilots:
  google_trends  : Social trust / collective behaviour via Google Trends (monthly)
                   Falls back to synthetic if pytrends/network unavailable.
  wvs_synthetic  : World Values Survey-calibrated norm diffusion model.

Usage:
  python 04_Code/sector/psych/run_sector_suite.py \\
      --pilot-id wvs_synthetic \\
      --outdir 05_Results/sector_psych/run_001 \\
      --seed 1234 \\
      --mode smoke_ci
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "04_Code" / "sector" / "shared"))

from sector_panel_runner import SectorConfig, make_parser, run_sector_panel
from generate_synth import generate as psych_generate


SECTOR_CONFIG = SectorConfig(
    sector_id     = "psych",
    pilot_ids     = ["google_trends", "wvs_synthetic"],
    default_pilot = "wvs_synthetic",
    data_root     = "03_Data/sector_psych",
    code_root     = "04_Code/sector/psych",
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
        psych_generate(outdir, seed, pilot_id, n=240)

    return run_sector_panel(
        config          = SECTOR_CONFIG,
        args            = args,
        repo_root       = _REPO_ROOT,
        synth_generator = synth_generator,
    )


if __name__ == "__main__":
    sys.exit(main())
