from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.validation import generate_alpha_discovery_candidates as generator
from scripts.validation import run_alpha_discovery as single_runner
from scripts.phase9_research.es_30m_target_smoke_harness import TARGET_SPECS


CANDIDATE_A = "vol_scaled_terminal_30m_v1"
CANDIDATE_B = "triple_barrier_30m_v1"


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _make_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    (root / ".gitignore").write_text("reports/\nlogs/\ndata/\nmodels/\n", encoding="utf-8")
    for name in ("AGENTS.md", "PROJECT_OUTLINE.md", "CODEX_HANDOFF.md"):
        (root / name).write_text(f"# {name}\n", encoding="utf-8")


def _template_config() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "template": True,
        "runner_mode": "source-tests",
        "hypothesis_id": "replace_with_registered_candidate_id",
        "market": "ES",
        "profile": "tier_1",
        "stage": "discovery",
        "target_registry": "manifests/target_hypotheses/registry.json",
        "target_trial_statuses": "manifests/target_hypotheses/trial_statuses.jsonl",
        "target_policy_contract": {
            "payoff_basis": "path_favorable_excursion",
            "entry_rule": "next_bar_open",
            "exit_or_capture_rule": "first_touch_take_profit_or_stop_loss_else_horizon_exit",
            "horizon_bars": 30,
            "cost_threshold_source": "configs/costs.yaml",
            "required_compatible_policy": "first_touch_path_capture",
            "compatible_policy_evaluation_basis": ["first_touch_path_capture"],
            "incompatible_policy_evaluation_basis": ["fixed_horizon_exit"],
        },
        "source_test_commands": [
            ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/example.py"]
        ],
        "discovery_command": [
            "python",
            "-m",
            "scripts.phase9_research.es_30m_target_smoke_harness",
            "--hypothesis-id",
            "replace_with_registered_candidate_id",
            "--run",
            "replace_with_bounded_run_name",
            "--stage",
            "discovery",
            "--folds",
            "ES_research_0001,ES_research_0002",
            "--target-registry",
            "manifests/target_hypotheses/registry.json",
            "--target-trial-statuses",
            "manifests/target_hypotheses/trial_statuses.jsonl",
        ],
        "timeout_seconds": 300,
        "approval_token": "RUN_PHASE9_DISCOVERY_ONCE",
        "expected_outputs": [
            "reports/pipeline_audit/replace_with_bounded_run_name_replace_with_registered_candidate_id_discovery_smoke.json",
            "reports/pipeline_audit/replace_with_bounded_run_name_replace_with_registered_candidate_id_discovery_smoke.md",
        ],
    }


def _registry(
    candidate_ids: list[str],
    *,
    status: str = "CANDIDATE",
    wfa_allowed: bool = False,
    source_reports: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "hypotheses": [
            {
                "target_hypothesis_id": candidate_id,
                "status": status,
                "wfa_allowed": wfa_allowed,
                "target_family": TARGET_SPECS.get(candidate_id, TARGET_SPECS[CANDIDATE_A]).target_family,
                "scope": {
                    "profile": "tier_1",
                    "resolved_profile": "tier_1_research",
                    "markets": ["ES"],
                    "years": [2023, 2024],
                },
                "source_reports": source_reports or [],
                "next_allowed_actions": ["preflight"],
            }
            for candidate_id in candidate_ids
        ],
    }


