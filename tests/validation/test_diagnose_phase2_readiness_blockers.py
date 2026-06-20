from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import diagnose_phase2_readiness_blockers as diagnose


def _write_checkpoint(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sample_rows() -> list[dict[str, object]]:
    return [
        {
            "market": "ES",
            "year": 2024,
            "status": "PASS",
            "warnings": [],
            "failures": [],
        },
        {
            "market": "RTY",
            "year": 2024,
            "status": "WARN",
            "synthetic_rows_pct": 4.0,
            "synthetic_rows": 100,
            "max_synthetic_gap_minutes": 23,
            "warnings": ["synthetic threshold breached: rows_pct=4.0"],
            "failures": [],
            "status_enrichment_missing_rows": 5,
            "status_enrichment_stale_rows": 5,
        },
        {
            "market": "ES",
            "year": 2019,
            "status": "WARN",
            "degraded_rows_pct": 1.5,
            "degraded_bar_rows": 10,
            "degraded_session_rows": 1,
            "warnings": ["degraded threshold breached: rows_pct=1.5"],
            "failures": [],
            "statistics_enrichment_missing_rows": 3,
            "statistics_enrichment_stale_rows": 3,
        },
        {
            "market": "SR1",
            "year": 2020,
            "status": "WARN",
            "synthetic_rows_pct": 91.0,
            "max_synthetic_gap_minutes": 120,
            "degraded_rows_pct": 3.0,
            "roll_window_rows_pct": 4.0,
            "roll_window_rows": 10,
            "warnings": [
                "synthetic threshold breached: rows_pct=91.0",
                "degraded threshold breached: rows_pct=3.0",
                "roll exclusion threshold breached: rows_pct=4.0 rows=10",
            ],
            "failures": [],
        },
    ]


def test_build_root_cause_report_classifies_causes_and_product_groups() -> None:
    report = diagnose.build_root_cause_report(_sample_rows(), top_n=2)

    assert report["status"] == "FAIL"
    assert report["policy"] == "FAIL_CLOSED_DIAGNOSTIC_ONLY"
    assert report["pass_count"] == 1
    assert report["blocker_count"] == 3
    assert report["reason_combo_counts"] == {
        "degraded+statistics_enrichment": 1,
        "synthetic+degraded+roll": 1,
        "synthetic+status_enrichment": 1,
    }
    groups = report["root_cause_groups"]
    assert groups["synthetic_coverage_or_session_scope"]["market_year_count"] == 2
    assert groups["synthetic_coverage_or_session_scope"]["product_group_counts"] == {
        "equity_index": 1,
        "rates": 1,
    }
    assert groups["degraded_raw_quality"]["market_year_count"] == 2
    assert groups["enrichment_coverage_or_join"]["status_market_year_count"] == 1
    assert groups["enrichment_coverage_or_join"]["statistics_market_year_count"] == 1
    assert groups["roll_metadata_or_roll_window"]["market_year_count"] == 1
    assert report["evidence_scope"]["raw_parquet_read"] is False
    assert report["evidence_scope"]["session_date_detail"] == "not_available_in_checkpoint"


def test_decision_tables_are_diagnostic_only() -> None:
    report = diagnose.build_root_cause_report(_sample_rows(), top_n=1)
    tables = report["decision_tables"]

    assert len(tables["repair_candidates"]) == 3
    assert tables["repair_candidates"][0]["status"] == "DIAGNOSTIC_ONLY"
    assert tables["exclusion_candidates"]["status"] == "DIAGNOSTIC_ONLY"
    assert len(tables["exclusion_candidates"]["market_years"]) == 3
    assert tables["already_passable"] == [
        {
            "market": "ES",
            "year": 2024,
            "product_group": "equity_index",
            "status": "PASS_DIAGNOSTIC_ONLY",
        }
    ]


def test_cli_writes_full_json_and_prints_compact_summary(
    tmp_path: Path,
    capsys,
) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    json_out = tmp_path / "root_cause.json"
    _write_checkpoint(checkpoint, _sample_rows())

    result = diagnose.main(
        [
            "--checkpoint-jsonl",
            str(checkpoint),
            "--top-n",
            "1",
            "--json-out",
            str(json_out),
        ]
    )
    stdout_payload = json.loads(capsys.readouterr().out)
    written_payload = json.loads(json_out.read_text(encoding="utf-8"))

    assert result == 1
    assert stdout_payload["blocker_count"] == 3
    assert "decision_tables" not in stdout_payload
    assert written_payload["decision_tables"]["exclusion_candidates"]["status"] == (
        "DIAGNOSTIC_ONLY"
    )


def test_cli_errors_on_missing_checkpoint(capsys) -> None:
    result = diagnose.main(["--checkpoint-jsonl", "missing.jsonl"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["status"] == "FAIL"
    assert "missing" in payload["failures"][0]


def test_cli_errors_on_malformed_checkpoint(tmp_path: Path, capsys) -> None:
    checkpoint = tmp_path / "bad.jsonl"
    checkpoint.write_text("{bad json}\n", encoding="utf-8")

    result = diagnose.main(["--checkpoint-jsonl", str(checkpoint)])
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["failure_count"] == 1
