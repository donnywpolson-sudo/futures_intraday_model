from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import build_master_audit_phase1a_reconciliation as phase1a


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, text: str = "ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _registry_row() -> dict[str, object]:
    return {
        "request_id": "request-1",
        "dataset": "GLBX.MDP3",
        "schema": "ohlcv-1m",
        "symbol": "ES.v.0",
        "stype_in": "continuous",
        "stype_out": "instrument_id",
        "start": "2024-01-01",
        "end": "2025-01-01",
        "output_path": "data/dbn/ohlcv_1m/ES/2024/2024-01-01_2025-01-01.dbn.zst",
        "request_timestamp": "2026-07-06T00:00:00+00:00",
        "approval_id": "legacy_unrecorded_approval",
        "plan_hash": "hash-1",
        "current_file_sha256": "current-hash",
        "original_file_sha256": None,
        "provenance_status": "post_transfer_hash_only",
        "reproducibility_status": "partially_reproducible",
        "validity_status": "valid_current_artifact_if_current_hash_matches",
    }


def _write_registry(path: Path, row: dict[str, object] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = row or _registry_row()
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _coverage_payload(
    *,
    status: str = "PASS",
    expected_archive_count: int = phase1a.EXPECTED_ARCHIVE_COUNT,
    missing_archive_count: int = 0,
    missing_manifest_count: int = 0,
    invalid_manifest_count: int = 0,
    required_schema_exception_failure_count: int = 0,
) -> dict[str, object]:
    return {
        "status": status,
        "profile": "phase1ab_33markets_2010_2026",
        "audit_end": "2026-06-13",
        "expected_archive_count": expected_archive_count,
        "missing_archive_count": missing_archive_count,
        "missing_manifest_count": missing_manifest_count,
        "invalid_manifest_count": invalid_manifest_count,
        "required_schema_exception_count": 1,
        "required_schema_exception_failure_count": required_schema_exception_failure_count,
    }


def _summary_payload(coverage: dict[str, object]) -> dict[str, object]:
    return {
        "status": "PASS",
        "phase1a": {
            "status": coverage["status"],
            "expected_archives": coverage["expected_archive_count"],
            "missing_archives": coverage["missing_archive_count"],
            "missing_manifests": coverage["missing_manifest_count"],
            "invalid_manifests": coverage["invalid_manifest_count"],
            "required_exceptions": coverage["required_schema_exception_count"],
            "exception_failures": coverage["required_schema_exception_failure_count"],
        },
        "phase1b": {"status": "PASS"},
    }


def _write_sources(repo_root: Path, coverage: dict[str, object] | None = None) -> None:
    coverage_payload = coverage or _coverage_payload()
    _write_registry(repo_root / phase1a.PHASE1A_REGISTRY)
    _write_json(repo_root / phase1a.PHASE1A_COVERAGE, coverage_payload)
    _write_json(repo_root / phase1a.PHASE1AB_SUMMARY, _summary_payload(coverage_payload))
    _write_text(repo_root / phase1a.REQUIRED_EXCEPTIONS_CONFIG, "exceptions: []\n")


def test_phase1a_pass_from_registry_and_archive_coverage(tmp_path: Path) -> None:
    _write_sources(tmp_path)

    report = phase1a.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / phase1a.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase1a.PASS_STATUS
    assert report["summary"]["phase1a_source_lineage_ready"] is True
    assert report["summary"]["expected_archive_count"] == phase1a.EXPECTED_ARCHIVE_COUNT
    assert report["summary"]["registry_validation_failure_count"] == 0
    assert report["summary"]["original_delivery_reproducibility_ready"] is False
    assert report["summary"]["post_transfer_hash_only_evidence"] is True
    assert all(value is False for value in report["non_approval"].values())


def test_missing_registry_fails_closed(tmp_path: Path) -> None:
    coverage = _coverage_payload()
    _write_json(tmp_path / phase1a.PHASE1A_COVERAGE, coverage)
    _write_json(tmp_path / phase1a.PHASE1AB_SUMMARY, _summary_payload(coverage))
    _write_text(tmp_path / phase1a.REQUIRED_EXCEPTIONS_CONFIG, "exceptions: []\n")

    report = phase1a.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / phase1a.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase1a.FAIL_STATUS
    assert report["summary"]["phase1a_source_lineage_ready"] is False
    assert any("missing Phase 1A acquisition registry" in failure for failure in report["failures"])


def test_failed_coverage_counts_fail_closed(tmp_path: Path) -> None:
    coverage = _coverage_payload(missing_manifest_count=1)
    _write_sources(tmp_path, coverage=coverage)

    report = phase1a.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / phase1a.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase1a.FAIL_STATUS
    assert any(
        "missing or invalid archive/manifest" in failure for failure in report["failures"]
    )


def test_required_exception_failures_fail_closed(tmp_path: Path) -> None:
    coverage = _coverage_payload(required_schema_exception_failure_count=1)
    _write_sources(tmp_path, coverage=coverage)

    report = phase1a.build_report(
        repo_root=tmp_path,
        reports_root=tmp_path / phase1a.DEFAULT_REPORTS_ROOT,
        generated_at_utc="2026-07-10T00:00:00Z",
        git_status_lines=[],
    )

    assert report["status"] == phase1a.FAIL_STATUS
    assert any("required-schema exception failures" in failure for failure in report["failures"])


def test_main_writes_exact_json_and_markdown_pair(tmp_path: Path) -> None:
    _write_sources(tmp_path)
    reports_root = tmp_path / phase1a.DEFAULT_REPORTS_ROOT

    exit_code = phase1a.main(
        [
            "--repo-root",
            str(tmp_path),
            "--reports-root",
            str(reports_root),
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in reports_root.iterdir()) == [
        phase1a.REPORT_JSON,
        phase1a.REPORT_MD,
    ]
    payload = json.loads((reports_root / phase1a.REPORT_JSON).read_text(encoding="utf-8"))
    assert payload["summary"]["phase1a_source_lineage_ready"] is True
