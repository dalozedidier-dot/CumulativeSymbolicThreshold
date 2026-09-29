# T6 sensitivity gate

The single-series helper is a numerical diagnostic, not a causal experiment.
Its schema v2 result always reports `INDETERMINATE` and
`confirmatory_eligible: false`. This supersedes the single-series ACCEPT/REJECT
interpretation in T6_CUT_SSPEC_v1 without modifying DECISION_RULES_v2 or its
confirmatory aggregation.

Run the installed synthetic lineage fixture:

```console
python 04_Code/sector/bio/run_t6_cut.py --csv examples/t6_lineage_synthetic.csv --spec contracts/s_spec_lineage_synthetic.json --sham permute_cap --outdir 05_Results/t6_cut/lineage_synthetic
```

The intact C is 19 and the transformed C is zero. The expected verdict is
INDETERMINATE, because zeroing S mechanically zeros C. This is a regression
fixture, not LTEE data or biological validation.

Missing or invalid SSpec, missing V, non-finite inputs and unsupported generation
resets produce `diagnostic_status: not_computed`. The CLI never substitutes Cap
for V. Unavailable numeric fields are JSON null, not NaN. Omitting `--spec` is
supported so the missing-contract gate can be exercised end to end.

Computed diagnostics preserve contrasts and expose a descriptive threshold
using 0.30 times the robust dispersion of the intact C trajectory. This is not
the confirmatory baseline SESOI. A constant C has no estimated scale and no
threshold. Changing S units cannot change the diagnostic threshold.

`reset_generation` is refused until generation boundaries and an explicit
reset model exist. Mean-centering is not a generation reset. Delay operators
preserve length even when the delay exceeds the series length.

The regression tests run in the existing smoke tier. No hook into the
confirmatory suite, no empirical lineage claim and no global aggregation change
are included in this installation.
