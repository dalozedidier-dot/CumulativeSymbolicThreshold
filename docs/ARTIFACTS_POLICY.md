# Artifacts policy — frozen reference vs regenerable artifact

**Status:** FROZEN policy · **Last reviewed:** 2026-06-22

Every file in this repository is exactly one of two kinds. Confusing them is how
a repo bloats, drifts, and starts contradicting its own `.gitignore`.

| | **Frozen reference** | **Regenerable artifact** |
|---|---|---|
| Definition | An input or contract the science depends on. Changing it changes results. | An *output* produced by running the code on the frozen reference. |
| Versioned? | **Yes** — committed, integrity-checked. | **No** — `.gitignore`d; reproduced on demand. |
| Integrity | sha256 in a manifest / contract; CI verifies. | None needed — it is a function of the frozen inputs. |
| If it changes | Requires review + a new freeze / pre-registration. | Just re-run the producer. |

## Frozen reference (committed, hashed, reviewed)

| Path | What | Integrity check |
|---|---|---|
| `contracts/*.json` | Frozen criteria, gates, pre-registrations | `tools/repo_doctor`, dedicated tests |
| `data/bundles/*.zip` | Source data bundles | `data_pack_manifest.json` |
| `data/climate`, `data/finance`, `data/qcc`, `data/survey` | Small reference series | `data_pack_manifest.json` |
| `data_pack_manifest.json` | The integrity record itself | `tools/verify_data_pack`, `--check` builder |
| `03_Data/real/_bundles/` | Pinned real-data bundles | `scripts/check_bundle_integrity.py` + `bundle_hashes.json` |
| `02_Protocol/PREREG_*`, `contracts/*PREREG*`, `FROZEN_PARAMS.json` | Pre-registered protocols / params | consistency tests |
| Source code (`src/`, `04_Code/`, `tools/`, `scripts/`) | The producers | tests, ruff, mypy |

The data-pack manifest pins the **source zips**, not their extracted contents:
hashing the zip already pins every member, and the extraction is deterministic.

## Regenerable artifact (gitignored, reproduced on demand)

| Path | Reproduce with |
|---|---|
| `05_Results/` (figures, bulk validation runs) | the `04_Code/pipeline/run_*` producers (each takes `--outdir 05_Results/...`) |
| `data/bundles_extracted/` | `python -m tools.extract_bundles` (members of `data/bundles/*.zip`) |
| `_ci_out/`, `runs/`, `replication_output/`, `dist/` | the CI workflows / `scripts/run_replication.sh` / `make bundle` |
| `*.png` figures under `05_Results/` | the reporting/plotting steps of each pipeline |
| caches (`__pycache__/`, `.pytest_cache/`, `.mplconfig/`, …) | the toolchain |

### Known exception (debt, flagged): `data/bundles_extracted/`

These 234 files are *regenerable* (every one is a member of a committed zip, see
`python -m tools.extract_bundles --verify`) yet they are **currently force-tracked**.
The reason is pragmatic: `data/real_datasets_index.csv` points three
`smoke_candidate` datasets directly at extracted paths, so `make smoke` needs the
tree present on a fresh checkout. The clean fix (point the index at the zips and
extract in CI, then untrack the tree) is left as a follow-up; until then this is
documented here so the contradiction with `.gitignore` is explicit, not silent.

## Rules

1. **Never commit a regenerable artifact** unless it is documented as a flagged
   exception above. `05_Results/` and `data/bundles_extracted/` are `.gitignore`d;
   do not `git add -f` new outputs into them.
2. **Never hand-edit a frozen reference** to match an observed result. Frozen
   means frozen; change it through review + a new freeze.
3. **The manifest is the source of truth for data integrity.** After adding or
   changing a frozen reference file, run `make data-pack-build` and commit; CI
   (`make data-pack-check`) fails if the manifest is stale or a tracked frozen
   file is unlisted.
4. **Reproduce, don't archive.** To inspect a result, re-run its producer into a
   gitignored output dir rather than committing the output.

See also: [`EVIDENCE_LADDER.md`](EVIDENCE_LADDER.md) (what the results mean),
`REPO_LAYOUT.md` (where things live), and `../.gitignore` (the enforcement).
