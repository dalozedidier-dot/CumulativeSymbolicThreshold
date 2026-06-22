#!/usr/bin/env python3
"""make_replication_bundle.py — assemble a self-contained Zenodo replication bundle.

Produces ``dist/oric_replication_bundle_<version>.zip`` containing everything an
independent party needs to rebuild the ORI-C verdicts: the code, the frozen
contracts, the constraints lock-ceiling, the reproducible Dockerfile, the
one-command driver (``scripts/run_replication.sh``), the small frozen inputs, and
the interpretation docs — plus a ``BUNDLE_MANIFEST.json`` with a sha256 for every
file and a top-level ``RUN.md``.

Network policy: the bundle carries all *code and data*, so once the Python 3.12
dependencies are installed (or the Docker image is built), the replication
**runs fully offline** — synthetic series are generated in-process and the only
real dataset (FRED monthly) is shipped inside the bundle. The dependency install
itself (pip / apt / the base image pull) DOES need network; for a truly air-gapped
run, pre-build the image or pre-populate a wheelhouse first (see RUN.md).

It deliberately EXCLUDES heavyweight, regenerable or non-essential material
(``05_Results/``, data bundles, large PDFs, git history, caches) so the archive
stays small and is itself reproducible.

Usage:
    python scripts/make_replication_bundle.py [--outdir dist] [--version v1.3.0]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Explicit allow-list of directories (recursive) and single files to ship.
INCLUDE_DIRS = [
    "src",
    "04_Code",
    "tools",
    "contracts",
    "02_Protocol",
    "scripts",
]
INCLUDE_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "constraints.txt",
    "conftest.py",
    "Dockerfile",
    "docker-compose.yml",
    "environment.yml",
    "Makefile",
    "README.md",
    "LICENSE",
    "CITATION.cff",
    ".zenodo.json",
    "docs/EVIDENCE_LADDER.md",
    "docs/EVIDENTIARY_STATUS.md",
    "docs/PYTHON_POLICY.md",
    "docs/TESTING.md",
    "docs/REPLICATION_BUNDLE.md",
    "docs/REPLICATION_PROTOCOL.md",
    "docs/REPRODUCE.md",
    # Small frozen real input used by the documented replication commands.
    "03_Data/real/fred_monthly/real.csv",
    "03_Data/real/fred_monthly/proxy_spec.json",
    "03_Data/real/fred_monthly/event_calendar.json",
]
# Patterns excluded even inside INCLUDE_DIRS.
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".so", ".png", ".pdf", ".docx", ".zip")
EXCLUDE_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                 ".egg-info", "tests"}  # drop test trees from the lean bundle


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _keep(path: Path) -> bool:
    if path.suffix in EXCLUDE_SUFFIXES:
        return False
    return not any(part in EXCLUDE_PARTS or part.endswith(".egg-info") for part in path.parts)


def _collect() -> list[Path]:
    files: list[Path] = []
    for d in INCLUDE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and _keep(p):
                files.append(p)
    for f in INCLUDE_FILES:
        p = ROOT / f
        if p.is_file():
            files.append(p)
    # De-duplicate, keep stable order.
    seen: set[Path] = set()
    uniq: list[Path] = []
    for p in files:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


_RUN_MD = """# ORI-C external replication bundle

Self-contained snapshot for independent replication: all *code and data* are
inside this archive.

## Network policy (what "offline" means here)

- **Running** the replication is fully **offline**: synthetic series are
  generated in-process and the only real dataset (FRED monthly) is bundled.
- **Installing the dependencies** is the one online step — `docker build`,
  `pip install`, `apt-get` and the base-image pull all reach the network.

So: do the install once with network, then every replication run is offline.
For a truly air-gapped machine, prepare the environment first on a connected
host (Option C) and copy it across.

## Option A — Docker (recommended, fully pinned; build needs network, run is offline)

```bash
docker build -t oric:latest .                                   # online (once)
docker run --rm --network none \\
  -v "$(pwd)/replication_output:/app/replication_output" \\
  oric:latest bash scripts/run_replication.sh                   # offline
```

## Option B — local Python 3.12 (install needs network, run is offline)

```bash
pip install -e ".[dev]"            # online (once); honours constraints.txt in CI/Docker
bash scripts/run_replication.sh    # offline
```

## Option C — air-gapped (pre-stage a wheelhouse on a connected host)

```bash
pip download -d wheelhouse -e ".[dev]"        # connected host
#   …copy the bundle + wheelhouse to the air-gapped host…
pip install --no-index --find-links wheelhouse -e ".[dev]"   # offline install
bash scripts/run_replication.sh                               # offline run
```

Outputs land in `replication_output/REPLICATION_SUMMARY.json`. The driver exits
non-zero on a TECHNICAL error, but exits 0 on an honest scientific negative.

## What you should see

The smoke-tier driver reproduces the **specificity** rungs:

- `strong_negatives.verdict == "STRONG_NEGATIVES_CLEAN"` (0 false positives on the
  adversarial negatives; the bare gate leaks on ~50 %).
- `accumulation_control.separates == true` (smooth accumulation rejected,
  bifurcation flagged).

The honest headline remains **NOT_CONFIRMED on real data** — read
`docs/EVIDENCE_LADDER.md` for what each rung means and why.

Integrity: every shipped file is hashed in `BUNDLE_MANIFEST.json`.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Assemble the ORI-C Zenodo replication bundle")
    ap.add_argument("--outdir", default="dist")
    ap.add_argument("--version", default=None, help="override version (default: read pyproject)")
    args = ap.parse_args()

    version = args.version
    if version is None:
        import tomllib
        version = "v" + tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    bundle_path = outdir / f"oric_replication_bundle_{version}.zip"

    files = _collect()
    manifest = {
        "schema": "oric.replication_bundle.v1",
        "version": version,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "n_files": len(files),
        "files": [
            {"path": str(p.relative_to(ROOT)), "sha256": _sha256(p), "size": p.stat().st_size}
            for p in files
        ],
    }

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, p.relative_to(ROOT))
        zf.writestr("BUNDLE_MANIFEST.json", json.dumps(manifest, indent=2))
        zf.writestr("RUN.md", _RUN_MD)

    total_mb = bundle_path.stat().st_size / 1e6
    print(f"Bundle:   {bundle_path.relative_to(ROOT)}")
    print(f"Files:    {len(files)}")
    print(f"Size:     {total_mb:.2f} MB")
    print(f"Manifest: BUNDLE_MANIFEST.json ({len(files)} sha256 entries) + RUN.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
