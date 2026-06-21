#!/usr/bin/env python3
"""run_surrogate_null.py — IAAFT surrogate null for ORI-C threshold crossing.

Gives the missing null law for statements like "176/250 steps exceed the
threshold": compares the observed crossing statistic of a real series against
the distribution obtained on IAAFT surrogates that preserve, per channel, the
amplitude distribution and power spectrum (hence the full linear autocorrelation)
while destroying nonlinear / cross-channel phase structure.

Usage
  python 04_Code/pipeline/run_surrogate_null.py \
    --input 03_Data/real/fred_monthly/real.csv \
    --outdir 05_Results/surrogate_null/fred \
    --n-surrogates 500 --seed 1234

Outputs
  tables/surrogate_null.json   observed stat, null summary, empirical p-value
  figures/surrogate_null.png   null histogram with the observed value marked
  verdict.txt                  SIGNIFICANT / NOT_SIGNIFICANT (α = 0.01)
  manifest.json                audit trail
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_HERE))

from oric.surrogates import surrogate_null_test  # noqa: E402
from ori_c_pipeline import ORICConfig, run_oric_from_observations  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    required = ["O", "R", "I"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"input {input_csv} missing required columns: {missing}")
    if "t" not in df.columns:
        df.insert(0, "t", np.arange(len(df)))
    return df


def _plot(res, figpath: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"  [figure] skipped: {exc}")
        return
    # Recompute the null sample is not stored; draw a normal approx band instead
    # using the reported summary plus the observed value marker.
    fig, ax = plt.subplots(figsize=(6, 4))
    mu, sd = res.null_mean, max(res.null_std, 1e-9)
    xs = np.linspace(min(mu - 4 * sd, res.observed), max(mu + 4 * sd, res.observed), 200)
    ax.plot(xs, np.exp(-0.5 * ((xs - mu) / sd) ** 2), color="#7f7f7f", label="IAAFT null (Gaussian approx)")
    ax.axvline(res.observed, color="#d62728", lw=2, label=f"observed = {res.observed:.3f}")
    ax.axvline(res.null_q99, color="#1f77b4", ls="--", lw=1, label=f"null q99 = {res.null_q99:.3f}")
    ax.set_xlabel(res.statistic)
    ax.set_ylabel("density (approx)")
    ax.set_title(f"Surrogate null — p = {res.p_value:.4f} ({'SIG' if res.significant_at_01 else 'n.s.'} at α=0.01)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figpath, dpi=110)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="IAAFT surrogate null for ORI-C threshold crossing")
    ap.add_argument("--input", required=True, help="CSV with O,R,I[,demand,S] columns")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--n-surrogates", type=int, default=500)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--statistic", choices=["crossing_rate", "max_run"], default="crossing_rate")
    ap.add_argument("--k", type=float, default=2.5)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--baseline-n", type=int, default=30)
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()

    n_surr = 40 if args.fast else args.n_surrogates
    out = Path(args.outdir)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)

    df = _load(Path(args.input))
    cfg = ORICConfig(seed=args.seed, n_steps=len(df), intervention="none",
                     k=args.k, m=args.m, baseline_n=args.baseline_n)
    rng = np.random.default_rng(args.seed)

    print(f"[SURR] input={args.input} rows={len(df)} surrogates={n_surr} stat={args.statistic}")
    res = surrogate_null_test(
        df, cfg, n_surrogates=n_surr, statistic=args.statistic,
        rng=rng, run_fn=run_oric_from_observations,
    )

    payload = res.to_dict()
    payload["input"] = str(args.input)
    payload["n_rows"] = int(len(df))
    with open(out / "tables" / "surrogate_null.json", "w") as f:
        json.dump(payload, f, indent=2)

    _plot(res, out / "figures" / "surrogate_null.png")

    verdict = "SIGNIFICANT" if res.significant_at_01 else "NOT_SIGNIFICANT"
    (out / "verdict.txt").write_text(verdict)

    manifest = {
        "test_id": "surrogate_null",
        "schema": "oric.surrogate_null.manifest.v1",
        "input": str(args.input),
        "seed": args.seed,
        "n_surrogates": n_surr,
        "statistic": args.statistic,
        "observed": res.observed,
        "p_value": res.p_value,
        "significant_at_01": res.significant_at_01,
        "json_sha256": _sha256(out / "tables" / "surrogate_null.json"),
    }
    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n  observed {args.statistic} = {res.observed:.4f}")
    print(f"  null mean = {res.null_mean:.4f}  q99 = {res.null_q99:.4f}  max = {res.null_max:.4f}")
    print(f"  empirical p = {res.p_value:.4f}  ->  {verdict} (α=0.01)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
