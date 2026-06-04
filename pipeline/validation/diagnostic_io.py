from __future__ import annotations

from pathlib import Path
from typing import Any


DIAGNOSTIC_STRING_FIELDS = {
    "run_id",
    "profile",
    "config_env",
    "symbol",
    "split",
    "threshold_type",
    "threshold_mode",
}


def stringify_diagnostic_keys(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for field in DIAGNOSTIC_STRING_FIELDS:
        if field in out and out[field] is not None:
            out[field] = str(out[field])
    return out


def read_diagnostic_csv(path: str | Path):
    import pandas as pd

    return pd.read_csv(path, dtype={field: "string" for field in DIAGNOSTIC_STRING_FIELDS})
