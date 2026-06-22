# External replication bundle (Docker / Zenodo)

This page is for an **independent third party** who wants to rebuild the ORI-C
verdicts from scratch, offline, and check them against frozen expectations.

There are three layers, from quickest to most rigorous.

## 1. One command (Docker — fully pinned)

```bash
docker build -t oric:latest .
docker run --rm -v "$(pwd)/replication_output:/app/replication_output" \
  oric:latest bash scripts/run_replication.sh
```

The image is `python:3.12-slim` (the only supported interpreter — see
[`PYTHON_POLICY.md`](PYTHON_POLICY.md)) and every `pip install` is bounded by
[`../constraints.txt`](../constraints.txt) via `PIP_CONSTRAINT`, so the build is
reproducible rather than "whatever PyPI shipped today".

`scripts/run_replication.sh` runs the **smoke tier**: repo health → canonical
synthetic suite → strong-negatives battery → accumulation control, and writes
`replication_output/REPLICATION_SUMMARY.json`.

## 2. The Zenodo bundle (self-contained, offline)

To produce the archive that is uploaded to Zenodo (or to verify one you
downloaded):

```bash
python scripts/make_replication_bundle.py            # → dist/oric_replication_bundle_v1.3.0.zip
```

The bundle contains the code, the frozen `contracts/`, the pre-registrations
(`02_Protocol/PREREG_*`), `constraints.txt`, the `Dockerfile`, the driver, the
small frozen FRED input, and the interpretation docs — plus a
`BUNDLE_MANIFEST.json` with a **sha256 for every file** and a top-level `RUN.md`.
It deliberately excludes `05_Results/`, data bundles, large PDFs and git history,
so it is small and itself reproducible. Zenodo metadata lives in
[`../.zenodo.json`](../.zenodo.json); citation in [`../CITATION.cff`](../CITATION.cff).

## 3. Full (non-fast) replication

```bash
make test                                            # full + scientific test tiers
python 04_Code/pipeline/run_strong_negatives.py    --outdir out/strong_negatives    --n-surrogates 200
python 04_Code/pipeline/run_accumulation_control.py --outdir out/accumulation_control --n-surrogates 200
python 04_Code/pipeline/run_oos_prediction.py       --outdir out/oos --n-replicates 50 --lead 60
python tools/replicate.py --outdir out/full
```

## What you should see (frozen expectations)

| Check | Expected token | Meaning |
|---|---|---|
| Strong-negatives battery | `STRONG_NEGATIVES_CLEAN` | localized gate fires on 0/11 adversarial negatives; bare gate leaks on ~50 % |
| Accumulation control | `separates = true` | smooth accumulation rejected, bifurcation flagged |
| Canonical smoke | `smoke_ci_accept` | code path verified; **not** a statistical claim |
| Headline real-data status | **NOT_CONFIRMED** | Test B (surrogate null) fails on the real pilots |

The headline being a **negative** is the point: ORI-C is a *built, falsifiable
machine* that has cleared the synthetic mechanism rungs but is not confirmed on
real data. Read [`EVIDENCE_LADDER.md`](EVIDENCE_LADDER.md) for the full rung-by-rung
interpretation, and [`EVIDENTIARY_STATUS.md`](EVIDENTIARY_STATUS.md) for the live
detail.

## Integrity

Every file in the bundle is hashed in `BUNDLE_MANIFEST.json`. To re-verify a file
against the bundle manifest:

```bash
python - <<'PY'
import json, hashlib
m = json.load(open("BUNDLE_MANIFEST.json"))
print(m["n_files"], "files,", "version", m["version"])
PY
```
