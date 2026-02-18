# Rapport causal seuil cumulatif

Run: 05_Results/falsification/2026-02-18_batch01/baseline_positive/run_0001

## Verdict

- Verdict: non_detecte
- Binaire (seuil detecte): False

## Seuil et persistence

- threshold_hit_t: None
- threshold_value: -0.009270929705039333
- C_mean_pre: -49.5668
- C_mean_post: -93.5348
- C_mean_post_minus_pre: -43.968
- C_positive_frac_post: 0
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 8.9026e-280
- bootstrap_mean_diff_C: -43.979 (95% CI [-51.9957, -35.6687])

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 6.10604e-46
- lag 2: 5.48583e-15
- lag 3: 5.44397e-07
- lag 4: 0.000249613
- lag 5: 0.017355
- lag 6: 0.055599
- lag 7: 0.349169
- lag 8: 0.720877
- lag 9: 0.928629
- lag 10: 0.98621

Granger delta_C -> S: non calcule

- VAR causality S -> delta_C: p=0.904404 (lag=9)
- Cointegration(C,S): p=0.986444

## Parametres

- alpha: 0.01
- c_mean_post_min: 0.1
- lags: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
- pre_horizon: 500
- post_horizon: 500
- baseline_n: 50
