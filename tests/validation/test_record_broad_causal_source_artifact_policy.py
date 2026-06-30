from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import record_broad_causal_source_artifact_policy as policy


def _row(pair: str) -> dict[str, object]:
    market, year_text = pair.split(":")
    return {
        "pair": pair,
        "market": market,
        "year": int(year_text),
        "readiness_status": "action_required_source_reference_failure",
        "disposition_status": policy.EXPECTED_DISPOSITION_STATUS,
        "planned_input_raw_path": f"data/raw/{market}/{year_text}.parquet",
        "raw_parquet_sha256": f"raw-{pair}",
        "raw_parquet_row_count": 10,
        "timestamp_min": f"{year_text}-01-02T00:00:00+00:00",
        "timestamp_max": f"{year_text}-12-31T23:59:00+00:00",
        "source_file": (
            f"data/dbn_sr_parent_candidate/{market}/{year_text}/"
            f"{year_text}-01-01_{int(year_text) + 1}-01-01.dbn.zst"
        ),
        "source_file_present": False,
        "current_source_hash_matches": None,
        "historical_evidence_only": True,
        "blockers": ["current source artifact missing"],
    }


def _disposition(rows: list[dict[str, object]]) -> dict[str, object]:
    pairs = sorted(str(row["pair"]) for row in rows)
    return {
        "summary": {
            "stage": policy.EXPECTED_INPUT_STAGE,
            "status": "ACTION_REQUIRED",
            "failed_pair_count": len(rows),
            "failed_pairs": pairs,
            "disposition_status_counts": {
                policy.EXPECTED_DISPOSITION_STATUS: len(rows),
                "blocked_current_source_hash_mismatch": 0,
                "current_source_recovered_rerun_readiness_required": 0,
                "invalid_unexpected_readiness_state": 0,
            },
            "data_mutation_performed": False,
            "build_approved": False,
            "restore_approved": False,
            "repair_approved": False,
            "exclusion_approved": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "research_use_allowed": False,
            "historical_evidence_only": True,
        },
        "rows": rows,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _valid_rows() -> list[dict[str, object]]:
    return [_row("SR1:2020"), _row("SR3:2020")]


def test_records_continued_block_policy_with_no_action_approved(tmp_path: Path) -> None:
    disposition_path = tmp_path / "disposition.json"
    _write_json(disposition_path, _disposition(_valid_rows()))

    report = policy.build_report(
        repo_root=tmp_path,
        disposition_path=disposition_path,
        generated_at_utc="2026-06-29T00:00:00Z",
    )

    assert report["summary"]["stage"] == policy.OUTPUT_STAGE
    assert report["summary"]["status"] == "ACTION_REQUIRED"
    assert report["summary"]["decision"] == policy.DECISION
    assert report["summary"]["source_action_approved"] is False
    assert report["summary"]["repair_approved"] is False
    assert report["summary"]["restore_approved"] is False
    assert report["summary"]["exclusion_approved"] is False
    assert {row["pair"] for row in report["rows"]} == {"SR1:2020", "SR3:2020"}
    assert all(row["approved_action"] == "none" for row in report["rows"])


def test_unexpected_pair_fails_closed(tmp_path: Path) -> None:
    disposition_path = tmp_path / "disposition.json"
    _write_json(disposition_path, _disposition([_row("SR1:2020"), _row("ES:2020")]))

    with pytest.raises(ValueError, match="summary.failed_pairs"):
        policy.build_report(repo_root=tmp_path, disposition_path=disposition_path)


def test_missing_expected_row_fails_closed(tmp_path: Path) -> None:
    disposition_path = tmp_path / "disposition.json"
    _write_json(disposition_path, _disposition([_row("SR1:2020")]))

    with pytest.raises(ValueError, match="summary.failed_pair_count"):
        policy.build_report(repo_root=tmp_path, disposition_path=disposition_path)


def test_changed_disposition_status_fails_closed(tmp_path: Path) -> None:
    rows = _valid_rows()
    rows[0]["disposition_status"] = "current_source_recovered_rerun_readiness_required"
    disposition_path = tmp_path / "disposition.json"
    _write_json(disposition_path, _disposition(rows))

    with pytest.raises(ValueError, match="row.failed_pairs"):
        policy.build_report(repo_root=tmp_path, disposition_path=disposition_path)


def test_true_approval_flag_fails_closed(tmp_path: Path) -> None:
    payload = _disposition(_valid_rows())
    payload["summary"]["repair_approved"] = True  # type: ignore[index]
    disposition_path = tmp_path / "disposition.json"
    _write_json(disposition_path, payload)

    with pytest.raises(ValueError, match="summary.repair_approved"):
        policy.build_report(repo_root=tmp_path, disposition_path=disposition_path)


def test_write_report_outputs_policy_and_non_approval_text(tmp_path: Path) -> None:
    disposition_path = tmp_path / "disposition.json"
    _write_json(disposition_path, _disposition(_valid_rows()))
    report = policy.build_report(repo_root=tmp_path, disposition_path=disposition_path)
    json_out = tmp_path / "out" / "policy.json"
    md_out = tmp_path / "out" / "policy.md"

    policy.write_report(report, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["stage"] == policy.OUTPUT_STAGE
    assert payload["summary"]["decision"] == policy.DECISION
    assert payload["summary"]["config_promotion_approved"] is False
    assert "continued_block_no_source_action_approved" in markdown
    assert "SR1:2020" in markdown
    assert "SR3:2020" in markdown
    assert "source repair" in markdown
    assert "config promotion" in markdown
