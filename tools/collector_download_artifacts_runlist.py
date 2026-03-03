#!/usr/bin/env python3
"""
Download artifacts using `gh run list` rather than REST workflow runs endpoint.

This avoids cases where `gh api .../workflows/{id}/runs` returns 404 under certain token policies.

Logic:
- For each workflow pattern, find matching workflow names (via `gh workflow list` JSON).
- For each matching workflow name, query latest successful run via `gh run list --workflow <name>`.
- Pick newest across matches, then `gh run download <run_id> --dir ...`.

Requires GH_TOKEN and gh CLI.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple


def _norm(s: str) -> str:
    s = s.strip()
    s = s.replace("—", "-").replace("–", "-").replace("−", "-")
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def _cmd(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr


@dataclass(frozen=True)
class WF:
    name: str


@dataclass(frozen=True)
class Pick:
    workflow_name: str
    run_id: int
    created_at: str


def list_workflows() -> List[WF]:
    # gh workflow list --json name
    rc, out, err = _cmd(["gh", "workflow", "list", "--json", "name"])
    if rc != 0:
        raise SystemExit(f"gh workflow list failed: {err.strip()}")
    data = json.loads(out) if out.strip() else []
    return [WF(name=str(w["name"])) for w in data]


def latest_success_for_workflow_name(wf_name: str) -> Optional[Tuple[int, str]]:
    # gh run list --workflow "<name>" --status success --limit 1 --json databaseId,createdAt
    rc, out, err = _cmd([
        "gh", "run", "list",
        "--workflow", wf_name,
        "--status", "success",
        "--limit", "1",
        "--json", "databaseId,createdAt",
    ])
    if rc != 0:
        # fail-soft
        print(f"[WARN] gh run list failed for workflow {wf_name!r}: {err.strip()}")
        return None
    data = json.loads(out) if out.strip() else []
    if not data:
        return None
    r0 = data[0]
    return int(r0["databaseId"]), str(r0.get("createdAt", ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workflows", nargs="+", required=True, help="Workflow name patterns (substring match).")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    wfs = list_workflows()

    picks: List[Pick] = []

    for patt in args.workflows:
        pnorm = _norm(patt)
        matches = [w for w in wfs if pnorm in _norm(w.name)]
        if not matches:
            print(f"[WARN] No workflow matched pattern: {patt!r}")
            continue

        best: Optional[Pick] = None
        for w in matches:
            res = latest_success_for_workflow_name(w.name)
            if not res:
                continue
            run_id, created_at = res
            cand = Pick(workflow_name=w.name, run_id=run_id, created_at=created_at)
            if best is None or cand.created_at > best.created_at:
                best = cand

        if not best:
            print(f"[WARN] No successful runs found for pattern {patt!r} (matched {[m.name for m in matches]}).")
            continue

        picks.append(best)
        print(f"[INFO] Pattern {patt!r} -> workflow '{best.workflow_name}' (run_id={best.run_id}, created_at={best.created_at})")

    # de-dup run_ids
    seen=set()
    uniq=[]
    for p in picks:
        if p.run_id in seen:
            continue
        seen.add(p.run_id)
        uniq.append(p)

    for p in uniq:
        dest = os.path.join(args.out, f"run_{p.run_id}")
        os.makedirs(dest, exist_ok=True)
        rc, _, err = _cmd(["gh", "run", "download", str(p.run_id), "--dir", dest])
        if rc != 0:
            raise SystemExit(f"gh run download failed for run_id={p.run_id}: {err.strip()}")

    # small index
    with open(os.path.join(args.out, "download_index.json"), "w", encoding="utf-8") as f:
        json.dump({"downloads": [p.__dict__ for p in uniq]}, f, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
