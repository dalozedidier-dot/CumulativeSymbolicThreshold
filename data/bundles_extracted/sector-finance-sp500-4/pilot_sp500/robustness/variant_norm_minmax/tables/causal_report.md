# Rapport causal seuil cumulatif

Run: _sector_finance_out/sp500/pilot_sp500/robustness/variant_norm_minmax

## Verdict

- Verdict: seuil_detecte
- Binaire (seuil detecte): True

## Seuil et persistence

- threshold_hit_t: 164
- threshold_value: 0.3464296732718225
- C_mean_pre: 36.2002
- C_mean_post: 63.0622
- C_mean_post_minus_pre: 26.862
- C_positive_frac_post: 1
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 2.32843e-48
- p_value_mannwhitney_C (MWU, one-tailed): nan
- ok_p_source: welch
- bootstrap_mean_diff_C: 26.5952 (95% CI [18.6258, 35.0627])

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 8.12083e-13
- lag 2: 9.14809e-07
- lag 3: 5.26286e-06
- lag 4: 1.53901e-05
- lag 5: 0.000124997

Granger delta_C -> S (p-values par lag)
- lag 1: 0.435862
- lag 2: 0.829016
- lag 3: 0.921446
- lag 4: 0.711804
- lag 5: 0.830928

- VAR causality S -> delta_C: p=2.02935e-13 (lag=1)
- Cointegration(C,S): p=0.973066

## Parametres

- alpha: 0.01
- c_mean_post_min: 0.1
- lags: [1, 2, 3, 4, 5]
- pre_horizon: 80
- post_horizon: 80
- baseline_n: 50

## Critere ok_p (mean shift)

- ok_p: True
- ok_p_source: welch
