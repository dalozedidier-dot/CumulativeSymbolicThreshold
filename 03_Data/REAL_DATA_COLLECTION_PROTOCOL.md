# Protocole de collecte de données réelles — ORI-C
Version: v1
Date: 2026-02-24

> Ce document définit de manière exhaustive les règles de collecte, de sélection, de nettoyage et
> de validation applicables à toutes les données réelles utilisées dans le cadre du projet ORI-C.
> Il doit être scellé avant la collecte et ne peut être modifié qu'avec un incrément de version.

---

## 1. Objectif et portée

Ce protocole couvre :
- La sélection des sources et séries
- Les critères d'inclusion et d'exclusion des unités et des périodes
- La granularité temporelle admissible
- Les règles de traitement des lacunes et valeurs manquantes
- L'identification et la documentation des biais de mesure
- Les contrôles de cohérence et d'intégrité
- Les exigences de traçabilité et de manifeste

Il s'applique à tout proxy de O, R, I, S, D(E) utilisé dans une analyse ORI-C sur données réelles.

---

## 2. Sélection des sources

### 2.1 Critères d'admissibilité des sources

Une source est admissible si elle satisfait **tous** les critères suivants :

| Critère | Exigence |
|---------|----------|
| Disponibilité publique ou autorisation formelle | Oui — licence documentée |
| Reproductibilité de l'accès | URL pérenne, DOI, ou dépôt archivé |
| Métadonnées de définition | Définition opératoire de la variable publiée par le producteur |
| Stabilité de la définition | Aucune rupture de définition non documentée |
| Couverture temporelle minimale | ≥ **15 observations** sur la période d'analyse après nettoyage |
| Granularité | Annuelle, trimestrielle ou mensuelle (voir Section 3) |

### 2.2 Sources préapprouvées par domaine

| Domaine | Source principale | Variable(s) proxies | URL de référence |
|---------|------------------|--------------------:|-----------------|
| Économique | World Bank WDI | O, R, I, S | https://data.worldbank.org |
| Énergie | IEA / Eurostat | O, R | https://www.iea.org |
| Météo/Environnement | ERA5 / Copernicus | D(E) | https://cds.climate.copernicus.eu |
| Trafic | OECD / Eurostat | O, R | https://ec.europa.eu/eurostat |
| CPI/Inflation | FRED / Eurostat | D(E), O | https://fred.stlouisfed.org |

> Toute source hors liste doit être justifiée dans le champ `proxy_spec.json` avant utilisation.

### 2.3 Hiérarchie de proxies

Quand plusieurs proxies candidats existent pour une variable (ex. O), retenir celui qui :
1. A la couverture temporelle la plus longue (priorité 1)
2. Est le plus indépendant des autres proxies retenus (priorité 2)
3. A la définition opératoire la plus stable (priorité 3)

La justification doit figurer dans `proxy_spec.json` (champ `proxy_selection_rationale`).

---

## 3. Granularité temporelle

### 3.1 Granularités admissibles

| Granularité | Condition d'utilisation | Agrégation vers pas ORI-C |
|-------------|------------------------|--------------------------|
| **Annuelle** | Préférentielle — aucune condition | Directe |
| **Trimestrielle** | Admissible si ≥ 20 trimestres | Moyenne par année (ou analyse trimestrielle) |
| **Mensuelle** | Admissible si ≥ 36 mois | Moyenne par trimestre puis par année |
| **Hebdomadaire ou infra** | Non admissible pour proxies ORI | Sauf pour D(E) météo/demande |

### 3.2 Mixage de granularités

Quand O, R, I n'ont pas la même granularité native :
- Toujours agréger vers la granularité la **plus grossière** (jamais interpoler vers le plus fin)
- Documenter le mixage dans `proxy_spec.json` (champ `temporal_resolution`)
- Si l'agrégation réduit la série < 15 observations, la source est exclue

### 3.3 Alignement temporel

Toutes les colonnes d'une série doivent être alignées sur le même index temporel avant toute
analyse. L'index `t` (ou `year`) doit être entier ou date ISO-8601. Aucune interpolation temporelle
n'est admissible sauf documentation explicite.

---

