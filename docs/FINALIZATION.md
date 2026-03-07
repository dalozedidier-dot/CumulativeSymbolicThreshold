# Finalisation ORI-C (interne repo)

Objectif: produire un statut final unique par run nightly, auditables, sans micro-corrections.

Artefact: `_combined/tables/final_status.json`
Règle: pass iff
- dual_proof_status == DUAL_PROOF_COMPLETE
- synthetic.global_verdict == ACCEPT
- real_data_fred.global_verdict == ACCEPT
- validation_protocol.verdict != REJECT

Les contrats vivent dans `contracts/`.
