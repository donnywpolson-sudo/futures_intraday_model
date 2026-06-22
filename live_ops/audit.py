"""Append-only JSONL audit logging for live decision cycles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .schemas import plain_data


class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write_decision(self, event: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp_utc": datetime.now(timezone.utc),
            **dict(event),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(plain_data(payload), sort_keys=True, separators=(",", ":")) + "\n")
