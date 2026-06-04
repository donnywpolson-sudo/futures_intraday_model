from types import SimpleNamespace

from pipeline.validation.alpha_evidence import build_alpha_evidence_row
from pipeline.validation.leakage_report import build_leakage_audit_rows


def _cfg():
    return SimpleNamespace(
        walkforward=SimpleNamespace(walkforward_target="target_15m_ret", purge_target_overlap=True, embargo_bars=1),
        execution=SimpleNamespace(threshold_mode="fixed"),
    )


def test_alpha_evidence_rejected_positive_is_research_only():
    row = build_alpha_evidence_row(
        run_id="run_test",
        profile="tier_1_bare_minimum_alpha",
        stage_scope="baseline",
        expected_rows=1,
        verification_rows=[{"run_id": "run_test", "symbol": "ES", "split": "1", "pnl": 10.0, "gross_pnl": 12.0, "ic": 0.1}],
        artifact_rows=[{"run_id": "run_test", "symbol": "ES", "split": "1", "status": "OK", "acceptance_status": "REJECT"}],
    )

    assert row["net_pnl"] == 10.0
    assert row["cost_drag"] == 2.0
    assert row["conclusion"] == "WEAK_ALPHA_RESEARCH_ONLY"


def test_alpha_evidence_rejected_negative_is_no_alpha():
    row = build_alpha_evidence_row(
        run_id="run_test",
        profile="tier_1_bare_minimum_alpha",
        stage_scope="baseline",
        expected_rows=1,
        verification_rows=[{"run_id": "run_test", "symbol": "ES", "split": "1", "pnl": -1.0, "gross_pnl": 2.0}],
        artifact_rows=[{"run_id": "run_test", "symbol": "ES", "split": "1", "status": "OK", "acceptance_status": "REJECT"}],
    )

    assert row["conclusion"] == "NO_ALPHA_FOUND"


def test_leakage_audit_detects_train_test_overlap():
    rows = build_leakage_audit_rows(
        run_id="run_test",
        profile="tier_1_bare_minimum_alpha",
        config=_cfg(),
        splits=[([1, 2, 3], [3, 4])],
        verification_rows=[],
    )

    overlap = next(r for r in rows if r["check"] == "train_test_split_no_overlap")
    assert overlap["status"] == "FAIL"
    assert "overlapping row indexes" in overlap["reason"]