def _trial_statuses(
    candidate_ids: list[str],
    *,
    status: str = "CANDIDATE",
    stage: str = "register_candidate",
    evidence: list[str] | None = None,
) -> str:
    return "".join(
        json.dumps(
            {
                "schema_version": 1,
                "hypothesis_id": candidate_id,
                "trial_id": f"{candidate_id}_registered",
                "stage": stage,
                "status": status,
                "evidence": evidence or [],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for candidate_id in candidate_ids
    )


def _write_spec(root: Path, candidates: list[dict[str, str]], **overrides: Any) -> Path:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "batch_id": "test_batch",
        "template_config": "configs/template_runner.test.json",
        "output_config_dir": "configs/generated/test_batch",
        "output_queue": "configs/generated/alpha_discovery_queue.test_batch.json",
        "max_candidates": 100,
        "candidates": candidates,
    }
    payload.update(overrides)
    return _write_json(root / "configs" / "alpha_discovery_candidates.test_batch.json", payload)


def _write_ideation_launcher(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "@echo off",
                "python -m scripts.validation.generate_alpha_discovery_candidates --self-check --launcher-path \"%~f0\"",
                (
                    "python -m scripts.validation.generate_alpha_discovery_candidates "
                    "--generate-candidates --write-review-packet --select-implementation --max-ideas 10"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_marked_v2_pair(root: Path, stem: str, *, json_note: str = "old") -> None:
    report_root = root / generator.IDEATION_REPORT_ROOT
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / f"{stem}.md").write_text(
        f"{generator.MARKDOWN_GENERATOR_MARKER}\n# old\n",
        encoding="utf-8",
    )
    _write_json(
        report_root / f"{stem}.json",
        {
            "schema_version": 2,
            "generated_by": generator.IDEATION_GENERATOR_ID,
            "note": json_note,
        },
    )


def _write_unmarked_pair(root: Path, stem: str, *, subdir: str | None = None) -> None:
    report_root = root / generator.IDEATION_REPORT_ROOT
    if subdir:
        report_root = report_root / subdir
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / f"{stem}.md").write_text("# user edited current packet\n", encoding="utf-8")
    _write_json(report_root / f"{stem}.json", {"schema_version": 1, "note": "unmarked current"})


def _proposal_id(index: int) -> str:
    return str(generator.IDEATION_LIBRARY[index - 1]["target_hypothesis_id"])


def _packet_filename(index: int, suffix: str) -> str:
    return generator._candidate_packet_filename(index, generator.IDEATION_LIBRARY[index - 1], suffix)


def _packet_path(index: int, suffix: str, *, root: str = "reports/pipeline_audit/strategy_candidate_ideation") -> str:
    return f"{root}/{_packet_filename(index, suffix)}"


def _packet_stem(index: int) -> str:
    return _packet_filename(index, "json").removesuffix(".json")


def test_default_ideation_library_has_ten_unique_candidates() -> None:
    ids = [proposal["target_hypothesis_id"] for proposal in generator.IDEATION_LIBRARY]

    assert generator.DEFAULT_IDEATION_MAX_CANDIDATES == 10
    assert len(ids) >= generator.DEFAULT_IDEATION_MAX_CANDIDATES
    assert len(ids) == len(set(ids))
    assert ids[:10] == [
        "opening_drive_followthrough_5m_v1",
        "opening_drive_failed_followthrough_15m_v1",
        "vwap_reclaim_continuation_15m_v1",
        "session_compression_breakout_30m_v1",
        "inside_session_range_breakout_60m_v1",
        "gap_fill_failure_continuation_60m_v1",
        "midday_liquidity_reversal_15m_v1",
        "trend_day_pullback_continuation_60m_v1",
        "opening_range_retest_first_touch_v1",
        "late_session_range_resolve_session_close_v1",
    ]
    assert not all(candidate_id.endswith("_30m_v1") for candidate_id in ids[:10])

    for proposal in generator.IDEATION_LIBRARY:
        assert set(generator._risk_flags(proposal).values()) <= generator.RISK_FLAG_VALUES
        assert proposal["horizon_label"]
        assert proposal["target_horizon"]
        assert proposal["exit_rule"]


def _prepare_inputs(
    root: Path,
    candidate_ids: list[str],
    *,
    registry: dict[str, Any] | None = None,
    trial_statuses: str | None = None,
    template: dict[str, Any] | None = None,
) -> None:
    _make_repo(root)
    _write_json(root / "configs" / "template_runner.test.json", template or _template_config())
    _write_json(root / generator.CANONICAL_REGISTRY, registry or _registry(candidate_ids))
    (root / generator.CANONICAL_TRIAL_STATUSES).parent.mkdir(parents=True, exist_ok=True)
    (root / generator.CANONICAL_TRIAL_STATUSES).write_text(
        trial_statuses or _trial_statuses(candidate_ids),
        encoding="utf-8",
    )


def test_generates_preflight_configs_and_queue(tmp_path: Path) -> None:
    candidates = [
        {"id": CANDIDATE_A, "run": "batch_a"},
        {"id": CANDIDATE_B, "run": "batch_b"},
    ]
    _prepare_inputs(tmp_path, [candidate["id"] for candidate in candidates])
    spec_path = _write_spec(tmp_path, candidates)

    result = generator.generate_from_spec(spec_path=spec_path, root=tmp_path)

    assert result["status"] == "GENERATOR_COMPLETED"
    assert result["candidate_count"] == 2
    assert result["canonical_candidate_gate"] == "passed"
    assert result["writes_restricted_to_configs"] is True
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "models").exists()
    assert not (tmp_path / "logs").exists()

    queue = json.loads((tmp_path / result["queue_path"]).read_text(encoding="utf-8"))
    assert queue["runner_mode"] == "preflight"
    assert queue["max_candidates"] == 100
    assert [entry["id"] for entry in queue["candidates"]] == [
        CANDIDATE_A,
        CANDIDATE_B,
    ]
    assert all(entry["approved"] is False for entry in queue["candidates"])

    for candidate, config_path_text in zip(candidates, result["config_paths"]):
        config = json.loads((tmp_path / config_path_text).read_text(encoding="utf-8"))
        assert "template" not in config
        assert config["runner_mode"] == "preflight"
        assert config["hypothesis_id"] == candidate["id"]
        assert candidate["run"] in config["expected_outputs"][0]
        assert candidate["id"] in config["expected_outputs"][0]
        single_runner.validate_runner_config(config, mode="preflight")
        preflight = single_runner.run_mode(
            config,
            root=tmp_path,
            mode="preflight",
            approval_token=None,
        )
        assert preflight["status"] == "PREFLIGHT_PASS"


def test_duplicate_candidate_ids_fail_closed(tmp_path: Path) -> None:
    _prepare_inputs(tmp_path, [CANDIDATE_A])
    spec_path = _write_spec(
        tmp_path,
        [
            {"id": CANDIDATE_A, "run": "batch_a"},
            {"id": CANDIDATE_A, "run": "batch_b"},
        ],
    )

    with pytest.raises(generator.GeneratorError, match="duplicate candidate id"):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)


def test_max_candidate_count_is_enforced(tmp_path: Path) -> None:
    candidates = [
        {"id": f"candidate_{index:03d}", "run": f"batch_{index:03d}"}
        for index in range(generator.HARD_MAX_CANDIDATES + 1)
    ]
    _prepare_inputs(tmp_path, [CANDIDATE_A])
    spec_path = _write_spec(tmp_path, candidates, max_candidates=generator.HARD_MAX_CANDIDATES)

    with pytest.raises(generator.GeneratorError, match="max_candidates"):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)


def test_empty_candidate_list_fails_closed(tmp_path: Path) -> None:
    _prepare_inputs(tmp_path, [])
    spec_path = _write_spec(tmp_path, [])

    with pytest.raises(generator.GeneratorError, match="at least one"):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)


def test_existing_output_file_fails_closed(tmp_path: Path) -> None:
    _prepare_inputs(tmp_path, [CANDIDATE_A])
    spec_path = _write_spec(tmp_path, [{"id": CANDIDATE_A, "run": "batch_a"}])
    existing = tmp_path / "configs" / "generated" / "test_batch" / f"alpha_discovery_runner.{CANDIDATE_A}.json"
    existing.parent.mkdir(parents=True)
    existing.write_text("{}", encoding="utf-8")

    with pytest.raises(generator.GeneratorError, match="refusing overwrite"):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)


