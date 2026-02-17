# Installation de l'environnement ORI C

## Méthode Conda

Créer l'environnement:
```bash
conda env create -f environment.yml
```

Activer:
```bash
conda activate ori_c_framework
```

Vérifier:
```bash
python -c "import numpy; print(numpy.__version__)"
```

## Méthode pip

Créer un environnement virtuel:
```bash
python -m venv ori_c_env
```

Activer.
Linux ou macOS:
```bash
source ori_c_env/bin/activate
```
Windows:
```bash
ori_c_env\Scripts\activate
```

Installer:
```bash
pip install -r requirements.txt
```

## Exécuter les démos

ORI C:
```bash
pip install -r 04_Code/requirements.txt
python 04_Code/pipeline/run_ori_c_demo.py --outdir 05_Results/ori_c_demo
python 04_Code/pipeline/tests_causaux.py --outdir 05_Results/ori_c_demo
```

Robustesse CSV:
```bash
python 04_Code/pipeline/run_robustness.py --input 03_Data/synthetic/synthetic_with_transition.csv --outdir 05_Results
```
