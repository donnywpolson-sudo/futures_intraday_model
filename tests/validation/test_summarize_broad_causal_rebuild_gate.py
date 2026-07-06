from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import summarize_broad_causal_rebuild_gate as gate


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _prebuild_plan() -> dict[str, object]:
    rows = [
        _prebuild_row("ES", 2024, "action_required"),
        _prebuild_row("SR1", 2020, "action_required"),
        _prebuild_row("SR3", 2020, "action_required"),
        _prebuild_row("ES", 2025, "deferred_policy_review"),
        _prebuild_row("ES", 2026, "deferred_policy_review"),
    ]
    return {
        "summary": {
            "stage": gate.PREBUILD_STAGE,
            "status": "ACTION_REQUIRED",
            "decision": "rebuild_new_broad_root",
            "future_root": gate.FUTURE_ROOT,
            "expected_rows": len(rows),
            "status_counts": {
                "ready_for_build": 0,
                "deferred_policy_review": 2,
                "excluded_from_phase2": 0,
                "action_required": 3,
            },
            "research_use_allowed": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "legacy_restore_approved": False,
        },
        "rows": rows,
    }


def _prebuild_row(market: str, year: int, status: str) -> dict[str, object]:
    return {
        "market": market,
        "year": year,
        "pair": f"{market}:{year}",
        "planned_input_raw_path": f"data/raw/{market}/{year}.parquet",
        "planned_output_causal_path": f"{gate.FUTURE_ROOT}/{market}/{year}.parquet",
        "prebuild_status": status,
    }


def _ready_row(market: str, year: int) -> dict[str, object]:
    source_root = gate.SR_PARENT_SOURCE_ROOT if market in {"SR1", "SR3"} else "data/dbn/ohlcv_1m"
    return {
        **_prebuild_row(market, year, "action_required"),
        "raw_read_performed": True,
        "raw_path_present": True,
        "raw_parquet_sha256": "c" * 64,
        "raw_parquet_row_count": 100,
        "source_reference_count": 1,
        "source_references": [
            {
                "source_file": f"{source_root}/{market}/{year}/source.dbn.zst",
                "expected_sha256": "a" * 64,
                "actual_sha256": "a" * 64,
                "hash_matches": True,
                "source_present": True,
            }
        ],
        "blockers": [],
        "readiness_status": "ready_for_build_input_only",
    }


def _blocked_readiness_row(pair: str) -> dict[str, object]:
    market, year_text = pair.split(":")
    year = int(year_text)
    return {
        **_prebuild_row(market, year, "action_required"),
        "raw_read_performed": True,
        "raw_path_present": True,
        "raw_parquet_sha256": f"raw-{pair}",
        "raw_parquet_row_count": 10,
        "source_reference_count": 1,
        "source_references": [
            {
                "source_file": f"{gate.SR_PARENT_SOURCE_ROOT}/{market}/{year}/source.dbn.zst",
                "expected_sha256": "b" * 64,
                "actual_sha256": None,
                "hash_matches": False,
                "source_present": False,
            }
        ],
        "blockers": [f"source file missing: {gate.SR_PARENT_SOURCE_ROOT}/{market}/{year}/source.dbn.zst"],
        "readiness_status": gate.READINESS_SOURCE_FAILURE,
    }


def _deferred_row(market: str, year: int) -> dict[str, object]:
    return {
        **_prebuild_row(market, year, "deferred_policy_review"),
        "raw_read_performed": False,
        "raw_path_present": None,
        "raw_parquet_sha256": None,
        "raw_parquet_row_count": None,
        "source_reference_count": 0,
        "source_references": [],
        "blockers": ["row remains non-research until separately approved"],
        "readiness_status": "deferred_policy_review_not_checked",
    }


