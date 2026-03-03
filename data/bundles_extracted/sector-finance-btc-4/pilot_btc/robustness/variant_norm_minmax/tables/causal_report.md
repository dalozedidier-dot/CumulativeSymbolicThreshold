# Rapport causal seuil cumulatif

Run: _sector_finance_out/btc/pilot_btc/robustness/variant_norm_minmax

## Verdict

- Verdict: non_detecte
- Binaire (seuil detecte): False

## Seuil et persistence

- threshold_hit_t: 76
- threshold_value: 0.0126272511909243
- C_mean_pre: 22.7311
- C_mean_post: 24.281
- C_mean_post_minus_pre: 1.54987
- C_positive_frac_post: 1
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 1.54322e-06
- p_value_mannwhitney_C (MWU, one-tailed): nan
- ok_p_source: welch
- bootstrap_mean_diff_C: 1.33126 (95% CI [-0.520295, 3.33724])

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 4.27963e-08
- lag 2: 4.53056e-07
- lag 3: 1.01211e-05
- lag 4: 2.14734e-05
- lag 5: 1.19397e-05

Granger delta_C -> S (p-values par lag)
- lag 1: 0.734202
- lag 2: 0.158867
- lag 3: 0.121627
- lag 4: 0.173916
- lag 5: 0.074314

- VAR causality S -> delta_C: p=1.55063e-05 (lag=4)
- Cointegration(C,S): p=0.881275

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
