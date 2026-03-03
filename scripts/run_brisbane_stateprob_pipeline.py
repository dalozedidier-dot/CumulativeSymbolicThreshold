#!/usr/bin/env python3
"""
scripts/run_brisbane_stateprob_pipeline.py

Workflow complet StateProb Brisbane → cross-conditions → stabilité.

Étapes enchaînées :
  1. Génération des données  (tools/generate_brisbane_stateprob.py)
  2. Analyse cross-conditions (tools/qcc_stateprob_cross_conditions.py)
  3. Batterie de stabilité    (tools/qcc_stateprob_stability_battery.py)

Usages typiques :

  # Simulation numpy locale (aucune dépendance extra) :
  python scripts/run_brisbane_stateprob_pipeline.py

  # Avec DD, variantes de stabilité, et pooling :
  python scripts/run_brisbane_stateprob_pipeline.py \\
      --dd xx --pooling pooled-by-depth --run-variants

  # IBM Brisbane hardware (nécessite qiskit-ibm-runtime) :
  python scripts/run_brisbane_stateprob_pipeline.py \\
      --backend brisbane --ibm-token $IBM_TOKEN \\
      --algo syncidle --dd xx \\
      --depths 1,2,4,6,8,12,16,20,28,40 \\
      --instances 5 --shots 20000 --n-qubits 20

  # Multi-input : plusieurs dossiers de données déjà générées :
  python scripts/run_brisbane_stateprob_pipeline.py \\
      --skip-generate \\
      --dataset-paths data/run_2025_06 data/run_2025_07 \\
      --pooling pooled-by-depth --run-variants

Sorties sous --out-root (défaut : _ci_out/brisbane_pipeline) :
  data/          CSV StateProb générés
  runs/<ts>/     tables, figures, contracts, manifest.json
  stability/     batterie de stabilité (resampling, bootstrap, windowing)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def _run(cmd: List[str], label: str) -> None:
    """Run a subprocess command; raise on failure."""
    print(f"\n{'─'*60}")
    print(f"[{label}]")
    print("$ " + " ".join(cmd))
    print(f"{'─'*60}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nERROR: '{label}' exited with code {result.returncode}.", file=sys.stderr)
        raise SystemExit(result.returncode)


def _latest_run_dir(out_root: Path) -> Optional[Path]:
    runs_dir = out_root / "runs"
    if not runs_dir.exists():
        return None
    candidates = sorted([p for p in runs_dir.iterdir() if p.is_dir()])
    return candidates[-1] if candidates else None


def _print_summary(out_root: Path) -> None:
    """Print final evidence_strength and counters from the latest run's summary.json."""
    run_dir = _latest_run_dir(out_root)
    if not run_dir:
        return
    summary_path = run_dir / "tables" / "summary.json"
    if not summary_path.exists():
        return
    try:
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        pd_ = s.get("power_diagnostic", {})
        det = pd_.get("details", {})
        thr = det.get("thresholds", {})
        h = thr.get("high", {})
        m = thr.get("medium", {})

        print(f"\n{'═'*60}")
        print("RÉSUMÉ PIPELINE")
        print(f"{'═'*60}")
        print(f"  run_dir          : {run_dir}")
        print(f"  evidence_strength: {s.get('evidence_strength', '?').upper()}")
        print(f"  total_points     : {det.get('total_points','?'):>6}  (medium≥{m.get('total_points','?')}, high≥{h.get('total_points','?')})")
        print(f"  depth_distinct   : {det.get('depth_distinct_total','?'):>6}  (medium≥{m.get('depth_distinct_total','?')}, high≥{h.get('depth_distinct_total','?')})")
        print(f"  instances_count  : {det.get('instances_count','?'):>6}  (medium≥{m.get('instances_count','?')}, high≥{h.get('instances_count','?')})")
        print(f"  n_pairs_selected : {s.get('n_pairs_selected','?')}")
        print(f"  pooling_mode     : {s.get('pooling_mode','?')}")

        stab_dir = run_dir / "stability"
        if (stab_dir / "stability_summary.json").exists():
            ss = json.loads((stab_dir / "stability_summary.json").read_text(encoding="utf-8"))
            sc = ss.get("stability_check", {}).get("checks", {})
            all_pass = ss.get("stability_check", {}).get("all_pass")
            print(f"\n  Stabilité checks : {'PASS' if all_pass else 'FAIL' if all_pass is False else 'n/a'}")
            for k, v in sc.items():
                print(f"    {k}: {v}")
            vv = ss.get("versioned_variants", {})
            if vv.get("run"):
                print(f"\n  Variantes versionnées ({vv.get('n_variants')} variantes) :")
                for var in vv.get("variants", []):
                    flag = "✓" if var.get("stability_all_pass") else ("✗" if var.get("stability_all_pass") is False else "?")
                    print(f"    {flag} {var['variant']}  thr={var['threshold']:.3f}  frac={var['subsample_frac']:.2f}")

        print(f"{'═'*60}\n")
    except Exception as e:
        print(f"(Impossible de lire summary.json : {e})")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Workflow complet Brisbane StateProb → cross-conditions → stabilité",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── étape 1 : génération ──────────────────────────────────────────────────
    ap.add_argument("--skip-generate", action="store_true",
                    help="Sauter l'étape de génération (données déjà présentes)")
    ap.add_argument("--backend", default="numpy", choices=["numpy", "aer", "brisbane"],
                    help="Backend de simulation/hardware (défaut: numpy)")
    ap.add_argument("--algo", default="ising", choices=["ising", "syncidle"],
                    help="Type de circuit (défaut: ising)")
    ap.add_argument("--depths",
                    default="2,4,6,8,12,16,20,28,36,48,64,80,100,128,160",
                    help="Profondeurs (Trotter steps ou idle rounds)")
    ap.add_argument("--instances", type=int, default=15,
                    help="Instances par profondeur (défaut: 15)")
    ap.add_argument("--shots", type=int, default=8192,
                    help="Shots par circuit (défaut: 8192)")
    ap.add_argument("--n-qubits", type=int, default=8,
                    help="Nombre de qubits (défaut: 8 ; utiliser 20 pour parité Brisbane)")
    ap.add_argument("--dd", default=None, choices=[None, "xx", "xy4"],
                    help="Séquence Dynamical Decoupling (None=off, xx=X-X, xy4=XY4)")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--ibm-token", default="", help="Token IBM Quantum (requis pour --backend brisbane)")

    # ── multi-input (skip-generate) ───────────────────────────────────────────
    ap.add_argument("--dataset-paths", nargs="*", default=None,
                    help="Chemins datasets supplémentaires (fusionnés avant analyse)")
    ap.add_argument("--dataset-glob", default="",
                    help="Pattern glob pour plusieurs datasets")

    # ── étape 2 : cross-conditions ────────────────────────────────────────────
    ap.add_argument("--pooling", default="pooled-by-depth",
                    choices=["by-instance", "pooled-by-depth", "multi-device"],
                    help="Stratégie de pooling (défaut: pooled-by-depth)")
    ap.add_argument("--metric", default="entropy",
                    choices=["entropy", "impurity", "one_minus_max"])
    ap.add_argument("--threshold", type=float, default=0.70,
                    help="Seuil CCL pour t* (défaut: 0.70)")
    ap.add_argument("--bootstrap-samples", type=int, default=500)
    ap.add_argument("--power-criteria", default="contracts/POWER_CRITERIA.json")

    # ── étape 3 : stabilité ───────────────────────────────────────────────────
    ap.add_argument("--stab-threshold", type=float, default=0.35,
                    help="Seuil t* pour la batterie de stabilité (défaut: 0.35)")
    ap.add_argument("--resamples", type=int, default=50)
    ap.add_argument("--bootstraps", type=int, default=200)
    ap.add_argument("--run-variants", action="store_true", default=False,
                    help="Activer les 3 variantes versionnées de la batterie de stabilité")
    ap.add_argument("--stability-criteria", default="contracts/STABILITY_CRITERIA.json")

    # ── sorties ───────────────────────────────────────────────────────────────
    ap.add_argument("--out-root", default="_ci_out/brisbane_pipeline",
                    help="Répertoire racine des sorties (défaut: _ci_out/brisbane_pipeline)")

    args = ap.parse_args(argv)
    out_root = Path(args.out_root)
    data_dir = out_root / "data"
    py = sys.executable

    print(f"\nPipeline Brisbane StateProb — {datetime.utcnow().isoformat(timespec='seconds')}Z")
    print(f"Backend    : {args.backend}")
    print(f"Algo       : {args.algo.upper()}")
    print(f"Profondeurs: {args.depths}")
    print(f"Instances  : {args.instances}  |  Shots: {args.shots}  |  Qubits: {args.n_qubits}")
    print(f"DD         : {args.dd or 'off'}")
    print(f"Pooling    : {args.pooling}")
    print(f"Out root   : {out_root}\n")

    # ── ÉTAPE 1 : génération ──────────────────────────────────────────────────
    if not args.skip_generate:
        gen_cmd = [
            py, "-m", "tools.generate_brisbane_stateprob",
            "--backend", args.backend,
            "--algo", args.algo,
            "--depths", args.depths,
            "--instances", str(args.instances),
            "--shots", str(args.shots),
            "--n-qubits", str(args.n_qubits),
            "--seed", str(args.seed),
            "--out-dir", str(data_dir),
        ]
        if args.dd:
            gen_cmd += ["--dd", args.dd]
        if args.ibm_token:
            gen_cmd += ["--ibm-token", args.ibm_token]
        _run(gen_cmd, "ÉTAPE 1 — Génération StateProb")
    else:
        print("[ÉTAPE 1 — Génération] Ignorée (--skip-generate)")

    # ── ÉTAPE 2 : cross-conditions ────────────────────────────────────────────
    cross_cmd = [
        py, "-m", "tools.qcc_stateprob_cross_conditions",
        "--out-dir", str(out_root),
        "--pooling", args.pooling,
        "--metric", args.metric,
        "--threshold", str(args.threshold),
        "--bootstrap-samples", str(args.bootstrap_samples),
        "--seed", str(args.seed),
        "--power-criteria", args.power_criteria,
        "--auto-plan",
    ]
    # Assemblage des sources de données
    if not args.skip_generate:
        cross_cmd += ["--dataset", str(data_dir)]
    if args.dataset_paths:
        cross_cmd += ["--dataset-paths"] + list(args.dataset_paths)
    if args.dataset_glob:
        cross_cmd += ["--dataset-glob", args.dataset_glob]
    # Si skip-generate sans dataset-paths ni glob, utilise data_dir si présent
    if args.skip_generate and not args.dataset_paths and not args.dataset_glob:
        if data_dir.exists():
            cross_cmd += ["--dataset", str(data_dir)]
        else:
            print(f"AVERTISSEMENT: --skip-generate mais {data_dir} absent et aucun --dataset-paths fourni.",
                  file=sys.stderr)

    _run(cross_cmd, "ÉTAPE 2 — Cross-conditions (CCL vs Depth)")

    # ── ÉTAPE 3 : batterie de stabilité ──────────────────────────────────────
    run_dir = _latest_run_dir(out_root)
    if run_dir is None:
        print("ERROR: aucun run trouvé après l'étape 2.", file=sys.stderr)
        return 1

    stab_cmd = [
        py, "-m", "tools.qcc_stateprob_stability_battery",
        "--out-root", str(out_root),
        "--run-dir", str(run_dir),
        "--threshold", str(args.stab_threshold),
        "--resamples", str(args.resamples),
        "--bootstraps", str(args.bootstraps),
        "--seed", str(args.seed),
        "--stability-criteria", args.stability_criteria,
    ]
    if args.run_variants:
        stab_cmd.append("--run-variants")
    _run(stab_cmd, "ÉTAPE 3 — Batterie de stabilité")

    # ── Résumé final ──────────────────────────────────────────────────────────
    _print_summary(out_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
