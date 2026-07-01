#!/usr/bin/env python3
"""Validate the repo coordination documents stay aligned."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_HANDOFF_SECTIONS = (
    "# Project Overview",
    "# Current State",
    "# Recent Changes",
    "# Active Tasks",
    "# Known Issues",
    "# Next Steps",
)

RETIRED_COORDINATION_PATHS = (
    Path("PROJECT_STATE.md"),
    Path("research") / "JOURNAL.md",
    Path("CURRENT_PIPELINE.md"),
    Path("project_layout.md"),
)

HANDOFF_REQUIRED_PHRASES = (
    "Pipeline authority: use `PIPELINE.md`",
    "Repo guidance authority: use `AGENTS.md`",
    "Handoff role: this file is mutable cross-run state",
    "Solo Codex files: keep `AGENTS.md` and `CODEX_HANDOFF.md` only",
)

AGENTS_REQUIRED_PHRASES = (
    "## Coordination source of truth",
    "`PIPELINE.md` is the project outline and runnable workflow authority",
    "`AGENTS.md` is the durable agent-rule authority",
    "`CODEX_HANDOFF.md` is mutable cross-run state",
    "meaningful multi-step work",
    "discovered blockers",
    "research decisions",
    "changed next steps",
    "fresh-thread continuation need",
    "At the end of each multi-step run, update `CODEX_HANDOFF.md`",
)

PIPELINE_REQUIRED_PHRASES = (
    "This file is the repo authority for pipeline rules, layout, runnable steps",
    "do not reintroduce parallel phase checklists",
)

README_REQUIRED_PHRASES = (
    "Use `PIPELINE.md` for the authoritative downloader smoke test",
    "Keep runnable pipeline commands there so setup docs do not",
)

RUNBOOK_REQUIRED_PHRASES = (
    "Use `PIPELINE.md` for the authoritative pipeline rebuild order",
    "validation coverage command, phase commands, acceptance checks",
)


def _read_required(root: Path, relative_path: str, errors: list[str]) -> str:
    path = root / relative_path
    if not path.is_file():
        errors.append(f"missing required file: {relative_path}")
        return ""
    return path.read_text(encoding="utf-8")


def _compact_whitespace(value: str) -> str:
    return " ".join(value.split())


def _require_phrases(
    text: str,
    *,
    relative_path: str,
    phrases: tuple[str, ...],
    errors: list[str],
) -> None:
    compact_text = _compact_whitespace(text)
    for phrase in phrases:
        if phrase not in text and _compact_whitespace(phrase) not in compact_text:
            errors.append(f"{relative_path} missing required phrase: {phrase}")


def _check_required_handoff_sections(text: str, errors: list[str]) -> None:
    for section in REQUIRED_HANDOFF_SECTIONS:
        if section not in text:
            errors.append(f"CODEX_HANDOFF.md missing required section: {section}")

    positions = [text.find(section) for section in REQUIRED_HANDOFF_SECTIONS]
    if all(position >= 0 for position in positions) and positions != sorted(positions):
        errors.append("CODEX_HANDOFF.md required sections are out of order")


def _check_retired_paths(root: Path, errors: list[str]) -> None:
    for relative_path in RETIRED_COORDINATION_PATHS:
        if (root / relative_path).exists():
            errors.append(
                "retired parallel coordination file exists: "
                f"{relative_path.as_posix()}"
            )


def check_coordination_docs(root: Path) -> list[str]:
    """Return actionable coordination-doc failures for *root*."""

    root = root.resolve()
    errors: list[str] = []

    handoff = _read_required(root, "CODEX_HANDOFF.md", errors)
    agents = _read_required(root, "AGENTS.md", errors)
    pipeline = _read_required(root, "PIPELINE.md", errors)
    readme = _read_required(root, "README.md", errors)
    runbook = _read_required(root, "README_RUNBOOK.md", errors)

    if handoff:
        _check_required_handoff_sections(handoff, errors)
        _require_phrases(
            handoff,
            relative_path="CODEX_HANDOFF.md",
            phrases=HANDOFF_REQUIRED_PHRASES,
            errors=errors,
        )
    if agents:
        _require_phrases(
            agents,
            relative_path="AGENTS.md",
            phrases=AGENTS_REQUIRED_PHRASES,
            errors=errors,
        )
    if pipeline:
        _require_phrases(
            pipeline,
            relative_path="PIPELINE.md",
            phrases=PIPELINE_REQUIRED_PHRASES,
            errors=errors,
        )
    if readme:
        _require_phrases(
            readme,
            relative_path="README.md",
            phrases=README_REQUIRED_PHRASES,
            errors=errors,
        )
    if runbook:
        _require_phrases(
            runbook,
            relative_path="README_RUNBOOK.md",
            phrases=RUNBOOK_REQUIRED_PHRASES,
            errors=errors,
        )

    _check_retired_paths(root, errors)
    return errors


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    errors = check_coordination_docs(Path(args.repo_root))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("PASS coordination docs are aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
