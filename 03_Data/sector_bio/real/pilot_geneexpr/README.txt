Contenu: real.csv au format ORI-C.
Source: SRP026387_scaledcounts.csv (matrice gènes x échantillons).
Construction d'une série 1D par échantillon:
- pc1: première composante principale de log1p(counts)
Colonnes ORI-C:
- demand: pseudo-temps linéaire normalisé 0..1 (placeholder, car métadonnées conditionnelles non fournies pour ces SRR)
- O: z-score robuste MAD de pc1
- R: proxy stabilité locale = -abs(delta pc1)
- I: invariant placeholder = 1.0
Note: si tu veux un pilot_geneexpr basé sur airway (dex control/treated), il faut les counts airway correspondants aux id de airway_metadata.csv.