def test_outputs_must_stay_under_configs(tmp_path: Path) -> None:
    _prepare_inputs(tmp_path, [CANDIDATE_A])
    spec_path = _write_spec(
        tmp_path,
        [{"id": CANDIDATE_A, "run": "batch_a"}],
        output_config_dir="reports/generated",
    )

    with pytest.raises(generator.GeneratorError, match="output_config_dir"):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)


def test_cli_accepts_batch_route_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _prepare_inputs(tmp_path, [CANDIDATE_A])
    spec_path = _write_spec(tmp_path, [{"id": CANDIDATE_A, "run": "batch_a"}])
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    try:
        exit_code = generator.main(["--generate-candidates", "--spec", spec_path.as_posix()])
    finally:
        generator.repo_root = original_repo_root

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out)["status"] == "GENERATOR_COMPLETED"


def test_cli_without_spec_prints_proposal_only_ideation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _make_repo(tmp_path)
    _write_json(
        tmp_path / generator.CANONICAL_REGISTRY,
        {
            "schema_version": 1,
            "hypotheses": [
                {
                    "target_hypothesis_id": "opening_drive_followthrough_5m_v1",
                    "status": "REJECTED",
                }
            ],
        },
    )
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    try:
        exit_code = generator.main(["--generate-candidates", "--max-ideas", "2"])
    finally:
        generator.repo_root = original_repo_root

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "STRATEGY_CANDIDATE_IDEATION_READY"
    assert payload["proposal_only"] is True
    assert payload["generated_runnable_configs"] is False
    assert payload["candidate_count"] == 2
    assert payload["schema_version"] == 2
    assert payload["generated_by"] == generator.IDEATION_GENERATOR_ID
    assert payload["safety"] == {
        "configs_written": False,
        "data_written": False,
        "logs_written": False,
        "models_written": False,
        "phase8_run": False,
        "promotion_or_deployment_evidence": False,
        "registry_status_mutated": False,
        "reports_written": False,
        "review_packet_written": False,
        "staging_commits_pushes": False,
        "target_specs_mutated": False,
        "wizard_run": False,
        "wfa_run": False,
    }
    assert payload["candidates"][0]["target_hypothesis_id"] != "opening_drive_followthrough_5m_v1"
    first = payload["candidates"][0]
    assert first["schema_version"] == 2
    assert first["generated_by"] == generator.IDEATION_GENERATOR_ID
    assert first["draft_only"] is True
    assert first["applied"] is False
    assert first["conversion_required"] is True
    assert first["compatible_runnable_harness"] is None
    assert first["current_wizard_compatible"] is False
    assert first["horizon_label"] == "15m"
    assert first["target_horizon"] == {"kind": "fixed_bars", "bar_size": "1m", "bars": 15}
    assert first["exit_rule"] == {"kind": "fixed_horizon_close"}
    assert first["evidence_status"] == "not_model_trust_evidence"
    assert first["requires_explicit_approval_before_registry_status_mutation"] is True
    assert first["actual_model_backtest_metrics"] == {
        "backtest_metrics": "not_run",
        "live_or_paper_metrics": "not_run",
        "phase8_metrics": "not_run",
        "promotion_metrics": "not_run",
        "wfa_metrics": "not_run",
    }
    assert set(first["actual_model_backtest_metrics"].values()) == {"not_run"}
    assert first["review_card"]["setup_type"]
    assert first["review_card"]["horizon_label"] == "15m"
    assert first["review_card"]["conversion_required"] is True
    assert first["review_card"]["compatible_runnable_harness"] is None
    assert first["review_card"]["current_wizard_compatible"] is False
    assert first["review_card"]["wizard_readiness_status"] in generator.WIZARD_READINESS_VALUES
    assert first["review_card"]["evidence_status"] == "not_model_trust_evidence"
    assert set(first["review_card"]["risk_flags"].values()) <= generator.RISK_FLAG_VALUES
    assert first["proposed_implementation_contract"]
    assert first["proposed_implementation_contract"]["compatible_runnable_harness"] is None
    assert first["proposed_implementation_contract"]["current_wizard_compatible"] is False
    assert "proposed_target_spec_location" not in first["proposed_implementation_contract"]
    assert first["target_construction_contract"]
    assert first["source_test_plan"]
    assert first["source_test_plan"]["pytest_targets"] == []
    assert first["source_test_plan"]["test_location_status"] == "requires_selected_compatible_harness"
    assert first["registry_patch_draft"]["status"] == "CANDIDATE"
    assert first["registry_patch_draft"]["wfa_allowed"] is False
    assert first["registry_patch_draft"]["current_wizard_compatible"] is False
    assert first["registry_patch_draft"]["source_reports"] == []
    assert first["trial_status_patch_draft"]["stage"] == "register_candidate"
    assert first["trial_status_patch_draft"]["evidence"] == []
    assert first["post_registration_config_spec_draft"]["runnable"] is False
    assert "No compatible runnable harness has been selected yet" in (
        first["post_registration_config_spec_draft"]["reason_not_runnable"]
    )
    assert first["selected_candidate_next_prompt"].startswith(
        "Implement only this selected candidate from its draft JSON: "
    )
    assert "discovery-run" in first["selected_candidate_next_prompt"]
    assert "TARGET_SPECS" not in first["selected_candidate_next_prompt"]
    assert "es_30m_target_smoke_harness" not in json.dumps(first, sort_keys=True)
    assert "test_es_30m_target_smoke_harness" not in json.dumps(first, sort_keys=True)
    assert "draft_registry_entry" not in first
    assert "draft_trial_status_entry" not in first
    assert not (tmp_path / "configs").exists()
    assert not (tmp_path / "reports").exists()
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "models").exists()
    assert not (tmp_path / "logs").exists()


