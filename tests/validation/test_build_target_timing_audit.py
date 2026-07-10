from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from scripts.pipeline_gates import file_sha256
from scripts.validation import build_target_timing_audit as audit


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _base_label_frame(market: str, year: int, rows: int = 70) -> pd.DataFrame:
    ts = pd.Series(pd.date_range(f"{year}-01-02T00:00:00Z", periods=rows, freq="min"))
    valid_30m = pd.Series(range(rows)).le(rows - audit.PRIMARY_EXIT_OFFSET_BARS - 1)
    valid_60m = pd.Series(range(rows)).le(rows - audit.ROBUSTNESS_EXIT_OFFSET_BARS - 1)
    return pd.DataFrame(
        {
            "ts": ts,
            "market": market,
            "year": year,
            "session_segment_id": f"{market}_{year}_session",
            "label_semantics": audit.LABEL_SEMANTICS_ID,
            "target_30m_valid": valid_30m,
            "target_60m_valid": valid_60m,
            "target_entry_ts_30m": ts.shift(-audit.ENTRY_OFFSET_BARS).where(valid_30m),
            "target_exit_ts_30m": ts.shift(-audit.PRIMARY_EXIT_OFFSET_BARS).where(valid_30m),
            "target_entry_ts_60m": ts.shift(-audit.ENTRY_OFFSET_BARS).where(valid_60m),
            "target_exit_ts_60m": ts.shift(-audit.ROBUSTNESS_EXIT_OFFSET_BARS).where(valid_60m),
            "target_valid": valid_30m,
            "feature_safe": 1.0,
        }
    )


def _base_feature_frame(label_frame: pd.DataFrame) -> pd.DataFrame:
    return label_frame[["ts", "market", "year", "session_segment_id", "feature_safe"]].copy()


def _write_fixture(
    tmp_path: Path,
    *,
    mutate_label: Callable[[pd.DataFrame], None] | None = None,
    mutate_feature: Callable[[pd.DataFrame], None] | None = None,
    feature_cols: list[str] | None = None,
    markets: tuple[str, ...] = audit.EXPECTED_MARKETS,
    years: tuple[int, ...] = audit.EXPECTED_YEARS,
) -> dict[str, Path]:
    label_root = tmp_path / "data" / "labeled"
    feature_root = tmp_path / "data" / "feature_matrices"
    feature_records: list[dict[str, object]] = []
    label_records: list[dict[str, object]] = []
    input_hashes: dict[str, str] = {}
    output_hashes: dict[str, str] = {}

    for market, year in audit.expected_pairs(markets, years):
        label_frame = _base_label_frame(market, year)
        if mutate_label is not None:
            mutate_label(label_frame)
        feature_frame = _base_feature_frame(label_frame)
        if mutate_feature is not None:
            mutate_feature(feature_frame)
        label_path = label_root / market / f"{year}.parquet"
        feature_path = feature_root / market / f"{year}.parquet"
        label_path.parent.mkdir(parents=True, exist_ok=True)
        feature_path.parent.mkdir(parents=True, exist_ok=True)
        label_frame.to_parquet(label_path, index=False)
        feature_frame.to_parquet(feature_path, index=False)
        label_hash = file_sha256(label_path)
        feature_hash = file_sha256(feature_path)
        label_rel = audit.rel(label_path, tmp_path)
        feature_rel = audit.rel(feature_path, tmp_path)
        input_hashes[label_rel] = label_hash
        output_hashes[feature_rel] = feature_hash
        label_records.append(
            {
                "active_path": label_rel,
                "active_sha256": label_hash,
                "staged_sha256": label_hash,
                "active_rows": len(label_frame),
                "market": market,
                "year": year,
            }
        )
        feature_records.append(
            {
                "path": feature_rel,
                "sha256": feature_hash,
                "staged_sha256": feature_hash,
                "rows": len(feature_frame),
            }
        )

    feature_cols_path = _write_json(feature_root / "feature_cols.json", feature_cols or ["feature_safe"])
    target_cols_path = _write_json(feature_root / "target_cols.json", ["target_30m_valid"])
    feature_records.extend(
        [
            {"path": audit.rel(feature_cols_path, tmp_path), "sha256": file_sha256(feature_cols_path)},
            {"path": audit.rel(target_cols_path, tmp_path), "sha256": file_sha256(target_cols_path)},
        ]
    )

    feature_manifest = _write_json(
        tmp_path / "reports" / "features" / "baseline_feature_manifest.json",
        {
            "status": "PASS",
            "failure_count": 0,
            "feature_cols": feature_cols or ["feature_safe"],
            "feature_audit_gate": {"status": "PASS", "failure_count": 0},
            "forbidden_feature_leakage_failures": [],
            "input_file_hashes": input_hashes,
            "output_file_hashes": output_hashes,
        },
    )
    feature_hashes = _write_json(
        tmp_path / "reports" / "features" / "post_active_feature_hashes.json",
        {
            "status": audit.FEATURE_PLACEMENT_STATUS,
            "scope": {
                "markets": list(markets),
                "years": list(years),
                "parquet_count": len(audit.expected_pairs(markets, years)),
            },
            "records": feature_records,
            "active_tree_hashes_after": output_hashes,
        },
    )
    label_hashes = _write_json(
        tmp_path / "reports" / "labels" / "post_replacement_hashes.json",
        {
            "status": audit.LABEL_PLACEMENT_STATUS,
            "label_semantics_id": audit.LABEL_SEMANTICS_ID,
            "scope": {
                "markets": list(markets),
                "years": list(years),
                "file_count": len(audit.expected_pairs(markets, years)),
            },
            "records": label_records,
        },
    )
    return {
        "label_root": label_root,
        "feature_root": feature_root,
        "feature_manifest": feature_manifest,
        "feature_hashes": feature_hashes,
        "label_hashes": label_hashes,
        "reports_root": tmp_path / "reports" / "target_timing",
    }


