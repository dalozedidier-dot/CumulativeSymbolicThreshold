"""run_sector_suite.py — Infra Cloud sector panel suite runner.

Usage:
  python 04_Code/sector/infra_cloud/run_sector_suite.py --pilot-id ec2_cpu_825cc2 --outdir 05_Results/sector_infra_cloud/run_001 --seed 1234 --mode smoke_ci
"""

from __future__ import annotations

import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "04_Code" / "sector" / "shared"))

from sector_panel_runner import SectorConfig, make_parser, run_sector_panel  # type: ignore


SECTOR_CONFIG = SectorConfig(
    sector_id         = "infra_cloud",
    pilot_ids         = ['ec2_cpu_825cc2', 'ec2_cpu_24ae8d', 'ec2_disk_c0d644', 'ec2_net_in_a2eb1cd9'],
    default_pilot     = "ec2_cpu_825cc2",
    data_root         = "03_Data/sector_infra_cloud",
    code_root         = "04_Code/sector/infra_cloud",
    default_seed      = 1234,
    default_alpha     = "0.01",
    default_lags      = "1-5",
    default_n_runs    = 50,
    default_normalize = "robust_minmax",
)

def main() -> int:
    parser = make_parser(SECTOR_CONFIG)
    args = parser.parse_args()
    return run_sector_panel(SECTOR_CONFIG, args)

if __name__ == "__main__":
    raise SystemExit(main())
