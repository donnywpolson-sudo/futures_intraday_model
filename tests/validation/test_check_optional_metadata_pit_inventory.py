from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.validation import check_optional_metadata_pit_inventory as gate
from scripts.validation import check_phase2_460_audit_readiness as scope_gate


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_parquet(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({column: pa.array(["x"]) for column in columns})
    pq.write_table(table, path)


BASE_COLUMNS = [
    "ts",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "status_action_name",
    "status_stale",
    "stat_open_interest",
    "stat_open_interest_ts_event",
    "stat_open_interest_source_file",
    "statistics_stale",
    "source_path",
    "source_file_hash",
    "bars_until_roll",
    "roll_window_flag",
    "causal_invalid_reason",
    "feature_return_1m",
]


def _fixture(
    tmp_path: Path,
    *,
    pairs: list[tuple[str, int]] | None = None,
    columns: list[str] | None = None,
) -> dict[str, Path]:
    pairs = pairs or [("ES", 2020), ("CL", 2021)]
    columns = columns or BASE_COLUMNS
    data_manifest_path = tmp_path / "configs" / "data_manifest.yaml"
    canonical_root = tmp_path / scope_gate.CANONICAL_ROOT_REL
    reports_root = tmp_path / scope_gate.REPORTS_ROOT_REL
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    build_script = tmp_path / "scripts" / "phase2_causal_base" / "build_causal_base_data.py"
    _write_text(
        data_manifest_path,
        "\n".join(["canonical_paths:", f"  causal_parquet_pattern: {scope_gate.TARGET_CANONICAL_PATTERN}"]),
    )
    _write_text(profile_config, "default_profile: tier_3_research\n")
    _write_text(build_script, "print('builder')\n")
    for market, year in pairs:
        _write_parquet(canonical_root / market / f"{year}.parquet", columns)
    _write_json(
        reports_root / "causal_base_manifest.json",
        {
            "status": "PASS",
            "generated_at": "2026-06-30T00:00:00Z",
            "git_commit": "current-head",
            "script_hash": scope_gate.sha256_file(build_script),
            "config_hash": scope_gate.sha256_file(profile_config),
            "output_root": scope_gate.CANONICAL_ROOT_REL,
            "reports_root": scope_gate.REPORTS_ROOT_REL,
            "requested_market_years": [{"market": market, "year": year} for market, year in pairs],
            "outputs": [{"market": market, "year": year} for market, year in pairs],
        },
    )
    _write_json(
        reports_root / "causal_base_validation.json",
        {
            "status": "PASS",
            "files": [{"market": market, "year": year} for market, year in pairs],
            "summary": {
                "file_count": len(pairs),
                "pass_count": len(pairs),
                "fail_count": 0,
                "local_trade_ohlcv_gap_gate_status": "NOT_RUN",
            },
        },
    )
    return {
        "repo_root": tmp_path,
        "data_manifest_path": data_manifest_path,
        "canonical_root": canonical_root,
        "reports_root": reports_root,
        "phase2_manifest_path": reports_root / "causal_base_manifest.json",
        "phase2_validation_path": reports_root / "causal_base_validation.json",
        "profile_config_path": profile_config,
        "build_script_path": build_script,
    }


def _evaluate(
    paths: dict[str, Path],
    *,
    expected_count: int = 2,
    feature_cols: list[str] | None = None,
):
    return gate.evaluate_inventory(
        repo_root=paths["repo_root"],
        data_manifest_path=paths["data_manifest_path"],
        canonical_root=paths["canonical_root"],
        reports_root=paths["reports_root"],
        phase2_manifest_path=paths["phase2_manifest_path"],
        phase2_validation_path=paths["phase2_validation_path"],
        profile_config_path=paths["profile_config_path"],
        build_script_path=paths["build_script_path"],
        expected_count=expected_count,
        feature_cols=feature_cols or ["feature_return_1m"],
        git_head="current-head",
        staged_names=[],
        scoped_status_lines=[],
        generated_at_utc="2026-06-30T00:00:00Z",
    )


def test_classifies_representative_columns_and_blocks_optional_metadata(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path))

    assert report["summary"]["status"] == gate.STATUS_GO
    classifications = report["classifications"]
    assert classifications["feature_return_1m"] == gate.CLASS_FEATURE_ALLOWED
    assert classifications["status_action_name"] == gate.CLASS_PIT_NOT_VERIFIED
    assert classifications["stat_open_interest"] == gate.CLASS_PIT_NOT_VERIFIED
    assert classifications["stat_open_interest_ts_event"] == gate.CLASS_PIT_NOT_VERIFIED
    assert classifications["stat_open_interest_source_file"] == gate.CLASS_SOURCE_LINEAGE
    assert classifications["statistics_stale"] == gate.CLASS_PIT_NOT_VERIFIED
    assert classifications["source_path"] == gate.CLASS_SOURCE_LINEAGE
    assert classifications["bars_until_roll"] == gate.CLASS_FORBIDDEN_FEATURE
    assert classifications["open"] == gate.CLASS_AUDIT_ONLY
    assert report["summary"]["pit_not_verified_count"] > 0
    assert report["warnings"][0]["code"] == gate.WARN_OPTIONAL_METADATA_BLOCKED


def test_fails_when_unknown_column_is_unclassified(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, columns=[*BASE_COLUMNS, "mystery_optional_vendor_metric"])

    report = _evaluate(paths)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert "mystery_optional_vendor_metric" in report["unclassified_columns"]
    assert any(check["name"] == "all_columns_classified" for check in report["checks"] if check["status"] == "FAIL")


def test_fails_when_blocked_column_is_in_feature_registry(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path), feature_cols=["feature_return_1m", "stat_open_interest"])

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert "stat_open_interest" in report["blocked_feature_columns"]
    assert any(
        check["name"] == "feature_registry_no_forbidden_columns"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_fails_when_scope_gate_rejects_forbidden_rows(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, pairs=[("ES", 2020), ("6M", 2012), ("CL", 2025)])

    report = _evaluate(paths, expected_count=3)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(check["name"] == "scope_gate_passed" for check in report["checks"] if check["status"] == "FAIL")


def test_fails_when_scope_count_is_wrong(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path), expected_count=3)

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert any(check["name"] == "scope_gate_passed" for check in report["checks"] if check["status"] == "FAIL")
