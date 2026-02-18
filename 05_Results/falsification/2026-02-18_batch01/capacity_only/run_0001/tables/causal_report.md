# Rapport causal seuil cumulatif

Run: 05_Results/falsification/2026-02-18_batch01/capacity_only/run_0001

## Verdict

- Verdict: non_detecte
- Binaire (seuil detecte): False

## Seuil et persistence

- threshold_hit_t: None
- threshold_value: -0.009270929705039333
- C_mean_pre: -47.597
- C_mean_post: -79.2994
- C_mean_post_minus_pre: -31.7024
- C_positive_frac_post: 0
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 1.23125e-209
- bootstrap_mean_diff_C: -31.4316 (95% CI [-38.9026, -24.2988])

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 8.70058e-05
- lag 2: 0.0813875
- lag 3: 0.42578
- lag 4: 0.693152
- lag 5: 0.902057
- lag 6: 0.931428
- lag 7: 0.988785
- lag 8: 0.997555
- lag 9: 0.999407
- lag 10: 0.999824

Granger delta_C -> S: non calcule

- VAR causality S -> delta_C: p=0.991852 (lag=10)
- Cointegration(C,S): p=0.986223

## Parametres

- alpha: 0.01
- c_mean_post_min: 0.1
- lags: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
- pre_horizon: 500
- post_horizon: 500
- baseline_n: 50
