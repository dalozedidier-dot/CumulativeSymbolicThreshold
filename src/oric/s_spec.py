"""s_spec.py — frozen ex-ante declaration that S is a transmissible stock.

SSpec is stricter than ProxySpec. A column labelled S is not enough.
The spec must name a copy rule, a cut rule, and a source that is not a
function of Cap / O / R / I. Pilots without a valid SSpec are INDETERMINATE
for the symbolic layer (T6), not ACCEPT.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_KINDS = frozenset({"lineage", "vesicle", "code", "language", "institution"})
ALLOWED_CUTS = frozenset({"zero", "permute", "delay", "reset_generation"})
FORBIDDEN_CAP_FUNCTIONS = frozenset({"O", "R", "I", "Cap", "cap", "sigma", "Sigma", "V"})


class SSpecError(ValueError):
    """S does not meet the transmissible-stock contract."""


@dataclass(frozen=True)
class SSpec:
    """Hashable contract for the symbolic stock S.

    Fields
    ------
    dataset_id     : Dataset this spec binds to.
    spec_version   : Bump on any field change.
    kind           : lineage | vesicle | code | language | institution
    unit           : Human-readable unit (variant count, inherited motif, …).
    source_column  : Raw column that *is* S, not a Cap transform.
    copy_rule      : How S moves from bearer t to bearer t+1.
    cut_rule       : How transmission is interrupted without destroying Cap.
    cut_operator   : zero | permute | delay | reset_generation
    delay_steps    : Used only when cut_operator == delay.
    notes          : Rationale and caveats.
    """

    dataset_id: str
    spec_version: str = "1.0"
    kind: str = "lineage"
    unit: str = "transmissible_repertoire_count"
    source_column: str = "S"
    copy_rule: str = ""
    cut_rule: str = ""
    cut_operator: str = "zero"
    delay_steps: int = 1
    notes: str = ""

    def validate(self) -> None:
        for name in ("dataset_id", "spec_version", "unit", "source_column", "copy_rule", "cut_rule"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise SSpecError(f"{name} must be a non-empty string")
        if self.kind not in ALLOWED_KINDS:
            raise SSpecError(f"kind must be one of {sorted(ALLOWED_KINDS)}")
        if self.cut_operator not in ALLOWED_CUTS:
            raise SSpecError(f"cut_operator must be one of {sorted(ALLOWED_CUTS)}")
        if not self.source_column.strip():
            raise SSpecError("source_column is required")
        if self.source_column.strip().casefold() in {
            name.casefold() for name in FORBIDDEN_CAP_FUNCTIONS
        }:
            raise SSpecError(
                "source_column cannot be a Cap-layer variable; S must have a distinct support"
            )
        if not self.copy_rule.strip():
            raise SSpecError("copy_rule must state how S is transmitted")
        if not self.cut_rule.strip():
            raise SSpecError("cut_rule must state how transmission is interrupted")
        if (
            not isinstance(self.delay_steps, int)
            or isinstance(self.delay_steps, bool)
            or self.delay_steps < 1
        ):
            raise SSpecError("delay_steps must be a positive integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "spec_version": self.spec_version,
            "kind": self.kind,
            "unit": self.unit,
            "source_column": self.source_column,
            "copy_rule": self.copy_rule,
            "cut_rule": self.cut_rule,
            "cut_operator": self.cut_operator,
            "delay_steps": self.delay_steps,
            "notes": self.notes,
        }

    def sha256(self) -> str:
        self.validate()
        canonical = json.dumps(
            self.to_dict(), sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_json_file(self, path: str | Path) -> None:
        self.validate()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SSpec":
        raw: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        spec = cls(
            dataset_id=raw["dataset_id"],
            spec_version=raw.get("spec_version", "1.0"),
            kind=raw.get("kind", "lineage"),
            unit=raw.get("unit", "transmissible_repertoire_count"),
            source_column=raw.get("source_column", "S"),
            copy_rule=raw.get("copy_rule", ""),
            cut_rule=raw.get("cut_rule", ""),
            cut_operator=raw.get("cut_operator", "zero"),
            delay_steps=raw.get("delay_steps", 1),
            notes=raw.get("notes", ""),
        )
        spec.validate()
        return spec
