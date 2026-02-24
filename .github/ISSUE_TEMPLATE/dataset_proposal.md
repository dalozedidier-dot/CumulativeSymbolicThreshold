---
name: Dataset Proposal
about: Propose a new real-data pilot sector for ORI-C testing
title: "[DATASET] <sector> — <brief description>"
labels: dataset-proposal, good-first-issue
assignees: ''
---

## Dataset summary

**Sector / domain:**
(e.g., health systems, social media, climate, cognitive load, transport)

**Geographic/organisational scope:**
(e.g., EU27 monthly, FR annual, single organisation)

**Temporal resolution and range:**
(e.g., monthly, 2000–2023, 276 observations)

**Data availability:**
- [ ] Publicly available (link: )
- [ ] Proprietary / restricted (describe access)
- [ ] Synthetic / simulated

---

## Proposed proxy mapping

For each ORI-C variable, describe the proposed proxy and justify its direction.

| ORI-C var | `source_column` | Direction | Normalization | Justification |
|-----------|----------------|-----------|---------------|---------------|
| O(t) | | positive/negative | robust_minmax / minmax / none | |
| R(t) | | | | |
| I(t) | | | | |
| demand | | | | (optional) |
| S(t) | | | | (optional) |

---

## Proxy spec draft (JSON)

Paste a draft `proxy_spec.json` here (or attach as a file):

```json
{
  "dataset_id": "",
  "sector": "",
  "spec_version": "1.0",
  "time_column": "t",
  "time_mode": "index",
  "columns": []
}
```

Validate your draft locally:
```bash
python 04_Code/pipeline/validate_proxy_spec.py --spec proxy_spec.json --csv real.csv
```

---

## Caveats

**Fragility notes** (e.g., proxy depends on reporting changes, structural breaks):

**Manipulability notes** (e.g., proxy could be administratively influenced):

**Known limitations:**

---

## Checklist

- [ ] At least 50 observations
- [ ] O, R, I proxies available and justifiable (independent, non-circular)
- [ ] Normalisation to [0, 1] feasible
- [ ] `proxy_spec.json` draft included above
- [ ] `validate_proxy_spec.py` passes on the draft spec + CSV
