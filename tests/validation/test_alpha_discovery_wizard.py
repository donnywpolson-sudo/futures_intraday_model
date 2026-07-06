from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.validation import run_alpha_discovery_wizard as wizard


def _write_launcher(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "@echo off",
                "python -m scripts.validation.run_alpha_discovery_wizard --skip-initial-ack --launcher-path \"%~f0\"",
                "python -m scripts.validation.run_alpha_discovery_wizard --self-check --launcher-path \"%~f0\"",
                "if /I \"%~1\"==\"--generate-candidates\" python -m scripts.validation.generate_alpha_discovery_candidates %*",
                "python -m scripts.validation.run_alpha_discovery_queue %*",
                "python -m scripts.validation.run_alpha_discovery %*",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_launcher_self_check_passes_for_matching_template(tmp_path: Path) -> None:
    template = tmp_path / "RUN_ALPHA_DISCOVERY.bat"
    _write_launcher(template)

    result = wizard.launcher_self_check(root=tmp_path, launcher_path=template)

    assert result["status"] == "LAUNCHER_SELF_CHECK_PASS"
    assert result["static_check_only"] is True
    assert result["no_arg_route"] == "scripts.validation.run_alpha_discovery_wizard"


def test_launcher_self_check_rejects_non_repo_launcher(tmp_path: Path) -> None:
    template = tmp_path / "RUN_ALPHA_DISCOVERY.bat"
    outside_launcher = tmp_path.parent / "RUN_ALPHA_DISCOVERY.bat"
    _write_launcher(template)
    outside_launcher.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(wizard.WizardError) as exc_info:
        wizard.launcher_self_check(root=tmp_path, launcher_path=outside_launcher)

    message = str(exc_info.value)
    assert "only the repo-local launcher is supported" in message
    assert "expected_launcher_path=" in message


def test_spec_for_batch_writes_configs_only_paths() -> None:
    spec = wizard._spec_for_batch(batch_id="batch_a", candidates=["candidate_a"])

    assert spec["output_config_dir"] == "configs/alpha_discovery_generated/batch_a"
    assert spec["output_queue"] == "configs/alpha_discovery_generated/alpha_discovery_queue.batch_a.json"
    assert spec["candidates"] == [
        {"id": "candidate_a", "run": "batch_a_candidate_a"},
    ]


def _write_queue(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "runner_mode": "preflight",
                "log_root": "logs/alpha_discovery_queue",
                "candidates": [
                    {
                        "id": "candidate_a",
                        "config": "configs/alpha_discovery_runner.candidate_a.json",
                        "approved": False,
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_approved_queue_copy_marks_candidates_and_refuses_overwrite(tmp_path: Path) -> None:
    queue_path = tmp_path / "configs" / "alpha_discovery_generated" / "alpha_discovery_queue.batch_a.json"
    _write_queue(queue_path)

    approved_path = wizard._approved_queue_copy(root=tmp_path, queue_path=queue_path, batch_id="batch_a")

    payload = json.loads(approved_path.read_text(encoding="utf-8"))
    assert payload["runner_mode"] == "discovery-run"
    assert payload["log_root"] == "logs/alpha_discovery_queue/batch_a"
    assert payload["candidates"][0]["approved"] is True
    assert payload["discovery_approval"]["approval_phrase"] == wizard.APPROVAL_PHRASE
    with pytest.raises(wizard.WizardError, match="refusing overwrite"):
        wizard._approved_queue_copy(root=tmp_path, queue_path=queue_path, batch_id="batch_a")


def test_discovery_prompt_prints_bounds_and_exact_repo_local_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    approved_path = wizard._approved_queue_path(tmp_path, "batch_a")

    command = wizard._print_discovery_prompt(
        root=tmp_path,
        batch_id="batch_a",
        approved_queue_path=approved_path,
        candidate_count=1,
    )

    output = capsys.readouterr().out
    assert "Optional bounded discovery-run" in output
    assert "Candidate count: 1" in output
    assert f"Default discovery candidate bound: {wizard.DEFAULT_DISCOVERY_MAX_CANDIDATES}" in output
    assert f"Timeout cap seconds: {wizard.DISCOVERY_TIMEOUT_SECONDS}" in output
    assert "Exact command:" in output
    assert str(wizard.default_launcher_path(tmp_path)) in output
    assert command[0] == str(wizard.default_launcher_path(tmp_path))
    assert "--approve-discovery-run" in command
    assert wizard.APPROVAL_PHRASE in command


def test_human_summary_for_no_candidates_is_plain_english(capsys: pytest.CaptureFixture[str]) -> None:
    wizard._print_human_summary(
        {
            "status": "NO_CANONICAL_CANDIDATES",
            "message": "Separate candidate registration is required first.",
        }
    )

    output = capsys.readouterr().out
    assert "Nothing ran." in output
    assert "no alpha-discovery candidates are registered and ready" in output
    assert "RUN_ALPHA_DISCOVERY.bat" in output
    assert "{" not in output


def test_wizard_skips_discovery_without_approved_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue_path = tmp_path / "configs" / "alpha_discovery_generated" / "alpha_discovery_queue.batch_a.json"

    monkeypatch.setattr(
        wizard,
        "launcher_self_check",
        lambda *, root, launcher_path: {"status": "LAUNCHER_SELF_CHECK_PASS"},
    )
    monkeypatch.setattr(wizard, "_ready_candidates", lambda root: ["candidate_a"])

    def fake_generate_from_spec(*, spec_path: Path, root: Path) -> dict[str, Any]:
        _write_queue(queue_path)
        return {
            "status": "GENERATOR_COMPLETED",
            "candidate_count": 1,
            "queue_path": wizard._relative(root, queue_path),
        }

    monkeypatch.setattr(wizard.generator, "generate_from_spec", fake_generate_from_spec)
    monkeypatch.setattr(
        wizard.queue_runner,
        "run_queue",
        lambda **kwargs: {
            "status": "QUEUE_COMPLETED",
            "summary": {"candidate_count": 1},
            "results": [],
        },
    )
    monkeypatch.setattr(
        wizard.autopsy,
        "write_autopsy",
        lambda **kwargs: {
            "status": "AUTOPSY_WRITTEN",
            "json_path": wizard._relative(tmp_path, kwargs["report_root"] / "autopsy.json"),
            "md_path": wizard._relative(tmp_path, kwargs["report_root"] / "autopsy.md"),
        },
    )
    inputs = iter(["all", "batch_a", "skip"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    result = wizard.run_wizard(
        root=tmp_path,
        launcher_path=tmp_path / "RUN_ALPHA_DISCOVERY.bat",
        skip_initial_ack=True,
    )

    assert result["status"] == "WIZARD_PREFLIGHT_COMPLETE"
    assert result["discovery"] is None
    assert not wizard._approved_queue_path(tmp_path, "batch_a").exists()


def test_wizard_discovery_run_writes_approved_queue_and_post_autopsy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue_path = tmp_path / "configs" / "alpha_discovery_generated" / "alpha_discovery_queue.batch_a.json"
    calls: dict[str, list[Any]] = {"queue_modes": [], "autopsy_roots": []}

    monkeypatch.setattr(
        wizard,
        "launcher_self_check",
        lambda *, root, launcher_path: {"status": "LAUNCHER_SELF_CHECK_PASS"},
    )
    monkeypatch.setattr(wizard, "_ready_candidates", lambda root: ["candidate_a"])

    def fake_generate_from_spec(*, spec_path: Path, root: Path) -> dict[str, Any]:
        _write_queue(queue_path)
        return {
            "status": "GENERATOR_COMPLETED",
            "candidate_count": 1,
            "queue_path": wizard._relative(root, queue_path),
        }

    def fake_run_queue(**kwargs: Any) -> dict[str, Any]:
        calls["queue_modes"].append(kwargs["mode_override"])
        if kwargs["mode_override"] == "discovery-run":
            approved_payload = json.loads(kwargs["queue_path"].read_text(encoding="utf-8"))
            assert approved_payload["candidates"][0]["approved"] is True
            assert kwargs["approval_token"] == wizard.APPROVAL_PHRASE
            assert kwargs["approve_discovery_run"] is True
            assert kwargs["max_discovery_candidates"] == 1
            return {
                "status": "QUEUE_COMPLETED",
                "summary": {"candidate_count": 1, "discovery_pass_count": 1},
                "results": [
                    {
                        "candidate_id": "candidate_a",
                        "config": "configs/alpha_discovery_runner.candidate_a.json",
                        "approved": True,
                        "mode": "discovery-run",
                        "status": "CANDIDATE_COMPLETED",
                        "runner_status": "DISCOVERY_RUN_CANDIDATE_DISCOVERY_PASS",
                    }
                ],
            }
        return {
            "status": "QUEUE_COMPLETED",
            "summary": {"candidate_count": 1},
            "results": [],
        }

    def fake_write_autopsy(**kwargs: Any) -> dict[str, Any]:
        calls["autopsy_roots"].append(kwargs["report_root"])
        return {
            "status": "AUTOPSY_WRITTEN",
            "json_path": wizard._relative(tmp_path, kwargs["report_root"] / "autopsy.json"),
            "md_path": wizard._relative(tmp_path, kwargs["report_root"] / "autopsy.md"),
        }

    monkeypatch.setattr(wizard.generator, "generate_from_spec", fake_generate_from_spec)
    monkeypatch.setattr(wizard.queue_runner, "run_queue", fake_run_queue)
    monkeypatch.setattr(wizard.autopsy, "write_autopsy", fake_write_autopsy)
    inputs = iter(
        [
            "ACK",
            "all",
            "batch_a",
            "discovery",
            wizard.DISCOVERY_ACKNOWLEDGEMENT,
            wizard.APPROVAL_PHRASE,
        ]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    result = wizard.run_wizard(root=tmp_path, launcher_path=tmp_path / "RUN_ALPHA_DISCOVERY.bat")

    assert result["status"] == "WIZARD_DISCOVERY_COMPLETE"
    assert calls["queue_modes"] == ["preflight", "discovery-run"]
    assert calls["autopsy_roots"] == [
        tmp_path / "reports" / "pipeline_audit" / "alpha_discovery_autopsy" / "batch_a" / "readiness",
        tmp_path / "reports" / "pipeline_audit" / "alpha_discovery_autopsy" / "batch_a" / "discovery",
    ]
    assert result["discovery"]["approved_queue_path"] == (
        "configs/alpha_discovery_generated/alpha_discovery_queue.batch_a.approved.json"
    )
    assert "--approve-discovery-run" in result["discovery"]["command"]
    assert wizard.APPROVAL_PHRASE in result["discovery"]["command"]
