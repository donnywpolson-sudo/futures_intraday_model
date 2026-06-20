from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.validation.audit_phase2_candidate import audit_phase2_candidate


def _sha256(path: Path) -> str:
    from scripts.validation.audit_phase2_candidate import _file_sha256

    return _file_sha256(path)


def _write_raw_alignment(path: Path, *, markets: list[str] | None = None) -> Path:
    markets = markets or ["ES"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "stage": "raw_dbn_alignment_audit",
                "status": "PASS",
                "profile": "tier_3",
                "resolved_profile": "tier_3_research",
                "markets": markets,
                "years": [2024],
                "pre_availability_exemptions": [],
                "expected_market_year_count": len(markets),
                "missing_raw_count": 0,
                "needs_phase1b_conversion_count": 0,
                "missing_ohlcv_dbn_count": 0,
                "missing_definition_dbn_count": 0,
                "invalid_manifest_count": 0,
                "raw_schema_failure_count": 0,
                "source_hash_mismatch_count": 0,
                "definition_join_mismatch_count": 0,
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_candidate(path: Path, *, enriched: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": pd.Timestamp("2024-01-02T14:30:00Z"),
        "market": path.parent.name,
        "year": int(path.stem),
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "volume": 1,
    }
    if enriched:
        payload.update(
            {
                "status_missing": False,
                "status_stale": False,
                "status_action": 7,
                "statistics_missing": False,
                "statistics_stale": False,
                "stat_opening_price": 1.0,
            }
        )
    pd.DataFrame([payload]).to_parquet(path, index=False)
    return path


def _write_manifest(
    path: Path,
    *,
    output_root: Path,
    output_paths: list[Path],
    status: str = "PASS",
    warning_count: int = 0,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "stage": "causal_base",
                "status": status,
                "profile": "tier_3",
                "resolved_profile": "tier_3_research",
                "output_root": output_root.as_posix(),
                "warning_count": warning_count,
                "failure_count": 0,
                "summary": {"warn_count": warning_count, "fail_count": 0},
                "output_file_hashes": {p.as_posix(): _sha256(p) for p in output_paths},
                "outputs": [
                    {
                        "market": p.parent.name,
                        "year": int(p.stem),
                        "status": status,
                        "warning_count": warning_count,
                        "failure_count": 0,
                        "failures": [],
                    }
                    for p in output_paths
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _audit(tmp_path: Path, *, markets: list[str] | None = None, status: str = "PASS", warning_count: int = 0):
    output_root = tmp_path / "data" / "causal_candidate"
    markets = markets or ["ES"]
    output_paths = [_write_candidate(output_root / market / "2024.parquet") for market in markets]
    raw_alignment = _write_raw_alignment(tmp_path / "reports" / "raw.json", markets=markets)
    manifest = _write_manifest(
        tmp_path / "reports" / "candidate" / "causal_base_manifest.json",
        output_root=output_root,
        output_paths=output_paths,
        status=status,
        warning_count=warning_count,
    )
    return audit_phase2_candidate(
        causal_root=output_root,
        manifest_path=manifest,
        raw_alignment_path=raw_alignment,
        expected_count=len(markets),
    )


def test_phase2_candidate_audit_passes_complete_enriched_candidate(tmp_path: Path) -> None:
    report = _audit(tmp_path)

    assert report["status"] == "PASS"
    assert report["eligible_candidate_output_count"] == 1


def test_phase2_candidate_audit_fails_missing_output(tmp_path: Path) -> None:
    output_root = tmp_path / "data" / "causal_candidate"
    es_path = _write_candidate(output_root / "ES" / "2024.parquet")
    raw_alignment = _write_raw_alignment(
        tmp_path / "reports" / "raw.json",
        markets=["ES", "CL"],
    )
    manifest = _write_manifest(
        tmp_path / "reports" / "candidate" / "causal_base_manifest.json",
        output_root=output_root,
        output_paths=[es_path],
    )

    report = audit_phase2_candidate(
        causal_root=output_root,
        manifest_path=manifest,
        raw_alignment_path=raw_alignment,
        expected_count=2,
    )

    assert report["status"] == "FAIL"
    assert report["missing_output_count"] == 1


def test_phase2_candidate_audit_fails_missing_enrichment_columns(tmp_path: Path) -> None:
    output_root = tmp_path / "data" / "causal_candidate"
    output_path = _write_candidate(output_root / "ES" / "2024.parquet", enriched=False)
    raw_alignment = _write_raw_alignment(tmp_path / "reports" / "raw.json")
    manifest = _write_manifest(
        tmp_path / "reports" / "candidate" / "causal_base_manifest.json",
        output_root=output_root,
        output_paths=[output_path],
    )

    report = audit_phase2_candidate(
        causal_root=output_root,
        manifest_path=manifest,
        raw_alignment_path=raw_alignment,
        expected_count=1,
    )

    assert report["status"] == "FAIL"
    assert report["missing_required_column_count"] == 1


def test_phase2_candidate_audit_fails_warn_manifest(tmp_path: Path) -> None:
    report = _audit(tmp_path, status="WARN", warning_count=1)

    assert report["status"] == "FAIL"
    assert any("manifest status" in failure for failure in report["failures"])
