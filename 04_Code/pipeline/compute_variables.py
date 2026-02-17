"""Pipeline minimal

Objectif:
- Charger des données brutes (ou synthétiques)
- Calculer O(t), R(t), I(t), V(t), Sigma(t), S(t), C(t), s(t)
- Exporter une table traitée

Ce script est un squelette. Les formules exactes et les poids doivent être définis ex ante et placés dans une configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import pandas as pd


@dataclass(frozen=True)
class Config:
    delta_window: int
    horizon_T: int
    omega: dict
    alpha: dict
    k: float
    m: int
    sigma_star: float
    tau: int
    capacity_form: str


def load_config(path: Path) -> Config:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Config(**data)


def compute_placeholder_scores(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    # Placeholders. Remplacer par les définitions opérationnelles verrouillées.
    out = df.copy()
    out["O"] = out.filter(regex=r"^O_raw_").mean(axis=1)
    out["R"] = out.filter(regex=r"^R_raw_").mean(axis=1)
    out["I"] = out.filter(regex=r"^I_raw_").mean(axis=1)

    out["V"] = (
        cfg.omega["survie"] * out["survie"]
        + cfg.omega["energie_nette"] * out["energie_nette"]
        + cfg.omega["integrite"] * out["integrite"]
        + cfg.omega["persistance"] * out["persistance"]
    )

    out["S"] = (
        cfg.alpha["repertoire"] * out["repertoire"]
        + cfg.alpha["codification"] * out["codification"]
        + cfg.alpha["densite_transmission"] * out["densite_transmission"]
        + cfg.alpha["fidelite"] * out["fidelite"]
    )

    if cfg.capacity_form == "product":
        out["Cap"] = out["O"] * out["R"] * out["I"]
    else:
        out["Cap"] = (out["O"] * out["R"] * out["I"]) ** (1.0 / 3.0)

    out["Sigma"] = (out["demande_env"] - out["Cap"]).clip(lower=0)

    # C(t) et s(t) sont laissés à définir selon le design.
    out["C"] = pd.NA
    out["s"] = pd.NA
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    cfg = load_config(args.config)
    df = pd.read_csv(args.input)
    out = compute_placeholder_scores(df, cfg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
