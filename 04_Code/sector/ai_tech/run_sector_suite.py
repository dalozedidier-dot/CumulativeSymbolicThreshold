"""run_sector_suite.py — AI/Tech sector panel suite runner.

Pilots:
  mlperf      : MLPerf training efficiency benchmarks (calibrated synthetic)
  llm_scaling : LLM emergent capability scaling (Chinchilla law calibrated)

Usage:
  python 04_Code/sector/ai_tech/run_sector_suite.py \\
      --pilot-id llm_scaling \\
      --outdir 05_Results/sector_ai_tech/run_001 \\
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
from generate_synth import generate as ai_generate


SECTOR_CONFIG = SectorConfig(
    sector_id     = "ai_tech",
    pilot_ids     = ["mlperf", "llm_scaling"],
    default_pilot = "llm_scaling",
    data_root     = "03_Data/sector_ai_tech",
    code_root     = "04_Code/sector/ai_tech",
    default_seed      = 1234,
    default_alpha     = "0.01",
    default_lags      = "1-5",
    default_normalize = "robust_minmax",
    robustness_variants = [
        {
            "name":         "window_short",
            "pre_horizon":  20,
            "post_horizon": 20,
            "normalize":    "robust_minmax",
        },
        {
            "name":         "window_medium",
            "pre_horizon":  40,
            "post_horizon": 40,
            "normalize":    "robust_minmax",
        },
        {
            "name":         "norm_minmax",
            "pre_horizon":  40,
            "post_horizon": 40,
            "normalize":    "minmax",
        },
        {
            "name":           "resample_80",
            "pre_horizon":    40,
            "post_horizon":   40,
            "normalize":      "robust_minmax",
            "resample_frac":  0.80,
        },
    ],
)


def main() -> int:
    parser = make_parser(SECTOR_CONFIG.sector_id, SECTOR_CONFIG.default_pilot)
    args   = parser.parse_args()

    def synth_generator(outdir: Path, seed: int, pilot_id: str) -> None:
        ai_generate(outdir, seed, pilot_id, n=80)

    return run_sector_panel(
        config          = SECTOR_CONFIG,
        args            = args,
        repo_root       = _REPO_ROOT,
        synth_generator = synth_generator,
    )


if __name__ == "__main__":
    sys.exit(main())
