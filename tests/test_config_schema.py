from pipeline.common.config import RootConfig


def test_config_schema_has_professional_sections():
    cfg = RootConfig()
    assert cfg.data.root == "data/validated"
    assert cfg.data.require_validated_files is True
    assert cfg.roll_policy.method == "volume_or_days_before_expiry"
    assert cfg.point_in_time.enabled is True
    assert cfg.leakage_audit.fail_on_error is True
    assert cfg.stress_tests.cost_multipliers == [1.0, 2.0, 3.0]
    assert cfg.acceptance_gate.min_oos_sharpe == 0.25
    assert cfg.deployment.mode == "research_only"
