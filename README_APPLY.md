Patch v1 — Fix STABILITY_CRITERIA key lookup in qcc_stateprob_stability_battery

Problem
- contracts/STABILITY_CRITERIA.json uses key: "max_relative_variation"
- tools/qcc_stateprob_stability_battery.py was reading: "relative_variation_max"
=> the stability check fell back to default 0.30 even when the contract set 0.305.

Fix
- stability battery now reads:
  max_relative_variation (preferred)
  then relative_variation_max (legacy)
  then 0.30 (fallback)

How to apply
- Unzip at repo root (overwrite allowed).
- Commit + push.
- Re-run the Brisbane full pipeline / densify+stability workflow.
- Verify in runs/<ts>/stability/stability_summary.json:
  stability_check.checks.relative_variation.threshold == 0.305
