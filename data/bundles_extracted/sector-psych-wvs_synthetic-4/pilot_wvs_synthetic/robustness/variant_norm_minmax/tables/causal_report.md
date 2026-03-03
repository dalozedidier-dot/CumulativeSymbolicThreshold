# Rapport causal seuil cumulatif

Run: _sector_psych_out/wvs_synthetic/pilot_wvs_synthetic/robustness/variant_norm_minmax

## Verdict

- Verdict: seuil_detecte
- Binaire (seuil detecte): True

## Seuil et persistence

- threshold_hit_t: 70
- threshold_value: -0.0005091326151813
- C_mean_pre: 26.054
- C_mean_post: 29.074
- C_mean_post_minus_pre: 3.01997
- C_positive_frac_post: 1
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 3.36976e-11
- p_value_mannwhitney_C (MWU, one-tailed): nan
- ok_p_source: welch
- bootstrap_mean_diff_C: 2.66023 (95% CI [0.163863, 5.22135])

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 4.46675e-54
- lag 2: 6.54041e-37
- lag 3: 1.99747e-28
- lag 4: 4.94887e-51
- lag 5: 2.8741e-46

Granger delta_C -> S (p-values par lag)
- lag 1: 0.532321
- lag 2: 0.292659
- lag 3: 0.723229
- lag 4: 0.261334
- lag 5: 0.311246

- VAR causality S -> delta_C: p=4.51708e-64 (lag=4)
- Cointegration(C,S): p=0.95226

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
