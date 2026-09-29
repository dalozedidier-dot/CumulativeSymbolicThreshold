"""Run T6-cut on a bio-sector table using a frozen SSpec.

Examples:
  python 04_Code/sector/bio/run_t6_cut.py \\
      --csv path/to/table.csv \\
      --spec contracts/s_spec_lineage_synthetic.json \\
      --outdir 05_Results/t6_cut/lineage_synthetic
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "src"))

from oric.s_spec import SSpec
from oric.t6_cut import run_t6_cut


def main() -> int:
    p = argparse.ArgumentParser(description="T6-cut diagnostic for bio SSpec")
    p.add_argument("--csv", required=True)
    p.add_argument("--spec", help="SSpec JSON; absence produces INDETERMINATE")
    p.add_argument("--outdir", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--sham", default="permute_v", choices=("permute_v", "permute_cap"))
    args = p.parse_args()

    spec = None
    spec_error = None
    if args.spec:
        try:
            spec = SSpec.from_json_file(args.spec)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            spec_error = f"invalid SSpec: {exc}"
    df = pd.read_csv(args.csv)
    result = run_t6_cut(df, spec, sham=args.sham, seed=args.seed)
    if spec_error:
        result.reason = spec_error

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "spec": spec.to_dict() if spec else None,
        "spec_sha256": spec.sha256() if spec else None,
        "result": result.to_dict(),
    }
    (outdir / "t6_cut_verdict.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    print(result.verdict, result.reason)
    print("sha256", result.spec_sha256)
    print("wrote", outdir / "t6_cut_verdict.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
