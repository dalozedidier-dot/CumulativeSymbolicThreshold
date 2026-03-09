# Generalization Pilots

**Version:** 2.0.0
**Frozen benchmark:** `contracts/GENERALIZATION_BENCHMARK.json`
**Frozen corpus:** `contracts/FROZEN_PILOT_CORPUS.json`

!!! info "Canonical benchmark object"
    This page documents the **ORI-C Generalization Benchmark v2.0.0**,
    frozen on 2026-03-09. All 7 pilots are decidable at Level B.
    When citing, use:
    *ORI-C Generalization Benchmark v2.0.0 (frozen 2026-03-09)*.

---

## Generalization Matrix

| Pilot | Domain | N | Signal | Verdict | Level | Power |
|-------|--------|---|--------|---------|-------|-------|
| EEG Bonn | Neuro | 500 | Seizure threshold | **ACCEPT** | B | adequate |
| Solar | Cosmo | 288 | Solar cycle | **ACCEPT** | B | adequate |
| COVID | Health | 192 | Excess mortality | **ACCEPT** | B | borderline |
| Pantheon SN | Cosmo | 150 | Hubble transition | **ACCEPT** | B | borderline |
| BTC | Finance | 141 | Volatility regime | **ACCEPT** | B | borderline |
| PBDB marine | Bio | 140 | Extinction threshold | **REJECT** | B | borderline |
| LLM scaling | AI/Tech | 120 | Scaling law | **REJECT** | B | borderline |

---

## Two Proof Levels

### Level A — Canonical
Core validation (not in pilot benchmark):
- Synthetic, FRED, validation protocol, dual proof
- Tracked in `dual_proof_manifest.json`

### Level B — Conclusive Real Pilots
All 7 datasets with decidable verdict:

!!! success "5 ACCEPT"
    BTC, COVID excess mortality, EEG Bonn, Solar, Pantheon SN — **publishable
    as confirmed out-of-domain applications.**

!!! info "2 REJECT"
    PBDB marine, LLM scaling — **no transition detected**. These are true
    negatives, not failures. They demonstrate that ORI-C has specificity.

---

## Power Classes

| Class | Criterion | Count | Datasets |
|-------|-----------|-------|----------|
| adequate | ≥200 pts, segments OK | 2 | EEG Bonn, Solar |
| borderline | 60–199 pts, segments OK | 5 | BTC, COVID, Pantheon SN, PBDB marine, LLM scaling |

Power class is **descriptive, not decisional**. All 5 borderline pilots
produced conclusive verdicts (3 ACCEPT, 2 REJECT).

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

## Power Upgrade Results (Completed)

All 3 former Level C pilots completed the full upgrade pipeline:

| Pilot | N before | N after | Verdict before | Verdict after | C1 | C2 | C3 |
|-------|----------|---------|----------------|---------------|----|----|-----|
| Pantheon SN | 100 | 150 | INDETERMINATE | **ACCEPT** | Passed | Passed | Passed |
| PBDB marine | 100 | 140 | INDETERMINATE | **REJECT** | Failed | Passed | Passed |
| LLM scaling | 60 | 120 | INDETERMINATE | **REJECT** | Failed | Passed | Passed |

Each upgrade preserved:

- The **research question** (unchanged)
- The **proxy definitions** (O, R, I, demand, S mapping identical)
- The **normalization** (robust_minmax)
- The **time axis semantics**

All 3 passed homogeneity checks before the pipeline run. The pipeline
then produced decidable verdicts with 0 indeterminate runs (45/45 each).

---

## Known Limitations

- Only 7 domains tested; framework incompatibility may emerge elsewhere
- No independent external replication yet
- `min_points_per_segment >= 60` blocks many real-world datasets by design
- REJECT verdicts may reflect proxy mapping inadequacy, not absence of physical threshold
- LLM scaling data is synthetic-calibrated, not real benchmark data

---

## Links

- [Framework Status](framework_status.md)
- [Limitations and Power](limitations_power.md)
- Frozen benchmark: `contracts/GENERALIZATION_BENCHMARK.json`
- Frozen corpus: `contracts/FROZEN_PILOT_CORPUS.json`
- Full report: `05_Results/PILOT_GENERALIZATION_REPORT.md`
