from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import summarize_phase2_readiness_blockers as triage


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
            "top_blocker_reason": "synthetic threshold breached: rows_pct=4.0",
            "synthetic_rows_pct": 4.0,
            "max_synthetic_gap_minutes": 23,
            "warnings": ["synthetic threshold breached: rows_pct=4.0"],
            "failures": [],
            "status_enrichment_missing_rows": 7,
            "status_enrichment_stale_rows": 7,
            "statistics_enrichment_missing_rows": 2,
            "statistics_enrichment_stale_rows": 2,
        },
        {
            "market": "ES",
            "year": 2019,
            "status": "WARN",
            "top_blocker_reason": "degraded threshold breached: rows_pct=1.5",
            "degraded_rows_pct": 1.5,
            "warnings": ["degraded threshold breached: rows_pct=1.5"],
            "failures": [],
        },
        {
            "market": "SR1",
            "year": 2020,
            "status": "WARN",
            "top_blocker_reason": "synthetic threshold breached: rows_pct=91.0",
            "synthetic_rows_pct": 91.0,
            "max_synthetic_gap_minutes": 120,
            "degraded_rows_pct": 3.0,
            "warnings": [
                "synthetic threshold breached: rows_pct=91.0",
                "degraded threshold breached: rows_pct=3.0",
                "roll exclusion threshold breached: rows_pct=4.0 rows=10",
            ],
            "failures": [],
        },
    ]


def test_build_triage_report_counts_blocker_classes_and_markets() -> None:
    report = triage.build_triage_report(_sample_rows(), top_n=2)

    assert report["status"] == "FAIL"
    assert report["pass_count"] == 1
    assert report["blocker_count"] == 3
    assert report["blocker_class_counts"] == {
        "synthetic": {"total": 2, "pure": 1},
        "degraded": {"total": 2, "pure": 1},
        "roll": {"total": 1, "pure": 0},
    }
    assert report["reason_combo_counts"] == {
        "degraded": 1,
        "synthetic": 1,
        "synthetic+degraded+roll": 1,
    }
    assert report["enrichment_blocker_counts"] == {
        "statistics_missing_or_stale": 1,
        "status_missing_or_stale": 1,
    }
    market_counts = {row["market"]: row for row in report["market_level_counts"]}
    assert market_counts["ES"]["pass_count"] == 1
    assert market_counts["ES"]["degraded_blockers"] == 1
    assert market_counts["RTY"]["synthetic_blockers"] == 1


def test_roll_maturity_sequence_warning_classifies_as_roll() -> None:
    classes, other = triage.classify_blocker(
        {
            "status": "WARN",
            "warnings": ["roll maturity sequence not monotonic: backsteps=12"],
            "failures": [],
        }
    )

    assert classes == {"roll"}
    assert other == []


def test_triage_report_marks_candidate_exclusions_diagnostic_only() -> None:
    report = triage.build_triage_report(_sample_rows(), top_n=1)

    exclusion = report["candidate_exclusion_universe"]
    assert exclusion["status"] == "DIAGNOSTIC_ONLY"
    assert len(exclusion["market_years"]) == 3
    assert report["ready_to_rebuild_tier3_phase2"] is False
    assert report["top_offenders"]["synthetic"][0]["market"] == "SR1"


def test_cli_reads_checkpoint_without_raw_access_and_writes_requested_reports(
    tmp_path: Path,
    capsys,
) -> None:
    checkpoint = tmp_path / "reports" / "phase2_readiness" / "checkpoint.jsonl"
    json_out = tmp_path / "reports" / "phase2_readiness" / "triage.json"
    csv_out = tmp_path / "reports" / "phase2_readiness" / "triage.csv"
    _write_checkpoint(checkpoint, _sample_rows())

    result = triage.main(
        [
            "--checkpoint-jsonl",
            str(checkpoint),
            "--top-n",
            "1",
            "--json-out",
            str(json_out),
            "--csv-out",
            str(csv_out),
        ]
    )
    stdout_payload = json.loads(capsys.readouterr().out)
    written_payload = json.loads(json_out.read_text(encoding="utf-8"))

    assert result == 1
    assert stdout_payload["blocker_count"] == 3
    assert written_payload == stdout_payload
    assert csv_out.read_text(encoding="utf-8").splitlines()[0].startswith("market,year")


def test_cli_errors_on_missing_checkpoint(capsys) -> None:
    result = triage.main(["--checkpoint-jsonl", "missing.jsonl"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["status"] == "FAIL"
    assert "missing" in payload["failures"][0]


def test_cli_errors_on_malformed_checkpoint(tmp_path: Path, capsys) -> None:
    checkpoint = tmp_path / "bad.jsonl"
    checkpoint.write_text("{not json}\n", encoding="utf-8")

    result = triage.main(["--checkpoint-jsonl", str(checkpoint)])
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["status"] == "FAIL"
    assert payload["failure_count"] == 1