def test_proposal_only_ideation_does_not_require_target_specs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})

    def fail_if_called() -> dict[str, Any]:
        raise AssertionError("proposal-only ideation must not import TARGET_SPECS")

    monkeypatch.setattr(generator, "_target_specs", fail_if_called)

    payload = generator.ideate_strategy_candidates(root=tmp_path, max_ideas=2)
    packet = generator.write_review_packet(root=tmp_path, max_ideas=1, timestamp="no_specs")

    assert payload["status"] == "STRATEGY_CANDIDATE_IDEATION_READY"
    assert payload["candidate_count"] == 2
    assert packet["status"] == "STRATEGY_CANDIDATE_REVIEW_PACKET_WRITTEN"
    assert packet["candidate_count"] == 1


def test_candidate_packet_filename_regex_and_bad_ids_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    bad_proposal = dict(generator.IDEATION_LIBRARY[0])
    bad_proposal["target_hypothesis_id"] = "Bad-Name_v1"

    assert generator.CANDIDATE_PACKET_FILENAME_RE == r"^[0-9]{3}_[a-z0-9_]+_v[0-9]+\.(md|json)$"
    assert re.fullmatch(
        generator.CANDIDATE_PACKET_FILENAME_RE,
        "001_opening_drive_followthrough_5m_v1.md",
    )
    assert not re.fullmatch(generator.CANDIDATE_PACKET_FILENAME_RE, "001_Bad-Name_v1.md")
    monkeypatch.setattr(generator, "IDEATION_LIBRARY", (bad_proposal,))

    with pytest.raises(generator.GeneratorError, match="candidate packet filename"):
        generator.ideate_strategy_candidates(root=tmp_path, max_ideas=1)


def test_write_review_packet_writes_markdown_and_json_under_reports_only(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    registry_path = tmp_path / generator.CANONICAL_REGISTRY
    statuses_path = tmp_path / generator.CANONICAL_TRIAL_STATUSES
    harness_path = tmp_path / "scripts" / "phase9_research" / "es_30m_target_smoke_harness.py"
    harness_path.parent.mkdir(parents=True, exist_ok=True)
    harness_path.write_text("# target spec harness fixture\n", encoding="utf-8")
    _write_json(registry_path, {"schema_version": 1, "hypotheses": []})
    statuses_path.parent.mkdir(parents=True, exist_ok=True)
    statuses_path.write_text("", encoding="utf-8")
    registry_before = registry_path.read_text(encoding="utf-8")
    statuses_before = statuses_path.read_text(encoding="utf-8")
    harness_before = harness_path.read_text(encoding="utf-8")

    result = generator.write_review_packet(root=tmp_path, max_ideas=2, timestamp="test_packet")

    assert result["status"] == "STRATEGY_CANDIDATE_REVIEW_PACKET_WRITTEN"
    assert result["candidate_count"] == 2
    assert result["output_dir"] == "reports/pipeline_audit/strategy_candidate_ideation"
    assert result["packet_timestamp"] == "test_packet"
    assert result["candidate_files"] == [
        {
            "index": 1,
            "target_hypothesis_id": "opening_drive_followthrough_5m_v1",
            "markdown_path": (
                "reports/pipeline_audit/strategy_candidate_ideation/"
                "001_opening_drive_followthrough_5m_v1.md"
            ),
            "json_path": (
                "reports/pipeline_audit/strategy_candidate_ideation/"
                "001_opening_drive_followthrough_5m_v1.json"
            ),
        },
        {
            "index": 2,
            "target_hypothesis_id": "opening_drive_failed_followthrough_15m_v1",
            "markdown_path": (
                "reports/pipeline_audit/strategy_candidate_ideation/"
                "002_opening_drive_failed_followthrough_15m_v1.md"
            ),
            "json_path": (
                "reports/pipeline_audit/strategy_candidate_ideation/"
                "002_opening_drive_failed_followthrough_15m_v1.json"
            ),
        },
    ]
    assert result["archive"] == {"archive_dir": None, "moved_files": []}
    assert registry_path.read_text(encoding="utf-8") == registry_before
    assert statuses_path.read_text(encoding="utf-8") == statuses_before
    assert harness_path.read_text(encoding="utf-8") == harness_before
    assert not (tmp_path / "configs").exists()
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "models").exists()
    assert not (tmp_path / "logs").exists()

    first_paths = result["candidate_files"][0]
    markdown = (tmp_path / first_paths["markdown_path"]).read_text(encoding="utf-8")
    payload = json.loads((tmp_path / first_paths["json_path"]).read_text(encoding="utf-8"))
    assert markdown.startswith(generator.MARKDOWN_GENERATOR_MARKER)
    assert "# 001 opening_drive_followthrough_5m_v1" in markdown
    assert "matching_json_path:" in markdown
    assert "horizon_label: 5m" in markdown
    assert "conversion_required: true" in markdown
    assert "current_wizard_compatible: false" in markdown
    assert "```json" not in markdown
    assert "Draft Registry Entry" not in markdown
    assert "Draft Trial-Status Entry" not in markdown
    assert "evidence_status: not_model_trust_evidence" in markdown
    assert "wizard_readiness_status: not_runnable" in markdown
    assert "TARGET_SPECS" not in markdown
    assert "es_30m_target_smoke_harness" not in markdown
    assert payload["status"] == "STRATEGY_CANDIDATE_IDEATION_READY"
    assert payload["schema_version"] == 2
    assert payload["generated_by"] == generator.IDEATION_GENERATOR_ID
    assert payload["draft_only"] is True
    assert payload["applied"] is False
    assert payload["conversion_required"] is True
    assert payload["compatible_runnable_harness"] is None
    assert payload["current_wizard_compatible"] is False
    assert payload["horizon_label"] == "5m"
    assert payload["target_horizon"] == {"kind": "fixed_bars", "bar_size": "1m", "bars": 5}
    assert payload["exit_rule"] == {"kind": "fixed_horizon_close"}
    assert payload["requires_explicit_approval_before_registry_status_mutation"] is True
    assert payload["evidence_status"] == "not_model_trust_evidence"
    assert payload["candidate_index"] == 1
    assert payload["target_hypothesis_id"] == "opening_drive_followthrough_5m_v1"
    assert payload["safety"]["review_packet_written"] is True
    assert payload["safety"]["reports_written"] is True
    assert payload["safety"]["configs_written"] is False
    assert payload["safety"]["data_written"] is False
    assert payload["safety"]["logs_written"] is False
    assert payload["safety"]["models_written"] is False
    assert payload["review_card"]["matching_json_path"] == first_paths["json_path"]
    assert payload["review_card"]["horizon_label"] == "5m"
    assert payload["review_card"]["conversion_required"] is True
    assert payload["review_card"]["current_wizard_compatible"] is False
    assert payload["review_card"]["wizard_readiness_status"] in generator.WIZARD_READINESS_VALUES
    assert payload["review_card"]["evidence_status"] == "not_model_trust_evidence"
    assert set(payload["review_card"]["risk_flags"].values()) <= generator.RISK_FLAG_VALUES
    assert payload["post_registration_config_spec_draft"]["runnable"] is False
    assert "No compatible runnable harness has been selected yet" in (
        payload["post_registration_config_spec_draft"]["reason_not_runnable"]
    )
    assert "draft_registry_entry" not in payload
    assert "draft_trial_status_entry" not in payload
    assert "registry_patch_draft" in payload
    assert "trial_status_patch_draft" in payload
    assert set(payload["actual_model_backtest_metrics"].values()) == {"not_run"}
    assert payload["selected_candidate_next_prompt"].startswith(
        "Implement only this selected candidate from its draft JSON: opening_drive_followthrough_5m_v1."
    )
    assert "WFA" in payload["selected_candidate_next_prompt"]
    assert "discovery-run" in payload["selected_candidate_next_prompt"]
    assert "TARGET_SPECS" not in payload["selected_candidate_next_prompt"]
    assert "es_30m_target_smoke_harness" not in json.dumps(payload, sort_keys=True)
    assert "test_es_30m_target_smoke_harness" not in json.dumps(payload, sort_keys=True)


