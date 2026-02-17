"""
Minimal pipeline

Computes O, R, I, V, S, Cap, Sigma from a CSV.
C(t) and s(t) are placeholders and must be defined per preregistered design.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class Config:
    delta_window: int
    horizon_T: int
    omega: dict[str, float]
    alpha: dict[str, float]
    k: float
    m: int
    sigma_star: float
    tau: int
    capacity_form: str  # "product" or "geom_mean"


REQUIRED_BASE_COLUMNS = [
    "id",
    "t",
    "survie",
    "energie_nette",
    "integrite",
    "persistance",
    "repertoire",
    "codification",
    "densite_transmission",
    "fidelite",
    "demande_env",
]


def load_config(path: Path) -> Config:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return Config(**data)


def require_columns(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def mean_of_prefix(df: pd.DataFrame, prefix: str) -> pd.Series:
    cols = [c for c in df.columns if c.startswith(prefix)]
    if not cols:
        raise ValueError(f"No columns found with prefix '{prefix}'.")
    return df[cols].mean(axis=1)


def compute_scores(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    require_columns(df, REQUIRED_BASE_COLUMNS)
    out = df.copy()

    out["O"] = mean_of_prefix(out, "O_raw_")
    out["R"] = mean_of_prefix(out, "R_raw_")
    out["I"] = mean_of_prefix(out, "I_raw_")

    omega = cfg.omega
    out["V"] = (
        omega["survie"] * out["survie"]
        + omega["energie_nette"] * out["energie_nette"]
        + omega["integrite"] * out["integrite"]
        + omega["persistance"] * out["persistance"]
    )

    alpha = cfg.alpha
    out["S"] = (
        alpha["repertoire"] * out["repertoire"]
        + alpha["codification"] * out["codification"]
        + alpha["densite_transmission"] * out["densite_transmission"]
        + alpha["fidelite"] * out["fidelite"]
    )

    if cfg.capacity_form == "product":
        out["Cap"] = out["O"] * out["R"] * out["I"]
    elif cfg.capacity_form == "geom_mean":
        base = (out["O"].clip(lower=0) * out["R"].clip(lower=0) * out["I"].clip(lower=0))
        out["Cap"] = base ** (1.0 / 3.0)
    else:
        raise ValueError("capacity_form must be 'product' or 'geom_mean'")

    out["Sigma"] = (out["demande_env"] - out["Cap"]).clip(lower=0.0)

    out["C"] = pd.NA
    out["s"] = pd.NA
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    cfg = load_config(args.config)
    df = pd.read_csv(args.input)
    out = compute_scores(df, cfg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
