# Seeds and reproducibility

Environnement:
- Python 3.11
- numpy
- pandas
- matplotlib

Seeds:
- ORI-C default seed: 42
- Tous les scripts acceptent --seed.

Résultats déterministes:
- run_ori_c_demo.py --seed 42 produit les mêmes CSV et figures.
- tests_causaux.py --seed 42 produit les mêmes verdicts.
