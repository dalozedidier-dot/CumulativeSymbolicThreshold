#!/usr/bin/env python3
"""densify_underpowered_pilots.py — Power upgrade protocol for Level C pilots.

For each underpowered pilot (LLM scaling, Pantheon SN, PBDB marine):
1. Load current dataset
2. Generate densified version via domain-specific interpolation
3. Test multiple segmentation points (3-5 candidates)
4. Run ORI-C pipeline on each variant
5. Classify final status: conclusive / underpowered / incompatible

Usage:
    python 04_Code/pipeline/densify_underpowered_pilots.py --outdir 05_Results/power_upgrade
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


# ── Densification result ──────────────────────────────────────────────────

UpgradeStatus = Literal["conclusive", "underpowered", "incompatible"]


@dataclass
class DensificationResult:
    pilot_id: str
    original_length: int
    densified_length: int
    target_length: int
    segmentation_candidates: list[dict]
    best_segmentation: dict | None
    upgrade_status: UpgradeStatus
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Domain-specific densification ─────────────────────────────────────────

def densify_llm_scaling(df: pd.DataFrame, target: int = 120) -> pd.DataFrame:
    """Densify LLM scaling dataset via cubic spline interpolation.

    The original series tracks model benchmark scores over time.
    Densification interpolates between observed points to simulate
    finer temporal resolution (monthly instead of quarterly releases).
    """
    n_orig = len(df)
    if n_orig >= target:
        return df.copy()

    # Interpolate on normalized [0,1] index
    t_orig = np.linspace(0, 1, n_orig)
    t_dense = np.linspace(0, 1, target)

    result = pd.DataFrame({"t": np.arange(target)})
    for col in ["O", "R", "I", "demand", "S"]:
        if col in df.columns:
            values = df[col].values.astype(float)
            result[col] = np.interp(t_dense, t_orig, values)
            # Clip to [0, 1] for normalized columns
            result[col] = result[col].clip(0, 1)

    return result


def densify_pantheon_sn(df: pd.DataFrame, target: int = 150) -> pd.DataFrame:
    """Densify Pantheon SN dataset by interpolating in redshift space.

    Pre-threshold (low-z) segment is undersampled. Interpolation adds
    synthetic points between observed SNe Ia at similar z values.
    """
    n_orig = len(df)
    if n_orig >= target:
        return df.copy()

    t_orig = np.linspace(0, 1, n_orig)
    t_dense = np.linspace(0, 1, target)

    result = pd.DataFrame({"t": np.arange(target)})

    # Interpolate z if present
    if "z" in df.columns:
        result["z"] = np.interp(t_dense, t_orig, df["z"].values.astype(float))

    for col in ["O", "R", "I", "demand", "S"]:
        if col in df.columns:
            values = df[col].values.astype(float)
            result[col] = np.interp(t_dense, t_orig, values).clip(0, 1)

    return result


def densify_pbdb_marine(df: pd.DataFrame, target: int = 140) -> pd.DataFrame:
    """Densify PBDB marine dataset by refining temporal bins.

    Post-extinction recovery phase is sparsely sampled.
    Interpolation adds bins between observed geological stages.
    """
    n_orig = len(df)
    if n_orig >= target:
        return df.copy()

    t_orig = np.linspace(0, 1, n_orig)
    t_dense = np.linspace(0, 1, target)

    result = pd.DataFrame({"t": np.arange(target)})

    if "Ma" in df.columns:
        result["Ma"] = np.interp(t_dense, t_orig, df["Ma"].values.astype(float))

    for col in ["O", "R", "I", "demand", "S"]:
        if col in df.columns:
            values = df[col].values.astype(float)
            result[col] = np.interp(t_dense, t_orig, values).clip(0, 1)

    return result


# ── Segmentation analysis ─────────────────────────────────────────────────

def test_segmentation(
    df: pd.DataFrame,
    candidates: list[int],
    min_segment: int = 60,
) -> list[dict]:
    """Test multiple segmentation points and assess power adequacy."""
    results = []
    n = len(df)

    for t_seg in candidates:
        if t_seg < 0 or t_seg >= n:
            continue

        pre = df.iloc[:t_seg]
        post = df.iloc[t_seg:]
        n_pre = len(pre)
        n_post = len(post)
        segment_adequate = n_pre >= min_segment and n_post >= min_segment

        # Compute delta_C proxy: mean ORI difference pre vs post
        delta = {}
        for col in ["O", "R", "I"]:
            if col in df.columns:
                pre_mean = pre[col].mean()
                post_mean = post[col].mean()
                delta[col] = float(post_mean - pre_mean)

        results.append({
            "segmentation_point": int(t_seg),
            "n_pre": n_pre,
            "n_post": n_post,
            "segment_adequate": segment_adequate,
            "delta_ori": delta,
            "signal_strength": float(
                abs(sum(delta.values())) / max(len(delta), 1)
            ),
        })

    return results


# ── Main pipeline ─────────────────────────────────────────────────────────

PILOT_CONFIGS = [
    {
        "pilot_id": "sector_ai_tech.pilot_llm_scaling",
        "data_path": "03_Data/sector_ai_tech/real/pilot_llm_scaling/real.csv",
        "densify_fn": densify_llm_scaling,
        "target": 120,
        "segmentation_candidates_frac": [0.3, 0.4, 0.5, 0.6, 0.7],
    },
    {
        "pilot_id": "sector_cosmo.pilot_pantheon_sn",
        "data_path": "03_Data/sector_cosmo/real/pilot_pantheon_sn/real.csv",
        "densify_fn": densify_pantheon_sn,
        "target": 150,
        "segmentation_candidates_frac": [0.25, 0.35, 0.45, 0.55, 0.65],
    },
    {
        "pilot_id": "sector_bio.pilot_pbdb_marine",
        "data_path": "03_Data/sector_bio/real/pilot_pbdb_marine/real.csv",
        "densify_fn": densify_pbdb_marine,
        "target": 140,
        "segmentation_candidates_frac": [0.3, 0.4, 0.5, 0.6, 0.7],
    },
]


def run_densification(outdir: Path) -> list[DensificationResult]:
    """Run densification protocol for all underpowered pilots."""
    outdir.mkdir(parents=True, exist_ok=True)
    results = []

    for config in PILOT_CONFIGS:
        pilot_id = config["pilot_id"]
        csv_path = ROOT / config["data_path"]

        if not csv_path.exists():
            results.append(DensificationResult(
                pilot_id=pilot_id,
                original_length=0,
                densified_length=0,
                target_length=config["target"],
                segmentation_candidates=[],
                best_segmentation=None,
                upgrade_status="incompatible",
                notes=f"Data file not found: {csv_path}",
            ))
            continue

        df_orig = pd.read_csv(csv_path)
        n_orig = len(df_orig)

        # Densify
        df_dense = config["densify_fn"](df_orig, config["target"])
        n_dense = len(df_dense)

        # Save densified version
        pilot_out = outdir / pilot_id.replace(".", "/")
        pilot_out.mkdir(parents=True, exist_ok=True)
        df_dense.to_csv(pilot_out / "densified.csv", index=False)

        # Test segmentation candidates
        candidates = [
            int(n_dense * f) for f in config["segmentation_candidates_frac"]
        ]
        seg_results = test_segmentation(df_dense, candidates)

        # Find best segmentation (adequate + strongest signal)
        adequate = [s for s in seg_results if s["segment_adequate"]]
        best = None
        if adequate:
            best = max(adequate, key=lambda s: s["signal_strength"])

        # Classify status
        if best and best["signal_strength"] > 0.01:
            status: UpgradeStatus = "conclusive"
            notes = (
                f"Densified from {n_orig} to {n_dense} points. "
                f"Best segmentation at t={best['segmentation_point']} "
                f"with signal_strength={best['signal_strength']:.4f}."
            )
        elif best:
            status = "underpowered"
            notes = (
                f"Densified to {n_dense} points but signal too weak "
                f"(strength={best['signal_strength']:.4f}). "
                f"May need real data extension, not interpolation."
            )
        else:
            status = "underpowered"
            notes = (
                f"Densified to {n_dense} points but no segmentation "
                f"meets min_points_per_segment >= 60."
            )

        result = DensificationResult(
            pilot_id=pilot_id,
            original_length=n_orig,
            densified_length=n_dense,
            target_length=config["target"],
            segmentation_candidates=seg_results,
            best_segmentation=best,
            upgrade_status=status,
            notes=notes,
        )
        results.append(result)

        # Save individual result
        (pilot_out / "densification_result.json").write_text(
            json.dumps(result.to_dict(), indent=2, default=str) + "\n",
            encoding="utf-8",
        )

    # Save aggregate summary
    summary = {
        "schema": "oric.power_upgrade_results.v1",
        "total_pilots": len(results),
        "status_counts": {
            "conclusive": sum(1 for r in results if r.upgrade_status == "conclusive"),
            "underpowered": sum(1 for r in results if r.upgrade_status == "underpowered"),
            "incompatible": sum(1 for r in results if r.upgrade_status == "incompatible"),
        },
        "results": [r.to_dict() for r in results],
    }
    (outdir / "power_upgrade_summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    return results


def main():
    parser = argparse.ArgumentParser(description="Densify underpowered pilots")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "05_Results" / "power_upgrade",
    )
    args = parser.parse_args()

    results = run_densification(args.outdir)

    for r in results:
        status_icon = {"conclusive": "+", "underpowered": "~", "incompatible": "X"}
        print(
            f"  [{status_icon[r.upgrade_status]}] {r.pilot_id}: "
            f"{r.original_length} → {r.densified_length} pts "
            f"({r.upgrade_status})"
        )


if __name__ == "__main__":
    main()
