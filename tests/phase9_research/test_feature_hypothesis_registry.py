from __future__ import annotations

import json
from pathlib import Path

from scripts.phase9_research.feature_hypothesis_registry import (
    ALLOWED_STATUSES,
    main,
    register_candidate,
    validate_registry,
    validate_trial_statuses,
)


def _write_feature_set(path: Path, *, status: str = "FROZEN", allowed: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "feature_set_id": "fixture_set",
                "status": status,
                "allowed_for_wfa": allowed,
                "feature_count": 1,
                "features": ["feature_signal"],
            }
        ),
        encoding="utf-8",
    )
    return path


def _registry_payload(feature_set: Path) -> dict[str, object]:
    return {
        "schema_version": 1,
        "allowed_statuses": list(ALLOWED_STATUSES),
        "wfa_allowed_statuses": ["FROZEN"],
        "allowed_transitions": {
            "CANDIDATE": ["DISCOVERY_PASS", "REJECTED", "QUARANTINED"],
            "DISCOVERY_PASS": ["CONFIRMATION_PASS", "REJECTED", "QUARANTINED"],
            "CONFIRMATION_PASS": ["FROZEN", "REJECTED", "QUARANTINED"],
            "FROZEN": ["RETIRED", "QUARANTINED"],
            "REJECTED": [],
            "RETIRED": [],
            "QUARANTINED": [],
        },
        "hypotheses": [
            {
                "hypothesis_id": "fixture_hypothesis",
                "status": "FROZEN",
                "wfa_allowed": True,
                "feature_set_manifest": feature_set.as_posix(),
                "feature_family": "fixture",
                "scope": {
                    "profile": "tier_1",
                    "markets": ["ES"],
                    "years": [2024],
                },
                "description": "fixture description",
                "status_reason": "fixture frozen status",
                "source_reports": [],
                "next_allowed_actions": ["WFA_WITH_FEATURE_SET"],
            }
        ],
    }