@pytest.mark.parametrize(
    ("raw_selection", "candidate_count", "expected"),
    [
        ("1,3,7", 10, [1, 3, 7]),
        ("1 3 7", 10, [1, 3, 7]),
        ("1, 3 7", 10, [1, 3, 7]),
        ("all", 3, [1, 2, 3]),
        ("1,1,2", 3, [1, 2]),
        ("", 3, None),
        ("\n", 3, None),
        ("skip", 3, None),
        ("cancel", 3, None),
    ],
)
def test_parse_implementation_selection_accepts_supported_inputs(
    raw_selection: str,
    candidate_count: int,
    expected: list[int] | None,
) -> None:
    assert generator._parse_implementation_selection(raw_selection, candidate_count=candidate_count) == expected


@pytest.mark.parametrize("raw_selection", ["x", "1,x", "0", "4", "all,1", "skip,1"])
def test_parse_implementation_selection_rejects_invalid_inputs(raw_selection: str) -> None:
    with pytest.raises(generator.GeneratorError):
        generator._parse_implementation_selection(raw_selection, candidate_count=3)


def test_select_implementation_writes_selection_under_review_root_only(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    registry_path = tmp_path / generator.CANONICAL_REGISTRY
    statuses_path = tmp_path / generator.CANONICAL_TRIAL_STATUSES
    harness_path = tmp_path / "scripts" / "phase9_research" / "es_30m_target_smoke_harness.py"
    harness_path.parent.mkdir(parents=True, exist_ok=True)
    harness_path.write_text("# target spec harness fixture\n", encoding="utf-8")
    _write_json(registry_path, {"schema_version": 1, "hypotheses": []})
    statuses_path.parent.mkdir(parents=True, exist_ok=True)
    statuses_path.write_text("", encoding="utf-8")
    registry_before = registry_path.read_text(encoding="utf-8")
    statuses_before = statuses_path.read_text(encoding="utf-8")
    harness_before = harness_path.read_text(encoding="utf-8")
    review_packet = generator.write_review_packet(root=tmp_path, max_ideas=2, timestamp="selection_packet")

    selection, exit_code = generator.select_implementation_candidates(
        root=tmp_path,
        review_packet=review_packet,
        raw_selection="2,1",
    )

    assert exit_code == 0
    assert selection["status"] == "READY"
    assert selection["selection_path"] == (
        "reports/pipeline_audit/strategy_candidate_ideation/implementation_selection.json"
    )
    selection_path = tmp_path / selection["selection_path"]
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["status"] == "IMPLEMENTATION_SELECTION_READY"
    assert payload["generated_by"] == generator.IMPLEMENTATION_SELECTION_GENERATOR_ID
    assert payload["selection_source"] == "review_packet_candidate_files"
    assert payload["source_review_dir"] == "reports/pipeline_audit/strategy_candidate_ideation"
    assert payload["source_packet_timestamp"] == "selection_packet"
    assert payload["raw_selection"] == "2,1"
    assert payload["selected_candidate_count"] == 2
    assert [item["index"] for item in payload["selected_candidates"]] == [2, 1]
    for item in payload["selected_candidates"]:
        json_path = tmp_path / item["json_path"]
        assert item["json_sha256"] == generator._sha256_file(json_path)
        assert item["markdown_path"].startswith("reports/pipeline_audit/strategy_candidate_ideation/")
        assert item["json_path"].startswith("reports/pipeline_audit/strategy_candidate_ideation/")
    assert "not registry/status approval" in payload["blocked_actions"]
    assert "verify every selected JSON file" in payload["next_step"]
    assert registry_path.read_text(encoding="utf-8") == registry_before
    assert statuses_path.read_text(encoding="utf-8") == statuses_before
    assert harness_path.read_text(encoding="utf-8") == harness_before
    assert not (tmp_path / "configs").exists()
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "models").exists()
    assert not (tmp_path / "logs").exists()


