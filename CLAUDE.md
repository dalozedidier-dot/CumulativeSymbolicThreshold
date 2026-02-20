# CLAUDE.md — AI Assistant Guide for CumulativeSymbolicThreshold

This file describes the codebase structure, development conventions, and workflows for the **Cumulative Symbolic Threshold (ORI-C)** project. It is the primary reference for AI assistants working in this repository.

## Project Purpose

This is a **reproducible scientific framework** for testing the ORI-C hypothesis: the existence of a causal threshold beyond which symbolic accumulation becomes self-reinforcing (cumulative symbolic regime). The project is pre-registered (DOI: 10.17605/OSF.IO/G62PZ) and follows strict falsifiability and pre-registration conventions.

## Repository Structure

```
CumulativeSymbolicThreshold/
├── 01_Theory/              # Canonical theoretical documents
│   ├── ORI_C_Pancarte_Normative_v1_0.md   # THE normative placard (canonical reference)
│   ├── theory_core.md
│   ├── glossary_variables.md
│   └── threshold_rationale.md
├── 02_Protocol/            # Pre-registration, protocol, intervention catalog
│   ├── PROTOCOL_v1.md
│   ├── PREREG_TEMPLATE.md              # Pre-registration template (parameters fixed ex ante)
│   ├── DECISION_RULES_v1.md / v2.md   # Statistical decision rules
│   ├── INTERVENTIONS_CATALOG.md
│   └── NEURO_EXTENSION_v1.md
├── 03_Data/                # Data definitions and datasets
│   ├── data_dictionary.md
│   ├── inclusion_exclusion.md
│   ├── raw/                # Raw data (gitkeep placeholder)
│   ├── processed/          # Processed data (gitkeep placeholder)
│   ├── synthetic/          # Synthetic CSV datasets for demo/testing
│   └── real/_bundles/      # Real data bundles (LITE v1/v2)
├── 04_Code/                # All executable code
│   ├── pipeline/           # Main pipeline scripts (entry points)
│   ├── tests/              # Pytest unit tests
│   ├── configs/            # JSON config files per run
│   ├── docs/               # Code documentation
│   ├── requirements.txt    # Runtime dependencies
│   ├── requirements-dev.txt# Dev dependencies (pytest, etc.)
│   ├── environment.yml     # Conda environment
│   └── seeds_and_repro.md  # Reproducibility guide
├── 05_Results/             # All run outputs (never committed, gitignored in CI)
├── 06_Manuscript/          # Academic manuscript
│   ├── manuscript.md
│   └── appendix_methods.md
├── src/oric/               # Importable source package
├── scripts/                # Utility scripts
│   └── resolve_real_datasets.py
├── .github/workflows/      # CI/CD workflows
├── conftest.py             # Root pytest config (adds src/ to PYTHONPATH)
├── run_all.py              # Top-level runner alias
├── run_all_tests.py        # Top-level test runner alias
├── ORIC_POINT_OF_TRUTH.md  # Canonical repo-level normative anchors
├── ORI_C_POINT_OF_TRUTH.md # (legacy alias)
├── CONTRIBUTING.md
├── CHANGELOG.md
├── CITATION.cff
└── LICENSE                 # MIT
```

## Core Model — ORI-C Variables

All variables and functional forms are **fixed ex ante** in `02_Protocol/PREREG_TEMPLATE.md` and `01_Theory/ORI_C_Pancarte_Normative_v1_0.md`. Never adjust them post-observation.

| Variable | Symbol | Description |
|----------|--------|-------------|
| Organisation | O(t) | Structural/functional coordination proxy |
| Resilience | R(t) | Perturbation absorption capacity proxy |
| Integration | I(t) | Inter-component coherence proxy |
| Capacity | Cap(t) | `O(t) * R(t) * I(t)` — primary form (fixed ex ante) |
| Viability | V(t) | Non-compensatory aggregation over `[t-Δ, t]` |
| Mismatch | Σ(t) | `max(0, D(E(t)) - Cap(t))` |
| Symbolic stock | S(t) | Transmissible repertoire proxy |
| Order variable | C(t) | Intergenerational symbolic gain |
| External perturbation | U(t) | Demand surge, capacity loss, or symbolic cut |

**Threshold detection criterion:**
```
ΔC(t) > μ_ΔC + k·σ_ΔC  for m consecutive steps
```
Default: `k=2.5`, `m=3`, baseline estimated on first `baseline_n=30` points.

## Python Environment

- **Python**: 3.12 (required)
- **Package manager**: conda (recommended) or pip

### Setup

```bash
# Conda (recommended)
conda env create -f environment.yml
conda activate cumulative_symbolic

# pip alternative
pip install -r requirements.txt
pip install -r 04_Code/requirements-dev.txt   # for tests
```

### Runtime dependencies (`requirements.txt`)

```
numpy>=1.26
pandas>=2.0
matplotlib>=3.8
scipy>=1.11
statsmodels>=0.14
tqdm>=4.66
```

