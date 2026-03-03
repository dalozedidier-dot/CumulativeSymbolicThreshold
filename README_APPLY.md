ORI-C / QCC — Stability contract lock (v1)

Goal
- Make stability criteria deterministic and auditable across CI runs.
- Prevent silent fallback to a default threshold (e.g. 0.300) when a contract is missing.

What this patch adds
1) contracts/STABILITY_CRITERIA.json
   - Sets max_relative_variation to 0.305 (and keeps other mechanical thresholds).
   - Must be versioned in the repo.
2) tools/qcc_stage_stability_criteria.py
   - Copies contracts/STABILITY_CRITERIA.json into runs/<timestamp>/contracts/
   - Optionally records its sha256 into runs/<timestamp>/tables/summary.json
3) tools/qcc_require_stability_criteria.py
   - Fail-fast guard. Exits non-zero if the staged contract is missing.

How to wire into GitHub Actions (recommended)
Insert these steps BEFORE running your stability battery:

  - name: Stage stability criteria into latest run dir
    run: |
      python -m tools.qcc_stage_stability_criteria --out-root _ci_out/qcc_stateprob_full

  - name: Require staged stability criteria (no silent fallback)
    run: |
      python -m tools.qcc_require_stability_criteria --out-root _ci_out/qcc_stateprob_full

And (optional but good):
- After generating stability outputs, regenerate/refresh manifest.json so it hashes the staged contract.
  If you already have a "write manifest" step, keep it AFTER staging.

Notes
- This patch does not recompute any metrics. It only locks the contract and improves traceability.
