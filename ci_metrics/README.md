# ci_metrics — clean run history

This directory was reset on 2026-07-02 because the previous CSV history mixed timestamps, commit SHAs and workflow names in the wrong columns.

## Canonical schema

`runs_index.csv` — one row per collected run:

```text
github_run_id,run_dir_name,dataset_id,sector,run_mode,evidence_strength,all_pass,manifest_sha256,stability_criteria_sha256,commit_sha,workflow_source
```

`history.csv` — the same fields, prefixed with the collection `timestamp`:

```text
timestamp,github_run_id,run_dir_name,dataset_id,sector,run_mode,evidence_strength,all_pass,manifest_sha256,stability_criteria_sha256,commit_sha,workflow_source
```

The schema is defined once in `tools/collect_ci_metrics.py` (`RUNS_INDEX_FIELDS` /
`HISTORY_FIELDS`) and enforced by `tools/repo_doctor.py` (`CI_METRICS_FIELDS`); a
unit test asserts the two never drift apart.

## Who writes here

Only `tools/collect_ci_metrics.py`, invoked by
`.github/workflows/metrics_collector.yml`. It appends without rewriting the
header and **refuses to append when the existing header does not match the
canonical fields**, so a schema change fails the job instead of silently
shifting every subsequent row.

## Column drift (fixed 2026-08-19)

The 2026-07-02 reset fixed the *files* but not the *writer*: the collector
workflow still carried an inline copy of the extraction logic that listed the
same eleven fields in a **different order**. Since rows are appended under the
existing header, both rows collected after the reset landed one schema apart —
`commit_sha` under `run_mode`, `run_mode` under `manifest_sha256`, and so on.

Fixed by pointing the workflow at `tools/collect_ci_metrics.py` (which has the
header guard) and repairing the two affected rows with
`tools/repair_ci_metrics.py`. The values themselves were never lost, only
misplaced, so the repair is a pure re-alignment — no run was re-derived or
invented.

## Repairing

`tools/repair_ci_metrics.py --ci-metrics-dir ci_metrics` rewrites both files
into the canonical schema, writing `*_repaired.csv` plus a `repair_report.json`
alongside the originals (it never overwrites them). It recognises the legacy
layout by content, not by row width, because the legacy and canonical schemas
have the same number of columns.

The pre-reset files were archived under `99_Archive/stale_ci_metrics_20260702/`
for traceability, but they should not be used as a clean metrics source.