def _write_registry(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_trials(path: Path, *, hypothesis_id: str = "fixture_hypothesis") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "trial_id": "fixture_trial",
                "hypothesis_id": hypothesis_id,
                "status": "FROZEN",
                "stage": "freeze",
                "evidence": ["fixture"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_repo_feature_hypothesis_registry_is_valid() -> None:
    assert validate_registry() == []
    assert validate_trial_statuses() == []


def test_valid_fixture_registry_and_trials_pass(tmp_path: Path) -> None:
    feature_set = _write_feature_set(tmp_path / "manifests" / "feature_sets" / "fixture.json")
    registry = _write_registry(
        tmp_path / "manifests" / "feature_hypotheses" / "registry.json",
        _registry_payload(feature_set),
    )
    trials = _write_trials(tmp_path / "manifests" / "feature_hypotheses" / "trial_statuses.jsonl")

    assert validate_registry(registry) == []
    assert validate_trial_statuses(trials, registry) == []


def test_registry_rejects_unknown_status(tmp_path: Path) -> None:
    feature_set = _write_feature_set(tmp_path / "manifests" / "feature_sets" / "fixture.json")
    payload = _registry_payload(feature_set)
    payload["hypotheses"][0]["status"] = "MAYBE"  # type: ignore[index]
    registry = _write_registry(tmp_path / "registry.json", payload)

    errors = validate_registry(registry)

    assert any("unknown status" in error for error in errors)


def test_registry_rejects_non_frozen_wfa_allowed(tmp_path: Path) -> None:
    feature_set = _write_feature_set(tmp_path / "manifests" / "feature_sets" / "fixture.json")
    payload = _registry_payload(feature_set)
    payload["hypotheses"][0]["status"] = "DISCOVERY_PASS"  # type: ignore[index]
    registry = _write_registry(tmp_path / "registry.json", payload)

    errors = validate_registry(registry)

    assert any("wfa_allowed requires FROZEN status" in error for error in errors)


def test_registry_rejects_frozen_without_feature_set_manifest(tmp_path: Path) -> None:
    feature_set = _write_feature_set(tmp_path / "manifests" / "feature_sets" / "fixture.json")
    payload = _registry_payload(feature_set)
    del payload["hypotheses"][0]["feature_set_manifest"]  # type: ignore[index]
    registry = _write_registry(tmp_path / "registry.json", payload)

    errors = validate_registry(registry)

    assert any("FROZEN status requires feature_set_manifest" in error for error in errors)


def test_trials_reject_unknown_hypothesis(tmp_path: Path) -> None:
    feature_set = _write_feature_set(tmp_path / "manifests" / "feature_sets" / "fixture.json")
    registry = _write_registry(tmp_path / "registry.json", _registry_payload(feature_set))
    trials = _write_trials(tmp_path / "trial_statuses.jsonl", hypothesis_id="missing")

    errors = validate_trial_statuses(trials, registry)

    assert any("unknown hypothesis_id" in error for error in errors)


def test_register_candidate_appends_registry_and_trial_event(tmp_path: Path) -> None:
    feature_set = _write_feature_set(tmp_path / "manifests" / "feature_sets" / "fixture.json")
    registry = _write_registry(
        tmp_path / "manifests" / "feature_hypotheses" / "registry.json",
        _registry_payload(feature_set),
    )
    trials = _write_trials(tmp_path / "manifests" / "feature_hypotheses" / "trial_statuses.jsonl")

    errors = register_candidate(
        registry_path=registry,
        trial_statuses_path=trials,
        hypothesis_id="new_candidate",
        description="new candidate description",
        feature_family="new_family",
        profile="tier_1",
        resolved_profile="tier_1_research",
        markets=["ES", "CL"],
        years=[2023, 2024],
    )

    payload = json.loads(registry.read_text(encoding="utf-8"))
    candidate = payload["hypotheses"][-1]
    events = [
        json.loads(line)
        for line in trials.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert errors == []
    assert candidate["hypothesis_id"] == "new_candidate"
    assert candidate["status"] == "CANDIDATE"
    assert candidate["wfa_allowed"] is False
    assert candidate["scope"]["markets"] == ["ES", "CL"]
    assert events[-1]["trial_id"] == "new_candidate_candidate"
    assert events[-1]["status"] == "CANDIDATE"
    assert validate_registry(registry) == []
    assert validate_trial_statuses(trials, registry) == []


def test_register_candidate_rejects_duplicate_without_writing(tmp_path: Path) -> None:
    feature_set = _write_feature_set(tmp_path / "manifests" / "feature_sets" / "fixture.json")
    registry = _write_registry(
        tmp_path / "manifests" / "feature_hypotheses" / "registry.json",
        _registry_payload(feature_set),
    )
    trials = _write_trials(tmp_path / "manifests" / "feature_hypotheses" / "trial_statuses.jsonl")
    before_registry = registry.read_text(encoding="utf-8")
    before_trials = trials.read_text(encoding="utf-8")

    errors = register_candidate(
        registry_path=registry,
        trial_statuses_path=trials,
        hypothesis_id="fixture_hypothesis",
        description="duplicate",
        feature_family="duplicate",
        profile="tier_1",
        resolved_profile="tier_1_research",
        markets=["ES"],
        years=[2024],
    )

    assert any("duplicate hypothesis_id" in error for error in errors)
    assert registry.read_text(encoding="utf-8") == before_registry
    assert trials.read_text(encoding="utf-8") == before_trials


def test_register_candidate_cli_writes_candidate(tmp_path: Path) -> None:
    feature_set = _write_feature_set(tmp_path / "manifests" / "feature_sets" / "fixture.json")
    registry = _write_registry(
        tmp_path / "manifests" / "feature_hypotheses" / "registry.json",
        _registry_payload(feature_set),
    )
    trials = _write_trials(tmp_path / "manifests" / "feature_hypotheses" / "trial_statuses.jsonl")

    exit_code = main(
        [
            "register-candidate",
            "--registry",
            registry.as_posix(),
            "--trial-statuses",
            trials.as_posix(),
            "--hypothesis-id",
            "cli_candidate",
            "--description",
            "CLI candidate description",
            "--feature-family",
            "cli_family",
            "--markets",
            "ES,CL,ZN,6E",
            "--years",
            "2023,2024",
        ]
    )

    payload = json.loads(registry.read_text(encoding="utf-8"))
    candidate = payload["hypotheses"][-1]

    assert exit_code == 0
    assert candidate["hypothesis_id"] == "cli_candidate"
    assert candidate["status"] == "CANDIDATE"
    assert candidate["scope"]["markets"] == ["ES", "CL", "ZN", "6E"]
    assert candidate["scope"]["years"] == [2023, 2024]
    assert validate_trial_statuses(trials, registry) == []
