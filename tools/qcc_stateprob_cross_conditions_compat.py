"""
Compatibility wrapper for qcc_stateprob_cross_conditions.

Problem fixed:
- Some workflow runs pass --metric ccl (historical ORI-C/QCC naming),
  but tools.qcc_stateprob_cross_conditions only accepts:
    entropy, impurity, one_minus_max

This wrapper accepts 'ccl' as a synonym for 'impurity' while preserving
the external/audit-facing naming 'ccl' in outputs (filenames + summary.json).

Design goals:
- Purely mechanical, no inference.
- Robust: if upstream changes outputs, wrapper degrades gracefully.
- Keeps existing workflow interface stable.

Usage (CI):
  python -m tools.qcc_stateprob_cross_conditions_compat --dataset ... --out-root ... --metric ccl ...

It delegates to tools.qcc_stateprob_cross_conditions after translating metric,
then post-processes the latest run directory to rename "impurity" -> "ccl"
in filenames and in a few JSON fields where safe.

"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def _latest_run_dir(out_root: Path) -> Optional[Path]:
    runs_dir = out_root / "runs"
    if not runs_dir.exists():
        return None
    candidates = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not candidates:
        return None
    # timestamp-like names sort lexicographically correctly for YYYYMMDD_HHMMSS
    return sorted(candidates)[-1]


def _safe_load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _rename_impurity_to_ccl(run_dir: Path) -> None:
    # Rename files containing "impurity" to "ccl" under run_dir/{tables,figures}
    for sub in ("tables", "figures"):
        d = run_dir / sub
        if not d.exists():
            continue
        for p in list(d.rglob("*")):
            if p.is_file() and "impurity" in p.name:
                p.rename(p.with_name(p.name.replace("impurity", "ccl")))

    # Patch common JSON files if present
    for json_name in ("summary.json", "selected_plan.json", "recommendations.json", "params.json"):
        p = run_dir / json_name
        if not p.exists():
            continue
        obj = _safe_load_json(p)
        if not isinstance(obj, dict):
            continue

        # Only patch obviously safe fields
        for k in ("metric", "metric_name", "score_metric"):
            if k in obj and obj[k] == "impurity":
                obj[k] = "ccl"

        _safe_write_json(p, obj)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="qcc_stateprob_cross_conditions_compat")
    ap.add_argument("--dataset", required=True, help="Path to StateProb dataset zip/folder")
    ap.add_argument("--out-dir", default=None, help="Optional legacy single-run output directory")
    ap.add_argument("--out-root", default=None, help="Output root, expected to contain runs/<timestamp>/")
    ap.add_argument("--auto-plan", action="store_true", help="Enable auto-plan selection")
    ap.add_argument("--no-auto-plan", action="store_true", help="Disable auto-plan selection")
    ap.add_argument("--algo", default=None)
    ap.add_argument("--device", default=None)
    ap.add_argument("--shots", default=None)
    ap.add_argument(
        "--metric",
        default="ccl",
        choices=["ccl", "entropy", "impurity", "one_minus_max"],
        help="Metric selector. 'ccl' is accepted as synonym for 'impurity'.",
    )
    ap.add_argument("--threshold", type=float, default=0.35)
    ap.add_argument("--bootstrap-samples", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # Resolve output root
    out_root = None
    if args.out_root:
        out_root = Path(args.out_root)
    elif args.out_dir:
        # Some older code uses --out-dir only. We emulate out-root behavior by using parent.
        out_root = Path(args.out_dir).parent
    else:
        out_root = Path("_ci_out/qcc_stateprob_cross")

    out_root.mkdir(parents=True, exist_ok=True)

    want_metric = args.metric
    delegate_metric = "impurity" if want_metric == "ccl" else want_metric

    # Build argv for the delegate module
    delegate_argv: List[str] = [
        "--dataset",
        args.dataset,
        "--out-root",
        str(out_root),
        "--metric",
        delegate_metric,
        "--threshold",
        str(args.threshold),
        "--bootstrap-samples",
        str(args.bootstrap_samples),
        "--seed",
        str(args.seed),
    ]

    # auto-plan flags
    if args.auto_plan and args.no_auto_plan:
        # Prefer explicit disable if both were passed (defensive)
        delegate_argv.append("--no-auto-plan")
    elif args.auto_plan:
        delegate_argv.append("--auto-plan")
    elif args.no_auto_plan:
        delegate_argv.append("--no-auto-plan")

    # optional filters
    if args.algo:
        delegate_argv += ["--algo", args.algo]
    if args.device:
        delegate_argv += ["--device", args.device]
    if args.shots:
        delegate_argv += ["--shots", str(args.shots)]

    # Delegate execution
    from tools import qcc_stateprob_cross_conditions as delegate  # type: ignore

    rc = 0
    try:
        rc = int(delegate.main(delegate_argv))  # expecting a main(argv)->int pattern
    except AttributeError:
        # Fallback: module may expose cli_main or use argparse in __main__
        try:
            rc = int(delegate.cli_main(delegate_argv))  # type: ignore
        except Exception:
            # Last resort: execute as module
            import runpy
            import sys

            old_argv = sys.argv[:]
            sys.argv = ["-m", "tools.qcc_stateprob_cross_conditions"] + delegate_argv
            try:
                runpy.run_module("tools.qcc_stateprob_cross_conditions", run_name="__main__")
                rc = 0
            except SystemExit as e:
                rc = int(e.code or 0)
            finally:
                sys.argv = old_argv
    except SystemExit as e:
        rc = int(e.code or 0)
    except Exception as e:
        print(f"[compat] delegate failed: {e}")
        return 2

    # Post-process naming if we asked for ccl
    if rc == 0 and want_metric == "ccl":
        run_dir = _latest_run_dir(out_root)
        if run_dir is not None:
            _rename_impurity_to_ccl(run_dir)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
