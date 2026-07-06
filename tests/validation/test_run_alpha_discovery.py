from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.validation import run_alpha_discovery as runner


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _make_repo(tmp_path: Path, *, hypothesis_status: str = "CANDIDATE") -> Path:
    root = tmp_path
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    (root / ".gitignore").write_text("reports/\nlogs/\ndata/\n", encoding="utf-8")
    for name in ("AGENTS.md", "PROJECT_OUTLINE.md", "CODEX_HANDOFF.md"):
        (root / name).write_text(f"# {name}\n", encoding="utf-8")
    _write_json(
        root / "manifests/target_hypotheses/registry.json",
        {
            "schema_version": 1,
            "hypotheses": [
                {
                    "target_hypothesis_id": "candidate_v1",
                    "status": hypothesis_status,
                    "wfa_allowed": hypothesis_status == "FROZEN",
                    "source_reports": [],
                    "next_allowed_actions": ["source_tests", "discovery_packet"],
                }
            ],
        },
    )
    (root / "manifests/target_hypotheses/trial_statuses.jsonl").parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    (root / "manifests/target_hypotheses/trial_statuses.jsonl").write_text(
        '{"hypothesis_id":"candidate_v1","stage":"register_candidate","status":"CANDIDATE"}\n',
        encoding="utf-8",
    )
    return root


def _config() -> dict[str, object]:
    return {
        "schema_version": 1,
        "runner_mode": "preflight",
        "hypothesis_id": "candidate_v1",
        "market": "ES",
        "profile": "tier_1",
        "stage": "discovery",
        "target_policy_contract": {
            "payoff_basis": "path_favorable_excursion",
            "entry_rule": "next_bar_open",
            "exit_or_capture_rule": "first_touch_take_profit_or_stop_loss_else_horizon_exit",
            "horizon_bars": 30,
            "cost_threshold_source": "configs/costs.yaml",
            "required_compatible_policy": "first_touch_path_capture",
            "compatible_policy_evaluation_basis": ["first_touch_path_capture"],
        },
        "source_test_commands": [
            ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/example.py"]
        ],
        "discovery_command": [
            "python",
            "-m",
            "scripts.phase9_research.es_30m_target_smoke_harness",
            "--hypothesis-id",
            "candidate_v1",
            "--run",
            "candidate_v1_discovery",
            "--stage",
            "discovery",
            "--folds",
            "ES_research_0001,ES_research_0002",
        ],
        "timeout_seconds": 300,
        "approval_token": "RUN_PHASE9_DISCOVERY_ONCE",
        "expected_outputs": [
            "reports/pipeline_audit/candidate_v1_discovery_smoke.json",
            "reports/pipeline_audit/candidate_v1_discovery_smoke.md",
        ],
    }


