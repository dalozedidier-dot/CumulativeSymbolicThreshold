# ORI-C — Cumulative Symbolic Threshold

**A pre-registered, falsifiable scientific framework** for testing whether,
beyond a critical threshold of symbolic accumulation, the symbolic transmission
channel becomes self-reinforcing — a measurable phase transition.

[![DOI](https://img.shields.io/badge/DOI-10.17605%2FOSF.IO%2FG62PZ-blue)](https://doi.org/10.17605/OSF.IO/G62PZ)

---

## What is ORI-C?

ORI-C (Onde de Recurrence Informationnelle — Cumulative) is a detection
framework that identifies **symbolic phase transitions** in time series.
It uses pre-registered parameters, frozen ex ante, with no post-hoc tuning.

The framework answers one question: *does this series exhibit a cumulative
symbolic threshold crossing?* The answer is a decidable verdict —
**ACCEPT**, **REJECT**, or **INDETERMINATE** — with full statistical support.

---

## Validation Status: VALIDATED

| Dimension | Status | Key metric |
|-----------|--------|------------|
| Synthetic validation | **ACCEPT** | Sensitivity 1.0, Specificity 1.0, Fisher p < 10⁻⁴⁰ |
| Real-data canonical (FRED) | **ACCEPT** | Full protocol (C1 + C2 + C3) |
| Validation protocol | **ACCEPT** | 150 runs, 0 indeterminate |
| Dual proof | **COMPLETE** | Synthetic + Real aligned |
| Replication | **REPLICATED** | 3 batches, 270 runs, identical verdicts |

[Full proof architecture](canonical_proof.md){ .md-button }

---

## Evidence Hierarchy

### Level A — Canonical Core

The reference lot. Synthetic simulation + FRED monthly economic data +
three-arm validation protocol + dual proof manifest. This is the
**falsifiable anchor** of the framework.

- Sensitivity >= 0.80, Specificity >= 0.80, Fisher p < 0.01
- 25 frozen parameters, no post-hoc tuning
- [Canonical Proof](canonical_proof.md) | [Validation Report](VALIDATION_CANONICAL_REPORT.md)

### Level B — Conclusive Pilots (4 datasets)

Real-world datasets **outside the canonical core** with decidable verdicts.
These are publishable as confirmed out-of-domain applications.

| Pilot | Domain | N | Verdict | Power |
|-------|--------|---|---------|-------|
| EEG Bonn | Neuroscience | 500 | **ACCEPT** | adequate |
| Solar | Astrophysics | 288 | **ACCEPT** | adequate |
| COVID mortality | Public health | 192 | **ACCEPT** | borderline |
| BTC | Finance | 141 | **ACCEPT** | borderline |

### Level C — Exploratory Pilots (3 datasets)

Plausible signals but **insufficient statistical power** for a canonical
conclusion. Published with explicit constraints, never cited as evidence.

| Pilot | Domain | N | Verdict | Blocking constraint |
|-------|--------|---|---------|---------------------|
| Pantheon SN | Cosmology | 100 | INDETERMINATE | Pre-threshold undersampled |
| PBDB marine | Paleobiology | 100 | INDETERMINATE | Post-extinction sparse |
| LLM scaling | AI/Tech | 60 | INDETERMINATE | Series too short |

Each has a concrete densification plan: [Power Upgrade Protocol](limitations_power.md#power-upgrade-protocol)

[Full generalization benchmark](generalization_pilots.md){ .md-button }
[Limitations and power](limitations_power.md){ .md-button }

---

## Replicate

Three entry points, from fastest to most thorough:

| What | Command | Time |
|------|---------|------|
| Smoke test | `make smoke` | ~2 min |
| Full canonical suite (T1-T8) | `make canonical` | ~15 min |
| Full replication (3 batches, 270 runs) | See [Replication Protocol](REPLICATION_PROTOCOL.md) | ~1 h |

All seeds, manifests, and checksums are frozen:

- [Installation](installation.md) — pip, conda, Docker
- [Reproduction Guide](REPRODUCE.md) — seeds, manifests, full reproducibility
- [CI Pipelines](CI_PIPELINES.md) — automated nightly + collector

---

## Repository Structure

| Layer | Content |
|-------|---------|
| `contracts/` | Frozen parameters, pilot corpus, validation gates |
| `src/` | Core ORI-C engine (ori_core, symbolic, decision) |
| `04_Code/pipeline/` | Validation and pilot pipelines |
| `04_Code/tests/` | 351 tests (17 files) |
| `05_Results/` | All canonical outputs with SHA-256 manifests |
| `docs/` | This documentation site |

[Full layout](REPO_LAYOUT.md) | [Point of Truth](ORI_C_POINT_OF_TRUTH.md)

---

## API Reference

| Module | Description |
|--------|-------------|
| [ori_core](api/ori_core.md) | Cap(t), Sigma(t), V(t) computations |
| [symbolic](api/symbolic.md) | S(t), C(t), threshold detection |
| [decision](api/decision.md) | NaN-safe hierarchical verdict engine |
| [proxy_spec](api/proxy_spec.md) | Versioned, hashable column mapping |
| [prereg](api/prereg.md) | Frozen ex-ante parameter spec |
| [randomization](api/randomization.md) | Seed management |

---

## Links

- [GitHub Repository](https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold)
- [OSF Pre-registration](https://osf.io/g62pz/)
- [DOI: 10.17605/OSF.IO/G62PZ](https://doi.org/10.17605/OSF.IO/G62PZ)
