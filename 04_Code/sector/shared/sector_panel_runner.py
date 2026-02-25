"""sector_panel_runner.py — Shared sector panel execution engine.

Called by each sector's run_sector_suite.py.  Provides a single
run_sector_panel(config, args) function that:

  1. Validates the proxy spec           → mapping_validity_verdict
  2. Generates synthetic pilot data     → via sector generate_synth.py
  3. Runs real-data pipeline            → run_real_data_demo.py
  4. Runs causal tests                  → tests_causaux.py
  5. Runs robustness variants           → window, normalization, resampling
  6. Aggregates all verdicts            → sector_global_verdict.json

Output directory layout (mirrors canonical suite):
  <outdir>/
    pilot_<pilot_id>/
      synth/                     # synthetic T1-T8 sub-run
        tables/
        figures/
        manifest.json
        verdict.json
      real/                      # real-data sub-run
        tables/
        figures/
        manifest.json
        verdict.json
      robustness/
        variant_<name>/
          tables/
          verdict.json
      mapping_validity.json
      sector_global_verdict.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# --------------------------------------------------------------------------- #
# Config dataclass
# --------------------------------------------------------------------------- #

@dataclass
class SectorConfig:
    """Immutable configuration for a sector panel runner."""
    sector_id: str                      # "bio" | "cosmo" | "infra"
    pilot_ids: list[str]                # ["epidemic", "geneexpr", ...]
    default_pilot: str                  # pilot used when --pilot-id not given

    # paths relative to repo root (resolved at runtime)
    data_root: str                      # "03_Data/sector_<name>"
    code_root: str                      # "04_Code/sector/<name>"

    # canonical pipeline scripts (relative to repo root)
    run_real_script:  str = "04_Code/pipeline/run_real_data_demo.py"
    run_synth_script: str = "04_Code/pipeline/run_synthetic_demo.py"
    causal_script:    str = "04_Code/pipeline/tests_causaux.py"
    validate_script:  str = "04_Code/pipeline/validate_proxy_spec.py"

    # default run parameters
    default_seed:      int  = 1234
    default_n_runs:    int  = 50
    default_alpha:     str  = "0.01"
    default_lags:      str  = "1-5"
    default_normalize: str  = "robust_minmax"

    # robustness variants (window_size, normalize, resample_frac)
    robustness_variants: list[dict[str, Any]] = field(default_factory=lambda: [
        {"name": "window_short",  "pre_horizon": 50,  "post_horizon": 50,  "normalize": "robust_minmax"},
        {"name": "window_medium", "pre_horizon": 100, "post_horizon": 100, "normalize": "robust_minmax"},
        {"name": "norm_minmax",   "pre_horizon": 100, "post_horizon": 100, "normalize": "minmax"},
        {"name": "resample_80",   "pre_horizon": 100, "post_horizon": 100, "normalize": "robust_minmax",
         "resample_frac": 0.80},
    ])


# --------------------------------------------------------------------------- #
# Subprocess helper
# --------------------------------------------------------------------------- #

def _run(cmd: list[str], cwd: Path, label: str, timeout: int = 600) -> dict[str, Any]:
    """Run subprocess, return {"ok", "returncode", "stdout", "stderr"}."""
    print(f"  [{label}] running: {' '.join(str(c) for c in cmd[-6:])}")
    t0 = time.monotonic()
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(cwd), timeout=timeout,
        )
        elapsed = time.monotonic() - t0
        ok = r.returncode == 0
        if not ok:
            print(f"  [{label}] FAILED (rc={r.returncode}, {elapsed:.1f}s)")
            print(r.stderr[-400:] if r.stderr else "")
        else:
            print(f"  [{label}] OK ({elapsed:.1f}s)")
        return {"ok": ok, "returncode": r.returncode,
                "stdout": r.stdout, "stderr": r.stderr}
    except subprocess.TimeoutExpired:
        print(f"  [{label}] TIMEOUT after {timeout}s")
        return {"ok": False, "returncode": -1,
                "stdout": "", "stderr": f"timeout after {timeout}s"}
    except Exception as exc:
        return {"ok": False, "returncode": -1,
                "stdout": "", "stderr": str(exc)}


# --------------------------------------------------------------------------- #
# Verdict helpers
# --------------------------------------------------------------------------- #

def _read_verdict(path: Path) -> str:
    """Read verdict from verdict.txt or verdict.json → canonical token."""
    txt = path / "verdict.txt"
    js  = path / "tables" / "verdict.json"
    if txt.exists():
        raw = txt.read_text().strip().upper()
        for tok in ("ACCEPT", "REJECT", "INDETERMINATE"):
            if tok in raw:
                return tok
        return "INDETERMINATE"
    if js.exists():
        try:
            data = json.loads(js.read_text())
            raw  = str(data.get("verdict", "")).upper()
            for tok in ("ACCEPT", "REJECT", "INDETERMINATE"):
                if tok in raw:
                    return tok
        except Exception:
            pass
    return "INDETERMINATE"


def _aggregate_verdicts(verdicts: list[str]) -> str:
    """ACCEPT only if all ACCEPT; REJECT if any REJECT; else INDETERMINATE."""
    if any(v == "REJECT" for v in verdicts):
        return "REJECT"
    if all(v == "ACCEPT" for v in verdicts):
        return "ACCEPT"
    return "INDETERMINATE"


def _support_level(verdict: str, mapping_verdict: str) -> str:
    if mapping_verdict == "REJECT":
        return "rejected_invalid_mapping"
    if verdict == "ACCEPT" and mapping_verdict == "ACCEPT":
        return "sector_panel_support"
    if verdict == "ACCEPT" and mapping_verdict == "INDETERMINATE":
        return "sector_panel_support_mapping_caveat"
    if verdict == "INDETERMINATE":
        return "sector_panel_indeterminate"
    return "rejected"


# --------------------------------------------------------------------------- #
# Main panel runner
# --------------------------------------------------------------------------- #

def run_sector_panel(
    config: SectorConfig,
    args: argparse.Namespace,
    repo_root: Path,
    synth_generator: Callable[[Path, int, str], None],
) -> int:
    """
    Run the full sector panel for one pilot.

    synth_generator(outdir, seed, pilot_id):
        writes outdir/real.csv + outdir/proxy_spec.json
        (used when --real-csv is not provided)

    Returns exit code: 0 = ACCEPT/INDETERMINATE, 1 = REJECT.
    """
    pilot_id  = args.pilot_id
    out_root  = Path(args.outdir) / f"pilot_{pilot_id}"
    seed      = args.seed
    py        = sys.executable

    print(f"\n{'='*60}")
    print(f"  SECTOR PANEL: {config.sector_id.upper()} / {pilot_id}")
    print(f"  outdir: {out_root}")
    print(f"{'='*60}\n")

    # ---------------------------------------------------------------------- #
    # 1. Resolve data paths
    # ---------------------------------------------------------------------- #
    data_dir   = repo_root / config.data_root / "real" / f"pilot_{pilot_id}"
    spec_path  = data_dir / "proxy_spec.json"

    synth_dir  = out_root / "synth_data"
    synth_dir.mkdir(parents=True, exist_ok=True)

    # If no real CSV provided, generate synthetic pilot data
    if args.real_csv:
        csv_path = Path(args.real_csv)
    else:
        print("[step 0] Generating synthetic pilot data...")
        try:
            synth_generator(synth_dir, seed, pilot_id)
            csv_path = synth_dir / "real.csv"
            # In synthetic mode: always prefer the synth proxy_spec (its source_column
            # values are the generic ORI roles "O","R","I","S","demand" that match the
            # generated CSV).  The real proxy_spec from 03_Data/ uses domain-specific
            # column names (e.g. "case_fatality_proxy") that only exist in real CSVs.
            synth_spec = synth_dir / "proxy_spec.json"
            if synth_spec.exists():
                spec_path = synth_spec
            elif not spec_path.exists():
                print("[FATAL] No proxy_spec.json found in synth dir or real data dir")
                return 1
            print(f"         → {csv_path}  (rows: {sum(1 for _ in open(csv_path))-1})")
        except Exception as exc:
            print(f"[step 0] FAILED: {exc}")
            return 1

    if not spec_path.exists():
        print(f"[FATAL] proxy_spec.json not found at {spec_path}")
        return 1
    if not csv_path.exists():
        print(f"[FATAL] real.csv not found at {csv_path}")
        return 1

    # ---------------------------------------------------------------------- #
    # 2. Validate proxy spec (canonical gate)
    # ---------------------------------------------------------------------- #
    print("[step 1] Validating proxy spec (canonical gate)...")
    canonical_spec_result = _run(
        [py, str(repo_root / config.validate_script),
         "--spec", str(spec_path), "--csv", str(csv_path)],
        cwd=repo_root, label="validate_proxy_spec",
    )

    # ---------------------------------------------------------------------- #
    # 3. Mapping validity gate (sector-specific extended check)
    # ---------------------------------------------------------------------- #
    print("[step 2] Running extended mapping validity check...")
    mapping_dir = out_root / "pilot_data"
    mapping_dir.mkdir(parents=True, exist_ok=True)
    mv_out = mapping_dir / "mapping_validity.json"

    from mapping_validator import validate_mapping
    mv_result = validate_mapping(spec_path, csv_path)
    mv_result["canonical_validate_ok"] = canonical_spec_result["ok"]
    with open(mv_out, "w") as f:
        json.dump(mv_result, f, indent=2, default=str)

    mapping_verdict = mv_result["verdict"]
    print(f"         → mapping_validity_verdict: {mapping_verdict}")
    if mv_result["hard_errors"]:
        for e in mv_result["hard_errors"]:
            print(f"           ✗ {e}")
    if mv_result["soft_warnings"]:
        for w in mv_result["soft_warnings"][:3]:
            print(f"           ! {w}")

    if mapping_verdict == "REJECT":
        print("[FATAL] Mapping validity REJECT — halting sector run")
        _write_global_verdict(out_root, pilot_id, config.sector_id,
                              "REJECT", mapping_verdict, {}, {})
        return 1

    # ---------------------------------------------------------------------- #
    # 4. Real-data pipeline run
    # ---------------------------------------------------------------------- #
    print("[step 3] Running ORI-C real-data pipeline...")
    real_out = out_root / "real"
    real_out.mkdir(parents=True, exist_ok=True)

    pipeline_r = _run(
        [py, str(repo_root / config.run_real_script),
         "--input",        str(csv_path),
         "--outdir",       str(real_out),
         "--time-mode",    "index",
         "--normalize",    config.default_normalize,
         "--control-mode", "no_symbolic",
         "--seed",         str(seed)],
        cwd=repo_root, label="run_real_data_demo",
    )
    real_pipeline_verdict = _read_verdict(real_out) if pipeline_r["ok"] else "INDETERMINATE"

    # ---------------------------------------------------------------------- #
    # 5. Causal tests
    # ---------------------------------------------------------------------- #
    print("[step 4] Running causal tests...")
    causal_r = _run(
        [py, str(repo_root / config.causal_script),
         "--run-dir",      str(real_out),
         "--alpha",        config.default_alpha,
         "--lags",         config.default_lags,
         "--pre-horizon",  "100",
         "--post-horizon", "100",
         "--seed",         str(seed)],
        cwd=repo_root, label="tests_causaux",
    )
    causal_verdict = _read_verdict(real_out) if causal_r["ok"] else "INDETERMINATE"

    # ---------------------------------------------------------------------- #
    # 6. Robustness variants
    # ---------------------------------------------------------------------- #
    print("[step 5] Running robustness variants...")
    robust_dir = out_root / "robustness"
    robust_dir.mkdir(parents=True, exist_ok=True)
    robust_verdicts: dict[str, str] = {}

    for variant in config.robustness_variants:
        vname  = variant["name"]
        var_out = robust_dir / f"variant_{vname}"
        var_out.mkdir(parents=True, exist_ok=True)

        # Re-run pipeline with variant parameters
        p_r = _run(
            [py, str(repo_root / config.run_real_script),
             "--input",        str(csv_path),
             "--outdir",       str(var_out),
             "--time-mode",    "index",
             "--normalize",    variant.get("normalize", config.default_normalize),
             "--control-mode", "no_symbolic",
             "--seed",         str(seed)],
            cwd=repo_root, label=f"robustness/{vname}",
        )
        if not p_r["ok"]:
            robust_verdicts[vname] = "INDETERMINATE"
            continue

        # Causal tests on variant
        c_r = _run(
            [py, str(repo_root / config.causal_script),
             "--run-dir",      str(var_out),
             "--alpha",        config.default_alpha,
             "--lags",         config.default_lags,
             "--pre-horizon",  str(variant.get("pre_horizon", 100)),
             "--post-horizon", str(variant.get("post_horizon", 100)),
             "--seed",         str(seed)],
            cwd=repo_root, label=f"causal/{vname}",
        )
        robust_verdicts[vname] = _read_verdict(var_out) if c_r["ok"] else "INDETERMINATE"
        print(f"         {vname}: {robust_verdicts[vname]}")

    # Robustness summary
    n_accept = sum(1 for v in robust_verdicts.values() if v == "ACCEPT")
    n_total  = len(robust_verdicts)
    robust_fraction = n_accept / n_total if n_total > 0 else float("nan")
    robust_summary  = {
        "n_variants":       n_total,
        "n_accept":         n_accept,
        "n_indeterminate":  sum(1 for v in robust_verdicts.values() if v == "INDETERMINATE"),
        "n_reject":         sum(1 for v in robust_verdicts.values() if v == "REJECT"),
        "accept_fraction":  round(robust_fraction, 3),
        "robust_note":      (
            "robust" if robust_fraction >= 0.75
            else ("borderline_robust" if robust_fraction >= 0.5 else "not_robust")
        ),
        "verdicts":         robust_verdicts,
    }

    # ---------------------------------------------------------------------- #
    # 7. Global verdict aggregation
    # ---------------------------------------------------------------------- #
    primary_verdicts = [causal_verdict]
    global_verdict   = _aggregate_verdicts(primary_verdicts)
    support          = _support_level(global_verdict, mapping_verdict)

    print(f"\n[SECTOR PANEL SUMMARY]")
    print(f"  mapping_validity  : {mapping_verdict}")
    print(f"  primary pipeline  : {causal_verdict}")
    print(f"  robustness        : {robust_fraction:.0%} ACCEPT ({n_accept}/{n_total})")
    print(f"  global_verdict    : {global_verdict}")
    print(f"  support_level     : {support}")

    _write_global_verdict(
        out_root, pilot_id, config.sector_id,
        global_verdict, mapping_verdict, robust_summary,
        {"pipeline": causal_verdict, "mapping": mapping_verdict},
    )

    return 0 if global_verdict != "REJECT" else 1


def _write_global_verdict(
    out_root: Path,
    pilot_id: str,
    sector_id: str,
    global_verdict: str,
    mapping_verdict: str,
    robust_summary: dict,
    sub_verdicts: dict,
) -> None:
    """Write sector_global_verdict.json to out_root."""
    data = {
        "sector_id":          sector_id,
        "pilot_id":           pilot_id,
        "global_verdict":     global_verdict,
        "mapping_validity":   mapping_verdict,
        "support_level":      _support_level(global_verdict, mapping_verdict),
        "sub_verdicts":       sub_verdicts,
        "robustness_summary": robust_summary,
        "forbidden_labels": (
            ["sector_panel_support"] if mapping_verdict == "REJECT" else []
        ),
        "run_mode":       "sector_panel",
        "protocol_note":  (
            "Sector panel verdict is distinct from the canonical T1-T8 synthetic suite. "
            "sector_panel_support requires both primary causal tests ACCEPT and "
            "mapping_validity ACCEPT. Indeterminate is informative, not a failure."
        ),
    }
    out_file = out_root / "sector_global_verdict.json"
    out_root.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  → sector_global_verdict.json written: {out_file}")


# --------------------------------------------------------------------------- #
# Shared argument parser
# --------------------------------------------------------------------------- #

def make_parser(sector_id: str, default_pilot: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"ORI-C {sector_id.upper()} sector panel suite runner"
    )
    parser.add_argument("--pilot-id",    default=default_pilot,
                        help=f"Pilot dataset id (default: {default_pilot})")
    parser.add_argument("--real-csv",    default=None,
                        help="Path to real data CSV (omit to use synthetic)")
    parser.add_argument("--outdir",      required=True,
                        help="Output directory for this sector run")
    parser.add_argument("--seed",        type=int, default=1234,
                        help="Random seed (default: 1234)")
    parser.add_argument("--n-runs",      type=int, default=50,
                        help="Number of simulation runs for statistical tests")
    parser.add_argument("--mode",        choices=["smoke_ci", "full_statistical"],
                        default="smoke_ci",
                        help="Run mode: smoke_ci (fast CI check) or full_statistical")
    return parser
