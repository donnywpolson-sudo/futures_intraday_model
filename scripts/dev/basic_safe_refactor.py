#!/usr/bin/env python3
"""Dry-run-first mechanical cleanup for Python files.

This intentionally avoids semantic refactors. The only writeable changes are:

* add one missing final newline
* strip trailing spaces/tabs outside Python string literals

Dirty Git paths are skipped by default so local work is not mixed with cleanup.
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


UTF8_BOM = b"\xef\xbb\xbf"

EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "_archive",
    "artifacts",
    "data",
    "logs",
    "manifests",
    "models",
    "reports",
}


@dataclass(frozen=True)
class RefactorResult:
    path: Path
    changed: bool
    changes: tuple[str, ...] = ()
    skipped: str | None = None


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def git_root() -> Path | None:
    result = run_git(["rev-parse", "--show-toplevel"], check=False)
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def normalize(path: Path | str) -> str:
    return str(path).replace("\\", "/").strip("/")


def excluded(path: str) -> bool:
    parts = PurePosixPath(normalize(path)).parts
    return any(part in EXCLUDED_DIRS for part in parts[:-1])


def tracked_python_files(root: Path) -> list[Path]:
    result = run_git(["ls-files", "*.py"])
    paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [root / Path(path) for path in paths if not excluded(path)]


def dirty_paths(root: Path) -> set[str]:
    result = run_git(["status", "--porcelain", "-z"], check=False)
    if result.returncode != 0:
        return set()

    entries = [entry for entry in result.stdout.split("\0") if entry]
    dirty: set[str] = set()
    idx = 0
    while idx < len(entries):
        entry = entries[idx]
        status = entry[:2]
        path = entry[3:]
        dirty.add(normalize(path))
        if status.startswith("R") or status.startswith("C"):
            idx += 1
            if idx < len(entries):
                dirty.add(normalize(entries[idx]))
        idx += 1

    return {normalize(root / Path(path)) for path in dirty}


def cli_paths(root: Path, paths: list[str]) -> list[Path]:
    selected: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        full_path = path if path.is_absolute() else root / path
        if full_path.is_dir():
            selected.extend(
                child
                for child in full_path.rglob("*.py")
                if not excluded(normalize(child.relative_to(root)))
            )
        elif full_path.suffix == ".py":
            selected.append(full_path)
    return sorted(set(selected))


def split_body_newline(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""


def dominant_newline(lines: list[str]) -> str:
    counts = {"\n": 0, "\r\n": 0, "\r": 0}
    for line in lines:
        _, newline = split_body_newline(line)
        if newline:
            counts[newline] += 1
    return max(counts, key=counts.get) if any(counts.values()) else "\n"


def string_literal_lines(text: str) -> set[int]:
    protected: set[int] = set()
    reader = io.StringIO(text).readline
    for token in tokenize.generate_tokens(reader):
        if token.type != tokenize.STRING:
            continue
        start_line = token.start[0]
        end_line = token.end[0]
        protected.update(range(start_line, end_line + 1))
    return protected


def compile_ok(path: Path, text: str) -> str | None:
    try:
        compile(text, str(path), "exec")
    except SyntaxError as exc:
        return f"syntax error before cleanup: line {exc.lineno}"
    return None


def cleaned_text(path: Path, text: str) -> tuple[str, tuple[str, ...], str | None]:
    syntax_error = compile_ok(path, text)
    if syntax_error is not None:
        return text, (), syntax_error

    try:
        protected = string_literal_lines(text)
    except tokenize.TokenError as exc:
        return text, (), f"tokenize error before cleanup: {exc.args[0]}"

    changes: list[str] = []
    lines = text.splitlines(keepends=True)
    cleaned_lines: list[str] = []
    stripped_count = 0
    for line_number, line in enumerate(lines, start=1):
        body, newline = split_body_newline(line)
        if line_number in protected:
            cleaned_lines.append(line)
            continue

        stripped = body.rstrip(" \t")
        if stripped != body:
            stripped_count += 1
        cleaned_lines.append(f"{stripped}{newline}")

    cleaned = "".join(cleaned_lines)
    if stripped_count:
        changes.append(f"strip trailing whitespace on {stripped_count} line(s)")

    if cleaned and not cleaned.endswith(("\n", "\r")):
        cleaned += dominant_newline(lines)
        changes.append("add final newline")

    if cleaned != text:
        try:
            compile(cleaned, str(path), "exec")
        except SyntaxError as exc:
            return text, (), f"cleanup would break syntax: line {exc.lineno}"

    return cleaned, tuple(changes), None


def read_source(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    had_bom = raw.startswith(UTF8_BOM)
    if had_bom:
        raw = raw[len(UTF8_BOM) :]
    return raw.decode("utf-8"), had_bom


def write_source(path: Path, text: str, had_bom: bool) -> None:
    raw = text.encode("utf-8")
    if had_bom:
        raw = UTF8_BOM + raw
    path.write_bytes(raw)


def refactor_file(path: Path, write: bool) -> RefactorResult:
    try:
        text, had_bom = read_source(path)
    except OSError as exc:
        return RefactorResult(path=path, changed=False, skipped=f"read failed: {exc}")
    except UnicodeDecodeError:
        return RefactorResult(path=path, changed=False, skipped="not UTF-8")

    cleaned, changes, skipped = cleaned_text(path, text)
    if skipped is not None:
        return RefactorResult(path=path, changed=False, skipped=skipped)
    if cleaned == text:
        return RefactorResult(path=path, changed=False)

    if write:
        write_source(path, cleaned, had_bom)

    return RefactorResult(path=path, changed=True, changes=changes)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run-first, semantics-preserving Python cleanup."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional files/directories. Defaults to tracked Python files.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply cleanup. Default only reports proposed changes.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit nonzero when cleanup would change files.",
    )
    parser.add_argument(
        "--include-dirty",
        action="store_true",
        help="Allow files with uncommitted Git changes.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = git_root()
    if root is None:
        print("Not inside a Git repository.")
        return 1

    paths = cli_paths(root, args.paths) if args.paths else tracked_python_files(root)
    seen = sorted(set(path.resolve() for path in paths))
    dirty = dirty_paths(root)

    results: list[RefactorResult] = []
    skipped_dirty = 0
    for path in seen:
        if not path.exists() or path.suffix != ".py":
            continue
        normalized_path = normalize(path)
        if not args.include_dirty and normalized_path in dirty:
            skipped_dirty += 1
            continue
        results.append(refactor_file(path, write=args.write))

    changed = [result for result in results if result.changed]
    skipped = [result for result in results if result.skipped]
    verb = "Changed" if args.write else "Would change"

    print(f"Scanned {len(results)} Python file(s).")
    print(f"{verb} {len(changed)} file(s).")
    if skipped_dirty:
        print(f"Skipped {skipped_dirty} dirty Git path(s).")

    for result in changed:
        rel_path = normalize(result.path.relative_to(root))
        print(f"  {rel_path}: {', '.join(result.changes)}")

    if skipped:
        print("Skipped files:")
        for result in skipped:
            rel_path = normalize(result.path.relative_to(root))
            print(f"  {rel_path}: {result.skipped}")

    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
