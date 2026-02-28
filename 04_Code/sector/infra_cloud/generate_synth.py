"""generate_synth.py — Infra Cloud sector fallback generator.

Despite the filename, this module does *not* generate synthetic data.

The shared sector panel runner expects a callable with signature:
    synth_generator(outdir: Path, seed: int, pilot_id: str) -> None

When --real-csv is omitted, we simply copy the pilot's real.csv and
proxy_spec.json from:
    03_Data/sector_infra_cloud/real/pilot_<pilot_id>/

into the run output directory.

This keeps CI deterministic and strictly real-data based.
"""

from __future__ import annotations

from pathlib import Path
import shutil


def synth_generator(outdir: Path, seed: int, pilot_id: str) -> None:
    _ = seed  # unused, kept for API compatibility

    repo_root = Path(__file__).resolve().parents[3]
    data_dir = repo_root / "03_Data" / "sector_infra_cloud" / "real" / f"pilot_{pilot_id}"

    src_csv = data_dir / "real.csv"
    src_spec = data_dir / "proxy_spec.json"

    if not src_csv.exists():
        raise FileNotFoundError(f"Missing real.csv for pilot_id={pilot_id}: {src_csv}")
    if not src_spec.exists():
        raise FileNotFoundError(f"Missing proxy_spec.json for pilot_id={pilot_id}: {src_spec}")

    outdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_csv, outdir / "real.csv")
    shutil.copy2(src_spec, outdir / "proxy_spec.json")
