from __future__ import annotations

import json
import subprocess
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
        "approval_token": "APPROVE_ALPHA_DISCOVERY_DISCOVERY_RUN_V1",
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
