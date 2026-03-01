#!/usr/bin/env python3
# 04_Code/reporting/build_real_data_ci_summary.py
#
# Robust against two layouts:
# 1) Flat: <root>/tables/..., <root>/figures/..., verdict.txt at root
# 2) Timestamped: <root>/<run_id>/tables/..., <root>/<run_id>/verdict.txt

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


def _is_run_dir(p: Path) -> bool:
    return (p / "tables" / "test_timeseries.csv").exists() and (p / "tables" / "summary.json").exists()


def _find_run_dir(root: Path) -> Path:
    if not root.exists():
        raise FileNotFoundError(f"root not found: {root}")

    if _is_run_dir(root):
        return root

    candidates = [p for p in root.rglob("*") if p.is_dir() and _is_run_dir(p)]
    if not candidates:
        raise FileNotFoundError(
            f"Could not find a run directory under {root}. "
            "Expected tables/test_timeseries.csv and tables/summary.json."
        )
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

    run_dir = _find_run_dir(real_root)

    tables = run_dir / "tables"
    verdict_json = tables / "verdict.json"
    verdict_txt = run_dir / "verdict.txt"
    summary_json = tables / "summary.json"
    causal_csv = tables / "causal_tests_summary.csv"
    manifest_json = run_dir / "manifest.json"
    params_txt = run_dir / "params.txt"

    verdict = _read_json(verdict_json) if verdict_json.exists() else {}
    summary = _read_json(summary_json) if summary_json.exists() else {}
    manifest = _read_json(manifest_json) if manifest_json.exists() else {}

    # Fallback verdict
    fallback_verdict_label = ""
    if verdict_txt.exists():
        fallback_verdict_label = verdict_txt.read_text(encoding="utf-8").strip()

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
    verdict_label = verdict.get("verdict", verdict.get("label", verdict.get("global", ""))) or summary.get("verdict") or fallback_verdict_label or "unknown"

    key_fields = {
        "verdict": verdict_label,
        "binary_detected": detected,
        "threshold_hit_t": verdict.get("threshold_hit_t", summary.get("threshold_hit_t")),
        "threshold_value": verdict.get("threshold_value", summary.get("threshold_value")),
        "boot_ci_low_C": verdict.get("boot_ci_low_C", verdict.get("boot_ci_low")),
        "boot_ci_high_C": verdict.get("boot_ci_high_C", verdict.get("boot_ci_high")),
        "min_granger_S_to_deltaC_p": verdict.get("min_granger_S_to_deltaC_p"),
        "reverse_warning": verdict.get("reverse_warning"),
        "p_value_mean_shift_C": verdict.get("p_value_mean_shift_C"),
        "n_steps": summary.get("n_steps"),
        "time_mode": summary.get("time_mode"),
        "run_mode": summary.get("run_mode"),
    }

    summary_out = {
        "generated_utc": now_utc,
        "run_dir": str(run_dir),
        "github": gh,
        "paths": {
            "verdict_json": str(verdict_json) if verdict_json.exists() else "",
            "verdict_txt": str(verdict_txt) if verdict_txt.exists() else "",
            "summary_json": str(summary_json) if summary_json.exists() else "",
            "causal_tests_summary_csv": str(causal_csv) if causal_csv.exists() else "",
            "manifest_json": str(manifest_json) if manifest_json.exists() else "",
            "params_txt": str(params_txt) if params_txt.exists() else "",
        },
        "real_data": {"key_fields": key_fields},
        "causal_tests_summary_head": _read_optional_csv_head(causal_csv, n=5),
        "manifest_trace": manifest.get("trace", {}),
    }

    (ci_out / "summary_real_data_ci.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")

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
