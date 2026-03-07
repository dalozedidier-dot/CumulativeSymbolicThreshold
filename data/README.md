# data/ — Operational datasets and bundles

This directory contains **operational** datasets: bundles, extracted caches, and
sector-specific working files used during development and exploratory analysis.

**For canonical reference data, see [`03_Data/`](../03_Data/README.md).**

| Subdirectory | Content |
|-------------|---------|
| `bundles/` | Downloaded data bundles |
| `bundles_extracted/` | Extracted bundle contents |
| `climate/` | Climate sector working data |
| `finance/` | Finance sector working data |
| `qcc/` | QCC (quantum contextual computing) variant data |
| `survey/` | Survey data |
| `real_datasets_index.csv` | Index of available real datasets |

## Relationship to 03_Data/

- `03_Data/` = **canonical** reference datasets with proxy_spec.json and SHA-256 hashes
- `data/` = **operational** working files, bundles, and caches

See [docs/REPO_LAYOUT.md](../docs/REPO_LAYOUT.md) for the full layout rationale.
