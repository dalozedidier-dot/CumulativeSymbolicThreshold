#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QCC / ORI-C - State_Probability dataset bootstrap
- Builds C_cl proxy from measured state probability distributions
- Uses circuit depth (or runtime) as the t-axis
- Bootstraps t* (first threshold crossing) across instances
Strict: no interpretive verdicts. Outputs are mechanical + fully auditable.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RunKey:
    device: str
    instance: int
    shots: int


_STATES_RE = re.compile(r".*/State_Probability/STATES_(?P<device>.+)_(?P<algo>[A-Z0-9_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$")
_ATTR_RE = re.compile(r".*/Count_Depth/ATTR_(?P<device>.+)_(?P<algo>[A-Z0-9_]+)_(?P<instance>\d+)_(?P<shots>\d+)\.csv$")


def _read_states_csv(raw_bytes: bytes) -> pd.DataFrame:
    # Two-column CSV without headers: bitstring, prob
    df = pd.read_csv(io.BytesIO(raw_bytes), header=None, names=["bitstring", "prob"])
    df["bitstring"] = df["bitstring"].astype(str)
    df["prob"] = pd.to_numeric(df["prob"], errors="coerce")
    df = df.dropna(subset=["prob"])
    s = float(df["prob"].sum())
    if s > 0:
        df["prob"] = df["prob"] / s
    return df


def _read_attr_csv(raw_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw_bytes))
    # Strip whitespace from headers
    df.columns = [str(c).strip() for c in df.columns]
    # Some files have " Count" and " Depth" as values; also strip those
    if "Count" not in df.columns and " Count" in df.columns:
        df = df.rename(columns={" Count": "Count"})
    if "Depth" not in df.columns and " Depth" in df.columns:
        df = df.rename(columns={" Depth": "Depth"})
    return df


def _ccl_entropy(df_states: pd.DataFrame) -> float:
    p = df_states["prob"].to_numpy(dtype=float)
    p = p[p > 0]
    if p.size == 0:
        return float("nan")
    # infer n qubits from max bitstring length
    n = int(df_states["bitstring"].map(lambda s: len(str(s))).max())
    if n <= 0:
        return float("nan")
    H = float(-np.sum(p * np.log(p)))
    Hmax = float(n * np.log(2.0))
    return float(H / Hmax) if Hmax > 0 else float("nan")


def _ccl_one_minus_maxprob(df_states: pd.DataFrame) -> float:
    pmax = float(df_states["prob"].max()) if len(df_states) else float("nan")
    return float(1.0 - pmax) if np.isfinite(pmax) else float("nan")


def _ccl_impurity(df_states: pd.DataFrame) -> float:
    p = df_states["prob"].to_numpy(dtype=float)
    if p.size == 0:
        return float("nan")
    return float(1.0 - np.sum(p * p))


def _compute_ccl(metric: str, df_states: pd.DataFrame) -> float:
    metric = metric.lower().strip()
    if metric == "entropy":
        return _ccl_entropy(df_states)
    if metric in ("1-maxprob", "one_minus_maxprob", "maxprob"):
        return _ccl_one_minus_maxprob(df_states)
    if metric in ("impurity", "1-purity"):
        return _ccl_impurity(df_states)
    raise ValueError(f"Unknown ccl_metric={metric!r}. Use entropy | 1-maxprob | impurity.")


