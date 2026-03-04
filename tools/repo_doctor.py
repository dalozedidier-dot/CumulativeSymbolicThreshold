#!/usr/bin/env python3
"""Repo doctor (ORI-C)

But : vérifier rapidement que l'arbo, les points de vérité et les invariants CI sont cohérents.
Sortie : 0 si OK, 1 si warnings, 2 si erreurs.

Ce script ne modifie rien. Il sert de check local et peut être branché en CI si souhaité.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ERRORS = 0
WARNS = 0

def err(msg: str) -> None:
    global ERRORS
    ERRORS += 1
    print(f"[ERR] {msg}")

def warn(msg: str) -> None:
    global WARNS
    WARNS += 1
    print(f"[WARN] {msg}")

def ok(msg: str) -> None:
    print(f"[OK] {msg}")

def main() -> int:
    # Point of truth
    pot = ROOT / "docs" / "ORI_C_POINT_OF_TRUTH.md"
    if not pot.exists():
        err("docs/ORI_C_POINT_OF_TRUTH.md manquant (point de vérité attendu).")
    else:
        ok("Point de vérité présent.")

    # Root redirect file optional
    pot_root = ROOT / "ORIC_POINT_OF_TRUTH.md"
    if pot_root.exists():
        warn("ORIC_POINT_OF_TRUTH.md en racine présent. Doit être un redirect de compatibilité (pas une 2e vérité).")

    # Data duplication note
    if (ROOT/"03_Data").exists() and (ROOT/"data").exists():
        ok("03_Data/ et data/ coexistent. Vérifier docs/REPO_LAYOUT.md pour règles de vérité.")

    # Requirements path sanity
    req_qcc_root = ROOT / "requirements-qcc-stateprob.txt"
    req_qcc_alt = ROOT / "requirements" / "requirements-qcc-stateprob.txt"
    if not req_qcc_root.exists() and not req_qcc_alt.exists():
        err("Requirements QCC stateprob introuvables (requirements-qcc-stateprob.txt ou requirements/requirements-qcc-stateprob.txt).")
    else:
        ok("Requirements QCC stateprob présents (au moins un chemin).")

    # CI metrics directory
    if not (ROOT/"ci_metrics").exists():
        warn("ci_metrics/ absent. Normal si collector pas encore exécuté.")
    else:
        ok("ci_metrics/ présent.")

    if ERRORS:
        return 2
    if WARNS:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
