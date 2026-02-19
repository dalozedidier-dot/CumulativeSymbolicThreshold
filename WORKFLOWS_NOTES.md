Ce patch ajoute trois workflows GitHub Actions.

1) CI and Canonical Tests (ci.yml)
Déclenché sur push, pull_request, et workflow_dispatch (bouton Run workflow).

2) Manual ORI-C Runs (manual_runs.yml)
Déclenché via workflow_dispatch, avec choix de suite.

3) Nightly Canonical Run (nightly.yml)
Déclenché par schedule et aussi via workflow_dispatch.

Tous les workflows uploadent un artefact _ci_out contenant logs et résultats.

## Real data smoke workflow
Workflow: .github/workflows/real_data_smoke.yml

But:
- Valider que le pipeline fonctionne sur une serie reelle au format CSV.
- Produire un artefact avec les tables, figures, verdicts et un manifest sha256.
- Executable en automatique sur changements de code ou de donnees reelles, et a la demande via Run workflow.

Dataset par defaut:
- 03_Data/real/pilot_cpi/real.csv
