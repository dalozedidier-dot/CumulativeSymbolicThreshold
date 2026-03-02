#!/usr/bin/env python3
"""QCC State Probability bootstrap pipeline.

This tool is deliberately mechanical: it computes Ccl(t) from state probability distributions,
builds simple t* detection, and runs bootstrap across instances. No interpretative verdicts.

Dataset resolution:
- If --dataset-zip path exists, use it.
- Else, try basename in common folders.
- Else, search the repository (limited depth) for the same filename.

"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


def _is_blank(val: object) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    s = str(val).strip()
    return s == "" or s.lower() in {"nan", "none", "null"}


def resolve_dataset_zip(dataset_zip: str) -> Path:
    p = Path(dataset_zip)
    if p.exists():
        return p

    # Try basename in common locations
    name = p.name
    candidates = [
        Path("data/qcc/stateprob") / name,
        Path("data/qcc/stateprob") / "04-09-2020.zip",
        Path(name),
    ]
    for c in candidates:
        if c.exists():
            return c

    # Search repo (limited depth)
    root = Path(".")
    hits: List[Path] = []
    for h in root.rglob(name):
        if h.is_file() and h.suffix.lower() == ".zip":
            # limit depth to avoid excessive traversal
            try:
                rel = h.relative_to(root)
                if len(rel.parts) <= 6:
                    hits.append(h)
            except Exception:
                hits.append(h)
        if len(hits) >= 5:
            break

    if hits:
        # deterministic: shortest path, then lexicographic
        hits.sort(key=lambda x: (len(str(x)), str(x)))
        return hits[0]

    raise FileNotFoundError(
        f"dataset_zip introuvable: {dataset_zip}. "
        f"Placez le fichier 04-09-2020.zip dans data/qcc/stateprob/ ou indiquez son chemin exact via --dataset-zip."
    )


@dataclass
class RunKey:
    algo: str
    device: str
    shots: int
    instance: str


def _entropy(probs: np.ndarray) -> float:
    p = probs[probs > 0]
    if p.size == 0:
        return 0.0
    return float(-(p * np.log(p)).sum())


def _ccl_from_probs(probs: np.ndarray, metric: str, n_qubits: Optional[int] = None) -> float:
    metric = metric.strip().lower()
    probs = np.asarray(probs, dtype=float)
    probs = probs[~np.isnan(probs)]
    if probs.size == 0:
        return float("nan")
    s = probs.sum()
    if s > 0:
        probs = probs / s

    if metric == "entropy":
        h = _entropy(probs)
        if n_qubits is None:
            # fall back to log(len(probs)) for normalization
            denom = math.log(max(probs.size, 2))
        else:
            denom = math.log(2**n_qubits)
        return float(h / denom) if denom > 0 else 0.0

    if metric in {"one_minus_maxprob", "1-max", "1-maxprob"}:
        return float(1.0 - float(np.max(probs)))

    if metric in {"one_minus_purity", "1-purity"}:
        purity = float(np.sum(probs**2))
        return float(1.0 - purity)

    raise ValueError(f"ccl_metric inconnu: {metric}")


def _parse_filename(meta_name: str) -> Tuple[str, str, str, int]:
    # Example: STATES_ibmqx2_BV_0_8192.csv  OR ATTR_ibmqx2_BV_0_8192.csv
    m = re.match(r"^(STATES|ATTR)_(.+?)_([A-Za-z0-9]+)_(\d+?)_(\d+)\.csv$", meta_name)
    if not m:
        raise ValueError(f"Nom de fichier inattendu: {meta_name}")
    kind = m.group(1)
    device = m.group(2)
    algo = m.group(3)
    instance = m.group(4)
    shots = int(m.group(5))
    return kind, device, algo, instance, shots


def _load_csv_from_zip(zf: zipfile.ZipFile, name: str) -> pd.DataFrame:
    with zf.open(name) as f:
        return pd.read_csv(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-zip", required=True)
    ap.add_argument("--algo", default="BV")
    ap.add_argument("--device", default="")
    ap.add_argument("--shots", default="8192")
    ap.add_argument("--t-axis", default="Depth", choices=["Depth", "Runtime"])
    ap.add_argument("--ccl-metric", default="entropy")
    ap.add_argument("--ccl-threshold", type=float, default=0.70)
    ap.add_argument("--bootstrap-samples", type=int, default=500)
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()

    dataset_zip = resolve_dataset_zip(args.dataset_zip)

    out_root = Path(args.out_root)
    run_dir = out_root / "runs" / pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")
    tables_dir = run_dir / "tables"
    figs_dir = run_dir / "figures"
    contracts_dir = run_dir / "contracts"
    for d in (tables_dir, figs_dir, contracts_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Copy contracts if present
    # (The workflow pack places these under data/qcc/stateprob/)
    contract_candidates = [
        Path("data/qcc/stateprob/DATA_CONTRACT.md"),
        Path("data/qcc/stateprob/mapping.json"),
        Path("data/qcc/stateprob/runs_index_stateprob.csv"),
    ]
    copied = []
    for c in contract_candidates:
        if c.exists():
            dst = contracts_dir / c.name
            dst.write_bytes(c.read_bytes())
            copied.append(dst.name)

    # Parse zip: collect STATES and ATTR pairs
    algo_filter = args.algo.strip()
    device_filter = args.device.strip()
    shots_filter = args.shots.strip()
    shots_target = None if _is_blank(shots_filter) else int(shots_filter)

    pairs: Dict[RunKey, Dict[str, str]] = {}
    with zipfile.ZipFile(dataset_zip, "r") as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".csv"):
                continue
            base = Path(name).name
            if not (base.startswith("STATES_") or base.startswith("ATTR_")):
                continue
            kind, device, algo, instance, shots = _parse_filename(base)
            if algo != algo_filter:
                continue
            if device_filter and device != device_filter:
                continue
            if shots_target is not None and shots != shots_target:
                continue

            key = RunKey(algo=algo, device=device, shots=shots, instance=instance)
            pairs.setdefault(key, {})
            pairs[key][kind] = name

    if not pairs:
        raise RuntimeError(
            "Aucun fichier STATES/ATTR trouvé pour les filtres demandés. "
            f"algo={algo_filter}, device={device_filter or '*'}, shots={shots_filter or '*'}."
        )

    # Build per-instance timeseries using chosen t-axis from ATTR and Ccl from STATES.
    rows = []
    for key, d in sorted(pairs.items(), key=lambda kv: (kv[0].device, kv[0].shots, kv[0].instance)):
        if "STATES" not in d or "ATTR" not in d:
            # skip incomplete pair
            continue

        df_states = _load_csv_from_zip(zipfile.ZipFile(dataset_zip, "r"), d["STATES"])
        df_attr = _load_csv_from_zip(zipfile.ZipFile(dataset_zip, "r"), d["ATTR"])

        # Infer probabilities column in STATES file
        prob_col = None
        for cand in ["Probability", "probability", "Prob", "p"]:
            if cand in df_states.columns:
                prob_col = cand
                break
        if prob_col is None:
            # Try second column
            if df_states.shape[1] >= 2:
                prob_col = df_states.columns[1]
            else:
                continue

        probs = df_states[prob_col].astype(float).to_numpy()

        # Determine n_qubits by bitstring length if present
        n_qubits = None
        for bit_col in ["State", "state", "Bitstring", "bitstring"]:
            if bit_col in df_states.columns:
                s0 = str(df_states[bit_col].iloc[0])
                n_qubits = len(s0.strip())
                break

        ccl = _ccl_from_probs(probs, args.ccl_metric, n_qubits=n_qubits)

        # t-axis from ATTR
        if args.t_axis == "Depth":
            if "Depth" in df_attr.columns:
                t_val = float(df_attr["Depth"].iloc[0])
            else:
                # fallback: any column containing depth
                cols = [c for c in df_attr.columns if str(c).lower().startswith("depth")]
                t_val = float(df_attr[cols[0]].iloc[0]) if cols else float("nan")
        else:
            # Runtime
            if "Runtime" in df_attr.columns:
                t_val = float(df_attr["Runtime"].iloc[0])
            else:
                cols = [c for c in df_attr.columns if "runtime" in str(c).lower()]
                t_val = float(df_attr[cols[0]].iloc[0]) if cols else float("nan")

        rows.append(
            {
                "algo": key.algo,
                "device": key.device,
                "shots": key.shots,
                "instance": key.instance,
                "t": t_val,
                "Ccl": ccl,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("Aucune paire STATES/ATTR complète après filtrage.")

    df = df.dropna(subset=["t", "Ccl"]).sort_values(["device", "shots", "instance", "t"]).reset_index(drop=True)

    # Compute t* per instance: first t where Ccl >= threshold
    tstar_rows = []
    for (device, shots, instance), g in df.groupby(["device", "shots", "instance"], sort=False):
        g2 = g.sort_values("t")
        hit = g2[g2["Ccl"] >= float(args.ccl_threshold)]
        tstar = float(hit["t"].iloc[0]) if not hit.empty else float("nan")
        tstar_rows.append({"device": device, "shots": int(shots), "instance": instance, "t_star": tstar})
    df_tstar = pd.DataFrame(tstar_rows)

    # Bootstrap across instances (within each device+shots)
    boot_rows = []
    rng = np.random.default_rng(0)
    for (device, shots), g in df_tstar.groupby(["device", "shots"], sort=False):
        vals = g["t_star"].dropna().to_numpy(dtype=float)
        if vals.size < 2:
            continue
        for b in range(int(args.bootstrap_samples)):
            sample = rng.choice(vals, size=vals.size, replace=True)
            boot_rows.append({"device": device, "shots": int(shots), "b": b, "t_star_mean": float(np.mean(sample))})
    df_boot = pd.DataFrame(boot_rows)

    # Write outputs
    df.to_csv(tables_dir / "ccl_timeseries.csv", index=False)
    df_tstar.to_csv(tables_dir / "tstar_by_instance.csv", index=False)
    df_boot.to_csv(tables_dir / "bootstrap_tstar.csv", index=False)

    summary = {
        "dataset_zip": str(dataset_zip),
        "algo": algo_filter,
        "device_filter": device_filter,
        "shots_filter": shots_filter,
        "t_axis": args.t_axis,
        "ccl_metric": args.ccl_metric,
        "ccl_threshold": float(args.ccl_threshold),
        "bootstrap_samples": int(args.bootstrap_samples),
        "contracts_copied": copied,
        "n_rows": int(df.shape[0]),
        "n_instances": int(df[["device", "shots", "instance"]].drop_duplicates().shape[0]),
    }
    (tables_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Minimal plots (matplotlib)
    import matplotlib.pyplot as plt

    # Mean Ccl vs t (aggregated by device+shots)
    for (device, shots), g in df.groupby(["device", "shots"], sort=False):
        g2 = g.groupby("t", as_index=False)["Ccl"].mean().sort_values("t")
        plt.figure()
        plt.plot(g2["t"], g2["Ccl"], marker="o")
        plt.xlabel("t")
        plt.ylabel("Ccl")
        plt.title(f"Ccl mean vs {args.t_axis} ({algo_filter})\n{device} shots={shots}")
        plt.ylim(0, 1)
        plt.grid(True, alpha=0.3)
        plt.savefig(figs_dir / f"ccl_mean_{device}_shots{shots}.png", dpi=160, bbox_inches="tight")
        plt.close()

    # Histogram of t* means
    if not df_boot.empty:
        for (device, shots), g in df_boot.groupby(["device", "shots"], sort=False):
            plt.figure()
            plt.hist(g["t_star_mean"].to_numpy(), bins=30)
            plt.xlabel("t_star_mean")
            plt.ylabel("count")
            plt.title(f"Bootstrap t* mean ({algo_filter})\n{device} shots={shots}")
            plt.grid(True, alpha=0.3)
            plt.savefig(figs_dir / f"tstar_boot_hist_{device}_shots{shots}.png", dpi=160, bbox_inches="tight")
            plt.close()

    # Build manifest
    from tools.make_manifest import build_manifest  # type: ignore

    build_manifest(run_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