def test_preflight_passes_for_candidate_with_contract_and_ignored_outputs(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    config = _config()

    result = runner.run_mode(config, root=root, mode="preflight", approval_token=None)

    assert result["status"] == "PREFLIGHT_PASS"
    assert result["preflight"]["registry_status"] == "CANDIDATE"
    assert result["preflight"]["target_smoke_is_tradability_proof"] is False


def test_stale_expected_output_fails_closed(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    config = _config()
    stale_path = root / "reports/pipeline_audit/candidate_v1_discovery_smoke.json"
    stale_path.parent.mkdir(parents=True)
    stale_path.write_text("{}", encoding="utf-8")

    with pytest.raises(runner.RunnerError, match="already exist"):
        runner.run_mode(config, root=root, mode="preflight", approval_token=None)


def test_missing_registry_fails_closed(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    (root / "manifests/target_hypotheses/registry.json").unlink()

    with pytest.raises(runner.RunnerError, match="missing target registry"):
        runner.run_mode(_config(), root=root, mode="preflight", approval_token=None)


def test_non_candidate_registry_status_fails_closed(tmp_path: Path) -> None:
    root = _make_repo(tmp_path, hypothesis_status="FROZEN")

    with pytest.raises(runner.RunnerError, match="requires a CANDIDATE"):
        runner.run_mode(_config(), root=root, mode="preflight", approval_token=None)


def test_target_policy_contract_required_and_path_target_cannot_use_fixed_exit() -> None:
    config = _config()
    contract = dict(config["target_policy_contract"])  # type: ignore[arg-type]
    contract["compatible_policy_evaluation_basis"] = ["fixed_horizon_exit"]
    contract["required_compatible_policy"] = "fixed_horizon_exit"
    config["target_policy_contract"] = contract

    with pytest.raises(runner.RunnerError, match="fixed_horizon_exit"):
        runner.validate_runner_config(config, mode="preflight")


def test_discovery_command_must_match_hypothesis_and_bounded_stage() -> None:
    config = _config()
    command = list(config["discovery_command"])  # type: ignore[arg-type]
    command[command.index("--hypothesis-id") + 1] = "other_candidate"
    config["discovery_command"] = command

    with pytest.raises(runner.RunnerError, match="must match"):
        runner.validate_runner_config(config, mode="discovery-packet")


def test_source_tests_allow_only_pytest_commands() -> None:
    config = _config()
    config["source_test_commands"] = [["python", "-m", "scripts.phase9_research.es_30m_target_smoke_harness"]]

    with pytest.raises(runner.RunnerError, match="approved pytest"):
        runner.validate_runner_config(config, mode="source-tests")


def test_discovery_run_requires_exact_approval_token(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)

    with pytest.raises(runner.RunnerError, match="approval token"):
        runner.run_mode(_config(), root=root, mode="discovery-run", approval_token="WRONG")


def test_discovery_pass_json_is_candidate_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_repo(tmp_path)
    config = _config()
    original_run_capture = runner._run_capture

    def fake_run_capture(
        argv: list[str],
        *,
        cwd: Path,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv == config["discovery_command"]:
            _write_json(
                root / "reports/pipeline_audit/candidate_v1_discovery_smoke.json",
                {"decision": "DISCOVERY_PASS", "failure_count": 0, "stage": "discovery"},
            )
            (root / "reports/pipeline_audit/candidate_v1_discovery_smoke.md").write_text(
                "# Discovery\n\nDo Not Do: promote.\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
        return original_run_capture(argv, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(runner, "_run_capture", fake_run_capture)

    result = runner.run_mode(
        config,
        root=root,
        mode="discovery-run",
        approval_token="RUN_PHASE9_DISCOVERY_ONCE",
    )

    assert result["status"] == "DISCOVERY_RUN_CANDIDATE_DISCOVERY_PASS"
    assert result["discovery"]["candidate_decision"] == "DISCOVERY_PASS"
    assert result["discovery"]["candidate_passed"] is True
    assert result["discovery"]["candidate_stopped"] is False


def test_stop_json_is_candidate_stop_even_when_process_returns_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _make_repo(tmp_path)
    config = _config()
    original_run_capture = runner._run_capture

    def fake_run_capture(
        argv: list[str],
        *,
        cwd: Path,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv == config["discovery_command"]:
            _write_json(
                root / "reports/pipeline_audit/candidate_v1_discovery_smoke.json",
                {"decision": "STOP_UNSTABLE_FOLDS", "failure_count": 0, "stage": "discovery"},
            )
            (root / "reports/pipeline_audit/candidate_v1_discovery_smoke.md").write_text(
                "# Discovery\n\nDo Not Do: promote.\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
        return original_run_capture(argv, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(runner, "_run_capture", fake_run_capture)

    result = runner.run_mode(
        config,
        root=root,
        mode="discovery-run",
        approval_token="RUN_PHASE9_DISCOVERY_ONCE",
    )

    assert result["status"] == "DISCOVERY_RUN_CANDIDATE_STOPPED"
    assert result["discovery"]["command_succeeded"] is True
    assert result["discovery"]["candidate_decision"] == "STOP_UNSTABLE_FOLDS"
    assert result["discovery"]["candidate_passed"] is False
    assert result["discovery"]["candidate_stopped"] is True


def test_missing_discovery_json_after_execution_remains_review_required(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _make_repo(tmp_path)
    config = _config()
    original_run_capture = runner._run_capture

    def fake_run_capture(
        argv: list[str],
        *,
        cwd: Path,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv == config["discovery_command"]:
            return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
        return original_run_capture(argv, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(runner, "_run_capture", fake_run_capture)

    result = runner.run_mode(
        config,
        root=root,
        mode="discovery-run",
        approval_token="RUN_PHASE9_DISCOVERY_ONCE",
    )

    assert result["status"] == "DISCOVERY_RUN_REVIEW_REQUIRED"
    assert result["discovery"]["candidate_passed"] is False
    assert result["discovery"]["candidate_stopped"] is False
    assert result["discovery"]["missing_outputs"]


def test_review_mode_allows_completed_discovery_evidence(tmp_path: Path) -> None:
    root = _make_repo(tmp_path, hypothesis_status="DISCOVERY_PASS")
    (root / "manifests/target_hypotheses/trial_statuses.jsonl").write_text(
        (
            '{"hypothesis_id":"candidate_v1","stage":"register_candidate","status":"CANDIDATE"}\n'
            '{"hypothesis_id":"candidate_v1","stage":"phase9_discovery_smoke",'
            '"status":"DISCOVERY_PASS"}\n'
        ),
        encoding="utf-8",
    )
    json_path = root / "reports/pipeline_audit/candidate_v1_discovery_smoke.json"
    md_path = root / "reports/pipeline_audit/candidate_v1_discovery_smoke.md"
    _write_json(json_path, {"decision": "DISCOVERY_PASS", "failure_count": 0, "stage": "discovery"})
    md_path.write_text("# Discovery\n\nDo Not Do: promote.\n", encoding="utf-8")

    result = runner.run_mode(_config(), root=root, mode="review", approval_token=None)

    assert result["status"] == "REVIEW_COMPLETE"
    assert result["review"]["json_summaries"][0]["decision"] == "DISCOVERY_PASS"
    assert result["review"]["json_summaries"][0]["candidate_passed"] is True
    assert result["review"]["md_checks"][0]["has_do_not_do"] is True


def test_project_outline_documents_guarded_batch_runner_without_parallel_phase_catalog() -> None:
    text = Path("PROJECT_OUTLINE.md").read_text(encoding="utf-8")

    assert r"C:\Users\donny\Desktop\futures_intraday_model\RUN_ALPHA_DISCOVERY.bat" in text
    assert "launcher, not pipeline authority" in text
    for mode in ("preflight", "source-tests", "discovery-packet", "discovery-run", "review"):
        assert f"`{mode}`" in text
    assert "### 9A" not in text
