#!/usr/bin/env python3
"""run_strong_negatives.py — the strong-negatives specificity battery.

Runs a broad battery of adversarial **non-transition** processes (the cases a
trend/threshold detector most easily false-positives on) through the *real* ORI-C
detector path and asks the specificity question:

    Does the localized-transition gate stay SILENT on a unit-root random walk,
    AR(1) red noise, 1/f noise, a sinusoid, a sawtooth and smooth saturating
    accumulations — while still flagging genuine bifurcations?

Negatives (must NOT fire): logistic/Gompertz/exp-saturation/linear accumulations,
random_walk, ar1_red_noise, brownian_drift, pink_noise, white_noise, sinusoid,
sawtooth.  Positive contrast (must fire): sharp_regime_switch, delayed_bifurcation.

Outputs
  tables/strong_negatives.json   per-control outcomes + decisive metrics
  tables/strong_negatives.csv    flat table
  figures/strong_negatives.png   ΔC trajectories vs the detection threshold
  verdict.txt                    STRONG_NEGATIVES_CLEAN / _LEAK / _INSENSITIVE
  manifest.json                  audit trail (seed, params, sha256, contract sha)

Frozen criteria: contracts/STRONG_NEGATIVES_CRITERIA.json (fpr_max=0.10, tpr_min=0.50).
This is a diagnostic artefact, not a CI gate: it always exits 0 so an honest LEAK
is recorded rather than masked. See docs/EVIDENCE_LADDER.md (rung 7).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_HERE))

from oric.strong_negatives import (  # noqa: E402
    FPR_MAX,
    TPR_MIN,
    run_strong_negatives_suite,
    strong_negatives_catalogue,
)
from oric.surrogates import threshold_crossing_statistic  # noqa: E402
from ori_c_pipeline import ORICConfig, run_oric_from_observations  # noqa: E402

_CONTRACT = _REPO / "contracts" / "STRONG_NEGATIVES_CRITERIA.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _plot(catalogue, cfg, figpath: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"  [figure] skipped: {exc}")
        return

    n = len(catalogue)
    ncol = 4
    nrow = (n + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 2.6 * nrow), sharex=True)
    for ax, entry in zip(axes.ravel(), catalogue):
        out = run_oric_from_observations(entry.df, cfg)
        dC = out["delta_C"].to_numpy()
        cs = threshold_crossing_statistic(dC, k=cfg.k, m=cfg.m, baseline_n=cfg.baseline_n)
        ax.plot(dC, lw=0.9, color="#1f77b4")
        ax.axhline(cs.threshold, ls="--", color="#d62728", lw=0.9)
        colour = "#2ca02c" if entry.label == 1 else "#ff7f0e"
        ax.set_title(f"{entry.name}\nraw_fired={cs.sustained_hit}", fontsize=7, color=colour)
        ax.tick_params(labelsize=6)
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    fig.suptitle("ORI-C ΔC vs threshold — strong negatives (orange, must NOT fire) vs bifurcations (green)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(figpath, dpi=110)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C strong-negatives specificity battery")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--n", type=int, default=220, help="series length")
    ap.add_argument("--n-surrogates", type=int, default=0,
                    help="IAAFT surrogates for the per-control null (0 to skip)")
    ap.add_argument("--fast", action="store_true",
                    help="smoke mode: short series, no surrogates")
    args = ap.parse_args()

    n = 120 if args.fast else args.n
    n_surr = 0 if args.fast else args.n_surrogates

    out = Path(args.outdir)
    tables = out / "tables"
    figures = out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    print(f"[STRONG-NEG] n={n} seed={args.seed} surrogates={n_surr}")
    result = run_strong_negatives_suite(n=n, seed=args.seed, n_surrogates=n_surr)
    result["fpr_max"] = FPR_MAX
    result["tpr_min"] = TPR_MIN

    json_path = tables / "strong_negatives.json"
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2)

    with open(tables / "strong_negatives.csv", "w", newline="") as f:
        w = csv.writer(f)
        cols = ["name", "kind", "family", "label", "detector_fired",
                "raw_detector_fired", "crossing_rate", "max_run", "surrogate_p"]
        w.writerow(cols)
        for o in result["outcomes"]:
            w.writerow([o[c] for c in cols])

    cfg = ORICConfig(seed=args.seed, n_steps=n, intervention="none")
    _plot(strong_negatives_catalogue(n, args.seed), cfg, figures / "strong_negatives.png")

    verdict = result["verdict"]
    (out / "verdict.txt").write_text(verdict + "\n")

    manifest = {
        "test_id": "strong_negatives",
        "schema": "oric.strong_negatives.manifest.v1",
        "seed": args.seed,
        "n_steps": n,
        "n_surrogates": n_surr,
        "fast_mode": args.fast,
        "fpr_max": FPR_MAX,
        "tpr_min": TPR_MIN,
        "strong_negatives_fpr": result["strong_negatives_fpr"],
        "raw_strong_negatives_fpr": result["raw_strong_negatives_fpr"],
        "bifurcation_tpr": result["bifurcation_tpr"],
        "fpr_by_family": result["fpr_by_family"],
        "verdict": verdict,
        "output_files": {
            "json": "tables/strong_negatives.json",
            "csv": "tables/strong_negatives.csv",
            "figure": "figures/strong_negatives.png",
        },
        "json_sha256": _sha256(json_path),
        "contract_sha256": _sha256(_CONTRACT) if _CONTRACT.exists() else None,
    }
    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*64}")
    print(f"  strong_negatives_fpr (localized) = {result['strong_negatives_fpr']}  (max {FPR_MAX})")
    print(f"  raw_strong_negatives_fpr (bare)  = {result['raw_strong_negatives_fpr']}")
    print(f"  bifurcation_tpr                  = {result['bifurcation_tpr']}  (min {TPR_MIN})")
    print(f"  fpr_by_family                    = {result['fpr_by_family']}")
    print(f"  VERDICT                          = {verdict}")
    if verdict == "STRONG_NEGATIVES_LEAK":
        print("  ** localized FPR exceeds the frozen ceiling: the gate leaks on")
        print("     adversarial nulls — honest negative, reported at equal status. **")
    print(f"{'='*64}\n")

    # Diagnostic artefact, never a hard gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
