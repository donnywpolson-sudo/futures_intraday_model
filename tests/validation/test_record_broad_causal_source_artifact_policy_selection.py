from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import record_broad_causal_source_artifact_policy_selection as selection


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
        "current_policy_decision": selection.CURRENT_DECISION,
        "current_policy_status": "ACTION_REQUIRED",
        "input_disposition_status": "blocked_missing_current_source_artifact",
        "source_file_present": False,
        "current_approved_action": "none",
        "requested_decision_options": selection.REQUESTED_DECISION_OPTIONS,
        "selected_decision_option": None,
        "approved_action": "none",
        "decision_required": True,
        "blockers": ["current source artifact missing"],
    }


def _request(rows: list[dict[str, object]]) -> dict[str, object]:
    pairs = sorted(str(row["pair"]) for row in rows)
    return {
        "summary": {
            "stage": selection.EXPECTED_INPUT_STAGE,
            "status": selection.EXPECTED_INPUT_STATUS,
            "current_decision": selection.CURRENT_DECISION,
            "pair_count": len(rows),
            "pairs": pairs,
            "requested_decision_options": selection.REQUESTED_DECISION_OPTIONS,
            "selected_decision_option": None,
            "approved_action": "none",
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


def test_records_continue_block_no_action_selection(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    _write_json(request_path, _request(_valid_rows()))

    report = selection.build_report(
        repo_root=tmp_path,
        request_path=request_path,
        generated_at_utc="2026-06-29T00:00:00Z",
    )

    assert report["summary"]["stage"] == selection.OUTPUT_STAGE
    assert report["summary"]["status"] == "ACTION_REQUIRED"
    assert report["summary"]["selected_decision_option"] == selection.SELECTED_OPTION
    assert report["summary"]["human_decision_recorded"] is True
    assert report["summary"]["approved_action"] == "none"
    assert report["summary"]["source_action_approved"] is False
    assert {row["pair"] for row in report["rows"]} == {"SR1:2020", "SR3:2020"}


def test_unexpected_pair_fails_closed(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    _write_json(request_path, _request([_row("SR1:2020"), _row("ES:2020")]))

    with pytest.raises(ValueError, match="summary.pairs"):
        selection.build_report(repo_root=tmp_path, request_path=request_path)


def test_changed_requested_options_fails_closed(tmp_path: Path) -> None:
    payload = _request(_valid_rows())
    payload["summary"]["requested_decision_options"] = ["continue_block_no_action"]  # type: ignore[index]
    request_path = tmp_path / "request.json"
    _write_json(request_path, payload)

    with pytest.raises(ValueError, match="requested_decision_options"):
        selection.build_report(repo_root=tmp_path, request_path=request_path)


def test_preselected_option_fails_closed(tmp_path: Path) -> None:
    payload = _request(_valid_rows())
    payload["summary"]["selected_decision_option"] = selection.SELECTED_OPTION  # type: ignore[index]
    request_path = tmp_path / "request.json"
    _write_json(request_path, payload)

    with pytest.raises(ValueError, match="selected_decision_option"):
        selection.build_report(repo_root=tmp_path, request_path=request_path)


def test_non_none_approved_action_fails_closed(tmp_path: Path) -> None:
    payload = _request(_valid_rows())
    payload["rows"][0]["approved_action"] = "repair"  # type: ignore[index]
    request_path = tmp_path / "request.json"
    _write_json(request_path, payload)

    with pytest.raises(ValueError, match="approved_action"):
        selection.build_report(repo_root=tmp_path, request_path=request_path)


def test_true_approval_flag_fails_closed(tmp_path: Path) -> None:
    payload = _request(_valid_rows())
    payload["summary"]["source_action_approved"] = True  # type: ignore[index]
    request_path = tmp_path / "request.json"
    _write_json(request_path, payload)

    with pytest.raises(ValueError, match="summary.source_action_approved"):
        selection.build_report(repo_root=tmp_path, request_path=request_path)


def test_write_report_outputs_selection_and_non_approval_text(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    _write_json(request_path, _request(_valid_rows()))
    report = selection.build_report(repo_root=tmp_path, request_path=request_path)
    json_out = tmp_path / "out" / "selection.json"
    md_out = tmp_path / "out" / "selection.md"

    selection.write_report(report, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["selected_decision_option"] == selection.SELECTED_OPTION
    assert payload["summary"]["human_decision_recorded"] is True
    assert "continue_block_no_action" in markdown
    assert "human_decision_recorded" not in markdown
    assert "SR1:2020" in markdown
    assert "SR3:2020" in markdown
    assert "does not approve data mutation" in markdown
