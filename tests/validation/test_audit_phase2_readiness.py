from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import audit_phase2_readiness
from scripts.validation.audit_phase2_readiness import (
    load_checkpoint_rows,
    summarize_checkpoint_rows,
    summarize_readiness_report,
)


def _sample_report() -> dict[str, object]:
    return {
        "stage": "phase2_readiness_preflight",
        "status": "FAIL",
        "profile": "tier_3",
        "resolved_profile": "tier_3_research",
        "selected_market_year_count": 5,
        "checked_market_year_count": 5,
        "blocker_count": 3,
        "failure_count": 0,
        "failures": [],
        "blockers": [
            {
                "market": "ES",
                "year": 2019,
                "status": "WARN",
                "top_blocker_reason": (
                    "degraded threshold breached: rows_pct=1.5 bars=10 sessions=1"
                ),
                "synthetic_rows_pct": 0.1,
                "max_synthetic_gap_minutes": 3,
                "degraded_rows_pct": 1.5,
                "status_enrichment_missing_rows": 0,
                "status_enrichment_stale_rows": 0,
                "statistics_enrichment_missing_rows": 2,
                "statistics_enrichment_stale_rows": 2,
                "warnings": [
                    "degraded threshold breached: rows_pct=1.5 bars=10 sessions=1"
                ],
                "failures": [],
            },
            {
                "market": "RTY",
                "year": 2024,
                "status": "WARN",
                "top_blocker_reason": (
                    "synthetic threshold breached: rows_pct=4.0 max_gap_minutes=23"
                ),
                "synthetic_rows_pct": 4.0,
                "max_synthetic_gap_minutes": 23,
                "degraded_rows_pct": 0.0,
                "status_enrichment_missing_rows": 0,
                "status_enrichment_stale_rows": 0,
                "statistics_enrichment_missing_rows": 17,
                "statistics_enrichment_stale_rows": 17,
                "warnings": [
                    "synthetic threshold breached: rows_pct=4.0 max_gap_minutes=23"
                ],
                "failures": [],
            },
            {
                "market": "NQ",
                "year": 2020,
                "status": "WARN",
                "top_blocker_reason": (
                    "synthetic threshold breached: rows_pct=3.0 max_gap_minutes=12"
                ),
                "synthetic_rows_pct": 3.0,
                "max_synthetic_gap_minutes": 12,
                "degraded_rows_pct": 2.25,
                "status_enrichment_missing_rows": 5,
                "status_enrichment_stale_rows": 5,
                "statistics_enrichment_missing_rows": 0,
                "statistics_enrichment_stale_rows": 0,
                "warnings": [
                    "synthetic threshold breached: rows_pct=3.0 max_gap_minutes=12",
                    "degraded threshold breached: rows_pct=2.25 bars=20 sessions=1",
                ],
                "failures": [],
            },
        ],
    }


def test_summary_omits_full_blocker_list_and_limits_top_rows() -> None:
    summary = summarize_readiness_report(_sample_report(), top_blockers=1)

    assert summary["stage"] == "phase2_readiness_summary"
    assert "blockers" not in summary
    assert summary["blocker_count"] == 3
    assert summary["pass_count"] == 2
    assert len(summary["top_synthetic_pct"]) == 1
    assert len(summary["top_degraded_pct"]) == 1
    assert summary["top_synthetic_pct"][0]["market"] == "RTY"
    assert summary["top_degraded_pct"][0]["market"] == "NQ"


def test_summary_counts_reasons_markets_and_enrichment() -> None:
    summary = summarize_readiness_report(_sample_report(), top_blockers=20)

    assert summary["reason_counts"] == {
        "degraded threshold breached": 2,
        "synthetic threshold breached": 2,
    }
    assert summary["market_blocker_counts"] == {"ES": 1, "NQ": 1, "RTY": 1}
    assert summary["enrichment_totals"]["status_missing_rows"] == 5
    assert summary["enrichment_totals"]["statistics_missing_rows"] == 19
    assert summary["enrichment_blocker_counts"]["status_missing"] == 1
    assert summary["enrichment_blocker_counts"]["statistics_missing"] == 2


def test_cli_default_full_json_behavior_is_unchanged(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        audit_phase2_readiness,
        "build_phase2_readiness_report",
        lambda **_: _sample_report(),
    )

    result = audit_phase2_readiness.main([])
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["stage"] == "phase2_readiness_preflight"
    assert "blockers" in payload
    assert len(payload["blockers"]) == 3


