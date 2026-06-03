import json

from pipeline.audit import pipeline_coverage
from pipeline.audit.run_manifest import write_run_manifest
from pipeline.common.config import RootConfig


def test_pipeline_coverage_report_includes_all_27_stages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline_coverage, "_module_exists", lambda path: True)
    monkeypatch.setattr(pipeline_coverage, "_represented_in_manifest", lambda key: True)
    (tmp_path / "tests").mkdir()
    for name in [
        "test_stage_raw_manifest.py", "test_stage_validation_to_validated.py", "test_stage_session_normalization.py",
        "test_stage_causal_gating.py", "test_stage_labels.py", "test_stage_baseline_features.py",
        "test_stage_column_registry.py", "test_stage_feature_expansion.py", "test_walkforward_contract.py",
        "test_full_research_integration.py", "test_oos_predictions.py", "test_acceptance_gate.py",
        "test_train_only_selection.py", "test_cli_integration.py",
    ]:
        (tmp_path / "tests" / name).write_text("def test_placeholder(): pass\n", encoding="utf-8")
    report = pipeline_coverage.build_coverage_report("configs/alpha_tiered.yaml")
    assert len(report["stages"]) == 27
    assert {s["name"] for s in report["stages"]} == {s.name for s in pipeline_coverage.stage_catalog()}
    assert (tmp_path / "reports" / "validation" / "pipeline_coverage_report.json").exists()
    assert (tmp_path / "reports" / "validation" / "pipeline_coverage_summary.csv").exists()


def test_pipeline_coverage_strict_fails_when_required_module_missing(monkeypatch):
    monkeypatch.setattr(pipeline_coverage, "_module_exists", lambda path: False if path != "external" else True)
    report = pipeline_coverage.build_coverage_report("configs/alpha_tiered.yaml")
    assert any(s["status"] == "FAIL" for s in report["stages"])


def test_run_manifest_includes_all_27_stages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = write_run_manifest("r1", RootConfig(), files=[], audit_paths={"output": "out/backtest_results.parquet", "oos_predictions": "out/oos_predictions.parquet", "execution_trace": "out/execution_trace_report.json", "metrics": "reports/metrics/m.json", "stress": "reports/stress/s.json", "acceptance": "reports/acceptance/a.json", "selector": "artifacts/selectors/s.json", "scaler": "artifacts/scalers/sc.json"})
    assert len(payload["stages"]) == 27
    assert {s["stage_name"] for s in payload["stages"]} == {s.name for s in pipeline_coverage.stage_catalog()}
    assert all(s["output_paths"] or s["external_contract"] for s in payload["stages"])
