from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


class ExperimentLogger:
    """Append-only JSONL logger for experiments."""

    def __init__(self, outdir: str | Path) -> None:
        self.outdir = Path(outdir)
        self.outdir.mkdir(parents=True, exist_ok=True)
        self.path = self.outdir / "experiment_log.jsonl"

    def log(self, event: str, payload: Dict[str, Any]) -> None:
        rec = {
            "ts_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "event": event,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
