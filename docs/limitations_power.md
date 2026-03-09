# Limitations and Power

---

## What ORI-C Cannot Claim

1. **Not validated for all domains.** Only 7 domains tested. Framework
   incompatibility may emerge in untested domains.

2. **Level C signals are not evidence.** Three pilots (LLM, Pantheon, PBDB)
   show plausible signals but lack contractual power. Their INDETERMINATE
   verdicts must not be cited as support.

3. **No independent external replication yet.** All validation was performed
   by the framework authors. External replication is the next critical step.

4. **Power constraints are real.** The `min_points_per_segment >= 60`
   requirement blocks many real-world datasets. This is by design (avoids
   underpowered conclusions) but limits applicability.

---

## Power Constraints

### Thresholds

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `MIN_ROWS_CANONICAL` | 200 | Full bootstrap + stability battery |
| `MIN_ROWS_CONCLUSIVE` | 60 | Minimum for decidable verdict |
| `MIN_POINTS_PER_SEGMENT` | 60 | Required per pre/post segment |

### Impact on Pilots

| Pilot | Blocking constraint | Impact |
|-------|---------------------|--------|
| LLM scaling | 60 total pts, ~30/segment | Cannot reach min_points_per_segment |
| Pantheon SN | ~35 pre-threshold pts | Pre-threshold segment undersampled |
| PBDB marine | ~40 post-threshold pts | Post-extinction recovery sparse |

---

## Power Upgrade Protocol

Each underpowered pilot has a concrete densification plan in
`contracts/POWER_UPGRADE_PROTOCOL.json`:

| Pilot | Current | Target | Strategy |
|-------|---------|--------|----------|
| LLM scaling | 60 | 120 | Add MLPerf, MMLU benchmarks |
| Pantheon SN | 100 | 150 | Augment low-z (Carnegie, CfA) |
| PBDB marine | 100 | 140 | Densify Cenozoic bins |

### Success criteria for upgrade
- `min_total_points >= 120`
- `min_points_per_segment >= 60`
- Prechecks pass
- Verdict decidable (ACCEPT or REJECT)

### Expected outcomes
These three pilots are the best candidates for demonstrating ORI-C's ability
to distinguish:
1. A **true indeterminate** (insufficient power)
2. A **true reject** (framework does not apply)
3. A **true positive** (framework detects signal)

---

## Overinterpretation Risks

| Risk level | Meaning | Pilots |
|------------|---------|--------|
| very_low | Strong evidence, adequate power | EEG Bonn |
| low | Decidable verdict, borderline power | BTC, COVID, Solar |
| medium | Plausible signal, precheck marginal | Pantheon SN, PBDB marine |
| high | Underpowered, cannot conclude | LLM scaling |

### Mitigation
- Level separation (A/B/C) prevents mixing evidence strengths
- Power class labeling makes limitations visible
- Frozen corpus versioning prevents post-hoc reclassification

---

## Links

- [Framework Status](framework_status.md)
- [Generalization Pilots](generalization_pilots.md)
- [Replication Protocol](REPLICATION_PROTOCOL.md)
- Power criteria: `contracts/POWER_CRITERIA.json`
