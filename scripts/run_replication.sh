#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_replication.sh — one-command external replication driver for ORI-C.
#
# Designed to run identically on a host (`bash scripts/run_replication.sh`) or
# inside the reproducible container:
#
#   docker build -t oric:latest .
#   docker run --rm -v "$(pwd)/replication_output:/app/replication_output" \
#     oric:latest bash scripts/run_replication.sh
#
# It is FAST by design (smoke-tier proofs) so a third party gets a verdict in
# minutes. The honest headline outcome is NOT_CONFIRMED on real data — see
# docs/EVIDENCE_LADDER.md. Full (non-fast) commands are printed at the end.
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail

OUTDIR="${1:-replication_output}"
SEED="${ORIC_SEED:-1234}"
export PYTHONPATH="src:04_Code:${PYTHONPATH:-}"
mkdir -p "$OUTDIR"

say() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
PASS=0; FAIL=0
step() { # step "label" cmd...
  local label="$1"; shift
  printf '  → %s\n' "$label"
  if "$@" > "$OUTDIR/$(echo "$label" | tr ' /' '__').log" 2>&1; then
    printf '    \033[32m[OK]\033[0m %s\n' "$label"; PASS=$((PASS+1)); return 0
  else
    printf '    \033[31m[FAIL]\033[0m %s (see %s log)\n' "$label" "$label"; FAIL=$((FAIL+1)); return 1
  fi
}

say "Environment"
python --version
python - <<'PY'
import importlib.metadata as m
for p in ("numpy","pandas","scipy","statsmodels","scikit-learn","matplotlib"):
    try: print(f"  {p}=={m.version(p)}")
    except m.PackageNotFoundError: print(f"  {p}: MISSING")
PY

say "1. Frozen-contract + repo health check"
step "repo_doctor" python -m tools.repo_doctor

say "2. Canonical synthetic suite (smoke_ci — fast, non-conclusive by design)"
step "canonical_smoke" python 04_Code/pipeline/run_all_tests.py --outdir "$OUTDIR/canonical" --fast --seed "$SEED"

say "3. Strong-negatives specificity battery (rung 7)"
step "strong_negatives" python 04_Code/pipeline/run_strong_negatives.py --outdir "$OUTDIR/strong_negatives" --fast --seed "$SEED"

say "4. Decisive trend-vs-transition accumulation control"
step "accumulation_control" python 04_Code/pipeline/run_accumulation_control.py --outdir "$OUTDIR/accumulation_control" --fast --seed "$SEED"

say "Replication summary"
python - "$OUTDIR" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1])

def read_json(p):
    try: return json.loads(Path(p).read_text())
    except Exception: return {}

sn = read_json(out / "strong_negatives" / "tables" / "strong_negatives.json")
ac = read_json(out / "accumulation_control" / "tables" / "accumulation_control.json")

summary = {
    "schema": "oric.replication_summary.v1",
    "note": "Smoke-tier external replication. Honest headline: NOT_CONFIRMED on real data (see docs/EVIDENCE_LADDER.md).",
    "strong_negatives": {
        "verdict": sn.get("verdict"),
        "strong_negatives_fpr": sn.get("strong_negatives_fpr"),
        "raw_strong_negatives_fpr": sn.get("raw_strong_negatives_fpr"),
        "bifurcation_tpr": sn.get("bifurcation_tpr"),
    },
    "accumulation_control": {
        "separates": ac.get("separates"),
        "accumulation_fpr": ac.get("accumulation_fpr"),
        "raw_accumulation_fpr": ac.get("raw_accumulation_fpr"),
        "bifurcation_tpr": ac.get("bifurcation_tpr"),
    },
    "expected": {
        "strong_negatives.verdict": "STRONG_NEGATIVES_CLEAN",
        "accumulation_control.separates": True,
    },
}
(out / "REPLICATION_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))

# Technical-failure detection: a smoke replication MUST produce these artefacts.
# A negative *verdict* is fine (honest result); a MISSING artefact is a tech error.
missing = [k for k, v in {"strong_negatives.json": sn, "accumulation_control.json": ac}.items() if not v]
if missing:
    print(f"TECHNICAL: missing/empty critical artefact(s): {missing}", file=sys.stderr)
    sys.exit(3)
PY
SUMMARY_RC=$?
if [ "$SUMMARY_RC" -ne 0 ]; then
  printf '    \033[31m[FAIL]\033[0m summary: missing/empty critical artefact(s)\n'
  FAIL=$((FAIL+1))
fi

say "Done — full (non-fast) replication"
cat <<'TXT'
  This was the FAST tier. For the full proofs (minutes→tens of minutes):
    make test                 # full + scientific test tiers
    python 04_Code/pipeline/run_strong_negatives.py    --outdir out/strong_negatives    --n-surrogates 200
    python 04_Code/pipeline/run_accumulation_control.py --outdir out/accumulation_control --n-surrogates 200
    python 04_Code/pipeline/run_oos_prediction.py       --outdir out/oos --n-replicates 50 --lead 60
    python tools/replicate.py --outdir out/full
  Interpretation ladder: docs/EVIDENCE_LADDER.md
TXT

printf '\nResult: %d step(s) OK, %d FAIL → %s\n' "$PASS" "$FAIL" "$OUTDIR/REPLICATION_SUMMARY.json"

# Fail on TECHNICAL errors (a step crashed, an integrity check failed, or a
# critical artefact is missing), but NOT on an honest scientific negative: the
# runners exit 0 and emit a verdict token (NOT_CONFIRMED / STRONG_NEGATIVES_LEAK
# / OOS_SKILL_INCONCLUSIVE), and those are valid results, not failures.
if [ "$FAIL" -ne 0 ]; then
  printf '\033[31mTECHNICAL FAILURE: %d replication step(s) errored (this is NOT a scientific negative).\033[0m\n' "$FAIL"
  exit 1
fi
echo "All replication steps completed. (Scientific verdicts may still be negative — that is a valid result.)"
exit 0
