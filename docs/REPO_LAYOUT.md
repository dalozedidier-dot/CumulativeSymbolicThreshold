# ORI-C . Layout du dépôt et sources de vérité

Objectif : éliminer toute ambiguïté sur "où est la vérité" sans casser l'historique.

## Répertoires numérotés (workflow scientifique)
- 01_Theory/ : fondements théoriques
- 02_Protocol/ : protocole et règles de décision
- 03_Data/ : données de référence, packs, proxy specs
- 04_Code/ : pipeline et scripts de recherche
- 05_Results/ : sorties (jamais versionnées)
- 06_Manuscript/ : manuscrit

Ces dossiers sont la trajectoire principale.

## Répertoires techniques (exécution/packaging)
- src/ : package Python installable (source of truth pour le code importable)
- tools/ : outils CLI et outillage CI (collect, checks, manifests)
- scripts/ : scripts utilitaires, génération, wrappers

Règle : si un module doit être importable, il est dans src/. Les scripts restent dans tools/ ou scripts/.

## Données "data/" vs "03_Data/"
- 03_Data/ : catalogue et packs de référence
- data/ : datasets opérationnels et index (ex data/real_datasets_index.csv), bundles, caches d'extraction

Règle : l'index canonique de datasets réels vit dans data/. Les artefacts et packs de référence vivent dans 03_Data/.

## Requirements
- requirements.txt : base
- requirements/ : fichiers spécialisés (qcc, real-data, dev)

Règle : les workflows CI doivent pointer vers un chemin existant. Le fichier racine requirements-qcc-stateprob.txt peut servir de pont de compatibilité.

## Point de vérité
- docs/ORI_C_POINT_OF_TRUTH.md est la référence unique.

Tout doublon éventuel en racine est considéré comme compatibilité/historique et doit rediriger vers docs/.
