# Canonical Proof

**Status:** COMPLETE
**Date:** 2026-03-09

---

## Architecture

The ORI-C canonical proof rests on four blocs:

### Bloc 1: Contractual Proof
- Dual proof manifest complete
- Final status schema v2 validated
- All integrity checks pass
- Unique schema enforcement

### Bloc 2: Discriminant Proof
- **Confusion matrix:** TP=50, FN=0, FP=0, TN=100
- **Sensitivity:** 1.0000 [0.8828, 1.0000] (99% CI)
- **Specificity:** 1.0000 [0.9378, 1.0000] (99% CI)
- **Fisher exact p:** 4.97 × 10⁻⁴¹
- **Indeterminate rate:** 0.00 per condition
- Three-condition design: test / stable / placebo

### Bloc 3: Robustness Proof
- Window stability: 5-7 variants tested, no verdict flip
- Subsample stability: 30 random 80% subsamples
- No opportunistic parameter tuning

### Bloc 4: External Proof
- **Replication:** 3 independent batches (seed_base: 100k, 150k, 200k)
- **Result:** REPLICATED (3/3 ACCEPT, 270 total runs)
- No retuning between batches

---

## Frozen Parameters

25 parameters frozen ex ante in `contracts/FROZEN_PARAMS.json`:

| Parameter | Value | Role |
|-----------|-------|------|
| alpha | 0.01 | Significance level |
| sesoi_c_robust_sd | 0.3 | Smallest effect of interest |
| ci_level | 0.99 | Confidence interval level |
| n_replicates | 50 | Runs per condition |
| seed_base | 7000 | Reproducibility anchor |

Full list: `contracts/FROZEN_PARAMS.json`

---

## Validation Protocol

Three-condition, three-dataset design:

1. **Test condition:** Full dataset with known transition → expects detection
2. **Stable condition:** Pre-transition segment only → expects non-detection
3. **Placebo condition:** Cyclic shift (no real transition) → expects non-detection

Hard conditions:
- C1: Test detection rate ≥ 80%
- C2: Stable false positive rate ≤ 20%
- C3: Placebo false positive rate ≤ 20%

---

## Links

- [Framework Status](framework_status.md)
- [Generalization Pilots](generalization_pilots.md)
- Full report: `docs/VALIDATION_CANONICAL_REPORT.md`
- Results: `05_Results/scientific_validation/`
