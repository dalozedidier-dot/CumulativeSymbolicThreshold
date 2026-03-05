#!/usr/bin/env python3
"""
Disable noisy GitHub Actions workflows by moving YAML files out of .github/workflows/.

Why: GitHub shows any workflow file present in .github/workflows on the default branch.
Moving unwanted workflows to .github/workflows_disabled hides them from the Actions UI,
while keeping the files for later restoration.

This script:
- creates .github/workflows_disabled/
- moves selected workflow yaml files there
- prints what it did
- is designed to be used by the one-shot workflow cleanup job.

It is conservative: it keeps a small "core" set (canonical + collector + qcc core).
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil

DEFAULT_KEEP = {
    "ci.yml",
    "collector.yml",
    "real_data_smoke.yml",
    "real_data_matrix.yml",
    "real_data_canonical_T1_T8.yml",
    "real_data_smoke_matrix.yml",
    "qcc_canonical_full.yml",
    "qcc_brisbane_stateprob_pipeline.yml",
    "qcc_polaron_real_smoke.yml",
    "qcc_real_data_smoke.yml",
    "symbolic_suite.yml",
    "t9_diagnostics.yml",
    "dependabot.yml",
}

# patterns of files to disable if present
DEFAULT_DISABLE_PREFIXES = (
    "sector_",
)
DEFAULT_DISABLE_NAMES = {
    "full_statistical.yml",
    "independent_replication.yml",
    "manual_runs.yml",
    "nightly_isolated.yml",
    "qcc_stateprob_bootstrap.yml",
    "qcc_stateprob_cross_conditions.yml",
    "qcc_stateprob_densify_stability.yml",
    "sector_bio.yml",
    "sector_bio_suite.yml",
    "sector_cosmo.yml",
    "sector_cosmo_suite.yml",
    "sector_infra.yml",
    "sector_infra_suite.yml",
    "sector_infra_cloud_suite.yml",
    "sector_social_suite.yml",
}

def should_disable(name: str, keep: set[str]) -> bool:
    if name in keep:
        return False
    if name in DEFAULT_DISABLE_NAMES:
        return True
    for pref in DEFAULT_DISABLE_PREFIXES:
        if name.startswith(pref):
            return True
    return False

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", help="Repo root path")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    wf_dir = root / ".github" / "workflows"
    disabled_dir = root / ".github" / "workflows_disabled"
    disabled_dir.mkdir(parents=True, exist_ok=True)

    if not wf_dir.exists():
        print(f"[ERR] {wf_dir} not found")
        return 2

    keep = set(DEFAULT_KEEP)

    moved = []
    kept = []
    for p in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        name = p.name
        if should_disable(name, keep):
            dest = disabled_dir / name
            if args.dry_run:
                print(f"[DRY] move {p} -> {dest}")
            else:
                shutil.move(str(p), str(dest))
                moved.append(name)
        else:
            kept.append(name)

    print(f"[INFO] kept ({len(kept)}): {', '.join(kept) if kept else '(none)'}")
    print(f"[INFO] moved ({len(moved)}): {', '.join(moved) if moved else '(none)'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
