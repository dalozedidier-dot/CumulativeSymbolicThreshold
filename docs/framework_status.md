# Framework Status

**Last updated:** 2026-03-09

---

## Current Status: VALIDATED — ALL PILOTS DECIDABLE

The ORI-C framework has completed its canonical validation cycle and all 7 pilots
have decidable verdicts.

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
| Level B (decidable) | **7** |
| Level C (indeterminate) | **0** |
| ACCEPT verdicts | 5 (BTC, COVID, EEG Bonn, Solar, Pantheon SN) |
| REJECT verdicts | 2 (PBDB marine, LLM scaling) |
| Domains covered | 7 |

### Verdict Table

| Pilot | Domain | N | Verdict | Power |
|-------|--------|---|---------|-------|
| EEG Bonn | Neuro | 500 | **ACCEPT** | adequate |
| Solar | Cosmo | 288 | **ACCEPT** | adequate |
| COVID | Health | 192 | **ACCEPT** | borderline |
| Pantheon SN | Cosmo | 150 | **ACCEPT** | borderline |
| BTC | Finance | 141 | **ACCEPT** | borderline |
| PBDB marine | Bio | 140 | **REJECT** | borderline |
| LLM scaling | AI/Tech | 120 | **REJECT** | borderline |

### Proof Levels

- **Level A — Canonical:** Synthetic, FRED, validation protocol, dual proof
- **Level B — Conclusive pilots:** All 7 real datasets with decidable verdict

### Test Suite

```
246 tests passing
4 test files (generalization + upgrade)
```

### Contracts

| Contract | Version | Purpose |
|----------|---------|---------|
| `FROZEN_PARAMS.json` | 1.0 | 25 immutable parameters |
| `FROZEN_PILOT_CORPUS.json` | 2.0.0 | 7 pilots, all decidable |
| `PILOT_GENERALIZATION.json` | 2.0 | Generalization matrix |
| `GENERALIZATION_BENCHMARK.json` | 2.0.0 | Frozen public benchmark |
| `POWER_UPGRADE_PROTOCOL.json` | 2.0 | Ex-ante upgrade plans |
| `SHOWCASE_PILOTS.json` | 1.0 | 2 showcase configurations |

### Links

- [Canonical Proof](canonical_proof.md)
- [Generalization Pilots](generalization_pilots.md)
- [Limitations and Power](limitations_power.md)
- [Replication Protocol](REPLICATION_PROTOCOL.md)
