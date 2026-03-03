Patch: Collector downloads artifacts from other workflow runs

Problem fixed:
- actions/download-artifact without run-id only downloads artifacts produced in the *current* workflow run.
  Therefore collector.yml saw an empty _collected_artifacts/ and wrote empty ci_metrics/*.csv.

Fix:
- For workflow_run triggers, collector.yml downloads artifacts from github.event.workflow_run.id.
- For schedule/workflow_dispatch, collector.yml uses tools/collector_download_artifacts.py (gh api + gh run download)
  to fetch artifacts from the latest successful runs of the canonical workflows.

How to apply:
- Unzip at repo root (overwrites .github/workflows/collector.yml, adds tools/collector_download_artifacts.py).
- Commit + push.
- Run "Collector — Append-only CI Metrics History" manually once (workflow_dispatch).
- Then run a canonical workflow (QCC Canonical Full or Real Data Canonical) and observe ci_metrics/history.csv populated.
