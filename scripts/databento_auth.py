"""Local Databento API-key resolution helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence


API_KEY_NAME = "DATABENTO_API_KEY"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_KEY_FILES = (
    PROJECT_ROOT / "secrets" / "databento.env",
    PROJECT_ROOT / "api.env",
    PROJECT_ROOT / "databento.env",
)


def normalize_api_key(value: str | None) -> str:
    if not value:
        return ""
    key = value.strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {"'", '"'}:
        key = key[1:-1].strip()
    return key


def load_databento_api_key_from_file(path: Path, *, key_name: str = API_KEY_NAME) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "=" not in text:
            return normalize_api_key(text)
        name, value = text.split("=", 1)
        if name.strip() == key_name:
            return normalize_api_key(value)
    return ""


def resolve_databento_api_key(
    *,
    env: Mapping[str, str] | None = None,
    key_name: str = API_KEY_NAME,
    key_files: Sequence[Path] = API_KEY_FILES,
) -> str:
    source = os.environ if env is None else env
    key = normalize_api_key(source.get(key_name, ""))
    if key:
        return key
    if env is not None:
        return ""
    for path in key_files:
        key = load_databento_api_key_from_file(path, key_name=key_name)
        if key:
            return key
    return ""
