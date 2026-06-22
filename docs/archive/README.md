# docs/archive — frozen historical reports

This directory holds **one-off, point-in-time documents** that were once at the
repository root. They are kept for provenance only and are **not maintained**.
Nothing in the codebase links to them, and they should not be treated as current
status.

For the live picture, use these instead:

| You want… | Look at |
|---|---|
| Current evidentiary state | [`../EVIDENTIARY_STATUS.md`](../EVIDENTIARY_STATUS.md), [`../EVIDENCE_LADDER.md`](../EVIDENCE_LADDER.md) |
| What changed and when | [`../../CHANGELOG.md`](../../CHANGELOG.md) |
| The single source of truth | [`../ORI_C_POINT_OF_TRUTH.md`](../ORI_C_POINT_OF_TRUTH.md) |
| Repository health checks | `python -m tools.repo_doctor` |
| Periodic check-ups / ops notes | [`../maintenance/`](../maintenance/) |

## Contents

| File | What it was |
|---|---|
| `CLEANUP_REPORT.txt` | Log of a one-off conservative cache-cleanup pass. |
| `ori-c-nightly-22811379618.md` | A single nightly run dump (`DUAL_PROOF_INCOMPLETE`). Superseded by every later nightly artifact. |
| `PATCH_NOTES_CORRECTION.md` | Notes on the trend-vs-transition detector correction. The substance is folded into the `CHANGELOG.md` *Unreleased* section and `02_Protocol/PREREG_ADDENDUM_2026-06_ACCUMULATION_SURROGATE.md`. |