def _readiness_report() -> dict[str, object]:
    rows = [
        _ready_row("ES", 2024),
        _ready_row("SR1", 2020),
        _ready_row("SR3", 2020),
        _deferred_row("ES", 2025),
        _deferred_row("ES", 2026),
    ]
    return {
        "summary": {
            "stage": gate.READINESS_STAGE,
            "status": gate.READINESS_READY_STATUS,
            "future_root": gate.FUTURE_ROOT,
            "expected_rows": len(rows),
            "checked_action_required_rows": 3,
            "deferred_policy_review_rows": 2,
            "readiness_status_counts": {
                "ready_for_build_input_only": 3,
                "action_required_missing_raw": 0,
                "action_required_unreadable_raw": 0,
                "action_required_schema_or_metadata_failure": 0,
                gate.READINESS_SOURCE_FAILURE: 0,
                "deferred_policy_review_not_checked": 2,
                "excluded_from_phase2_not_checked": 0,
            },
            "data_mutation_performed": False,
            "build_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
        },
        "rows": rows,
    }


def _source_resolution() -> dict[str, object]:
    repairs = [_repair_row("SR1:2020"), _repair_row("SR3:2020")]
    return {
        "stage": gate.SOURCE_RESOLUTION_STAGE,
        "status": gate.SOURCE_RESOLUTION_STATUS,
        "scope": {
            "rows": ["SR1:2020", "SR3:2020"],
            "raw_files_updated": [
                "data/raw/SR1/2020.parquet",
                "data/raw/SR3/2020.parquet",
            ],
            "source_files": [
                f"{gate.SR_PARENT_SOURCE_ROOT}/SR1/2020/2020-01-01_2021-01-01.dbn.zst",
                f"{gate.SR_PARENT_SOURCE_ROOT}/SR3/2020/2020-01-01_2021-01-01.dbn.zst",
            ],
        },
        "repairs": repairs,
        "post_repair_readiness": {
            "status": gate.READINESS_READY_STATUS,
            "ready_for_build_input_only": 3,
            gate.READINESS_SOURCE_FAILURE: 0,
            "deferred_policy_review_not_checked": 2,
            "SR1:2020": "ready_for_build_input_only",
            "SR3:2020": "ready_for_build_input_only",
        },
        "approval_flags": {
            "build_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
            "wfa_modeling_approved": False,
            "metrics_approved": False,
        },
    }


def _repair_row(pair: str) -> dict[str, object]:
    market, year_text = pair.split(":")
    return {
        "pair": pair,
        "raw_path": f"data/raw/{market}/{year_text}.parquet",
        "source_file": f"{gate.SR_PARENT_SOURCE_ROOT}/{market}/{year_text}/source.dbn.zst",
        "old_source_sha256": "b" * 64,
        "new_source_sha256": "a" * 64,
        "new_raw_parquet_sha256": "c" * 64,
        "row_count": 100,
        "column_count": 86,
    }


def _policy_row(pair: str) -> dict[str, object]:
    market, year_text = pair.split(":")
    return {
        "pair": pair,
        "market": market,
        "year": int(year_text),
        "source_file": f"{gate.SR_PARENT_SOURCE_ROOT}/{market}/{year_text}/source.dbn.zst",
        "planned_input_raw_path": f"data/raw/{market}/{year_text}.parquet",
        "raw_parquet_sha256": f"raw-{pair}",
        "raw_parquet_row_count": 10,
        "input_disposition_status": "blocked_missing_current_source_artifact",
        "source_file_present": False,
        "selected_decision_option": gate.SELECTED_OPTION,
        "human_decision_recorded": True,
        "approved_action": "none",
        "policy_status": "ACTION_REQUIRED",
        "blockers": ["human selected continue_block_no_action; no source/data action approved"],
    }


