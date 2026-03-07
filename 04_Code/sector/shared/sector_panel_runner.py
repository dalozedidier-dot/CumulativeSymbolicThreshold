"""sector_panel_runner.py — Shared sector panel execution engine.

Called by each sector's run_sector_suite.py.  Provides a single
run_sector_panel(config, args) function that:

  1. Validates the proxy spec (canonical gate)  → validate_proxy_spec.py
  2. Runs extended mapping validity check        → mapping_validator.validate_mapping()
  3. Runs real-data ORI-C pipeline              → run_real_data_demo.py
  4. Runs causal tests                           → tests_causaux.py
  5. Runs robustness variants                    → window/normalize/resample sweeps
  6. Aggregates all verdicts                     → sector_global_verdict.json

Mode semantics
--------------
  smoke_ci        : REJECT at any step is logged but non-blocking.
                    The CI job exits 0 if artifacts are produced.
                    ci_smoke_non_blocking = true in the verdict JSON.
  full_statistical: REJECT at mapping_validity or global level → exit 1.

Output directory layout
-----------------------
  <outdir>/
    pilot_<pilot_id>/
      _logs/                     # full stdout/stderr for every subprocess
        validate_proxy_spec.log
        run_real_data_demo.log
        tests_causaux.log
        robustness_<variant>.log
      pilot_data/
        mapping_validity.json
      real/                      # ORI-C pipeline output
        tables/
        figures/
        verdict.json
      robustness/
        variant_<name>/
          verdict.json
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
    {"name": "window_long",   "pre_horizon": 150, "post_horizon": 150, "normalize": "robust_minmax"},
    {"name": "norm_minmax",   "pre_horizon": 100, "post_horizon": 100, "normalize": "minmax"},
    {"name": "resample_80",   "pre_horizon": 100, "post_horizon": 100, "normalize": "robust_minmax", "resample_frac": 0.80},
    {"name": "resample_60",   "pre_horizon": 100, "post_horizon": 100, "normalize": "robust_minmax", "resample_frac": 0.60},
])


# --------------------------------------------------------------------------- #
# Subprocess helper — full logging
# --------------------------------------------------------------------------- #

def _run(
    cmd: list[str],
    cwd: Path,
    label: str,
    log_dir: Path | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    """Run subprocess; capture full stdout/stderr; write log file.

    Always prints:
      - the exact command being run
      - full stdout + stderr on failure (not just last N chars)

    If log_dir is given, writes <label>.log with cmd, rc, stdout, stderr.
    Returns {"ok", "returncode", "stdout", "stderr", "elapsed", "log_file"}.
    """
    cmd_str = " ".join(str(c) for c in cmd)
    print(f"  [{label}] cmd: {cmd_str}")
    t0 = time.monotonic()
    log_file: Path | None = None
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(cwd), timeout=timeout,
        )
        elapsed = time.monotonic() - t0
        ok = r.returncode == 0

        # Write full log file
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            safe_label = label.replace("/", "_").replace(" ", "_")
            log_file = log_dir / f"{safe_label}.log"
            with open(log_file, "w", encoding="utf-8") as lf:
                lf.write(f"CMD:     {cmd_str}\n")
                lf.write(f"CWD:     {cwd}\n")
                lf.write(f"RC:      {r.returncode}\n")
                lf.write(f"ELAPSED: {elapsed:.1f}s\n\n")
                lf.write("=== STDOUT ===\n")
                lf.write(r.stdout or "(empty)\n")
                lf.write("\n=== STDERR ===\n")
                lf.write(r.stderr or "(empty)\n")

        if not ok:
            print(f"  [{label}] FAILED (rc={r.returncode}, {elapsed:.1f}s)")
            if r.stdout:
                print(f"  --- stdout ---\n{r.stdout}")
            if r.stderr:
                print(f"  --- stderr ---\n{r.stderr}")
            if log_file:
                print(f"  --- log written to: {log_file}")
        else:
            print(f"  [{label}] OK ({elapsed:.1f}s)")

        return {
            "ok": ok, "returncode": r.returncode,
            "stdout": r.stdout, "stderr": r.stderr,
            "elapsed": elapsed, "log_file": str(log_file) if log_file else None,
        }
    except subprocess.TimeoutExpired:
        print(f"  [{label}] TIMEOUT after {timeout}s")
        return {
            "ok": False, "returncode": -1,
            "stdout": "", "stderr": f"TIMEOUT after {timeout}s",
            "elapsed": float(timeout), "log_file": None,
        }
    except Exception as exc:
        print(f"  [{label}] ERROR: {exc}")
        return {
            "ok": False, "returncode": -1,
            "stdout": "", "stderr": str(exc),
            "elapsed": 0.0, "log_file": None,
        }


# --------------------------------------------------------------------------- #
# Verdict helpers
# --------------------------------------------------------------------------- #

def _read_verdict(path: Path) -> str:
    """Read verdict from verdict.txt or tables/verdict.json → canonical token."""
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




def _sync_summary_verdict(run_dir: Path) -> None:
    """Align tables/summary.json['verdict'] on tables/verdict.json['verdict'] when both exist.

    This is contract-preserving: verdict.json is the causal source of truth after tests_causaux.py.
    """
    s_path = run_dir / "tables" / "summary.json"
    v_path = run_dir / "tables" / "verdict.json"
    if not s_path.exists() or not v_path.exists():
        return
    try:
        s = json.loads(s_path.read_text(encoding="utf-8"))
        v = json.loads(v_path.read_text(encoding="utf-8"))
    except Exception:
        return

    verdict_value = v.get("verdict", v.get("label", v.get("global")))
    if verdict_value is None:
        return

    s["verdict"] = verdict_value
    if "precheck_passed" in v:
        s["precheck_passed"] = v.get("precheck_passed")
    if "precheck_reason" in v:
        s["precheck_reason"] = v.get("precheck_reason")

    s_path.write_text(json.dumps(s, indent=2), encoding="utf-8")

def _aggregate_verdicts(verdicts: list[str]) -> str:
    """ACCEPT only if all ACCEPT; REJECT if any REJECT; else INDETERMINATE."""
    if any(v == "REJECT" for v in verdicts):
        return "REJECT"
    if all(v == "ACCEPT" for v in verdicts):
        return "ACCEPT"
    return "INDETERMINATE"


def _support_level(verdict: str, mapping_verdict: str, smoke_ci: bool) -> str:
    if smoke_ci:
        return f"smoke_ci_{verdict.lower()}"
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
        (used only when --real-csv is not provided)

    Returns:
      smoke_ci mode        → always 0 if artifacts produced (REJECT is informational)
      full_statistical mode → 0 (ACCEPT/INDETERMINATE) | 1 (REJECT)
    """
    pilot_id = args.pilot_id
    out_root = Path(args.outdir) / f"pilot_{pilot_id}"
    seed     = args.seed
    py       = sys.executable

    # Mode: smoke_ci is non-blocking; full_statistical is strict
    mode     = getattr(args, "mode", "smoke_ci")
    smoke_ci = (mode == "smoke_ci")

    # Log directory: every subprocess writes here
    log_dir = out_root / "_logs"

    print(f"\n{'='*60}")
    print(f"  SECTOR PANEL: {config.sector_id.upper()} / {pilot_id}")
    print(f"  mode   : {mode}  (smoke_ci={smoke_ci})")
    print(f"  outdir : {out_root}")
    print(f"{'='*60}\n")

    # ---------------------------------------------------------------------- #
    # 1. Resolve data paths
    # ---------------------------------------------------------------------- #
    data_dir  = repo_root / config.data_root / "real" / f"pilot_{pilot_id}"
    spec_path = data_dir / "proxy_spec.json"

    synth_dir = out_root / "synth_data"
    synth_dir.mkdir(parents=True, exist_ok=True)

    if args.real_csv:
        csv_path = Path(args.real_csv)
        print(f"[step 0] Using provided real CSV: {csv_path}")
    else:
        real_csv = data_dir / "real.csv"
        if real_csv.exists():
            csv_path = real_csv
            print(f"[step 0] Using real pilot CSV from repo: {csv_path}")
            # Snapshot inputs into synth_data/ for auditability and CI artifacts
            try:
                (synth_dir / "real.csv").write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] Could not snapshot real.csv into synth_data: {exc}")
            if spec_path.exists():
                try:
                    (synth_dir / "proxy_spec.json").write_text(spec_path.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception as exc:  # noqa: BLE001
                    print(f"[WARN] Could not snapshot proxy_spec.json into synth_data: {exc}")
        else:
            print("[step 0] No --real-csv provided and no repo real.csv found — generating synthetic pilot data...")
            try:
                synth_generator(synth_dir, seed, pilot_id)
                csv_path = synth_dir / "real.csv"
                synth_spec = synth_dir / "proxy_spec.json"
                if synth_spec.exists():
                    spec_path = synth_spec
                elif not spec_path.exists():
                    print("[FATAL] No proxy_spec.json found (synth dir or real data dir)")
                    return 1
                try:
                    n_rows = sum(1 for _ in open(csv_path, "r", encoding="utf-8", errors="ignore")) - 1
                except Exception:
                    n_rows = "?"
                print(f"         → {csv_path}  ({n_rows} rows)")
            except Exception as exc:
                print(f"[step 0] Synth generator FAILED: {exc}")
                return 1

    if not spec_path.exists():
        print(f"[FATAL] proxy_spec.json not found: {spec_path}")
        return 1
    if not csv_path.exists():
        print(f"[FATAL] real.csv not found: {csv_path}")
        return 1

    print(f"         proxy_spec : {spec_path}")
    print(f"         csv        : {csv_path}")

    # ---------------------------------------------------------------------- #
    # 2. Validate proxy spec (canonical gate)
    # ---------------------------------------------------------------------- #
    print("\n[step 1] Validating proxy spec (canonical gate)...")
    print(f"         script: {config.validate_script}")
    print(f"         --spec {spec_path}")
    print(f"         --csv  {csv_path}")

    canonical_spec_result = _run(
        [py, str(repo_root / config.validate_script),
         "--spec", str(spec_path), "--csv", str(csv_path)],
        cwd=repo_root, label="validate_proxy_spec", log_dir=log_dir,
    )

    if not canonical_spec_result["ok"]:
        print(f"  [validate_proxy_spec] rc={canonical_spec_result['returncode']}")
        print(f"  STDOUT: {canonical_spec_result['stdout'] or '(empty)'}")
        print(f"  STDERR: {canonical_spec_result['stderr'] or '(empty)'}")

    # ---------------------------------------------------------------------- #
    # 3. Mapping validity gate (extended check)
    # ---------------------------------------------------------------------- #
    print("\n[step 2] Running extended mapping validity check...")
    mapping_dir = out_root / "pilot_data"
    mapping_dir.mkdir(parents=True, exist_ok=True)
    mv_out = mapping_dir / "mapping_validity.json"

    from mapping_validator import validate_mapping  # noqa: PLC0415
    mv_result = validate_mapping(spec_path, csv_path)
    mv_result["canonical_validate_ok"] = canonical_spec_result["ok"]
    mv_result["canonical_validate_stdout"] = canonical_spec_result["stdout"]
    mv_result["canonical_validate_stderr"] = canonical_spec_result["stderr"]
    with open(mv_out, "w") as f:
        json.dump(mv_result, f, indent=2, default=str)

    mapping_verdict = mv_result["verdict"]
    print(f"         → mapping_validity_verdict: {mapping_verdict}")
    print(f"         → mapping_validity.json:    {mv_out}")

    if mv_result.get("hard_errors"):
        for e in mv_result["hard_errors"]:
            print(f"           ✗ {e}")
    if mv_result.get("soft_warnings"):
        for w in mv_result["soft_warnings"][:5]:
            print(f"           ! {w}")

    if mapping_verdict == "REJECT":
        if smoke_ci:
            print("[WARN]  mapping_validity REJECT — non-blocking in smoke_ci mode")
            print("[WARN]  CI job will still exit 0 (verdict recorded in JSON)")
        else:
            print("[FATAL] mapping_validity REJECT — halting (full_statistical mode)")
            _write_global_verdict(
                out_root, pilot_id, config.sector_id,
                "REJECT", mapping_verdict, {}, {}, smoke_ci=False,
            )
            return 1

    # ---------------------------------------------------------------------- #
    # 4. Real-data pipeline run
    # ---------------------------------------------------------------------- #
    print("\n[step 3] Running ORI-C real-data pipeline...")
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
        cwd=repo_root, label="run_real_data_demo", log_dir=log_dir,
    )
    real_pipeline_verdict = _read_verdict(real_out) if pipeline_r["ok"] else "INDETERMINATE"

    # ---------------------------------------------------------------------- #
    # 5. Causal tests
    # ---------------------------------------------------------------------- #
    print("\n[step 4] Running causal tests...")
    causal_r = _run(
        [py, str(repo_root / config.causal_script),
         "--run-dir",      str(real_out),
         "--alpha",        config.default_alpha,
         "--lags",         config.default_lags,
         "--pre-horizon",  "100",
         "--post-horizon", "100",
         "--seed",         str(seed)],
        cwd=repo_root, label="tests_causaux", log_dir=log_dir,
    )
    causal_verdict = _read_verdict(real_out) if causal_r["ok"] else "INDETERMINATE"
    _sync_summary_verdict(real_out)

    # ---------------------------------------------------------------------- #
    # 6. Robustness variants
    # ---------------------------------------------------------------------- #
    print("\n[step 5] Running robustness variants...")
    robust_dir = out_root / "robustness"
    robust_dir.mkdir(parents=True, exist_ok=True)
    robust_verdicts: dict[str, str] = {}

    for variant in config.robustness_variants:
        vname   = variant["name"]
        var_out = robust_dir / f"variant_{vname}"
        var_out.mkdir(parents=True, exist_ok=True)

        p_r = _run(
            [py, str(repo_root / config.run_real_script),
             "--input",        str(csv_path),
             "--outdir",       str(var_out),
             "--time-mode",    "index",
             "--normalize",    variant.get("normalize", config.default_normalize),
             "--control-mode", "no_symbolic",
             "--seed",         str(seed)],
            cwd=repo_root, label=f"robustness_{vname}", log_dir=log_dir,
        )
        if not p_r["ok"]:
            robust_verdicts[vname] = "INDETERMINATE"
            continue

        c_r = _run(
            [py, str(repo_root / config.causal_script),
             "--run-dir",      str(var_out),
             "--alpha",        config.default_alpha,
             "--lags",         config.default_lags,
             "--pre-horizon",  str(variant.get("pre_horizon", 100)),
             "--post-horizon", str(variant.get("post_horizon", 100)),
             "--seed",         str(seed)],
            cwd=repo_root, label=f"causal_{vname}", log_dir=log_dir,
        )
        robust_verdicts[vname] = _read_verdict(var_out) if c_r["ok"] else "INDETERMINATE"
        _sync_summary_verdict(var_out)
        print(f"         {vname}: {robust_verdicts[vname]}")

    n_accept  = sum(1 for v in robust_verdicts.values() if v == "ACCEPT")
    n_total   = len(robust_verdicts)
    robust_fraction = n_accept / n_total if n_total > 0 else float("nan")
    robust_summary  = {
        "n_variants":      n_total,
        "n_accept":        n_accept,
        "n_indeterminate": sum(1 for v in robust_verdicts.values() if v == "INDETERMINATE"),
        "n_reject":        sum(1 for v in robust_verdicts.values() if v == "REJECT"),
        "accept_fraction": round(robust_fraction, 3),
        "robust_note": (
            "robust"            if robust_fraction >= 0.75 else
            "borderline_robust" if robust_fraction >= 0.50 else
            "not_robust"
        ),
        "verdicts": robust_verdicts,
    }

    # ---------------------------------------------------------------------- #
    # 7. Global verdict aggregation
    # ---------------------------------------------------------------------- #
    primary_verdicts = [causal_verdict]
    global_verdict   = _aggregate_verdicts(primary_verdicts)
    support          = _support_level(global_verdict, mapping_verdict, smoke_ci)

    print(f"\n{'='*60}")
    print(f"  SECTOR PANEL SUMMARY  ({config.sector_id.upper()} / {pilot_id})")
    print(f"  mode              : {mode}")
    print(f"  mapping_validity  : {mapping_verdict}")
    print(f"  primary pipeline  : {causal_verdict}")
    f_str = f"{robust_fraction:.0%}" if n_total > 0 else "n/a"
    print(f"  robustness        : {f_str} ACCEPT ({n_accept}/{n_total})")
    print(f"  global_verdict    : {global_verdict}")
    print(f"  support_level     : {support}")
    if smoke_ci:
        print(f"  ci_smoke_non_blocking: True — exit code 0 regardless of verdict")
    print(f"{'='*60}")

    _write_global_verdict(
        out_root, pilot_id, config.sector_id,
        global_verdict, mapping_verdict, robust_summary,
        {"pipeline": causal_verdict, "mapping": mapping_verdict},
        smoke_ci=smoke_ci,
    )

    # Exit code: smoke_ci always 0 (verdict informational); full_statistical strict
    if smoke_ci:
        return 0
    return 0 if global_verdict != "REJECT" else 1


