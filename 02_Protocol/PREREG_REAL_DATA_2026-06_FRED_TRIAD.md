# Pre-registration — real-data A/B/C block (FRED monthly, 2008 GFC)

**Status:** FROZEN ex ante · **Freeze date:** 2026-06-22 · **Applies to:** ORI-C v1.3+
**Machine-readable twin:** [`contracts/REAL_DATA_REGISTRATION.json`](../contracts/REAL_DATA_REGISTRATION.json)
**Runner:** `04_Code/pipeline/run_registered_block.py` · **Ladder:** rungs 5–6 of [`docs/EVIDENCE_LADDER.md`](../docs/EVIDENCE_LADDER.md)

This is the *one real rung* the project needs to move from **indicative /
exploratory** toward **strongly supported on real data**: a complete real-data
block whose every choice is frozen **before** the outcome is read.

## Why FRED, and why this is the honest choice

FRED monthly is the **hard case**. Exploratory analysis already shows it is
`ROBUST_NEGATIVE` (0/27 multiverse specifications fire) with an IAAFT surrogate
`p = 1.0`. Registering it — rather than a series where ORI-C happens to look good
— is the **anti-cherry-pick** decision. The deliverable is the *frozen apparatus
and rule*, not a manufactured positive. A `REAL_BLOCK_REJECTED` verdict is
reported at equal status to a confirmation.

## The block (all frozen here)

| Condition | What | Expectation |
|---|---|---|
| **A — test** | `03_Data/real/fred_monthly/real.csv` (1986-01…2025-12) | a localized transition in the dated window |
| **B — stable** | pre-onset segment of A (`t < t1`) **+** independent `ecology_pelt` | **no** detection |
| **C — placebo** | cyclic shift of A by `N // 3` (autocorrelation kept, onset alignment broken) | **no** detection |

### Dated hypothesis (frozen)

> A localized regime transition is expected in **t ∈ [272, 281]** =
> **2008-09 → 2009-06** (the Global Financial Crisis), with `t* = 272` (2008-09).

This window and `t*` are fixed before the detector is run; they are not moved to
fit the result.

### Frozen everything-else

| Item | Frozen value |
|---|---|
| proxy / column mapping | `t, O, R, I, demand, S` (fixed by the dataset) |
| normalization | `robust`, control mode `no_symbolic` |
| detector | `k = 2.5`, `m = 3`, `baseline_n = 50`, `α = 0.01`, gate = localized transition |
| classical benchmarks | CUSUM, PELT (AMOC, dependency-free), EWS (variance+AR1), structural break |
| surrogate null | IAAFT, statistic = crossing rate, `n = 200`, confirm iff `p < 0.01` |
| OOS | train `t < t*`, test `t ≥ t*`; localized CSD predictor; skill = pre-`t*` directional call |
| aggregation | see below |
| seed | `1234` |

### Aggregation rule (frozen)

> **`REAL_BLOCK_CONFIRMED`** iff **all** hold:
> 1. A fires a localized transition **inside** `[t1, t2] ± 18`;
> 2. B (stable + external) is silent;
> 3. C (placebo) is silent;
> 4. the IAAFT surrogate `p < 0.01`;
> 5. the pre-`t*` OOS shows directional skill.
>
> Otherwise **`REAL_BLOCK_REJECTED`**. **`REAL_BLOCK_INDETERMINATE`** if undecidable.

Robustness/sensitivity alone never confirms: ORI-C must be **both** sensitive on
A **and** specific on B/C **and** beat the surrogate null **and** hold out of
sample. Beating or complementing the classical panel is recorded
(`classical_false_positives_on_controls`) as supporting evidence, not as a gate.

## Reproduce (≈ 3–8 min)

```bash
make real-registered            # or:
python 04_Code/pipeline/run_registered_block.py --outdir 05_Results/registered_block --fast
```

## Outcome on this freeze (exploratory record)

The committed apparatus yields **`REAL_BLOCK_REJECTED`** on FRED: ORI-C does **not**
fire on A (crossing rate 0.0), the surrogate `p = 1.0`, and there is no OOS skill —
*yet* ORI-C stays **silent on B and C while the classical panel false-fires 8×* on
the controls. The honest one-line reading: on FRED, ORI-C is **specific but
insensitive**, the classical baselines are **sensitive but non-specific**. Neither
is a confirmed transition. To climb the rung, this same frozen block must return
`REAL_BLOCK_CONFIRMED` on a genuinely transitioning real series.

## Parameters held fixed

`k = 2.5`, `m = 3`, `baseline_n = 50`, `α = 0.01`, IAAFT `n = 200`, `seed = 1234`,
window `[272, 281]`, `t* = 272`. Any change requires a **new dated
pre-registration**; this file is append-only by supersession.
