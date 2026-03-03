"""proxy_spec.py — versioned, hashable proxy mapping for ORI-C real-data runs.

A ProxySpec declares ex ante exactly which raw CSV columns become which ORI-C
variables (O, R, I, demand, S), how they are normalised, and how missing values
are handled.  The SHA-256 hash of the serialised spec must be logged in every
run manifest so that post-hoc column relabelling is detectable.

Usage
-----
    spec = ProxySpec.from_json_file("03_Data/real/economie/pilot_cpi/proxy_spec.json")
    print(spec.sha256())   # embed in manifest

Design constraints
------------------
- ProxySpec is frozen: construct once, never mutate.
- sha256() is deterministic across Python versions (JSON canonical form, UTF-8).
- from_json_file / to_json_file are the only I/O methods.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ColumnSpec:
    """Mapping rule for one raw column → one ORI-C variable."""

    source_column: str            # Raw CSV column name
    oric_variable: str            # Target: O | R | I | demand | S
    direction: str = "positive"   # "positive" (higher = more) or "negative" (inverted)
    normalization: str = "robust_minmax"  # none | minmax | robust_minmax
    missing_strategy: str = "linear_interp"  # none | forward_fill | linear_interp | zero
    scale_lo: float | None = None  # Override lower bound (pre-normalization)
    scale_hi: float | None = None  # Override upper bound (pre-normalization)
    fragility_note: str = ""       # Qualitative: how sensitive is this proxy to data quality?
    manipulability_note: str = ""  # Qualitative: could this proxy be gamed or mismeasured?

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_column": self.source_column,
            "oric_variable": self.oric_variable,
            "direction": self.direction,
            "normalization": self.normalization,
            "missing_strategy": self.missing_strategy,
            "scale_lo": self.scale_lo,
            "scale_hi": self.scale_hi,
            "fragility_note": self.fragility_note,
            "manipulability_note": self.manipulability_note,
        }


@dataclass(frozen=True)
class ProxySpec:
    """Versioned, hashable ex-ante declaration of all proxy mappings for one dataset.

    Fields
    ------
    dataset_id      : Unique identifier for this dataset (e.g. "pilot_cpi_FR")
    sector          : Sector label (e.g. "economie", "energie", "fred_monthly")
    spec_version    : Semantic version of this spec (bump on any change)
    time_column     : Raw column to use as time axis (ignored if time_mode="index")
    time_mode       : "index" (row order 0..n-1) or "value" (parse time column)
    columns         : Tuple of ColumnSpec, one per mapped variable
    normalization_global : Default normalization applied if column spec says "inherit"
    notes           : Free-text rationale and caveats
    """

    dataset_id: str
    sector: str
    spec_version: str = "1.0"
    time_column: str = "t"
    time_mode: str = "index"
    columns: tuple[ColumnSpec, ...] = field(default_factory=tuple)
    normalization_global: str = "robust_minmax"
    notes: str = ""

    # ── serialisation ──────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "sector": self.sector,
            "spec_version": self.spec_version,
            "time_column": self.time_column,
            "time_mode": self.time_mode,
            "normalization_global": self.normalization_global,
            "columns": [c.to_dict() for c in self.columns],
            "notes": self.notes,
        }

    def sha256(self) -> str:
        """Return SHA-256 hex digest of the canonical JSON representation.

        Canonical = sorted keys, ASCII-safe, no extra whitespace.
        Embed this in every run manifest to detect post-hoc spec modifications.
        """
        canonical = json.dumps(
            self.to_dict(), sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_json_file(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    # ── deserialisation ────────────────────────────────────────────────────────

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ProxySpec":
        p = Path(path)
        raw: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
        cols = tuple(
            ColumnSpec(
                source_column=c["source_column"],
                oric_variable=c["oric_variable"],
                direction=c.get("direction", "positive"),
                normalization=c.get("normalization", "robust_minmax"),
                missing_strategy=c.get("missing_strategy", "linear_interp"),
                scale_lo=c.get("scale_lo"),
                scale_hi=c.get("scale_hi"),
                fragility_note=c.get("fragility_note", ""),
                manipulability_note=c.get("manipulability_note", ""),
            )
            for c in raw.get("columns", [])
        )
        return cls(
            dataset_id=raw["dataset_id"],
            sector=raw["sector"],
            spec_version=raw.get("spec_version", "1.0"),
            time_column=raw.get("time_column", "t"),
            time_mode=raw.get("time_mode", "index"),
            columns=cols,
            normalization_global=raw.get("normalization_global", "robust_minmax"),
            notes=raw.get("notes", ""),
        )

    # ── helpers ────────────────────────────────────────────────────────────────

    def column_for(self, oric_variable: str) -> ColumnSpec | None:
        """Return the ColumnSpec for a given ORI-C variable, or None if absent."""
        for c in self.columns:
            if c.oric_variable == oric_variable:
                return c
        return None

    def source_columns(self) -> list[str]:
        return [c.source_column for c in self.columns]
