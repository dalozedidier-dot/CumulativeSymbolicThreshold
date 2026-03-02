# tools/qcc_checks.py
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


def _find_latest_run(out_root: Path) -> Path:
    latest = out_root / "LATEST_RUN.txt"
    if latest.exists():
        p = Path(latest.read_text(encoding="utf-8").strip())
        if p.exists():
            return p

    runs_dir = out_root / "runs"
    runs = sorted(runs_dir.glob("*")) if runs_dir.exists() else []
    if not runs:
        raise SystemExit(f"Aucun run trouvé dans {out_root}")
    return runs[-1]


def _manifest_files_set(manifest_path: Path) -> set[str]:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    return set(m.get("files", {}).keys())


def _require_any(files: set[str], prefixes: Iterable[str]) -> None:
    for f in files:
        for p in prefixes:
            if f.startswith(p):
                return
    raise SystemExit(f"Manifest incomplet: aucun fichier ne commence par {list(prefixes)}")


def check_run(run_dir: Path) -> None:
    tables = run_dir / "tables"
    figs = run_dir / "figures"
    manifest = run_dir / "manifest.json"

    if not tables.exists():
        raise SystemExit(f"Dossier manquant: {tables}")
    if not figs.exists():
        raise SystemExit(f"Dossier manquant: {figs}")
    if not manifest.exists():
        raise SystemExit(f"Fichier manquant: {manifest}")

    # Exigences minimales, indépendantes du mode (qcc complet ou cq_only)
    summary = tables / "summary.json"
    if not summary.exists():
        raise SystemExit(f"Sortie attendue manquante: {summary}")

    # Au moins un timeseries*.csv (multi-run) OU timeseries.csv (single-run)
    ts_candidates = list(tables.glob("timeseries*.csv"))
    if not ts_candidates:
        raise SystemExit(f"Aucun timeseries*.csv trouvé dans {tables}")

    # Au moins une figure PNG
    pngs = list(figs.glob("*.png"))
    if not pngs:
        raise SystemExit(f"Aucune figure *.png trouvée dans {figs}")

    # Checks sur chaque timeseries
    for ts in ts_candidates:
        df = pd.read_csv(ts)
        if "t" not in df.columns:
            raise SystemExit(f"{ts.name}: colonne 't' manquante")
        t = pd.to_numeric(df["t"], errors="coerce").to_numpy(dtype=float)
        if len(t) < 5:
            raise SystemExit(f"{ts.name}: trop court (n < 5)")
        dt = np.diff(t)
        if not np.all(dt > 0):
            bad = int(np.sum(dt <= 0))
            raise SystemExit(f"{ts.name}: temps non strictement croissant ({bad} pas invalides)")

        # Sigma est requis seulement si présent (mode qcc complet)
        if "Sigma" in df.columns:
            sigma = pd.to_numeric(df["Sigma"], errors="coerce").to_numpy(dtype=float)
            if np.any(np.isnan(sigma)):
                raise SystemExit(f"{ts.name}: NaN détectés dans Sigma")
            ds = np.diff(sigma)
            if np.any(ds < -1e-12):
                raise SystemExit(f"{ts.name}: Sigma non monotone croissante")

    # Vérification manifest: présence des contrats et des sorties minimales
    files = _manifest_files_set(manifest)

    # minimum: summary + au moins un timeseries + au moins un png + contracts/*
    if "tables/summary.json" not in files:
        raise SystemExit("Manifest incomplet, manque: ['tables/summary.json']")

    _require_any(files, prefixes=("tables/timeseries",))
    _require_any(files, prefixes=("figures/",))
    _require_any(files, prefixes=("contracts/",))

    # events: accepté sous plusieurs noms (events.json, events_<run>.json, events.csv)
    # et optionnel pour cq_only. Si aucun fichier events* n'existe, on ne bloque pas.
    # (Mais s'il existe dans le dossier, on veut qu'il soit hashé.)
    disk_events = list(tables.glob("events*"))
    if disk_events:
        _require_any(files, prefixes=("tables/events",))

    print("OK: checks passed (non interprétatif)")


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
