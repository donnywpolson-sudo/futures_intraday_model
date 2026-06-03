from pipeline.common.config import RootConfig
from pipeline.orchestration.stage_plan import build_stage_plan, normalize_start_stage


def test_stage_plan_from_causally_gated_marks_1_to_8_skipped():
    plan = build_stage_plan("causally_gated_normalized", RootConfig())
    assert [r["status"] for r in plan[:8]] == ["SKIPPED_CHECKPOINT"] * 8
    assert plan[8]["stage_num"] == 9
    assert plan[8]["status"] == "PENDING"


def test_stage_plan_accepts_casually_normalized_alias():
    assert normalize_start_stage("casually normalized") == "causally_gated_normalized"

