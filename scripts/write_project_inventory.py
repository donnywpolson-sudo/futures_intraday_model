#!/usr/bin/env python3
"""Write a small project inventory manifest.

The script reads project files and writes a CSV manifest. It never modifies
data/artifact inputs. By default it excludes local data, generated artifacts,
virtual environments, Git metadata, and caches.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("manifests/project_inventory.csv")

ALWAYS_EXCLUDE_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "venv",
}

DATA_ARTIFACT_DIRS = {
    "artifacts",
    "cache",
    "data",
    "logs",
    "models",
    "output",
    "outputs",
    "reports",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT.as_posix(),
        help="Manifest CSV path relative to the project root.",
    )
    parser.add_argument(
        "--hash",
        action="store_true",
        help="Compute SHA256 for each included file. This is off by default.",
    )
    parser.add_argument(
        "--include-data",
        action="store_true",
        help="Include local data/artifact directories in the inventory.",
    )
    return parser.parse_args()


def relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def is_excluded_dir(path: Path, include_data: bool) -> bool:
    name = path.name
    if name in ALWAYS_EXCLUDE_NAMES:
        return True
    if include_data:
        return False
    rel = relative_posix(path)
    return rel in DATA_ARTIFACT_DIRS


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(include_data: bool) -> list[Path]:
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        current = Path(dirpath)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not is_excluded_dir(current / dirname, include_data)
        ]
        for filename in filenames:
            path = current / filename
            if path.name in ALWAYS_EXCLUDE_NAMES:
                continue
            paths.append(path)
    return sorted(paths, key=relative_posix)


def format_mtime(path: Path) -> str:
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return modified.isoformat(timespec="seconds").replace("+00:00", "Z")


def build_row(path: Path, include_hash: bool) -> dict[str, str | int]:
    size_bytes = path.stat().st_size
    row: dict[str, str | int] = {
        "relative_path": relative_posix(path),
        "size_bytes": size_bytes,
        "size_mb": f"{size_bytes / (1024 * 1024):.6f}",
        "modified_time": format_mtime(path),
        "suffix": path.suffix.lower(),
    }
    if include_hash:
        row["sha256"] = sha256_file(path)
    return row


def main() -> int:
    args = parse_args()
    output = PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "relative_path",
        "size_bytes",
        "size_mb",
        "modified_time",
        "suffix",
    ]
    if args.hash:
        fieldnames.append("sha256")

    files = iter_files(include_data=args.include_data)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for path in files:
            writer.writerow(build_row(path, include_hash=args.hash))

    print(f"Wrote {relative_posix(output)} with {len(files)} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
