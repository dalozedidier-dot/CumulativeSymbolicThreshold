# Generalization Pilots

**Version:** 1.0.0
**Frozen corpus:** `contracts/FROZEN_PILOT_CORPUS.json`

---

## Generalization Matrix

| Pilot | Domain | N | Signal | Verdict | Level | Power | Risk |
|-------|--------|---|--------|---------|-------|-------|------|
| EEG Bonn | Neuro | 500 | Seizure threshold | **ACCEPT** | B | adequate | very low |
| Solar | Cosmo | 288 | Solar cycle | **ACCEPT** | B | adequate | low |
| COVID | Health | 192 | Excess mortality | **ACCEPT** | B | borderline | low |
| BTC | Finance | 141 | Volatility regime | **ACCEPT** | B | borderline | low |
| Pantheon SN | Cosmo | 100 | Hubble transition | INDETERMINATE | C | borderline | medium |
| PBDB marine | Bio | 100 | Extinction threshold | INDETERMINATE | C | borderline | medium |
| LLM scaling | AI/Tech | 60 | Scaling law | INDETERMINATE | C | underpowered | high |

---

## Three Proof Levels

### Level A — Canonical
Core validation (not in pilot benchmark):
- Synthetic, FRED, validation protocol, dual proof
- Tracked in `dual_proof_manifest.json`

### Level B — Conclusive Real Pilots
4 datasets with decidable verdict:

!!! success "Exploitable"
    BTC, COVID excess mortality, EEG Bonn, Solar — **publishable as confirmed
    out-of-domain applications.**

### Level C — Exploratory Under Precheck
3 datasets with plausible signal but insufficient power:

!!! warning "Under precheck"
    LLM scaling, Pantheon SN, PBDB marine — **publishable as exploratory
    signals with explicit power constraints.**

---

## Power Classes

| Class | Criterion | Count | Datasets |
|-------|-----------|-------|----------|
| adequate | ≥200 pts, segments OK | 2 | EEG Bonn, Solar |
| borderline | 60–199 pts, segments OK | 3 | BTC, COVID, Pantheon SN |
| underpowered | <60 pts or segments fail | 2 | LLM scaling, PBDB marine |

Power class is **descriptive, not decisional**. A borderline pilot can produce
a conclusive verdict (BTC and COVID prove this).

---

## Showcase Pilots

### Primary: EEG Bonn (Neuroscience)
- 500 segments, 5 class labels
- Strongest detection, out-of-domain
- Adequate power

### Secondary: BTC (Finance)
- 141 points, clear regime transition
- Borderline power, conclusive verdict
- Cross-domain portability

---

## Comparative Benchmark

Each pilot is benchmarked against four baseline methods:

| Method | Type | Strength |
|--------|------|----------|
| CUSUM changepoint | Mean shift detection | Fast, simple |
| Structural break | F-test at candidate points | Classical econometrics |
| Anomaly z-score | Rolling z-score | Novelty detection |
| Early warning signal | Variance + autocorrelation trend | Critical slowing down |

Results: `05_Results/benchmark/comparative_benchmark.json`

The goal is **not** to win everywhere, but to situate ORI-C:
- Where it is better (structured multi-proxy framework)
- Where it is complementary (EWS for pre-transition)
- Where it is more demanding but cleaner (avoids false positives via prechecks)

---

## Links

- [Framework Status](framework_status.md)
- [Limitations and Power](limitations_power.md)
- Frozen corpus: `contracts/FROZEN_PILOT_CORPUS.json`
- Full report: `05_Results/PILOT_GENERALIZATION_REPORT.md`