## 4. Critères d'inclusion et d'exclusion des unités et périodes

### 4.1 Inclusion d'une unité (pays, région, organisation…)

Une unité est incluse si :
- ≥ **15** observations valides pour O **et** au moins un proxy parmi {R, I} après nettoyage
- Présence sur au moins **80 %** de la période commune avec les autres unités du panel
- Aucune rupture de définition non documentée dans O, R ou I

### 4.2 Exclusion d'une unité

Cause d'exclusion obligatoire :
- Taux de valeurs manquantes **> 40 %** pour O, R ou I combinés sur la période d'analyse
- Rupture structurelle non documentée : test de Chow à p ≤ 0.01 sur O ou R sur la période de référence
- Proxy remplacé mi-série sans documentation (deux sources non comparables concaténées)

### 4.3 Inclusion d'une période

Une période est incluse si :
- O n'est pas manquant sur cette période
- Pas de signalement de rupture méthodologique par le producteur de données

### 4.4 Exclusion d'une période

- Année de transition de source (ex. révision de méthodologie documentée)
- Année avec valeur aberrante non expliquée détectée par la règle IQR × 3 (valeurs > Q3+3·IQR ou < Q1−3·IQR)

Les exclusions de périodes sont documentées dans la colonne `exclusion_reason` du fichier `data_dictionary.md`.

---

## 5. Traitement des valeurs manquantes

### 5.1 Règle générale

**Aucune imputation par défaut.** Les valeurs manquantes sont traitées comme suit :

| Cas | Action |
|-----|--------|
| Manquant dans une colonne optionnelle (I, S) | Exclure la colonne du calcul Cap/S pour cette unité si < 25 % de couverture |
| Manquant dans une colonne principale (O) | Exclure l'observation de tous les calculs nécessitant O |
| Bloc de manquants consécutifs ≤ 2 obs. | Admissible — mentionner dans le manifeste |
| Bloc de manquants consécutifs > 2 obs. | Traiter comme rupture temporelle — envisager exclusion d'unité |

### 5.2 Imputation admissible (si explicitement pré-enregistrée)

Si et seulement si déclarée en Section 9.3 du PREREG_TEMPLATE, une imputation est permise :

| Méthode | Condition d'usage |
|---------|-----------------|
| Interpolation linéaire | ≤ 2 manquants consécutifs, série monotone |
| Carry-forward (LOCF) | ≤ 1 manquant consécutif, série stable |
| Modèle de tendance | Déclaré ex ante, appliqué uniquement hors fenêtre de calibration |

L'imputation ne s'applique **jamais** à la variable C(t), ni aux valeurs post-seuil.

### 5.3 Documentation

Chaque valeur imputée doit être flagguée dans le CSV source avec une colonne `{col}_imputed = True/False`.

---

## 6. Normalisation

Toutes les colonnes O, R, I, S doivent être normalisées dans **[0, 1]** avant toute analyse ORI-C.

| Méthode | Condition |
|---------|-----------|
| Min-Max sur la **période de calibration seule** (pas sur le test) | Méthode par défaut |
| Min-Max sur la **série complète** | Admissible si déclaré ex ante — à éviter car fuite temporelle |
| Normalisation par z-score | Non admissible pour la forme principale Cap = O×R×I |

La méthode retenue est déclarée dans `proxy_spec.json` (champ `normalization`).

> **Attention fuite temporelle** : la normalisation sur la série complète utilise des informations
> futures dans le calibration set. Sauf justification spécifique, normaliser sur la période de
> calibration uniquement.

---

## 7. Biais de mesure : identification et documentation

### 7.1 Biais à identifier systématiquement

Pour chaque proxy, les biais suivants doivent être identifiés et documentés dans `proxy_spec.json` :

| Biais | Description | Méthode de détection |
|-------|-------------|---------------------|
| **Biais de sélection** | L'indicateur ne couvre qu'un sous-ensemble de la population cible | Comparer la définition du producteur avec la définition ORI-C |
| **Biais d'attrition** | Les unités qui quittent le panel sont systématiquement différentes | Test de non-attrition aléatoire |
| **Biais de définition** | Changement de méthodologie de collecte mid-série | Test de Chow sur la série brute |
| **Biais de comparabilité** | Unités mesurées avec des méthodes différentes | Vérifier si la source utilise des normes harmonisées |
| **Biais d'agrégation** | Le proxy agrège des sous-composantes hétérogènes | Décomposer et tester la contribution de chaque sous-composante |
| **Biais de décalage temporel** | Le proxy reflète t−1 plutôt que t | Vérifier si l'indicateur est publié avec délai |

