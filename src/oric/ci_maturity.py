"""ci_maturity.py — CI memory as robustness signal.

Tracks framework maturity indicators from CI run history:
- Verdict stability: how often verdicts flip between runs
- Regression frequency: how often a passing test starts failing
- Coverage evolution: test coverage trajectory
- Manifest coherence: consistency of output contracts across runs
- Cross-run robustness: how stable key metrics are across runs

Usage:
    from oric.ci_maturity import CIMaturityTracker
    tracker = CIMaturityTracker(log_path)
    tracker.record_run(run_data)
    report = tracker.compute_maturity_report()
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


RunStatus = Literal["pass", "fail", "partial"]


@dataclass
class CIRunRecord:
    """Record of a single CI run."""
    run_id: str
    timestamp: str
    branch: str = ""
    run_status: RunStatus = "pass"
    verdicts: dict[str, str] = field(default_factory=dict)
    test_count: int = 0
    test_passed: int = 0
    test_failed: int = 0
    coverage_pct: float | None = None
    manifest_coherent: bool = True
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MaturityReport:
    """Maturity indicators derived from CI history."""
    total_runs: int = 0
    pass_rate: float = 0.0
    verdict_stability: float = 0.0
    regression_count: int = 0
    regression_rate: float = 0.0
    coverage_trend: str = ""
    manifest_coherence_rate: float = 0.0
    cross_run_verdict_flips: int = 0
    maturity_level: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class CIMaturityTracker:
    """Track and analyze CI run history for framework maturity."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.runs: list[CIRunRecord] = []
        if log_path.exists():
            data = json.loads(log_path.read_text())
            for r in data.get("runs", []):
                self.runs.append(CIRunRecord(**r))

    def record_run(self, run: CIRunRecord) -> None:
        """Append a new CI run record."""
        self.runs.append(run)
        self._save()

    def _save(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema": "oric.ci_maturity_log.v1",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_runs": len(self.runs),
            "runs": [r.to_dict() for r in self.runs],
        }
        self.log_path.write_text(
            json.dumps(data, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

    def compute_maturity_report(self) -> MaturityReport:
        """Compute maturity indicators from run history."""
        report = MaturityReport()
        n = len(self.runs)
        report.total_runs = n

        if n == 0:
            report.maturity_level = "no_data"
            return report

        # Pass rate
        n_pass = sum(1 for r in self.runs if r.run_status == "pass")
        report.pass_rate = n_pass / n

        # Verdict stability: fraction of runs where all verdicts match previous
        flips = 0
        for i in range(1, n):
            prev_verdicts = self.runs[i - 1].verdicts
            curr_verdicts = self.runs[i].verdicts
            common_keys = set(prev_verdicts) & set(curr_verdicts)
            for k in common_keys:
                if prev_verdicts[k] != curr_verdicts[k]:
                    flips += 1
        report.cross_run_verdict_flips = flips
        max_possible = sum(
            len(set(self.runs[i - 1].verdicts) & set(self.runs[i].verdicts))
            for i in range(1, n)
        )
        report.verdict_stability = (
            1.0 - (flips / max_possible) if max_possible > 0 else 1.0
        )

        # Regression count: test that passed in run i-1 but failed in run i
        regressions = 0
        for i in range(1, n):
            prev = self.runs[i - 1]
            curr = self.runs[i]
            if prev.run_status == "pass" and curr.run_status == "fail":
                regressions += 1
        report.regression_count = regressions
        report.regression_rate = regressions / max(n - 1, 1)

        # Coverage trend
        coverages = [
            r.coverage_pct for r in self.runs if r.coverage_pct is not None
        ]
        if len(coverages) >= 2:
            if coverages[-1] > coverages[0]:
                report.coverage_trend = "increasing"
            elif coverages[-1] < coverages[0]:
                report.coverage_trend = "decreasing"
            else:
                report.coverage_trend = "stable"
        elif len(coverages) == 1:
            report.coverage_trend = "single_point"
        else:
            report.coverage_trend = "no_data"

        # Manifest coherence
        coherent = sum(1 for r in self.runs if r.manifest_coherent)
        report.manifest_coherence_rate = coherent / n

        # Maturity level
        if n >= 10 and report.pass_rate >= 0.95 and report.verdict_stability >= 0.95:
            report.maturity_level = "mature"
        elif n >= 5 and report.pass_rate >= 0.80 and report.verdict_stability >= 0.80:
            report.maturity_level = "stabilizing"
        elif n >= 1:
            report.maturity_level = "emerging"
        else:
            report.maturity_level = "no_data"

        report.details = {
            "n_runs": n,
            "n_pass": n_pass,
            "n_flips": flips,
            "n_regressions": regressions,
            "latest_coverage": coverages[-1] if coverages else None,
        }

        return report

    def save_report(self, outpath: Path) -> MaturityReport:
        """Compute and save maturity report."""
        report = self.compute_maturity_report()
        outpath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema": "oric.ci_maturity_report.v1",
            "generated": datetime.now(timezone.utc).isoformat(),
            **report.to_dict(),
        }
        outpath.write_text(
            json.dumps(data, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        return report
