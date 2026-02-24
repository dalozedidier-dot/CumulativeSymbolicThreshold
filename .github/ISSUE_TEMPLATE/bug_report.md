---
name: Bug Report
about: Report a reproducibility failure, incorrect verdict, or pipeline error
title: "[BUG] <brief description>"
labels: bug
assignees: ''
---

## Summary

A clear one-sentence description of the problem.

---

## Reproduction steps

```bash
# Exact commands to reproduce
python 04_Code/pipeline/...
```

Include:
- Python version: `python --version`
- Package versions: `pip freeze | grep -E "numpy|pandas|scipy|statsmodels"`
- Operating system:
- Seed used (if applicable): `--seed <value>`

---

## Expected behaviour

What should have happened?

---

## Actual behaviour

What actually happened? Paste the relevant error output:

```
<error message or unexpected output here>
```

---

## Output files

If the run produced output files, attach or paste the relevant ones:
- `verdict.txt` content:
- `tables/summary.json` relevant fields:
- `tables/verdict.json` relevant fields (for real-data runs):

---

## Normative impact assessment

- [ ] This bug affects a **primary verdict** (T1–T8 accept/reject)
- [ ] This bug affects **robustness analysis only** (secondary)
- [ ] This bug is a **UI/logging issue** (no impact on verdict)
- [ ] This bug is a **reproducibility failure** (same seed → different result)

---

## Additional context

Any other relevant information (e.g., known dataset quirks, recent code changes, CI log link).
