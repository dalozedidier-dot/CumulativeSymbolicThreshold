#!/usr/bin/env python3
"""regen_evidence.py — re-run the evidence surface and detect drift.

Why this exists
---------------
`04_Code/tests/test_stored_artifacts_match_contracts.py` is a *static* gate: it
proves a committed artifact still matches its own manifest and contract. It
cannot prove the artifact still matches what the code *produces* — so when a
runner changes, the stored artifact silently stops describing the current
system. That is not hypothetical: two artifacts had drifted that way. The rung-3
demonstration still claimed `power>=gate` was part of its PASS rule after the
runner stopped imposing it, and the Test A control was a pre-localized-gate run
reporting `accumulation_fpr = 1.0 / DOES_NOT_SEPARATE` while the README claimed
`0.0`. Both were caught by hand, which does not scale.

This closes the loop: every evidence run is replayed under its frozen parameters
and compared field by field against the committed artifact. Every run here is
seeded and deterministic, so any difference is real drift — a code change that
moved a number, or a stale artifact.

Usage
-----
    python -m tools.regen_evidence --check            # replay all, diff, exit 1 on drift
    python -m tools.regen_evidence --check --only rung3
    python -m tools.regen_evidence --write --only testA   # accept a deliberate change
    python -m tools.regen_evidence --list

`--write` refreshes the committed artifact from the replay. Use it only when the
change is intended, and say why in the commit message: these files are the
evidence behind the rungs claimed in docs/EVIDENCE_LADDER.md.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class EvidenceRun:
    """One replayable evidence artifact.

    ``args`` are the frozen parameters. They are duplicated from the artifact's
    own manifest on purpose: if a runner's *default* changes, the replay must
    still use the parameters the stored artifact was produced under, otherwise
    the comparison silently comes to be about two different runs.
    """

    run_id: str
    rung: str
    artifact_dir: str
    script: str
    args: tuple[str, ...]
    tables: tuple[str, ...]
    side_files: tuple[str, ...] = field(default=("manifest.json", "verdict.txt"))


EVIDENCE_RUNS: tuple[EvidenceRun, ...] = (
    EvidenceRun(
        run_id="rung3",
        rung="3 — synthetic full-statistical demonstration",
        artifact_dir="05_Results/endogenous_full_statistical",
        script="04_Code/pipeline/run_endogenous_full_statistical.py",
        args=("--n-replicates", "50", "--n-surrogates", "199",
              "--n-steps", "1500", "--seed-base", "7000"),
        tables=("tables/full_statistical.json",),
    ),
    EvidenceRun(
        run_id="testA",
        rung="6 — Test A, accumulation control (localized gate)",
        artifact_dir="05_Results/falsification/accumulation_control",
        script="04_Code/pipeline/run_accumulation_control.py",
        args=("--seed", "1234", "--n", "220", "--n-surrogates", "200"),
        tables=("tables/accumulation_control.json",),
    ),
    EvidenceRun(
        run_id="testB",
        rung="6 — Test B, surrogate null (Pantheon SN)",
        artifact_dir="05_Results/surrogate_null/pantheon_sn",
        script="04_Code/pipeline/run_surrogate_null.py",
        args=("--input", "03_Data/sector_cosmo/real/pilot_pantheon_sn/real_densified.csv",
              "--n-surrogates", "500", "--seed", "1234", "--statistic", "crossing_rate"),
        tables=("tables/surrogate_null.json",),
    ),
    EvidenceRun(
        run_id="confirmatory-pantheon",
        rung="6 — joint confirmatory (Pantheon SN)",
        artifact_dir="05_Results/confirmatory/pantheon_sn",
        script="04_Code/pipeline/run_confirmatory_suite.py",
        args=("--input", "03_Data/sector_cosmo/real/pilot_pantheon_sn/real_densified.csv",
              "--seed", "1234", "--n-surrogates", "500"),
        tables=("tables/confirmatory.json",),
    ),
    EvidenceRun(
        run_id="confirmatory-fred",
        rung="6 — joint confirmatory (FRED monthly)",
        artifact_dir="05_Results/confirmatory/fred_monthly",
        script="04_Code/pipeline/run_confirmatory_suite.py",
        args=("--input", "03_Data/real/fred_monthly/real.csv",
              "--seed", "1234", "--n-surrogates", "500"),
        tables=("tables/confirmatory.json",),
    ),
    EvidenceRun(
        run_id="registered-block",
        rung="5–6 — registered real-data A/B/C block",
        artifact_dir="05_Results/registered_block",
        script="04_Code/pipeline/run_registered_block.py",
        args=("--contract", "contracts/REAL_DATA_REGISTRATION.json"),
        tables=("tables/registered_block.json",),
    ),
    EvidenceRun(
        run_id="rung7",
        rung="7 — strong-negatives battery",
        artifact_dir="05_Results/strong_negatives",
        script="04_Code/pipeline/run_strong_negatives.py",
        args=("--seed", "1234", "--n", "220", "--n-surrogates", "0"),
        tables=("tables/strong_negatives.json",),
    ),
    EvidenceRun(
        run_id="rung8",
        rung="8 — pre-registered OOS prediction (lead=60)",
        artifact_dir="05_Results/oos_prediction",
        script="04_Code/pipeline/run_oos_prediction.py",
        args=("--n-replicates", "50", "--n-surrogates", "99", "--n-steps", "1500",
              "--noise-sd", "0.05", "--lead", "60", "--alpha", "0.05",
              "--seed-base", "7000"),
        # NOTE: exploratory_lead40_prefreeze/ lives under the same directory and is
        # a different, pre-freeze run. It is part of the audit trail and is never
        # touched here — only the top-level table is replayed.
        tables=("tables/oos_prediction.json",),
    ),
)


def _flatten(obj, prefix: str = "") -> dict:
    """Flatten nested JSON to dotted paths so a diff points at the field."""
    out: dict = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}{k}."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}[{i}]."))
    else:
        out[prefix.rstrip(".")] = obj
    return out


def _diff_json(committed: Path, replayed: Path) -> list[str]:
    old = _flatten(json.loads(committed.read_text(encoding="utf-8")))
    new = _flatten(json.loads(replayed.read_text(encoding="utf-8")))
    lines = []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key, "<absent>"), new.get(key, "<absent>")
        if a != b:
            lines.append(f"      {key}\n        committed: {a!s:.200}\n        replayed : {b!s:.200}")
    return lines


def _replay(run: EvidenceRun, outdir: Path) -> None:
    cmd = [sys.executable, str(REPO / run.script), "--outdir", str(outdir), *run.args]
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(REPO / "src")}
    proc = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"[{run.run_id}] runner failed (exit {proc.returncode})\n"
            f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
        )


def check(runs: list[EvidenceRun]) -> int:
    drifted: list[str] = []
    for run in runs:
        print(f"[replay] {run.run_id:24} rung {run.rung}", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "out"
            _replay(run, outdir)
            for table in run.tables:
                committed = REPO / run.artifact_dir / table
                replayed = outdir / table
                if not committed.exists():
                    drifted.append(f"  {run.run_id}: committed artifact missing ({table})")
                    continue
                if not replayed.exists():
                    drifted.append(f"  {run.run_id}: replay produced no {table}")
                    continue
                lines = _diff_json(committed, replayed)
                if lines:
                    drifted.append(f"  {run.run_id} — {table} drifted:\n" + "\n".join(lines))
                else:
                    print(f"           {table}: identical")

    print()
    if drifted:
        print("DRIFT DETECTED — the committed evidence no longer matches what the code produces:\n")
        print("\n".join(drifted))
        print(
            "\nEvery run here is seeded, so this is a real change, not noise.\n"
            "If it is intended, refresh with --write --only <id> and justify it in\n"
            "the commit message; the stored artifacts back the rungs claimed in\n"
            "docs/EVIDENCE_LADDER.md."
        )
        return 1
    print(f"OK: {len(runs)} evidence run(s) reproduce their committed artifacts exactly.")
    return 0


def write(runs: list[EvidenceRun]) -> int:
    for run in runs:
        print(f"[refresh] {run.run_id}", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "out"
            _replay(run, outdir)
            target = REPO / run.artifact_dir
            for rel in (*run.tables, *run.side_files):
                src = outdir / rel
                if not src.exists():
                    continue
                dst = target / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"          wrote {run.artifact_dir}/{rel}")
    print("\nRefreshed. Re-run the anti-drift tests before committing:")
    print("  pytest 04_Code/tests/test_stored_artifacts_match_contracts.py")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="replay and diff (exit 1 on drift)")
    mode.add_argument("--write", action="store_true", help="replay and overwrite the artifacts")
    mode.add_argument("--list", action="store_true", help="list the evidence runs")
    ap.add_argument("--only", action="append", default=[], metavar="RUN_ID",
                    help="restrict to these run ids (repeatable)")
    args = ap.parse_args()

    if args.list:
        for run in EVIDENCE_RUNS:
            print(f"{run.run_id:24} {run.rung}\n{'':24} {run.artifact_dir}")
        return 0

    runs = list(EVIDENCE_RUNS)
    if args.only:
        known = {r.run_id for r in EVIDENCE_RUNS}
        unknown = sorted(set(args.only) - known)
        if unknown:
            raise SystemExit(f"unknown run id(s): {', '.join(unknown)}; known: {', '.join(sorted(known))}")
        runs = [r for r in runs if r.run_id in set(args.only)]

    return write(runs) if args.write else check(runs)


if __name__ == "__main__":
    raise SystemExit(main())
