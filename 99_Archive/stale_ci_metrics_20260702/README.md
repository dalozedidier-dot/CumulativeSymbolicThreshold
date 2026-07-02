# ci_metrics/ — CI run history and metrics

Collected metrics from CI pipeline runs, used for tracking pipeline health over time.

| File | Content |
|------|---------|
| `history.csv` | Raw CI run history |
| `history_repaired.csv` | Cleaned/normalized history |
| `runs_index.csv` | Index of all CI runs |
| `runs_index_repaired.csv` | Cleaned runs index |
| `repair_report.json` | Report from last repair operation |

These files are populated by `tools/collect_ci_metrics.py` and repaired by
`tools/repair_ci_metrics.py`.
