# Support Python

Le dépôt déclare Python 3.12 comme cible maintenue.

Cette décision aligne :

- `pyproject.toml` avec `requires-python >=3.12` ;
- Ruff et mypy, déjà configurés pour Python 3.12 ;
- le Dockerfile, basé sur Python 3.12 ;
- les workflows de packaging et de couverture.

Les scripts historiques peuvent fonctionner sur d’autres versions selon les dépendances installées, mais ils ne constituent pas une promesse de support. Toute extension officielle du support doit modifier en même temps `pyproject.toml`, les classifiers, le README, Docker et la matrice CI.
