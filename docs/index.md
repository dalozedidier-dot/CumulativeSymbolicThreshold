# ORI-C — Cumulative Symbolic Threshold

**A pre-registered, falsifiable scientific framework** for testing the ORI-C hypothesis:
beyond a critical threshold of symbolic accumulation, the symbolic transmission channel
becomes self-reinforcing — a measurable phase transition.

## Quick navigation

| Document | Description |
|----------|-------------|
| [Installation](installation.md) | pip, conda, Docker setup |
| [Reproduction](REPRODUCE.md) | Seeds, manifests, full reproducibility |
| [CI Pipelines](CI_PIPELINES.md) | Workflow reference (CI, nightly, collector) |
| [Symbolic Tests](SYMBOLIC_TESTS.md) | T1–T8 test descriptions |
| [Repository Layout](REPO_LAYOUT.md) | Directory structure and sources of truth |
| [Point of Truth](ORI_C_POINT_OF_TRUTH.md) | Canonical normative reference |

## API Reference

| Module | Description |
|--------|-------------|
| [ori_core](api/ori_core.md) | Cap(t), Sigma(t), V(t) computations |
| [symbolic](api/symbolic.md) | S(t), C(t), threshold detection |
| [decision](api/decision.md) | NaN-safe hierarchical verdict engine |
| [proxy_spec](api/proxy_spec.md) | Versioned, hashable column mapping |
| [prereg](api/prereg.md) | Frozen ex-ante parameter spec |
| [randomization](api/randomization.md) | Seed management |

## Links

- [GitHub Repository](https://github.com/dalozedidier-dot/CumulativeSymbolicThreshold)
- [OSF Pre-registration](https://osf.io/g62pz/)
- [DOI: 10.17605/OSF.IO/G62PZ](https://doi.org/10.17605/OSF.IO/G62PZ)
