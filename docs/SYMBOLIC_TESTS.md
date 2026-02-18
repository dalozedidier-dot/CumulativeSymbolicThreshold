# Symbolic tests T4, T5, T7

This repository includes a minimal symbolic test suite that validates the cumulative regime without changing the ORI-C framework.

## Run the symbolic suite (T4, T5, T7)

```bash
python 04_Code/pipeline/run_symbolic_suite_T4_T5_T7.py --outdir 05_Results/symbolic_suite
```

Outputs are written under:
- 05_Results/symbolic_suite/tables/
- 05_Results/symbolic_suite/figures/
- 05_Results/symbolic_suite/verdict.txt

## Minimal visual pack

If you have a processed CSV that contains at least columns `t,Sigma,C,V`, you can generate a compact visual pack:

```bash
python 04_Code/pipeline/plot_phase_suite.py --input path/to/processed.csv --outdir 05_Results/visual_suite
```
