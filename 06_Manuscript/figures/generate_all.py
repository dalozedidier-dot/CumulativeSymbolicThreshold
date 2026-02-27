"""
Génère les 4 figures du manuscrit dans le répertoire courant.
Usage :
    cd 06_Manuscript/figures
    python generate_all.py
"""
import subprocess
import sys
import os

SCRIPTS = [
    "fig1_pipeline_oric.py",
    "fig2_synthetic_threshold.py",
    "fig3_real_fred.py",
    "fig4_tests_table.py",
]

here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)

ok, failed = 0, []
for script in SCRIPTS:
    print(f"  Running {script} …", end=" ", flush=True)
    r = subprocess.run([sys.executable, script], capture_output=True, text=True)
    if r.returncode == 0:
        print("OK")
        ok += 1
    else:
        print("FAILED")
        print(r.stderr[-600:] if r.stderr else "(no stderr)")
        failed.append(script)

print(f"\n{ok}/{len(SCRIPTS)} figures générées.")
if failed:
    print(f"Échecs : {failed}")
    sys.exit(1)
