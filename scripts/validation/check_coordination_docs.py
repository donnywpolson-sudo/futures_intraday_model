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

MAX_HANDOFF_LINES = 180
EXACT_NEXT_MARKER = "Exact next recommended step:"
EXACT_NEXT_DECISION_MARKER = "Exact next decision:"
FRESH_THREAD_MARKER = "Continue from CODEX_HANDOFF.md"

RETIRED_COORDINATION_PATHS = (
    Path("PROJECT_STATE.md"),
    Path("research") / "JOURNAL.md",
    Path("CURRENT_PIPELINE.md"),
    Path("project_layout.md"),
)

HANDOFF_REQUIRED_PHRASES = (
    "Project outline authority: use `PROJECT_OUTLINE.md`",
    "Repo guidance authority: use `AGENTS.md`",
    "Handoff role: this file is mutable cross-run state",
    "Solo Codex files: keep `AGENTS.md`, `PROJECT_OUTLINE.md`, and `CODEX_HANDOFF.md` only",
)

AGENTS_REQUIRED_PHRASES = (
    "## Project-Specific Rules",
    "## General Codex Rules For This Repo",
    "### Coordination Source Of Truth",
    "`PROJECT_OUTLINE.md` is the project outline, workflow, and runnable command authority",
    "`PIPELINE.md`, when kept, is a compatibility pointer for older references only",
    "`AGENTS.md` is the durable agent-rule authority",
    "`CODEX_HANDOFF.md` is mutable cross-run state",
    "meaningful multi-step work",
    "discovered blockers",
    "research decisions",
    "changed next steps",
    "fresh-thread continuation need",
    "At the end of each multi-step run, update `CODEX_HANDOFF.md`",
)

PROJECT_OUTLINE_REQUIRED_PHRASES = (
    "`AGENTS.md` is the active operating rulebook",
    "This file is the project outline, workflow, and runnable command authority",
    "Detailed runnable commands live in this file under `Detailed Pipeline Runbook`",
    "`PROJECT_OUTLINE.md`: project objective, layout, phase workflow, detailed runnable commands",
    "This section is the authoritative workflow map",
    "Feature promotion requires an audit record",
    "## Production Deferral Gate",
    "Live/paper claims remain deferred",
    "contract-specific execution mapping",
    "## Detailed Pipeline Runbook",
    "Feature audit gate:",
    "Model risk gate:",
    "Statistical validity gate:",
    "Probability of Backtest Overfitting",
    "Deflated Sharpe",
    "Probabilistic Sharpe",
    "bootstrap confidence intervals",
    "multiple-testing adjustment",
    "parameter stability",
    "regime breakdowns",
)

PIPELINE_REQUIRED_PHRASES = (
    "The detailed pipeline runbook has been merged into `PROJECT_OUTLINE.md`",
    "This file is kept only as a compatibility pointer",
    "add parallel phase checklists or runnable command catalogs here",
)

README_REQUIRED_PHRASES = (
    "Use `PROJECT_OUTLINE.md` for the authoritative project outline",
    "`PIPELINE.md` is only a compatibility pointer",
)

def _read_required(root: Path, relative_path: str, errors: list[str]) -> str:
    path = root / relative_path
    if not path.is_file():
        errors.append(f"missing required file: {relative_path}")
        return ""
    return path.read_text(encoding="utf-8")


def _read_optional(root: Path, relative_path: str) -> str:
    path = root / relative_path
    if not path.is_file():
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


def _check_handoff_continuation_markers(text: str, errors: list[str]) -> None:
    line_count = len(text.splitlines())
    if line_count > MAX_HANDOFF_LINES:
        errors.append(
            "CODEX_HANDOFF.md exceeds maximum active handoff length: "
            f"{line_count} lines > {MAX_HANDOFF_LINES}"
        )

    exact_next_count = text.count(EXACT_NEXT_MARKER)
    if exact_next_count != 1:
        errors.append(
            "CODEX_HANDOFF.md must contain exactly one "
            f"{EXACT_NEXT_MARKER} marker; found {exact_next_count}"
        )

    next_steps_position = text.find("# Next Steps")
    exact_next_position = text.find(EXACT_NEXT_MARKER)
    if exact_next_position >= 0 and (
        next_steps_position < 0 or exact_next_position < next_steps_position
    ):
        errors.append(
            "CODEX_HANDOFF.md Exact next recommended step must appear "
            "after # Next Steps"
        )

    if EXACT_NEXT_DECISION_MARKER in text:
        errors.append(
            f"CODEX_HANDOFF.md contains stale marker: {EXACT_NEXT_DECISION_MARKER}"
        )

    if FRESH_THREAD_MARKER in text:
        errors.append(
            f"CODEX_HANDOFF.md contains stale fresh-thread prompt: {FRESH_THREAD_MARKER}"
        )


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
    project_outline = _read_required(root, "PROJECT_OUTLINE.md", errors)
    pipeline = _read_optional(root, "PIPELINE.md")
    readme = _read_required(root, "README.md", errors)

    if handoff:
        _check_required_handoff_sections(handoff, errors)
        _check_handoff_continuation_markers(handoff, errors)
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
    if project_outline:
        _require_phrases(
            project_outline,
            relative_path="PROJECT_OUTLINE.md",
            phrases=PROJECT_OUTLINE_REQUIRED_PHRASES,
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
