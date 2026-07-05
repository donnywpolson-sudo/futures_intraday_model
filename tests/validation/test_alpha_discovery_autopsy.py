from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import alpha_discovery_autopsy as autopsy


def _queue_result(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": "QUEUE_COMPLETED",
        "summary": {"candidate_count": len(rows)},
        "results": rows,
    }


def test_autopsy_records_safe_preflight_summary(tmp_path: Path) -> None:
    result = autopsy.write_autopsy(
        root=tmp_path,
        batch_id="batch_a",
        queue_result=_queue_result(
            [
                {
                    "candidate_id": "candidate_a",
                    "config": "configs/candidate_a.json",
                    "mode": "preflight",
                    "status": "CANDIDATE_COMPLETED",
                    "runner_status": "PREFLIGHT_PASS",
                }
            ]
        ),
    )

    payload = json.loads((tmp_path / result["json_path"]).read_text(encoding="utf-8"))
    assert payload["report_stamp"] == autopsy.SAFE_REPORT_STAMP
    assert payload["aggregate_bias_warning"] == autopsy.AGGREGATE_BIAS_WARNING
    candidate = payload["candidates"][0]
    assert candidate["decision"] == "PREFLIGHT_READY"
    assert candidate["allowed_next_action"] == "STOP"
    assert candidate["derived_followup_blocked"] is True


def test_discovery_pass_is_only_confirmation_plan_action() -> None:
    payload = autopsy.build_autopsy(
        batch_id="batch_a",
        queue_result=_queue_result(
            [
                {
                    "candidate_id": "candidate_a",
                    "config": "configs/candidate_a.json",
                    "mode": "discovery-run",
                    "status": "CANDIDATE_COMPLETED",
                    "runner_status": "DISCOVERY_RUN_CANDIDATE_DISCOVERY_PASS",
                },
                {
                    "candidate_id": "candidate_b",
                    "config": "configs/candidate_b.json",
                    "mode": "discovery-run",
                    "status": "CANDIDATE_COMPLETED",
                    "runner_status": "DISCOVERY_RUN_CANDIDATE_STOPPED",
                },
            ]
        ),
    )

    by_id = {item["candidate_id"]: item for item in payload["candidates"]}
    assert by_id["candidate_a"]["allowed_next_action"] == "PREPARE_SEPARATE_CONFIRMATION_PLAN"
    assert by_id["candidate_a"]["derived_followup_blocked"] is False
    assert by_id["candidate_b"]["allowed_next_action"] == "STOP"
    assert by_id["candidate_b"]["derived_followup_blocked"] is True


@pytest.mark.parametrize(
    "text",
    [
        "alpha ready",
        "near pass",
        "paper ready",
        "approved for WFA",
        "promising failure",
    ],
)
def test_forbidden_report_wording_fails(text: str) -> None:
    with pytest.raises(autopsy.AutopsyError):
        autopsy.validate_safe_text(text)


def test_failed_candidates_are_sorted_by_id_not_scores() -> None:
    payload = autopsy.build_autopsy(
        batch_id="batch_a",
        queue_result=_queue_result(
            [
                {
                    "candidate_id": "candidate_z",
                    "config": "configs/candidate_z.json",
                    "status": "CANDIDATE_FAILED",
                    "failure": "failed",
                },
                {
                    "candidate_id": "candidate_a",
                    "config": "configs/candidate_a.json",
                    "status": "CANDIDATE_FAILED",
                    "failure": "failed",
                },
            ]
        ),
    )

    assert [item["candidate_id"] for item in payload["candidates"]] == [
        "candidate_a",
        "candidate_z",
    ]
