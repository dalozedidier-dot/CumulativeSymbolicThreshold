# 04_Code

## Installation avec pip
```bash
pip install -r 04_Code/requirements.txt
```

## Installation avec conda
```bash
conda env create -f 04_Code/environment.yml
conda activate cumulative_symbolic_threshold
```

## Démo sur données synthétiques
Cas pré seuil:
```bash
python 04_Code/pipeline/run_synthetic_demo.py --input 03_Data/synthetic/synthetic_minimal.csv --outdir 05_Results
```

Cas avec transition:
```bash
python 04_Code/pipeline/run_synthetic_demo.py --input 03_Data/synthetic/synthetic_with_transition.csv --outdir 05_Results
```

## Tests initiaux
```bash
pip install -r 04_Code/requirements-dev.txt
PYTHONPATH=04_Code pytest -q
```
