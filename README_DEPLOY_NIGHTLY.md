# nightly.html . Déploiement simple

## Fichiers fournis
- `nightly.html`

## Hypothèse par défaut
La page lit :
- `./tables/final_status.json`
- `./dual_proof_manifest.json`

Donc, si vous déposez `nightly.html` dans le dossier racine de l'artefact dual proof, la page fonctionnera telle quelle.

## Si vos fichiers sont ailleurs
Modifiez dans `nightly.html` :

```js
const CONFIG = {
  finalStatusUrl: "./tables/final_status.json",
  dualProofUrl: "./dual_proof_manifest.json"
};
```

## Champs affichés
- `final_pass`
- `dual_proof_status`
- `synthetic.global_verdict`
- `real_data_fred.global_verdict`
- `real_data_validation_protocol.verdict`
- `real_data_validation_protocol.test_detection_rate`
- `best_input` / `best_stem`
- `reasons[]`

## Source de vérité
- `final_status.json`
- `dual_proof_manifest.json`

La page n'interprète pas. Elle affiche.
