#!/usr/bin/env python3
"""make_replication_bundle.py — assemble a self-contained Zenodo replication bundle.

Produces ``dist/oric_replication_bundle_<version>.zip`` containing everything an
independent party needs to rebuild the ORI-C verdicts **offline**: the code, the
frozen contracts, the constraints lock-ceiling, the reproducible Dockerfile, the
one-command driver (``scripts/run_replication.sh``), the small frozen inputs, and
the interpretation docs — plus a ``BUNDLE_MANIFEST.json`` with a sha256 for every
file and a top-level ``RUN.md``.

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

Self-contained snapshot for independent replication. No network required.

## Option A — Docker (recommended, fully pinned)

```bash
docker build -t oric:latest .
docker run --rm -v "$(pwd)/replication_output:/app/replication_output" \\
  oric:latest bash scripts/run_replication.sh
```

## Option B — local Python 3.12

```bash
pip install -e ".[dev]"            # honours constraints.txt automatically in CI/Docker
bash scripts/run_replication.sh
```

Outputs land in `replication_output/REPLICATION_SUMMARY.json`.

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
