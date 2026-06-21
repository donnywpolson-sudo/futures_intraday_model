from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.phase2_causal_base.build_causal_base_data as causal_base
from scripts.phase2_causal_base.build_causal_base_data import (
    LOCAL_TRADE_GAP_FAILED_STATUS,
    LOCAL_TRADE_GAP_VALIDATED_STATUS,
    OUTPUT_COLUMNS,
    build_phase2_readiness_report,
    discover_raw_inputs,
    filter_inputs_by_raw_alignment,
    load_causal_base_config,
    main as phase2_main,
    output_root_guard_failures,
    phase2_exit_code,
    profile_requires_local_trade_gap_gate,
    process_file,
    raw_alignment_guard_failures,
    raw_alignment_expected_market_years,
    resolve_profile_inputs,
    write_reports,
)


def _write_raw(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_raw_with_datetime_index(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.index = pd.DatetimeIndex(df.pop("ts"), name="ts")
    df.to_parquet(path, index=True)


def _write_profile_config(
    path: Path,
    *,
    synthetic_pct: float = 2.0,
    degraded_pct: float = 1.0,
    roll_pct: float = 1.0,
    synthetic_action: str = "warn",
    tier0_markets: list[str] | None = None,
    sparse_markets: list[str] | None = None,
    sparse_roll_window_minutes: int | None = None,
    vendor_trusted_markets: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tier0_markets = tier0_markets or ["ES"]
    sparse_markets = sparse_markets or []
    vendor_trusted_markets = vendor_trusted_markets or []
    causal_base_lines = []
    if sparse_markets or vendor_trusted_markets:
        causal_base_lines = ["causal_base:"]
    if sparse_markets:
        causal_base_lines.append(
            "  sparse_trade_derived_ohlcv_markets: ["
            + ", ".join(sparse_markets)
            + "]"
        )
        if sparse_roll_window_minutes is not None:
            causal_base_lines.append(
                f"  sparse_trade_derived_roll_window_minutes: {sparse_roll_window_minutes}"
            )
    if vendor_trusted_markets:
        causal_base_lines.append(
            "  vendor_trusted_ohlcv_no_trade_markets: ["
            + ", ".join(vendor_trusted_markets)
            + "]"
        )
    path.write_text(
        "\n".join(
            [
                "defaults:",
                "  years: [2024]",
                "  max_synthetic_gap_minutes: 120",
                f"  max_synthetic_rows_pct: {synthetic_pct}",
                f"  synthetic_gap_threshold_action: {synthetic_action}",
                f"  max_degraded_rows_pct: {degraded_pct}",
                f"  max_roll_window_rows_pct: {roll_pct}",
                "  require_roll_metadata_for_profiles: [tier_1, tier_2, tier_3]",
                *causal_base_lines,
                "profiles:",
                "  tier_0:",
                "    markets: [" + ", ".join(tier0_markets) + "]",
                "    years: [2024]",
                "  metadata_optional_test:",
                "    markets: [ES]",
                "    years: [2024]",
                "  tier_1:",
                "    markets: [CL, ES, ZN]",
                "    years: [2024]",
                "aliases:",
                "  tier_1_core: tier_1",
            ]
        ),
        encoding="utf-8",
    )


def _write_profile_defaults_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "defaults:",
                "  years: [2024]",
                "  max_synthetic_gap_minutes: 77",
                "  require_roll_metadata_for_profiles: [tier_1, tier_3]",
                "profile_defaults:",
                "  smoke:",
                "    max_synthetic_rows_pct: 5.0",
                "    max_degraded_rows_pct: 5.0",
                "    max_roll_window_rows_pct: 2.0",
                "  recent_research:",
                "    max_synthetic_rows_pct: 2.0",
                "    max_degraded_rows_pct: 1.0",
                "    max_roll_window_rows_pct: 1.0",
                "  production_like:",
                "    max_synthetic_rows_pct: 1.0",
                "    max_degraded_rows_pct: 0.5",
                "    max_roll_window_rows_pct: 1.0",
                "profiles:",
                "  tier_0:",
                "    settings_profile: smoke",
                "    markets: [ES]",
                "    years: [2024]",
                "  tier_1:",
                "    settings_profile: recent_research",
                "    markets: [CL, ES, ZN]",
                "    years: [2024]",
                "  tier_3:",
                "    settings_profile: production_like",
                "    markets: [ES]",
                "    years: [2026]",
                "aliases:",
                "  tier_1_core: tier_1",
                "  tier_2_forward: tier_3",
            ]
        ),
        encoding="utf-8",
    )


