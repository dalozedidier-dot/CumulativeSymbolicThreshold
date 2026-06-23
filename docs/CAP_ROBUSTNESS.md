# Cap(t) robustness gate

`Cap(t)` is a central structural specification because it directly conditions:

- the mismatch `Sigma(t) = max(0, D(t) - Cap(t))`,
- overload diagnostics,
- downstream viability diagnostics,
- collapse-threshold interpretations.

The primary implementation may use:

```text
Cap_product(t) = O(t) * R(t) * I(t)
```

This form is not treated as a final theoretical truth. It is treated as an ex-ante specification that must be tested against reasonable alternatives declared before interpretation.

Canonical alternatives are:

```text
Cap_geometric(t) = (O(t) * R(t) * I(t)) ** (1/3)
Cap_weighted(t)  = 0.4 * O(t) + 0.35 * R(t) + 0.25 * I(t)
Cap_min(t)       = min(O(t), R(t), I(t))
```

A structural result is considered robust only when its mismatch profile and overload diagnostics remain stable across the declared alternatives. If a result depends entirely on one form of `Cap(t)`, it remains specification-sensitive and should not be presented as strongly established.

The executable gate is implemented by:

```bash
python -m oric.cap_robustness --input input.csv --output cap_robustness_report.json
```

The machine-readable criteria are stored in:

```text
contracts/CAP_ROBUSTNESS.json
```
