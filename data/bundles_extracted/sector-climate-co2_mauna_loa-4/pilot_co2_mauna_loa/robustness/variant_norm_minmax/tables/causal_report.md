# Rapport causal seuil cumulatif

Run: _sector_climate_out/co2_mauna_loa/pilot_co2_mauna_loa/robustness/variant_norm_minmax

## Verdict

- Verdict: non_detecte
- Binaire (seuil detecte): False

## Seuil et persistence

- threshold_hit_t: 101
- threshold_value: -0.0463421075666725
- C_mean_pre: 24.9234
- C_mean_post: 17.6442
- C_mean_post_minus_pre: -7.27921
- C_positive_frac_post: 1
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 8.3349e-41
- p_value_mannwhitney_C (MWU, one-tailed): nan
- ok_p_source: welch
- bootstrap_mean_diff_C: -7.12008 (95% CI [-9.78063, -4.48022])

## Causalite

Granger S -> delta_C: non calcule

Granger delta_C -> S: non calcule

- VAR causality S -> delta_C: p=nan (lag=0)
- Cointegration(C,S): p=0.988642

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
