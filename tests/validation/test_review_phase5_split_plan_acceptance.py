import json
from pathlib import Path

from scripts.pipeline_gates import file_sha256
from scripts.validation.review_phase5_split_plan_acceptance import (
    FAIL_STATUS,
    PASS_STATUS,
    build_report,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _base_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    repo_root = tmp_path
    split_plan_path = repo_root / "reports/wfa/fixture/split_plan.json"
    csv_path = repo_root / "reports/wfa/fixture/split_plan.csv"
    json_out = repo_root / "reports/wfa/fixture/split_plan_acceptance_report.json"
    md_out = repo_root / "reports/wfa/fixture/split_plan_acceptance_report.md"

    feature_manifest_path = repo_root / "reports/data_audit/current_state/active_feature_manifest.json"
    _write_json(feature_manifest_path, {"status": "PASS", "feature_count": 1})

    universe_path = repo_root / "reports/data_audit/universe.json"
    _write_json(
        universe_path,
        {
            "status": "PASS",
            "summary": {"audit_status_counts": {"usable": 1}},
            "market_years": [
                {
                    "market": "ES",
                    "year": 2024,
                    "audit_status": "usable",
                    "usable_for_wfa": True,
                    "final_decision": "fixture_usable",
                    "reason": "fixture usable",
                }
            ],
        },
    )

    fold = {
        "market": "ES",
        "fold_id": "ES_research_0001",
        "fold_number": 1,
        "year": 2024,
        "split_group": "research",
        "selection_allowed": True,
        "final_holdout": False,
        "is_final_holdout": False,
        "train_start": "2023-01-02T23:00:00+00:00",
        "train_end": "2024-01-02T21:43:00+00:00",
        "purged_train_end": "2024-01-02T20:58:00+00:00",
        "test_start": "2024-01-02T23:00:00+00:00",
        "test_end": "2024-02-01T21:43:00+00:00",
        "embargo_end": "2024-02-01T23:30:00+00:00",
        "train_rows_before_purge": 101,
        "train_rows_after_purge": 70,
        "purged_train_rows": 31,
        "test_rows": 30,
        "embargo_rows": 31,
        "purge_bars": 31,
        "resolved_purge_bars": 31,
        "embargo_bars": 31,
    }
    _write_json(
        split_plan_path,
        {
            "profile": "tier_1_core",
            "resolved_profile": "tier_1_research",
            "input_root": "data/feature_matrices",
            "markets": ["ES"],
            "years": [2024],
            "fold_count": 1,
            "fold_count_by_market": {"ES": 1},
            "failure_count": 0,
            "skipped_input_count": 0,
            "purge_policy": {
                "purge_bars": 31,
                "resolved_purge_bars": 31,
                "embargo_bars": 31,
            },
            "feature_manifest_gate": {
                "status": "PASS",
                "manifest_path": "reports/data_audit/current_state/active_feature_manifest.json",
                "manifest_hash": file_sha256(feature_manifest_path),
                "expected_output_root": "data/feature_matrices",
                "expected_resolved_profile": "tier_1_research",
                "failures": [],
            },
            "data_audit_universe": {
                "path": "reports/data_audit/universe.json",
                "file_hash": file_sha256(universe_path),
                "status_counts": {"usable": 1},
                "requires_usable_for_wfa": True,
            },
            "folds": [fold],
        },
    )
    _write_text(
        csv_path,
        "fold_id,market,fold_number\nES_research_0001,ES,1\n",
    )
    return repo_root, split_plan_path, csv_path, json_out, md_out


def _build_fixture_report(tmp_path: Path) -> dict:
    repo_root, split_plan_path, csv_path, json_out, md_out = _base_fixture(tmp_path)
    return build_report(
        repo_root=repo_root,
        split_plan_path=split_plan_path,
        csv_path=csv_path,
        json_out=json_out,
        md_out=md_out,
        expected_profile="tier_1_core",
        expected_resolved_profile="tier_1_research",
        expected_input_root="data/feature_matrices",
        expected_markets=["ES"],
        expected_years=[2024],
        expected_purge_bars=31,
        expected_embargo_bars=31,
        predictions_root=repo_root / "data/predictions",
        generated_at_utc="2026-07-06T00:00:00Z",
    )


def test_build_report_accepts_valid_split_plan_fixture(tmp_path: Path) -> None:
    report = _build_fixture_report(tmp_path)

    assert report["status"] == PASS_STATUS
    assert report["summary"]["fold_count"] == 1
    assert report["summary"]["prediction_file_count"] == 0
    assert [(check["name"], check["status"]) for check in report["checks"]] == [
        ("split_plan_files_exist", "PASS"),
        ("scope_matches_objective", "PASS"),
        ("fold_counts_match_manifest_and_csv", "PASS"),
        ("fold_chronology_positive_rows_and_purge_embargo", "PASS"),
        ("feature_manifest_gate_evidence", "PASS"),
        ("data_audit_universe_evidence", "PASS"),
        ("generated_artifact_scope", "PASS"),
    ]


def test_build_report_fails_when_fold_chronology_leaks_test_window(tmp_path: Path) -> None:
    repo_root, split_plan_path, csv_path, json_out, md_out = _base_fixture(tmp_path)
    payload = json.loads(split_plan_path.read_text(encoding="utf-8"))
    payload["folds"][0]["purged_train_end"] = "2024-01-02T23:30:00+00:00"
    _write_json(split_plan_path, payload)

    report = build_report(
        repo_root=repo_root,
        split_plan_path=split_plan_path,
        csv_path=csv_path,
        json_out=json_out,
        md_out=md_out,
        expected_profile="tier_1_core",
        expected_resolved_profile="tier_1_research",
        expected_input_root="data/feature_matrices",
        expected_markets=["ES"],
        expected_years=[2024],
        expected_purge_bars=31,
        expected_embargo_bars=31,
        predictions_root=repo_root / "data/predictions",
        generated_at_utc="2026-07-06T00:00:00Z",
    )

    assert report["status"] == FAIL_STATUS
    assert any("fold_chronology_positive_rows_and_purge_embargo" in item for item in report["failures"])
