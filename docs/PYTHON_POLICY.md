# Python policy — **3.12 only**

**Status:** FROZEN · **Applies to:** ORI-C v1.3+ · **Last reviewed:** 2026-06-22

ORI-C targets **exactly one** Python interpreter: **CPython 3.12**.

This is a deliberate reproducibility choice. A single, pinned interpreter means
every CI job, the Docker image, the conda environment and the replication bundle
run the *same* bytecode, the same NumPy/SciPy ABI and the same RNG/stats behaviour.
Scientific verdicts therefore do not depend on which interpreter happened to run
the suite.

## What "3.12 only" means

| Surface | Setting | Source of truth |
|---|---|---|
| Package metadata | `requires-python = ">=3.12,<3.13"` | `pyproject.toml` |
| Trove classifiers | `Programming Language :: Python :: 3.12 :: Only` | `pyproject.toml` |
| Lint target | `target-version = "py312"` | `pyproject.toml` `[tool.ruff]` |
| Type-check target | `python_version = "3.12"` | `pyproject.toml` `[tool.mypy]` |
| CI unit tests | `matrix.python-version: ["3.12"]` | `.github/workflows/ci_smoke.yml` |
| CI lint / compile / canonical | `python-version: "3.12"` | `.github/workflows/ci_smoke.yml` |
| Nightly | `python-version: "3.12"` | `.github/workflows/nightly_full_proof.yml` |
| QCC / collector / sector pilots | `python-version: "3.12"` | `.github/workflows/*.yml` |
| Container | `FROM python:3.12-slim` | `Dockerfile` |
| Conda | `python=3.12` | `environment.yml` |

## Rationale (why not 3.10–3.13)

- **No untested claims.** Previously the classifiers advertised 3.10, 3.11, 3.12
  and 3.13, but CI only exercised 3.10–3.12 and *never* 3.13. A policy that
  advertises a version it does not test is a reproducibility liability.
- **One ABI.** The scientific stack (NumPy ≥ 1.26, SciPy ≥ 1.11, statsmodels
  ≥ 0.14) ships compiled wheels per minor version. Pinning 3.12 removes a whole
  axis of "works on my machine".
- **Lowest maintenance.** ruff, mypy, the Docker image and the conda env were
  already on 3.12; collapsing the test matrix to match is the smallest, most
  honest configuration.

## Changing the policy

Bumping to a new interpreter (e.g. 3.13) is a single, reviewable change set:

1. `pyproject.toml` — `requires-python`, classifiers, `[tool.ruff] target-version`,
   `[tool.mypy] python_version`.
2. Every file under `.github/workflows/` — all `python-version:` keys and the
   `unit_tests` matrix.
3. `Dockerfile` — base image tag.
4. `environment.yml` — `python=` pin.
5. This document's table and the README badge.

A green CI run on the new version (lint + mypy + the full unit + canonical
suites) is the acceptance gate. Do **not** widen the matrix to several minor
versions: pick the next single canonical interpreter and move the whole repo to
it atomically.
