# Rapport causal seuil cumulatif

Run: _sector_ai_tech_out/mlperf/pilot_mlperf/robustness/variant_norm_minmax

## Verdict

- Verdict: indetermine_sigma_nul
- Binaire (seuil detecte): False

## Seuil et persistence

- threshold_hit_t: 65
- threshold_value: 0.0428019650018152
- C_mean_pre: 5.22569
- C_mean_post: 5.54217
- C_mean_post_minus_pre: 0.316477
- C_positive_frac_post: 1
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 0.172677
- p_value_mannwhitney_C (MWU, one-tailed): nan
- ok_p_source: welch
- bootstrap_mean_diff_C: 0.254604 (95% CI [-0.332764, 0.805098])
- SIGMA GATE: Sigma(t)=0 throughout post-threshold window: symbolic canal inoperable, cannot falsify H.

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 0.000305262
- lag 2: 0.00155166
- lag 3: 0.000215905
- lag 4: 0.000530292
- lag 5: 0.000956553

Granger delta_C -> S (p-values par lag)
- lag 1: 0.895483
- lag 2: 0.992715
- lag 3: 0.999612
- lag 4: 0.998826
- lag 5: 0.994773

- VAR causality S -> delta_C: p=0.000525246 (lag=5)
- Cointegration(C,S): p=0.807571

## Parametres

- alpha: 0.01
- c_mean_post_min: 0.1
- lags: [1, 2, 3, 4, 5]
- pre_horizon: 40
- post_horizon: 40
- baseline_n: 50

## Critere ok_p (mean shift)

- ok_p: False
- ok_p_source: welch
