# ORI-C threshold validation overview (2026-02-18)

Files:
- 2026-02-18_overview.csv (concat of all batches)
- Each batch folder contains per-run figures and tables.

Top runs by persistence then C_mean_post:

| batch | seed | intervention | sigma_star | tau | demand_noise | ori_trend | threshold_hit_t | C_mean_post | C_positive_frac_post | effect_C_post_mean | p_value_C_post_mean |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-02-18_oric_batchB | 2102 | demand_shock | 120 | 800 | 0.03 | 0.0005 | 911 | 22.66 | 0.6633 | 178.6 | 0 |
| 2026-02-18_oric_batchA | 1101 | demand_shock | 0 | 400 | 0.03 | 0 | 910 | 11.1 | 0.6267 | 168.2 | 0 |
| 2026-02-18_oric_batchB | 2101 | demand_shock | 120 | 800 | 0.03 | 0.0005 | 923 | 12.1 | 0.605 | 179.4 | 0 |
| 2026-02-18_oric_batchB | 2103 | demand_shock | 120 | 800 | 0.03 | 0.0005 | 919 | 11.69 | 0.6 | 176.8 | 0 |
| 2026-02-18_oric_batchB | 2100 | demand_shock | 120 | 800 | 0.03 | 0.0005 | 912 | 11.16 | 0.595 | 174.5 | 0 |
| 2026-02-18_oric_batchA | 1102 | demand_shock | 0 | 400 | 0.03 | 0 | 908 | -6.346 | 0.5217 | 169 | 0 |
| 2026-02-18_oric_batchA | 1103 | demand_shock | 0 | 400 | 0.03 | 0 | 907 | -10.36 | 0.4917 | 168.9 | 0 |
| 2026-02-18_oric_batchA | 1100 | demand_shock | 0 | 400 | 0.03 | 0 | 905 | -14.58 | 0.4617 | 170 | 0 |
| 2026-02-18_oric_batchC | 3100 | demand_shock | 150 | 600 | 0.08 | -0.0005 |  | -72.2 | 0 | 4.161 | 0.008694 |
| 2026-02-18_oric_batchC | 3103 | demand_shock | 150 | 600 | 0.08 | -0.0005 |  | -97.95 | 0 | 4.061 | 0.0138 |
| 2026-02-18_oric_batchC | 3102 | demand_shock | 150 | 600 | 0.08 | -0.0005 |  | -99.54 | 0 | 4.182 | 0.01141 |
| 2026-02-18_oric_batchC | 3101 | demand_shock | 150 | 600 | 0.08 | -0.0005 |  | -108.4 | 0 | 4.305 | 0.01006 |