### Dev dependencies

```
pytest>=8.0
```

## Running Tests

```bash
# From repo root
PYTHONPATH=04_Code pytest -q

# Or via 04_Code prefix
PYTHONPATH=04_Code pytest 04_Code/tests/ -q
```

Test files live in `04_Code/tests/`. Root `conftest.py` adds `src/` to `sys.path`. The `04_Code/tests/conftest.py` file handles import resolution for pipeline modules.

## Key Pipeline Scripts

All pipeline scripts live in `04_Code/pipeline/` and are invoked from the repo root.

### Core simulator

```python
# 04_Code/pipeline/ori_c_pipeline.py
from pipeline.ori_c_pipeline import ORICConfig, run_oric

cfg = ORICConfig(seed=123, n_steps=200, intervention="demand_shock")
df = run_oric(cfg)  # returns a DataFrame with columns: t, O, R, I, Cap, demand, Sigma, S, V, C, delta_C, ...
```

`ORICConfig` is a **frozen dataclass** — all parameters must be set at construction time and cannot be modified.

Supported interventions: `none`, `demand_shock`, `capacity_hit`, `symbolic_cut`, `symbolic_injection`, `symbolic_cut_then_inject`.

### Main entry points

| Script | Purpose |
|--------|---------|
| `run_all_tests.py` | **Canonical suite runner** — runs T1–T8, writes `global_summary.csv` |
| `run_ori_c_demo.py` | ORI-C synthetic demo with selectable intervention |
| `run_synthetic_demo.py` | CSV-based demo (pre-threshold or transition dataset) |
| `run_robustness.py` | Robustness analysis (alternative Cap specs, window sizes, etc.) |
| `run_real_data_demo.py` | Run ORI-C on real observed CSV data |
| `tests_causaux.py` | Causal test battery on a run directory |
| `run_canonical_suite.py` | Canonical suite with verdict aggregation |
| `analyse_verdicts_canonical.py` | Aggregate local verdicts → global verdict |
| `run_symbolic_T4_s_rich_poor.py` | T4: S-rich vs S-poor on C |
| `run_symbolic_T5_injection.py` | T5: Symbolic injection effect on C |
| `run_symbolic_T7_progressive_sweep.py` | T7: Progressive S sweep → threshold |
| `run_reinjection_demo.py` | T8: Cut-then-reinjection recovery |
| `run_symbolic_suite_T4_T5_T7.py` | Combined T4/T5/T7 runner |
| `generate_synthetic_with_threshold.py` | Generate synthetic datasets |
| `plot_canonical_overview.py` | Canonical figure plotting |
| `make_sha256_manifest.py` | Data integrity manifest |

### Quick demo commands

```bash
# Synthetic demo (pre-threshold)
python 04_Code/pipeline/run_synthetic_demo.py \
  --input 03_Data/synthetic/synthetic_minimal.csv \
  --outdir 05_Results/demo

# Synthetic demo (with transition)
python 04_Code/pipeline/run_synthetic_demo.py \
  --input 03_Data/synthetic/synthetic_with_transition.csv \
  --outdir 05_Results/demo_transition

# ORI-C executable demo
python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/ori_c_demo
python 04_Code/pipeline/tests_causaux.py --outdir 05_Results/ori_c_demo

# Full canonical suite (T1–T8)
python 04_Code/pipeline/run_all_tests.py --outdir 05_Results/canonical_tests

# Robustness (secondary)
python 04_Code/pipeline/run_robustness.py \
  --input 03_Data/synthetic/synthetic_with_transition.csv \
  --outdir 05_Results/robust
```

### Real data workflow

```bash
# Step 1: Run ORI-C on real CSV
python 04_Code/pipeline/run_real_data_demo.py \
  --input 03_Data/real/pilot_cpi/real.csv \
  --outdir 05_Results/real/pilot_cpi/run_0001 \
  --col-time date --auto-scale --control-mode no_symbolic

# Step 2: Causal tests
python 04_Code/pipeline/tests_causaux.py \
  --run-dir 05_Results/real/pilot_cpi/run_0001 \
  --alpha 0.01 --lags 1-10 --pre-horizon 200 --post-horizon 200 --pdf
```

Real data CSV format: required columns `t` (or date), `O`, `R`, `I` (normalized to [0,1]); optional `demand`, `S`.

See `04_Code/pipeline/README_REAL_DATA.md` for full reference.

## Canonical Output Convention

Every executable test **must** write these files inside its `--outdir`:

```
<outdir>/
├── tables/
│   ├── summary.csv     # One-row summary with a 'verdict' column
│   └── summary.json    # JSON equivalent (optional but standard)
├── verdict.txt         # Single token: ACCEPT, REJECT, or INDETERMINATE
└── figures/            # PNG figures (recommended)
```

This convention is enforced by `ORIC_POINT_OF_TRUTH.md`.

## Decision Framework (Normative)

All decision criteria are **locked ex ante** and must not be changed post-observation.

