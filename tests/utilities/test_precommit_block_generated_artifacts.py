from __future__ import annotations

from scripts.utilities import precommit_block_generated_artifacts as blocker


def test_blocks_generated_report_and_build_paths() -> None:
    assert blocker.is_blocked("reports/visualizations/dashboard.html")
    assert blocker.is_blocked("live_chart/PYZ-00.pyz")
    assert blocker.is_blocked("live_chart/warn-LiveChartFeed.txt")
    assert blocker.is_blocked("live_chart/xref-LiveChartFeed.html")
    assert blocker.is_blocked("live_chart/localpycs/struct.pyc")
    assert blocker.is_blocked("dist/LiveChartFeed.exe")


def test_blocks_local_secret_and_env_files() -> None:
    assert blocker.is_blocked("api.env")
    assert blocker.is_blocked("databento.env")
    assert blocker.is_blocked("secrets/databento.env")
    assert blocker.is_blocked("databento_api_key.local")


def test_blocks_generated_data_suffixes() -> None:
    assert blocker.is_blocked("outputs/run/oos_predictions.parquet")
    assert blocker.is_blocked("reports/run/progress.jsonl")
    assert blocker.is_blocked("models/model.joblib")


def test_allows_source_docs_and_manifest_metadata() -> None:
    assert not blocker.is_blocked("README.md")
    assert not blocker.is_blocked("scripts/check_git_hygiene.py")
    assert not blocker.is_blocked("manifests/feature_hypotheses/trial_statuses.jsonl")
    assert not blocker.is_blocked("manifests/data_inventory.csv")
