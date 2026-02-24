# Contributing to ORI-C

Thank you for your interest in contributing to the Cumulative Symbolic Threshold project.
This document describes the contribution process, PR checklist, and reviewer expectations.

---

## Core principles (non-negotiable)

1. **Keep the framework falsifiable and pre-registerable.**
   Every addition must be testable without post-hoc adjustment.
   New model parameters require a new pre-registration entry in `02_Protocol/PREREG_TEMPLATE.md`.

2. **Separate decisional definitions from robustness analyses.**
   Robustness tests are secondary and never change primary verdict.
   Do not move a robustness result into the primary decision path.

3. **Avoid circularity** between V(t), S(t), and C(t).
   These must remain causally independent — no feedback loops between them.

4. **Add a minimal example** whenever introducing a new concept or script.

5. **Never modify parameters after observing data.**
   Any parameter change is a new pre-registration. Document it in `CHANGELOG.md`.

6. **Null and negative results are first-class.** Report them at equal status.

---

## PR checklist

Before opening a pull request, verify all items below:

### Correctness
- [ ] Code runs without error: `PYTHONPATH=04_Code pytest -q`
- [ ] All existing tests pass (no regressions)
- [ ] If a new pipeline script is added, it produces `verdict.txt` with a valid token (`ACCEPT`, `REJECT`, or `INDETERMINATE`)
- [ ] Frozen dataclasses (`ORICConfig`, `PreregSpec`, `ProxySpec`) are not mutated — only reconstructed
- [ ] Seeds are fixed and logged in every new simulation run

### Normative compliance
- [ ] No new parameter was calibrated on observed data
- [ ] `Cap(t) = O(t) · R(t) · I(t)` is unchanged in the main path (robustness variants are allowed in secondary scripts only)
- [ ] Significance level α = 0.01 is preserved (not 0.05)
- [ ] If a new real-data source is added, a `proxy_spec.json` is included and passes `validate_proxy_spec.py`
- [ ] Decision hierarchy (Welch → bootstrap → MWU → INDETERMINATE) is not altered

### Documentation
- [ ] `CHANGELOG.md` updated with a meaningful entry under the correct version section
- [ ] New public functions have a one-line docstring
- [ ] New pipeline scripts are listed in `CLAUDE.md` and `README.md` if they are primary entry points

### CI
- [ ] The `ci.yml` smoke test passes locally (or on the PR branch)
- [ ] No ephemeral output files committed (`_ci_out/`, `_demo_out/`, `_tmp_results_ci/`, `05_Results/`)

---

## Reviewer guide

When reviewing a PR, check:

1. **Does it break the normative chain?**
   Verify Cap form, α level, and verdict token set are unchanged.

2. **Is the test falsifiable?**
   Any new test must have an explicit falsification condition (what outcome rejects the claim?).

3. **Are seeds reproducible?**
   New simulation scripts must have `--seed` with a default and log it.

4. **Is the proxy spec complete?**
   Any new real-data integration needs `proxy_spec.json` with all required fields and direction annotations.

5. **Is the verdict output canonical?**
   `verdict.txt` must contain exactly one of: `ACCEPT`, `REJECT`, `INDETERMINATE`.

---

## Proposing a new dataset

To propose a new real-data pilot sector:

1. Open an issue using the **Dataset Proposal** template (`.github/ISSUE_TEMPLATE/dataset_proposal.md`)
2. Describe the sector, available proxies, and their proposed O/R/I mapping
3. Include a `proxy_spec.json` draft with `fragility_note` and `manipulability_note` for each column
4. The dataset must have at least 50 observations and pre-normalised [0, 1] proxies

Good candidate sectors: health systems, climate/ecology, cognitive load, social media dynamics, transport networks.

---

## Good first issues

Look for issues labelled `good-first-issue`. Examples:
- Add a new plot type to an existing pipeline script (e.g. Σ(t) over time)
- Write a unit test for a currently untested function in `src/oric/`
- Improve a docstring or add a type annotation to a public function
- Propose a new synthetic scenario (new intervention type in `ORICConfig`)

---

## Branch conventions

| Branch prefix | Purpose |
|--------------|---------|
| `feature/xxx` | New feature or enhancement |
| `fix/xxx` | Bug fix |
| `docs/xxx` | Documentation only |
| `refactor/xxx` | Internal restructuring (no behaviour change) |

All PRs target `main`. Do not force-push to `main`.

---

## Contact

For questions about the theoretical framework or pre-registration, see the
[OSF pre-registration (G62PZ)](https://osf.io/g62pz/).
For code issues, open a GitHub issue.
