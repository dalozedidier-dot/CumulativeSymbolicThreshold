# Cumulative Symbolic Threshold

Version: v1  
Date: 2026-02-17

This repository provides a reproducible, preregistrable, and falsifiable framework to test a transition toward a cumulative symbolic regime.

Core concepts:
- Internal cycle: Organization O(t), Resilience R(t), Integration I(t)
- Viability metric: V(t) measured on a window [t-Δ, t], aggregation fixed ex ante
- Mismatch (stress): Σ(t) = max(0, D(E(t)) - C(O(t), R(t), I(t)))
- Symbolic stock: S(t)
- Symbolic efficiency under intervention: s(t) = ΔV(t) / ΔS(t)
- Order parameter: C(t), intergenerational performance gain due to social transmission at (approximately) constant genetics over a preregistered horizon T

## Repository structure
- `01_Theory/` theory core and variable glossary
- `02_Protocol/` protocol, preregistration template, intervention catalog
- `03_Data/` data dictionary, inclusion and exclusion rules, example synthetic dataset
- `04_Code/` minimal pipeline skeleton and configuration example
- `05_Results/` output structure (figures, tables)
- `06_Manuscript/` draft manuscript and methods appendix placeholders

## How to cite
See `CITATION.cff`.

## License
MIT License. See `LICENSE`.
Clarifications: see `LICENSING.md`.

## Preregistration note
All decision parameters must be fixed ex ante in `02_Protocol/PREREG_TEMPLATE.md`, including Δ, T, τ, Σ*, k, m, weights ω and α, and the functional form of C(O,R,I).
Robustness analyses are allowed but must be labeled as secondary.
