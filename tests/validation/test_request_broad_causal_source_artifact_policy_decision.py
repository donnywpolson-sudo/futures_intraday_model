from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import request_broad_causal_source_artifact_policy_decision as request


def _row(pair: str) -> dict[str, object]:
    market, year_text = pair.split(":")
    return {
        "pair": pair,
        "market": market,
        "year": int(year_text),
        "source_file": f"data/dbn/ohlcv_1m_parent/{market}/{year_text}/source.dbn.zst",
        "planned_input_raw_path": f"data/raw/{market}/{year_text}.parquet",
        "raw_parquet_sha256": f"raw-{pair}",
        "raw_parquet_row_count": 10,
        "input_disposition_status": "blocked_missing_current_source_artifact",
        "source_file_present": False,
        "current_source_hash_matches": None,
        "policy_decision": request.EXPECTED_CURRENT_DECISION,
        "policy_status": "ACTION_REQUIRED",
        "approved_action": "none",
        "blockers": ["current source artifact missing"],
    }


def _policy(rows: list[dict[str, object]]) -> dict[str, object]:
    pairs = sorted(str(row["pair"]) for row in rows)
    return {
        "summary": {
            "stage": request.EXPECTED_INPUT_STAGE,
            "status": "ACTION_REQUIRED",
            "decision": request.EXPECTED_CURRENT_DECISION,
            "pair_count": len(rows),
            "pairs": pairs,
            "data_mutation_performed": False,
            "build_approved": False,
            "restore_approved": False,
            "repair_approved": False,
            "exclusion_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
            "source_action_approved": False,
        },
        "rows": rows,
    }


def _valid_rows() -> list[dict[str, object]]:
    return [_row("SR1:2020"), _row("SR3:2020")]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_valid_policy_produces_human_decision_request(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    _write_json(policy_path, _policy(_valid_rows()))

    report = request.build_report(
        repo_root=tmp_path,
        policy_path=policy_path,
        generated_at_utc="2026-06-29T00:00:00Z",
    )

    assert report["summary"]["stage"] == request.OUTPUT_STAGE
    assert report["summary"]["status"] == request.OUTPUT_STATUS
    assert report["summary"]["selected_decision_option"] is None
    assert report["summary"]["approved_action"] == "none"
    assert report["summary"]["source_action_approved"] is False
    assert report["summary"]["requested_decision_options"] == request.REQUESTED_DECISION_OPTIONS
    assert {row["pair"] for row in report["rows"]} == {"SR1:2020", "SR3:2020"}


def test_unexpected_pair_fails_closed(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    _write_json(policy_path, _policy([_row("SR1:2020"), _row("ES:2020")]))

    with pytest.raises(ValueError, match="summary.pairs"):
        request.build_report(repo_root=tmp_path, policy_path=policy_path)


def test_selected_or_approved_action_fails_closed(tmp_path: Path) -> None:
    payload = _policy(_valid_rows())
    payload["rows"][0]["approved_action"] = "repair"  # type: ignore[index]
    policy_path = tmp_path / "policy.json"
    _write_json(policy_path, payload)

    with pytest.raises(ValueError, match="approved_action"):
        request.build_report(repo_root=tmp_path, policy_path=policy_path)


def test_changed_policy_decision_fails_closed(tmp_path: Path) -> None:
    payload = _policy(_valid_rows())
    payload["summary"]["decision"] = "approve_policy_exclusion_deferment_plan"  # type: ignore[index]
    policy_path = tmp_path / "policy.json"
    _write_json(policy_path, payload)

    with pytest.raises(ValueError, match="summary.decision"):
        request.build_report(repo_root=tmp_path, policy_path=policy_path)


def test_true_approval_flag_fails_closed(tmp_path: Path) -> None:
    payload = _policy(_valid_rows())
    payload["summary"]["source_action_approved"] = True  # type: ignore[index]
    policy_path = tmp_path / "policy.json"
    _write_json(policy_path, payload)

    with pytest.raises(ValueError, match="summary.source_action_approved"):
        request.build_report(repo_root=tmp_path, policy_path=policy_path)


def test_write_report_outputs_options_and_non_approval_text(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    _write_json(policy_path, _policy(_valid_rows()))
    report = request.build_report(repo_root=tmp_path, policy_path=policy_path)
    json_out = tmp_path / "out" / "request.json"
    md_out = tmp_path / "out" / "request.md"

    request.write_report(report, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["status"] == request.OUTPUT_STATUS
    assert payload["summary"]["selected_decision_option"] is None
    assert "approve_separate_source_repair_restore_plan" in markdown
    assert "approve_policy_exclusion_deferment_plan" in markdown
    assert "continue_block_no_action" in markdown
    assert "SR1:2020" in markdown
    assert "SR3:2020" in markdown
    assert "does not approve data mutation" in markdown