def _write_session_config(
    path: Path,
    *,
    early_closes: dict[str, str] | None = None,
    closed_dates: list[str] | None = None,
    intraday_breaks: list[tuple[str, str]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    early_closes = early_closes or {}
    closed_dates = closed_dates or []
    intraday_breaks = intraday_breaks or []
    early_lines = [f'      {day}: "{time}"' for day, time in early_closes.items()]
    closed_text = ", ".join(closed_dates)
    break_lines = [
        f'      - start: "{start}"\n        end: "{end}"' for start, end in intraday_breaks
    ]
    path.write_text(
        "\n".join(
            [
                "session_templates:",
                "  cme_globex_17_16_ct:",
                "    timezone: America/Chicago",
                '    regular_open: "17:00"',
                '    regular_close: "16:00"',
                "    holidays: []",
                f"    closed_dates: [{closed_text}]",
                "    early_closes:",
                *(early_lines or []),
                "    intraday_breaks:",
                *(break_lines or []),
                "markets:",
                "  default:",
                "    session_template: cme_globex_17_16_ct",
                "  CL:",
                "    session_template: cme_globex_17_16_ct",
                "  ES:",
                "    session_template: cme_globex_17_16_ct",
                "  ZN:",
                "    session_template: cme_globex_17_16_ct",
            ]
        ),
        encoding="utf-8",
    )


def _local_trade_gate(
    *,
    status: str = "PASS",
    market_statuses: dict[str, str] | None = None,
) -> dict[str, object]:
    market_statuses = market_statuses or {"ES": "PASS"}
    return {
        "status": status,
        "method": "local trades DBN cross-check of OHLCV synthetic missing minutes",
        "profiles": ["tier_3_holdout", "tier_3_forward"],
        "selected_markets": sorted(market_statuses),
        "window": {
            "start": "2025-06-18T00:00:00Z",
            "end": "2026-06-13T00:00:00Z",
        },
        "report_paths": {
            "json": "reports/causal_base/local_trade_ohlcv_gap_crosscheck_2025_2026.json",
            "markdown": "reports/causal_base/local_trade_ohlcv_gap_crosscheck_2025_2026.md",
        },
        "caveat": (
            "A passing local trades cross-check supports a Databento OHLCV "
            "no-trade convention assumption for similar archives; it does not "
            "independently prove every older market-year minute is complete."
        ),
        "summary": {"missing_minute_count": 0},
        "market_statuses": market_statuses,
        "validation_status_by_market": {
            market: (
                LOCAL_TRADE_GAP_VALIDATED_STATUS
                if market_status == "PASS"
                else LOCAL_TRADE_GAP_FAILED_STATUS
            )
            for market, market_status in market_statuses.items()
        },
        "failures": [] if status == "PASS" else ["local trades gate failed"],
    }


def _write_raw_alignment_report(
    path: Path,
    *,
    status: str = "PASS",
    raw_root: Path | str = "data/raw",
    profile: str = "tier_3",
    resolved_profile: str = "tier_3_research",
    overrides: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "stage": "raw_dbn_alignment_audit",
        "status": status,
        "audit_completeness": "full",
        "definition_join_status": "checked",
        "profile": profile,
        "resolved_profile": resolved_profile,
        "raw_root": str(raw_root),
        "missing_raw_count": 0,
        "needs_phase1b_conversion_count": 0,
        "missing_ohlcv_dbn_count": 0,
        "missing_definition_dbn_count": 0,
        "invalid_manifest_count": 0,
        "raw_schema_failure_count": 0,
        "source_hash_mismatch_count": 0,
        "definition_join_mismatch_count": 0,
    }
    if overrides:
        payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _readiness_raw_row(
    ts_event: str | pd.Timestamp,
    *,
    close: float = 100.5,
    instrument_id: int = 100,
    symbol: str = "ESH4",
) -> dict[str, object]:
    return {
        "rtype": 33,
        "publisher_id": 1,
        "instrument_id": instrument_id,
        "symbol": symbol,
        "ts_event": ts_event,
        "open": close - 0.5,
        "high": close + 0.5,
        "low": close - 1.0,
        "close": close,
        "volume": 10,
        "data_quality_status": "available",
        "data_quality_degraded": False,
        "status_is_trading": True,
        "status_is_quoting": True,
        "status_missing": False,
        "status_stale": False,
        "statistics_missing": False,
        "statistics_stale": False,
    }


def _write_tier0_alignment(path: Path, raw_root: Path, *, status: str = "PASS") -> None:
    _write_raw_alignment_report(
        path,
        status=status,
        raw_root=raw_root,
        profile="tier_0",
        resolved_profile="tier_0",
        overrides={
            "markets": ["ES"],
            "years": [2024],
            "pre_availability_exemptions": [],
            "expected_market_year_count": 1,
        },
    )


def test_phase2_raw_alignment_guard_requires_report(tmp_path: Path) -> None:
    failures = raw_alignment_guard_failures(
        report_path=tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json",
        raw_root=tmp_path / "data" / "raw",
        profile="tier_3",
        profile_config_path=tmp_path / "configs" / "alpha_tiered.yaml",
    )

    assert failures == [
        "raw alignment report missing: "
        + (tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json").as_posix()
    ]


def test_phase2_raw_alignment_guard_accepts_passed_matching_phase1c_report(
    tmp_path: Path,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_defaults_config(profile_config)
    report_path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    raw_root = tmp_path / "data" / "raw"
    _write_raw_alignment_report(report_path, raw_root=raw_root)

    failures = raw_alignment_guard_failures(
        report_path=report_path,
        raw_root=raw_root,
        profile="tier_3",
        profile_config_path=profile_config,
    )

    assert failures == []


def test_phase2_raw_alignment_guard_rejects_failed_or_stale_phase1c_report(
    tmp_path: Path,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_defaults_config(profile_config)
    report_path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    raw_root = tmp_path / "data" / "raw"
    _write_raw_alignment_report(
        report_path,
        status="FAIL",
        raw_root=tmp_path / "other_raw",
        overrides={"needs_phase1b_conversion_count": 1},
    )

    failures = raw_alignment_guard_failures(
        report_path=report_path,
        raw_root=raw_root,
        profile="tier_3",
        profile_config_path=profile_config,
    )

    assert "raw alignment report status is 'FAIL', not PASS" in failures
    assert any("raw_root does not match" in failure for failure in failures)
    assert "raw alignment report needs_phase1b_conversion_count is 1, not 0" in failures


def test_output_root_guard_rejects_partial_root_without_manifest(tmp_path: Path) -> None:
    output_root = tmp_path / "data" / "causally_gated_normalized_candidate"
    reports_root = tmp_path / "reports" / "causal_base_candidate"
    _write_raw(
        output_root / "ES" / "2024.parquet",
        [_readiness_raw_row("2024-01-02T15:00:00Z")],
    )

    failures = output_root_guard_failures(
        output_root=output_root,
        reports_root=reports_root,
    )

    assert len(failures) == 1
    assert "already contains parquet files" in failures[0]
    assert "causal_base_manifest.json" in failures[0]


def test_output_root_guard_allows_nonempty_root_with_manifest(tmp_path: Path) -> None:
    output_root = tmp_path / "data" / "causally_gated_normalized"
    reports_root = tmp_path / "reports" / "causal_base"
    _write_raw(
        output_root / "ES" / "2024.parquet",
        [_readiness_raw_row("2024-01-02T15:00:00Z")],
    )
    reports_root.mkdir(parents=True)
    (reports_root / "causal_base_manifest.json").write_text("{}", encoding="utf-8")

    assert output_root_guard_failures(
        output_root=output_root,
        reports_root=reports_root,
    ) == []


def test_output_root_guard_allows_empty_new_candidate_root(tmp_path: Path) -> None:
    assert output_root_guard_failures(
        output_root=tmp_path / "data" / "new_candidate",
        reports_root=tmp_path / "reports" / "new_candidate",
    ) == []


def test_phase2_readiness_fails_missing_raw_alignment_report(tmp_path: Path) -> None:
    report = build_phase2_readiness_report(
        profile="tier_0",
        raw_root=tmp_path / "data" / "raw",
        raw_alignment_report=tmp_path / "reports" / "raw_ingest" / "missing.json",
    )

    assert report["status"] == "FAIL"
    assert report["failure_count"] == 1
    assert "raw alignment report missing" in report["failures"][0]
    assert report["checked_market_year_count"] == 0


def test_phase2_readiness_fails_warn_raw_alignment_report(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    report_path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    _write_tier0_alignment(report_path, raw_root, status="WARN")

    report = build_phase2_readiness_report(
        profile="tier_0",
        raw_root=raw_root,
        raw_alignment_report=report_path,
    )

    assert report["status"] == "FAIL"
    assert "raw alignment report status is 'WARN', not PASS" in report["failures"]
    assert report["checked_market_year_count"] == 0


def test_phase2_readiness_blocks_warn_synthetic_gap_before_writing(
    tmp_path: Path,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(profile_config)
    raw_root = tmp_path / "data" / "raw"
    raw_path = raw_root / "ES" / "2024.parquet"
    output_root = tmp_path / "data" / "causally_gated_normalized"
    report_path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    _write_tier0_alignment(report_path, raw_root)
    _write_raw(
        raw_path,
        [
            _readiness_raw_row("2024-01-02T15:00:00Z", close=100.5),
            _readiness_raw_row("2024-01-02T15:10:00Z", close=101.0),
        ],
    )

    report = build_phase2_readiness_report(
        profile="tier_0",
        raw_root=raw_root,
        raw_alignment_report=report_path,
        output_root=output_root,
        profile_config_path=profile_config,
    )

    assert report["status"] == "FAIL"
    assert report["blocker_count"] == 1
    blocker = report["blockers"][0]
    assert blocker["market"] == "ES"
    assert blocker["year"] == 2024
    assert blocker["status"] == "WARN"
    assert "synthetic threshold breached" in blocker["top_blocker_reason"]
    assert blocker["status_enrichment_available"] is True
    assert blocker["statistics_enrichment_available"] is True
    assert not (output_root / "ES" / "2024.parquet").exists()


def test_phase2_readiness_allows_vendor_trusted_ohlcv_no_trade_gap(
    tmp_path: Path,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(
        profile_config,
        synthetic_pct=0.1,
        tier0_markets=["ZN"],
        vendor_trusted_markets=["ZN"],
    )
    raw_root = tmp_path / "data" / "raw"
    raw_path = raw_root / "ZN" / "2024.parquet"
    output_root = tmp_path / "data" / "causally_gated_normalized"
    report_path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    _write_raw_alignment_report(
        report_path,
        raw_root=raw_root,
        profile="tier_0",
        resolved_profile="tier_0",
        overrides={
            "markets": ["ZN"],
            "years": [2024],
            "pre_availability_exemptions": [],
            "expected_market_year_count": 1,
        },
    )
    _write_raw(
        raw_path,
        [
            _readiness_raw_row("2024-01-02T15:00:00Z", close=100.5, symbol="ZNH4"),
            _readiness_raw_row("2024-01-02T15:10:00Z", close=101.0, symbol="ZNH4"),
        ],
    )

    report = build_phase2_readiness_report(
        profile="tier_0",
        raw_root=raw_root,
        raw_alignment_report=report_path,
        output_root=output_root,
        profile_config_path=profile_config,
    )
    result = process_file(
        raw_path,
        output_root / "ZN" / "2024.parquet",
        profile="tier_0",
        profile_config_path=profile_config,
    )

    assert report["status"] == "PASS"
    assert report["checked_market_year_count"] == 1
    assert report["blocker_count"] == 0
    assert result.status == "PASS"
    assert result.synthetic_gap_threshold_breached is True
    assert result.synthetic_gap_threshold_action == "diagnostic"
    assert result.vendor_trusted_ohlcv_no_trade_policy == (
        "databento_ohlcv_1m_trade_derived_no_bar_no_trade"
    )
    output = pd.read_parquet(output_root / "ZN" / "2024.parquet")
    synthetic = output[output["is_synthetic"]]
    assert not synthetic.empty
    assert synthetic["raw_row_present"].eq(False).all()
    assert synthetic["causal_valid"].eq(False).all()
    assert synthetic["volume"].eq(0).all()


def test_vendor_trusted_ohlcv_policy_does_not_override_l0_gate_failure(
    tmp_path: Path,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(
        profile_config,
        synthetic_pct=0.1,
        tier0_markets=["ZN"],
        vendor_trusted_markets=["ZN"],
    )
    raw_path = tmp_path / "data" / "raw" / "ZN" / "2025.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ZN" / "2025.parquet"
    _write_raw(
        raw_path,
        [
            _readiness_raw_row("2025-07-21T05:13:00Z", close=110.5, symbol="ZNU5"),
            _readiness_raw_row("2025-07-21T05:15:00Z", close=110.75, symbol="ZNU5"),
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_0",
        max_synthetic_gap_minutes=3,
        profile_config_path=profile_config,
    )

    assert result.status == "PASS"
    assert result.synthetic_gap_threshold_breached is True
    assert (
        phase2_exit_code(
            [result],
            _local_trade_gate(status="FAIL", market_statuses={"ZN": "FAIL"}),
        )
        == 1
    )


def test_sparse_trade_derived_ohlcv_policy_does_not_fabricate_synthetic_rows(
    tmp_path: Path,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(
        profile_config,
        tier0_markets=["SR3"],
        sparse_markets=["SR3"],
    )
    raw_path = tmp_path / "data" / "raw" / "SR3" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "SR3" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            _readiness_raw_row("2024-01-02T15:00:00Z", close=100.5),
            _readiness_raw_row("2024-01-02T15:10:00Z", close=101.0),
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_0",
        profile_config_path=profile_config,
    )
    output = pd.read_parquet(out_path)

    assert result.status == "PASS"
    assert result.synthetic_rows == 0
    assert result.synthetic_gap_threshold_breached is False
    assert result.sparse_ohlcv_policy == "trade_derived_no_trade_gaps_not_filled"
    assert result.sparse_ohlcv_assumption_status == "ASSUMPTION_BACKED"
    assert result.sparse_ohlcv_suppressed_synthetic_rows == 9
    assert result.sparse_ohlcv_suppressed_gap_count == 1
    assert result.sparse_ohlcv_suppressed_max_gap_minutes == 10
    assert not output["is_synthetic"].any()
    assert len(output) == 2
    assert not any("synthetic threshold breached" in item for item in result.warnings)


def test_sparse_trade_derived_roll_window_uses_elapsed_minutes_not_trade_bars(
    tmp_path: Path,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(
        profile_config,
        roll_pct=100.0,
        tier0_markets=["SR3"],
        sparse_markets=["SR3"],
        sparse_roll_window_minutes=15,
    )
    raw_path = tmp_path / "data" / "raw" / "SR3" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "SR3" / "2024.parquet"
    rows = []
    for i, (minute, instrument_id, symbol) in enumerate(
        [
            (0, 100, "SR3H4"),
            (10, 100, "SR3H4"),
            (60, 101, "SR3M4"),
            (100, 101, "SR3M4"),
            (140, 101, "SR3M4"),
        ]
    ):
        rows.append(
            _readiness_raw_row(
                pd.Timestamp("2024-01-02T15:00:00Z") + pd.Timedelta(minutes=minute),
                close=95.0 + i,
                instrument_id=instrument_id,
                symbol=symbol,
            )
        )
    _write_raw(raw_path, rows)

    result = process_file(
        raw_path,
        out_path,
        profile="tier_0",
        profile_config_path=profile_config,
        roll_window_bars=15,
    )

    output = pd.read_parquet(out_path)
    assert result.status == "PASS"
    assert result.roll_window_policy == "elapsed_minutes_sparse_ohlcv"
    assert result.roll_window_minutes == 15
    assert result.roll_policy_status == "active_elapsed_time_sparse_ohlcv"
    assert output["roll_boundary_flag"].sum() == 1
    assert output["roll_window_flag"].sum() == 1
    boundary_idx = int(output.index[output["roll_boundary_flag"]][0])
    assert output.loc[boundary_idx, "roll_window_flag"] == True
    assert output.loc[boundary_idx - 1, "bars_until_roll"] == 1
    assert output.loc[boundary_idx - 1, "roll_window_flag"] == False
    assert output.loc[boundary_idx + 1, "bars_since_roll"] == 1
    assert output.loc[boundary_idx + 1, "roll_window_flag"] == False


def test_non_monotonic_roll_maturity_sequence_warns(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(profile_config, roll_pct=100.0)
    rows = [
        {
            **_readiness_raw_row(
                "2024-01-02T15:00:00Z",
                close=100.5,
                instrument_id=100,
                symbol="ES.v.0",
            ),
            "raw_symbol": "ESH4",
            "maturity_year": 2024,
            "maturity_month": 3,
        },
        {
            **_readiness_raw_row(
                "2024-01-02T15:01:00Z",
                close=101.0,
                instrument_id=101,
                symbol="ES.v.0",
            ),
            "raw_symbol": "ESM4",
            "maturity_year": 2024,
            "maturity_month": 6,
        },
        {
            **_readiness_raw_row(
                "2024-01-02T15:02:00Z",
                close=100.75,
                instrument_id=100,
                symbol="ES.v.0",
            ),
            "raw_symbol": "ESH4",
            "maturity_year": 2024,
            "maturity_month": 3,
        },
    ]
    _write_raw(raw_path, rows)

    result = process_file(
        raw_path,
        out_path,
        profile="tier_0",
        profile_config_path=profile_config,
        roll_window_bars=1,
    )

    assert result.status == "WARN"
    assert result.roll_maturity_sequence_available is True
    assert result.roll_maturity_backstep_count == 1
    assert len(result.roll_maturity_backstep_examples) == 1
    assert any("roll maturity sequence not monotonic" in item for item in result.warnings)


def test_phase2_readiness_allows_configured_sparse_trade_derived_ohlcv_gap(
    tmp_path: Path,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(
        profile_config,
        tier0_markets=["SR3"],
        sparse_markets=["SR3"],
    )
    raw_root = tmp_path / "data" / "raw"
    raw_path = raw_root / "SR3" / "2024.parquet"
    output_root = tmp_path / "data" / "causally_gated_normalized"
    report_path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    _write_raw_alignment_report(
        report_path,
        raw_root=raw_root,
        profile="tier_0",
        resolved_profile="tier_0",
        overrides={
            "markets": ["SR3"],
            "years": [2024],
            "pre_availability_exemptions": [],
            "expected_market_year_count": 1,
        },
    )
    _write_raw(
        raw_path,
        [
            _readiness_raw_row("2024-01-02T15:00:00Z", close=100.5),
            _readiness_raw_row("2024-01-02T15:10:00Z", close=101.0),
        ],
    )

    report = build_phase2_readiness_report(
        profile="tier_0",
        raw_root=raw_root,
        raw_alignment_report=report_path,
        output_root=output_root,
        profile_config_path=profile_config,
    )

    assert report["status"] == "PASS"
    assert report["checked_market_year_count"] == 1
    assert report["blocker_count"] == 0
    assert not (output_root / "SR3" / "2024.parquet").exists()


def test_phase2_main_exits_before_writing_when_readiness_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(profile_config)
    raw_root = tmp_path / "data" / "raw"
    output_root = tmp_path / "data" / "causally_gated_normalized"
    reports_root = tmp_path / "reports" / "causal_base"
    report_path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    _write_tier0_alignment(report_path, raw_root)
    _write_raw(
        raw_root / "ES" / "2024.parquet",
        [
            _readiness_raw_row("2024-01-02T15:00:00Z", close=100.5),
            _readiness_raw_row("2024-01-02T15:10:00Z", close=101.0),
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_causal_base_data.py",
            "--profile",
            "tier_0",
            "--raw-root",
            str(raw_root),
            "--output-root",
            str(output_root),
            "--reports-root",
            str(reports_root),
            "--profile-config",
            str(profile_config),
            "--raw-alignment-report",
            str(report_path),
        ],
    )

    assert phase2_main() == 1
    assert not (output_root / "ES" / "2024.parquet").exists()
    assert not (reports_root / "causal_base_manifest.json").exists()


def test_phase2_main_skips_local_trade_gate_for_smoke_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(profile_config)
    raw_root = tmp_path / "data" / "raw"
    output_root = tmp_path / "data" / "causally_gated_normalized"
    reports_root = tmp_path / "reports" / "causal_base"
    report_path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    _write_tier0_alignment(report_path, raw_root)
    _write_raw(
        raw_root / "ES" / "2024.parquet",
        [
            _readiness_raw_row("2024-01-02T15:00:00Z", close=100.5),
            _readiness_raw_row("2024-01-02T15:01:00Z", close=100.75),
            _readiness_raw_row("2024-01-02T15:02:00Z", close=101.0),
        ],
    )

    def fail_if_called(**_: object) -> dict[str, object]:
        raise AssertionError("local trade gap gate should not run for tier_0")

    monkeypatch.setattr(causal_base, "build_local_trade_ohlcv_gap_gate", fail_if_called)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_causal_base_data.py",
            "--profile",
            "tier_0",
            "--raw-root",
            str(raw_root),
            "--output-root",
            str(output_root),
            "--reports-root",
            str(reports_root),
            "--profile-config",
            str(profile_config),
            "--raw-alignment-report",
            str(report_path),
        ],
    )

    assert profile_requires_local_trade_gap_gate("tier_0", profile_config) is False
    assert phase2_main() == 0

    manifest = json.loads((reports_root / "causal_base_manifest.json").read_text())
    assert manifest["status"] == "PASS"
    assert manifest["local_trade_ohlcv_gap_gate"] is None
    assert manifest["summary"]["local_trade_ohlcv_gap_gate_status"] == "NOT_RUN"
    assert manifest["outputs"][0]["local_trade_gap_gate_status"] == "NOT_RUN"


def test_phase2_readiness_passes_clean_fixture(tmp_path: Path) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(profile_config)
    raw_root = tmp_path / "data" / "raw"
    report_path = tmp_path / "reports" / "raw_ingest" / "raw_dbn_alignment.json"
    _write_tier0_alignment(report_path, raw_root)
    _write_raw(
        raw_root / "ES" / "2024.parquet",
        [
            _readiness_raw_row("2024-01-02T15:00:00Z", close=100.5),
            _readiness_raw_row("2024-01-02T15:01:00Z", close=100.75),
            _readiness_raw_row("2024-01-02T15:02:00Z", close=101.0),
        ],
    )

    report = build_phase2_readiness_report(
        profile="tier_0",
        raw_root=raw_root,
        raw_alignment_report=report_path,
        profile_config_path=profile_config,
    )

    assert report["status"] == "PASS"
    assert report["blocker_count"] == 0
    assert report["checked_market_year_count"] == 1


def test_phase2_readiness_uses_raw_alignment_pre_availability_exemptions() -> None:
    raw_alignment = {
        "markets": ["ES", "RTY"],
        "years": [2024],
        "pre_availability_exemptions": [{"market": "RTY", "year": 2024}],
    }
    assert raw_alignment_expected_market_years(raw_alignment) == {("ES", 2024)}

    selected, missing = filter_inputs_by_raw_alignment(
        [
            ("ES", 2024, Path("data/raw/ES/2024.parquet")),
            ("RTY", 2024, Path("data/raw/RTY/2024.parquet")),
        ],
        raw_alignment,
    )

    assert [(market, year) for market, year, _ in selected] == [("ES", 2024)]
    assert missing == []


def test_phase2_readiness_prefers_explicit_raw_alignment_market_years() -> None:
    raw_alignment = {
        "markets": ["SR1", "SR3"],
        "years": [2018, 2019],
        "market_years": [
            {"market": "SR1", "year": 2018},
            {"market": "SR1", "year": 2019},
            {"market": "SR3", "year": 2019},
        ],
    }

    assert raw_alignment_expected_market_years(raw_alignment) == {
        ("SR1", 2018),
        ("SR1", 2019),
        ("SR3", 2019),
    }


def test_causal_base_config_uses_smoke_profile_thresholds(tmp_path: Path) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_defaults_config(profile_config)

    config = load_causal_base_config(profile_config, "tier_0")

    assert config.max_synthetic_rows_pct == 5.0
    assert config.max_degraded_rows_pct == 5.0
    assert config.max_roll_window_rows_pct == 2.0
    assert config.max_synthetic_gap_minutes == 77
    assert config.sparse_trade_derived_roll_window_minutes == 15


def test_causal_base_config_resolves_alias_before_threshold_lookup(tmp_path: Path) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_defaults_config(profile_config)

    config = load_causal_base_config(profile_config, "tier_1")
    direct_config = load_causal_base_config(profile_config, "tier_1")

    assert config.max_synthetic_rows_pct == 2.0
    assert config.max_degraded_rows_pct == 1.0
    assert config.max_roll_window_rows_pct == 1.0
    assert direct_config == config


def test_causal_base_config_uses_forward_production_like_thresholds(tmp_path: Path) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_defaults_config(profile_config)

    config = load_causal_base_config(profile_config, "tier_2_forward")

    assert config.max_synthetic_rows_pct == 1.0
    assert config.max_degraded_rows_pct == 0.5
    assert config.max_roll_window_rows_pct == 1.0


def test_causal_base_schema_synthetic_and_source_lineage(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    rows = [
        {
            "rtype": 33,
            "publisher_id": 1,
            "instrument_id": 100,
            "symbol": "ESH4",
            "ts_event": "2024-01-02T15:00:00Z",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 10,
        },
        {
            "rtype": 33,
            "publisher_id": 1,
            "instrument_id": 100,
            "symbol": "ESH4",
            "ts_event": "2024-01-02T15:02:00Z",
            "open": 100.5,
            "high": 101.5,
            "low": 100.0,
            "close": 101.0,
            "volume": 12,
        },
    ]
    _write_raw(raw_path, rows)

    result = process_file(raw_path, out_path, profile="metadata_optional_test")

    assert result.status == "WARN"
    assert result.synthetic_rows == 1
    output = pd.read_parquet(out_path)
    assert list(output.columns) == OUTPUT_COLUMNS
    assert output["ts"].is_monotonic_increasing
    assert {
        "causal_invalid_reason",
        "session_calendar_status",
        "holiday_calendar_available",
        "early_close_calendar_available",
        "calendar_coverage_status",
    }.issubset(output.columns)

    synthetic = output.loc[output["is_synthetic"]].iloc[0]
    assert synthetic["raw_row_present"] == False
    assert synthetic["causal_valid"] == False
    assert "synthetic" in synthetic["causal_invalid_reason"]
    assert synthetic["boundary_session_flag"] == True
    assert pd.isna(synthetic["source_row_number"])
    assert synthetic["open"] == 100.5
    assert synthetic["high"] == 100.5
    assert synthetic["low"] == 100.5
    assert synthetic["close"] == 100.5
    assert synthetic["volume"] == 0

    raw_rows = output.loc[~output["is_synthetic"]]
    assert raw_rows["source_row_number"].tolist() == [0, 1]
    assert raw_rows["source_file_hash"].nunique() == 1
    assert raw_rows["inside_session"].all()
    assert raw_rows["boundary_session_flag"].all()
    assert not raw_rows["causal_valid"].any()
    assert raw_rows["causal_invalid_reason"].str.contains("boundary_session").all()
    assert output["calendar_coverage_status"].eq("config_backed").all()


def test_causal_base_preserves_raw_enrichment_metadata_columns(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw_enriched_candidate" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    rows = [
        {
            "rtype": 33,
            "publisher_id": 1,
            "instrument_id": 100,
            "symbol": "ESH4",
            "ts_event": "2024-01-02T15:00:00Z",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 10,
            "data_quality_status": "available",
            "data_quality_degraded": False,
            "status_ts_event": "2024-01-02T14:59:00Z",
            "status_action_name": "TRADING",
            "status_missing": False,
            "status_stale": False,
            "stat_opening_price": 100.25,
            "stat_opening_price_ts_event": "2024-01-02T14:58:00Z",
            "stat_opening_price_missing": False,
            "statistics_missing": False,
            "statistics_stale": False,
        }
    ]
    _write_raw(raw_path, rows)

    result = process_file(raw_path, out_path, profile="metadata_optional_test")

    output = pd.read_parquet(out_path)
    for column in [
        "status_ts_event",
        "status_action_name",
        "status_missing",
        "stat_opening_price",
        "stat_opening_price_ts_event",
        "statistics_missing",
    ]:
        assert column in output.columns
    assert result.raw_enrichment_column_count == 9
    assert result.status_enrichment_missing_rows == 0
    assert result.statistics_enrichment_missing_rows == 0
    assert output.loc[0, "stat_opening_price"] == 100.25


def test_roll_boundary_sets_window_and_blocks_causal_valid(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "CL" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "CL" / "2024.parquet"
    rows = []
    for i, symbol in enumerate(["CLH4", "CLH4", "CLK4", "CLK4"]):
        rows.append(
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 10 if symbol == "CLH4" else 11,
                "symbol": symbol,
                "ts_event": pd.Timestamp("2024-01-02T15:00:00Z") + pd.Timedelta(minutes=i),
                "open": 70.0 + i,
                "high": 71.0 + i,
                "low": 69.0 + i,
                "close": 70.5 + i,
                "volume": 10 + i,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        )
    _write_raw(raw_path, rows)

    result = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        roll_window_bars=1,
    )

    assert result.status == "WARN"
    assert result.failures == []
    output = pd.read_parquet(out_path)
    assert output["roll_boundary_flag"].sum() == 1
    assert output["symbol_change_flag"].sum() == 1
    assert output["instrument_id_change_flag"].sum() == 1

    boundary_idx = int(output.index[output["roll_boundary_flag"]][0])
    window = output.loc[[boundary_idx - 1, boundary_idx, boundary_idx + 1]]
    assert window["roll_window_flag"].all()
    assert not window["causal_valid"].any()
    assert window["causal_invalid_reason"].str.contains("roll_window").all()


def test_roll_exclusion_is_not_warn_under_threshold(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "CL" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "CL" / "2024.parquet"
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(profile_config, roll_pct=100.0)
    rows = []
    for i, symbol in enumerate(["CLH4", "CLH4", "CLK4", "CLK4"]):
        rows.append(
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 10 if symbol == "CLH4" else 11,
                "symbol": symbol,
                "ts_event": pd.Timestamp("2024-01-02T15:00:00Z") + pd.Timedelta(minutes=i),
                "open": 70.0 + i,
                "high": 71.0 + i,
                "low": 69.0 + i,
                "close": 70.5 + i,
                "volume": 10 + i,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        )
    _write_raw(raw_path, rows)

    result = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        roll_window_bars=1,
        profile_config_path=profile_config,
    )

    output = pd.read_parquet(out_path)
    assert output.loc[output["roll_window_flag"], "causal_valid"].eq(False).all()
    assert result.roll_window_threshold_breached is False
    assert not any("roll exclusion threshold breached" in item for item in result.warnings)


def test_missing_audit_columns_warn_but_output_required_columns(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ZN" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ZN" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 110.0,
                "high": 111.0,
                "low": 109.0,
                "close": 110.5,
                "volume": 10,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="metadata_optional_test")

    assert result.status == "WARN"
    assert result.failures == []
    assert result.raw_schema_variant == "ohlcv_only"
    assert result.timestamp_source == "ts_event_column"
    assert result.metadata_available is False
    assert result.roll_detection_available is False
    assert result.roll_detection_source == "unavailable"
    assert result.roll_policy_status == "unavailable_metadata"
    assert set(result.missing_audit_cols) == {
        "rtype",
        "publisher_id",
        "instrument_id",
        "symbol",
    }
    output = pd.read_parquet(out_path)
    assert list(output.columns) == OUTPUT_COLUMNS
    assert output.loc[0, "boundary_session_flag"]
    assert output.loc[0, "causal_valid"] == False
    assert output.loc[0, "raw_schema_variant"] == "ohlcv_only"
    assert output.loc[0, "timestamp_source"] == "ts_event_column"
    assert output.loc[0, "roll_detection_available"] == False


def test_reports_are_written(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    reports_root = tmp_path / "reports" / "causal_base"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )
    result = process_file(raw_path, out_path, profile="tier_0")

    write_reports([result], reports_root, "metadata_optional_test")

    manifest = json.loads((reports_root / "causal_base_manifest.json").read_text())
    validation = json.loads((reports_root / "causal_base_validation.json").read_text())
    assert (reports_root / "causal_base_validation.csv").exists()
    provenance_keys = {
        "generated_at",
        "git_commit",
        "script_path",
        "script_hash",
        "config_hash",
        "input_root",
        "output_root",
        "reports_root",
        "input_file_hashes",
        "output_file_hashes",
        "profile",
        "markets",
        "years",
        "warning_count",
        "failure_count",
        "failures",
    }
    assert provenance_keys <= set(manifest)
    assert provenance_keys <= set(validation)
    assert manifest["input_root"] == (tmp_path / "data" / "raw").as_posix()
    assert manifest["output_root"] == (
        tmp_path / "data" / "causally_gated_normalized"
    ).as_posix()
    assert manifest["reports_root"] == reports_root.as_posix()
    assert validation["input_root"] == manifest["input_root"]
    assert validation["output_root"] == manifest["output_root"]
    assert validation["reports_root"] == manifest["reports_root"]
    assert manifest["input_file_hashes"][result.input_path] == result.source_file_hash
    output_hash = manifest["output_file_hashes"][result.output_path]
    assert isinstance(output_hash, str)
    assert len(output_hash) == 64
    assert manifest["warning_count"] == result.to_dict()["warning_count"]
    assert manifest["failure_count"] == 0
    assert manifest["failures"] == []
    assert manifest["markets"] == ["ES"]
    assert manifest["years"] == [2024]
    assert manifest["stage"] == "causal_base"
    assert manifest["outputs"][0]["raw_schema_variant"] == "databento_full"
    assert manifest["outputs"][0]["timestamp_source"] == "ts_event_column"
    assert manifest["outputs"][0]["metadata_available"] is True
    assert manifest["outputs"][0]["roll_detection_available"] is True
    assert manifest["outputs"][0]["roll_detection_source"] == "instrument_id"
    assert manifest["outputs"][0]["roll_policy_status"] == "active"
    assert manifest["outputs"][0]["raw_schema_policy"] == "strict"
    assert manifest["outputs"][0]["required_raw_schema_cols"] == [
        "ts_event",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "rtype",
        "publisher_id",
        "instrument_id",
        "symbol",
        "data_quality_status",
        "data_quality_degraded",
    ]
    assert manifest["outputs"][0]["raw_schema_missing_cols"] == []
    assert manifest["outputs"][0]["missing_required_raw_cols"] == []
    assert manifest["outputs"][0]["symbol_nonnull_count"] == 1
    assert manifest["outputs"][0]["instrument_id_nonnull_count"] == 1
    assert manifest["outputs"][0]["instrument_id_nunique"] == 1
    assert manifest["outputs"][0]["warning_count"] == result.to_dict()["warning_count"]
    assert manifest["outputs"][0]["failure_count"] == 0
    assert manifest["outputs"][0]["failures"] == []
    assert manifest["outputs"][0]["boundary_session_rows"] == 1
    assert manifest["outputs"][0]["causal_valid_rows"] == 0
    assert manifest["outputs"][0]["causal_invalid_rows"] == 1
    assert manifest["outputs"][0]["session_calendar_status"] == "config_backed"
    assert manifest["outputs"][0]["holiday_calendar_available"] is True
    assert manifest["outputs"][0]["early_close_calendar_available"] is True
    assert manifest["outputs"][0]["calendar_coverage_status"] == "config_backed"
    assert "warnings" in manifest["outputs"][0]
    assert "holiday calendar unavailable: using hardcoded regular session" not in manifest["outputs"][0]["warnings"]
    assert "early-close calendar unavailable: using hardcoded regular session" not in manifest["outputs"][0]["warnings"]
    validation_file = validation["files"][0]
    assert validation_file["synthetic_gap_count"] == 0
    assert validation_file["synthetic_rows_pct"] == 0.0
    assert validation_file["synthetic_gap_threshold_breached"] is False
    assert validation_file["roll_window_rows_pct"] == 0.0
    assert validation_file["roll_window_threshold_breached"] is False
    assert validation_file["degraded_rows_pct"] == 0.0
    assert validation_file["degraded_threshold_breached"] is False
    assert validation_file["raw_schema_policy"] == "strict"
    assert validation_file["raw_schema_missing_cols"] == []
    assert validation_file["calendar_coverage_status"] == "config_backed"
    assert validation["summary"]["synthetic_gap_threshold_breached_files"] == 0
    assert validation["summary"]["roll_window_threshold_breached_files"] == 0
    assert validation["summary"]["degraded_threshold_breached_files"] == 0
    assert validation["files"][0]["output_path"].endswith("2024.parquet")


def test_reports_mark_older_years_validated_by_local_trades_convention(
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    reports_root = tmp_path / "reports" / "causal_base"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )
    result = process_file(raw_path, out_path, profile="tier_0")
    gate = _local_trade_gate()

    write_reports(
        [result],
        reports_root,
        "tier_3",
        input_root=tmp_path / "data" / "raw",
        output_root=tmp_path / "data" / "causally_gated_normalized",
        local_trade_gap_gate=gate,
    )

    manifest = json.loads((reports_root / "causal_base_manifest.json").read_text())
    validation = json.loads((reports_root / "causal_base_validation.json").read_text())
    output = pd.read_parquet(out_path)
    assert list(output.columns) == OUTPUT_COLUMNS
    assert manifest["local_trade_ohlcv_gap_gate"]["status"] == "PASS"
    assert validation["local_trade_ohlcv_gap_gate"]["status"] == "PASS"
    assert validation["summary"]["local_trade_ohlcv_gap_gate_status"] == "PASS"
    assert manifest["outputs"][0]["year"] == 2024
    assert (
        manifest["outputs"][0]["local_trade_gap_validation_status"]
        == LOCAL_TRADE_GAP_VALIDATED_STATUS
    )
    assert (
        validation["files"][0]["local_trade_gap_validation_status"]
        == LOCAL_TRADE_GAP_VALIDATED_STATUS
    )
    assert "older market-year" in manifest["outputs"][0]["local_trade_gap_gate_caveat"]


def test_phase2_exit_code_fails_when_local_trades_gate_fails(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )
    result = process_file(raw_path, out_path, profile="tier_0")

    assert phase2_exit_code([result], _local_trade_gate(status="PASS")) == 0
    assert phase2_exit_code([result], _local_trade_gate(status="FAIL")) == 1


def test_calendar_config_removes_hardcoded_calendar_warning(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    session_config = tmp_path / "configs" / "market_sessions.yaml"
    _write_session_config(session_config)
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-03T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        session_config_path=session_config,
    )

    assert result.session_calendar_status == "config_backed_regular_session"
    assert result.calendar_coverage_status == "regular_session_only"
    assert result.holiday_calendar_available is False
    assert result.early_close_calendar_available is False
    assert "hardcoded session calendar used" not in result.warnings
    assert (
        "holiday/early-close calendar coverage unavailable: regular session only"
        in result.warnings
    )


def test_early_close_changes_minutes_until_session_close(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    session_config = tmp_path / "configs" / "market_sessions.yaml"
    _write_session_config(session_config, early_closes={"2024-01-03": "12:00"})
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-03T17:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        session_config_path=session_config,
    )

    assert result.session_calendar_status == "config_backed"
    assert result.calendar_coverage_status == "config_backed"
    assert result.holiday_calendar_available is False
    assert result.early_close_calendar_available is True
    output = pd.read_parquet(out_path)
    assert output.loc[0, "inside_session"] == True
    assert output.loc[0, "minutes_until_session_close"] == 60.0


def test_closed_date_is_excluded(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    session_config = tmp_path / "configs" / "market_sessions.yaml"
    _write_session_config(session_config, closed_dates=["2024-01-03"])
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-03T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        session_config_path=session_config,
    )

    assert result.session_calendar_status == "config_backed"
    assert result.calendar_coverage_status == "config_backed"
    assert result.holiday_calendar_available is True
    assert result.early_close_calendar_available is False
    output = pd.read_parquet(out_path)
    assert output.loc[0, "inside_session"] == False
    assert output.loc[0, "causal_valid"] == False


def test_all_raw_discovery_uses_top_level_market_year_files_only(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    _write_raw(
        raw_root / "ES" / "2024.parquet",
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )
    _write_raw(
        raw_root / "CL" / "2023.parquet",
        [
            {
                "ts_event": "2023-01-03T15:00:00Z",
                "open": 70.0,
                "high": 71.0,
                "low": 69.0,
                "close": 70.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )
    _write_raw(
        raw_root / "GC" / "LE" / "2024.parquet",
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1,
            }
        ],
    )

    discovered = discover_raw_inputs(raw_root)

    assert [(market, year) for market, year, _ in discovered] == [
        ("CL", 2023),
        ("ES", 2024),
    ]


def test_profile_resolution_supports_all_raw_and_tier_profile(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    _write_raw(
        raw_root / "ZN" / "2025.parquet",
        [
            {
                "ts_event": "2025-01-02T15:00:00Z",
                "open": 110.0,
                "high": 111.0,
                "low": 109.0,
                "close": 110.5,
                "volume": 10,
            }
        ],
    )

    all_raw = resolve_profile_inputs("all_raw", raw_root)
    tier = resolve_profile_inputs("tier_1", raw_root)

    assert [(market, year) for market, year, _ in all_raw] == [("ZN", 2025)]
    assert len(tier) == 8
    assert ("6E", 2024) in [(market, year) for market, year, _ in tier]


def test_boundary_sessions_are_not_causal_valid(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    rows = []
    for day in [2, 3, 4]:
        rows.append(
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": f"2024-01-{day:02d}T15:00:00Z",
                "open": 100.0 + day,
                "high": 101.0 + day,
                "low": 99.0 + day,
                "close": 100.5 + day,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        )
    _write_raw(raw_path, rows)

    result = process_file(raw_path, out_path, profile="metadata_optional_test")

    assert result.boundary_session_rows == 2
    assert result.causal_valid_rows == 1
    output = pd.read_parquet(out_path)
    assert output["boundary_session_flag"].tolist() == [True, False, True]
    assert output["causal_valid"].tolist() == [False, True, False]
    assert output.loc[output["causal_valid"], "causal_invalid_reason"].eq("").all()
    assert output.loc[output["boundary_session_flag"], "causal_invalid_reason"].str.contains(
        "boundary_session"
    ).all()


def test_year_boundary_bleed_prevents_boundary_flag_when_adjacent_data_exists(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "data" / "raw" / "ES"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    common = {
        "rtype": 33,
        "publisher_id": 1,
        "instrument_id": 100,
        "symbol": "ESH4",
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 10,
        "data_quality_status": "available",
        "data_quality_degraded": False,
    }
    _write_raw(raw_root / "2023.parquet", [{**common, "ts_event": "2023-12-31T23:30:00Z"}])
    _write_raw(
        raw_root / "2024.parquet",
        [
            {**common, "ts_event": "2024-01-01T06:30:00Z"},
            {**common, "ts_event": "2024-12-31T23:30:00Z"},
        ],
    )
    _write_raw(raw_root / "2025.parquet", [{**common, "ts_event": "2025-01-01T06:30:00Z"}])

    process_file(raw_root / "2024.parquet", out_path, profile="tier_1")

    output = pd.read_parquet(out_path)
    assert output["boundary_session_flag"].tolist() == [False, False]


def test_boundary_session_flag_remains_true_when_adjacent_data_missing(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-03T06:30:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    process_file(raw_path, out_path, profile="tier_1")

    output = pd.read_parquet(out_path)
    assert output.loc[0, "boundary_session_flag"] == True
    assert output.loc[0, "causal_valid"] == False


def test_context_clipping_retains_adjacent_year_tail_and_head_rows(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw" / "ES"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    base_row = {
        "rtype": 33,
        "publisher_id": 1,
        "instrument_id": 100,
        "symbol": "ESH4",
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 10,
        "data_quality_status": "available",
        "data_quality_degraded": False,
    }
    _write_raw(raw_root / "2023.parquet", [{**base_row, "ts_event": "2023-12-15T15:00:00Z"}])
    _write_raw(raw_root / "2024.parquet", [{**base_row, "ts_event": "2024-01-02T15:00:00Z"}])
    _write_raw(raw_root / "2025.parquet", [{**base_row, "ts_event": "2025-01-15T15:00:00Z"}])

    process_file(raw_root / "2024.parquet", out_path, profile="tier_1")

    output = pd.read_parquet(out_path)
    assert len(output) == 1
    assert output.loc[0, "boundary_session_flag"] == False


def test_causal_valid_formula_includes_boundary_session_flag(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "CL" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "CL" / "2024.parquet"
    rows = []
    for day in [2, 3, 4]:
        rows.append(
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 10,
                "symbol": "CLH4",
                "ts_event": f"2024-01-{day:02d}T15:00:00Z",
                "open": 70.0 + day,
                "high": 71.0 + day,
                "low": 69.0 + day,
                "close": 70.5 + day,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        )
    _write_raw(raw_path, rows)

    process_file(raw_path, out_path, profile="tier_1")

    output = pd.read_parquet(out_path)
    expected = (
        output["raw_row_present"]
        & ~output["is_synthetic"]
        & output["valid_ohlcv"]
        & output["inside_session"]
        & output["trainable_data_quality"]
        & ~output["roll_window_flag"]
        & ~output["boundary_session_flag"]
    )
    assert output["causal_valid"].equals(expected)
    assert output.loc[0, "boundary_session_flag"]
    assert output.loc[0, "causal_valid"] == False


def test_missing_raw_file_manifest_reports_failure_count_and_failures(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ZN" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ZN" / "2024.parquet"
    reports_root = tmp_path / "reports" / "causal_base"

    result = process_file(raw_path, out_path, profile="tier_0")
    write_reports([result], reports_root, "tier_1")

    manifest = json.loads((reports_root / "causal_base_manifest.json").read_text())
    item = manifest["outputs"][0]
    assert manifest["partial_scope"] is True
    assert manifest["authoritative"] is False
    assert manifest["expected_input_count"] == 8
    assert manifest["actual_input_count"] == 1
    assert item["status"] == "FAIL"
    assert item["failure_count"] == 1
    assert item["failures"] == ["input file missing"]


def test_synthetic_gap_at_max_limit_is_filled(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:03:00Z",
                "open": 100.5,
                "high": 101.5,
                "low": 100.0,
                "close": 101.0,
                "volume": 12,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        max_synthetic_gap_minutes=3,
    )

    assert result.synthetic_rows == 2
    output = pd.read_parquet(out_path)
    synthetic_ts = output.loc[output["is_synthetic"], "ts"].tolist()
    assert synthetic_ts == [
        pd.Timestamp("2024-01-02T15:01:00Z"),
        pd.Timestamp("2024-01-02T15:02:00Z"),
    ]
    assert output.loc[output["is_synthetic"], "causal_valid"].eq(False).all()
    assert output.loc[output["is_synthetic"], "synthetic_gap_id"].notna().all()
    assert output.loc[output["is_synthetic"], "synthetic_gap_size_minutes"].eq(3).all()
    assert output.loc[output["is_synthetic"], "synthetic_gap_reason"].eq(
        "missing_in_session_minute"
    ).all()


def test_synthetic_gap_above_max_limit_is_not_filled(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:04:00Z",
                "open": 100.5,
                "high": 101.5,
                "low": 100.0,
                "close": 101.0,
                "volume": 12,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        max_synthetic_gap_minutes=3,
    )

    assert result.synthetic_rows == 0
    output = pd.read_parquet(out_path)
    assert not output["is_synthetic"].any()


def test_no_synthetic_fill_across_instrument_change_when_metadata_available(
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "data" / "raw" / "CL" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "CL" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 10,
                "symbol": "CLH4",
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 70.0,
                "high": 71.0,
                "low": 69.0,
                "close": 70.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 11,
                "symbol": "CLK4",
                "ts_event": "2024-01-02T15:03:00Z",
                "open": 70.5,
                "high": 71.5,
                "low": 70.0,
                "close": 71.0,
                "volume": 12,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        max_synthetic_gap_minutes=3,
    )

    assert result.synthetic_rows == 0
    output = pd.read_parquet(out_path)
    assert not output["is_synthetic"].any()
    assert output["instrument_id_change_flag"].sum() == 1
    assert output["roll_boundary_flag"].sum() == 1


def test_synthetic_warning_only_triggers_above_threshold(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    high_threshold_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(high_threshold_config, synthetic_pct=90.0)
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:03:00Z",
                "open": 100.5,
                "high": 101.5,
                "low": 100.0,
                "close": 101.0,
                "volume": 12,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
        ],
    )

    high = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        max_synthetic_gap_minutes=3,
        profile_config_path=high_threshold_config,
    )
    low = process_file(
        raw_path,
        tmp_path / "data" / "second" / "ES" / "2024.parquet",
        profile="tier_1",
        max_synthetic_gap_minutes=3,
    )

    assert high.synthetic_gap_threshold_breached is False
    assert not any("synthetic threshold breached" in item for item in high.warnings)
    assert low.synthetic_gap_threshold_breached is True
    assert any("synthetic threshold breached" in item for item in low.warnings)


def test_synthetic_gap_threshold_can_be_diagnostic_only_for_smoke(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(profile_config, synthetic_pct=0.1, synthetic_action="diagnostic")
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T15:03:00Z",
                "open": 100.5,
                "high": 101.5,
                "low": 100.0,
                "close": 101.0,
                "volume": 12,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_0",
        max_synthetic_gap_minutes=3,
        profile_config_path=profile_config,
    )

    assert result.synthetic_gap_threshold_breached is True
    assert result.synthetic_gap_threshold_action == "diagnostic"
    assert not any("synthetic threshold breached" in item for item in result.warnings)
    assert result.status == "PASS"


def test_no_synthetic_fill_across_session_boundary(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T21:59:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": "2024-01-02T23:00:00Z",
                "open": 100.5,
                "high": 101.5,
                "low": 100.0,
                "close": 101.0,
                "volume": 12,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.synthetic_rows == 0
    output = pd.read_parquet(out_path)
    assert output["session_id"].nunique() == 2
    assert not output["is_synthetic"].any()


def test_intraday_break_prevents_synthetic_fill_across_equity_index_pause(
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    session_config = tmp_path / "configs" / "market_sessions.yaml"
    _write_session_config(session_config, intraday_breaks=[("15:15", "15:30")])
    common = {
        "rtype": 33,
        "publisher_id": 1,
        "instrument_id": 100,
        "symbol": "ESH4",
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 10,
        "data_quality_status": "available",
        "data_quality_degraded": False,
    }
    _write_raw(
        raw_path,
        [
            {**common, "ts_event": "2024-01-02T21:14:00Z"},
            {**common, "ts_event": "2024-01-02T21:20:00Z"},
            {**common, "ts_event": "2024-01-02T21:30:00Z"},
        ],
    )

    result = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        session_config_path=session_config,
    )

    output = pd.read_parquet(out_path)
    assert result.synthetic_rows == 0
    assert not output["is_synthetic"].any()
    break_row = output.loc[
        output["ts"].eq(pd.Timestamp("2024-01-02T21:20:00Z")),
        "inside_session",
    ]
    assert break_row.iloc[0] == False
    assert output.loc[output["inside_session"], "ts"].tolist() == [
        pd.Timestamp("2024-01-02T21:14:00Z"),
        pd.Timestamp("2024-01-02T21:30:00Z"),
    ]


def test_metadata_with_timestamp_index_file_passes(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw_with_datetime_index(
        raw_path,
        [
            {
                "ts": "2024-01-02T15:00:00Z",
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="metadata_optional_test")

    assert result.status == "PASS"
    assert result.raw_schema_variant == "metadata_no_ts_event"
    assert result.raw_schema_policy == "relaxed"
    assert result.timestamp_source == "dataframe_index"
    assert result.metadata_available is True
    assert result.roll_detection_available is True
    output = pd.read_parquet(out_path)
    assert output.loc[0, "raw_schema_variant"] == "metadata_no_ts_event"
    assert output.loc[0, "timestamp_source"] == "dataframe_index"


def test_full_databento_schema_file_passes(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "CL" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "CL" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 10,
                "symbol": "CLH4",
                "open": 70.0,
                "high": 71.0,
                "low": 69.0,
                "close": 70.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.status == "PASS"
    assert result.raw_schema_variant == "databento_full"
    assert result.raw_schema_policy == "strict"
    assert result.timestamp_source == "ts_event_column"
    assert result.roll_policy_status == "active"


def test_missing_timestamp_fails(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ZN" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ZN" / "2024.parquet"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ZNH4",
                "open": 110.0,
                "high": 111.0,
                "low": 109.0,
                "close": 110.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ]
    ).to_parquet(raw_path, index=False)

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.status == "FAIL"
    assert result.missing_required_raw_cols == ["ts_event"]
    assert result.raw_schema_missing_cols == ["ts_event"]
    assert "missing required raw schema columns: ts_event" in result.failures
    assert not out_path.exists()


def test_missing_ohlcv_column_fails(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ZN" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ZN" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ZNH4",
                "open": 110.0,
                "high": 111.0,
                "low": 109.0,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.status == "FAIL"
    assert result.missing_required_raw_cols == ["close"]
    assert result.raw_schema_missing_cols == ["close"]
    assert "missing required raw schema columns: close" in result.failures
    assert not out_path.exists()


def test_production_profile_fails_if_data_quality_status_missing(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.status == "FAIL"
    assert result.missing_required_raw_cols == ["data_quality_status"]
    assert result.raw_schema_missing_cols == ["data_quality_status"]
    assert "missing required raw schema columns: data_quality_status" in result.failures
    assert not out_path.exists()


def test_production_profile_fails_if_data_quality_degraded_missing(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.status == "FAIL"
    assert result.missing_required_raw_cols == ["data_quality_degraded"]
    assert result.raw_schema_missing_cols == ["data_quality_degraded"]
    assert "missing required raw schema columns: data_quality_degraded" in result.failures
    assert not out_path.exists()


def test_strict_profile_fails_if_required_metadata_values_are_null(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": None,
                "publisher_id": None,
                "instrument_id": None,
                "symbol": None,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.status == "FAIL"
    assert result.missing_required_raw_cols == [
        "rtype",
        "publisher_id",
        "instrument_id",
        "symbol",
    ]
    assert (
        "null or blank required raw schema columns: rtype, publisher_id, instrument_id, symbol"
        in result.failures
    )
    assert not out_path.exists()


def test_strict_profile_fails_if_symbol_is_blank(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": " ",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.status == "FAIL"
    assert result.missing_required_raw_cols == ["symbol"]
    assert "null or blank required raw schema columns: symbol" in result.failures
    assert not out_path.exists()


def test_strict_profile_fails_if_data_quality_status_is_null(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": None,
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.status == "FAIL"
    assert result.missing_required_raw_cols == ["data_quality_status"]
    assert "null or blank required raw schema columns: data_quality_status" in result.failures
    assert not out_path.exists()


def test_strict_profile_fails_if_data_quality_degraded_is_null(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": None,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    assert result.status == "FAIL"
    assert result.missing_required_raw_cols == ["data_quality_degraded"]
    assert "null or blank required raw schema columns: data_quality_degraded" in result.failures
    assert not out_path.exists()


def test_metadata_optional_test_remains_relaxed_for_null_optional_fields(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": None,
                "publisher_id": None,
                "instrument_id": None,
                "symbol": " ",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": None,
                "data_quality_degraded": None,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="metadata_optional_test")

    assert result.status == "WARN"
    assert result.raw_schema_policy == "relaxed"
    assert result.failures == []
    assert out_path.exists()
    output = pd.read_parquet(out_path)
    assert output.loc[0, "data_quality_status"] == "unknown"
    assert output.loc[0, "data_quality_degraded"] == False


def test_symbol_change_without_instrument_id_does_not_activate_roll_window(
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    reports_root = tmp_path / "reports" / "causal_base"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "ts_event": "2024-01-02T15:00:00Z",
                "symbol": "ESH4",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
            },
            {
                "ts_event": "2024-01-02T15:01:00Z",
                "symbol": "ESM4",
                "open": 101.0,
                "high": 102.0,
                "low": 100.0,
                "close": 101.5,
                "volume": 11,
            },
        ],
    )

    result = process_file(raw_path, out_path, profile="metadata_optional_test")

    assert result.status == "WARN"
    assert result.roll_detection_available is False
    output = pd.read_parquet(out_path)
    assert output["symbol_change_flag"].sum() == 1
    assert output["instrument_id_change_flag"].sum() == 0
    assert output["roll_boundary_flag"].sum() == 0
    assert output["roll_window_flag"].sum() == 0
    assert output["roll_detection_available"].eq(False).all()

    write_reports([result], reports_root, "metadata_optional_test")
    manifest = json.loads((reports_root / "causal_base_manifest.json").read_text())
    item = manifest["outputs"][0]
    assert item["roll_detection_available"] is False
    assert item["roll_detection_source"] == "unavailable"
    assert item["roll_policy_status"] == "unavailable_metadata"
    assert "roll detection unavailable: missing populated instrument_id" in item["warnings"]


def test_production_profile_fails_if_roll_metadata_missing(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    alias_out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024_alias.parquet"
    _write_raw(
        raw_path,
        [
            {
                "ts_event": "2024-01-02T15:00:00Z",
                "rtype": 33,
                "publisher_id": 1,
                "symbol": "ESH4",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")
    alias_result = process_file(raw_path, alias_out_path, profile="tier_1")

    assert result.status == "FAIL"
    assert result.missing_required_raw_cols == ["instrument_id"]
    assert result.raw_schema_missing_cols == ["instrument_id"]
    assert "missing required raw schema columns: instrument_id" in result.failures
    assert not out_path.exists()
    assert alias_result.status == "FAIL"
    assert alias_result.missing_required_raw_cols == ["instrument_id"]
    assert "missing required raw schema columns: instrument_id" in alias_result.failures
    assert not alias_out_path.exists()


def test_degraded_data_quality_blocks_whole_session_from_causal_valid(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    _write_raw(
        raw_path,
        [
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ES.v.0",
                "ts_event": "2024-01-02T15:00:00Z",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 10,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            },
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ES.v.0",
                "ts_event": "2024-01-02T15:01:00Z",
                "open": 100.5,
                "high": 101.5,
                "low": 100.0,
                "close": 101.0,
                "volume": 12,
                "data_quality_status": "degraded",
                "data_quality_degraded": True,
            },
        ],
    )

    result = process_file(raw_path, out_path, profile="tier_1")

    output = pd.read_parquet(out_path)
    raw_rows = output[output["raw_row_present"]]
    assert result.degraded_bar_rows == 1
    assert result.degraded_session_rows == 1
    assert raw_rows["session_data_quality_degraded"].all()
    assert not raw_rows["trainable_data_quality"].any()
    assert not raw_rows["causal_valid"].any()
    assert raw_rows["causal_invalid_reason"].str.contains("degraded_session").all()


def test_degraded_warning_only_triggers_above_threshold(tmp_path: Path) -> None:
    raw_path = tmp_path / "data" / "raw" / "ES" / "2024.parquet"
    out_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    high_threshold_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_profile_config(high_threshold_config, degraded_pct=100.0)
    rows = []
    for i, degraded in enumerate([False, True, False]):
        rows.append(
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ES.v.0",
                "ts_event": pd.Timestamp("2024-01-02T15:00:00Z") + pd.Timedelta(minutes=i),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 10,
                "data_quality_status": "degraded" if degraded else "available",
                "data_quality_degraded": degraded,
            }
        )
    _write_raw(raw_path, rows)

    high = process_file(
        raw_path,
        out_path,
        profile="tier_1",
        profile_config_path=high_threshold_config,
    )
    low = process_file(
        raw_path,
        tmp_path / "data" / "second" / "ES" / "2024.parquet",
        profile="tier_1",
    )

    assert high.degraded_threshold_breached is False
    assert not any("degraded threshold breached" in item for item in high.warnings)
    assert low.degraded_threshold_breached is True
    assert any("degraded threshold breached" in item for item in low.warnings)

