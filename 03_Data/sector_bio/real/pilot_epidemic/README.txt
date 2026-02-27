Contenu: real.csv au format ORI-C.
Source: dataset ECDC COVID (fichier 'téléchargement' fourni par l'utilisateur).
Sélection: Belgique, tri temporel croissant.
Colonnes ORI-C:
- demand: Cumulative_number_for_14_days_of_COVID-19_cases_per_100000
- O: z-score robuste MAD sur fenêtre glissante 30 jours appliqué à demand
- R: proxy recovery = -(demand[t] - demand[t-1]) (positif quand la pression baisse)
- I: invariant placeholder = 1.0 (à spécialiser via proxy_spec.json si besoin)
Colonnes supplémentaires conservées: cases, deaths, popData2019.
