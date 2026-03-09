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
| Domains covered | 7 |

### Proof Levels

- **Level A — Canonical:** Synthetic, FRED, validation protocol, dual proof
- **Level B — Conclusive pilots:** Real datasets with decidable verdict
- **Level C — Exploratory:** Signal present, insufficient power

### Test Suite

```
351 tests passing
17 test files
43 generalization-specific tests
```

### Contracts

| Contract | Purpose |
|----------|---------|
| `FROZEN_PARAMS.json` | 25 immutable parameters |
| `FROZEN_PILOT_CORPUS.json` | 7 pilots, versioned |
| `PILOT_GENERALIZATION.json` | Generalization matrix |
| `POWER_UPGRADE_PROTOCOL.json` | Level C densification plans |
| `SHOWCASE_PILOTS.json` | 2 showcase configurations |

### Links

- [Canonical Proof](canonical_proof.md)
- [Generalization Pilots](generalization_pilots.md)
- [Limitations and Power](limitations_power.md)
- [Replication Protocol](REPLICATION_PROTOCOL.md)
