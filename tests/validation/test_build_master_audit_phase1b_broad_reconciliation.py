from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validation import build_master_audit_phase1b_broad_reconciliation as phase1b


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _market_counts() -> dict[str, int]:
    counts = {market: 16 for market in phase1b.EXPECTED_MARKETS}
    counts[phase1b.EXPECTED_MARKETS[-1]] = 15
    assert sum(counts.values()) == phase1b.EXPECTED_MARKET_YEAR_COUNT
    return counts


def _market_years(market: str, count: int) -> list[dict[str, object]]:
    return [{"market": market, "year": 2010 + offset} for offset in range(count)]


def _phase1a_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE1A_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "phase1a_source_lineage_ready": True,
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _phase1ab_summary_payload() -> dict[str, object]:
    counts = _market_counts()
    market_reports = [
        {
            "market": market,
            "path": phase1b.market_alignment_path(market).as_posix(),
            "status": "PASS",
            "expected_market_year_count": count,
            "raw_market_year_count": count,
            "missing_status_dbn_count": 0,
            "missing_statistics_dbn_count": 0,
            "needs_phase1b_conversion_count": 0,
            "raw_only_count": 0,
            "invalid_manifest_count": 0,
            "source_hash_mismatch_count": 0,
            "definition_join_mismatch_count": 0,
            "raw_schema_failure_count": 0,
            "required_schema_exception_failure_count": 0,
            "status_required_schema_exception_count": 0,
            "accepted_repair_source_count": 0,
            "repair_manifest_failure_count": 0,
        }
        for market, count in counts.items()
    ]
    market_reports[0]["accepted_repair_source_count"] = phase1b.EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT
    return {
        "status": "PASS",
        "phase1b": {
            "status": "PASS",
            "mode": "one_market_batches_expected_only",
            "batch_root": phase1b.MARKET_ALIGNMENT_ROOT.as_posix(),
            "repair_manifest": phase1b.REPAIR_MANIFEST.as_posix(),
            "summary_counts": {
                "market_reports": phase1b.EXPECTED_MARKET_COUNT,
                "missing_report_count": 0,
                "pass_market_reports": phase1b.EXPECTED_MARKET_COUNT,
                "fail_market_reports": 0,
                "expected_market_year_count": phase1b.EXPECTED_MARKET_YEAR_COUNT,
                "raw_market_year_count": phase1b.EXPECTED_MARKET_YEAR_COUNT,
                "missing_status_dbn_count": 0,
                "missing_statistics_dbn_count": 0,
                "needs_phase1b_conversion_count": 0,
                "raw_only_count": 0,
                "invalid_manifest_count": 0,
                "source_hash_mismatch_count": 0,
                "definition_join_mismatch_count": 0,
                "raw_schema_failure_count": 0,
                "required_schema_exception_failure_count": 0,
                "status_required_schema_exception_count": 1,
                "accepted_repair_source_count": phase1b.EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT,
                "repair_manifest_failure_count": 0,
            },
            "market_reports": market_reports,
            "missing_reports": [],
            "fail_markets": [],
        },
    }


def _legacy_alignment_payload() -> dict[str, object]:
    return {
        "status": "FAIL",
        "expected_market_year_count": phase1b.EXPECTED_MARKET_YEAR_COUNT,
        "raw_market_year_count": phase1b.EXPECTED_MARKET_YEAR_COUNT,
        "source_hash_mismatch_count": phase1b.EXPECTED_LEGACY_FULL_ALIGNMENT_SOURCE_HASH_MISMATCHES,
        "raw_schema_failure_count": 0,
        "definition_join_status": "checked",
        "definition_join_mismatch_count": 0,
        "invalid_manifest_count": 0,
        "repair_manifest_status": "PASS",
        "repair_manifest_failure_count": 0,
    }


def _repair_manifest_payload() -> dict[str, object]:
    pairs = sorted(phase1b.EXPECTED_REPAIR_MARKET_YEARS)
    return {
        "status": "PASS",
        "approvals": {
            "active_raw_replacement": False,
            "causal_rebuild": False,
            "cleanup": False,
            "commit": False,
            "dbn_placement": False,
            "paper_or_live": False,
            "provider_download": False,
            "push": False,
            "raw_rebuild": False,
        },
        "strict_limits": {
            "allowed_market_years": [
                {"market": market, "year": year} for market, year in pairs
            ],
            "not_a_general_hash_bypass": True,
            "repair_count": phase1b.EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT,
        },
        "repairs": [
            {"market": market, "year": year, "reason": "test"} for market, year in pairs
        ],
    }


def _alignment_payload(market: str) -> dict[str, object]:
    count = _market_counts()[market]
    return {
        "status": "PASS",
        "expected_only": True,
        "market_year_include_list_applied": True,
        "expected_market_year_count": count,
        "raw_market_year_count": count,
        "ohlcv_dbn_market_year_count": count,
        "definition_dbn_market_year_count": count,
        "status_dbn_market_year_count": count,
        "statistics_dbn_market_year_count": count,
        "missing_raw_count": 0,
        "missing_ohlcv_dbn_count": 0,
        "missing_definition_dbn_count": 0,
        "missing_status_dbn_count": 0,
        "missing_statistics_dbn_count": 0,
        "needs_phase1b_conversion_count": 0,
        "raw_only_count": 0,
        "invalid_manifest_count": 0,
        "source_hash_mismatch_count": 0,
        "definition_join_status": "checked",
        "definition_join_mismatch_count": 0,
        "raw_schema_failure_count": 0,
        "required_schema_exception_failure_count": 0,
        "status_required_schema_exception_count": 0,
        "accepted_repair_source_count": (
            phase1b.EXPECTED_ACCEPTED_REPAIR_SOURCE_COUNT
            if market == phase1b.EXPECTED_MARKETS[0]
            else 0
        ),
        "repair_manifest_status": "PASS",
        "repair_manifest_failure_count": 0,
        "failures": [],
        "market_years": _market_years(market, count),
    }


