#!/usr/bin/env python3
"""Disable selected GitHub Actions workflows by renaming them.

Why:
- GitHub Actions shows every *.yml/*.yaml file in .github/workflows/.
- To reduce clutter, we "disable" legacy/redundant workflows by renaming to *.yml.disabled
  (GitHub will ignore them).

Usage:
  python tools/disable_workflows.py

This script is idempotent.
"""
from __future__ import annotations

from pathlib import Path

WORKFLOWS_DIR = Path(".github/workflows")
DISABLED_DIR = Path(".github/workflows_disabled")

DISABLE = [
    "sector_bio.yml",
    "sector_bio_suite.yml",
    "sector_cosmo.yml",
    "sector_cosmo_suite.yml",
    "sector_infra.yml",
    "sector_infra_suite.yml",
    "sector_infra_cloud_suite.yml",
    "sector_social_suite.yml",
    "full_statistical.yml",
    "independent_replication.yml",
    "manual_runs.yml",
    "nightly_isolated.yml",
]

def main() -> int:
    if not WORKFLOWS_DIR.exists():
        print(f"[ERR] Missing {WORKFLOWS_DIR}")
        return 2
    DISABLED_DIR.mkdir(parents=True, exist_ok=True)

    changed = 0
    for name in DISABLE:
        src = WORKFLOWS_DIR / name
        if not src.exists():
            # already moved/renamed
            alt = WORKFLOWS_DIR / f"{name}.disabled"
            if alt.exists():
                continue
            continue

        dst = DISABLED_DIR / name
        # move original into workflows_disabled/ for archive
        dst.write_text(src.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        src.unlink()
        # write a small stub to keep a pointer (optional). But we prefer no stub in workflows/.
        changed += 1
        print(f"[OK] Disabled {name} -> .github/workflows_disabled/{name}")

    # Add README
    readme = DISABLED_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Workflows désactivés\n\n"
            "Ces fichiers ont été déplacés ici pour réduire le bruit dans l'onglet Actions.\n"
            "GitHub n'exécute pas les workflows en dehors de .github/workflows/.\n\n"
            "Pour réactiver : déplacer le fichier vers .github/workflows/.\n",
            encoding="utf-8",
        )

    print(f"[INFO] Disabled {changed} workflow(s).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