def _build_report(tmp_path: Path, **fixture_kwargs: object) -> dict[str, object]:
    paths = _write_fixture(tmp_path, **fixture_kwargs)
    return audit.build_report(
        repo_root=tmp_path,
        label_root=paths["label_root"],
        feature_root=paths["feature_root"],
        feature_manifest_path=paths["feature_manifest"],
        feature_placement_hashes_path=paths["feature_hashes"],
        label_placement_hashes_path=paths["label_hashes"],
        reports_root=paths["reports_root"],
        markets=audit.EXPECTED_MARKETS,
        years=audit.EXPECTED_YEARS,
    )


def test_target_timing_audit_passes_clean_fixture(tmp_path: Path) -> None:
    report = _build_report(tmp_path)
    assert report["status"] == audit.PASS_STATUS
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["same_session_30m_violations"] == 0
    assert report["summary"]["same_session_60m_violations"] == 0
    assert report["summary"]["completed_bar_convention_assumed"] is True


def test_target_timing_audit_writes_reports(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path)
    exit_code = audit.main(
        [
            "--repo-root",
            str(tmp_path),
            "--label-root",
            paths["label_root"].as_posix(),
            "--feature-root",
            paths["feature_root"].as_posix(),
            "--feature-manifest",
            paths["feature_manifest"].as_posix(),
            "--feature-placement-hashes",
            paths["feature_hashes"].as_posix(),
            "--label-placement-hashes",
            paths["label_hashes"].as_posix(),
            "--reports-root",
            paths["reports_root"].as_posix(),
        ]
    )
    assert exit_code == 0
    assert (paths["reports_root"] / "target_timing_audit.json").exists()
    assert (paths["reports_root"] / "target_timing_audit.md").exists()


def test_entry_at_feature_timestamp_fails(tmp_path: Path) -> None:
    def mutate(label_frame: pd.DataFrame) -> None:
        label_frame.loc[0, "target_entry_ts_30m"] = label_frame.loc[0, "ts"]

    report = _build_report(tmp_path, mutate_label=mutate)
    assert report["status"] == audit.FAIL_STATUS
    assert any("entry_30m_not_after_ts" in failure for failure in report["failures"])


def test_wrong_exit_offsets_fail(tmp_path: Path) -> None:
    def mutate(label_frame: pd.DataFrame) -> None:
        label_frame.loc[0, "target_exit_ts_30m"] = label_frame.loc[30, "ts"]
        label_frame.loc[0, "target_exit_ts_60m"] = label_frame.loc[60, "ts"]

    report = _build_report(tmp_path, mutate_label=mutate)
    assert report["status"] == audit.FAIL_STATUS
    assert any("exit_30m_offset_mismatches" in failure for failure in report["failures"])
    assert any("exit_60m_offset_mismatches" in failure for failure in report["failures"])


def test_session_crossing_valid_target_fails(tmp_path: Path) -> None:
    def mutate(label_frame: pd.DataFrame) -> None:
        label_frame.loc[10:20, "session_segment_id"] = "new_session"

    report = _build_report(tmp_path, mutate_label=mutate)
    assert report["status"] == audit.FAIL_STATUS
    assert any("same_session_30m_violations" in failure for failure in report["failures"])
    assert any("same_session_60m_violations" in failure for failure in report["failures"])


def test_feature_row_mismatch_fails(tmp_path: Path) -> None:
    def mutate(feature_frame: pd.DataFrame) -> None:
        feature_frame.loc[0, "session_segment_id"] = "wrong_session"

    report = _build_report(tmp_path, mutate_feature=mutate)
    assert report["status"] == audit.FAIL_STATUS
    assert any("row key mismatches" in failure for failure in report["failures"])


def test_forbidden_feature_name_fails(tmp_path: Path) -> None:
    report = _build_report(tmp_path, feature_cols=["feature_safe", "target_ret_30m"])
    assert report["status"] == audit.FAIL_STATUS
    assert report["feature_name_gate"]["forbidden_feature_count"] == 1


def test_scope_outside_tier1_core_fails(tmp_path: Path) -> None:
    paths = _write_fixture(tmp_path, markets=("ES",), years=(2024,))
    report = audit.build_report(
        repo_root=tmp_path,
        label_root=paths["label_root"],
        feature_root=paths["feature_root"],
        feature_manifest_path=paths["feature_manifest"],
        feature_placement_hashes_path=paths["feature_hashes"],
        label_placement_hashes_path=paths["label_hashes"],
        reports_root=paths["reports_root"],
        markets=("ES",),
        years=(2024,),
    )
    assert report["status"] == audit.FAIL_STATUS
    assert any("scope markets must be exactly" in failure for failure in report["failures"])
