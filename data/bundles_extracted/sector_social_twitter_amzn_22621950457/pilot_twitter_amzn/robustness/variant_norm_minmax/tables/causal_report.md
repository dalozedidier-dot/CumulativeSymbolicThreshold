# Rapport causal seuil cumulatif

Run: _sector_social_out/twitter_amzn/pilot_twitter_amzn/robustness/variant_norm_minmax

## Verdict

- Verdict: indetermine_stats_indisponibles
- Binaire (seuil detecte): False

## Seuil et persistence

- threshold_hit_t: 1
- threshold_value: 0.5196257433522047
- C_mean_pre: 1899.52
- C_mean_post: 1911.42
- C_mean_post_minus_pre: 11.9011
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
- lag 1: 0
- lag 2: 0
- lag 3: 0
- lag 4: 0
- lag 5: 0

Granger delta_C -> S (p-values par lag)
- lag 1: 0
- lag 2: 0
- lag 3: 0
- lag 4: 3.15504e-186
- lag 5: 4.2077e-92

- VAR causality S -> delta_C: p=4.73156e-14 (lag=10)
- Cointegration(C,S): p=0.985805

## Parametres

- alpha: 0.01
- c_mean_post_min: 0.1
- lags: [1, 2, 3, 4, 5]
- pre_horizon: 100
- post_horizon: 100
- baseline_n: 50

## Critere ok_p (mean shift)

- ok_p: False
- ok_p_source: unavailable
