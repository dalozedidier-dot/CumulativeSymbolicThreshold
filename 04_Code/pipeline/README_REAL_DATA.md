# ORI-C sur données réelles

Ce guide ajoute un point d'entrée simple pour exécuter ORI-C sur une série réelle, puis lancer les tests causaux.

## 1. Format CSV minimal

Colonnes requises:
- t: temps (entier croissant) ou date (convertie en index)
- O, R, I: proxies normalisés dans [0,1]

Colonnes optionnelles:
- demand: demande ou pression externe (même unité sur toute la série)
- S: proxy symbolique observé, normalisé dans [0,1]

## 2. Exécuter la démo "real data"

Exemple:

python 04_Code/pipeline/run_real_data_demo.py \
  --input 03_Data/real/pilot_cpi/real.csv \
  --outdir 05_Results/real/pilot_cpi/run_0001 \
  --col-time date --time-mode index --col-O O --col-R R --col-I I --col-demand demand --col-S S \
  --auto-scale \
  --sigma-star 0.0 --tau 500 \
  --k 2.5 --m 3 --baseline-n 50 \
  --control-mode no_symbolic

Sorties:
- tables/test_timeseries.csv
- tables/control_timeseries.csv
- tables/summary.json
- figures/s_t.png
- figures/c_t.png
- figures/delta_c_t.png

## 3. Lancer les tests causaux

python 04_Code/pipeline/tests_causaux.py \
  --run-dir 05_Results/real/pilot_cpi/run_0001 \
  --alpha 0.01 --lags 1-10 \
  --pre-horizon 200 --post-horizon 200 \
  --k 2.5 --m 3 --baseline-n 50 \
  --pdf

Lire:
- tables/verdict.json
- tables/causal_report.md
- tables/causal_report.pdf (si --pdf)

## 4. Dépannage

- O, R, I doivent être dans [0,1]. Utiliser --normalize robust ou minmax si besoin.
- Si demand est fourni mais très différent d'échelle, garder --auto-scale.
- Si aucun seuil n'est détecté, ajuster baseline-n, pre-horizon, post-horizon.
- Si C est trop négatif par construction, préférer le critère C_mean_post_minus_pre dans le verdict.
