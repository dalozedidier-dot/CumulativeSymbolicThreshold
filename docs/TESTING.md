# Test tiers — smoke · full · scientific

The suite is split into three tiers so that a developer (and CI) can pay for
exactly the confidence they need. Tiers are **labels**, applied centrally in the
root `conftest.py` (`pytest_collection_modifyitems`) from each test's module
name — there is no `pytestmark` scattered across files.

| Tier | Marker | What it is | Run it |
|---|---|---|---|
| **smoke** | `@pytest.mark.smoke` | Minimal, fast confidence check: package imports, `summarize_run`, the core ORI-C pipeline, proof-package plumbing. Seconds. | `make test-smoke` / `pytest -m smoke` |
| **full** | *(everything not `scientific`)* | The bulk of the suite — unit + integration + tool tests. The default dev gate. | `make test-full` / `pytest -m "not scientific"` |
| **scientific** | `@pytest.mark.scientific` | Heavy statistical proofs: N≥50 endogenous runs, IAAFT/block surrogates, the multiverse grid, OOS prediction skill, DiD/synthetic-control causal inference, real-data onset, the strong-negatives battery. Minutes. | `make test-scientific` / `pytest -m scientific` |

`smoke ⊂ full`. `scientific` is disjoint from `full`. `full + scientific = the
whole suite`.

## Which tier runs where

| Surface | Tier(s) | Notes |
|---|---|---|
| `make test-smoke` | smoke | fastest local signal |
| `make test-full` | full | recommended pre-commit / pre-push gate |
| `make test-scientific` | scientific | run before claiming a statistical result |
| `make test` | **all** | smoke + full + scientific |
| CI `smoke` job | smoke | fail-fast, no coverage |
| CI `unit_tests` job | **all** (with coverage) | the 95 % coverage gate runs the *whole* suite, so tiering never lowers measured coverage |
| Nightly | scientific (N=60 proofs) | `full_statistical` + real-data canonical, the authoritative scientific run |

## Adding / re-tiering a test

Edit the two sets at the top of `conftest.py`:

```python
_SMOKE_MODULES = {"test_smoke", "test_oric_pipeline", "test_proof_infrastructure"}
_SCIENTIFIC_MODULES = {"test_oos_prediction", "test_multiverse", "test_strong_negatives", ...}
```

A module not listed in either set is, by definition, in the **full** tier. Keep
`scientific` for tests whose runtime is dominated by Monte-Carlo / resampling /
N≥50 simulation — i.e. tests that prove a *statistical* claim rather than a code
path. Everything else stays in `full` so the default gate keeps catching
regressions fast.