def _write_global_verdict(
    out_root: Path,
    pilot_id: str,
    sector_id: str,
    global_verdict: str,
    mapping_verdict: str,
    robust_summary: dict,
    sub_verdicts: dict,
    smoke_ci: bool = False,
) -> None:
    """Write sector_global_verdict.json to out_root."""
    data = {
        "sector_id":           sector_id,
        "pilot_id":            pilot_id,
        "global_verdict":      global_verdict,
        "mapping_validity":    mapping_verdict,
        "support_level":       _support_level(global_verdict, mapping_verdict, smoke_ci),
        "run_mode":            "smoke_ci" if smoke_ci else "full_statistical",
        "ci_smoke_non_blocking": smoke_ci,
        "sub_verdicts":        sub_verdicts,
        "robustness_summary":  robust_summary,
        "forbidden_labels": (
            ["sector_panel_support"] if mapping_verdict == "REJECT" else []
        ),
        "protocol_note": (
            "smoke_ci: verdict is informational; CI exits 0 regardless of REJECT. "
            "Use full_statistical for auditable results."
            if smoke_ci else
            "full_statistical: sector_panel_support requires mapping_validity ACCEPT "
            "and primary causal tests ACCEPT."
        ),
    }
    out_file = out_root / "sector_global_verdict.json"
    out_root.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  → sector_global_verdict.json: {out_file}")


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
                        help="Path to real data CSV (omit to use synthetic fallback)")
    parser.add_argument("--outdir",      required=True,
                        help="Output directory for this sector run")
    parser.add_argument("--seed",        type=int, default=1234,
                        help="Random seed (default: 1234)")
    parser.add_argument("--n-runs",      type=int, default=50,
                        help="Number of simulation runs for statistical tests")
    parser.add_argument("--mode",        choices=["smoke_ci", "full_statistical"],
                        default="smoke_ci",
                        help="smoke_ci: REJECT non-blocking (CI exits 0); "
                             "full_statistical: REJECT → exit 1")
    parser.add_argument("--fail-on-reject", action="store_true", default=False,
                        help="Force exit 1 on REJECT even in smoke_ci mode "
                             "(default: False)")
    return parser
