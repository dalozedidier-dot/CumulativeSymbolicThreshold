from __future__ import annotations

import argparse
import json
import math
import os
import re
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from make_manifest import write_manifest_sha256


STATES_RE = re.compile(r"STATES_(?P<device>.+?)_(?P<algo>[A-Za-z0-9]+)_(?P<instance>[0-9]+)_(?P<shots>[0-9]+)\.csv$")
ATTR_RE = re.compile(r"ATTR_(?P<device>.+?)_(?P<algo>[A-Za-z0-9]+)_(?P<instance>[0-9]+)_(?P<shots>[0-9]+)\.csv$")


@dataclass
class Inputs:
    dataset_zip: str
    algo: str
    device: str
    shots: str
    t_axis: str
    ccl_metric: str
    ccl_threshold: float
    bootstrap_samples: int
    out_root: str


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _read_probs_csv(path: Path) -> Dict[str, float]:
    df = pd.read_csv(path)
    # Colonnes attendues: "States" et "Probability" ou variantes
    cols = {c.lower(): c for c in df.columns}
    state_col = cols.get("states") or cols.get("state") or df.columns[0]
    prob_col = cols.get("probability") or cols.get("prob") or df.columns[-1]
    probs: Dict[str, float] = {}
    for _, row in df.iterrows():
        s = str(row[state_col]).strip()
        p = float(row[prob_col])
        if p < 0:
            continue
        probs[s] = probs.get(s, 0.0) + p
    # Normalisation douce
    total = sum(probs.values())
    if total > 0:
        probs = {k: v / total for k, v in probs.items()}
    return probs


def _bitstring_len(probs: Dict[str, float]) -> int:
    if not probs:
        return 0
    k = max(probs.keys(), key=len)
    return len(k)


def _entropy_norm(probs: Dict[str, float]) -> float:
    n = _bitstring_len(probs)
    if n <= 0:
        return float("nan")
    h = 0.0
    for p in probs.values():
        if p <= 0:
            continue
        h -= p * math.log(p)
    hmax = math.log(2 ** n)
    return float(h / hmax) if hmax > 0 else float("nan")


def _one_minus_maxprob(probs: Dict[str, float]) -> float:
    if not probs:
        return float("nan")
    return float(1.0 - max(probs.values()))


def _one_minus_purity(probs: Dict[str, float]) -> float:
    if not probs:
        return float("nan")
    purity = sum(p * p for p in probs.values())
    return float(1.0 - purity)


def _compute_ccl(probs: Dict[str, float], metric: str) -> float:
    metric = metric.strip().lower()
    if metric == "entropy":
        return _entropy_norm(probs)
    if metric == "one_minus_maxprob":
        return _one_minus_maxprob(probs)
    if metric == "one_minus_purity":
        return _one_minus_purity(probs)
    raise SystemExit(f"Metric Ccl inconnue: {metric}")


def _read_attr_t(path: Path, t_axis: str) -> float:
    df = pd.read_csv(path)
    if t_axis not in df.columns:
        # tolérer casing
        cols = {c.lower(): c for c in df.columns}
        alt = cols.get(t_axis.lower())
        if alt:
            t_axis = alt
        else:
            raise SystemExit(f"Colonne t_axis={t_axis} absente dans {path.name}. Colonnes: {list(df.columns)}")
    # Fichiers ATTR semblent être une seule ligne
    val = float(df.iloc[0][t_axis])
    return val


def _collect_pairs(root: Path, algo_filter: str, device_sub: str, shots_filter: str) -> List[Tuple[dict, Path, Path]]:
    states_files: List[Tuple[dict, Path]] = []
    attr_files: List[Tuple[dict, Path]] = []

    for p in root.rglob("*.csv"):
        m = STATES_RE.search(p.name)
        if m:
            meta = m.groupdict()
            states_files.append((meta, p))
            continue
        m = ATTR_RE.search(p.name)
        if m:
            meta = m.groupdict()
            attr_files.append((meta, p))

    # Index ATTR par clé
    attr_index: Dict[Tuple[str, str, str, str], Path] = {}
    for meta, p in attr_files:
        key = (meta["device"], meta["algo"], meta["instance"], meta["shots"])
        attr_index[key] = p

    pairs: List[Tuple[dict, Path, Path]] = []
    for meta, st_path in states_files:
        if algo_filter and meta["algo"] != algo_filter:
            continue
        if shots_filter and meta["shots"] != shots_filter:
            continue
        if device_sub and device_sub not in meta["device"]:
            continue
        key = (meta["device"], meta["algo"], meta["instance"], meta["shots"])
        at_path = attr_index.get(key)
        if not at_path:
            continue
        pairs.append((meta, st_path, at_path))

    return pairs


