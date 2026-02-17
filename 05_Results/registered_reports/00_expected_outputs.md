# Registered Reports: Expected Outputs (Placeholders)

## Figures attendues (prérégistrées)
- c_t_with_threshold.png: C(t) + détection seuil (ligne rouge = thr, points verts = franchissement)
- v_t_perturbation.png: V(t) original vs perturbé (intervention symbolique ou exogène)
- robustness_summary.png: comparaison seuil et effet causal sous variantes ω, α, Δ

## Tables attendues
- processed_synthetic.csv: variables calculées par run (V, S, Cap, Sigma, C, delta_C, threshold_hit)
- robustness_results.csv: résultats variantes (omega, alpha, delta_window, threshold_detected, effect_size_H3, etc.)
- falsification_summary.csv: statut H1 à H4 par condition (supporté, falsifié, nul)

## Rapports nuls ou négatifs
- Si aucun franchissement malgré Sigma(t) > Sigma* prolongé, H1 est considérée comme falsifiée et le rapport nul est accepté.
- Si perturbation symbolique n'affecte pas V(t) différemment pré et post seuil, H3 est considérée comme falsifiée.
- Tous résultats, positifs, nuls, inattendus, sont inclus sans filtre.

Version: v0. placeholders  
Date: 2026-02-17  
Statut: à remplir après runs principaux et robustesse
