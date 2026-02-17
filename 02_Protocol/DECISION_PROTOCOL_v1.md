# Protocole de décision ORI-C (v1)

Ce document fixe un point de vérité stable pour la prise de décision.

## Conventions

- Niveau de risque: α = 0,01.
- SESOI (effets minimalement pertinents):
  - Cap: +10 % relatif (baseline).
  - V: -10 % relatif (quantile bas ou fenêtre finale).
  - C: +0,3 écart-type robuste (MAD) si standardisé. Sinon utiliser un SESOI relatif documenté.
- Triplet décisionnel requis pour un verdict local: p-value, intervalle de confiance, SESOI.
- Si puissance au SESOI < 70 %, verdict local forcé à INDETERMINATE, même si p <= 0,01.

## Gate de qualité

Le gate de qualité doit passer avant toute agrégation.

- Taux d'échec technique < 5 %.
- Au moins 50 runs valides par condition.
- Diagnostics basiques OK: absence de patterns grossiers dans les résidus, VIF < 5 si modèle multivarié.

Si le gate échoue: verdict global INDETERMINATE.

## Agrégation minimale

- Noyau ORI: tests structurels et causaux cohérents.
- Couche symbolique: seuil, robustesse, reinjection.

La logique d'agrégation de référence est implémentée dans `04_Code/pipeline/run_all_tests.py`.

## Exécution canonique

Lancer:

- `python run_all_tests.py`

Les résultats sont écrits sous `05_Results/canonical_tests/`.
