#!/usr/bin/env python3
"""
qcc_stateprob_pooling.py

Pooling strategies for StateProb cross-conditions analysis.

pool_by_depth
  Groups all instances sharing the same (shots, depth) into a pool.
  The points DataFrame is unchanged (each instance row is kept as-is),
  but a pool_membership.csv is written for audit traceability.
  Effect on power_diagnostic: depth_distinct_total = number of unique depth
  values across ALL instances, instances_count = total instance count.

multi_device_pool
  Aggregates points across devices for the same (algo, shots).
  The 'device' column is relabelled 'pooled'; all devices contribute rows.
  pool_membership.csv lists source devices per (algo, shots, depth) group.
  Only valid when devices produce comparable CCL values (same scale).
  Caller is responsible for asserting this via DATA_CONTRACT.

Both functions write pool_membership.csv under out_dir when provided.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd


def pool_by_depth(
    points: pd.DataFrame,
    out_dir: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (points_unchanged, membership_df).

    membership_df — one row per (shots, depth) pool:
      pooling_mode, shots, depth, pool_size, instances (JSON list)
    """
    if points.empty:
        membership = pd.DataFrame(
            columns=["pooling_mode", "shots", "depth", "pool_size", "instances"]
        )
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            membership.to_csv(out_dir / "pool_membership.csv", index=False)
        return points, membership

    rows = []
    for (shots, depth), g in points.groupby(["shots", "depth"]):
        instances = sorted(int(i) for i in g["instance"].tolist())
        rows.append(
            {
                "pooling_mode": "pooled_by_depth",
                "shots": int(shots),
                "depth": float(depth),
                "pool_size": len(instances),
                "instances": json.dumps(instances),
            }
        )

    membership = (
        pd.DataFrame(rows).sort_values(["shots", "depth"]).reset_index(drop=True)
    )

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        membership.to_csv(out_dir / "pool_membership.csv", index=False)

    return points, membership


def multi_device_pool(
    points: pd.DataFrame,
    devices: Optional[List[str]] = None,
    out_dir: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (pooled_points, membership_df).

    pooled_points — same rows as input (or filtered to `devices`),
      with 'device' relabelled to 'pooled'.

    membership_df — one row per (algo, shots, depth) group:
      pooling_mode, algo, shots, depth, pool_size, devices (JSON list),
      instances (JSON list)

    IMPORTANT: only valid when the devices produce comparable CCL values.
    Assert this in DATA_CONTRACT before enabling multi-device mode.
    """
    if points.empty:
        membership = pd.DataFrame(
            columns=[
                "pooling_mode",
                "algo",
                "shots",
                "depth",
                "pool_size",
                "devices",
                "instances",
            ]
        )
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            membership.to_csv(out_dir / "pool_membership.csv", index=False)
        return points, membership

    filtered = points.copy()
    if devices is not None:
        filtered = filtered[filtered["device"].isin(devices)].copy()

    rows = []
    for (algo, shots, depth), g in filtered.groupby(["algo", "shots", "depth"]):
        devs = sorted(g["device"].unique().tolist())
        instances = sorted(int(i) for i in g["instance"].tolist())
        rows.append(
            {
                "pooling_mode": "multi_device",
                "algo": str(algo),
                "shots": int(shots),
                "depth": float(depth),
                "pool_size": len(g),
                "devices": json.dumps(devs),
                "instances": json.dumps(instances),
            }
        )

    membership = (
        pd.DataFrame(rows)
        .sort_values(["algo", "shots", "depth"])
        .reset_index(drop=True)
    )

    filtered["device"] = "pooled"

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        membership.to_csv(out_dir / "pool_membership.csv", index=False)

    return filtered, membership
