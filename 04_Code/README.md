# 04_Code

## Installation rapide
1) Créer un environnement virtuel
2) Installer les dépendances

Exemple:
pip install -r 04_Code/requirements.txt

## Démo sur données synthétiques
python 04_Code/pipeline/run_synthetic_demo.py \
  --input 03_Data/synthetic/synthetic_minimal.csv \
  --outdir 05_Results \
  --k 2.0 \
  --m 3