def _include_payload(market: str) -> dict[str, object]:
    count = _market_counts()[market]
    return {
        "market": market,
        "source": "test-fixture",
        "market_years": _market_years(market, count),
    }


def _base_repo(
    tmp_path: Path,
    *,
    omitted_market: str | None = None,
    alignment_overrides: dict[str, dict[str, object]] | None = None,
    phase1ab_summary: dict[str, object] | None = None,
    legacy_alignment: dict[str, object] | None = None,
    repair_manifest: dict[str, object] | None = None,
) -> Path:
    _write_json(tmp_path / phase1b.PHASE1A_RECONCILIATION, _phase1a_payload())
    _write_json(
        tmp_path / phase1b.PHASE1AB_SUMMARY,
        phase1ab_summary or _phase1ab_summary_payload(),
    )
    _write_json(
        tmp_path / phase1b.BROAD_ALIGNMENT,
        legacy_alignment or _legacy_alignment_payload(),
    )
    _write_json(
        tmp_path / phase1b.REPAIR_MANIFEST,
        repair_manifest or _repair_manifest_payload(),
    )
    alignment_overrides = alignment_overrides or {}
    for market in phase1b.EXPECTED_MARKETS:
        if market == omitted_market:
            continue
        _write_json(
            tmp_path / phase1b.market_alignment_path(market),
            alignment_overrides.get(market, _alignment_payload(market)),
        )
        _write_json(tmp_path / phase1b.market_include_path(market), _include_payload(market))
    return tmp_path / phase1b.DEFAULT_REPORTS_ROOT


def _build(
    tmp_path: Path,
    *,
    omitted_market: str | None = None,
    alignment_overrides: dict[str, dict[str, object]] | None = None,
    phase1ab_summary: dict[str, object] | None = None,
    legacy_alignment: dict[str, object] | None = None,
    repair_manifest: dict[str, object] | None = None,
) -> dict[str, object]:
    reports_root = _base_repo(
        tmp_path,
        omitted_market=omitted_market,
        alignment_overrides=alignment_overrides,
        phase1ab_summary=phase1ab_summary,
        legacy_alignment=legacy_alignment,
        repair_manifest=repair_manifest,
    )
    return phase1b.build_report(
        repo_root=tmp_path,
        reports_root=reports_root,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )


def test_phase1b_broad_reconciliation_passes_current_style_expected_only_evidence(
    tmp_path: Path,
) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase1b.PASS_STATUS
    assert report["summary"]["raw_row_parity_and_conversion_ready"] is True
    assert report["summary"]["broad_phase1b_accepted"] is True
    assert report["summary"]["market_report_count"] == 33
    assert report["summary"]["expected_market_year_count"] == 527
    assert report["summary"]["raw_market_year_count"] == 527
    assert report["summary"]["legacy_full_alignment_context"] == (
        "SUPERSEDED_BY_CORRECTED_EXPECTED_ONLY_BATCHES"
    )
    assert report["summary"]["phase2_accepted"] is False
    assert report["summary"]["model_trust_ready"] is False
    assert report["summary"]["promotion_allowed"] is False
    assert all(value is False for value in report["non_approval"].values())


def test_missing_market_batch_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path, omitted_market="ES")

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("missing required Phase 1B" in failure for failure in report["failures"])
    assert report["summary"]["raw_row_parity_and_conversion_ready"] is False


def test_stale_legacy_failure_without_corrected_repair_evidence_fails_closed(
    tmp_path: Path,
) -> None:
    bad_repair = _repair_manifest_payload()
    bad_repair["strict_limits"]["repair_count"] = 5

    report = _build(tmp_path, repair_manifest=bad_repair)

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("repair manifest" in failure for failure in report["failures"])
    assert report["summary"]["legacy_full_alignment_context"] == "UNRESOLVED"


@pytest.mark.parametrize(
    "field",
    [
        "needs_phase1b_conversion_count",
        "raw_only_count",
        "invalid_manifest_count",
        "source_hash_mismatch_count",
        "definition_join_mismatch_count",
        "raw_schema_failure_count",
        "required_schema_exception_failure_count",
    ],
)
def test_market_alignment_defects_fail_closed(tmp_path: Path, field: str) -> None:
    bad_alignment = _alignment_payload("ES")
    bad_alignment[field] = 1

    report = _build(tmp_path, alignment_overrides={"ES": bad_alignment})

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("ES expected-only" in failure for failure in report["failures"])
    assert report["summary"]["raw_row_parity_and_conversion_ready"] is False


def test_summary_count_defects_fail_closed(tmp_path: Path) -> None:
    bad_summary = copy.deepcopy(_phase1ab_summary_payload())
    bad_summary["phase1b"]["summary_counts"]["fail_market_reports"] = 1

    report = _build(tmp_path, phase1ab_summary=bad_summary)

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("summary" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    reports_root = _base_repo(tmp_path)

    exit_code = phase1b.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        phase1b.REPORT_JSON,
        phase1b.REPORT_MD,
    ]
    payload = json.loads((reports_root / phase1b.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["raw_row_parity_and_conversion_ready"] is True
    assert payload["non_approval"]["phase1b_conversion_executed"] is False
    assert payload["non_approval"]["raw_dbn_alignment_audit_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase1b.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
