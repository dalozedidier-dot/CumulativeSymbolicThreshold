# DATA_CONTRACT: State_Probability + ATTR (Count_Depth)

Objet
- Construire Ccl(t) et des résumés bootstrap à partir de distributions de probabilité mesurées (bitstrings) et d'attributs de circuits.
- Aucun verdict interprétatif. Les sorties sont mécaniques et auditables.

Entrées attendues
- Un zip contenant une arborescence de type:
  - <DATE>/<ALGO>/State_Probability/STATES_<device>_<ALGO>_<instance>_<shots>.csv
  - <DATE>/<ALGO>/Count_Depth/ATTR_<device>_<ALGO>_<instance>_<shots>.csv

Sémantique minimale
- STATES*.csv: distribution empirique p(x) sur les bitstrings. Le nombre de shots est encodé dans le nom de fichier.
- ATTR*.csv: attributs de circuit dont un axe de complexité. Par défaut, Depth est utilisé comme t.

Définitions mécaniques
- Axe t:
  - t = Depth (recommandé), ou t = Runtime si la colonne existe.
- Ccl(t) (classicité au sens dispersion):
  - entropy: H(p)/log(2^n), avec H(p) = -sum p log p, n = longueur bitstring.
  - one_minus_maxprob: 1 - max_x p(x)
  - one_minus_purity: 1 - sum p(x)^2
- t* (optionnel): premier t tel que Ccl(t) >= ccl_threshold.

Bootstrap
- Le bootstrap rééchantillonne les instances disponibles pour un groupe (algo, device, shots).
- Résumé produit sur t* si calculable.

Sorties
- tables/ccl_timeseries.csv: une ligne par run (algo, device, shots, instance) avec t et Ccl.
- tables/tstar_by_instance.csv: t* par instance si défini.
- tables/bootstrap_summary.json: statistiques bootstrap et paramètres.
- figures/ccl_mean.png, figures/tstar_hist.png (si t* existe)
- contracts/: copies du mapping et du runs index
- manifest.json: sha256 de tous les fichiers.

Limites connues
- Sans état idéal, Cq n'est pas défini ici. Ce pipeline traite Ccl uniquement.
- Si Depth varie fortement entre instances, les agrégations utilisent une grille de t commune basée sur l'union des valeurs observées.
