Données attendues pour QCC (real data)

Placez un ou plusieurs fichiers CSV dans ce dossier.

Nom de fichier
- libre, par exemple run_001.csv, qcc_ramsey_2026_03_01.csv

Colonnes minimales
- t : temps (secondes ou index régulier). Si t n'est pas fourni, le script fabrique un index 0..n-1.
- Cq : cohérence quantique (proxy mesuré, par exemple visibilité interférence). Doit être dans [0,1].
- O : exposition au bruit (proxy mesuré indépendamment). Valeurs >= 0.
- R : régulation / protection (proxy mesuré indépendamment). Valeurs >= 0.

Colonnes optionnelles
- Ccl : indicateur de classicité (proxy basé sur répétitions, variance, etc). Doit être dans [0,1].

Important
- Le workflow est conçu pour tourner même si vous n'avez pas encore de données réelles.
  Si aucun CSV n'est présent, il génère un petit dataset demo dans la sortie (flag demo_used=true).
- Aucun verdict global n'est produit. Le check CI vérifie uniquement la présence des sorties et des invariants de forme.

Sorties produites (par run)
- 05_Results/qcc_real/<run_id>/tables/timeseries_out.csv
- 05_Results/qcc_real/<run_id>/tables/events.csv
- 05_Results/qcc_real/<run_id>/tables/summary.json
- 05_Results/qcc_real/<run_id>/figures/qcc_overview.png
- 05_Results/qcc_real/<run_id>/manifest.json
