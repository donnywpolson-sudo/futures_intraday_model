from __future__ import annotations

from pathlib import Path

from scripts.validation.check_coordination_docs import check_coordination_docs


ROOT = Path(__file__).resolve().parents[2]


def _write_valid_coordination_tree(root: Path) -> None:
    (root / "CODEX_HANDOFF.md").write_text(
        "\n".join(
            [
                "# Project Overview",
                "- Pipeline authority: use `PIPELINE.md` for phase order.",
                "- Repo guidance authority: use `AGENTS.md` for agent workflow.",
                "- Handoff role: this file is mutable cross-run state.",
                "- Solo Codex files: keep `AGENTS.md` and `CODEX_HANDOFF.md` only.",
                "# Current State",
                "# Recent Changes",
                "# Active Tasks",
                "# Known Issues",
                "# Next Steps",
            ]
        ),
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS",
                "## Coordination source of truth",
                "- `PIPELINE.md` is the project outline and runnable workflow authority.",
                "- `AGENTS.md` is the durable agent-rule authority.",
                "- `CODEX_HANDOFF.md` is mutable cross-run state.",
                "- Update after meaningful multi-step work, discovered blockers, research decisions, changed next steps, or any fresh-thread continuation need.",
                "- At the end of each multi-step run, update `CODEX_HANDOFF.md` before the final response.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "PIPELINE.md").write_text(
        "\n".join(
            [
                "# Pipeline",
                "This file is the repo authority for pipeline rules, layout, runnable steps.",
                "Do not reintroduce parallel phase checklists.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "Use `PIPELINE.md` for the authoritative downloader smoke test. "
        "Keep runnable pipeline commands there so setup docs do not drift.",
        encoding="utf-8",
    )
    (root / "README_RUNBOOK.md").write_text(
        "Use `PIPELINE.md` for the authoritative pipeline rebuild order, "
        "validation coverage command, phase commands, acceptance checks, and current stop rules.",
        encoding="utf-8",
    )


def test_current_repo_coordination_docs_pass() -> None:
    assert check_coordination_docs(ROOT) == []


def test_missing_handoff_section_fails(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    handoff = tmp_path / "CODEX_HANDOFF.md"
    handoff.write_text(
        handoff.read_text(encoding="utf-8").replace("# Known Issues\n", ""),
        encoding="utf-8",
    )

    errors = check_coordination_docs(tmp_path)

    assert "CODEX_HANDOFF.md missing required section: # Known Issues" in errors


def test_retired_parallel_state_file_fails(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "JOURNAL.md").write_text("stale", encoding="utf-8")

    errors = check_coordination_docs(tmp_path)

    assert "retired parallel coordination file exists: research/JOURNAL.md" in errors


def test_missing_role_links_fail(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    handoff = tmp_path / "CODEX_HANDOFF.md"
    handoff.write_text(
        handoff.read_text(encoding="utf-8").replace(
            "- Pipeline authority: use `PIPELINE.md` for phase order.\n",
            "",
        ),
        encoding="utf-8",
    )

    errors = check_coordination_docs(tmp_path)

    assert any(
        error.startswith("CODEX_HANDOFF.md missing required phrase: Pipeline authority")
        for error in errors
    )
