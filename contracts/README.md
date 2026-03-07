# contracts/ — Validation contracts (JSON schemas)

Machine-readable contracts that define the acceptance criteria for CI pipeline runs.

| File | Purpose |
|------|---------|
| `DUAL_PROOF_CONTRACT.json` | Dual proof (synthetic + real) acceptance gate |
| `SYNTHETIC_GATE_CONTRACT.json` | Synthetic suite pass/fail criteria |
| `VALIDATION_PROTOCOL_CONTRACT.json` | Real data validation protocol criteria |
| `VALIDATION_BENCHMARK.json` | Benchmark thresholds |
| `VALIDATION_DECIDABILITY.json` | Decidability requirements |
| `VALIDATION_PRECHECKS.json` | Pre-check requirements before running validation |
| `VALIDATION_SPECIFICITY.json` | Specificity criteria |
| `POWER_CRITERIA.json` | Statistical power gate (≥ 0.70) |
| `STABILITY_CRITERIA.json` | Stability criteria for regime detection |
| `PLAN_SCHEMA.json` | Plan schema definition |

These contracts are consumed by `tools/enforce_output_contract.py` and the CI pipelines.
