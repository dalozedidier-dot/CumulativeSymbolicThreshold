"""
Pipeline minimal

Objectif:
- Charger des données brutes (ou synthétiques)
- Calculer O(t), R(t), I(t), V(t), Cap(t), Sigma(t), S(t)
- Enregistrer U(t) si un proxy est fourni
- Laisser C(t) et s(t) comme variables à définir selon le design pré enregistré
- Exporter une table traitée

Ce script est un squelette. Les formules exactes et les poids doivent être définis ex ante
dans une configuration.
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

    # O, R, I from raw proxies
    out["O"] = mean_of_prefix(out, "O_raw_")
    out["R"] = mean_of_prefix(out, "R_raw_")
    out["I"] = mean_of_prefix(out, "I_raw_")

    # Viability V(t), weights fixed ex ante
    omega = cfg.omega
    out["V"] = (
        omega["survie"] * out["survie"]
        + omega["energie_nette"] * out["energie_nette"]
        + omega["integrite"] * out["integrite"]
        + omega["persistance"] * out["persistance"]
    )

    # Symbolic stock S(t), weights fixed ex ante
    alpha = cfg.alpha
    out["S"] = (
        alpha["repertoire"] * out["repertoire"]
        + alpha["codification"] * out["codification"]
        + alpha["densite_transmission"] * out["densite_transmission"]
        + alpha["fidelite"] * out["fidelite"]
    )

    # Capacity used in mismatch Sigma
    if cfg.capacity_form == "product":
        out["Cap"] = out["O"] * out["R"] * out["I"]
    elif cfg.capacity_form == "geom_mean":
        base = out["O"].clip(lower=0) * out["R"].clip(lower=0) * out["I"].clip(lower=0)
        out["Cap"] = base ** (1.0 / 3.0)
    else:
        raise ValueError("capacity_form must be 'product' or 'geom_mean'")

    # Sigma(t) = max(0, demand - capacity)
    out["Sigma"] = (out["demande_env"] - out["Cap"]).clip(lower=0.0)

    # Optional exogenous intervention proxy
    if "U_raw" in out.columns:
        out["U"] = out["U_raw"]
    else:
        out["U"] = pd.NA

    # Placeholders. Must be defined per preregistered design.
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
