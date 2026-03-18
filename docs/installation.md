# Installation de l'environnement ORI-C

## Installation canonique (recommandée)

```bash
pip install -e ".[dev]"
```

Ceci installe le package `oric` en mode éditable avec toutes les dépendances
de développement (pytest, ruff, mypy).

## Méthode Conda

Créer l'environnement :
```bash
conda env create -f environment.yml
conda activate cumulative_symbolic
```

L'environnement Conda utilise `pip install -e ".[dev]"` en interne.

## Méthode pip (environnement virtuel)

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate        # Windows
pip install -e ".[dev]"
```

## Vérification

```bash
python -c "import oric; print('OK')"
pytest -q
```

## Exécuter les démos

ORI-C :
```bash
python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/ori_c_demo
python 04_Code/pipeline/tests_causaux.py --outdir 05_Results/ori_c_demo
```

Robustesse CSV :
```bash
python 04_Code/pipeline/run_robustness.py --input 03_Data/synthetic/synthetic_with_transition.csv --outdir 05_Results
```

## Mode legacy (04_Code)

Le répertoire `04_Code/` contient le pipeline historique. Pour une installation
legacy, voir `04_Code/README.md`.
