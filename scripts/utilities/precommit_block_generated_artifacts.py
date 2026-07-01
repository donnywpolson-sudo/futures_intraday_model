#!/usr/bin/env python3
"""Reject generated artifacts in staged changes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath


BLOCKED_SUFFIXES = {
    ".arrow",
    ".csv",
    ".dbn",
    ".duckdb",
    ".exe",
    ".feather",
    ".h5",
    ".hdf5",
    ".joblib",
    ".jsonl",
    ".log",
    ".npy",
    ".npz",
    ".parquet",
    ".pickle",
    ".pkl",
    ".pkg",
    ".pyz",
    ".sqlite",
    ".sqlite3",
    ".toc",
    ".zip",
    ".zst",
}
ALLOWED_METADATA_SUFFIXES = {".csv", ".jsonl"}
BLOCKED_FILENAMES = {
    ".env",
    ".env.local",
    ".envrc",
    "api.env",
    "credentials.json",
    "databento.env",
    "secrets.json",
}
BLOCKED_NAME_PREFIXES = ("databento_api_key", ".databento_api_key")
BLOCKED_DIRS = {
    ".codex_home",
    ".venv",
    "artifacts",
    "build",
    "cache",
    "codex-log",
    "credentials",
    "data",
    "dist",
    "logs",
    "models",
    "output",
    "outputs",
    "reports",
    "secrets",
    "venv",
}


def is_blocked(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")
    parts = PurePosixPath(normalized).parts
    name = PurePosixPath(normalized).name.lower()
    suffix = PurePosixPath(normalized).suffix.lower()
    is_allowed_manifest_metadata = (
        bool(parts)
        and parts[0] == "manifests"
        and suffix in ALLOWED_METADATA_SUFFIXES
    )
    return (
        name in BLOCKED_FILENAMES
        or any(name.startswith(prefix) for prefix in BLOCKED_NAME_PREFIXES)
        or (suffix in BLOCKED_SUFFIXES and not is_allowed_manifest_metadata)
        or any(part in BLOCKED_DIRS for part in parts[:-1])
    )


def staged_paths() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def main(argv: list[str]) -> int:
    paths = argv or staged_paths()
    blocked = sorted(path for path in paths if is_blocked(path))
    if not blocked:
        return 0

    print("Generated artifacts must not be committed:")
    for path in blocked:
        print(f"  {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
