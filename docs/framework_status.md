# Framework Status

**Last updated:** 2026-07-01

---

> ⚠️ **Read [`EVIDENTIARY_STATUS.md`](EVIDENTIARY_STATUS.md) first — it governs the
> interpretation of everything below.** The table headings here ("VALIDATED",
> "ACCEPT", "Fisher p < 10⁻⁴⁰") describe the *exploratory* pipeline state. They do
> **not** mean *solidly confirmed*: the only stored `full_statistical` proof run
> with the obligatory triplet (p + CI₉₉ % + SESOI + power) is the **synthetic
> endogenous bistable demonstration** (`05_Results/endogenous_full_statistical/`)
> — no *real-data pilot* has one. The synthetic p-values are N-driven artefacts,
> the one densified-pilot ACCEPT (Pantheon SN) is config-fragile (15/15 vs 0/15),
> and the decisive smooth-accumulation / surrogate-null controls are now
> implemented. The old bare detector fails the trend control; the current code
> adds a localized-transition gate that passes the shipped accumulation-specificity
> control, but the headline real pilots remain NOT_CONFIRMED because other
> confirmatory gates still fail.

## Current Status: EXPLORATORY / INDICATIVE — detector specificity patched, real pilots not confirmed

The ORI-C framework has completed its *exploratory* cycle and all 7 pilots have
decidable verdicts at Level B. The accumulation-specificity confound has been corrected in code by a localized-transition gate, while the IAAFT surrogate-null, full-statistical proof run and independent replication remain outstanding. See `EVIDENTIARY_STATUS.md`.

### Proof Dimensions

| Dimension | Status | Key metric |
|-----------|--------|------------|
| Synthetic validation | **INDICATIVE** | T1-T8 smoke and exploratory tests pass; the stored full-statistical triplet exists only for the endogenous bistable demonstration |
| Accumulation specificity | **PATCHED** | Localized gate passes shipped smooth-accumulation controls |
| Strong negatives (rung 7) | **CLEAN** | `STRONG_NEGATIVES_CLEAN` stored (`05_Results/strong_negatives/`): localized FPR 0.0 on 11 adversarial negatives, bifurcation TPR 1.0 |
| Registered A/B/C block (rung 5–6) | **REJECTED (honest negative)** | `REAL_BLOCK_REJECTED` stored (`05_Results/registered_block/`): ORI-C silent on FRED/GFC (surrogate p=1.0) but specific — silent on B/C while the classical panel false-fires 8× |
| FRED canonical | **NOT_CONFIRMED** | Fails surrogate-null and multiverse gates in confirmatory rerun |
| Pantheon SN | **NOT_CONFIRMED** | Passes Test A and multiverse, fails surrogate-null gate |
| Replication | **INFRASTRUCTURE PRESENT** | Needs clean external rerun for strong confirmation |

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