def _extract_depth_or_runtime(t_axis: str, df_attr: pd.DataFrame) -> float:
    t_axis = t_axis.lower().strip()
    if t_axis == "depth":
        if "Depth" not in df_attr.columns:
            raise KeyError("ATTR file missing 'Depth' column")
        # Depth is constant per file in this dataset; take first numeric
        val = pd.to_numeric(df_attr["Depth"], errors="coerce").dropna()
        if val.empty:
            raise ValueError("Depth column contains no numeric values")
        return float(val.iloc[0])
    if t_axis == "runtime":
        # Some datasets store runtime elsewhere; keep option for future
        # If Runtime not present, fail explicitly.
        if "Runtime" not in df_attr.columns:
            raise KeyError("ATTR file missing 'Runtime' column")
        val = pd.to_numeric(df_attr["Runtime"], errors="coerce").dropna()
        if val.empty:
            raise ValueError("Runtime column contains no numeric values")
        return float(val.iloc[0])
    raise ValueError("t_axis must be Depth or Runtime")


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _safe_float(x) -> Optional[float]:
    try:
        v = float(x)
        if math.isnan(v):
            return None
        return v
    except Exception:
        return None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-zip", required=True, help="Path to 04-09-2020.zip (or compatible).")
    ap.add_argument("--algo", default="BV", help="Algorithm folder name, e.g. BV, QAOA, QFT.")
    ap.add_argument("--device", default="", help="Optional device filter. Empty = all devices.")
    ap.add_argument("--shots", default="8192", help="Shots filter (as int).")
    ap.add_argument("--t-axis", default="Depth", help="Depth or Runtime.")
    ap.add_argument("--ccl-metric", default="entropy", help="entropy | 1-maxprob | impurity")
    ap.add_argument("--ccl-threshold", default="0.70", help="Threshold for t* on mean Ccl.")
    ap.add_argument("--bootstrap-samples", default="500", help="Bootstrap resamples.")
    ap.add_argument("--out-root", default="05_Results/qcc_stateprob_bootstrap", help="Output root dir.")
    args = ap.parse_args(argv)

    dataset_zip = Path(args.dataset_zip)
    if not dataset_zip.exists():
        raise FileNotFoundError(f"dataset_zip not found: {dataset_zip}")

    algo = str(args.algo).strip()
    device_filter = str(args.device).strip()
    shots = int(str(args.shots).strip())
    t_axis = str(args.t_axis).strip()
    ccl_metric = str(args.ccl_metric).strip()
    ccl_threshold = float(str(args.ccl_threshold).strip())
    bootstrap_samples = int(str(args.bootstrap_samples).strip())
    out_root = Path(args.out_root)

    # Timestamped run dir (UTC-ish, no timezone dependency)
    run_dir = out_root / "runs" / pd.Timestamp.now(tz="UTC").strftime("%Y%m%d_%H%M%S")
    tables_dir = run_dir / "tables"
    figures_dir = run_dir / "figures"
    contracts_dir = run_dir / "contracts"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    contracts_dir.mkdir(parents=True, exist_ok=True)

    # Minimal contracts captured for audit
    _write_json(contracts_dir / "mapping.json", {
        "dataset_zip": str(dataset_zip.as_posix()),
        "algo": algo,
        "device_filter": device_filter,
        "shots": shots,
        "t_axis": t_axis,
        "ccl_metric": ccl_metric,
        "ccl_threshold": ccl_threshold,
        "bootstrap_samples": bootstrap_samples,
        "note": "Ccl computed mechanically from State_Probability distributions. No interpretive verdict."
    })

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        shutil.unpack_archive(str(dataset_zip), str(td_path))

        # Collect pairs (STATES + ATTR) for given algo + shots (+ optional device)
        pairs: Dict[RunKey, Dict[str, Path]] = {}
        for p in td_path.rglob("*.csv"):
            sp = p.as_posix()
            mS = _STATES_RE.match(sp)
            if mS and mS.group("algo") == algo and int(mS.group("shots")) == shots:
                dev = mS.group("device")
                if device_filter and dev != device_filter:
                    continue
                key = RunKey(dev, int(mS.group("instance")), shots)
                pairs.setdefault(key, {})["states"] = p
                continue
            mA = _ATTR_RE.match(sp)
            if mA and mA.group("algo") == algo and int(mA.group("shots")) == shots:
                dev = mA.group("device")
                if device_filter and dev != device_filter:
                    continue
                key = RunKey(dev, int(mA.group("instance")), shots)
                pairs.setdefault(key, {})["attr"] = p

        # Filter only complete pairs
        complete = {k: v for k, v in pairs.items() if "states" in v and "attr" in v}
        if not complete:
            raise RuntimeError(
                f"No complete (STATES+ATTR) pairs found for algo={algo}, shots={shots}, device_filter={device_filter!r}."
            )

        rows = []
        for key, v in sorted(complete.items(), key=lambda kv: (kv[0].device, kv[0].instance)):
            states_bytes = v["states"].read_bytes()
            attr_bytes = v["attr"].read_bytes()
            df_states = _read_states_csv(states_bytes)
            df_attr = _read_attr_csv(attr_bytes)

            t_val = _extract_depth_or_runtime(t_axis, df_attr)
            ccl = _compute_ccl(ccl_metric, df_states)

            rows.append({
                "device": key.device,
                "instance": key.instance,
                "shots": key.shots,
                "t": t_val,
                "t_axis": t_axis,
                "ccl_metric": ccl_metric,
                "Ccl": ccl,
                "states_file": v["states"].name,
                "attr_file": v["attr"].name,
            })

        df = pd.DataFrame(rows)
        df = df.sort_values(["device", "t", "instance"]).reset_index(drop=True)
        df.to_csv(tables_dir / "ccl_timeseries.csv", index=False)

        # Mean by depth per device
        mean_df = (
            df.groupby(["device", "t"], as_index=False)
            .agg(Ccl_mean=("Ccl", "mean"), Ccl_std=("Ccl", "std"), n=("Ccl", "size"))
            .sort_values(["device", "t"])
        )
        mean_df.to_csv(tables_dir / "ccl_mean_by_t.csv", index=False)

        # Bootstrap t* per device: first t where Ccl_mean >= threshold
        boot_rows = []
        rng = np.random.default_rng(1337)
        for dev, sub in df.groupby("device"):
            instances = sub["instance"].unique()
            if len(instances) < 2:
                continue
            inst_to_rows = {i: sub[sub["instance"] == i] for i in instances}
            for b in range(bootstrap_samples):
                samp = rng.choice(instances, size=len(instances), replace=True)
                samp_df = pd.concat([inst_to_rows[i] for i in samp], ignore_index=True)
                m = (
                    samp_df.groupby("t", as_index=False)["Ccl"].mean()
                    .sort_values("t")
                )
                tstar = None
                for _, r in m.iterrows():
                    if np.isfinite(r["Ccl"]) and float(r["Ccl"]) >= ccl_threshold:
                        tstar = float(r["t"])
                        break
                boot_rows.append({
                    "device": dev,
                    "bootstrap_i": b,
                    "tstar": tstar,
                })

        boot_df = pd.DataFrame(boot_rows)
        boot_df.to_csv(tables_dir / "bootstrap_tstar.csv", index=False)

        # Summary
        summary = {
            "algo": algo,
            "shots": shots,
            "device_filter": device_filter,
            "t_axis": t_axis,
            "ccl_metric": ccl_metric,
            "ccl_threshold": ccl_threshold,
            "bootstrap_samples": bootstrap_samples,
            "n_pairs": int(len(df)),
            "devices": sorted(df["device"].unique().tolist()),
        }
        # Add per-device t* on full mean
        tstars = {}
        for dev, m in mean_df.groupby("device"):
            tstar = None
            for _, r in m.sort_values("t").iterrows():
                if np.isfinite(r["Ccl_mean"]) and float(r["Ccl_mean"]) >= ccl_threshold:
                    tstar = float(r["t"])
                    break
            tstars[dev] = tstar
        summary["tstar_by_device"] = tstars
        _write_json(tables_dir / "summary.json", summary)

        # Figures (matplotlib imported lazily to keep deps minimal)
        import matplotlib.pyplot as plt

        # Plot mean Ccl by t for each device
        plt.figure()
        for dev, m in mean_df.groupby("device"):
            plt.plot(m["t"].to_numpy(), m["Ccl_mean"].to_numpy(), marker="o", linestyle="-", label=dev)
        plt.axhline(ccl_threshold, linestyle="--")
        plt.xlabel(t_axis)
        plt.ylabel("Ccl_mean")
        plt.title(f"Ccl mean by {t_axis} (algo={algo}, shots={shots}, metric={ccl_metric})")
        if len(mean_df["device"].unique()) <= 12:
            plt.legend(fontsize="small")
        plt.tight_layout()
        plt.savefig(figures_dir / "ccl_mean.png", dpi=150)
        plt.close()

        # t* histogram if any finite values
        if not boot_df.empty and boot_df["tstar"].notna().any():
            plt.figure()
            vals = boot_df["tstar"].dropna().to_numpy(dtype=float)
            plt.hist(vals, bins=30)
            plt.xlabel(f"t* ({t_axis})")
            plt.ylabel("count")
            plt.title("Bootstrap distribution of t*")
            plt.tight_layout()
            plt.savefig(figures_dir / "tstar_hist.png", dpi=150)
            plt.close()

    # Let existing make_manifest.py handle manifest if present, else write a minimal one.
    manifest_path = run_dir / "manifest.json"
    try:
        # Local import (repo tool) if available
        from tools.make_manifest import make_manifest  # type: ignore
        make_manifest(run_dir, manifest_path)
    except Exception:
        # Minimal manifest: sha256 for all files under run_dir
        import hashlib
        entries = {}
        for fp in run_dir.rglob("*"):
            if fp.is_file():
                h = hashlib.sha256(fp.read_bytes()).hexdigest()
                entries[str(fp.relative_to(run_dir))] = h
        _write_json(manifest_path, {"sha256": entries})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
