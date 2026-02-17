#!/usr/bin/env python3
# analyse_verdicts_canonical.py
#
# Canonical aggregation of local test verdicts.
#
# Reads verdict.txt files produced by tests and applies a minimal decision tree:
# - core ORI (tests 1-3)
# - symbolic layer (tests 4-7)
# Writes:
# - global_verdicts.csv
# - global_verdict.txt

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import pandas as pd


VALID = {"ACCEPT", "REJECT", "INDETERMINATE"}


def read_verdict(path: Path) -> str:
    if not path.exists():
        return "INDETERMINATE"
    v = path.read_text(encoding="utf-8").strip().upper()
    return v if v in VALID else "INDETERMINATE"


@dataclass(frozen=True)
class AggregateConfig:
    allow_indeterminate_when_low_power: bool = True


def aggregate_core(v: Dict[str, str], cfg: AggregateConfig) -> str:
    t1 = v.get("Test1", "INDETERMINATE")
    t2 = v.get("Test2", "INDETERMINATE")
    t3 = v.get("Test3", "INDETERMINATE")

    if "REJECT" in (t1, t2, t3):
        return "REJECT"
    if t1 == "ACCEPT" and t2 == "ACCEPT" and t3 == "ACCEPT":
        return "ACCEPT"
    if cfg.allow_indeterminate_when_low_power and t1 == "ACCEPT" and t2 == "ACCEPT" and t3 == "INDETERMINATE":
        return "ACCEPT"
    return "INDETERMINATE"


def aggregate_symbolic(v: Dict[str, str]) -> str:
    t4 = v.get("Test4", "INDETERMINATE")
    t5 = v.get("Test5", "INDETERMINATE")
    t6 = v.get("Test6", "INDETERMINATE")
    t7 = v.get("Test7", "INDETERMINATE")

    if "REJECT" in (t4, t5, t6, t7):
        if t7 == "REJECT" and t4 != "ACCEPT":
            return "REJECT"
        return "REJECT"

    if t4 == "ACCEPT" and ("ACCEPT" in (t5, t6, t7)):
        return "ACCEPT"

    return "INDETERMINATE"


def aggregate_global(core: str, symbolic: str) -> str:
    if core == "REJECT" or symbolic == "REJECT":
        return "REJECT"
    if core == "ACCEPT" and symbolic == "ACCEPT":
        return "ACCEPT"
    return "INDETERMINATE"


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate local verdicts into core, symbolic, and global verdicts.")
    ap.add_argument("--results-root", default="05_Results", help="Root directory containing Test*/ verdicts.")
    ap.add_argument("--run-id", default=None, help="If provided, use 05_Results/canonical_runs/<run_id>/ as root.")
    args = ap.parse_args()

    root = Path(args.results_root)
    if args.run_id is not None:
        root = root / "canonical_runs" / args.run_id

    tests = ["Test1", "Test2", "Test3", "Test4", "Test5", "Test6", "Test7", "Test8", "Test9A", "Test9B"]
    verdicts: Dict[str, str] = {t: read_verdict(root / t / "verdict.txt") for t in tests}

    core = aggregate_core(verdicts, AggregateConfig())
    symbolic = aggregate_symbolic(verdicts)
    global_v = aggregate_global(core, symbolic)

    out = pd.DataFrame(
        [
            {"level": "core", "verdict": core},
            {"level": "symbolic", "verdict": symbolic},
            {"level": "global", "verdict": global_v},
        ]
    )
    out_path = root / "global_verdicts.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    (root / "global_verdict.txt").write_text(global_v + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
