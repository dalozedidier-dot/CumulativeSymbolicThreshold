# ORI-C — Résultats Pilote Données Réelles Eurostat
## Tests causaux T1–T8 sur 13 pays européens

**Date:** 21 février 2026  
**Statut:** Données réelles (Eurostat) — Proxies observationnels — Pilote exploratoire

⚠ **Statut épistémique:** Ce pilote utilise des données réelles (Eurostat) mais avec des proxies observationnels, pas des manipulations expérimentales. Les résultats établissent des *associations cohérentes avec le modèle*, pas des relations causales au sens strict. Le design observationnel est une limitation fondamentale.

---

## 1. Sources de données

| Code Eurostat | Contenu | Proxy ORI-C | Période |
|---|---|---|---|
| estat_sts_inpr_a | Production industrielle (B-D, base 2021) | **O(t)** Organisation | 1990–2025 |
| estat_nrg_cb_rw | Énergie renouvelable (consommation finale, TJ) | **R(t)** Résilience | 1990–2024 |
| estat_lfsa_esgaed | Emploi diplômés supérieurs / total indépendants | **I(t)** Intégration | 1992–2024 |
| estat_env_ac_taxind2 | Taxes environnementales (total, M€) | **D(E(t))** Demande | 1995–2023 |
| estat_rd_e_berdind | R&D entreprises (€/hab, total industrie) | **S₁(t)** Codification | 1981–2010 |
| estat_lfsa_etgar | % emploi temporaire pour formation | **S₂(t)** Transmission | 1983–2024 |
| estat_rd_p_bempocc | Personnel R&D (ETP) | **S₃(t)** Répertoire | 1980–2010 |

**Pays:** AT, BE, CZ, DE, DK, ES, FI, FR, IT, NL, PL, PT, SE (13 pays)

---

## 2. Deux datasets construits

### Dataset 1: 2008–2023 (période moderne)
- 204 observations (13 pays × ~16 ans)
- S(t) = S₂ seul (formation) — les données R&D s'arrêtent en 2010
- Couverture D(E) complète

### Dataset 2: 1995–2010 (période R&D)
- 162 observations (13 pays × ~12 ans)
- S(t) = moyenne(S₁, S₂, S₃) — canal symbolique riche (3 composantes)
- D(E) partiellement disponible

---

## 3. Résultats T1–T8

### Dataset 1 — 2008–2023

| Test | Verdict | Statistique clé | Détail |
|------|---------|-----------------|--------|
| **T1** | ✓ ACCEPT | ρ_O=0.62, ρ_R=0.71, ρ_I=0.74 | Tous p < 10⁻²², relation monotone confirmée |
| **T2** | ✓ ACCEPT | 186 cas surcharge, 100% Σ>0 | Mécanisme de tension parfaitement opérationnel |
| **T3** | ✓ ACCEPT | V(Σ bas)=0.118 vs V(Σ haut)=0.039 | Mann-Whitney p=4.8×10⁻⁶, ρ_ΣV=−0.46 |
| **T4** | ✗ REJECT | Corrélation intra-pays S→C = −0.07 | 6/13 pays positifs seulement |
| **T5** | ✓ ACCEPT | Lag ΔS→ΔC(t+1) moyen = 0.21 | 11/13 pays avec effet positif |
| **T6** | ✗ REJECT | 36 épisodes, ρ_ΔS↔ΔC = 0.15 | p=0.37, non significatif |
| **T7** | ✓ ACCEPT | S₀* = 0.20 | Chow F=3.76, p=0.025 |
| **T8** | ✓ ACCEPT | 20 épisodes, Cap=ORI 100% | Récupération C=100%, V=95% |

**Score: 6/8**

### Dataset 2 — 1995–2010

| Test | Verdict | Statistique clé | Détail |
|------|---------|-----------------|--------|
| **T1** | ✓ ACCEPT | ρ_O=0.73, ρ_R=0.78, ρ_I=0.78 | Tous p < 10⁻²⁸, monotonie encore plus nette |
| **T2** | ✓ ACCEPT | 134 cas surcharge, 100% Σ>0 | Parfait |
| **T3** | ✓ ACCEPT | V(Σ bas)=0.198 vs V(Σ haut)=0.049 | Mann-Whitney p=2.9×10⁻⁸, ρ_ΣV=−0.62 |
| **T4** | ✓ ACCEPT | Corrélation intra-pays S→C = 0.64 | 11/13 pays positifs, 10/13 significatifs |
| **T5** | ✗ REJECT | Lag ΔS→ΔC(t+1) moyen = −0.06 | 8/13 positifs mais effet faible |
| **T6** | ✗ REJECT | 19 épisodes, ρ_ΔS↔ΔC = 0.27 | p=0.26, non significatif |
| **T7** | ✓ ACCEPT | S₀* = 0.54 | Chow F=6.78, p=0.0015 |
| **T8** | ✓ ACCEPT | 8 épisodes, Cap=ORI 100% | Récupération C et V = 100% |

