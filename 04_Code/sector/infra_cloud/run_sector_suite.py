"""run_sector_suite.py — Infra Cloud sector panel suite runner.

This runner is intentionally thin: it delegates all logic to the shared
sector panel runner (04_Code/sector/shared/sector_panel_runner.py).

Note:
- In CI we run in smoke_ci mode by default (non-blocking REJECT).
- When --real-csv is omitted, we *do not* generate synthetic data here.
  Instead we copy the pilot's real.csv + proxy_spec.json from 03_Data.
"""

from __future__ import annotations

import pathlib
import sys
from pathlib import Path

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_SHARED_DIR = _REPO_ROOT / "04_Code" / "sector" / "shared"
sys.path.insert(0, str(_SHARED_DIR))

from sector_panel_runner import SectorConfig, make_parser, run_sector_panel  # type: ignore

from .generate_synth import synth_generator  # copies real pilot files when --real-csv is omitted


SECTOR_CONFIG = SectorConfig(
    sector_id="infra_cloud",
    pilot_ids=["ec2_cpu_825cc2", "ec2_cpu_24ae8d", "ec2_disk_c0d644", "ec2_net_in_a2eb1cd9"],
    default_pilot="ec2_cpu_825cc2",
    data_root="03_Data/sector_infra_cloud",
    code_root="04_Code/sector/infra_cloud",
    default_seed=1234,
    default_alpha="0.01",
    default_lags="1-5",
    default_n_runs=50,
    default_normalize="robust_minmax",
)


def main() -> int:
    parser = make_parser(SECTOR_CONFIG.sector_id, SECTOR_CONFIG.default_pilot)
    args = parser.parse_args()
    return run_sector_panel(
        config=SECTOR_CONFIG,
        args=args,
        repo_root=Path(_REPO_ROOT),
        synth_generator=synth_generator,
    )


if __name__ == "__main__":
    raise SystemExit(main())
