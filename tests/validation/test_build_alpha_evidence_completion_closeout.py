from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import build_alpha_evidence_completion_closeout as closeout


def _build_default(*, write_reports: bool = False) -> dict[str, object]:
    return closeout.build_alpha_evidence_completion_closeout(
        repo_root=Path("."),
        generated_at_utc="2026-07-09T04:00:00+00:00",
        write_reports=write_reports,
    )


def _bucket(result: dict[str, object], bucket_id: str) -> dict[str, object]:
    rows = result["bucket_dispositions"]
    assert isinstance(rows, list)
    return next(row for row in rows if isinstance(row, dict) and row["bucket_id"] == bucket_id)


def test_terminal_fails_force_terminal_no_alpha_verdict() -> None:
    result = _build_default()

    assert result["verdict"] == closeout.CLOSEOUT_VERDICT
    assert result["modeling_pause_required"] is True
    assert result["future_modeling_allowed"] is False
    assert result["future_evidence_work_allowed"] is True
    assert result["promotion_allowed"] is False
    assert result["bucket_count"] == 23
    assert result["bucket_status_counts"] == {
        closeout.FAIL: 6,
        closeout.MISSING: 11,
        closeout.PASS: 6,
    }
    assert result["terminal_fail_count"] == 5
    assert _bucket(result, "baseline_no_trade")["closeout_classification"] == "terminal_fail"
    assert _bucket(result, "baseline_random_entry_null")["closeout_classification"] == "terminal_fail"
    assert (
        _bucket(result, "statistical_probabilistic_sharpe")["closeout_classification"]
        == "terminal_fail"
    )
    assert (
        _bucket(result, "stability_fold_market_year_session")["closeout_classification"]
        == "terminal_fail"
    )
    assert _bucket(result, "execution_cost_stress")["closeout_classification"] == "terminal_fail"


def test_missing_execution_evidence_remains_blocking() -> None:
    result = _build_default()

    for bucket_id in [
        "execution_delay_stress",
        "execution_capacity",
        "execution_liquidity_window",
        "execution_spread_slippage",
        "execution_partial_fills_rejects",
    ]:
        row = _bucket(result, bucket_id)
        assert row["source_status"] == closeout.MISSING
        assert row["closeout_classification"] == "missing_required_evidence"
        assert row["blocks_current_line"] is True


def test_diagnostic_pass_buckets_do_not_override_terminal_fails() -> None:
    result = _build_default()

    for bucket_id in [
        "baseline_cost_only",
        "baseline_simple_trend",
        "baseline_simple_mean_reversion",
        "statistical_bootstrap_ci",
        "stability_parameter",
        "execution_turnover",
    ]:
        row = _bucket(result, bucket_id)
        assert row["source_status"] == closeout.PASS
        assert row["closeout_classification"] == "diagnostic_pass_only"
        assert row["blocked_by_terminal_fail"] is True
        assert row["blocks_current_line"] is False
    assert result["verdict"] == closeout.CLOSEOUT_VERDICT
    assert result["future_modeling_allowed"] is False


def test_non_terminal_fail_is_not_actionable_for_current_line() -> None:
    result = _build_default()

    row = _bucket(result, "stability_regime_breakdowns")

    assert row["source_status"] == closeout.FAIL
    assert row["closeout_classification"] == "not_actionable_for_current_line"
    assert row["blocks_current_line"] is True


def test_missing_matrix_input_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(closeout.CloseoutError, match="required matrix input missing"):
        closeout.build_alpha_evidence_completion_closeout(
            repo_root=Path("."),
            matrix_path=tmp_path / "missing_matrix.json",
            write_reports=False,
        )


def test_cli_writes_only_expected_files_under_requested_report_root(tmp_path: Path, capsys) -> None:
    report_root = tmp_path / "alpha_evidence_completion_closeout"

    exit_code = closeout.main(["--report-root", str(report_root)])
    stdout = capsys.readouterr().out

    assert exit_code == 0
    assert closeout.CLOSEOUT_VERDICT in stdout
    assert sorted(path.name for path in report_root.iterdir()) == sorted(closeout.EXPECTED_OUTPUT_FILES)
    written = json.loads(
        (report_root / "alpha_evidence_completion_closeout.json").read_text(encoding="utf-8")
    )
    assert written["bucket_count"] == 23
    assert written["bucket_status_counts"] == {
        closeout.FAIL: 6,
        closeout.MISSING: 11,
        closeout.PASS: 6,
    }
    assert written["verdict"] == closeout.CLOSEOUT_VERDICT
    assert written["promotion_allowed"] is False
