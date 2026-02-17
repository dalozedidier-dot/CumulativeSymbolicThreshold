# 04_Code

## Installation pip
pip install -r 04_Code/requirements.txt

## Installation conda
conda env create -f 04_Code/environment.yml
conda activate cumulative_symbolic_threshold

## Démo CSV
python 04_Code/pipeline/run_synthetic_demo.py --input 03_Data/synthetic/synthetic_minimal.csv --outdir 05_Results

## Démo ORI-C (Option B)
python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/ori_c_demo

## Tests
pip install -r 04_Code/requirements-dev.txt
PYTHONPATH=04_Code pytest -q