### 7.2 Format de documentation des biais

Dans `proxy_spec.json` pour chaque proxy, ajouter un champ `measurement_bias` :

```json
"measurement_bias": {
  "selection_bias": "description ou 'none identified'",
  "definition_change": "date et nature du changement ou 'none identified'",
  "temporal_lag": "0 (aucun décalage) ou N (décalage de N périodes)",
  "comparability_notes": "texte libre",
  "mitigation": "action prise ou 'none'"
}
```

### 7.3 Biais non corrigibles

Un biais est qualifié de **non corrigible** si :
- Il affecte > 50 % des observations de manière directionnelle
- Il ne peut pas être atténué par normalisation ou exclusion

Un proxy avec biais non corrigible est **exclu**. Si aucun proxy alternatif n'existe, la variable
est marquée `unavailable` dans `proxy_spec.json` et le test correspondant produit
automatiquement un verdict `INDETERMINATE` avec note `proxy_unavailable`.

---

## 8. Contrôles de cohérence et d'intégrité

### 8.1 Contrôles automatiques (exécutés par `scripts/validate_proxy_spec.py`)

| Contrôle | Critère de passage |
|----------|------------------|
| Chaque variable O, R, I apparaît exactement une fois dans la spec | Erreur si dupliquée ou absente |
| Normalisation dans l'ensemble admissible | `{minmax_cal, minmax_full, none}` |
| Direction dans `{positive, negative, none}` | Erreur sinon |
| Stratégie manquants dans `{exclude, locf, linear_interp, none}` | Erreur sinon |
| Couverture ≥ 15 obs. non nulles après nettoyage | Avertissement si < 15, erreur si < 5 |

### 8.2 Contrôle d'intégrité des fichiers (SHA-256)

Après finalisation de chaque jeu de données réel, générer un manifeste SHA-256 :

```bash
python scripts/make_sha256_manifest.py \
  --input-dir 03_Data/real/<secteur>/ \
  --output 03_Data/real/<secteur>/sha256_manifest.json
```

Ce manifeste doit être enregistré dans `03_Data/real/_bundles/bundle_hashes.json` avant tout
lancement de la CI d'analyse (voir `.github/workflows/independent_replication.yml`).

### 8.3 Contrôle de stationnarité (informatif, non décisionnel)

Pour chaque proxy, exécuter un test ADF (Augmented Dickey-Fuller) et documenter le résultat.
Ce test est **informatif uniquement** — un proxy non stationnaire n'est pas exclu, mais la note
doit figurer dans `proxy_spec.json` et dans les annexes du manuscrit.

---

## 9. Exigences de traçabilité

### 9.1 Fichiers obligatoires par jeu de données réel

```
03_Data/real/<secteur>/
├── real.csv               # Données nettoyées, colonnes t, O, R, I (et optionnels S, demand)
├── proxy_spec.json        # Spécification des proxies (validée par validate_proxy_spec.py)
├── sha256_manifest.json   # Hash de real.csv et proxy_spec.json
├── sources.md             # Références complètes des sources (URL, date d'accès, licence)
└── exclusions.md          # Liste de toutes les unités/périodes exclues avec justification
```

### 9.2 Format `proxy_spec.json` requis

```json
{
  "dataset_id": "<secteur>_<version>",
  "created": "YYYY-MM-DD",
  "columns": [
    {
      "name": "O",
      "oric_variable": "O",
      "source": "<nom de la source>",
      "source_url": "<URL>",
      "source_access_date": "YYYY-MM-DD",
      "original_series_name": "<nom exact dans la source>",
      "direction": "positive",
      "normalization": "minmax_cal",
      "missing_strategy": "exclude",
      "temporal_resolution": "annual",
      "coverage_start": "YYYY",
      "coverage_end": "YYYY",
      "proxy_selection_rationale": "...",
      "measurement_bias": {
        "selection_bias": "none identified",
        "definition_change": "none identified",
        "temporal_lag": 0,
        "comparability_notes": "...",
        "mitigation": "none"
      }
    }
  ]
}
```

