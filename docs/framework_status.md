# Framework Status

**Last updated:** 2026-03-09

---

## Current Status: VALIDATED

The ORI-C framework has completed its canonical validation cycle.

### Proof Dimensions

| Dimension | Status | Key metric |
|-----------|--------|------------|
| Synthetic validation | **ACCEPT** | Sensitivity 1.0, Specificity 1.0, Fisher p < 10⁻⁴⁰ |
| FRED canonical | **ACCEPT** | Full protocol (C1+C2+C3) |
| Validation protocol | **ACCEPT** | 150 runs, 0 indeterminate |
| Dual proof | **COMPLETE** | Synthetic + Real aligned |
| Replication | **REPLICATED** | 3 batches, 270 runs, identical verdicts |

### Pilot Generalization

| Metric | Value |
|--------|-------|
| Total pilots | 7 |
| Level B (conclusive) | 4 (BTC, COVID, EEG Bonn, Solar) |
| Level C (exploratory) | 3 (LLM, Pantheon SN, PBDB marine) |
| Upgrade candidates | 3 (all passed homogeneity checks) |
| Domains covered | 7 |

### Proof Levels

- **Level A — Canonical:** Synthetic, FRED, validation protocol, dual proof
- **Level B — Conclusive pilots:** Real datasets with decidable verdict
- **Level C — Exploratory:** Signal present, insufficient power

### Power Upgrade Status

All 3 Level C pilots have ex-ante upgrade plans with documented invariants:

| Pilot | N before | N after | Power before | Power after | Status |
|-------|----------|---------|--------------|-------------|--------|
| Pantheon SN | 100 | 150 | underpowered | borderline | B_candidate |
| PBDB marine | 100 | 140 | underpowered | borderline | B_candidate |
| LLM scaling | 60 | 120 | underpowered | borderline | B_candidate |

!!! warning "Candidates, not confirmed"
    These pilots remain Level C. Upgrade to Level B requires full ORI-C
    pipeline run on densified data + decidable verdict + stability tests.
    See `contracts/POWER_UPGRADE_PROTOCOL.json` (v2.0).

### Test Suite

```
232 tests passing
19 test files
108 upgrade-specific tests
```

### Contracts

| Contract | Purpose |
|----------|---------|
| `FROZEN_PARAMS.json` | 25 immutable parameters |
| `FROZEN_PILOT_CORPUS.json` | 7 pilots, versioned |
| `PILOT_GENERALIZATION.json` | Generalization matrix |
| `GENERALIZATION_BENCHMARK.json` | Frozen public benchmark (v1.0.0) |
| `POWER_UPGRADE_PROTOCOL.json` | Ex-ante upgrade plans (v2.0) |
| `SHOWCASE_PILOTS.json` | 2 showcase configurations |

### Links

- [Canonical Proof](canonical_proof.md)
- [Generalization Pilots](generalization_pilots.md)
- [Limitations and Power](limitations_power.md)
- [Replication Protocol](REPLICATION_PROTOCOL.md)
