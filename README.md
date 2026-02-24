# Cumulative Symbolic Threshold (ORI-C)

[![DOI](https://img.shields.io/badge/DOI-10.17605%2FOSF.IO%2FG62PZ-blue)](https://doi.org/10.17605/OSF.IO/G62PZ)
[![OSF Pre-registration](https://img.shields.io/badge/OSF-G62PZ-lightgrey)](https://osf.io/g62pz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold/actions/workflows/ci.yml/badge.svg)](https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold/actions/workflows/ci.yml)
[![Nightly](https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold/actions/workflows/nightly.yml/badge.svg)](https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold/actions/workflows/nightly.yml)

**A pre-registered, falsifiable scientific framework** for testing the ORI-C hypothesis: beyond a critical threshold of symbolic accumulation, the symbolic transmission channel becomes self-reinforcing — a measurable phase transition from a pre-threshold regime to a cumulative symbolic regime.

> **Current synthetic verdict (T1–T8):** `ACCEPT` — `full_statistical_support`
> **Current real-data verdict (FRED monthly pilot):** `ACCEPT` — `real_data_canonical_support`

[Theory](#theory) · [Quick Start](#quick-start) · [Tests T1–T8](#tests-t1t8) · [Real Data](#real-data) · [Examples](#examples) · [Structure](#structure) · [Citation](#citation)

---

## Theory

### Core Variables (fixed ex ante)

| Symbol | Name | Description |
|--------|------|-------------|
| O(t) | Organisation | Structural/functional coordination proxy |
| R(t) | Resilience | Perturbation absorption capacity proxy |
| I(t) | Integration | Inter-component coherence proxy |
| Cap(t) | Capacity | `O(t) · R(t) · I(t)` — primary form |
| V(t) | Viability | Non-compensatory aggregation over `[t−Δ, t]` |
| Σ(t) | Mismatch | `max(0, D(E(t)) − Cap(t))` |
| S(t) | Symbolic stock | Transmissible repertoire proxy |
| C(t) | Order variable | Intergenerational symbolic gain |
| U(t) | Perturbation | Demand surge, capacity loss, or symbolic cut |

### Key Equations

```
Cap(t) = O(t) · R(t) · I(t)              [capacity — ex ante form]

Σ(t)   = max(0, D(E(t)) − Cap(t))        [mismatch — structural tension]

ΔC(t) > μ_ΔC + k · σ_ΔC  for m steps    [threshold detection criterion]
         k = 2.5, m = 3  (pre-registered)
```

### Causal Chain

```
O(t) ─┐
R(t) ─┼──► Cap(t) = O·R·I ──► Σ(t) = max(0, D − Cap) ──► V(t)
I(t) ─┘

S(t) ──────────────────────────────────────────────────► C(t) ──► ΔC(t) ──► threshold?
```

### Dynamic Regimes

| Regime | C(t) | S(t) | Interpretation |
|--------|------|------|----------------|
| **Pre-threshold** | ≈ 0 | Non-cumulative | Symbolic transmission does not self-amplify |
| **Transition** | Unstable | Partial decorrelation | O, R, I and C begin to decouple |
| **Cumulative** | > 0, stable | Amplifying | Intergenerational gain locked in |

---

## Quick Start

```bash
# 1. Create environment
conda env create -f environment.yml && conda activate cumulative_symbolic

# 2. Run synthetic demo (full ORI-C pipeline)
python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/demo

# 3. Causal tests on demo output
python 04_Code/pipeline/tests_causaux.py --run-dir 05_Results/demo

# 4. Full canonical suite T1–T8
python 04_Code/pipeline/run_all_tests.py --outdir 05_Results/canonical
```

With pip:

```bash
pip install -r requirements.txt
PYTHONPATH=04_Code pytest -q       # run test suite
```

---

## Tests T1–T8

Eight independently falsifiable causal tests in two proof dimensions.

### Dimension 1 — ORI Core (T1–T3)

| Test | Manipulation | Variable | Success | Falsification |
|------|-------------|----------|---------|---------------|
| **T1** | Vary O, R, I | Cap(t) | Monotone relation matches ex-ante form | Decorrelation or inversion |
| **T2** | Increase D(E(t)) | Σ(t) | Σ > 0 when D > Cap | Σ = 0 despite overload |
| **T3** | Induce high Σ | V(t) | V degrades proportionally to Σ | V stable despite high Σ |

### Dimension 2 — Cumulative Symbolic Regime (T4–T8)

| Test | Manipulation | Variable | Success | Falsification |
|------|-------------|----------|---------|---------------|
| **T4** | Vary S(t) | C(t) | ΔC attributable to ΔS | C invariant despite ΔS |
| **T5** | Inject S at t₀ | C(t+T) | Delayed effect measurable at horizon T | No delayed effect |
| **T6** | Cut/reduce S | C(t) | C drops without O, R, I change | C stable despite symbolic cut |
| **T7** | Progressive S sweep | C(t) | Stable tipping point S* detected | C strictly linear (no tipping) |
| **T8** | Combined U(t) multi-stress | O, R, I, S, C | Causal relations coherent under stress | Relations unstable or inverted |

### Minimal cumulative proof requirements

- **T1 + T2 + T3** → validates ORI–Cap–Σ–V core
- **T4 + T5 + T7** → validates cumulative symbolic regime
- **T6** → symbolic dimension irreducible to O, R, I alone

---

## Real Data

ORI-C runs on any time series with pre-normalised O, R, I proxies.

### Required CSV format

| Column | Required | Description |
|--------|----------|-------------|
| `O` | Yes | Organisation proxy, normalised to [0, 1] |
| `R` | Yes | Resilience proxy, normalised to [0, 1] |
| `I` | Yes | Integration proxy, normalised to [0, 1] |
| `demand` | No | Environmental demand proxy |
| `S` | No | Symbolic stock proxy |
| `t` / date | Conditional | Required when `--time-mode value` |

### Workflow

```bash
# Step 1 — validate proxy spec (hard gate: fails if spec is broken)
python 04_Code/pipeline/validate_proxy_spec.py \
  --spec 03_Data/real/fred_monthly/proxy_spec.json \
  --csv  03_Data/real/fred_monthly/real.csv

# Step 2 — run ORI-C
python 04_Code/pipeline/run_real_data_demo.py \
  --input 03_Data/real/fred_monthly/real.csv \
  --outdir 05_Results/real/fred/run_001 \
  --time-mode index --normalize robust_minmax --control-mode no_symbolic

# Step 3 — causal tests (Granger, VAR, cointegration, bootstrap CI)
python 04_Code/pipeline/tests_causaux.py \
  --run-dir 05_Results/real/fred/run_001 \
  --alpha 0.01 --lags 1-10 --pre-horizon 200 --post-horizon 200 --pdf
```

### Available pilot datasets

| Dataset | Sector | Notes |
|---------|--------|-------|
| `03_Data/real/fred_monthly/` | Economic (US FRED) | Pre-normalised monthly series |
| `03_Data/real/economie/pilot_cpi/` | Economic (FR CPI) | Sector pilot |
| `03_Data/real/energie/pilot_energie/` | Energy (EU27) | Sector pilot |
| `03_Data/real/meteo/pilot_meteo/` | Meteorological (EE) | Sector pilot |
| `03_Data/real/trafic/pilot_trafic/` | Transport (DE) | Sector pilot |

Each dataset includes a `proxy_spec.json` with column mappings, normalisation strategy, and SHA-256 audit hash.
See [`04_Code/pipeline/README_REAL_DATA.md`](04_Code/pipeline/README_REAL_DATA.md) for full reference.

---

## Examples

Interactive Jupyter notebooks in [`examples/`](examples/):

| Notebook | Description |
|----------|-------------|
| [`01_synthetic_demo.ipynb`](examples/notebook_01_synthetic_demo.ipynb) | Pre-threshold vs cumulative regime on synthetic data — visualise C(t), ΔC(t), and threshold detection |
| [`02_real_data_pilot.ipynb`](examples/notebook_02_real_data_pilot.ipynb) | FRED monthly real-data run + causal test output interpretation |
| [`03_robustness_analysis.ipynb`](examples/notebook_03_robustness_analysis.ipynb) | Robustness sweep: vary k, m, window, normalisation — secondary analysis |

---

## Reproducibility

Every result is fully reproducible:

- **Seeds**: all runs require `--seed`; logged in `manifest.json` with `seed_table.csv`
- **Parameters**: `k`, `m`, `α`, SESOI fixed in `02_Protocol/PREREG_TEMPLATE.md` before data collection
- **Audit trail**: each run writes `proxy_spec_sha256`, `seed_table.csv`, `manifest.json`
- **Data integrity**: SHA-256 checksums in `03_Data/real/_bundles/`
- **No post-hoc tuning**: parameter changes require a new pre-registration

```bash
# Verify a run's data integrity
python 04_Code/pipeline/make_sha256_manifest.py \
  --root 05_Results/my_run --out 05_Results/my_run/manifest.json
```

---

## Structure

```
CumulativeSymbolicThreshold/
├── 01_Theory/          # Normative placard, theory, glossary
├── 02_Protocol/        # Pre-registration, decision rules, intervention catalog
├── 03_Data/            # Synthetic + real datasets with proxy_spec.json
├── 04_Code/
│   ├── pipeline/       # All executable pipeline scripts (40+ scripts)
│   ├── tests/          # Pytest unit and integration tests
│   └── configs/        # JSON run configs
├── 05_Results/         # Run outputs (gitignored — never committed)
├── 06_Manuscript/      # Academic manuscript draft
├── examples/           # Jupyter notebooks (3 demos)
├── src/oric/           # Importable Python package
│   ├── ori_core.py     # Cap, Σ, V computations
│   ├── symbolic.py     # S(t), C(t), S* detection
│   ├── decision.py     # Nan-safe hierarchical verdict
│   ├── proxy_spec.py   # ProxySpec: versioned, hashable column mapping
│   ├── prereg.py       # PreregSpec frozen dataclass (all ex-ante params)
│   ├── randomization.py
│   └── logger.py       # JSONL append-only experiment log
├── ORIC_POINT_OF_TRUTH.md   # Normative repo anchors
├── CONTRIBUTING.md
├── CHANGELOG.md
└── CITATION.cff
```

---

## Decision Framework

All decision parameters **locked ex ante** — never adjusted post-observation.

| Parameter | Value |
|-----------|-------|
| Significance level α | **0.01** (non-negotiable) |
| Confidence intervals | 99% |
| Decision basis | Triplet: p-value + CI + SESOI |
| Verdict tokens | `ACCEPT` / `REJECT` / `INDETERMINATE` |
| Power gate | Power < 0.70 → forced `INDETERMINATE` |
| N_min per condition | 50 runs (100 preferred for stable power) |

**Welch-NaN fallback** (normative, `WELCH_NAN_FALLBACK_POLICY`):
Welch unavailable → bootstrap CI → Mann-Whitney U → `INDETERMINATE`. Never a silent default failure.

---

## Citation

```bibtex
@software{daloze2026oric,
  author  = {Daloze, Didier},
  title   = {Cumulative Symbolic Threshold: Architecture, threshold,
             and test protocol for O-R-I dynamics},
  year    = {2026},
  version = {v1.3},
  doi     = {10.17605/OSF.IO/G62PZ},
  url     = {https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold},
  license = {MIT}
}
```

[CITATION.cff](CITATION.cff) · [OSF pre-registration](https://osf.io/g62pz/) · [DOI: 10.17605/OSF.IO/G62PZ](https://doi.org/10.17605/OSF.IO/G62PZ)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — PR checklist, reviewer guide, dataset proposal process.

## License

MIT — see [LICENSE](LICENSE).
