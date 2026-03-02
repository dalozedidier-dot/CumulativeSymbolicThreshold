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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()

    out_root = Path(args.out_root).resolve()
    run_dir = _find_latest_run(out_root)
    tables = run_dir / "tables"
    figs = run_dir / "figures"
    contracts = run_dir / "contracts"
    manifest = run_dir / "manifest.json"

    for p in [tables, figs, manifest]:
        if not p.exists():
            raise SystemExit(f"Manquant: {p}")

    required_tables = ["ccl_timeseries.csv", "tstar_by_instance.csv", "bootstrap_tstar.csv", "summary.json"]
    for name in required_tables:
        p = tables / name
        if not p.exists():
            raise SystemExit(f"Table manquante: {p}")

    if not (figs / "ccl_mean.png").exists():
        raise SystemExit("Figure manquante: ccl_mean.png")

    # Manifest: vérifier présence tables et figures, et contrats si présents
    m = json.loads(manifest.read_text(encoding="utf-8"))
    files = set(m.get("files", {}).keys())

    expected = {
        "tables/ccl_timeseries.csv",
        "tables/tstar_by_instance.csv",
        "tables/bootstrap_tstar.csv",
        "tables/summary.json",
        "figures/ccl_mean.png",
        "manifest.json",
    }
    # manifest.json n'est pas listé dans lui-même, donc on ne l'exige pas
    expected.discard("manifest.json")

    missing = sorted(expected - files)
    if missing:
        raise SystemExit(f"Manifest incomplet, manque: {missing}")

    # Contrats: si le dossier existe et contient des fichiers, ils doivent être hashés
    if contracts.exists():
        for p in contracts.glob("*"):
            rel = p.relative_to(run_dir).as_posix()
            if rel not in files:
                raise SystemExit(f"Contrat non hashé dans manifest: {rel}")

    print("OK: checks passed (non interpretatif)")


if __name__ == "__main__":
    main()
