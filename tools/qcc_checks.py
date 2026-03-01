# tools/qcc_checks.py
from __future__ import annotations

import argparse
import json
from pathlib import Path


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


def _expect(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Sortie attendue manquante: {path}")


def check_run(run_dir: Path) -> None:
    tables = run_dir / "tables"
    figs = run_dir / "figures"
    manifest = run_dir / "manifest.json"

    _expect(tables)
    _expect(figs)
    _expect(manifest)

    summary = tables / "summary.json"
    _expect(summary)

    s = json.loads(summary.read_text(encoding="utf-8"))
    runs = s.get("runs", [])
    if not isinstance(runs, list) or len(runs) == 0:
        raise SystemExit("summary.json: runs vide")

    # checks per run
    for r in runs:
        run_id = r.get("run_id")
        if not run_id:
            raise SystemExit("summary.json: run_id manquant")
        _expect(tables / f"timeseries_{run_id}.csv")
        _expect(tables / f"events_{run_id}.json")
        _expect(figs / f"plot_{run_id}.png")

    # compare plot optional, but recommended
    _expect(figs / "compare_Cq.png")

    # manifest content minimal
    m = json.loads(manifest.read_text(encoding="utf-8"))
    files = set(m.get("files", {}).keys())
    if "tables/summary.json" not in files:
        raise SystemExit("manifest.json: tables/summary.json manquant")
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