def test_select_implementation_skip_does_not_replace_existing_selection(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    review_packet = generator.write_review_packet(root=tmp_path, max_ideas=1, timestamp="skip_packet")
    selection_path = tmp_path / review_packet["output_dir"] / generator.IMPLEMENTATION_SELECTION_FILENAME
    selection_path.write_text("existing\n", encoding="utf-8")

    selection, exit_code = generator.select_implementation_candidates(
        root=tmp_path,
        review_packet=review_packet,
        raw_selection="skip\n",
    )

    assert exit_code == 0
    assert selection["status"] == "SKIPPED"
    assert selection_path.read_text(encoding="utf-8") == "existing\n"


def test_select_implementation_invalid_keeps_review_packet_without_selection_write(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    review_packet = generator.write_review_packet(root=tmp_path, max_ideas=1, timestamp="invalid_packet")

    selection, exit_code = generator.select_implementation_candidates(
        root=tmp_path,
        review_packet=review_packet,
        raw_selection="2",
    )

    assert exit_code == 1
    assert selection["status"] == "FAILED"
    assert "out of range" in selection["failure"]
    assert (tmp_path / review_packet["candidate_files"][0]["json_path"]).exists()
    assert not (tmp_path / review_packet["output_dir"] / generator.IMPLEMENTATION_SELECTION_FILENAME).exists()


def test_review_packet_refresh_archives_unmarked_files_and_overwrites_v2_only(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    report_root = tmp_path / generator.IDEATION_REPORT_ROOT
    _write_marked_v2_pair(tmp_path, "001_opening_drive_followthrough_5m_v1", json_note="old_v2")
    _write_unmarked_pair(tmp_path, "002_opening_drive_failed_followthrough_15m_v1")
    _write_unmarked_pair(tmp_path, "003_vwap_reclaim_continuation_15m_v1", subdir="nested")
    (report_root / "notes.md").write_text("# keep me\n", encoding="utf-8")
    (report_root / "_archive" / "collision").mkdir(parents=True, exist_ok=True)

    result = generator.write_review_packet(root=tmp_path, max_ideas=2, timestamp="collision")

    assert result["archive"]["archive_dir"] == (
        "reports/pipeline_audit/strategy_candidate_ideation/_archive/collision_001"
    )
    assert result["archive"]["moved_files"] == [
        {
            "from": (
                "reports/pipeline_audit/strategy_candidate_ideation/"
                "002_opening_drive_failed_followthrough_15m_v1.json"
            ),
            "to": (
                "reports/pipeline_audit/strategy_candidate_ideation/_archive/collision_001/"
                "002_opening_drive_failed_followthrough_15m_v1.json"
            ),
        },
        {
            "from": (
                "reports/pipeline_audit/strategy_candidate_ideation/"
                "002_opening_drive_failed_followthrough_15m_v1.md"
            ),
            "to": (
                "reports/pipeline_audit/strategy_candidate_ideation/_archive/collision_001/"
                "002_opening_drive_failed_followthrough_15m_v1.md"
            ),
        },
    ]
    refreshed_markdown = (
        report_root / "001_opening_drive_followthrough_5m_v1.md"
    ).read_text(encoding="utf-8")
    refreshed_json = json.loads(
        (report_root / "001_opening_drive_followthrough_5m_v1.json").read_text(encoding="utf-8")
    )
    assert refreshed_markdown.startswith(generator.MARKDOWN_GENERATOR_MARKER)
    assert "# old" not in refreshed_markdown
    assert "note" not in refreshed_json
    archived_markdown = (
        report_root
        / "_archive"
        / "collision_001"
        / "002_opening_drive_failed_followthrough_15m_v1.md"
    )
    archived_json = (
        report_root
        / "_archive"
        / "collision_001"
        / "002_opening_drive_failed_followthrough_15m_v1.json"
    )
    assert archived_markdown.read_text(encoding="utf-8") == "# user edited current packet\n"
    assert json.loads(archived_json.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "note": "unmarked current",
    }
    new_second_payload = json.loads(
        (report_root / "002_opening_drive_failed_followthrough_15m_v1.json").read_text(encoding="utf-8")
    )
    assert new_second_payload["generated_by"] == generator.IDEATION_GENERATOR_ID
    assert (report_root / "notes.md").read_text(encoding="utf-8") == "# keep me\n"
    assert (
        report_root / "nested" / "003_vwap_reclaim_continuation_15m_v1.md"
    ).read_text(encoding="utf-8") == "# user edited current packet\n"


def test_cli_write_review_packet_outputs_paths(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    try:
        exit_code = generator.main(
            [
                "--generate-candidates",
                "--write-review-packet",
                "--max-ideas",
                "1",
                "--timestamp",
                "cli_packet",
            ]
        )
    finally:
        generator.repo_root = original_repo_root

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "STRATEGY_CANDIDATE_REVIEW_PACKET_WRITTEN"
    assert payload["candidate_count"] == 1
    assert payload["candidate_files"] == [
        {
            "index": 1,
            "target_hypothesis_id": "opening_drive_followthrough_5m_v1",
            "markdown_path": (
                "reports/pipeline_audit/strategy_candidate_ideation/"
                "001_opening_drive_followthrough_5m_v1.md"
            ),
            "json_path": (
                "reports/pipeline_audit/strategy_candidate_ideation/"
                "001_opening_drive_followthrough_5m_v1.json"
            ),
        }
    ]
    assert "Review directory:" in captured.err
    assert "Written candidate files:" in captured.err
    assert "001_opening_drive_followthrough_5m_v1.md" in captured.err
    assert "001_opening_drive_followthrough_5m_v1.json" in captured.err


def test_cli_write_review_packet_prints_archive_notice(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    _write_unmarked_pair(tmp_path, "001_opening_drive_followthrough_5m_v1")
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    try:
        exit_code = generator.main(
            [
                "--generate-candidates",
                "--write-review-packet",
                "--max-ideas",
                "1",
                "--timestamp",
                "cli_archive",
            ]
        )
    finally:
        generator.repo_root = original_repo_root

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["archive"]["archive_dir"] == (
        "reports/pipeline_audit/strategy_candidate_ideation/_archive/cli_archive"
    )
    assert "Archive directory:" in captured.err
    assert "Archived candidate files:" in captured.err
    assert "001_opening_drive_followthrough_5m_v1.md" in captured.err
    assert "001_opening_drive_followthrough_5m_v1.json" in captured.err


def test_cli_select_implementation_valid_selection_keeps_stdout_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
    try:
        exit_code = generator.main(
            [
                "--generate-candidates",
                "--write-review-packet",
                "--select-implementation",
                "--max-ideas",
                "1",
                "--timestamp",
                "cli_select",
            ]
        )
    finally:
        generator.repo_root = original_repo_root

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "STRATEGY_CANDIDATE_REVIEW_PACKET_WRITTEN"
    assert payload["implementation_selection"]["status"] == "READY"
    assert payload["implementation_selection"]["selection_path"] == (
        "reports/pipeline_audit/strategy_candidate_ideation/implementation_selection.json"
    )
    assert "Type candidate numbers" in captured.err
    assert "Implementation selection:" in captured.err
    assert "opening_drive_followthrough_5m_v1" in captured.err
    assert (tmp_path / payload["implementation_selection"]["selection_path"]).exists()


def test_cli_select_implementation_skip_and_eof_do_not_write_selection(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    monkeypatch.setattr(sys, "stdin", io.StringIO("skip\n"))
    try:
        skip_exit_code = generator.main(
            [
                "--generate-candidates",
                "--write-review-packet",
                "--select-implementation",
                "--max-ideas",
                "1",
                "--timestamp",
                "cli_skip",
            ]
        )
        skip_captured = capsys.readouterr()
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        eof_exit_code = generator.main(
            [
                "--generate-candidates",
                "--write-review-packet",
                "--select-implementation",
                "--max-ideas",
                "1",
                "--timestamp",
                "cli_eof",
            ]
        )
    finally:
        generator.repo_root = original_repo_root

    eof_captured = capsys.readouterr()
    skip_payload = json.loads(skip_captured.out)
    eof_payload = json.loads(eof_captured.out)
    assert skip_exit_code == 0
    assert eof_exit_code == 0
    assert skip_payload["implementation_selection"]["status"] == "SKIPPED"
    assert eof_payload["implementation_selection"]["status"] == "SKIPPED"
    assert "Implementation selection skipped." in skip_captured.err
    assert "Implementation selection skipped." in eof_captured.err
    assert not (
        tmp_path
        / "reports"
        / "pipeline_audit"
        / "strategy_candidate_ideation"
        / generator.IMPLEMENTATION_SELECTION_FILENAME
    ).exists()


def test_cli_select_implementation_invalid_returns_nonzero_after_review_packet(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    monkeypatch.setattr(sys, "stdin", io.StringIO("9\n"))
    try:
        exit_code = generator.main(
            [
                "--generate-candidates",
                "--write-review-packet",
                "--select-implementation",
                "--max-ideas",
                "1",
                "--timestamp",
                "cli_invalid",
            ]
        )
    finally:
        generator.repo_root = original_repo_root

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["status"] == "STRATEGY_CANDIDATE_REVIEW_PACKET_WRITTEN"
    assert payload["implementation_selection"]["status"] == "FAILED"
    assert "out of range" in payload["implementation_selection"]["failure"]
    assert "Implementation selection failed" in captured.err
    assert (tmp_path / payload["candidate_files"][0]["json_path"]).exists()
    assert not (
        tmp_path
        / "reports"
        / "pipeline_audit"
        / "strategy_candidate_ideation"
        / generator.IMPLEMENTATION_SELECTION_FILENAME
    ).exists()


def test_cli_select_implementation_all_and_custom_review_root(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _write_json(tmp_path / generator.CANONICAL_REGISTRY, {"schema_version": 1, "hypotheses": []})
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    monkeypatch.setattr(sys, "stdin", io.StringIO("all\n"))
    try:
        exit_code = generator.main(
            [
                "--generate-candidates",
                "--write-review-packet",
                "--select-implementation",
                "--max-ideas",
                "2",
                "--review-root",
                "reports/custom_ideation",
                "--timestamp",
                "cli_all",
            ]
        )
    finally:
        generator.repo_root = original_repo_root

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["output_dir"] == "reports/custom_ideation"
    assert payload["implementation_selection"]["status"] == "READY"
    assert payload["implementation_selection"]["selected_candidate_count"] == 2
    assert payload["implementation_selection"]["selection_path"] == (
        "reports/custom_ideation/implementation_selection.json"
    )
    assert (tmp_path / payload["implementation_selection"]["selection_path"]).exists()


def test_cli_select_implementation_gating_failures(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_inputs(tmp_path, [CANDIDATE_A])
    spec_path = _write_spec(tmp_path, [{"id": CANDIDATE_A, "run": "batch_a"}])
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    try:
        with_spec = generator.main(
            [
                "--generate-candidates",
                "--spec",
                spec_path.as_posix(),
                "--select-implementation",
            ]
        )
        with_spec_captured = capsys.readouterr()
        without_review = generator.main(["--generate-candidates", "--select-implementation"])
        without_review_captured = capsys.readouterr()
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
        self_check = generator.main(
            [
                "--self-check",
                "--select-implementation",
                "--launcher-path",
                str(tmp_path / generator.IDEATION_LAUNCHER_NAME),
            ]
        )
    finally:
        generator.repo_root = original_repo_root

    self_check_captured = capsys.readouterr()
    assert with_spec == 1
    assert without_review == 1
    assert self_check == 1
    assert "--spec cannot be combined" in with_spec_captured.err
    assert "--select-implementation requires --write-review-packet" in without_review_captured.err
    assert "--select-implementation cannot be combined with --self-check" in self_check_captured.err


def test_spec_cannot_be_combined_with_review_packet(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _prepare_inputs(tmp_path, [CANDIDATE_A])
    spec_path = _write_spec(tmp_path, [{"id": CANDIDATE_A, "run": "batch_a"}])
    original_repo_root = generator.repo_root
    generator.repo_root = lambda: tmp_path
    try:
        exit_code = generator.main(
            [
                "--generate-candidates",
                "--spec",
                spec_path.as_posix(),
                "--write-review-packet",
            ]
        )
    finally:
        generator.repo_root = original_repo_root

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--spec cannot be combined" in captured.err


def test_ideation_launcher_self_check_passes_for_matching_template(tmp_path: Path) -> None:
    launcher = tmp_path / generator.IDEATION_LAUNCHER_NAME
    _write_ideation_launcher(launcher)

    result = generator.ideation_launcher_self_check(root=tmp_path, launcher_path=launcher)

    assert result["status"] == "IDEATION_LAUNCHER_SELF_CHECK_PASS"
    assert result["static_check_only"] is True
    assert result["default_route"] == (
        "scripts.validation.generate_alpha_discovery_candidates --write-review-packet --select-implementation"
    )


def test_ideation_launcher_self_check_rejects_non_repo_launcher(tmp_path: Path) -> None:
    template = tmp_path / generator.IDEATION_LAUNCHER_NAME
    outside_launcher = tmp_path.parent / generator.IDEATION_LAUNCHER_NAME
    _write_ideation_launcher(template)
    outside_launcher.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(generator.GeneratorError, match="only the repo-local ideation launcher"):
        generator.ideation_launcher_self_check(root=tmp_path, launcher_path=outside_launcher)


def test_missing_canonical_registry_entry_fails_closed(tmp_path: Path) -> None:
    _prepare_inputs(tmp_path, [])
    spec_path = _write_spec(tmp_path, [{"id": CANDIDATE_A, "run": "batch_a"}])

    with pytest.raises(generator.GeneratorError, match="canonical registry entry"):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)


@pytest.mark.parametrize(
    ("registry", "match"),
    [
        (_registry([CANDIDATE_A], status="REJECTED"), "status must be CANDIDATE"),
        (_registry([CANDIDATE_A], wfa_allowed=True), "wfa_allowed must be false"),
        (
            _registry([CANDIDATE_A], source_reports=["reports/pipeline_audit/stale.json"]),
            "source_reports must be empty",
        ),
    ],
)
def test_registry_candidate_readiness_failures_block_generation(
    tmp_path: Path,
    registry: dict[str, Any],
    match: str,
) -> None:
    _prepare_inputs(tmp_path, [CANDIDATE_A], registry=registry)
    spec_path = _write_spec(tmp_path, [{"id": CANDIDATE_A, "run": "batch_a"}])

    with pytest.raises(generator.GeneratorError, match=match):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)


@pytest.mark.parametrize(
    ("trial_statuses", "match"),
    [
        (
            _trial_statuses([CANDIDATE_A], status="DISCOVERY_PASS"),
            "latest trial status must be CANDIDATE",
        ),
        (
            _trial_statuses([CANDIDATE_A], stage="phase9_discovery_smoke"),
            "latest trial stage must be register_candidate",
        ),
        (
            _trial_statuses([CANDIDATE_A], evidence=["reports/pipeline_audit/stale.json"]),
            "latest trial evidence must be empty",
        ),
    ],
)
def test_trial_status_readiness_failures_block_generation(
    tmp_path: Path,
    trial_statuses: str,
    match: str,
) -> None:
    _prepare_inputs(tmp_path, [CANDIDATE_A], trial_statuses=trial_statuses)
    spec_path = _write_spec(tmp_path, [{"id": CANDIDATE_A, "run": "batch_a"}])

    with pytest.raises(generator.GeneratorError, match=match):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)


def test_noncanonical_template_registry_path_fails_closed(tmp_path: Path) -> None:
    template = _template_config()
    template["target_registry"] = "configs/smoke_registry.json"
    _prepare_inputs(tmp_path, [CANDIDATE_A], template=template)
    spec_path = _write_spec(tmp_path, [{"id": CANDIDATE_A, "run": "batch_a"}])

    with pytest.raises(generator.GeneratorError, match="target_registry"):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)


def test_candidate_must_be_supported_by_target_smoke_harness(tmp_path: Path) -> None:
    candidate_id = "not_a_target_spec_v1"
    _prepare_inputs(tmp_path, [candidate_id])
    spec_path = _write_spec(tmp_path, [{"id": candidate_id, "run": "batch_a"}])

    with pytest.raises(generator.GeneratorError, match="not supported by the ES 30m"):
        generator.generate_from_spec(spec_path=spec_path, root=tmp_path)
