# Rapport causal seuil cumulatif

Run: _sector_ai_tech_out/llm_scaling/pilot_llm_scaling/robustness/variant_norm_minmax

## Verdict

- Verdict: seuil_detecte
- Binaire (seuil detecte): True

## Seuil et persistence

- threshold_hit_t: 61
- threshold_value: 0.1686531344810257
- C_mean_pre: 6.9881
- C_mean_post: 11.0759
- C_mean_post_minus_pre: 4.08779
- C_positive_frac_post: 1
- no_false_positives_pre: True

## Tests statistiques

- p_value_mean_shift_C (Welch): 5.27468e-12
- p_value_mannwhitney_C (MWU, one-tailed): nan
- ok_p_source: welch
- bootstrap_mean_diff_C: 4.50307 (95% CI [3.82924, 5.1384])

## Causalite

Granger S -> delta_C (p-values par lag)
- lag 1: 4.83944e-05
- lag 2: 0.00208551
- lag 3: 0.00149155
- lag 4: 0.00190377
- lag 5: 0.00866205

Granger delta_C -> S (p-values par lag)
- lag 1: 0.00655435
- lag 2: 0.00496062
- lag 3: 0.00092617
- lag 4: 0.0190309
- lag 5: 0.0261977

- VAR causality S -> delta_C: p=0.00102947 (lag=3)
- Cointegration(C,S): p=0.757788

## Parametres

- alpha: 0.01
- c_mean_post_min: 0.1
- lags: [1, 2, 3, 4, 5]
- pre_horizon: 40
- post_horizon: 40
- baseline_n: 50

## Critere ok_p (mean shift)

- ok_p: True
- ok_p_source: welch
