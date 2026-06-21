#!/usr/bin/env python3
"""run_confirmatory_suite.py — Joint confirmatory verdict for a pilot.

Runs the four decisive controls (A accumulation specificity [global], B IAAFT
surrogate null, C multiverse, D effect size vs SESOI) and applies the frozen
joint rule: CONFIRMED iff all pass. This is the honest one-command answer to
"is this pilot a confirmed transition, or just a detectable trend?".

Usage
  python 04_Code/pipeline/run_confirmatory_suite.py \
    --input 03_Data/sector_cosmo/real/pilot_pantheon_sn/real_densified.csv \
    --outdir 05_Results/confirmatory/pantheon_sn --n-surrogates 500
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

from oric.confirmatory import run_confirmatory_suite  # noqa: E402
from ori_c_pipeline import ORICConfig, run_oric_from_observations  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(input_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    missing = [c for c in ("O", "R", "I") if c not in df.columns]
    if missing:
        raise SystemExit(f"input {input_csv} missing required columns: {missing}")
    if "t" not in df.columns:
        df.insert(0, "t", np.arange(len(df)))
    return df


def main() -> int:
    ap = argparse.ArgumentParser(description="ORI-C joint confirmatory suite")
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--n-surrogates", type=int, default=500)
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()

    n_surr = 40 if args.fast else args.n_surrogates
    out = Path(args.outdir)
    (out / "tables").mkdir(parents=True, exist_ok=True)

    df = _load(Path(args.input))
    cfg = ORICConfig(seed=args.seed, n_steps=len(df), intervention="none")

    print(f"[CONFIRM] {args.input} rows={len(df)} surrogates={n_surr}")
    result = run_confirmatory_suite(
        df, cfg, n_surrogates=n_surr, rng=np.random.default_rng(args.seed),
        run_fn=run_oric_from_observations,
    )
    result["input"] = str(args.input)
    result["n_rows"] = int(len(df))

    with open(out / "tables" / "confirmatory.json", "w") as f:
        json.dump(result, f, indent=2)
    (out / "verdict.txt").write_text(result["verdict"])

    manifest = {
        "test_id": "confirmatory_suite",
        "schema": "oric.confirmatory.manifest.v1",
        "input": str(args.input),
        "seed": args.seed,
        "n_surrogates": n_surr,
        "verdict": result["verdict"],
        "failing_tests": result["failing_tests"],
        "json_sha256": _sha256(out / "tables" / "confirmatory.json"),
    }
    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    t = result["tests"]
    print(f"\n  A accumulation_specificity : {'PASS' if t['A_accumulation_specificity']['pass'] else 'FAIL'}"
          f"  (fpr={t['A_accumulation_specificity']['accumulation_fpr']})")
    print(f"  B surrogate_null           : {'PASS' if t['B_surrogate_null']['pass'] else 'FAIL'}"
          f"  (p={t['B_surrogate_null']['p_value']:.3f})")
    print(f"  C multiverse               : {'PASS' if t['C_multiverse']['pass'] else 'FAIL'}"
          f"  ({t['C_multiverse']['robustness']})")
    print(f"  D effect_size              : {'PASS' if t['D_effect_size']['pass'] else 'FAIL'}"
          f"  ({t['D_effect_size']['verdict']})")
    print(f"\n  ===> {result['verdict']}"
          + (f" (limiting: {result['limiting_factor']})" if result['failing_tests'] else "") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
