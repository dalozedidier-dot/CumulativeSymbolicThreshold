"""generate_synth.py — Social sector fallback generator (real-data only).

Copies the pilot's real.csv + proxy_spec.json into the run outdir when
--real-csv is omitted.
"""

from __future__ import annotations

from pathlib import Path
import shutil


def synth_generator(outdir: Path, seed: int, pilot_id: str) -> None:
    _ = seed  # unused, kept for API compatibility

    repo_root = Path(__file__).resolve().parents[3]
    data_dir = repo_root / "03_Data" / "sector_social" / "real" / f"pilot_{pilot_id}"

    src_csv = data_dir / "real.csv"
    src_spec = data_dir / "proxy_spec.json"

    if not src_csv.exists():
        raise FileNotFoundError(f"Missing real.csv for pilot_id={pilot_id}: {src_csv}")
    if not src_spec.exists():
        raise FileNotFoundError(f"Missing proxy_spec.json for pilot_id={pilot_id}: {src_spec}")

    outdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_csv, outdir / "real.csv")
    shutil.copy2(src_spec, outdir / "proxy_spec.json")