def _policy_selection() -> dict[str, object]:
    rows = [_policy_row("SR1:2020"), _policy_row("SR3:2020")]
    return {
        "summary": {
            "stage": gate.POLICY_SELECTION_STAGE,
            "status": "ACTION_REQUIRED",
            "selected_decision_option": gate.SELECTED_OPTION,
            "human_decision_recorded": True,
            "approved_action": "none",
            "pair_count": 2,
            "pairs": ["SR1:2020", "SR3:2020"],
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


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    prebuild_path = tmp_path / "prebuild.json"
    readiness_path = tmp_path / "readiness.json"
    selection_path = tmp_path / "selection.json"
    resolution_path = tmp_path / "resolution.json"
    _write_json(prebuild_path, _prebuild_plan())
    _write_json(readiness_path, _readiness_report())
    _write_json(selection_path, _policy_selection())
    _write_json(resolution_path, _source_resolution())
    return prebuild_path, readiness_path, selection_path, resolution_path


def _build_report(tmp_path: Path) -> dict[str, object]:
    prebuild_path, readiness_path, selection_path, resolution_path = _write_inputs(tmp_path)
    return gate.build_report(
        repo_root=tmp_path,
        prebuild_plan_path=prebuild_path,
        readiness_path=readiness_path,
        policy_selection_path=selection_path,
        source_resolution_path=resolution_path,
        generated_at_utc="2026-06-29T00:00:00Z",
        expected_rows=5,
        expected_action_required=3,
        expected_deferred_policy_review=2,
        expected_ready_input_only=3,
    )


def test_build_report_records_blocked_gate_without_approving_build(tmp_path: Path) -> None:
    report = _build_report(tmp_path)

    assert report["summary"]["stage"] == gate.OUTPUT_STAGE
    assert report["summary"]["status"] == gate.GATE_STATUS
    assert report["summary"]["gate_decision"] == gate.GATE_DECISION
    assert report["summary"]["ready_for_build_rows"] == 0
    assert report["summary"]["raw_source_readiness_status"] == gate.READINESS_READY_STATUS
    assert report["summary"]["input_only_ready_rows"] == 3
    assert report["summary"]["blocked_source_artifact_rows"] == 0
    assert report["summary"]["blocked_pairs"] == []
    assert report["summary"]["resolved_source_hash_pairs"] == ["SR1:2020", "SR3:2020"]
    assert report["summary"]["build_approved"] is False
    assert report["summary"]["source_action_approved"] is False
    assert report["summary"]["block_reason"] == "raw_source_hash_readiness_passed_but_separate_broad_build_approval_missing"
    assert report["blocked_rows"] == []
    assert {row["pair"] for row in report["resolved_source_hash_rows"]} == {"SR1:2020", "SR3:2020"}


def test_policy_option_change_fails_closed(tmp_path: Path) -> None:
    prebuild_path, readiness_path, selection_path, resolution_path = _write_inputs(tmp_path)
    selection_payload = json.loads(selection_path.read_text(encoding="utf-8"))
    selection_payload["summary"]["selected_decision_option"] = "approve_policy_exclusion_deferment_plan"
    _write_json(selection_path, selection_payload)

    with pytest.raises(ValueError, match="selected_decision_option"):
        gate.build_report(
            repo_root=tmp_path,
            prebuild_plan_path=prebuild_path,
            readiness_path=readiness_path,
            policy_selection_path=selection_path,
            source_resolution_path=resolution_path,
            expected_rows=5,
            expected_action_required=3,
            expected_deferred_policy_review=2,
            expected_ready_input_only=3,
        )


def test_true_policy_approval_flag_fails_closed(tmp_path: Path) -> None:
    prebuild_path, readiness_path, selection_path, resolution_path = _write_inputs(tmp_path)
    selection_payload = json.loads(selection_path.read_text(encoding="utf-8"))
    selection_payload["summary"]["source_action_approved"] = True
    _write_json(selection_path, selection_payload)

    with pytest.raises(ValueError, match="source_action_approved"):
        gate.build_report(
            repo_root=tmp_path,
            prebuild_plan_path=prebuild_path,
            readiness_path=readiness_path,
            policy_selection_path=selection_path,
            source_resolution_path=resolution_path,
            expected_rows=5,
            expected_action_required=3,
            expected_deferred_policy_review=2,
            expected_ready_input_only=3,
        )


def test_readiness_source_failure_count_fails_closed(tmp_path: Path) -> None:
    prebuild_path, readiness_path, selection_path, resolution_path = _write_inputs(tmp_path)
    readiness_payload = json.loads(readiness_path.read_text(encoding="utf-8"))
    readiness_payload["summary"]["readiness_status_counts"][gate.READINESS_SOURCE_FAILURE] = 1
    _write_json(readiness_path, readiness_payload)

    with pytest.raises(ValueError, match=gate.READINESS_SOURCE_FAILURE):
        gate.build_report(
            repo_root=tmp_path,
            prebuild_plan_path=prebuild_path,
            readiness_path=readiness_path,
            policy_selection_path=selection_path,
            source_resolution_path=resolution_path,
            expected_rows=5,
            expected_action_required=3,
            expected_deferred_policy_review=2,
            expected_ready_input_only=3,
        )


def test_prebuild_ready_for_build_count_fails_closed(tmp_path: Path) -> None:
    prebuild_path, readiness_path, selection_path, resolution_path = _write_inputs(tmp_path)
    prebuild_payload = json.loads(prebuild_path.read_text(encoding="utf-8"))
    prebuild_payload["summary"]["status_counts"]["ready_for_build"] = 1
    _write_json(prebuild_path, prebuild_payload)

    with pytest.raises(ValueError, match="ready_for_build"):
        gate.build_report(
            repo_root=tmp_path,
            prebuild_plan_path=prebuild_path,
            readiness_path=readiness_path,
            policy_selection_path=selection_path,
            source_resolution_path=resolution_path,
            expected_rows=5,
            expected_action_required=3,
            expected_deferred_policy_review=2,
            expected_ready_input_only=3,
        )


def test_source_resolution_status_fails_closed(tmp_path: Path) -> None:
    prebuild_path, readiness_path, selection_path, resolution_path = _write_inputs(tmp_path)
    resolution_payload = json.loads(resolution_path.read_text(encoding="utf-8"))
    resolution_payload["status"] = "ACTION_REQUIRED"
    _write_json(resolution_path, resolution_payload)

    with pytest.raises(ValueError, match="source_resolution.status"):
        gate.build_report(
            repo_root=tmp_path,
            prebuild_plan_path=prebuild_path,
            readiness_path=readiness_path,
            policy_selection_path=selection_path,
            source_resolution_path=resolution_path,
            expected_rows=5,
            expected_action_required=3,
            expected_deferred_policy_review=2,
            expected_ready_input_only=3,
        )


def test_true_source_resolution_approval_flag_fails_closed(tmp_path: Path) -> None:
    prebuild_path, readiness_path, selection_path, resolution_path = _write_inputs(tmp_path)
    resolution_payload = json.loads(resolution_path.read_text(encoding="utf-8"))
    resolution_payload["approval_flags"]["build_approved"] = True
    _write_json(resolution_path, resolution_payload)

    with pytest.raises(ValueError, match="build_approved"):
        gate.build_report(
            repo_root=tmp_path,
            prebuild_plan_path=prebuild_path,
            readiness_path=readiness_path,
            policy_selection_path=selection_path,
            source_resolution_path=resolution_path,
            expected_rows=5,
            expected_action_required=3,
            expected_deferred_policy_review=2,
            expected_ready_input_only=3,
        )


def test_write_report_outputs_blocked_summary_and_non_approval_text(tmp_path: Path) -> None:
    report = _build_report(tmp_path)
    json_out = tmp_path / "out" / "gate.json"
    md_out = tmp_path / "out" / "gate.md"

    gate.write_report(report, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["status"] == gate.GATE_STATUS
    assert payload["summary"]["build_approved"] is False
    assert payload["summary"]["blocked_source_artifact_rows"] == 0
    assert "BLOCKED_NO_BUILD_APPROVAL" in markdown
    assert gate.READINESS_READY_STATUS in markdown
    assert "broad_rebuild_blocked" in markdown
    assert "SR1:2020" in markdown
    assert "SR3:2020" in markdown
    assert "RESOLVED_FOR_SOURCE_READINESS" in markdown
    assert "does not approve data mutation" in markdown
