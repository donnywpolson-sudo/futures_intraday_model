from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validation import build_master_audit_phase1b_reconciliation as phase1b


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _run_status_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_RUN_STATUS_INVENTORY",
        "summary": {
            "current_line_classification": "closed_no_alpha_evidence",
            "current_split_classification": "same_fold_rolling_retraining_research_only",
            "failure_count": 0,
        },
        "run_status_table": [
            {
                "audit_area": "Phase 1B",
                "run_status": "NOT_RUN",
                "detail_status": "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
                "evidence_state": "unknown",
                "accepted_evidence": [],
                "scope": "raw-to-normalized audit not executed here",
                "notes": ["No bounded Phase 1B master audit artifact was accepted."],
            },
            {
                "audit_area": "Phase 2",
                "run_status": "NOT_RUN",
                "detail_status": "NOT_RUN_NO_DIRECT_MASTER_AUDIT_EVIDENCE",
                "evidence_state": "unknown",
                "accepted_evidence": [],
                "scope": "causal/session audit not executed here",
                "notes": [],
            },
        ],
    }


def _overview_payload() -> dict[str, object]:
    return {"status": "PASS_MASTER_AUDIT_OVERVIEW_REPORT_ONLY", "summary": {"failure_count": 0}}


def _phase6_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE6_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase6_master_audit_status": "RUN_LIMITED_SCOPE_PHASE6_REPORT_ONLY_WFA_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _phase7_payload() -> dict[str, object]:
    return {
        "status": "PASS_MASTER_AUDIT_PHASE7_RECONCILIATION_REPORT_ONLY",
        "summary": {
            "failure_count": 0,
            "phase7_master_audit_status": "RUN_LIMITED_SCOPE_PREDICTION_ARTIFACT_RECONCILIATION",
            "model_trust_ready": False,
            "promotion_allowed": False,
        },
    }


def _phase1ab_summary_payload() -> dict[str, object]:
    return {
        "status": "PASS",
        "phase1b": {
            "status": "PASS",
            "mode": "one_market_batches_expected_only",
            "batch_root": phase1b.MARKET_ALIGNMENT_ROOT.as_posix(),
            "summary_counts": {
                "market_reports": 33,
                "missing_report_count": 0,
                "pass_market_reports": 33,
                "fail_market_reports": 0,
                "expected_market_year_count": 527,
                "raw_market_year_count": 527,
                "missing_status_dbn_count": 0,
                "missing_statistics_dbn_count": 0,
                "needs_phase1b_conversion_count": 0,
                "raw_only_count": 0,
                "invalid_manifest_count": 0,
                "source_hash_mismatch_count": 0,
                "definition_join_mismatch_count": 0,
                "raw_schema_failure_count": 0,
                "repair_manifest_failure_count": 0,
            },
        },
    }


def _alignment_payload(market: str) -> dict[str, object]:
    return {
        "status": "PASS",
        "profile": "phase1ab_33markets_2010_2026",
        "resolved_profile": "phase1ab_33markets_2010_2026",
        "expected_only": True,
        "market_year_include_list_applied": True,
        "expected_market_year_count": 17,
        "raw_market_year_count": 17,
        "ohlcv_dbn_market_year_count": 17,
        "definition_dbn_market_year_count": 17,
        "status_dbn_market_year_count": 17,
        "statistics_dbn_market_year_count": 17,
        "missing_raw_count": 0,
        "missing_ohlcv_dbn_count": 0,
        "missing_definition_dbn_count": 0,
        "source_hash_mismatch_count": 0,
        "raw_schema_failure_count": 0,
        "definition_join_status": "checked",
        "definition_join_mismatch_count": 0,
        "invalid_manifest_count": 0,
        "repair_manifest_status": "PASS",
        "repair_manifest_failure_count": 0,
        "failures": [],
        "raw_file_metrics": [
            {"market": market, "year": 2023},
            {"market": market, "year": 2024},
        ],
        "market_years": [{"market": market, "year": year} for year in range(2010, 2027)],
    }


def _include_payload(market: str) -> dict[str, object]:
    return {
        "market": market,
        "source": "test-fixture",
        "market_years": [{"market": market, "year": year} for year in range(2010, 2027)],
    }


