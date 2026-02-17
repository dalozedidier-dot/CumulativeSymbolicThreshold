#!/usr/bin/env python3
"""run_all.py

Point d'entrée pratique pour exécuter les démos et écrire les sorties dans 05_Results.

Usage:
python run_all.py
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def run(cmd: list[str]) -> None:
    print("\n$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    root = Path(__file__).resolve().parent
    out_oric = root / "05_Results" / "ori_c_demo"
    out_oric.mkdir(parents=True, exist_ok=True)

    run([sys.executable, str(root / "04_Code" / "pipeline" / "run_ori_c_demo.py"), "--outdir", str(out_oric)])
    run([sys.executable, str(root / "04_Code" / "pipeline" / "tests_causaux.py"), "--outdir", str(out_oric)])

    run([sys.executable, str(root / "04_Code" / "pipeline" / "run_synthetic_demo.py"),
         "--input", str(root / "03_Data" / "synthetic" / "synthetic_with_transition.csv"),
         "--outdir", str(root / "05_Results")])

    run([sys.executable, str(root / "04_Code" / "pipeline" / "run_robustness.py"),
         "--input", str(root / "03_Data" / "synthetic" / "synthetic_with_transition.csv"),
         "--outdir", str(root / "05_Results")])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
