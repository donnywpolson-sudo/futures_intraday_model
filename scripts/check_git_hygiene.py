#!/usr/bin/env python3
"""Check tracked and staged Git files for large or forbidden artifacts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath


MAX_BYTES = 50 * 1024 * 1024
FORBIDDEN_SUFFIXES = {
    ".dbn",
    ".feather",
    ".h5",
    ".hdf5",
    ".joblib",
    ".npy",
    ".npz",
    ".parquet",
    ".pkl",
    ".zst",
}
FORBIDDEN_DIRS = {
    ".venv",
    "artifacts",
    "cache",
    "data/causally_gated_normalized",
    "data/dbn",
    "data/feature_matrices",
    "data/features",
    "data/labeled",
    "data/predictions",
    "data/raw",
    "data/session_normalized",
    "data/validated",
    "logs",
    "models",
    "output",
    "outputs",
    "reports",
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


def forbidden_suffix(path: str) -> str | None:
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
    contexts = path_contexts(tracked, staged)

    large_files: list[tuple[str, str]] = []
    forbidden_files: list[tuple[str, str]] = []

    for path in sorted(contexts):
        context = ",".join(sorted(contexts[path]))
        size = working_tree_size(root, path)
        if size > MAX_BYTES:
            mb = size / (1024 * 1024)
            large_files.append((path, f"{mb:.2f} MiB, {context}"))

        blocked_dir = matches_forbidden_dir(path)
        blocked_suffix = forbidden_suffix(path)
        if blocked_dir:
            forbidden_files.append((path, f"forbidden directory {blocked_dir}, {context}"))
        elif blocked_suffix:
            forbidden_files.append((path, f"forbidden extension {blocked_suffix}, {context}"))

    print_findings("Large tracked/staged files over 50 MiB:", large_files)
    print_findings("Forbidden tracked/staged artifact paths:", forbidden_files)

    if large_files or forbidden_files:
        print()
        print("Remediation:")
        print("  1. If a file is only staged, unstage it with: git restore --staged -- <path>")
        print("  2. If a generated file is already tracked, remove it from Git only with: git rm --cached -- <path>")
        print("  3. Confirm .gitignore covers the path, then rerun: python scripts/check_git_hygiene.py")
        return 1

    print("Git hygiene clean: no tracked/staged large or forbidden artifact paths found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
