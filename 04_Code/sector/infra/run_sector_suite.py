"""run_sector_suite.py — Infra sector panel suite runner.

Pilots:
  grid    : Electrical grid (frequency, reserve margin, cross-border flows)
  traffic : Urban traffic network (speed ratio, congestion, routing memory)
  finance : Macro-financial regime (volatility, credit spread, liquidity)

Note: the finance pilot is methodologically equivalent to the FRED monthly
canonical pilot but uses ORI-C mapped proxies with explicit U(t) annotation.
It demonstrates ORI-C in its "natural domain" with a controlled policy shock.

Usage:
  python 04_Code/sector/infra/run_sector_suite.py \\
      --pilot-id grid \\
      --outdir 05_Results/sector_infra/run_001 \\
      --seed 1234 --mode smoke_ci

  # Finance pilot with real FRED data (if available):
  python 04_Code/sector/infra/run_sector_suite.py \\
      --pilot-id finance \\
      --real-csv 03_Data/real/fred_monthly/real.csv \\
      --outdir 05_Results/sector_infra/finance_real_001

Output mirrors other sectors: pilot_<id>/real/, robustness/, sector_global_verdict.json
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "04_Code" / "sector" / "shared"))

from sector_panel_runner import SectorConfig, make_parser, run_sector_panel
from generate_synth import generate as infra_generate


SECTOR_CONFIG = SectorConfig(
    sector_id     = "infra",
    pilot_ids     = ["grid", "traffic", "finance"],
    default_pilot = "grid",
    data_root     = "03_Data/sector_infra",
    code_root     = "04_Code/sector/infra",
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
        infra_generate(outdir, seed, pilot_id, n=300)

    rc = run_sector_panel(
        config          = SECTOR_CONFIG,
        args            = args,
        repo_root       = _REPO_ROOT,
        synth_generator = synth_generator,
    )
    sys.exit(rc)


if __name__ == "__main__":

    raise SystemExit(main())
"""run_sector_suite.py — Infra sector panel suite runner.

Pilots:
  grid    : Electrical grid (frequency, reserve margin, cross-border flows)
  traffic : Urban traffic network (speed ratio, congestion, routing memory)
  finance : Macro-financial regime (volatility, credit spread, liquidity)

Note: the finance pilot is methodologically equivalent to the FRED monthly
canonical pilot but uses ORI-C mapped proxies with explicit U(t) annotation.
It demonstrates ORI-C in its "natural domain" with a controlled policy shock.

Usage:
  python 04_Code/sector/infra/run_sector_suite.py \\
      --pilot-id grid \\
      --outdir 05_Results/sector_infra/run_001 \\
      --seed 1234 --mode smoke_ci

  # Finance pilot with real FRED data (if available):
  python 04_Code/sector/infra/run_sector_suite.py \\
      --pilot-id finance \\
      --real-csv 03_Data/real/fred_monthly/real.csv \\
      --outdir 05_Results/sector_infra/finance_real_001

Output mirrors other sectors: pilot_<id>/real/, robustness/, sector_global_verdict.json
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE      = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "04_Code" / "sector" / "shared"))

from sector_panel_runner import SectorConfig, make_parser, run_sector_panel
from generate_synth import generate as infra_generate


SECTOR_CONFIG = SectorConfig(
    sector_id     = "infra",
    pilot_ids     = ["grid", "traffic", "finance"],
    default_pilot = "grid",
    data_root     = "03_Data/sector_infra",
    code_root     = "04_Code/sector/infra",
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
        infra_generate(outdir, seed, pilot_id, n=300)

    rc = run_sector_panel(
        config          = SECTOR_CONFIG,
        args            = args,
        repo_root       = _REPO_ROOT,
        synth_generator = synth_generator,
    )
    sys.exit(rc)


if __name__ == "__main__":
main
    main()
main
