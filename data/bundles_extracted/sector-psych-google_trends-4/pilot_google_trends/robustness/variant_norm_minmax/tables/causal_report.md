# Rapport causal seuil cumulatif

Run: _sector_psych_out/google_trends/pilot_google_trends/robustness/variant_norm_minmax

## Verdict

- Verdict: non_detecte
- Binaire (seuil detecte): False

## Seuil et persistence

- threshold_hit_t: 78
- threshold_value: 0.0019925306886866
- C_mean_pre: 23.5156
- C_mean_post: 24.5896
- C_mean_post_minus_pre: 1.07397
- C_positive_frac_post: 1
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 6.85376e-05
- p_value_mannwhitney_C (MWU, one-tailed): nan
- ok_p_source: welch
- bootstrap_mean_diff_C: 0.890892 (95% CI [-0.597998, 2.52535])

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 3.71174e-07
- lag 2: 0.000859483
- lag 3: 0.0175509
- lag 4: 0.0477636
- lag 5: 0.0650851

Granger delta_C -> S (p-values par lag)
- lag 1: 0.410357
- lag 2: 0.680788
- lag 3: 0.812947
- lag 4: 0.932889
- lag 5: 0.9574

- VAR causality S -> delta_C: p=0.0167635 (lag=3)
- Cointegration(C,S): p=0.882844

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
