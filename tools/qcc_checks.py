# tools/qcc_checks.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _find_latest_run(out_root: Path) -> Path:
    latest = out_root / "LATEST_RUN.txt"
    if latest.exists():
        p = Path(latest.read_text(encoding="utf-8").strip())
        if p.exists():
            return p

    runs = sorted((out_root / "runs").glob("*"))
    if not runs:
        raise SystemExit(f"Aucun run trouvé dans {out_root}")
    return runs[-1]


def _check_time_strict(t: np.ndarray) -> None:
    if len(t) < 2:
        return
    dt = np.diff(t)
    if not np.all(dt > 0):
        bad = int(np.sum(dt <= 0))
        raise SystemExit(f"Temps non strictement croissant: {bad} pas invalides")


def check_run(run_dir: Path) -> None:
    tables = run_dir / "tables"
    figs = run_dir / "figures"
    contracts = run_dir / "contracts"
    manifest = run_dir / "manifest.json"

    for p in [tables, figs, contracts, manifest]:
        if not p.exists():
            raise SystemExit(f"Sortie attendue manquante: {p}")

    # Contracts must exist and be hashed
    for p in [contracts / "mapping.json", contracts / "qcc_runs_index.csv"]:
        if not p.exists():
            raise SystemExit(f"Contrat manquant: {p}")

    m = json.loads(manifest.read_text(encoding="utf-8"))
    files = set(m.get("files", {}).keys())
    expected_contracts = {"contracts/mapping.json", "contracts/qcc_runs_index.csv", "tables/summary.json", "tables/events.csv"}
    missing_contracts = sorted(expected_contracts - files)
    if missing_contracts:
        raise SystemExit(f"Manifest incomplet, manque: {missing_contracts}")

    # Summary defines modes per run
    summary = json.loads((tables / "summary.json").read_text(encoding="utf-8"))
    runs = summary.get("runs", {})
    if not isinstance(runs, dict) or not runs:
        raise SystemExit("summary.json: runs missing or empty")

    # Figures: compare_Cq is required
    if not (figs / "compare_Cq.png").exists():
        raise SystemExit("Figure manquante: figures/compare_Cq.png")

    # Per-run checks
    for run_id, info in runs.items():
        mode = str(info.get("mode", "")).strip().lower()
        ts = tables / f"timeseries_{run_id}.csv"
        fig = figs / f"plot_{run_id}.png"
        if not ts.exists():
            raise SystemExit(f"Timeseries manquante: {ts}")
        if not fig.exists():
            raise SystemExit(f"Figure manquante: {fig}")

        df = pd.read_csv(ts)
        if "t" not in df.columns or "Cq" not in df.columns:
            raise SystemExit(f"{ts}: colonnes t et Cq requises")

        if len(df) < 5:
            raise SystemExit(f"{ts}: série trop courte (n < 5)")

        t = df["t"].to_numpy(dtype=float)
        cq = df["Cq"].to_numpy(dtype=float)
        _check_time_strict(t)

        if np.any(np.isnan(cq)):
            raise SystemExit(f"{ts}: NaN détectés dans Cq")

        if mode == "qcc_full":
            for c in ["O", "R", "Sigma"]:
                if c not in df.columns:
                    raise SystemExit(f"{ts}: mode qcc_full requiert colonne {c}")
            sigma = df["Sigma"].to_numpy(dtype=float)
            if np.any(np.isnan(sigma)):
                raise SystemExit(f"{ts}: NaN détectés dans Sigma")
            ds = np.diff(sigma)
            if np.any(ds < -1e-12):
                raise SystemExit(f"{ts}: Sigma non monotone croissante")

        elif mode == "cq_only":
            # Do not require Sigma
            pass
        else:
            raise SystemExit(f"Mode inconnu pour {run_id}: {mode}")

    print("OK: checks passed (non interprétatif, modes supportés)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True, help="Répertoire racine des outputs")
    args = ap.parse_args()

    out_root = Path(args.out_root).resolve()
    run_dir = _find_latest_run(out_root)
    print(f"Checking run_dir={run_dir}")
    check_run(run_dir)


if __name__ == "__main__":
    main()
