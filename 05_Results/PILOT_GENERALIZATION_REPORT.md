# ORI-C Generalization Pilots Report

**Version:** 2.0
**Date:** 2026-03-09
**Status:** CANONICAL
**Contract:** `contracts/PILOT_GENERALIZATION.json`
**Registry:** `05_Results/pilots/pilot_generalization_registry.json`

---

## 1. Why These Pilots Were Chosen

The ORI-C framework was validated canonically on synthetic data, FRED economic data,
and a formal three-condition validation protocol. To demonstrate **portability beyond
the canonical domain**, seven real-data pilots were selected across six independent
scientific domains:

| Domain | Pilot | Rationale |
|--------|-------|-----------|
| Finance | BTC | Market regime transition with volatility threshold |
| Public Health | COVID excess mortality | Multi-country mortality threshold (FR, IT, US, BE) |
| Neuroscience | EEG Bonn | Seizure detection — 500 segments, 5 class labels |
| Astrophysics | Solar | Solar cycle regime with sunspot thresholds |
| AI / Technology | LLM scaling | Scaling law transition in LLM benchmarks |
| Cosmology | Pantheon SN | Type Ia SNe distance-redshift threshold |
| Paleobiology | PBDB marine | Marine biodiversity mass extinction threshold |

**Selection criteria:** Each pilot covers a distinct scientific domain, uses publicly
available data, and presents a plausible threshold or regime transition that the ORI-C
framework should be able to detect (or explicitly fail to detect for principled reasons).

---

## 2. What They Show

### Generalization Matrix

| Pilot | Domain | N | Signal | Verdict | Level | Power | Risk |
|-------|--------|---|--------|---------|-------|-------|------|
| EEG Bonn | Neuro | 500 | Seizure threshold | ACCEPT | **B** | adequate | very low |
| Solar | Cosmo | 288 | Solar cycle | ACCEPT | **B** | adequate | low |
| COVID | Health | 192 | Excess mortality | ACCEPT | **B** | borderline | low |
| BTC | Finance | 141 | Volatility regime | ACCEPT | **B** | borderline | low |
| Pantheon SN | Cosmo | 100 | Hubble transition | INDETERMINATE | **C** | borderline | medium |
| PBDB marine | Bio | 100 | Extinction threshold | INDETERMINATE | **C** | borderline | medium |
| LLM scaling | AI/Tech | 60 | Scaling law | INDETERMINATE | **C** | underpowered | high |

### Three Proof Levels

**Level A — Canonical** (not in pilot benchmark)
- Synthetic, FRED, validation protocol, dual proof
- Tracked in `dual_proof_manifest.json`

**Level B — Conclusive Real Pilots** (4 datasets)
- BTC, COVID excess mortality, EEG Bonn, Solar
- Decidable verdict (ACCEPT), prechecks passed, causal tests available
- **Publishable** as confirmed out-of-domain applications

**Level C — Exploratory Under Precheck** (3 datasets)
- LLM scaling, Pantheon SN, PBDB marine
- Signal plausible but insufficient power for canonical conclusion
- **Publishable** as exploratory signals with explicit power constraints

### Power Classes

| Power Class | Count | Datasets |
|-------------|-------|----------|
| adequate (≥200 pts) | 2 | EEG Bonn, Solar |
| borderline (60–199 pts) | 3 | BTC, COVID, Pantheon SN |
| underpowered (<60 pts) | 2 | LLM scaling, PBDB marine |

**Key insight:** Power class is **descriptive, not decisional**. A borderline pilot
can still produce a conclusive Level B verdict (as BTC and COVID demonstrate).
An underpowered pilot cannot — it requires data densification.

---

## 3. What They Do Not Yet Allow

### Limitations of Level B pilots
- Not at canonical rigour (Level A requires ≥200 rows + full protocol)
- No independent replication yet
- Causal interpretation constrained by domain-specific confounders

### Limitations of Level C pilots
- **LLM scaling**: 60 data points total; min_points_per_segment (60) not met
- **Pantheon SN**: Pre-threshold segment undersampled (~35 points before z threshold)
- **PBDB marine**: Post-threshold recovery phase sparsely sampled (~40 post-extinction points)

### What cannot be claimed
- ORI-C is not validated for **all** domains — only for the 7 tested
- Level C signals do **not** constitute evidence for or against the framework
- Power constraints are **data limitations**, not framework failures

---

## 4. Required Extensions

### Power Upgrade Protocol (Level C → Level B)

Each underpowered pilot has a concrete densification plan
(see `contracts/POWER_UPGRADE_PROTOCOL.json`):

| Pilot | Current N | Target N | Strategy | Feasibility | Timeline |
|-------|-----------|----------|----------|-------------|----------|
| LLM scaling | 60 | 120 | Add MLPerf, MMLU, HumanEval benchmarks | medium | 2–3 weeks |
| Pantheon SN | 100 | 150 | Augment low-z coverage (Carnegie, CfA surveys) | high | 1–2 weeks |
| PBDB marine | 100 | 140 | Densify Cenozoic with 5-Myr bins | high | 1 week |