### 9.3 Journal de collecte

Chaque acte de collecte (téléchargement, accès API) doit être consigné dans `sources.md` avec :
- Date d'accès
- URL exacte ou commande API
- Version ou release de la source
- Hash du fichier brut téléchargé

---

## 10. Procédure de validation avant analyse

Avant de lancer toute analyse ORI-C sur un nouveau jeu de données réel, exécuter dans l'ordre :

```bash
# Étape 1 — Valider la spécification des proxies
python scripts/validate_proxy_spec.py 03_Data/real/<secteur>/proxy_spec.json

# Étape 2 — Vérifier l'intégrité des fichiers
python scripts/check_bundle_integrity.py \
  --bundle-root 03_Data/real/_bundles \
  --hashes-file 03_Data/real/_bundles/bundle_hashes.json

# Étape 3 — Vérification visuelle de la série (diagnostique)
python 04_Code/pipeline/run_real_data_demo.py \
  --input 03_Data/real/<secteur>/real.csv \
  --outdir 05_Results/real/<secteur>/diagnostic \
  --control-mode no_symbolic --seed 42

# Étape 4 — Tests causaux
python 04_Code/pipeline/tests_causaux.py \
  --outdir 05_Results/real/<secteur>/diagnostic \
  --alpha 0.01 --lags 1-5

# Étape 5 — (si panel multi-pays) DiD / Contrôle synthétique
python 04_Code/pipeline/run_did_synthetic_control.py \
  --panel 03_Data/real/_bundles/data_real_v2/oric_inputs/oric_inputs_panel.csv \
  --treated-geo <geo> --event-year <annee> --outcome-col O \
  --outdir 05_Results/real/<secteur>/did --alpha 0.01 --n-boot 500 --seed 42
```

Toutes les étapes doivent passer sans erreur avant qu'une analyse ne soit déclarée valide.

---

## 11. Saut de domaine : de la simulation au réel

### 11.1 Différences structurelles

| Dimension | Simulation | Données réelles |
|-----------|-----------|----------------|
| Contrôle des variables | Total | Partiel ou nul |
| Sources de bruit | Connues et paramétrées | Inconnues, structurelles |
| Nombre d'observations | Arbitraire | Fixé par la réalité |
| Indépendance des runs | Garantie par seed | Impossible — une seule histoire |
| Falsification T2–T3 | Directe (Σ contrôlé) | Indirecte (Σ inféré) |
| Identification causale | Par design | Requiert stratégie quasi-expérimentale |

### 11.2 Ajustements obligatoires pour l'analyse réelle

1. **Identification causale** : toute affirmation causale sur données réelles requiert une stratégie
   d'identification (DiD + parallel trends, RDD, IV, ou SC) documentée ex ante.

2. **N d'observations** : avec une seule série temporelle de N années, le «run» unique ne permet
   pas de tests T1–T8 au sens simulation. Le protocole de validation réelle (Section 10 + fichier
   `run_real_data_validation_protocol.py`) remplace les N=50 runs par des approches
   de split temporel et de sous-échantillonnage.

3. **Seuil de détection** : les paramètres k et m sont hérités de PreregSpec. Si la série réelle
   est plus courte que 30+m observations, la baseline ne peut pas être estimée — le run produit
   automatiquement un verdict `INDETERMINATE` avec note `baseline_too_short`.

4. **Biais de confirmation** : l'analyse sur données réelles est particulièrement exposée à
   l'auto-justification post-hoc. Toute décision de sélection de proxy, de fenêtre, ou de
   granularité doit être documentée AVANT de regarder la série complète.

5. **Résultats négatifs** : un verdict REJECT sur données réelles est scientifiquement équivalent
   à un verdict ACCEPT. Les deux doivent être rapportés avec le même niveau de détail.

---

*Document scellé le : ___________
Version : v1
Approbation : ___________*
