from __future__ import annotations

from pathlib import Path

from scripts.validation.check_coordination_docs import check_coordination_docs


ROOT = Path(__file__).resolve().parents[2]


def _write_valid_coordination_tree(root: Path) -> None:
    (root / "CODEX_HANDOFF.md").write_text(
        "\n".join(
            [
                "# Project Overview",
                "- Project outline authority: use `PROJECT_OUTLINE.md` for phase order.",
                "- Repo guidance authority: use `AGENTS.md` for agent workflow.",
                "- Handoff role: this file is mutable cross-run state.",
                "- Solo Codex files: keep `AGENTS.md`, `PROJECT_OUTLINE.md`, and `CODEX_HANDOFF.md` only.",
                "# Current State",
                "# Recent Changes",
                "# Active Tasks",
                "# Known Issues",
                "# Next Steps",
                "Exact next recommended step: review the active handoff decision.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "\n".join(
            [
                "# AGENTS",
                "## Project-Specific Rules",
                "### Coordination Source Of Truth",
                "- `PROJECT_OUTLINE.md` is the project outline, workflow, and runnable command authority.",
                "- `PIPELINE.md`, when kept, is a compatibility pointer for older references only.",
                "- `AGENTS.md` is the durable agent-rule authority.",
                "- `CODEX_HANDOFF.md` is mutable cross-run state.",
                "- Update after meaningful multi-step work, discovered blockers, research decisions, changed next steps, or any fresh-thread continuation need.",
                "- At the end of each multi-step run, update `CODEX_HANDOFF.md` before the final response.",
                "## General Codex Rules For This Repo",
            ]
        ),
        encoding="utf-8",
    )
    (root / "PROJECT_OUTLINE.md").write_text(
        "\n".join(
            [
                "# Project Outline",
                "`AGENTS.md` is the active operating rulebook.",
                "This file is the project outline, workflow, and runnable command authority.",
                "Detailed runnable commands live in this file under `Detailed Pipeline Runbook`.",
                "`PROJECT_OUTLINE.md`: project objective, layout, phase workflow, detailed runnable commands.",
                "This section is the authoritative workflow map.",
                "Feature promotion requires an audit record.",
                "## Production Deferral Gate",
                "Live/paper claims remain deferred.",
                "contract-specific execution mapping.",
                "## Detailed Pipeline Runbook",
                "Feature audit gate:",
                "Model risk gate:",
                "Statistical validity gate:",
                "Probability of Backtest Overfitting.",
                "Deflated Sharpe.",
                "Probabilistic Sharpe.",
                "bootstrap confidence intervals.",
                "multiple-testing adjustment.",
                "parameter stability.",
                "regime breakdowns.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "PIPELINE.md").write_text(
        "\n".join(
            [
                "# Pipeline",
                "The detailed pipeline runbook has been merged into `PROJECT_OUTLINE.md`.",
                "This file is kept only as a compatibility pointer.",
                "Do not add parallel phase checklists or runnable command catalogs here.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "Use `PROJECT_OUTLINE.md` for the authoritative project outline. "
        "`PIPELINE.md` is only a compatibility pointer.",
        encoding="utf-8",
    )


def test_current_repo_coordination_docs_pass() -> None:
    assert check_coordination_docs(ROOT) == []


def test_pipeline_pointer_is_optional_when_absent(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    (tmp_path / "PIPELINE.md").unlink()

    assert check_coordination_docs(tmp_path) == []


def test_pipeline_pointer_is_validated_when_present(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    (tmp_path / "PIPELINE.md").write_text("# Pipeline\nstale runnable catalog", encoding="utf-8")

    errors = check_coordination_docs(tmp_path)

    assert any(
        error.startswith(
            "PIPELINE.md missing required phrase: The detailed pipeline runbook"
        )
        for error in errors
    )


def test_project_outline_missing_research_gate_fails(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    project_outline = tmp_path / "PROJECT_OUTLINE.md"
    project_outline.write_text(
        project_outline.read_text(encoding="utf-8").replace(
            "Feature audit gate:\n",
            "",
        ),
        encoding="utf-8",
    )

    errors = check_coordination_docs(tmp_path)

    assert (
        "PROJECT_OUTLINE.md missing required phrase: Feature audit gate:"
        in errors
    )


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
            "- Project outline authority: use `PROJECT_OUTLINE.md` for phase order.\n",
            "",
        ),
        encoding="utf-8",
    )

    errors = check_coordination_docs(tmp_path)

    assert any(
        error.startswith(
            "CODEX_HANDOFF.md missing required phrase: Project outline authority"
        )
        for error in errors
    )


def test_duplicate_exact_next_blocks_fail(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    handoff = tmp_path / "CODEX_HANDOFF.md"
    handoff.write_text(
        handoff.read_text(encoding="utf-8")
        + "\nExact next recommended step: stale duplicate.\n",
        encoding="utf-8",
    )

    errors = check_coordination_docs(tmp_path)

    assert any(
        error.startswith(
            "CODEX_HANDOFF.md must contain exactly one Exact next recommended step:"
        )
        for error in errors
    )


def test_exact_next_outside_next_steps_fails(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    handoff = tmp_path / "CODEX_HANDOFF.md"
    handoff.write_text(
        handoff.read_text(encoding="utf-8")
        .replace(
            "# Next Steps\nExact next recommended step: review the active handoff decision.",
            "# Next Steps",
        )
        .replace(
            "# Current State",
            "Exact next recommended step: stale location.\n# Current State",
        ),
        encoding="utf-8",
    )

    errors = check_coordination_docs(tmp_path)

    assert (
        "CODEX_HANDOFF.md Exact next recommended step must appear after # Next Steps"
        in errors
    )


def test_exact_next_decision_leakage_fails(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    handoff = tmp_path / "CODEX_HANDOFF.md"
    handoff.write_text(
        handoff.read_text(encoding="utf-8")
        + "\nExact next decision: approve stale command.\n",
        encoding="utf-8",
    )

    errors = check_coordination_docs(tmp_path)

    assert (
        "CODEX_HANDOFF.md contains stale marker: Exact next decision:"
        in errors
    )


def test_continue_from_handoff_leakage_fails_only_in_handoff(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        agents.read_text(encoding="utf-8")
        + "\nContinue from CODEX_HANDOFF.md.\n",
        encoding="utf-8",
    )

    assert check_coordination_docs(tmp_path) == []

    handoff = tmp_path / "CODEX_HANDOFF.md"
    handoff.write_text(
        handoff.read_text(encoding="utf-8")
        + "\nContinue from CODEX_HANDOFF.md.\n",
        encoding="utf-8",
    )

    errors = check_coordination_docs(tmp_path)

    assert (
        "CODEX_HANDOFF.md contains stale fresh-thread prompt: "
        "Continue from CODEX_HANDOFF.md"
    ) in errors


def test_over_budget_handoff_length_fails(tmp_path: Path) -> None:
    _write_valid_coordination_tree(tmp_path)
    handoff = tmp_path / "CODEX_HANDOFF.md"
    handoff.write_text(
        handoff.read_text(encoding="utf-8")
        + "\n"
        + "\n".join(f"- historical line {index}" for index in range(200)),
        encoding="utf-8",
    )

    errors = check_coordination_docs(tmp_path)

    assert any(
        error.startswith(
            "CODEX_HANDOFF.md exceeds maximum active handoff length:"
        )
        for error in errors
    )
