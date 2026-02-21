# PREREG_TEMPLATE — ORI-C Pilote Données Réelles Eurostat
# Préenregistrement ex ante — Version 1.0 — 21 février 2026

## Identifiant
- **Projet:** ORI-C Validation Empirique — Domaine Groupe Humain (Pays UE)
- **Auteur:** [à compléter]
- **Date de verrouillage:** 2026-02-21
- **Seed aléatoire:** 42
- **Dépôt:** GitHub dalozedidier-dot/CumulativeSymbolicThreshold

## Domaine d'application
- **Système:** Économies nationales européennes (13 pays UE)
- **Unité:** pays × année
- **Pays:** AT, BE, CZ, DE, DK, ES, FI, FR, IT, NL, PL, PT, SE

## Proxies déclarés ex ante

### Variables internes O, R, I

| Variable | Proxy | Source Eurostat | Unité |
|----------|-------|----------------|-------|
| O(t) | Indice production industrielle (B-D, NSA, base 2021) | estat_sts_inpr_a | Index 2021=100 |
| R(t) | Consommation finale énergie renouvelable (total) | estat_nrg_cb_rw (FC, R5110-5150_W6000RI) | TJ |
| I(t) | Part diplômés supérieurs parmi indépendants (25-64 ans) | estat_lfsa_esgaed (ED5-8/TOTAL, SELF, T, Y25-64) | ratio |

### Demande environnementale D(E)

| Variable | Proxy | Source | Unité |
|----------|-------|--------|-------|
| D(E(t)) | Taxes environnementales totales (économie entière) | estat_env_ac_taxind2 (ENV, TOTAL, MIO_EUR) | M€ |

### Canal symbolique S(t)

| Composante | Proxy | Source | Unité | Poids α |
|------------|-------|--------|-------|---------|
| S1: Codification | Dépenses R&D entreprises par habitant | estat_rd_e_berdind (TOTAL, EUR_HAB) | €/hab | 1/3 |
| S2: Transmission | % emploi temporaire pour formation | estat_lfsa_etgar (EDUC_TNG, T, Y15-64, PC_SAL) | % | 1/3 |
| S3: Répertoire | Personnel R&D (ETP total) | estat_rd_p_bempocc (T, TOTAL, TOTAL, FTE) | FTE | 1/3 |

**Note:** S1 et S3 ne sont disponibles que jusqu'en 2010. Le dataset 2008-2023 utilise S2 seul.

### Variable d'ordre C(t)
- **Définition:** C(t) = cumsum(S(t) × V(t)) / normalisation min-max
- **Interprétation:** Effet cumulatif intégré de la transmission symbolique pondérée par la viabilité

### Viabilité V(t)
- **Forme:** V(t) = clip(Cap(t) − 0.5 × Σ(t), 0.01, 1.0)
- **Poids ω:** ω₁=1 (survie ≡ Cap), ω₂=−0.5 (pénalité tension)

## Formes fonctionnelles (verrouillées)

| Fonction | Forme |
|----------|-------|
| Cap(t) | O(t) × R(t) × I(t) |
| Σ(t) | max(0, D(E(t)) − Cap(t)) |
| S(t) | moyenne(α₁·S1, α₂·S2, α₃·S3) [normalisation min-max intra-pays] |
| V(t) | clip(Cap − 0.5·Σ, 0.01, 1.0) |
| C(t) | normalize_01(cumsum(S × V)) × 0.9 + 0.05 |

## Normalisation
- Toutes les variables sont normalisées min-max [0,1] **intra-pays** puis compressées [0.05, 0.95]
- Le flag `--auto-scale` est activé

## Seuils déclarés ex ante

| Paramètre | Valeur |
|-----------|--------|
| α (significativité) | 0.01 pour T1-T3, 0.05 pour T4-T8 |
| Seuil Σ* | Non applicable (Σ est continu) |
| Critère T6 épisode | ΔS < −0.03, max(ΔO, ΔR, ΔI) < 0.20 |
| Critère T8 stress | Σ > quantile 70%, S en baisse |
| Fenêtre Δ | 1 an (résolution annuelle) |
| Horizon T | 1 an (lag +1) |

## Datasets

| Dataset | Fenêtre | Observations | Variable S |
|---------|---------|-------------|------------|
| oric_pilot_2008_2023.csv | 2008-2023 | 204 (13×~16) | S2 seul |
| oric_pilot_1995_2010.csv | 1995-2010 | 162 (13×~12) | S1+S2+S3 |

## Tests statistiques déclarés ex ante

| Test | Statistique | Critère de succès |
|------|-------------|-------------------|
| T1 | Spearman O→Cap, R→Cap, I→Cap | Tous ρ > 0, p < 0.01 |
| T2 | % Σ > 0 quand D > Cap | > 95% |
| T3 | Mann-Whitney V(Σ bas) vs V(Σ haut) | p < 0.01, V décroissant |
| T4 | Spearman intra-pays S→C | > 50% pays ρ > 0 |
| T5 | Corrélation lag ΔS→ΔC(t+1) | Moyenne > 0, > 50% pays positifs |
| T6 | Corrélation ΔS↔ΔC dans épisodes coupure | ρ > 0, p < 0.10 |
| T7 | Test de Chow (rupture de pente S→C) | F significatif p < 0.05, Δslope > 0.05 |
| T8 | Récupération C et V post-stress | Cap=ORI maintenu >90%, récupération >30% |

## Aucun ajustement post-observation
Ce document est verrouillé. Tout écart par rapport aux paramètres ci-dessus invalide l'essai.
