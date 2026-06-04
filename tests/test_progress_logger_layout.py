from pipeline.audit.pipeline_coverage import stage_catalog
import run


def test_progress_logger_uses_project_layout_stage_catalog():
    expected = {stage.number: stage.name for stage in stage_catalog()}

    assert run.PipelineProgressLogger.STAGES == expected
    assert run.PipelineProgressLogger.STAGE_TOTAL == 27
    assert run.PipelineProgressLogger.STAGES[14] == "WFA SPLIT PLAN"
    assert run.PipelineProgressLogger.STAGES[27] == "STRATEGY ACCEPT / REJECT GATE"


def test_progress_logger_checkpoint_stage_mapping(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = run.PipelineProgressLogger("clean", "run_test")
    try:
        logger.set_context(start_stage="baseline_feature_matrix")
        assert logger.input_stage() == 12
        assert logger.wfa_stage() == 15
        assert logger.oos_stage() == 16
        assert logger.metrics_stage() == 18
        assert logger.acceptance_stage() == 19
        assert logger.feature_registry_stage() == 13

        logger.set_context(start_stage="expanded_feature_matrix")
        assert logger.input_stage() == 20
        assert logger.wfa_stage() == 24
        assert logger.oos_stage() == 25
        assert logger.metrics_stage() == 26
        assert logger.acceptance_stage() == 27
        assert logger.feature_registry_stage() == 22
    finally:
        logger.close()