| Parameter | Value |
|-----------|-------|
| Significance level α | **0.01** |
| Decision basis | Triplet: p-value + CI 99% + SESOI |
| Verdict tokens | `ACCEPT`, `REJECT`, `INDETERMINATE` |
| Power gate | If estimated power < 0.70 → forced `INDETERMINATE` |
| Quality gate | Failure rate < 5%; N ≥ N_min per condition |
| N_min | 50 valid runs (100 preferred for stable power) |

**SESOI defaults:**
- Cap*: +10% relative vs baseline (or +0.5 robust SD via MAD)
- V (low-quantile): -10% relative vs baseline (or -0.5 robust SD via MAD)
- C (intergenerational): +0.3 robust SD via MAD

## Causal Tests T1–T8

| Test | Manipulation | Variable | Falsification |
|------|-------------|----------|---------------|
| T1 | Vary O, R, I | Cap(t) | Decorrelation or inversion |
| T2 | Increase D(E) | Σ(t) | Σ=0 despite overload |
| T3 | Induce high Σ | V(t) | V stable despite high Σ |
| T4 | Vary S(t) | C(t) | C invariant despite ΔS |
| T5 | Inject S at t0 | C(t+T) | No delayed effect |
| T6 | Cut/reduce S | C(t) | C stable despite symbolic cut |
| T7 | Progressive S sweep | C(t) | C strictly linear (no tipping) |
| T8 | Combined U(t) | O,R,I,S,C | Relations unstable or inverted |

Minimal cumulative proof requirements:
- **T1+T2+T3**: validates ORI-Cap-Σ-V core
- **T4+T5+T7**: validates cumulative symbolic regime
- **T6**: symbolic dimension is non-trivial (not reducible to O,R,I)

## Reproducibility Requirements

- **Every run must fix a seed**. Pass `--seed` to all pipeline scripts.
- **Log seed, code version, dependency versions, and decision parameters** per run.
- Store one JSON config per run in `04_Code/configs/`.
- **No post-observation recalibration** of any parameter.
- All proxies, functional forms, weights, windows Δ and T, thresholds k and m must be fixed in `PREREG_TEMPLATE.md` before data collection.

## CI/CD Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push to `main`, PRs | Canonical suite (T1–T8 or fallback) |
| `nightly.yml` | Nightly schedule | Extended overnight tests |
| `symbolic_suite.yml` | Mondays 02:00 UTC, manual | Symbolic tests T4/T5/T7 |
| `manual_runs.yml` | Manual dispatch | On-demand runs with custom params |
| `real_data_smoke*.yml` | Various | Sector-specific real data smoke tests |
| `real_data_suite_max_demo.yml` | Manual | Full real data suite |

CI uses Python 3.12, installs from `requirements.txt` and `04_Code/requirements.txt`, then runs `run_all_tests.py` (falling back to synthetic demo if not found). Artifacts are uploaded to `_ci_out/`.

## Contributing Conventions

From `CONTRIBUTING.md`:

1. **Keep the framework falsifiable and pre-registerable.** Every addition must be testable without post-hoc adjustment.
2. **Separate decisional definitions from robustness analyses.** Robustness tests are secondary and never change the primary verdict.
3. **Avoid circularity** between V(t), S(t), and C(t) definitions.
4. **Add a minimal example** whenever introducing a new concept.
5. **Never modify parameters after observing data.** Any parameter change must be treated as a new pre-registration.

## Important Constraints for AI Assistants

- **Do not introduce circular definitions** between V, S, and C. These must remain causally independent.
- **Do not add post-hoc tuning** of any model parameter. All parameters in `ORICConfig` are fixed ex ante.
- **The core functional form `Cap = O * R * I` is normative** — only change it in a robustness variant, never in the main path.
- **All tests must produce `verdict.txt`** with a single token (`ACCEPT`, `REJECT`, `INDETERMINATE`). Do not introduce other verdict formats.
- **Significance level is α = 0.01**, not 0.05. This is non-negotiable.
- **Null and negative results must be reported** at the same level as positive results.
- **Seeds must be fixed and logged** for every simulation run.
- **Do not modify `01_Theory/ORI_C_Pancarte_Normative_v1_0.md`** without a new version number and protocol update.
- **Robustness analyses are secondary** — they inform but do not change primary hypothesis verdicts.

## Glossary of Key Terms

| Term | Meaning |
|------|---------|
| Ex ante | Parameter fixed before observing data |
| SESOI | Smallest Effect Size of Interest |
| Pré-seuil | Pre-threshold regime: C(t) ≈ 0, S non-cumulative |
| Transition | Partial decorrelation of O, R, I and C |
| Cumulatif | Post-threshold: C(t) > 0 stable, symbolic amplification |
| Falsification | Condition that definitively rejects a hypothesis |
| Noyau ORI | Core subsystem: O, R, I, Cap, Σ, V |
| Canal symbolique | Symbolic channel: S → C pathway |
