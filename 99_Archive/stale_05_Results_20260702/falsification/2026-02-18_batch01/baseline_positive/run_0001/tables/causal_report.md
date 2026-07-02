# Rapport causal seuil cumulatif

Run: 05_Results/falsification/2026-02-18_batch01/baseline_positive/run_0001

## Verdict

- Verdict: seuil_detecte
- Binaire (seuil detecte): True

## Seuil et persistence

- threshold_hit_t: 904
- threshold_value: -0.0091857181971893
- C_mean_pre: -29.7037
- C_mean_post: 21.91
- C_mean_post_minus_pre: 51.6137
- C_positive_frac_post: 0.662
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 1.91832e-108
- bootstrap_mean_diff_C: 51.2762 (95% CI [34.1489, 67.275])

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 1.2715e-24
- lag 2: 4.24521e-141
- lag 3: 1.37308e-186
- lag 4: 1.13912e-178
- lag 5: 6.50444e-178
- lag 6: 1.11409e-151
- lag 7: 1.26972e-159
- lag 8: 2.40807e-162
- lag 9: 1.16865e-161
- lag 10: 6.04848e-163

Granger delta_C -> S (p-values par lag)
- lag 1: 1.03214e-62
- lag 2: 0.170417
- lag 3: 0.000809193
- lag 4: 0.351072
- lag 5: 0.473401
- lag 6: 0.467904
- lag 7: 0.641022
- lag 8: 0.610881
- lag 9: 0.477021
- lag 10: 0.848886

- VAR causality S -> delta_C: p=4.40859e-178 (lag=10)
- Cointegration(C,S): p=0.990927

## Parametres

- alpha: 0.01
- c_mean_post_min: 0.1
- lags: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
- pre_horizon: 500
- post_horizon: 500
- baseline_n: 50
