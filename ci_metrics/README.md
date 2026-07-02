# ci_metrics — clean run history

This directory was reset on 2026-07-02 because the previous CSV history mixed timestamps, commit SHAs and workflow names in the wrong columns.

The active collector should append rows using this canonical schema:

```text
github_run_id,run_dir_name,dataset_id,sector,run_mode,evidence_strength,all_pass,manifest_sha256,stability_criteria_sha256,commit_sha,workflow_source
```

The previous files were archived under `99_Archive/stale_ci_metrics_20260702/` for traceability, but they should not be used as a clean metrics source.
