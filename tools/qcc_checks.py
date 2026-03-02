from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_CONTRACTS = {
    "contracts/mapping.json",
    "contracts/qcc_runs_index.csv",
    "contracts/DATA_CONTRACT.md",
}

EXPECTED_FIGURES_MIN = {
    "figures/compare_Cq.png",
}


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


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_run(run_dir: Path) -> None:
    tables = run_dir / "tables"
    figs = run_dir / "figures"
    manifest_path = run_dir / "manifest.json"

    for p in [tables, figs, manifest_path]:
        if not p.exists():
            raise SystemExit(f"Manquant: {p}")

    m = _load_manifest(manifest_path)
    files = set(m.get("files", {}).keys())

    missing_contracts = sorted(EXPECTED_CONTRACTS - files)
    if missing_contracts:
        raise SystemExit(f"Contrats manquants dans manifest: {missing_contracts}")

    missing_figs = sorted(EXPECTED_FIGURES_MIN - files)
    if missing_figs:
        raise SystemExit(f"Figures minimales manquantes dans manifest: {missing_figs}")

    summary_path = tables / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"Manquant: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    runs = summary.get("runs", {})
    if not isinstance(runs, dict) or not runs:
        raise SystemExit("summary.runs absent ou vide")

    # Vérifie chaque run
    for run_id, info in runs.items():
        ts_rel = f"tables/timeseries_{run_id}.csv"
        ev_rel = f"tables/events_{run_id}.json"
        fig_rel = f"figures/plot_{run_id}.png"

        for rel in [ts_rel, ev_rel, fig_rel]:
            if rel not in files:
                raise SystemExit(f"Fichier attendu absent du manifest: {rel}")

        ts_path = run_dir / ts_rel
        df = pd.read_csv(ts_path)

        for col in ["t", "Cq", "O", "R", "Sigma"]:
            if col not in df.columns:
                raise SystemExit(f"Colonne manquante dans {ts_rel}: {col}")

        if len(df) < 5:
            raise SystemExit(f"Run trop court: {run_id} n={len(df)}")

        t = df["t"].to_numpy(dtype=float)
        sigma = df["Sigma"].to_numpy(dtype=float)
        cq = df["Cq"].to_numpy(dtype=float)

        dt = np.diff(t)
        if not np.all(dt > 0):
            raise SystemExit(f"Temps non strictement croissant dans {run_id}")

        ds = np.diff(sigma)
        if np.any(ds < -1e-12):
            raise SystemExit(f"Sigma non monotone dans {run_id}")

        if np.any(np.isnan(cq)) or np.any(np.isnan(sigma)):
            raise SystemExit(f"NaN détectés dans {run_id}")

        # Check de précision: delta U_imp borné par mapping.json
        u_delta = float(info.get("u_imp_abs_delta", 0.0))
        mapping = json.loads((run_dir / "contracts/mapping.json").read_text(encoding="utf-8"))
        allowed = float(mapping.get("o", {}).get("u_imp_max_abs_delta_allowed", 1e9))
        if u_delta > allowed:
            raise SystemExit(f"U_imp delta trop grand dans {run_id}: {u_delta} > {allowed}")

    print("OK: checks passed (contrats, manifest, cohérence mécanique)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()

    out_root = Path(args.out_root).resolve()
    run_dir = _find_latest_run(out_root)
    print(f"Checking run_dir={run_dir}")
    check_run(run_dir)


if __name__ == "__main__":
    main()