def _base_repo(
    tmp_path: Path,
    *,
    alignment_overrides: dict[str, dict[str, object]] | None = None,
    include_overrides: dict[str, dict[str, object]] | None = None,
    broad_alignment: dict[str, object] | None = None,
    phase1ab_summary: dict[str, object] | None = None,
) -> dict[str, Path]:
    for name in ("MASTER_AUDIT.md", "CODEX_HANDOFF.md", "PROJECT_OUTLINE.md"):
        _write_text(tmp_path / name)
    _write_json(tmp_path / phase1b.DEFAULT_RUN_STATUS, _run_status_payload())
    _write_json(tmp_path / phase1b.DEFAULT_OVERVIEW, _overview_payload())
    _write_json(tmp_path / phase1b.DEFAULT_PHASE6, _phase6_payload())
    _write_json(tmp_path / phase1b.DEFAULT_PHASE7, _phase7_payload())
    _write_json(tmp_path / phase1b.PHASE1AB_SUMMARY, phase1ab_summary or _phase1ab_summary_payload())
    _write_json(tmp_path / phase1b.BROAD_ALIGNMENT, broad_alignment or {"status": "FAIL"})
    alignment_overrides = alignment_overrides or {}
    include_overrides = include_overrides or {}
    for market in phase1b.EXPECTED_MARKETS:
        _write_json(
            tmp_path / phase1b.market_alignment_path(market),
            alignment_overrides.get(market, _alignment_payload(market)),
        )
        _write_json(
            tmp_path / phase1b.market_include_path(market),
            include_overrides.get(market, _include_payload(market)),
        )
    return {"reports_root": tmp_path / phase1b.DEFAULT_REPORTS_ROOT}


def _build(
    tmp_path: Path,
    *,
    alignment_overrides: dict[str, dict[str, object]] | None = None,
    include_overrides: dict[str, dict[str, object]] | None = None,
    broad_alignment: dict[str, object] | None = None,
    phase1ab_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    paths = _base_repo(
        tmp_path,
        alignment_overrides=alignment_overrides,
        include_overrides=include_overrides,
        broad_alignment=broad_alignment,
        phase1ab_summary=phase1ab_summary,
    )
    return phase1b.build_report(
        repo_root=tmp_path,
        reports_root=paths["reports_root"],
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )


def test_phase1b_reconciliation_passes_limited_scope_without_parquet(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["status"] == phase1b.PASS_STATUS
    assert report["summary"]["phase1b_master_audit_status"] == "RUN_LIMITED_SCOPE_PHASE1B_RAW_DBN_RECONCILIATION"
    assert report["summary"]["scoped_market_year_count"] == 8
    assert report["summary"]["broad_phase1b_alignment_status"] == "FAIL"
    assert report["summary"]["broad_phase1b_accepted"] is False
    assert report["summary"]["phase2_accepted"] is False
    assert report["summary"]["raw_parquet_read_executed"] is False
    assert not list(tmp_path.glob("data/**/*.parquet"))


def test_broad_alignment_pass_fails_because_fail_must_be_preserved(tmp_path: Path) -> None:
    report = _build(tmp_path, broad_alignment={"status": "PASS"})

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("broad Phase 1B" in failure for failure in report["failures"])


def test_scoped_market_alignment_failure_fails_closed(tmp_path: Path) -> None:
    bad_alignment = _alignment_payload("ES")
    bad_alignment["source_hash_mismatch_count"] = 1

    report = _build(tmp_path, alignment_overrides={"ES": bad_alignment})

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("ES Phase 1B alignment" in failure for failure in report["failures"])


def test_missing_scoped_include_year_fails_closed(tmp_path: Path) -> None:
    bad_include = _include_payload("ZN")
    bad_include["market_years"] = [
        row for row in bad_include["market_years"] if row["year"] != 2024
    ]

    report = _build(tmp_path, include_overrides={"ZN": bad_include})

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("ZN include-list" in failure for failure in report["failures"])


def test_phase1ab_summary_failure_fails_closed(tmp_path: Path) -> None:
    bad_summary = copy.deepcopy(_phase1ab_summary_payload())
    bad_summary["phase1b"]["summary_counts"]["fail_market_reports"] = 1

    report = _build(tmp_path, phase1ab_summary=bad_summary)

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("Phase 1AB" in failure for failure in report["failures"])


def test_main_writes_only_json_and_markdown_reports(tmp_path: Path) -> None:
    paths = _base_repo(tmp_path)

    exit_code = phase1b.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(paths["reports_root"]),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in paths["reports_root"].iterdir()) == [
        phase1b.REPORT_JSON,
        phase1b.REPORT_MD,
    ]
    payload = json.loads((paths["reports_root"] / phase1b.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["non_approval"]["phase1b_conversion_executed"] is False
    assert payload["non_approval"]["raw_parquet_read_executed"] is False


def test_invalid_output_root_fails_closed(tmp_path: Path) -> None:
    _base_repo(tmp_path)

    report = phase1b.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / "data" / "bad",
        generated_at_utc="2026-07-09T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase1b.FAIL_STATUS
    assert any("invalid report output root" in failure for failure in report["failures"])
