# 04_Code

Pipeline historique ORI-C. Pour l'installation canonique, voir le README racine.

## Installation canonique (recommandée)

```bash
pip install -e ".[dev]"
pytest -q
```

## Installation legacy

```bash
pip install -r 04_Code/requirements.txt
conda env create -f environment.yml && conda activate cumulative_symbolic
```

## Démo CSV

```bash
python 04_Code/pipeline/run_synthetic_demo.py --input 03_Data/synthetic/synthetic_minimal.csv --outdir 05_Results
```

## Démo ORI-C

```bash
python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/ori_c_demo
```

## Tests

```bash
pytest -q
```
