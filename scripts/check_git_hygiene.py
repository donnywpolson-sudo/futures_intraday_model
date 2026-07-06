#!/usr/bin/env python3
"""Check staged Git changes for generated artifacts and large files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath


MAX_BYTES = 50 * 1024 * 1024
FORBIDDEN_SUFFIXES = {
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
FORBIDDEN_FILENAMES = {
    ".env",
    ".env.local",
    ".envrc",
    "api.env",
    "credentials.json",
    "databento.env",
    "secrets.json",
}
FORBIDDEN_NAME_PREFIXES = ("databento_api_key", ".databento_api_key")
FORBIDDEN_DIRS = {
    ".codex_home",
    ".venv",
    "artifacts",
    "build",
    "cache",
    "codex-log",
    "credentials",
    "data/causally_gated_normalized",
    "data",
    "data/dbn",
    "data/feature_matrices",
    "data/features",
    "data/labeled",
    "data/predictions",
    "data/raw",
    "data/session_normalized",
    "data/validated",
    "dist",
    "live_chart",
    "logs",
    "models",
    "output",
    "outputs",
    "reports",
    "secrets",
    "venv",
}


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def git_lines(args: list[str]) -> list[str]:
    result = run_git(args)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def git_root() -> Path | None:
    result = run_git(["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def path_contexts(tracked: set[str], staged: set[str]) -> dict[str, set[str]]:
    contexts: dict[str, set[str]] = {}
    for path in tracked:
        contexts.setdefault(path, set()).add("tracked")
    for path in staged:
        contexts.setdefault(path, set()).add("staged")
    return contexts


def working_tree_size(root: Path, path: str) -> int:
    full_path = root / Path(path)
    if full_path.exists() and full_path.is_file():
        return full_path.stat().st_size
    return 0


def matches_forbidden_dir(path: str) -> str | None:
    normalized = normalize(path)
    for forbidden in sorted(FORBIDDEN_DIRS, key=len, reverse=True):
        if normalized == forbidden or normalized.startswith(f"{forbidden}/"):
            return forbidden
    return None


def is_allowed_metadata(path: str) -> bool:
    normalized = normalize(path)
    parts = PurePosixPath(normalized).parts
    suffix = PurePosixPath(normalized).suffix.lower()
    return bool(parts and parts[0] == "manifests" and suffix in ALLOWED_METADATA_SUFFIXES)


def forbidden_filename(path: str) -> str | None:
    name = PurePosixPath(normalize(path)).name.lower()
    if name in FORBIDDEN_FILENAMES:
        return name
    if any(name.startswith(prefix) for prefix in FORBIDDEN_NAME_PREFIXES):
        return name
    return None


def forbidden_suffix(path: str) -> str | None:
    if is_allowed_metadata(path):
        return None
    suffix = PurePosixPath(normalize(path)).suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES:
        return suffix
    return None


def print_findings(title: str, rows: list[tuple[str, str]]) -> None:
    if not rows:
        return
    print(title)
    for path, reason in rows:
        print(f"  {path} ({reason})")


def collect_findings(
    root: Path,
    *,
    tracked: set[str],
    staged: set[str],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return large-file and forbidden-artifact findings.

    Existing tracked generated reports are intentionally grandfathered. A path
    fails artifact policy when it is staged for add/copy/modify/rename.
    """

    contexts = path_contexts(tracked, staged)
    large_files: list[tuple[str, str]] = []
    forbidden_files: list[tuple[str, str]] = []

    for path in sorted(contexts):
        context_set = contexts[path]
        context = ",".join(sorted(context_set))
        size = working_tree_size(root, path)
        if size > MAX_BYTES and "staged" in context_set:
            mb = size / (1024 * 1024)
            large_files.append((path, f"{mb:.2f} MiB, {context}"))

        if "staged" not in context_set:
            continue

        blocked_name = forbidden_filename(path)
        blocked_dir = matches_forbidden_dir(path)
        blocked_suffix = forbidden_suffix(path)
        if blocked_name:
            forbidden_files.append((path, f"forbidden filename {blocked_name}, {context}"))
        elif blocked_dir:
            forbidden_files.append((path, f"forbidden directory {blocked_dir}, {context}"))
        elif blocked_suffix:
            forbidden_files.append((path, f"forbidden extension {blocked_suffix}, {context}"))

    return large_files, forbidden_files


def main() -> int:
    root = git_root()
    if root is None:
        print("Not inside a Git repository; no Git hygiene check was run.")
        return 0

    tracked = {normalize(path) for path in git_lines(["ls-files"])}
    staged = {
        normalize(path)
        for path in git_lines(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    }
    large_files, forbidden_files = collect_findings(root, tracked=tracked, staged=staged)

    print_findings("Large staged files over 50 MiB:", large_files)
    print_findings("Forbidden staged artifact paths:", forbidden_files)

    if large_files or forbidden_files:
        print()
        print("Remediation:")
        print("  1. If a file is only staged, unstage it with: git restore --staged -- <path>")
        print("  2. If a generated file is staged from prior tracking, untrack it with: git rm --cached -- <path>")
        print("  3. Confirm .gitignore covers the path, then rerun: python scripts/check_git_hygiene.py")
        return 1

    print("Git hygiene clean: no staged large or forbidden artifact paths found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