def test_cli_summary_only_and_json_out(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    out_path = tmp_path / "reports" / "phase2_readiness_summary.json"
    monkeypatch.setattr(
        audit_phase2_readiness,
        "build_phase2_readiness_report",
        lambda **_: _sample_report(),
    )

    result = audit_phase2_readiness.main(
        [
            "--summary-only",
            "--top-blockers",
            "1",
            "--json-out",
            str(out_path),
        ]
    )
    stdout_payload = json.loads(capsys.readouterr().out)
    written_payload = json.loads(out_path.read_text(encoding="utf-8"))

    assert result == 1
    assert "blockers" not in stdout_payload
    assert stdout_payload == written_payload
    assert stdout_payload["stage"] == "phase2_readiness_summary"
    assert len(stdout_payload["top_synthetic_pct"]) == 1


def test_checkpoint_summary_matches_direct_summary() -> None:
    report = _sample_report()
    rows = [
        {
            "stage": "phase2_readiness_market_year",
            "profile": "tier_3",
            "resolved_profile": "tier_3_research",
            "market": "YM",
            "year": 2024,
            "status": "PASS",
            "warnings": [],
            "failures": [],
        },
        {
            "stage": "phase2_readiness_market_year",
            "profile": "tier_3",
            "resolved_profile": "tier_3_research",
            "market": "ZN",
            "year": 2024,
            "status": "PASS",
            "warnings": [],
            "failures": [],
        },
        *report["blockers"],
    ]

    direct = summarize_readiness_report(report, top_blockers=2)
    checkpoint = summarize_checkpoint_rows(rows, base_report=report, top_blockers=2)

    assert checkpoint["status"] == direct["status"]
    assert checkpoint["blocker_count"] == direct["blocker_count"]
    assert checkpoint["pass_count"] == direct["pass_count"]
    assert checkpoint["reason_counts"] == direct["reason_counts"]
    assert checkpoint["market_blocker_counts"] == direct["market_blocker_counts"]
    assert checkpoint["top_synthetic_pct"] == direct["top_synthetic_pct"]
    assert checkpoint["top_degraded_pct"] == direct["top_degraded_pct"]


def test_cli_checkpoint_preserves_completed_rows_when_builder_stops(
    tmp_path: Path,
    monkeypatch,
) -> None:
    checkpoint_path = tmp_path / "reports" / "phase2_readiness" / "checkpoint.jsonl"

    def fake_build_phase2_readiness_report(**kwargs):
        kwargs["checkpoint_row_callback"](
            {
                "stage": "phase2_readiness_market_year",
                "profile": "tier_3",
                "resolved_profile": "tier_3_research",
                "market": "ES",
                "year": 2024,
                "status": "PASS",
                "warnings": [],
                "failures": [],
            }
        )
        raise RuntimeError("interrupted")

    monkeypatch.setattr(
        audit_phase2_readiness,
        "build_phase2_readiness_report",
        fake_build_phase2_readiness_report,
    )

    with pytest.raises(RuntimeError):
        audit_phase2_readiness.main(["--checkpoint-jsonl", str(checkpoint_path)])

    rows = load_checkpoint_rows(checkpoint_path)
    assert [(row["market"], row["year"], row["status"]) for row in rows] == [
        ("ES", 2024, "PASS")
    ]


def test_cli_resume_skips_completed_checkpoint_rows(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    checkpoint_path = tmp_path / "reports" / "phase2_readiness" / "checkpoint.jsonl"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "stage": "phase2_readiness_market_year",
                "profile": "tier_3",
                "resolved_profile": "tier_3_research",
                "market": "ES",
                "year": 2024,
                "status": "PASS",
                "warnings": [],
                "failures": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_build_phase2_readiness_report(**kwargs):
        captured["skip_market_years"] = kwargs["skip_market_years"]
        return {
            "stage": "phase2_readiness_preflight",
            "status": "PASS",
            "profile": "tier_3",
            "resolved_profile": "tier_3_research",
            "selected_market_year_count": 1,
            "expected_market_year_count": 1,
            "checked_market_year_count": 1,
            "resumed_market_year_count": 1,
            "pending_market_year_count": 0,
            "blocker_count": 0,
            "failure_count": 0,
            "failures": [],
            "blockers": [],
        }

    monkeypatch.setattr(
        audit_phase2_readiness,
        "build_phase2_readiness_report",
        fake_build_phase2_readiness_report,
    )

    result = audit_phase2_readiness.main(
        ["--resume-from", str(checkpoint_path), "--summary-only"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert captured["skip_market_years"] == [("ES", 2024)]
    assert payload["checked_market_year_count"] == 1
    assert payload["pass_count"] == 1


def test_cli_passes_market_year_filters(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_build_phase2_readiness_report(**kwargs):
        captured["markets"] = kwargs["markets"]
        captured["years"] = kwargs["years"]
        return {
            "stage": "phase2_readiness_preflight",
            "status": "PASS",
            "profile": "tier_3",
            "resolved_profile": "tier_3_research",
            "selected_market_year_count": 0,
            "checked_market_year_count": 0,
            "blocker_count": 0,
            "failure_count": 0,
            "failures": [],
            "blockers": [],
        }

    monkeypatch.setattr(
        audit_phase2_readiness,
        "build_phase2_readiness_report",
        fake_build_phase2_readiness_report,
    )

    result = audit_phase2_readiness.main(
        ["--markets", "ES", "NQ", "--years", "2023", "2024"]
    )
    capsys.readouterr()

    assert result == 0
    assert captured["markets"] == ["ES", "NQ"]
    assert captured["years"] == [2023, 2024]


def test_checkpoint_summary_only_reads_checkpoint_without_scan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    checkpoint_path = tmp_path / "reports" / "phase2_readiness" / "checkpoint.jsonl"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "stage": "phase2_readiness_market_year",
                "profile": "tier_3",
                "resolved_profile": "tier_3_research",
                "market": "ES",
                "year": 2024,
                "status": "WARN",
                "synthetic_rows_pct": 3.0,
                "max_synthetic_gap_minutes": 12,
                "warnings": ["synthetic threshold breached: rows_pct=3.0"],
                "failures": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fail_if_scan_runs(**_kwargs):
        raise AssertionError("raw readiness scan should not run")

    monkeypatch.setattr(
        audit_phase2_readiness,
        "build_phase2_readiness_report",
        fail_if_scan_runs,
    )
    monkeypatch.setattr(
        audit_phase2_readiness,
        "checkpoint_summary_base_report",
        lambda **_: {
            "stage": "phase2_readiness_checkpoint_summary",
            "status": "PASS",
            "profile": "tier_3",
            "resolved_profile": "tier_3_research",
            "selected_market_year_count": 461,
            "expected_market_year_count": 461,
            "failure_count": 0,
            "failures": [],
        },
    )

    result = audit_phase2_readiness.main(
        [
            "--resume-from",
            str(checkpoint_path),
            "--checkpoint-summary-only",
            "--summary-only",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert payload["checked_market_year_count"] == 1
    assert payload["pending_market_year_count"] == 460
    assert payload["blocker_count"] == 1


def test_cli_max_market_years_preserves_resume_rows_and_reports_pending(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    checkpoint_path = tmp_path / "reports" / "phase2_readiness" / "checkpoint.jsonl"
    checkpoint_path.parent.mkdir(parents=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "stage": "phase2_readiness_market_year",
                "profile": "tier_3",
                "resolved_profile": "tier_3_research",
                "market": "ES",
                "year": 2023,
                "status": "PASS",
                "warnings": [],
                "failures": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_build_phase2_readiness_report(**kwargs):
        captured["max_market_years"] = kwargs["max_market_years"]
        kwargs["checkpoint_row_callback"](
            {
                "stage": "phase2_readiness_market_year",
                "profile": "tier_3",
                "resolved_profile": "tier_3_research",
                "market": "ES",
                "year": 2024,
                "status": "PASS",
                "warnings": [],
                "failures": [],
            }
        )
        return {
            "stage": "phase2_readiness_preflight",
            "status": "PASS",
            "profile": "tier_3",
            "resolved_profile": "tier_3_research",
            "selected_market_year_count": 3,
            "expected_market_year_count": 3,
            "checked_market_year_count": 2,
            "resumed_market_year_count": 1,
            "pending_market_year_count": 1,
            "blocker_count": 0,
            "failure_count": 0,
            "failures": [],
            "blockers": [],
        }

    monkeypatch.setattr(
        audit_phase2_readiness,
        "build_phase2_readiness_report",
        fake_build_phase2_readiness_report,
    )

    result = audit_phase2_readiness.main(
        [
            "--resume-from",
            str(checkpoint_path),
            "--checkpoint-jsonl",
            str(checkpoint_path),
            "--summary-only",
            "--max-market-years",
            "1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert captured["max_market_years"] == 1
    assert payload["checked_market_year_count"] == 2
    assert payload["pending_market_year_count"] == 1
    assert payload["pass_count"] == 2


def test_cli_stop_after_blockers_returns_fail_with_partial_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    checkpoint_path = tmp_path / "reports" / "phase2_readiness" / "checkpoint.jsonl"
    captured: dict[str, object] = {}

    def fake_build_phase2_readiness_report(**kwargs):
        captured["stop_after_blockers"] = kwargs["stop_after_blockers"]
        kwargs["checkpoint_row_callback"](
            {
                "stage": "phase2_readiness_market_year",
                "profile": "tier_3",
                "resolved_profile": "tier_3_research",
                "market": "RTY",
                "year": 2024,
                "status": "WARN",
                "synthetic_rows_pct": 4.0,
                "max_synthetic_gap_minutes": 23,
                "warnings": ["synthetic threshold breached: rows_pct=4.0"],
                "failures": [],
            }
        )
        return {
            "stage": "phase2_readiness_preflight",
            "status": "FAIL",
            "profile": "tier_3",
            "resolved_profile": "tier_3_research",
            "selected_market_year_count": 3,
            "expected_market_year_count": 3,
            "checked_market_year_count": 1,
            "resumed_market_year_count": 0,
            "pending_market_year_count": 2,
            "blocker_count": 1,
            "failure_count": 0,
            "failures": [],
            "blockers": [],
        }

    monkeypatch.setattr(
        audit_phase2_readiness,
        "build_phase2_readiness_report",
        fake_build_phase2_readiness_report,
    )

    result = audit_phase2_readiness.main(
        [
            "--checkpoint-jsonl",
            str(checkpoint_path),
            "--summary-only",
            "--stop-after-blockers",
            "1",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert result == 1
    assert captured["stop_after_blockers"] == 1
    assert payload["status"] == "FAIL"
    assert payload["blocker_count"] == 1
    assert payload["pending_market_year_count"] == 2
