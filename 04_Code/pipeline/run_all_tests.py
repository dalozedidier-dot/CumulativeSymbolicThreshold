#!/usr/bin/env python3
"""
04_Code/pipeline/run_all_tests.py

Orchestrator for a canonical, reproducible run of the repo's main demos/tests.

It runs (when available):
- run_ori_c_demo.py
- tests_causaux.py
- run_synthetic_demo.py
- run_robustness.py
- run_reinjection_demo.py

It also standardizes a global summary:
- global_verdicts.csv
- global_verdict.json
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure 04_Code is on sys.path so `import pipeline.*` works when scripts are executed directly.
_CODE_DIR = Path(__file__).resolve().parents[1]
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from pipeline.ori_c_pipeline import ORICConfig, run_oric


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _ensure_input_csv(root: Path, outdir: Path, input_csv: str | None) -> Path:
    if input_csv:
        p = Path(input_csv)
        if p.is_file():
            return p

    # Prefer a committed canonical synthetic dataset if available.
    preferred = root / "03_Data" / "synthetic" / "synthetic_with_threshold.csv"
    if preferred.is_file():
        return preferred

    fallback = root / "03_Data" / "synthetic" / "synthetic_with_transition.csv"
    if fallback.is_file():
        return fallback

    # Last resort: generate a synthetic run with a demand shock.
    gen = outdir / "_generated_synthetic.csv"
    df = run_oric(ORICConfig(intervention="demand_shock"))
    df.to_csv(gen, index=False)
    return gen
def _read_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _verdict_from_ori_demo(test_dir: Path) -> str:
    summary = test_dir / "tables" / "summary.csv"
    if not summary.exists():
        return "INDETERMINATE"
    df = pd.read_csv(summary)
    # Expect two rows: control and intervention
    if "condition" not in df.columns or "V_mean_post" not in df.columns:
        return "INDETERMINATE"
    try:
        v_control = float(df.loc[df["condition"] == "control", "V_mean_post"].iloc[0])
        v_interv = float(df.loc[df["condition"] == "intervention", "V_mean_post"].iloc[0])
    except Exception:
        return "INDETERMINATE"
    return "ACCEPT" if v_interv < v_control else "INDETERMINATE"


def _verdict_from_causal_tests(test_dir: Path) -> str:
    """Local verdict for the causal suite.

    Preferred source of truth is tables/verdict.json if present.
    A CSV heuristic is kept only for backward compatibility.
    """
    vjson = test_dir / "tables" / "verdict.json"
    if vjson.exists():
        return str(_read_json(vjson).get("verdict", "INDETERMINATE"))

    p = test_dir / "tables" / "causal_tests_summary.csv"
    if not p.exists():
        return "INDETERMINATE"
    df = pd.read_csv(p)
    if "causal_ok" not in df.columns:
        return "INDETERMINATE"
    if bool((df["causal_ok"] == True).all()):  # noqa: E712
        return "ACCEPT"
    return "INDETERMINATE"
def _verdict_from_synthetic_demo(test_dir: Path) -> str:
    p = test_dir / "tables" / "verdict.json"
    if not p.exists():
        return "INDETERMINATE"
    return str(_read_json(p).get("verdict", "INDETERMINATE"))


def _verdict_from_robustness(test_dir: Path) -> str:
    """Local verdict for robustness.

    Preferred source of truth is tables/verdict.json if present.
    The CSV heuristic is kept for backward compatibility.
    """
    vjson = test_dir / "tables" / "verdict.json"
    if vjson.exists():
        return str(_read_json(vjson).get("verdict", "INDETERMINATE"))

    p = test_dir / "tables" / "robustness_results.csv"
    if not p.exists():
        return "INDETERMINATE"
    df = pd.read_csv(p)
    if "threshold_detected" not in df.columns:
        return "INDETERMINATE"
    share = float((df["threshold_detected"] == True).mean())  # noqa: E712
    if share >= 0.80:
        return "ACCEPT"
    return "INDETERMINATE"
def _verdict_from_reinjection(test_dir: Path) -> str:
    p = test_dir / "tables" / "verdict.json"
    if not p.exists():
        return "INDETERMINATE"
    return str(_read_json(p).get("verdict", "INDETERMINATE"))


def _aggregate(verdicts: Dict[str, str]) -> Dict[str, str]:
    core_ok = (verdicts.get("T1_ori_demo") == "ACCEPT") and (verdicts.get("T2_causal") == "ACCEPT")
    symbolic_ok = (
        (verdicts.get("T3_synth_threshold") == "ACCEPT")
        and (verdicts.get("T4_robustness") in {"ACCEPT", "INDETERMINATE"})
        and (verdicts.get("T5_reinjection") in {"ACCEPT", "INDETERMINATE"})
    )

    if core_ok and symbolic_ok:
        global_v = "ACCEPT"
    elif "REJECT" in verdicts.values():
        global_v = "REJECT"
    else:
        global_v = "INDETERMINATE"

    return {
        "core": "ACCEPT" if core_ok else "INDETERMINATE",
        "symbolic": "ACCEPT" if symbolic_ok else "INDETERMINATE",
        "global": global_v,
    }
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outroot", default=None, help="Base directory under 05_Results/")
    ap.add_argument("--input", default=None, help="Optional synthetic CSV input")
    ap.add_argument("--intervention", default="symbolic_cut", help="Intervention for ORI-C demo")
    args = ap.parse_args()

    here = Path(__file__).resolve()
    root = here.parents[2]
    results_root = root / "05_Results"
    outroot = Path(args.outroot) if args.outroot else (results_root / "canonical_tests" / _ts())
    outroot.mkdir(parents=True, exist_ok=True)

    input_csv = _ensure_input_csv(root, outroot, args.input)

    # T1: ORI-C demo
    t1 = outroot / "T1_ori_demo"
    _run([sys.executable, str(root / "04_Code" / "pipeline" / "run_ori_c_demo.py"), "--outdir", str(t1), "--intervention", str(args.intervention)])

    # T2: causal tests
    t2 = outroot / "T2_causal"
    _run([sys.executable, str(root / "04_Code" / "pipeline" / "tests_causaux.py"), "--outdir", str(t2)])

    # T3: synthetic demo threshold
    t3 = outroot / "T3_synth_threshold"
    _run([sys.executable, str(root / "04_Code" / "pipeline" / "run_synthetic_demo.py"), "--input", str(input_csv), "--outdir", str(t3)])

    # T4: robustness (requires run_synthetic_demo helpers)
    t4 = outroot / "T4_robustness"
    _run([sys.executable, str(root / "04_Code" / "pipeline" / "run_robustness.py"), "--input", str(input_csv), "--outdir", str(t4)])

    # T5: reinjection demo
    t5 = outroot / "T5_reinjection"
    _run([sys.executable, str(root / "04_Code" / "pipeline" / "run_reinjection_demo.py"), "--outdir", str(t5)])

    verdicts = {
        "T1_ori_demo": _verdict_from_ori_demo(t1),
        "T2_causal": _verdict_from_causal_tests(t2),
        "T3_synth_threshold": _verdict_from_synthetic_demo(t3),
        "T4_robustness": _verdict_from_robustness(t4),
        "T5_reinjection": _verdict_from_reinjection(t5),
    }

    agg = _aggregate(verdicts)

    df = pd.DataFrame([{"test": k, "verdict_local": v} for k, v in verdicts.items()])
    df = pd.concat([df, pd.DataFrame([{"test": "GLOBAL", "verdict_local": agg["global"]}])], ignore_index=True)
    df.to_csv(outroot / "global_verdicts.csv", index=False)

    (outroot / "global_verdict.json").write_text(json.dumps({"verdicts": verdicts, "aggregate": agg}, indent=2), encoding="utf-8")

    print("Results:", outroot)
    print("Global verdict:", agg["global"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
