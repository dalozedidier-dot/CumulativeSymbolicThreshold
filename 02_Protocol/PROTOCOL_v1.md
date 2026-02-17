# PROTOCOL v1

Version: v1  
Date: 2026-02-17

## Scope
This protocol tests a transition toward a cumulative symbolic regime operationalized with O, R, I, viability V(t), mismatch Σ(t), symbolic stock S(t), symbolic efficiency s(t), and order parameter C(t).

## Hypotheses
H1 Activation:
External cycle is active if Σ(t) > Σ* for at least τ.

H2 Regime shift:
C(t) exhibits a robust regime change at a threshold, with transition signatures.

H3 Causality:
Perturbing the symbolic channel reduces V(t) reproducibly in the cumulative regime.

H4 Hysteresis:
Reversal requires stronger parameter change than the one producing the shift.

## Primary threshold criterion
ΔC(t) = C(t) - C(t-1)
Threshold crossed if ΔC(t) > μ_ΔC + k·σ_ΔC for m consecutive steps.
Reference period for μ_ΔC and σ_ΔC is preregistered.
k and m are fixed ex ante.

## Designs
Mechanistic simulation, experimental or quasi experimental, and instrumented historical time series are acceptable, with one primary design preregistered.

## Interventions and controls
See 02_Protocol/INTERVENTIONS_CATALOG.md.

## Reproducibility
Fixed seeds, pinned dependencies, run logs, and a minimal synthetic dataset are provided.
