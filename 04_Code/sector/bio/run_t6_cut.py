"""Run T6-cut on a bio-sector table using a frozen SSpec.

Examples:
  python 04_Code/sector/bio/run_t6_cut.py \\
      --csv path/to/table.csv \\
      --spec contracts/s_spec_epidemic.json \\
      --outdir 05_Results/t6_cut/epidemic
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


def _prepare(df: pd.DataFrame, spec: SSpec) -> pd.DataFrame:
    out = df.copy()
    if spec.source_column not in out.columns:
        raise SystemExit(f"missing S column {spec.source_column!r}; have {list(out.columns)}")
    if "S" not in out.columns:
        out["S"] = out[spec.source_column]
    if "V" not in out.columns:
        # last-resort viability proxy so the diagnostic can run on incomplete tables
        if "Cap" in out.columns:
            out["V"] = out["Cap"]
        else:
            raise SystemExit("table needs a V column (or Cap as fallback)")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="T6-cut diagnostic for bio SSpec")
    p.add_argument("--csv", required=True)
    p.add_argument("--spec", required=True)
    p.add_argument("--outdir", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--sham", default="permute_v", choices=("permute_v", "permute_cap"))
    args = p.parse_args()

    spec = SSpec.from_json_file(args.spec)
    df = _prepare(pd.read_csv(args.csv), spec)
    result = run_t6_cut(df, spec, sham=args.sham, seed=args.seed)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "spec": spec.to_dict(),
        "spec_sha256": spec.sha256(),
        "result": result.to_dict(),
    }
    (outdir / "t6_cut_verdict.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(result.verdict, result.reason)
    print("sha256", spec.sha256())
    print("wrote", outdir / "t6_cut_verdict.json")
    return 0 if result.verdict != "INDETERMINATE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
