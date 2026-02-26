# REPRODUCE.md — Guide de reproduction ORI-C

Ce document permet de reproduire tous les résultats du manuscrit à partir du dépôt seul.

## Prérequis

```bash
Python >= 3.12
git clone https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold
cd CumulativeSymbolicThreshold
pip install -r requirements.txt
```

Vérification de l'intégrité du code :

```bash
python -m compileall 04_Code -q   # doit retourner 0 erreur
python -m pytest 04_Code/tests/ -q  # doit passer (62+ tests)
```

## 1. Run canonical — smoke CI (vérification rapide, non conclusive)

```bash
python 04_Code/pipeline/run_all_tests.py \
  --outdir _runs/repro_smoke \
  --seed 1234 \
  --fast
```

- Mode : `smoke_ci` (non conclusif — voir manuscrit §2.3)
- Durée : ~2–5 min selon la machine
- Artefacts produits : `_runs/repro_smoke/<timestamp>/`
  - `global_summary.csv` — verdicts T1–T9
  - `seed_table.csv` — seeds exhaustives
  - `manifest.json` — audit trail complet

## 2. Run canonical — proof run (preuve statistique complète)

```bash
python 04_Code/pipeline/run_all_tests.py \
  --outdir _runs/repro_full \
  --seed 1234
```

- Mode : `full_statistical` (N = 60 pour les tests statistiques)
- Durée : ~30–60 min selon la machine
- Ce run est le seul autorisé à produire des conclusions publiables

## 3. Pilote FRED — T9 cross-domain (données réelles)

```bash
python 04_Code/pipeline/run_T9_cross_domain.py \
  --outdir _runs/t9_fred \
  --seed 1242
```

- Données : `03_Data/real/fred_monthly/real.csv` (480 points mensuels US)
- Artefacts :
  - `_runs/t9_fred/tables/verdict.json` — verdict T9
  - `_runs/t9_fred/tables/metrics.json` — AUC, balanced_accuracy, FPR
  - `_runs/t9_fred/figures/roc_curve.png` — courbe ROC
  - `_runs/t9_fred/manifest.json` — SHA256 de tous les artefacts

Version rapide (smoke CI) :

```bash
python 04_Code/pipeline/run_T9_cross_domain.py \
  --outdir _runs/t9_fred_fast \
  --seed 1242 \
  --fast
```

## 4. Pilote FRED — Suite canonique real data

```bash
python 04_Code/pipeline/run_real_data_canonical_suite.py \
  --input 03_Data/real/fred_monthly/real.csv \
  --outdir _runs/fred_canonical \
  --col-time date \
  --time-mode value \
  --col-O O \
  --col-R R \
  --col-I I \
  --col-demand demand \
  --alpha 0.01 \
  --lags 1-6 \
  --pre-horizon 120 \
  --post-horizon 120 \
  --k 2.5 \
  --m 3 \
  --baseline-n 60
```

## 5. Validation proxy_spec (ex ante)

Chaque dataset réel doit être validé avant tout run :

```bash
python 04_Code/pipeline/validate_proxy_spec.py \
  --spec 03_Data/real/fred_monthly/proxy_spec.json \
  --csv  03_Data/real/fred_monthly/real.csv
```

## 6. Manifest SHA256 (intégrité des artefacts)

```bash
python 04_Code/pipeline/make_sha256_manifest.py \
  --root _runs/repro_full/<timestamp> \
  --out  _runs/repro_full/<timestamp>/manifest_sha256.json
```

## 7. Seeds et reproductibilité

La stratégie de seeds est deterministe par offset :

```
seed(test_id) = base_seed + fixed_offset
```

Tableau des offsets (ex ante, immuable — vérifié par CI) :

| Test | Offset | Seed par défaut (base=1234) |
|------|--------|-----------------------------|
| T1 noyau demand shock | 0 | 1234 |
| T2 threshold demo | 1 | 1235 |
| T3 robustness OOS | 2 | 1236 |
| T4 symbolic S-rich vs S-poor | 3 | 1237 |
| T5 symbolic injection | 4 | 1238 |
| T6 symbolic cut | 5 | 1239 |
| T7 progressive sweep | 6 | 1240 |
| T8 reinjection recovery | 7 | 1241 |
| T9 cross-domain | 8 | 1242 |

Pour changer le base_seed : `--seed <N>`. Les offsets sont immuables.

## 8. Données réelles

Toutes les données réelles sont dans `03_Data/real/`. Le registre canonique est :

```
03_Data/real/registry/real_datasets.json
```

Chaque dataset liste : chemin, fréquence, colonnes, proxy_spec, taille minimale.

**Règles de qualité (non négociables) :**
- Mensuel : n_min = 120 points
- Trimestriel : n_min = 40 points
- Annuel : n_min = 60 points
- Pas de synthétique dans les workflows real data
- Toute transformation déclarée dans `proxy_spec.json` avant le run

## 9. Structure des artefacts de run

```
_runs/<run_id>/
  manifest.json          # base_seed, run_mode, seed_table, verdicts
  seed_table.csv         # seeds exhaustives par test
  global_summary.csv     # verdicts T1–T9, scripts, outdir, n_runs
  <test_id>/
    verdict.txt          # ACCEPT | INDETERMINATE | REJECT | ERROR
    verdict.json         # métriques détaillées
    summary.json         # résumé du run
    _logs/               # logs subprocess complets
```

## 10. CI

Le workflow CI principal est `.github/workflows/ci.yml`.
Les workflows sector sont `.github/workflows/sector_{bio,cosmo,infra}_suite.yml`.
Le workflow real data matrix est `.github/workflows/real_data_matrix.yml`.

Pour un run manuel : GitHub Actions → `Real Data Matrix` → `Run workflow` → choisir mode.

## Versions des dépendances

Voir `requirements.txt`. Versions minimales testées :

```
numpy>=1.26
scipy>=1.12
pandas>=2.2
matplotlib>=3.8
scikit-learn>=1.4
statsmodels>=0.14
```

Python 3.12 est requis (gate compileall vérifié par CI).
