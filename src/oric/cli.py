"""Packaged command-line interface for ORI-C.

The commands in this module are intentionally self-contained and import only the
installed ``oric`` package. They are safe to run from an installed wheel, without
relying on repository-local ``scripts/`` or ``04_Code/`` files.
"""
from __future__ import annotations

import argparse
import json
import math
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import pandas as pd

from oric.ori_core import compute_cap_projection, compute_sigma, compute_viability, summarize_run
from oric.prereg import PreregSpec
from oric.symbolic import compute_order_C, compute_stock_S, detect_s_star_piecewise


def _package_version() -> str:
    try:
        return version("oric")
    except PackageNotFoundError:
        return "0+unknown"


def run_packaged_smoke() -> dict[str, Any]:
    """Run a deterministic package-only smoke check.

    This exercises the public ORI-C computational core from an installed package.
    It deliberately avoids repository-local scripts so that wheel installation is
    tested honestly.
    """
    df = pd.DataFrame(
        {
            "O": [0.80, 0.78, 0.76, 0.74, 0.73, 0.72],
            "R": [0.70, 0.70, 0.69, 0.68, 0.68, 0.67],
            "I": [0.60, 0.60, 0.61, 0.61, 0.62, 0.62],
            "demande_env": [0.20, 0.35, 0.42, 0.48, 0.55, 0.58],
            "survie": [0.90, 0.88, 0.84, 0.80, 0.76, 0.72],
            "energie_nette": [0.91, 0.87, 0.83, 0.79, 0.75, 0.71],
            "integrite": [0.89, 0.86, 0.82, 0.78, 0.74, 0.70],
            "persistance": [0.92, 0.89, 0.85, 0.81, 0.77, 0.73],
            "repertoire": [0.20, 0.24, 0.29, 0.35, 0.42, 0.50],
            "codification": [0.18, 0.23, 0.28, 0.34, 0.41, 0.49],
            "densite_transmission": [0.19, 0.25, 0.31, 0.38, 0.46, 0.55],
            "fidelite": [0.21, 0.26, 0.32, 0.39, 0.47, 0.56],
        }
    )
    prereg = PreregSpec()
    cap = compute_cap_projection(df["O"], df["R"], df["I"], form=prereg.cap_form)
    sigma = compute_sigma(df["demande_env"], cap, form=prereg.sigma_form)
    viability = compute_viability(df, prereg.omega_v)
    stock = compute_stock_S(df, prereg.alpha_s)

    tmp = df.copy()
    tmp["Cap"] = cap
    tmp["Sigma"] = sigma
    tmp["V"] = viability
    tmp["S"] = stock
    tmp["C"] = compute_order_C(tmp)
    threshold = detect_s_star_piecewise(tmp["S"].to_numpy(), tmp["C"].to_numpy())
    summary = summarize_run(tmp, window_W=3)

    s_star = float(threshold["S_star"])
    return {
        "ok": True,
        "package": "oric",
        "version": _package_version(),
        "n_points": int(len(tmp)),
        "cap_last": float(tmp["Cap"].iloc[-1]),
        "sigma_sum": float(tmp["Sigma"].sum()),
        "v_q05_tail": float(summary["V_q05"]),
        "s_star": None if math.isnan(s_star) else s_star,
        "threshold_improvement": float(threshold["improvement"]),
    }


def main_smoke(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a package-only ORI-C smoke check.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args(argv)
    result = run_packaged_smoke()
    if args.json:
        print(json.dumps(result, allow_nan=False, indent=2, sort_keys=True))
    else:
        print(
            "ORI-C smoke OK "
            f"version={result['version']} "
            f"n_points={result['n_points']} "
            f"sigma_sum={result['sigma_sum']:.6f}"
        )
    return 0


def main_version(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the installed ORI-C package version.")
    parser.parse_args(argv)
    print(_package_version())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oric", description="ORI-C packaged CLI.")
    sub = parser.add_subparsers(dest="command", required=True)
    smoke = sub.add_parser("smoke", help="Run a package-only smoke check.")
    smoke.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    sub.add_parser("version", help="Print package version.")
    args = parser.parse_args(argv)
    if args.command == "smoke":
        forwarded = ["--json"] if args.json else []
        return main_smoke(forwarded)
    if args.command == "version":
        return main_version([])
    parser.error(f"Unknown command: {args.command}")
    return 2


# Backward-compatible names for old console scripts. They now run a genuine
# package-only smoke instead of delegating to repository-local scripts.
def run_all() -> int:
    return main_smoke([])


def run_all_tests() -> int:
    return main_smoke([])


if __name__ == "__main__":
    raise SystemExit(main())
