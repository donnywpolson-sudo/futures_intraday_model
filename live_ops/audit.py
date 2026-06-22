"""Append-only JSONL audit logging for live decision cycles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .schemas import plain_data

SENSITIVE_FIELD_MARKERS = (
    "api_key",
    "secret",
    "token",
    "password",
    "credential",
    "account_id",
    "account_number",
)
REDACTED = "[REDACTED]"


class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def ensure_writable(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8"):
            pass

    def write_decision(self, event: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp_utc": datetime.now(timezone.utc),
            **_redact_sensitive(dict(event)),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(plain_data(payload), sort_keys=True, separators=(",", ":")) + "\n")


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            if any(marker in text_key.lower() for marker in SENSITIVE_FIELD_MARKERS):
                result[text_key] = REDACTED
            else:
                result[text_key] = _redact_sensitive(item)
        return result
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_sensitive(item) for item in value)
    return value
