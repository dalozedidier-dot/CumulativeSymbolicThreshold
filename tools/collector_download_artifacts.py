"""Download artifacts from latest successful canonical workflow runs.

Used by .github/workflows/collector.yml for schedule/workflow_dispatch runs.
Requires GH_TOKEN env var (GitHub token with actions:read).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import List


def _run(cmd: List[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDERR:\n{p.stderr}")
    return p.stdout.strip()


def get_repo() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY not set")
    return repo


def find_workflow_id(repo: str, workflow_name: str) -> int:
    # List workflows and match by name
    data = json.loads(_run(["gh", "api", f"repos/{repo}/actions/workflows"]))
    for wf in data.get("workflows", []):
        if wf.get("name") == workflow_name:
            return int(wf["id"])
    names = [wf.get("name") for wf in data.get("workflows", [])]
    raise RuntimeError(f"Workflow not found by name: {workflow_name}. Available: {names}")


def find_latest_success_run_id(repo: str, workflow_id: int) -> int:
    data = json.loads(
        _run(["gh", "api", f"repos/{repo}/actions/workflows/{workflow_id}/runs", "-f", "per_page=20"])
    )
    for run in data.get("workflow_runs", []):
        if run.get("conclusion") == "success":
            return int(run["id"])
    raise RuntimeError(f"No successful runs found for workflow id {workflow_id}")


def download_artifacts(repo: str, run_id: int, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # gh run download will fetch all artifacts for that run
    _run(["gh", "run", "download", str(run_id), "-R", repo, "-D", str(out_dir)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output directory for downloaded artifacts")
    ap.add_argument("--workflows", nargs="+", required=True, help="Workflow names to collect from")
    args = ap.parse_args()

    repo = get_repo()
    out_dir = Path(args.out)

    for wf_name in args.workflows:
        wf_id = find_workflow_id(repo, wf_name)
        run_id = find_latest_success_run_id(repo, wf_id)
        print(f"Downloading artifacts: workflow='{wf_name}' run_id={run_id}")
        download_artifacts(repo, run_id, out_dir / f"{wf_name.replace(' ', '_')}_{run_id}")


if __name__ == "__main__":
    main()
