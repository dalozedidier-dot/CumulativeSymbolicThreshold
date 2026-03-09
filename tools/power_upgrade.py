#!/usr/bin/env python3
"""power_upgrade.py — ORI-C power upgrade pipeline.

Loads a pilot's current and densified datasets, produces a structured
upgrade report with homogeneity checks, precheck comparison, and
power class transition assessment.

The upgrade is an ORI-C object, not a CSV manipulation:
- Research question must remain unchanged
- Proxy mappings must remain unchanged
- Homogeneity of the observed regime must be maintained
- Decidability must genuinely increase

Usage:
    python tools/power_upgrade.py --pilot sector_cosmo.pilot_pantheon_sn
    python tools/power_upgrade.py --all
    python tools/power_upgrade.py --all --outdir 05_Results/pilots/power_upgrade
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"

# ── Pilot configuration ──────────────────────────────────────────────────

PILOT_CONFIGS = {
    "sector_cosmo.pilot_pantheon_sn": {
        "data_dir": "03_Data/sector_cosmo/real/pilot_pantheon_sn",
        "oric_columns": ["O", "R", "I", "demand", "S"],
        "domain_columns": ["z"],
    },
    "sector_bio.pilot_pbdb_marine": {
        "data_dir": "03_Data/sector_bio/real/pilot_pbdb_marine",
        "oric_columns": ["O", "R", "I", "demand", "S"],
        "domain_columns": ["Ma"],
    },
    "sector_ai_tech.pilot_llm_scaling": {
        "data_dir": "03_Data/sector_ai_tech/real/pilot_llm_scaling",
        "oric_columns": ["O", "R", "I", "demand", "S"],
        "domain_columns": [],
    },
}

MIN_POINTS_PER_SEGMENT = 60


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class HomogeneityCheck:
    """Result of a proxy distribution stability check."""
    column: str
    mean_before: float
    mean_after: float
    std_before: float
    std_after: float
    mean_shift: float
    std_ratio: float
    passed: bool  # shift < 0.3 and 0.5 < ratio < 2.0


@dataclass
class SegmentCount:
    """Segment point counts at a given segmentation point."""
    segmentation_point: int
    n_pre: int
    n_post: int
    adequate: bool


@dataclass
class PrecheckComparison:
    """Before/after precheck comparison."""
    n_before: int
    n_after: int
    segments_before: list[SegmentCount]
    segments_after: list[SegmentCount]
    adequate_segments_before: int
    adequate_segments_after: int
    precheck_improved: bool


@dataclass
class UpgradeReport:
    """Full structured upgrade report for one pilot."""
    pilot_id: str
    domain: str
    research_question: str
    n_before: int
    n_after: int
    power_class_before: str
    power_class_after: str
    segment_counts_before: list[dict]
    segment_counts_after: list[dict]
    precheck_before: dict
    precheck_after: dict
    homogeneity_checks: list[dict]
    homogeneity_passed: bool
    upgrade_status: str  # "upgrade_candidate" | "no_improvement" | "homogeneity_failed"
    level_before: str
    level_after: str
    justification: str
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Core functions ───────────────────────────────────────────────────────

def classify_power(n_rows: int, has_adequate_segment: bool) -> str:
    """Classify power class based on total points and segment adequacy."""
    if n_rows >= 200 and has_adequate_segment:
        return "adequate"
    elif n_rows >= 60 and has_adequate_segment:
        return "borderline"
    else:
        return "underpowered"


def compute_segment_counts(
    df: pd.DataFrame,
    segmentation_fracs: list[float],
) -> list[SegmentCount]:
    """Compute segment counts at candidate segmentation points."""
    n = len(df)
    results = []
    for frac in segmentation_fracs:
        t_seg = int(n * frac)
        if t_seg <= 0 or t_seg >= n:
            continue
        n_pre = t_seg
        n_post = n - t_seg
        results.append(SegmentCount(
            segmentation_point=t_seg,
            n_pre=n_pre,
            n_post=n_post,
            adequate=n_pre >= MIN_POINTS_PER_SEGMENT and n_post >= MIN_POINTS_PER_SEGMENT,
        ))
    return results


def check_homogeneity(
    df_before: pd.DataFrame,
    df_after: pd.DataFrame,
    columns: list[str],
) -> list[HomogeneityCheck]:
    """Check proxy distribution stability between original and densified."""
    checks = []
    for col in columns:
        if col not in df_before.columns or col not in df_after.columns:
            continue
        v_before = df_before[col].dropna().values.astype(float)
        v_after = df_after[col].dropna().values.astype(float)
        if len(v_before) == 0 or len(v_after) == 0:
            continue

        m_b, m_a = float(np.mean(v_before)), float(np.mean(v_after))
        s_b, s_a = float(np.std(v_before)), float(np.std(v_after))

        shift = abs(m_a - m_b)
        ratio = s_a / s_b if s_b > 1e-10 else float("inf")
        passed = shift < 0.3 and 0.5 < ratio < 2.0

        checks.append(HomogeneityCheck(
            column=col,
            mean_before=round(m_b, 6),
            mean_after=round(m_a, 6),
            std_before=round(s_b, 6),
            std_after=round(s_a, 6),
            mean_shift=round(shift, 6),
            std_ratio=round(ratio, 6),
            passed=passed,
        ))
    return checks


def build_precheck(
    n: int,
    segments: list[SegmentCount],
) -> dict:
    """Build precheck summary."""
    adequate = [s for s in segments if s.adequate]
    return {
        "n_rows": n,
        "n_segmentation_candidates": len(segments),
        "n_adequate_segments": len(adequate),
        "has_adequate_segment": len(adequate) > 0,
        "best_segment": asdict(adequate[0]) if adequate else None,
    }


def run_pilot_upgrade(pilot_id: str) -> UpgradeReport:
    """Run the full upgrade pipeline for one pilot."""
    config = PILOT_CONFIGS[pilot_id]
    data_dir = ROOT / config["data_dir"]

    # Load datasets
    df_before = pd.read_csv(data_dir / "real.csv")
    df_after = pd.read_csv(data_dir / "real_densified.csv")

    # Load upgrade plan for metadata
    plan_path = data_dir / "upgrade_plan.json"
    plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}

    # Segmentation candidates (7 fractions, including 0.50 midpoint)
    seg_fracs = [0.25, 0.35, 0.40, 0.45, 0.50, 0.55, 0.65]

    # Compute segments
    seg_before = compute_segment_counts(df_before, seg_fracs)
    seg_after = compute_segment_counts(df_after, seg_fracs)

    # Precheck
    precheck_before = build_precheck(len(df_before), seg_before)
    precheck_after = build_precheck(len(df_after), seg_after)

    # Power classification
    has_adequate_before = precheck_before["has_adequate_segment"]
    has_adequate_after = precheck_after["has_adequate_segment"]
    power_before = classify_power(len(df_before), has_adequate_before)
    power_after = classify_power(len(df_after), has_adequate_after)

    # Homogeneity checks
    homo_checks = check_homogeneity(
        df_before, df_after, config["oric_columns"],
    )
    homo_passed = all(c.passed for c in homo_checks)

    # Determine upgrade status
    precheck_improved = (
        precheck_after["n_adequate_segments"] > precheck_before["n_adequate_segments"]
    )

    if not homo_passed:
        status = "homogeneity_failed"
        level_after = "C"
        justification = (
            "Homogeneity checks failed. Densification changed proxy "
            "distributions beyond acceptable thresholds. Cannot upgrade."
        )
    elif precheck_improved and has_adequate_after:
        status = "upgrade_candidate"
        level_after = "B_candidate"
        justification = (
            f"Power class: {power_before} -> {power_after}. "
            f"Adequate segments: {precheck_before['n_adequate_segments']} -> "
            f"{precheck_after['n_adequate_segments']}. "
            f"Homogeneity checks passed. Upgrade to Level B candidate."
        )
    else:
        status = "no_improvement"
        level_after = "C"
        justification = (
            "Densification did not improve decidability. "
            "No additional adequate segments gained."
        )

    return UpgradeReport(
        pilot_id=pilot_id,
        domain=plan.get("domain", ""),
        research_question=plan.get("research_question", ""),
        n_before=len(df_before),
        n_after=len(df_after),
        power_class_before=power_before,
        power_class_after=power_after,
        segment_counts_before=[asdict(s) for s in seg_before],
        segment_counts_after=[asdict(s) for s in seg_after],
        precheck_before=precheck_before,
        precheck_after=precheck_after,
        homogeneity_checks=[asdict(c) for c in homo_checks],
        homogeneity_passed=homo_passed,
        upgrade_status=status,
        level_before="C",
        level_after=level_after,
        justification=justification,
    )


def save_report(report: UpgradeReport, outdir: Path) -> Path:
    """Save upgrade report to the output directory."""
    pilot_dir = outdir / report.pilot_id.replace(".", "/")
    pilot_dir.mkdir(parents=True, exist_ok=True)

    # JSON report
    report_path = pilot_dir / "power_upgrade_report.json"
    data = {
        "schema": "oric.power_upgrade_report.v1",
        **report.to_dict(),
    }
    report_path.write_text(
        json.dumps(data, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    # Precheck comparison
    comparison_path = pilot_dir / "precheck_comparison.json"
    comparison = {
        "schema": "oric.precheck_comparison.v1",
        "pilot_id": report.pilot_id,
        "precheck_before": report.precheck_before,
        "precheck_after": report.precheck_after,
        "homogeneity_checks": report.homogeneity_checks,
        "homogeneity_passed": report.homogeneity_passed,
        "upgrade_status": report.upgrade_status,
    }
    comparison_path.write_text(
        json.dumps(comparison, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    # Markdown report
    md_path = pilot_dir / "power_upgrade_report.md"
    md = _render_markdown_report(report)
    md_path.write_text(md, encoding="utf-8")

    # Copy densified CSV
    src = ROOT / PILOT_CONFIGS[report.pilot_id]["data_dir"] / "real_densified.csv"
    if src.exists():
        dst = pilot_dir / "real_densified.csv"
        dst.write_bytes(src.read_bytes())

    return report_path


def _render_markdown_report(report: UpgradeReport) -> str:
    """Render a markdown upgrade report."""
    lines = [
        f"# Power Upgrade Report: {report.pilot_id}",
        "",
        f"**Domain:** {report.domain}",
        f"**Research question:** {report.research_question}",
        f"**Upgrade status:** {report.upgrade_status}",
        "",
        "## Summary",
        "",
        f"| Metric | Before | After |",
        f"|--------|--------|-------|",
        f"| N rows | {report.n_before} | {report.n_after} |",
        f"| Power class | {report.power_class_before} | {report.power_class_after} |",
        f"| Level | {report.level_before} | {report.level_after} |",
        f"| Adequate segments | {report.precheck_before['n_adequate_segments']} | {report.precheck_after['n_adequate_segments']} |",
        "",
        "## Justification",
        "",
        report.justification,
        "",
        "## Homogeneity Checks",
        "",
        f"**All passed:** {'Yes' if report.homogeneity_passed else 'NO'}",
        "",
        "| Proxy | Mean shift | Std ratio | Passed |",
        "|-------|-----------|-----------|--------|",
    ]
    for h in report.homogeneity_checks:
        lines.append(
            f"| {h['column']} | {h['mean_shift']:.4f} | {h['std_ratio']:.4f} | "
            f"{'Yes' if h['passed'] else 'NO'} |"
        )
    lines.extend([
        "",
        "## Segment Analysis (After)",
        "",
        "| Seg. point | N pre | N post | Adequate |",
        "|------------|-------|--------|----------|",
    ])
    for s in report.segment_counts_after:
        lines.append(
            f"| {s['segmentation_point']} | {s['n_pre']} | {s['n_post']} | "
            f"{'Yes' if s['adequate'] else 'No'} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ORI-C power upgrade pipeline",
    )
    parser.add_argument(
        "--pilot",
        type=str,
        help="Pilot ID to upgrade (e.g. sector_cosmo.pilot_pantheon_sn)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run upgrade for all Level C pilots",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=ROOT / "05_Results" / "pilots" / "power_upgrade",
    )
    args = parser.parse_args()

    if args.all:
        pilot_ids = list(PILOT_CONFIGS.keys())
    elif args.pilot:
        if args.pilot not in PILOT_CONFIGS:
            parser.error(f"Unknown pilot: {args.pilot}")
        pilot_ids = [args.pilot]
    else:
        parser.error("Specify --pilot or --all")
        return

    reports = []
    for pid in pilot_ids:
        report = run_pilot_upgrade(pid)
        path = save_report(report, args.outdir)
        reports.append(report)
        icon = {"upgrade_candidate": "+", "no_improvement": "~", "homogeneity_failed": "X"}
        print(
            f"  [{icon.get(report.upgrade_status, '?')}] {pid}: "
            f"{report.n_before} -> {report.n_after} pts, "
            f"{report.power_class_before} -> {report.power_class_after}, "
            f"{report.upgrade_status}"
        )
        print(f"      -> {path}")

    # Save aggregate summary
    summary = {
        "schema": "oric.power_upgrade_summary.v2",
        "total_pilots": len(reports),
        "upgrade_candidates": sum(1 for r in reports if r.upgrade_status == "upgrade_candidate"),
        "no_improvement": sum(1 for r in reports if r.upgrade_status == "no_improvement"),
        "homogeneity_failed": sum(1 for r in reports if r.upgrade_status == "homogeneity_failed"),
        "reports": [r.to_dict() for r in reports],
    }
    summary_path = args.outdir / "power_upgrade_summary_v2.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"\n  Summary: {summary_path}")


if __name__ == "__main__":
    main()
