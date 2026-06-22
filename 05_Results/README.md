# 05_Results — regenerable run outputs

`05_Results/` is **regenerable**: it holds the outputs of the `04_Code/pipeline/run_*`
producers, not frozen reference data. The whole directory is `.gitignore`d (see
[`docs/ARTIFACTS_POLICY.md`](../docs/ARTIFACTS_POLICY.md)).

## What is kept vs regenerated

To keep the repository light, only the **lightweight textual evidence of record**
is committed — the JSON/CSV/MD verdicts and summaries that documents such as
[`docs/EVIDENTIARY_STATUS.md`](../docs/EVIDENTIARY_STATUS.md) and
[`docs/EVIDENCE_LADDER.md`](../docs/EVIDENCE_LADDER.md) cite (e.g.
`endogenous_full_statistical/`, `confirmatory/`, `oos_prediction/`,
`real_validation/`, `surrogate_null/`, `multiverse/`, `effect_size/`).

**Regenerated, not committed:**

- all `*.png` figures — re-rendered by each pipeline's reporting step;
- bulk validation trees (`threshold_validation/`, one-off debug runs) — large and
  reproducible.

## Reproduce

Re-run the relevant producer into this directory, e.g.:

```bash
python 04_Code/pipeline/run_endogenous_full_statistical.py --outdir 05_Results/endogenous_full_statistical
python 04_Code/pipeline/run_confirmatory_suite.py          --outdir 05_Results/confirmatory
python 04_Code/pipeline/run_strong_negatives.py            --outdir 05_Results/strong_negatives
```

Do **not** `git add -f` new outputs here: that is exactly the bloat this policy
removes. If an artifact must be cited, commit only its small JSON/CSV/MD summary.
