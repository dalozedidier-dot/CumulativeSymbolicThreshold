# ORI-C . Finalisation (interne repo)

Objectif : arrêter les micro-corrections en figeant un contrat global et un gate final binaire.

## Artifacts attendus (nightly)
- nightly_synthetic_*.zip
- nightly_real_fred_*.zip
- nightly_validation_protocol_*.zip
- nightly_dual_proof_*.zip

## Contrat
Voir `contracts/`:
- DUAL_PROOF_CONTRACT.json
- VALIDATION_PROTOCOL_CONTRACT.json
- SYNTHETIC_GATE_CONTRACT.json

## Gate final
Le workflow nightly produit `_combined/final_status.json`.

- `final_pass=true` seulement si:
  - dual_proof_status == DUAL_PROOF_COMPLETE
  - synthetic.global_verdict == ACCEPT
  - real_data_fred.global_verdict == ACCEPT
  - validation_protocol_fast.verdict != REJECT

