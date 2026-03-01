# T9 Cross-domain Diagnostics (non-blocking)

This workflow is intentionally **diagnostic only**.

Rules enforced by design:
- T9 is triggered manually (workflow_dispatch).
- T9 does not write or modify canonical verdicts.
- CI never fails due to T9 (continue-on-error + forced exit 0).
- Output is logs + a simple status file under `_ci_out/t9_diagnostics/`.

If you want T9 to be blocking (but still non-interpretive), create a second workflow with `exit $EXIT_CODE`
and keep the same rule: no ACCEPT/REJECT, no aggregation into global verdicts.
