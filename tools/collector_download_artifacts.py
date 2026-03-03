#!/usr/bin/env python3
"""
Download artifacts from the latest successful runs of a set of workflows.

This tool is robust to workflow name drift:
- Accepts workflow *patterns* (case-insensitive substring match).
- Normalizes unicode dashes and whitespace.
- If multiple workflows match a pattern, picks the most recent successful run across them.
Requires GH_TOKEN and the GitHub CLI (`gh`) to be available in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


def _norm(s: str) -> str:
    # Normalize dashes and whitespace for matching stability.
    s = s.strip()
    s = s.replace("—", "-").replace("–", "-").replace("−", "-")
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def _run(cmd: List[str]) -> str:
    p = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.stdout


@dataclass(frozen=True)
class Workflow:
    wid: int
    name: str


@dataclass(frozen=True)
class Run:
    run_id: int
    created_at: str
    workflow_name: str


def list_workflows(repo: str) -> List[Workflow]:
    data = json.loads(_run(["gh", "api", f"repos/{repo}/actions/workflows", "--paginate"]))
    # GH API may return either {"workflows":[...]} or concatenated pages; handle both.
    wfs: List[Workflow] = []
    if isinstance(data, dict) and "workflows" in data:
        items = data["workflows"]
    else:
        # paginate returns a JSON per page; but gh api --paginate concatenates JSON objects.
        # Safer: re-fetch without paginate if structure unexpected.
        data2 = json.loads(_run(["gh", "api", f"repos/{repo}/actions/workflows"]))
        items = data2.get("workflows", [])
    for w in items:
        wfs.append(Workflow(wid=int(w["id"]), name=str(w["name"])))
    return wfs


def latest_success_run(repo: str, workflow_id: int) -> Optional[Tuple[int, str]]:
    # Get latest successful completed run for this workflow.
    # We ask for 1 item; GitHub returns newest first by default.
    out = _run([
        "gh", "api",
        f"repos/{repo}/actions/workflows/{workflow_id}/runs",
        "-F", "status=completed",
        "-F", "conclusion=success",
        "-F", "per_page=1",
    ])
    data = json.loads(out)
    runs = data.get("workflow_runs", []) if isinstance(data, dict) else []
    if not runs:
        return None
    r0 = runs[0]
    return int(r0["id"]), str(r0.get("created_at", ""))


def pick_latest_across(repo: str, workflows: List[Workflow]) -> Optional[Run]:
    best: Optional[Run] = None
    for wf in workflows:
        res = latest_success_run(repo, wf.wid)
        if not res:
            continue
        run_id, created_at = res
        cand = Run(run_id=run_id, created_at=created_at, workflow_name=wf.name)
        if best is None or cand.created_at > best.created_at:
            best = cand
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output directory for downloaded artifacts.")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="owner/repo (default: env GITHUB_REPOSITORY)")
    ap.add_argument("--workflows", nargs="+", required=True, help="Workflow name patterns (substring match, case-insensitive).")
    ap.add_argument("--dry-run", action="store_true", help="List what would be downloaded without downloading.")
    args = ap.parse_args()

    repo = args.repo.strip()
    if not repo or "/" not in repo:
        raise SystemExit(f"Invalid --repo '{repo}'. Expected 'owner/repo'.")

    os.makedirs(args.out, exist_ok=True)

    all_wfs = list_workflows(repo)
    name_map = {wf.wid: wf.name for wf in all_wfs}

    matched_any = False
    downloads: List[Run] = []

    for patt in args.workflows:
        pnorm = _norm(patt)
        matches = [wf for wf in all_wfs if pnorm in _norm(wf.name)]
        if not matches:
            # Provide helpful diagnostics but DO NOT crash the whole collector; just skip.
            avail = sorted([wf.name for wf in all_wfs])
            print(f"[WARN] No workflow matched pattern: {patt!r}. Available names: {avail}")
            continue
        matched_any = True
        best = pick_latest_across(repo, matches)
        if not best:
            print(f"[WARN] No successful runs found for pattern {patt!r} (matched {[m.name for m in matches]}).")
            continue
        downloads.append(best)
        print(f"[INFO] Pattern {patt!r} -> using workflow '{best.workflow_name}' (run_id={best.run_id}, created_at={best.created_at})")

    if not matched_any:
        raise SystemExit("No workflow patterns matched anything. Refine --workflows patterns.")

    # De-duplicate run_ids
    seen = set()
    downloads_unique: List[Run] = []
    for r in downloads:
        if r.run_id in seen:
            continue
        seen.add(r.run_id)
        downloads_unique.append(r)

    if args.dry_run:
        print("[DRYRUN] Would download:", [(r.workflow_name, r.run_id) for r in downloads_unique])
        return

    # Download artifacts for each chosen run
    for r in downloads_unique:
        # Put each run in its own directory to avoid collisions
        dest = os.path.join(args.out, f"run_{r.run_id}")
        os.makedirs(dest, exist_ok=True)
        print(f"[INFO] Downloading artifacts for run {r.run_id} into {dest} ...")
        subprocess.run(["gh", "run", "download", str(r.run_id), "--dir", dest], check=True)

    # Write a small index for auditability
    index_path = os.path.join(args.out, "download_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(
            {"repo": repo, "downloads": [r.__dict__ for r in downloads_unique]},
            f,
            indent=2,
            sort_keys=True,
        )
    print(f"[INFO] Wrote {index_path}")


if __name__ == "__main__":
    main()
