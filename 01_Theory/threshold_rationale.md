# Justification du seuil ΔC(t) > μ + kσ

Hypothèse:
Une rupture de régime correspond à une accélération durable de la croissance de C(t).

Définition:
ΔC(t) = C(t) - C(t-1)

Critère décisionnel:
ΔC(t) > μ + kσ pendant m pas consécutifs.

μ et σ sont calculés sur une fenêtre de référence fixée ex ante.
Deux options usuelles:
- baseline initiale, par exemple les premiers p% des points
- fenêtre glissante de largeur w, en excluant le point courant pour éviter l'auto inclusion

Propriétés:
- détectable avant effondrement de V si C accélère en amont
- basé sur le passé, donc moins manipulable
- paramétrable ex ante via k, m et la règle de référence