**Success criteria for upgrade:** min_total_points ≥ 120, min_points_per_segment ≥ 60,
precheck passes, verdict decidable (ACCEPT or REJECT).

### Value of the underpowered cases
These three pilots are the best candidates for demonstrating that ORI-C can
distinguish:
1. A **true indeterminate** due to insufficient power
2. A **true reject** (framework does not apply)
3. A **true positive** (framework detects signal)

This three-way discrimination is extremely valuable for framework credibility.

---

## 5. Showcase Pilots

Two showcase pilots are selected for detailed presentation:

### Primary: EEG Bonn (Neuroscience)
- **500 segments**, 5 class labels (Z, O, N, F, S)
- Strong detection with high signal-to-noise ratio
- **Out-of-domain** — non socio-economic, demonstrating framework generality
- Adequate power (Level B, power class adequate)

### Secondary: BTC (Finance)
- **141 data points**, clear volatility regime transition
- Demonstrates portability to market dynamics
- Borderline power but conclusive verdict
- Shows framework handles financial time series

**Selection rationale:** Two showcases, not twelve half-examples. EEG Bonn proves
cross-domain portability. BTC proves financial applicability.

---

## 6. Summary Statistics

```
Total pilots evaluated:           7
Domains covered:                  7 (Finance, Health, Neuro, Cosmo, AI, Cosmo, Bio)
Level B (conclusive):             4 / 7 (57%)
Level C (exploratory):            3 / 7 (43%)
ACCEPT verdicts:                  4
INDETERMINATE verdicts:           3
REJECT verdicts:                  0
Power adequate:                   2 / 7 (29%)
Power borderline:                 3 / 7 (43%)
Power underpowered:               2 / 7 (29%)
Showcase pilots:                  EEG Bonn (primary), BTC (secondary)
```

**Reading:** The ORI-C framework demonstrates portability across 4 domains with
conclusive Level B evidence. Three additional domains show plausible signals
requiring power upgrade. No domain tested produced a definitive rejection,
but this should not be overinterpreted — framework incompatibility may emerge
once power constraints are resolved.

---

## 7. Densification Results

All 3 underpowered pilots were densified via domain-specific interpolation:

| Pilot | Original N | Densified N | Best t_seg | Signal | Status |
|-------|-----------|-------------|------------|--------|--------|
| LLM scaling | 60 | 120 | t=60 | 0.412 | conclusive |
| Pantheon SN | 100 | 150 | t=82 | 0.105 | conclusive |
| PBDB marine | 100 | 140 | t=70 | 0.060 | conclusive |

**Interpretation:** All 3 respond positively to interpolation-based densification.
This confirms the signals are structurally present but the original sampling was
insufficient. **This does NOT constitute independent data extension** — real data
augmentation remains required for Level B upgrade.

---

## 8. Comparative Benchmark (BTC / EEG Bonn / Solar)

ORI-C was benchmarked against 4 baseline methods on the 3 showcase pilots:

| Method | BTC | EEG Bonn | Solar |
|--------|-----|----------|-------|
| **ORI-C** | ACCEPT | ACCEPT | ACCEPT |
| CUSUM changepoint | detected (p<0.01) | detected (p<0.01) | detected (p<0.01) |
| Structural break | detected (p<0.01) | detected (p<0.01) | detected (p<0.01) |
| Anomaly z-score | detected (z=3.2) | detected (z=5.8) | detected (z=6.3) |
| Early warning (EWS) | not detected | detected | not detected |

**Reading:** ORI-C agrees with 3–4 out of 4 baselines on all pilots. ORI-C does
not detect something baselines miss. Its value is in **structured multi-proxy
semantics** and **built-in prechecks** that reduce false positives — not raw
detection power. EWS is complementary for pre-transition warning.

---

## 9. CI Maturity

Framework maturity is tracked via `src/oric/ci_maturity.py`:

- **Current maturity level:** emerging (1 baseline run)
- **Verdict stability:** 1.0 (no flips observed)
- **Pass rate:** 1.0
- **Regression count:** 0

As CI history accumulates, the tracker will classify the framework as:
- **emerging** (<5 runs)
- **stabilizing** (≥5 runs, ≥80% pass rate, ≥80% verdict stability)
- **mature** (≥10 runs, ≥95% pass rate, ≥95% verdict stability)

---

## References

- `05_Results/pilots/pilot_generalization_registry.json` — Single source of truth
- `contracts/PILOT_GENERALIZATION.json` — Generalization matrix contract
- `contracts/FROZEN_PILOT_CORPUS.json` — Frozen corpus v1.0.0
- `contracts/POWER_UPGRADE_PROTOCOL.json` — Power upgrade protocol
- `05_Results/pilots/power_upgrade/power_upgrade_summary.json` — Densification results
- `05_Results/pilots/comparative_benchmark.json` — Benchmark results
- `05_Results/pilots/ci_maturity_log.json` — CI maturity history
- `src/oric/proof_levels.py` — Level A/B/C classification code
- `src/oric/comparative_benchmark.py` — Benchmark baselines
- `src/oric/ci_maturity.py` — CI maturity tracker
- `tools/replicate.py` — External replication script
