from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.validation import run_alpha_discovery as single_runner
from scripts.validation import run_alpha_discovery_queue as queue_runner


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _write_candidate_config(root: Path, candidate_id: str) -> Path:
    return _write_json(
        root / "configs" / f"alpha_discovery_runner.{candidate_id}.json",
        {
            "schema_version": 1,
            "hypothesis_id": candidate_id,
        },
    )


def _write_queue(root: Path, candidates: list[dict[str, Any]], **overrides: Any) -> Path:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "runner_mode": "preflight",
        "log_root": "logs/alpha_discovery_queue_test",
        "candidates": candidates,
    }
    payload.update(overrides)
    return _write_json(root / "configs" / "alpha_discovery_queue.test.json", payload)


def _entry(candidate_id: str, *, approved: bool = False) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "config": f"configs/alpha_discovery_runner.{candidate_id}.json",
        "approved": approved,
    }


def test_queue_runs_one_candidate_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_candidate_config(tmp_path, "candidate_1")
    queue_path = _write_queue(tmp_path, [_entry("candidate_1")])

    def fake_run_mode(
        config: dict[str, Any],
        *,
        root: Path,
        mode: str,
        approval_token: str | None,
    ) -> dict[str, Any]:
        assert config["hypothesis_id"] == "candidate_1"
        assert mode == "preflight"
        assert approval_token is None
        return {"status": "PREFLIGHT_PASS"}

    monkeypatch.setattr(single_runner, "run_mode", fake_run_mode)

    result = queue_runner.run_queue(
        queue_path=queue_path,
        root=tmp_path,
        mode_override=None,
        approval_token=None,
        approve_discovery_run=False,
    )

    assert result["status"] == "QUEUE_COMPLETED"
    assert result["summary"]["candidate_completed_count"] == 1
    assert result["results"][0]["runner_status"] == "PREFLIGHT_PASS"


