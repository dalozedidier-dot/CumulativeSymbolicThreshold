#!/usr/bin/env python3
"""run_accumulation_control.py — The decisive trend-vs-transition control.

Feeds smooth, monotone, **non-bifurcating** accumulations (logistic growth,
Gompertz, exponential saturation, noisy linear ramp) plus genuine-bifurcation
contrasts through the *real* ORI-C detector path (``run_oric_from_observations``,
``auto_scale=True``) and asks the single decisive question:

    Does ORI-C's criterion ΔC > μ + k·σ (for m steps) separate a smooth
    accumulation from a genuine phase transition, or does it fire on both?

Outputs
  tables/accumulation_control.json   full per-control outcomes + decisive metrics
  tables/accumulation_control.csv    flat table
  figures/accumulation_delta_c.png   ΔC trajectories with the detection threshold
  verdict.txt                        SEPARATES / DOES_NOT_SEPARATE
  manifest.json                      audit trail (seed, params, sha256)

Frozen falsification rule (see 02_Protocol/PREREG_ADDENDUM_2026-06_ACCUMULATION_SURROGATE.md):
  accumulation_fpr > ACCUMULATION_FPR_MAX  ⇒  hypothesis refuted in current form.
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

from oric.accumulation_controls import (  # noqa: E402
    accumulation_control_catalogue,
    run_accumulation_control_suite,
)
from oric.surrogates import threshold_crossing_statistic  # noqa: E402
from ori_c_pipeline import ORICConfig, run_oric_from_observations  # noqa: E402

# Frozen ex-ante ceiling: at most this fraction of smooth non-bifurcating
# accumulations may be flagged as sustained transitions.
ACCUMULATION_FPR_MAX = 0.25


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

    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True)
    for ax, entry in zip(axes.ravel(), catalogue):
        out = run_oric_from_observations(entry.df, cfg)
        dC = out["delta_C"].to_numpy()
        cs = threshold_crossing_statistic(dC, k=cfg.k, m=cfg.m, baseline_n=cfg.baseline_n)
        ax.plot(dC, lw=1.0, color="#1f77b4")
        ax.axhline(cs.threshold, ls="--", color="#d62728", lw=1.0)
        colour = "#2ca02c" if entry.label == 1 else "#ff7f0e"
        ax.set_title(f"{entry.name}\nfired={cs.sustained_hit} run={cs.max_run}",
                     fontsize=8, color=colour)
        ax.tick_params(labelsize=7)
    fig.suptitle("ORI-C ΔC vs detection threshold — smooth accumulation (orange) vs bifurcation (green)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(figpath, dpi=110)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="Decisive trend-vs-transition accumulation control")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--n", type=int, default=220, help="series length")
    ap.add_argument("--n-surrogates", type=int, default=200,
                    help="IAAFT surrogates for the null (0 to skip)")
    ap.add_argument("--fast", action="store_true",
                    help="smoke mode: short series, few surrogates")
    args = ap.parse_args()

    n = 120 if args.fast else args.n
    n_surr = 40 if args.fast else args.n_surrogates

    out = Path(args.outdir)
    tables = out / "tables"
    figures = out / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    print(f"[ACC] n={n} seed={args.seed} surrogates={n_surr}")
    result = run_accumulation_control_suite(n=n, seed=args.seed, n_surrogates=n_surr)
    result["accumulation_fpr_max"] = ACCUMULATION_FPR_MAX
    refuted = result["accumulation_fpr"] > ACCUMULATION_FPR_MAX
    result["refutes_current_form"] = bool(refuted)

    with open(tables / "accumulation_control.json", "w") as f:
        json.dump(result, f, indent=2)

    with open(tables / "accumulation_control.csv", "w", newline="") as f:
        w = csv.writer(f)
        cols = [
            "name", "kind", "label", "detector_fired", "raw_detector_fired",
            "crossing_rate", "max_run", "acceleration_concentration",
            "acceleration_peak_fraction", "surrogate_p_rate", "surrogate_p_maxrun",
            "surrogate_significant",
        ]
        w.writerow(cols)
        for o in result["outcomes"]:
            w.writerow([o[c] for c in cols])

    # Figure
    cfg = ORICConfig(seed=args.seed, n_steps=n, intervention="none")
    _plot(accumulation_control_catalogue(n, args.seed), cfg, figures / "accumulation_delta_c.png")

    verdict = "DOES_NOT_SEPARATE" if not result["separates"] else "SEPARATES"
    (out / "verdict.txt").write_text(verdict)

    manifest = {
        "test_id": "accumulation_control",
        "schema": "oric.accumulation_control.manifest.v1",
        "seed": args.seed,
        "n_steps": n,
        "n_surrogates": n_surr,
        "fast_mode": args.fast,
        "accumulation_fpr_max": ACCUMULATION_FPR_MAX,
        "accumulation_fpr": result["accumulation_fpr"],
        "bifurcation_tpr": result["bifurcation_tpr"],
        "raw_accumulation_fpr": result.get("raw_accumulation_fpr"),
        "raw_bifurcation_tpr": result.get("raw_bifurcation_tpr"),
        "detector_note": result.get("detector_note"),
        "separates": result["separates"],
        "refutes_current_form": result["refutes_current_form"],
        "output_files": {
            "json": "tables/accumulation_control.json",
            "csv": "tables/accumulation_control.csv",
            "figure": "figures/accumulation_delta_c.png",
        },
        "json_sha256": _sha256(tables / "accumulation_control.json"),
    }
    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  accumulation_fpr = {result['accumulation_fpr']}  (max {ACCUMULATION_FPR_MAX})")
    print(f"  bifurcation_tpr  = {result['bifurcation_tpr']}")
    print(f"  separates        = {result['separates']}")
    print(f"  VERDICT          = {verdict}")
    if refuted:
        print("  ** accumulation_fpr exceeds the frozen ceiling: the localized")
        print("     transition gate still does not distinguish smooth accumulation")
        print("     from a genuine transition. **")
    if result.get("raw_accumulation_fpr", 0) > ACCUMULATION_FPR_MAX:
        print("  NOTE: raw_accumulation_fpr still records the older sustained ΔC")
        print("        crossing behaviour for audit continuity.")
    print(f"{'='*60}\n")

    # This control is diagnostic, not a CI gate: always exit 0 so the honest
    # finding is recorded as an artefact rather than masked by a non-zero code.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
