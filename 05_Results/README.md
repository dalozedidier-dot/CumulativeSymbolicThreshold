# 05_Results — evidence surface + generated output

This directory holds two different kinds of thing, with opposite rules.

## 1. The evidence surface (committed, anti-drift gated)

`docs/EVIDENCE_LADDER.md` fixes one governance rule: **every rung claimed in the
docs must be backed by a committed artifact under `05_Results/`**, produced under
the *frozen* parameters of its contract. These directories are that surface:

| Rung | Artifact | Verdict token |
|------|----------|---------------|
| 3 — synthetic full-statistical | `endogenous_full_statistical/` | `DEMONSTRATION_CONFIRMED` |
| 5–6 — registered A/B/C block | `registered_block/` | `REAL_BLOCK_REJECTED` |
| 6 — joint confirmatory (Tests A–D) | `confirmatory/` | `NOT_CONFIRMED` ×2 |
| 6 — Test B detail | `surrogate_null/` | — |
| 6 — Test A detail | `falsification/accumulation_control/` | — |
| 7 — strong negatives | `strong_negatives/` | `STRONG_NEGATIVES_CLEAN` |
| 8 — pre-registered OOS | `oos_prediction/` | `OOS_SKILL_INCONCLUSIVE` |
| 4 — real pilots | `real_validation/`, `pilots/`, `pilot_benchmark_summary.json` | Level B |

They are un-ignored one by one in `.gitignore`; everything else here is not.
Adding a rung means adding its artifact directory to that list.

`04_Code/tests/test_stored_artifacts_match_contracts.py` is the anti-drift gate:
cheap JSON reads that fail loudly if an artifact is deleted, regenerated with
off-contract parameters, or edited by hand (manifest `sha256` vs table file).
**It runs by default** — a gate nobody opts into enforces nothing. Opt out with
`--no-stored-artifact-tests` when you are deliberately working without them.

Negative and inconclusive verdicts are stored at exactly the same status as
positive ones. That is the point: `REAL_BLOCK_REJECTED` and
`OOS_SKILL_INCONCLUSIVE` are evidence, not failures to hide.

## 2. Generated run output (never committed)

Everything else — `canonical_tests/`, `registered_reports/`, demo runs, figures
rebuilt by `04_Code/reporting/` — is throwaway output of a pipeline run and stays
ignored. Regenerate locally with:

```bash
PYTHONPATH=src python 04_Code/pipeline/run_all_tests.py --outdir 05_Results/canonical_tests --fast
```

Use the nightly proof workflow for full statistical runs.

## History

Results committed before 2026-07-02 were stale and were moved to
`99_Archive/stale_05_Results_20260702/` — in particular an old FRED monthly PDF
reporting `GLOBAL VERDICT: ACCEPT` from 2026-02-21, which no longer represented
the validation state. That cleanup also swept out the evidence surface above,
which left the ladder's governance rule unenforceable and the anti-drift tests
skipped; the artifacts were restored from the same archive on 2026-08-19. The
stale FRED report stays archived.
