# Rapport causal seuil cumulatif

Run: _sector_social_out/twitter_fb/pilot_twitter_fb/robustness/variant_norm_minmax

## Verdict

- Verdict: seuil_detecte
- Binaire (seuil detecte): True

## Seuil et persistence

- threshold_hit_t: 64
- threshold_value: 0.0400684516720409
- C_mean_pre: 1897.78
- C_mean_post: 1911.34
- C_mean_post_minus_pre: 13.5575
- C_positive_frac_post: 1
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 1.12485e-30
- p_value_mannwhitney_C (MWU, one-tailed): nan
- ok_p_source: welch
- bootstrap_mean_diff_C: 13.4852 (95% CI [7.6645, 19.4294])

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 0
- lag 2: 0
- lag 3: 0
- lag 4: 0
- lag 5: 0

Granger delta_C -> S (p-values par lag)
- lag 1: 6.39704e-16
- lag 2: 3.8586e-47
- lag 3: 0.483579
- lag 4: 1
- lag 5: 0.921778

- VAR causality S -> delta_C: p=0 (lag=10)
- Cointegration(C,S): p=0.968223

## Parametres

- alpha: 0.01
- c_mean_post_min: 0.1
- lags: [1, 2, 3, 4, 5]
- pre_horizon: 100
- post_horizon: 100
- baseline_n: 50

## Critere ok_p (mean shift)

- ok_p: True
- ok_p_source: welch