def _bootstrap_tstar(tstars: np.ndarray, n_boot: int, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    tstars = tstars[~np.isnan(tstars)]
    if len(tstars) == 0:
        return {"n": 0}
    boots = []
    for _ in range(int(n_boot)):
        samp = rng.choice(tstars, size=len(tstars), replace=True)
        boots.append(float(np.nanmedian(samp)))
    boots = np.array(boots, dtype=float)
    return {
        "n": int(len(tstars)),
        "bootstrap_samples": int(n_boot),
        "median_of_medians": float(np.nanmedian(boots)),
        "ci_05": float(np.nanpercentile(boots, 5)),
        "ci_95": float(np.nanpercentile(boots, 95)),
    }


def run(inp: Inputs) -> Path:
    out_root = Path(inp.out_root).resolve()
    run_dir = out_root / "runs" / _now_tag()
    tables_dir = run_dir / "tables"
    figs_dir = run_dir / "figures"
    contracts_dir = run_dir / "contracts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figs_dir.mkdir(parents=True, exist_ok=True)
    contracts_dir.mkdir(parents=True, exist_ok=True)

    dataset_zip = Path(inp.dataset_zip)
    if not dataset_zip.exists():
        raise SystemExit(f"dataset_zip introuvable: {dataset_zip}")

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        with zipfile.ZipFile(dataset_zip, "r") as zf:
            zf.extractall(td_path)

        pairs = _collect_pairs(td_path, inp.algo.strip(), inp.device.strip(), inp.shots.strip())
        if not pairs:
            raise SystemExit("Aucun couple STATES/ATTR trouvé avec les filtres fournis.")

        rows = []
        for meta, st_path, at_path in pairs:
            probs = _read_probs_csv(st_path)
            ccl = _compute_ccl(probs, inp.ccl_metric)
            t_val = _read_attr_t(at_path, inp.t_axis)
            rows.append({
                "algo": meta["algo"],
                "device": meta["device"],
                "shots": int(meta["shots"]),
                "instance": int(meta["instance"]),
                "t": float(t_val),
                "Ccl": float(ccl),
                "states_file": st_path.relative_to(td_path).as_posix(),
                "attr_file": at_path.relative_to(td_path).as_posix(),
            })

        df = pd.DataFrame(rows)
        df = df.sort_values(["algo", "device", "shots", "instance", "t"]).reset_index(drop=True)

        # t* par instance: premier t où Ccl >= threshold
        tstars = []
        for (algo, device, shots, inst), g in df.groupby(["algo", "device", "shots", "instance"], sort=False):
            g2 = g.sort_values("t")
            hit = g2[g2["Ccl"] >= float(inp.ccl_threshold)]
            tstar = float(hit.iloc[0]["t"]) if len(hit) else float("nan")
            tstars.append({
                "algo": algo,
                "device": device,
                "shots": int(shots),
                "instance": int(inst),
                "t_star": tstar,
                "ccl_threshold": float(inp.ccl_threshold),
            })

        df_tstar = pd.DataFrame(tstars).sort_values(["algo", "device", "shots", "instance"]).reset_index(drop=True)

        # Bootstrap sur la médiane de t* au niveau (algo, device, shots)
        boot_rows = []
        for (algo, device, shots), g in df_tstar.groupby(["algo", "device", "shots"], sort=False):
            stats = _bootstrap_tstar(g["t_star"].to_numpy(dtype=float), inp.bootstrap_samples)
            boot_rows.append({
                "algo": algo,
                "device": device,
                "shots": int(shots),
                **stats,
            })
        df_boot = pd.DataFrame(boot_rows).sort_values(["algo", "device", "shots"]).reset_index(drop=True)

        # Sauvegardes
        df.to_csv(tables_dir / "ccl_timeseries.csv", index=False)
        df_tstar.to_csv(tables_dir / "tstar_by_instance.csv", index=False)
        (tables_dir / "bootstrap_tstar.csv").write_text(df_boot.to_csv(index=False), encoding="utf-8")

        summary = {
            "dataset_zip": str(dataset_zip.as_posix()),
            "filters": {
                "algo": inp.algo,
                "device": inp.device,
                "shots": inp.shots,
            },
            "t_axis": inp.t_axis,
            "ccl_metric": inp.ccl_metric,
            "ccl_threshold": float(inp.ccl_threshold),
            "bootstrap_samples": int(inp.bootstrap_samples),
            "n_pairs": int(len(df)),
            "n_instances": int(df[["algo","device","shots","instance"]].drop_duplicates().shape[0]),
            "notes": "Ccl uniquement. Aucun verdict.",
        }
        (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        # Figures
        plt.figure()
        for (algo, device, shots), g in df.groupby(["algo", "device", "shots"], sort=False):
            # moyenne par t
            gg = g.groupby("t")["Ccl"].mean().reset_index()
            plt.plot(gg["t"].to_numpy(dtype=float), gg["Ccl"].to_numpy(dtype=float), label=f"{algo} | {device} | {shots}")
        plt.xlabel(inp.t_axis)
        plt.ylabel("Ccl")
        plt.title("Ccl moyen par t")
        plt.legend()
        plt.tight_layout()
        plt.savefig(figs_dir / "ccl_mean.png", dpi=150)
        plt.close()

        # Histogram t* si au moins un t* non nan
        if np.any(~np.isnan(df_tstar["t_star"].to_numpy(dtype=float))):
            plt.figure()
            plt.hist(df_tstar["t_star"].dropna().to_numpy(dtype=float), bins=20)
            plt.xlabel("t_star")
            plt.ylabel("count")
            plt.title("Distribution t* par instance")
            plt.tight_layout()
            plt.savefig(figs_dir / "tstar_hist.png", dpi=150)
            plt.close()

        # Contrats: copier fichiers versionnés si présents dans repo
        # On copie mapping.json, DATA_CONTRACT.md, runs_index_stateprob.csv si existants à côté du dataset_zip ou dans data/qcc/stateprob
        repo_candidates = [
            Path("data/qcc/stateprob/mapping.json"),
            Path("data/qcc/stateprob/DATA_CONTRACT.md"),
            Path("data/qcc/stateprob/runs_index_stateprob.csv"),
        ]
        for p in repo_candidates:
            if p.exists():
                contracts_dir.joinpath(p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

        # Manifest
        write_manifest_sha256(run_dir, run_dir / "manifest.json")

        # Pointer latest
        (out_root / "LATEST_RUN.txt").write_text(str(run_dir), encoding="utf-8")

    return run_dir


def parse_args() -> Inputs:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-zip", required=True)
    ap.add_argument("--algo", default="")
    ap.add_argument("--device", default="")
    ap.add_argument("--shots", default="")
    ap.add_argument("--t-axis", required=True)
    ap.add_argument("--ccl-metric", required=True)
    ap.add_argument("--ccl-threshold", required=True, type=float)
    ap.add_argument("--bootstrap-samples", required=True, type=int)
    ap.add_argument("--out-root", required=True)
    a = ap.parse_args()
    return Inputs(
        dataset_zip=a.dataset_zip,
        algo=a.algo,
        device=a.device,
        shots=a.shots,
        t_axis=a.t_axis,
        ccl_metric=a.ccl_metric,
        ccl_threshold=float(a.ccl_threshold),
        bootstrap_samples=int(a.bootstrap_samples),
        out_root=a.out_root,
    )


def main() -> None:
    inp = parse_args()
    run_dir = run(inp)
    print(f"OK: run_dir={run_dir}")


if __name__ == "__main__":
    main()
