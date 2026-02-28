#!/usr/bin/env python3
# 04_Code/reporting/build_ci_summary.py

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_latest_run_dir(canonical_root: Path) -> Path:
    if not canonical_root.exists():
        raise FileNotFoundError(f"canonical root not found: {canonical_root}")

    candidates = [p for p in canonical_root.iterdir() if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"no run dirs under: {canonical_root}")

    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates[-1]


def _mk_md_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_(no rows)_"

    cols = ["test", "verdict", "n_runs_observed", "n_check_exempt", "gate_passed", "reason"]
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for r in rows:
        line = "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |"
        lines.append(line)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ci-out", default="_ci_out", help="CI output directory")
    ap.add_argument("--canonical-root", default="_ci_out/canonical_tests", help="Canonical tests root")
    args = ap.parse_args()

    ci_out = Path(args.ci_out)
    canonical_root = Path(args.canonical_root)

    ci_out.mkdir(parents=True, exist_ok=True)

    latest_run_dir = _find_latest_run_dir(canonical_root)
    manifest_path = latest_run_dir / "manifest.json"
    verdict_path = latest_run_dir / "global_verdict.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in: {latest_run_dir}")
    if not verdict_path.exists():
        raise FileNotFoundError(f"global_verdict.json not found in: {latest_run_dir}")

    manifest = _read_json(manifest_path)
    verdict = _read_json(verdict_path)

    run_mode = str(manifest.get("run_mode", "unknown"))
    base_seed = manifest.get("base_seed", None)

    global_v = str(verdict.get("global", "INDETERMINATE"))
    support_level = str(verdict.get("support_level", "unknown"))

    gate = verdict.get("full_validation_gate", {}) or {}
    gate_passed = bool(gate.get("gate_passed", False))
    gate_tests = gate.get("tests", {}) or {}

    tests_rows: list[dict[str, Any]] = []
    for test_key in sorted(gate_tests.keys()):
        t = gate_tests[test_key] or {}
        tests_rows.append(
            {
                "test": test_key,
                "verdict": str(verdict.get("verdicts", {}).get(test_key, "INDETERMINATE")),
                "n_runs_observed": int(t.get("n_runs_observed", 0) or 0),
                "n_check_exempt": bool(t.get("n_check_exempt", False)),
                "gate_passed": bool(t.get("passed", False)),
                "reason": str(t.get("reason", "")),
            }
        )

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gh = {
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_number": os.environ.get("GITHUB_RUN_NUMBER"),
        "sha": os.environ.get("GITHUB_SHA"),
        "ref": os.environ.get("GITHUB_REF"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
    }

    summary_json = {
        "generated_utc": now_utc,
        "latest_run_dir": str(latest_run_dir),
        "run_mode": run_mode,
        "support_level": support_level,
        "global_verdict": global_v,
        "gate_passed": gate_passed,
        "base_seed": base_seed,
        "github": gh,
        "paths": {
            "manifest_json": str(manifest_path),
            "global_verdict_json": str(verdict_path),
        },
        "tests": tests_rows,
    }

    (ci_out / "summary_ci.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

    md = []
    md.append("## ORI-C Smoke CI Summary")
    md.append("")
    md.append(f"- generated_utc: `{now_utc}`")
    md.append(f"- latest_run_dir: `{latest_run_dir}`")
    md.append(f"- run_mode: `{run_mode}`")
    md.append(f"- support_level: `{support_level}`")
    md.append(f"- global_verdict: `{global_v}`")
    md.append(f"- gate_passed: `{gate_passed}`")
    md.append(f"- base_seed: `{base_seed}`")
    md.append("")
    md.append("### Trace GitHub")
    md.append("")
    md.append(f"- repository: `{gh.get('repository')}`")
    md.append(f"- workflow: `{gh.get('workflow')}`")
    md.append(f"- run_id: `{gh.get('run_id')}`")
    md.append(f"- run_number: `{gh.get('run_number')}`")
    md.append(f"- sha: `{gh.get('sha')}`")
    md.append(f"- ref: `{gh.get('ref')}`")
    md.append("")
    md.append("### Canonical pointers")
    md.append("")
    md.append(f"- manifest.json: `{manifest_path}`")
    md.append(f"- global_verdict.json: `{verdict_path}`")
    md.append("")
    md.append("### Full-validation gate detail")
    md.append("")
    md.append(_mk_md_table(tests_rows))
    md.append("")

    md_text = "\n".join(md)
    (ci_out / "summary_ci.md").write_text(md_text, encoding="utf-8")

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(md_text + "\n")

    print(md_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
