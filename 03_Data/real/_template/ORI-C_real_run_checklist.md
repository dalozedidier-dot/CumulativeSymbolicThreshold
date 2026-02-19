ORI-C : premier test reel, checklist minimale

1) Preparer le CSV
- Colonnes minimales : t, O, R, I
- O, R, I doivent etre normalises dans [0,1]
- Optionnel : demand (sinon approx par 0.90 * Cap)
- Optionnel : S0 (condition initiale), sinon S0=0.20

2) Lancer le pipeline ORI-C sur donnees reelles
Exemple :
python 04_Code/pipeline/run_real_data_demo.py   --input 03_Data/real/pilot_001/real.csv   --outdir 05_Results/real/pilot_001/run_0001   --col-O O --col-R R --col-I I --col-demand demand   --auto-scale   --sigma-star 0.0 --tau 500   --k 2.5 --m 3 --baseline-n 50

Sorties :
- tables/real_timeseries_oric.csv
- tables/summary.json
- figures/svc_real.png

3) Lancer les tests causaux et obtenir un verdict
Remarque : tests_causaux.py attend deux CSV. On peut passer le meme fichier en control et test.
python 04_Code/pipeline/tests_causaux.py   --control-csv 05_Results/real/pilot_001/run_0001/tables/real_timeseries_oric.csv   --test-csv    05_Results/real/pilot_001/run_0001/tables/real_timeseries_oric.csv   --outdir      05_Results/real/pilot_001/run_0001   --alpha 0.01 --lags 1-10   --pre-horizon 500 --post-horizon 500   --k 2.5 --m 3 --baseline-n 50   --pdf

Lire :
- tables/verdict.json
- tables/causal_report.md

4) Si pas de seuil detecte
- Verifier l'echelle de O,R,I. Ils doivent etre dans [0,1].
- Ajuster baseline-n (ex 30, 50, 100) selon le bruit.
- Ajuster pre-horizon et post-horizon selon l'echelle temporelle.
- Si C est tres negatif par construction, diminuer --c-mean-post-min ou baser le verdict sur C_mean_post_minus_pre.