def test_queue_simulates_hundreds_of_candidates_serially(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    count = 125
    candidates = []
    seen: list[str] = []
    for index in range(count):
        candidate_id = f"candidate_{index:03d}"
        _write_candidate_config(tmp_path, candidate_id)
        candidates.append(_entry(candidate_id))
    queue_path = _write_queue(tmp_path, candidates, max_candidates=200)

    def fake_run_mode(
        config: dict[str, Any],
        *,
        root: Path,
        mode: str,
        approval_token: str | None,
    ) -> dict[str, Any]:
        seen.append(str(config["hypothesis_id"]))
        return {"status": "PREFLIGHT_PASS"}

    monkeypatch.setattr(single_runner, "run_mode", fake_run_mode)

    result = queue_runner.run_queue(
        queue_path=queue_path,
        root=tmp_path,
        mode_override="preflight",
        approval_token=None,
        approve_discovery_run=False,
    )

    assert result["status"] == "QUEUE_COMPLETED"
    assert result["summary"]["candidate_count"] == count
    assert seen == [f"candidate_{index:03d}" for index in range(count)]


def test_duplicate_candidate_ids_fail_closed(tmp_path: Path) -> None:
    _write_candidate_config(tmp_path, "candidate_1")
    queue_path = _write_queue(tmp_path, [_entry("candidate_1"), _entry("candidate_1")])

    with pytest.raises(queue_runner.QueueError, match="duplicate candidate id"):
        queue_runner.run_queue(
            queue_path=queue_path,
            root=tmp_path,
            mode_override=None,
            approval_token=None,
            approve_discovery_run=False,
        )


def test_missing_candidate_config_path_fails_closed(tmp_path: Path) -> None:
    queue_path = _write_queue(tmp_path, [_entry("missing_candidate")])

    with pytest.raises(queue_runner.QueueError, match="missing config path"):
        queue_runner.run_queue(
            queue_path=queue_path,
            root=tmp_path,
            mode_override=None,
            approval_token=None,
            approve_discovery_run=False,
        )


def test_discovery_run_requires_approved_queue_entries(tmp_path: Path) -> None:
    _write_candidate_config(tmp_path, "candidate_1")
    queue_path = _write_queue(tmp_path, [_entry("candidate_1", approved=False)])

    with pytest.raises(queue_runner.QueueError, match="unapproved candidates"):
        queue_runner.run_queue(
            queue_path=queue_path,
            root=tmp_path,
            mode_override="discovery-run",
            approval_token="APPROVE_ALPHA_DISCOVERY_DISCOVERY_RUN_V1",
            approve_discovery_run=True,
        )


def test_wrong_discovery_approval_token_is_infrastructure_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_candidate_config(tmp_path, "candidate_1")
    queue_path = _write_queue(tmp_path, [_entry("candidate_1", approved=True)])

    def fake_run_mode(
        config: dict[str, Any],
        *,
        root: Path,
        mode: str,
        approval_token: str | None,
    ) -> dict[str, Any]:
        assert approval_token == "WRONG"
        raise single_runner.RunnerError("discovery-run requires the exact configured approval token")

    monkeypatch.setattr(single_runner, "run_mode", fake_run_mode)

    result = queue_runner.run_queue(
        queue_path=queue_path,
        root=tmp_path,
        mode_override="discovery-run",
        approval_token="WRONG",
        approve_discovery_run=True,
    )

    assert result["status"] == "QUEUE_INFRASTRUCTURE_FAILURE"
    assert result["summary"]["infrastructure_failure_count"] == 1


def test_candidate_failure_continues_to_next_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_candidate_config(tmp_path, "candidate_1")
    _write_candidate_config(tmp_path, "candidate_2")
    queue_path = _write_queue(tmp_path, [_entry("candidate_1"), _entry("candidate_2")])

    def fake_run_mode(
        config: dict[str, Any],
        *,
        root: Path,
        mode: str,
        approval_token: str | None,
    ) -> dict[str, Any]:
        if config["hypothesis_id"] == "candidate_1":
            raise single_runner.RunnerError(
                "registry status for 'candidate_1' is 'FROZEN'; discovery runner requires a CANDIDATE"
            )
        return {"status": "PREFLIGHT_PASS"}

    monkeypatch.setattr(single_runner, "run_mode", fake_run_mode)

    result = queue_runner.run_queue(
        queue_path=queue_path,
        root=tmp_path,
        mode_override="preflight",
        approval_token=None,
        approve_discovery_run=False,
    )

    assert result["status"] == "QUEUE_COMPLETED_WITH_CANDIDATE_FAILURES"
    assert [row["status"] for row in result["results"]] == [
        "CANDIDATE_FAILED",
        "CANDIDATE_COMPLETED",
    ]


def test_infrastructure_failure_stops_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_candidate_config(tmp_path, "candidate_1")
    _write_candidate_config(tmp_path, "candidate_2")
    queue_path = _write_queue(tmp_path, [_entry("candidate_1"), _entry("candidate_2")])

    def fake_run_mode(
        config: dict[str, Any],
        *,
        root: Path,
        mode: str,
        approval_token: str | None,
    ) -> dict[str, Any]:
        raise single_runner.RunnerError(
            "expected generated outputs are not ignored by git: ['reports/not_ignored.json']"
        )

    monkeypatch.setattr(single_runner, "run_mode", fake_run_mode)

    result = queue_runner.run_queue(
        queue_path=queue_path,
        root=tmp_path,
        mode_override="preflight",
        approval_token=None,
        approve_discovery_run=False,
    )

    assert result["status"] == "QUEUE_INFRASTRUCTURE_FAILURE"
    assert len(result["results"]) == 1


def test_summary_json_and_jsonl_are_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_candidate_config(tmp_path, "candidate_1")
    queue_path = _write_queue(tmp_path, [_entry("candidate_1")])

    def fake_run_mode(
        config: dict[str, Any],
        *,
        root: Path,
        mode: str,
        approval_token: str | None,
    ) -> dict[str, Any]:
        return {"status": "PREFLIGHT_PASS"}

    monkeypatch.setattr(single_runner, "run_mode", fake_run_mode)

    result = queue_runner.run_queue(
        queue_path=queue_path,
        root=tmp_path,
        mode_override="preflight",
        approval_token=None,
        approve_discovery_run=False,
    )
    summary_path = tmp_path / result["summary_log_path"]
    row_log_path = tmp_path / result["row_log_path"]

    assert summary_path.exists()
    assert row_log_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["status"] == "QUEUE_COMPLETED"
    assert len(row_log_path.read_text(encoding="utf-8").splitlines()) == 1


def test_bad_mode_fails_closed(tmp_path: Path) -> None:
    _write_candidate_config(tmp_path, "candidate_1")
    queue_path = _write_queue(tmp_path, [_entry("candidate_1")], runner_mode="not-a-mode")

    with pytest.raises(queue_runner.QueueError, match="unsupported mode"):
        queue_runner.run_queue(
            queue_path=queue_path,
            root=tmp_path,
            mode_override=None,
            approval_token=None,
            approve_discovery_run=False,
        )
