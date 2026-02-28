#!/usr/bin/env python3
# 04_Code/reporting/build_real_data_ci_summary.py

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _find_latest_run_dir(root: Path) -> Path:
    if not root.exists():
        raise FileNotFoundError(f"root not found: {root}")

    candidates: list[Path] = []
    for p in root.rglob("*"):
        if p.is_dir() and (p / "tables" / "verdict.json").exists():
            candidates.append(p)

    if not candidates:
        # fallback: timestamped dirs directly under root
        candidates = [p for p in root.iterdir() if p.is_dir()]
        if not candidates:
            raise FileNotFoundError(f"no run dirs under: {root}")

    candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates[-1]


def _read_optional_csv_head(path: Path, n: int = 5) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, r in enumerate(reader):
            if i >= n:
                break
            rows.append({k: ("" if v is None else str(v)) for k, v in r.items()})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ci-out", default="_ci_out", help="CI output directory")
    ap.add_argument("--real-root", default="_ci_out/real_data_smoke", help="Real-data smoke root directory")
    args = ap.parse_args()

    ci_out = Path(args.ci_out)
    real_root = Path(args.real_root)
    ci_out.mkdir(parents=True, exist_ok=True)

    run_dir = _find_latest_run_dir(real_root)

    verdict_path = run_dir / "tables" / "verdict.json"
    summary_path = run_dir / "tables" / "summary.json"
    causal_csv = run_dir / "tables" / "causal_tests_summary.csv"
    manifest_path = run_dir / "manifest.json"
    params_path = run_dir / "params.txt"

    verdict = _read_json(verdict_path) if verdict_path.exists() else {}
    summary = _read_json(summary_path) if summary_path.exists() else {}
    manifest = _read_json(manifest_path) if manifest_path.exists() else {}

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gh = {
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_number": os.environ.get("GITHUB_RUN_NUMBER"),
        "sha": os.environ.get("GITHUB_SHA"),
        "ref": os.environ.get("GITHUB_REF"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
    }

    detected = verdict.get("binary_detected", verdict.get("detected", None))
    verdict_label = verdict.get("verdict", verdict.get("label", verdict.get("global", "unknown")))

    key_fields = {
        "verdict": verdict_label,
        "binary_detected": detected,
        "threshold_hit_t": verdict.get("threshold_hit_t"),
        "boot_ci_low_C": verdict.get("boot_ci_low_C", verdict.get("boot_ci_low")),
        "boot_ci_high_C": verdict.get("boot_ci_high_C", verdict.get("boot_ci_high")),
        "min_granger_S_to_deltaC_p": verdict.get("min_granger_S_to_deltaC_p"),
        "reverse_warning": verdict.get("reverse_warning"),
        "p_value_mean_shift_C": verdict.get("p_value_mean_shift_C"),
    }

    summary_json = {
        "generated_utc": now_utc,
        "run_dir": str(run_dir),
        "github": gh,
        "paths": {
            "verdict_json": str(verdict_path) if verdict_path.exists() else "",
            "summary_json": str(summary_path) if summary_path.exists() else "",
            "causal_tests_summary_csv": str(causal_csv) if causal_csv.exists() else "",
            "manifest_json": str(manifest_path) if manifest_path.exists() else "",
            "params_txt": str(params_path) if params_path.exists() else "",
        },
        "real_data": {
            "key_fields": key_fields,
            "verdict_json_present": verdict_path.exists(),
            "summary_json_present": summary_path.exists(),
            "manifest_present": manifest_path.exists(),
        },
        "causal_tests_summary_head": _read_optional_csv_head(causal_csv, n=5),
        "manifest_trace": manifest.get("trace", {}),
    }

    (ci_out / "summary_real_data_ci.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

    md = []
    md.append("## ORI-C Real Data Smoke Summary")
    md.append("")
    md.append(f"- generated_utc: `{now_utc}`")
    md.append(f"- run_dir: `{run_dir}`")
    md.append("")
    md.append("### Verdict")
    md.append("")
    for k, v in key_fields.items():
        md.append(f"- {k}: `{v}`")
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
    for k, v in summary_json["paths"].items():
        if v:
            md.append(f"- {k}: `{v}`")
    md.append("")

    md_text = "\n".join(md)
    (ci_out / "summary_real_data_ci.md").write_text(md_text, encoding="utf-8")

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(md_text + "\n")

    print(md_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