**Score: 6/8**

---

## 4. Synthèse par bloc

| Bloc | Exigence | Dataset 1 | Dataset 2 |
|------|----------|-----------|-----------|
| **Noyau ORI** (T1+T2+T3) | Tous ACCEPT | ✓ **VALIDÉ** | ✓ **VALIDÉ** |
| **Régime symbolique** (T4+T5+T7) | Tous ACCEPT | ✗ T4 échoue | ✗ T5 échoue |
| **Non-trivialité** (T6) | ACCEPT | ✗ **NON VALIDÉE** | ✗ **NON VALIDÉE** |
| **Robustesse** (T8) | ACCEPT | ✓ **VALIDÉE** | ✓ **VALIDÉE** |

---

## 5. Interprétation

### Ce qui est établi (robuste sur les deux datasets)

**Le noyau ORI–Cap–Σ–V fonctionne sur données réelles.** C'est le résultat le plus solide :

- La capacité Cap = O×R×I montre une relation monotone forte avec chacune de ses composantes (T1). Les corrélations de Spearman sont toutes supérieures à 0.6, avec des p-values extrêmement faibles. Ce n'est pas trivial car les proxies sont indépendants (production industrielle, énergie renouvelable, emploi qualifié).

- Le mécanisme de tension Σ = max(0, D−Cap) est parfaitement opérationnel (T2) : 100% des cas de surcharge produisent une tension positive.

- La dégradation de V sous tension est confirmée (T3) avec un effet très significatif (p < 10⁻⁶ sur les deux datasets).

- La robustesse sous stress combiné (T8) est également confirmée : les relations causales ORI→Cap se maintiennent sous perturbation, et le système récupère.

### Ce qui est partiellement établi

**Le canal symbolique a un effet, mais sa nature exacte est ambiguë :**

- T4 (S→C) passe avec le canal S riche (3 composantes R&D + formation, dataset 2) mais échoue avec S₂ seul (formation, dataset 1). Cela suggère que la formation seule est un proxy insuffisant du canal symbolique.

- T5 (effet différé) montre le pattern inverse : significatif sur le dataset moderne mais pas sur le dataset R&D. La résolution annuelle est probablement trop grossière pour capturer des effets différés.

- T7 (seuil critique) est confirmé sur les deux datasets, avec un test de Chow significatif. Les seuils diffèrent (S₀*=0.20 vs 0.54), ce qui est attendu puisque les proxies S sont différents.

### Ce qui n'est pas établi

**T6 (non-trivialité) échoue systématiquement.** C'est le résultat le plus important à discuter :

- Sur données réelles observationnelles, on ne trouve pas d'épisodes clairs où S baisse significativement pendant que O-R-I restent stables et où C chute en conséquence.

- Explication probable : les variables macroéconomiques sont trop corrélées entre elles pour isoler une "coupure symbolique" pure. Quand l'investissement R&D ou la formation baisse, la production industrielle et l'emploi sont généralement aussi affectés.

- **C'est une limitation fondamentale du design observationnel**, pas nécessairement une réfutation du modèle. T6 exige un quasi-experiment naturel (ex : choc de politique scientifique sans récession associée).

---

## 6. Limitations

1. **Pas de manipulation contrôlée.** Tous les tests reposent sur de la variation observée, pas sur des interventions. Les tests T4–T6 sont les plus affectés.

2. **C(t) est dérivé, pas observé.** Le proxy C(t) = cumsum(S×V) est construit à partir du modèle lui-même. Ce n'est pas une mesure indépendante du gain intergénérationnel. **La circularité C/V n'est pas totalement résolue.**

3. **Résolution annuelle.** Trop grossière pour détecter des transitions de phase fines (T7) ou des effets différés (T5).

4. **Proxies imparfaits.** L'emploi des indépendants diplômés n'est qu'un proxy partiel de l'intégration. La formation temporaire ne capture qu'une fraction du canal symbolique.

5. **Données agrégées au niveau national.** Les dynamiques ORI-C sont probablement plus visibles à une échelle inférieure (entreprises, secteurs, régions).

---

## 7. Prochaines étapes recommandées

Pour avancer vers une validation plus complète :

1. **Résoudre la circularité C/V** : trouver une mesure de C(t) indépendante de V(t). Piste : productivité totale des facteurs (TFP) résiduelle, après contrôle du capital physique et humain.

2. **Trouver un quasi-experiment pour T6** : identifier un choc exogène sur le canal symbolique (ex : réforme de politique scientifique, rupture d'échanges académiques, fermeture d'institutions de formation) sans choc économique simultané.

3. **Données infra-nationales** : utiliser des données régionales (NUTS2) ou sectorielles pour augmenter la résolution et le nombre d'observations.

4. **Données infra-annuelles** : pour T5 et T7, des données trimestrielles ou mensuelles seraient préférables.

5. **Domaine alternatif** : tester sur un domaine complètement différent (cellulaire ou organismal) pour vérifier la transférabilité.
