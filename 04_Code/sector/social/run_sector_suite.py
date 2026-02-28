"""run_sector_suite.py — Social sector panel suite runner (Twitter volume pilots)."""

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
    sector_id="social",
    pilot_ids=["twitter_amzn", "twitter_fb"],
    default_pilot="twitter_amzn",
    data_root="03_Data/sector_social",
    code_root="04_Code/sector/social",
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
