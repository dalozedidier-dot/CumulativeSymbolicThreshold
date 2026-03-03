# Rapport causal seuil cumulatif

Run: _sector_climate_out/gistemp/pilot_gistemp/robustness/variant_norm_minmax

## Verdict

- Verdict: indetermine_stats_indisponibles
- Binaire (seuil detecte): False

## Seuil et persistence

- threshold_hit_t: 1
- threshold_value: 0.3723999981223534
- C_mean_pre: 34.6748
- C_mean_post: 46.0148
- C_mean_post_minus_pre: 11.34
- C_positive_frac_post: 1
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): nan
- p_value_mannwhitney_C (MWU, one-tailed): nan
- ok_p_source: unavailable
- bootstrap_mean_diff_C: nan (95% CI [nan, nan])
- SIGMA GATE: All p-value sources unavailable (Welch NaN, bootstrap NaN, MWU NaN): INDETERMINATE per WELCH_NAN_FALLBACK_POLICY.

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 4.37701e-30
- lag 2: 4.57839e-08
- lag 3: 1.64731e-06
- lag 4: 5.97839e-06
- lag 5: 1.61175e-05

Granger delta_C -> S (p-values par lag)
- lag 1: 4.07227e-05
- lag 2: 0.501044
- lag 3: 0.797608
- lag 4: 0.970586
- lag 5: 0.985051

- VAR causality S -> delta_C: p=4.29217e-06 (lag=4)
- Cointegration(C,S): p=0.66566

## Parametres

- alpha: 0.01
- c_mean_post_min: 0.1
- lags: [1, 2, 3, 4, 5]
- pre_horizon: 80
- post_horizon: 80
- baseline_n: 50

## Critere ok_p (mean shift)

- ok_p: False
- ok_p_source: unavailable
