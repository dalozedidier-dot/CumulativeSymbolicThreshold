Ce patch ajoute trois workflows GitHub Actions.

1) CI and Canonical Tests (ci.yml)
Déclenché sur push, pull_request, et workflow_dispatch (bouton Run workflow).

2) Manual ORI-C Runs (manual_runs.yml)
Déclenché via workflow_dispatch, avec choix de suite.

3) Nightly Canonical Run (nightly.yml)
Déclenché par schedule et aussi via workflow_dispatch.

Tous les workflows uploadent un artefact _ci_out contenant logs et résultats.
