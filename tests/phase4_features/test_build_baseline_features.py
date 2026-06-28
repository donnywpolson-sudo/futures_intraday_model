from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pipeline_gates import file_sha256
from scripts.phase4_features import build_baseline_features as features_mod
from scripts.phase4_features import build_missing_baseline_features as missing_features_mod
from scripts.phase4_features.build_baseline_features import (
    FEATURE_COLS,
    FeatureResult,
    FORBIDDEN_FEATURE_COLUMNS,
    FORBIDDEN_FEATURE_PREFIXES,
    PHASE3_LABEL_SEMANTICS_ID,
    REGIME_LABEL_COLUMNS,
    add_base_market_features,
    add_intermarket_features,
    enrich_label_manifest_gate_evidence,
    process_file,
    resolve_profile_inputs,
    select_profile_inputs,
    shock_decay_features,
    validate_registry,
    write_reports,
)
from scripts.profile_scope import load_profile_scope
from scripts.phase4_features.audit_feature_coverage import (
    build_coverage_audit,
    write_coverage_audit,
)


ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.filterwarnings("ignore:DataFrame is highly fragmented:Warning")


def _write_phase4_profile_config(path: Path, *, profile: str = "research") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
profiles:
  {profile}:
    markets: ["ES"]
    years: [2024]
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_label_manifest(
    path: Path,
    *,
    profile: str,
    output_root: Path,
    output_path: Path,
    status: str = "PASS",
    warning_count: int = 0,
    causal_base_gate: dict[str, object] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "labels",
        "status": status,
        "profile": profile,
        "resolved_profile": profile,
        "output_root": output_root.as_posix(),
        "warning_count": warning_count,
        "failure_count": 0,
        "failures": [],
        "summary": {"fail_count": 0, "warn_count": warning_count},
        "output_file_hashes": {output_path.as_posix(): file_sha256(output_path)},
        "outputs": [
            {
                "market": "ES",
                "year": 2024,
                "status": status,
                "warning_count": warning_count,
                "failure_count": 0,
                "failures": [],
            }
        ],
    }
    if causal_base_gate is not None:
        payload["causal_base_manifest_gate"] = causal_base_gate
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _accepted_6e_caveats() -> list[dict[str, object]]:
    return [
        {
            "market": "6E",
            "year": 2023,
            "category": "vendor_trusted_ohlcv_no_trade",
            "metric": "synthetic_rows_pct",
            "observed": 2.057954,
            "approved_limit": 2.1,
            "warning": "synthetic threshold breached: rows_pct=2.057954 max_gap_minutes=48",
        },
        {
            "market": "6E",
            "year": 2024,
            "category": "vendor_trusted_ohlcv_no_trade",
            "metric": "synthetic_rows_pct",
            "observed": 2.539287,
            "approved_limit": 2.6,
            "warning": "synthetic threshold breached: rows_pct=2.539287 max_gap_minutes=54",
        },
    ]


def test_phase4_cli_output_root_has_no_implicit_default() -> None:
    args = features_mod.build_arg_parser().parse_args([])
    missing_args = missing_features_mod.build_arg_parser().parse_args([])

    assert args.output_root is None
    assert missing_args.output_root is None


def test_phase4_main_missing_output_root_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["build_baseline_features.py"])

    with pytest.raises(SystemExit) as exc:
        features_mod.main()

    assert exc.value.code == 2
    assert (
        "--output-root is required; pass an explicit feature output root"
        in capsys.readouterr().err
    )


def test_missing_phase4_main_missing_output_root_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["build_missing_baseline_features.py"])

    with pytest.raises(SystemExit) as exc:
        missing_features_mod.main()

    assert exc.value.code == 2
    assert (
        "--output-root is required; pass an explicit feature output root"
        in capsys.readouterr().err
    )


def test_missing_phase4_build_requires_explicit_output_root() -> None:
    with pytest.raises(
        ValueError,
        match="output_root is required; pass an explicit feature output root",
    ):
        missing_features_mod.build_missing_features()


def test_phase4_coverage_audit_requires_output_root_or_config_value(tmp_path: Path) -> None:
    profile_config = _write_phase4_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")

    with pytest.raises(ValueError, match="feature_matrix_root is required"):
        build_coverage_audit(
            profile="research",
            input_root=tmp_path / "data" / "labeled",
            profile_config=profile_config,
        )


def test_phase4_coverage_audit_accepts_explicit_output_root_without_config_value(
    tmp_path: Path,
) -> None:
    profile_config = _write_phase4_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    output_root = tmp_path / "explicit" / "features"

    audit = build_coverage_audit(
        profile="research",
        input_root=tmp_path / "data" / "labeled",
        output_root=output_root,
        profile_config=profile_config,
    )

    assert Path(str(audit["output_root"])).as_posix() == output_root.as_posix()


def test_phase4_coverage_audit_accepts_approved_rebuilt_config_root(tmp_path: Path) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    approved_root = Path("data/feature_matrices/baseline_tier1_rebuild_v1")
    profile_config.parent.mkdir(parents=True, exist_ok=True)
    profile_config.write_text(
        "\n".join(
            [
                "paths:",
                f"  feature_matrix_root: {approved_root.as_posix()}",
                "profiles:",
                "  research:",
                "    markets: [\"ES\"]",
                "    years: [2024]",
                "",
            ]
        ),
        encoding="utf-8",
    )

    audit = build_coverage_audit(
        profile="research",
        input_root=tmp_path / "data" / "labeled",
        profile_config=profile_config,
    )

    assert Path(str(audit["output_root"])).as_posix() == approved_root.as_posix()


def test_phase4_main_rejects_warn_label_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "labeled"
    input_path = input_root / "ES" / "2024.parquet"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"labels")
    profile_config = _write_phase4_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    manifest = _write_label_manifest(
        tmp_path / "reports" / "labels" / "label_manifest.json",
        profile="research",
        output_root=input_root,
        output_path=input_path,
        status="WARN",
        warning_count=1,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_baseline_features.py",
            "--profile",
            "research",
            "--input-root",
            input_root.as_posix(),
            "--output-root",
            (tmp_path / "data" / "feature_matrices" / "baseline").as_posix(),
            "--reports-root",
            (tmp_path / "reports" / "features").as_posix(),
            "--profile-config",
            profile_config.as_posix(),
            "--costs-config",
            (tmp_path / "configs" / "costs.yaml").as_posix(),
            "--label-manifest",
            manifest.as_posix(),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        features_mod.main()

    assert "label_manifest_gate failed" in str(exc.value)


def test_phase4_main_accepts_passed_label_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "labeled"
    input_path = input_root / "ES" / "2024.parquet"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"labels")
    profile_config = _write_phase4_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    manifest = _write_label_manifest(
        tmp_path / "reports" / "labels" / "label_manifest.json",
        profile="research",
        output_root=input_root,
        output_path=input_path,
    )
    captured: dict[str, object] = {}

    def fake_process_file(
        input_path: Path,
        output_path: Path,
        *,
        profile: str,
        costs_config: Path,
        input_root: Path,
    ) -> features_mod.FeatureResult:
        return features_mod.FeatureResult(
            profile=profile,
            market=input_path.parent.name,
            year=int(input_path.stem),
            input_path=input_path.as_posix(),
            output_path=output_path.as_posix(),
        )

    def fake_write_reports(*args: object, **kwargs: object) -> None:
        captured["gate"] = kwargs["label_gate"]

    monkeypatch.setattr(features_mod, "process_file", fake_process_file)
    monkeypatch.setattr(features_mod, "write_reports", fake_write_reports)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_baseline_features.py",
            "--profile",
            "research",
            "--input-root",
            input_root.as_posix(),
            "--output-root",
            (tmp_path / "data" / "feature_matrices" / "baseline").as_posix(),
            "--reports-root",
            (tmp_path / "reports" / "features").as_posix(),
            "--profile-config",
            profile_config.as_posix(),
            "--costs-config",
            (tmp_path / "configs" / "costs.yaml").as_posix(),
            "--label-manifest",
            manifest.as_posix(),
        ],
    )

    assert features_mod.main() == 0
    assert captured["gate"]["status"] == "PASS"  # type: ignore[index]


def test_phase4_main_carries_label_causal_gate_and_accepted_caveats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "labeled"
    input_path = input_root / "ES" / "2024.parquet"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"labels")
    profile_config = _write_phase4_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    causal_gate = {
        "gate": "causal_base_manifest_gate",
        "status": "PASS",
        "manifest_path": "reports/data_audit/causal_base_repair_plan/tier1_candidate_v1/causal_base_manifest.json",
        "manifest_hash": "candidate-hash",
        "accepted_readiness_exception_count": 2,
        "accepted_readiness_exceptions": _accepted_6e_caveats(),
    }
    manifest = _write_label_manifest(
        tmp_path / "reports" / "labels" / "label_manifest.json",
        profile="research",
        output_root=input_root,
        output_path=input_path,
        causal_base_gate=causal_gate,
    )
    captured: dict[str, object] = {}

    def fake_process_file(
        input_path: Path,
        output_path: Path,
        *,
        profile: str,
        costs_config: Path,
        input_root: Path,
    ) -> features_mod.FeatureResult:
        return features_mod.FeatureResult(
            profile=profile,
            market=input_path.parent.name,
            year=int(input_path.stem),
            input_path=input_path.as_posix(),
            output_path=output_path.as_posix(),
        )

    def fake_write_reports(*args: object, **kwargs: object) -> None:
        captured["gate"] = kwargs["label_gate"]

    monkeypatch.setattr(features_mod, "process_file", fake_process_file)
    monkeypatch.setattr(features_mod, "write_reports", fake_write_reports)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_baseline_features.py",
            "--profile",
            "research",
            "--input-root",
            input_root.as_posix(),
            "--output-root",
            (tmp_path / "data" / "feature_matrices" / "baseline").as_posix(),
            "--reports-root",
            (tmp_path / "reports" / "features").as_posix(),
            "--profile-config",
            profile_config.as_posix(),
            "--costs-config",
            (tmp_path / "configs" / "costs.yaml").as_posix(),
            "--label-manifest",
            manifest.as_posix(),
        ],
    )

    assert features_mod.main() == 0
    gate = captured["gate"]  # type: ignore[assignment]
    assert gate["status"] == "PASS"  # type: ignore[index]
    assert gate["manifest_path"] == manifest.as_posix()  # type: ignore[index]
    assert gate["label_manifest_causal_base_manifest_gate"] == causal_gate  # type: ignore[index]
    assert gate["accepted_readiness_exception_count"] == 2  # type: ignore[index]
    assert gate["accepted_readiness_exceptions"] == _accepted_6e_caveats()  # type: ignore[index]
    assert validate_registry(FEATURE_COLS) == []


def test_enrich_label_manifest_gate_evidence_is_noop_without_nested_causal_gate() -> None:
    gate = {"gate": "label_manifest_gate", "status": "PASS"}
    enriched = enrich_label_manifest_gate_evidence(
        gate,
        {"stage": "labels", "status": "PASS"},
    )

    assert enriched == gate


def _frame(
    rows: int = 70,
    *,
    market: str = "ES",
    year: int = 2024,
    start: str = "2024-01-02T14:30:00Z",
    segment: str | None = None,
) -> pd.DataFrame:
    ts = pd.date_range(start, periods=rows, freq="min", tz="UTC")
    close = pd.Series(100.0 + np.arange(rows, dtype=float))
    segment_id = segment or f"{market}_{year}_seg0"
    df = pd.DataFrame(
        {
            "ts": ts,
            "market": market,
            "year": year,
            "symbol": f"{market}.v.0",
            "instrument_id": 1,
            "publisher_id": 1,
            "rtype": 33,
            "open": close - 0.25,
            "high": close + 0.50,
            "low": close - 0.50,
            "close": close,
            "volume": 100.0 + np.arange(rows, dtype=float),
            "raw_row_present": True,
            "is_synthetic": False,
            "synthetic_gap_id": pd.NA,
            "synthetic_gap_size_minutes": pd.NA,
            "synthetic_gap_reason": "",
            "valid_ohlcv": True,
            "data_quality_status": "available",
            "data_quality_degraded": False,
            "session_data_quality_degraded": False,
            "trainable_data_quality": True,
            "inside_session": True,
            "causal_valid": True,
            "causal_invalid_reason": "",
            "session_id": f"{market}_{year}_session",
            "session_date": "2024-01-02",
            "session_segment_id": segment_id,
            "boundary_session_flag": False,
            "minutes_since_session_open": np.arange(rows, dtype=float),
            "minutes_until_session_close": 390.0 - np.arange(rows, dtype=float),
            "session_progress": np.arange(rows, dtype=float) / 390.0,
            "minute_of_day": 510 + np.arange(rows),
            "day_of_week": 1,
            "roll_window_flag": False,
            "target_valid": True,
            "target_invalid_reason": "",
            "target_ret_15m": 0.0,
            "target_ret_ticks_15m": 0.0,
            "target_gross_dollars_15m": 0.0,
            "target_estimated_cost_ticks": 2.0,
            "target_estimated_cost_dollars": 25.0,
            "target_net_ticks_after_est_cost": 0.0,
            "target_net_dollars_after_est_cost": 0.0,
            "target_sign_15m": 0,
            "target_sign_with_deadzone": 0,
            "target_tradeable_after_cost": False,
            "target_horizon_bars": 15,
            "mae_ticks_15m": 0.0,
            "mfe_ticks_15m": 0.0,
            "fade_long_success_15m": False,
            "fade_short_success_15m": False,
            "target_fade_long_success_15m": False,
            "target_fade_short_success_15m": False,
            "target_fade_success_15m": False,
            "trend_danger_up_30m": False,
            "trend_danger_down_30m": False,
            "target_trend_adverse_long_30m": False,
            "target_trend_favorable_long_30m": False,
            "target_trend_adverse_short_30m": False,
            "target_trend_favorable_short_30m": False,
            "target_trend_danger_long_30m": False,
            "target_trend_danger_short_30m": False,
            "target_trend_danger_30m": False,
            "revert_to_vwap_30m": False,
            "revert_to_session_mid_30m": False,
            "source_path": "fixture",
            "source_file_hash": "hash",
            "source_row_number": np.arange(rows),
            "raw_schema_variant": "fixture",
            "timestamp_source": "fixture",
            "metadata_available": True,
            "roll_detection_available": True,
            "roll_detection_source": "fixture",
            "roll_policy_status": "active",
            "label_semantics": PHASE3_LABEL_SEMANTICS_ID,
            "cost_source": "fixture_costs",
            "cost_provisional": False,
        }
    )
    return df


def _write_costs(path: Path, market: str = "ES", tick_size: float = 0.25) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "markets:",
                f"  {market}:",
                f"    tick_size: {tick_size}",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_profile_aliases_resolve_for_phase4() -> None:
    inputs = resolve_profile_inputs("tier_1", ROOT / "data" / "labeled")
    assert [(market, year) for market, year, _ in inputs] == [
        ("ES", 2023),
        ("ES", 2024),
        ("CL", 2023),
        ("CL", 2024),
        ("ZN", 2023),
        ("ZN", 2024),
        ("6E", 2023),
        ("6E", 2024),
    ]


def test_phase4_input_filters_and_one_based_shards_are_deterministic(tmp_path: Path) -> None:
    inputs = [
        ("ES", 2023, tmp_path / "ES" / "2023.parquet"),
        ("ES", 2024, tmp_path / "ES" / "2024.parquet"),
        ("CL", 2023, tmp_path / "CL" / "2023.parquet"),
        ("CL", 2024, tmp_path / "CL" / "2024.parquet"),
    ]

    selected, selection = select_profile_inputs(
        inputs,
        markets={"ES", "CL"},
        years={2023, 2024},
        shard_count=2,
        shard_index=1,
    )

    assert [(market, year) for market, year, _ in selected] == [
        ("ES", 2023),
        ("CL", 2023),
    ]
    assert selection["profile_input_count"] == 4
    assert selection["selected_input_count"] == 2
    assert selection["requested_markets"] == ["CL", "ES"]
    assert selection["requested_years"] == [2023, 2024]
    assert selection["shard_count"] == 2
    assert selection["shard_index"] == 1
    assert selection["selected_markets"] == ["CL", "ES"]
    assert selection["selected_years"] == [2023]


def test_ret_1_uses_only_completed_prior_bar_and_invalidates_bad_prior() -> None:
    df = _frame(5)
    out = add_base_market_features(df, tick_size=0.25)
    assert out.loc[1, "feature_ret_1"] == (101.0 / 100.0) - 1.0

    df.loc[1, "is_synthetic"] = True
    out = add_base_market_features(df, tick_size=0.25)
    assert pd.isna(out.loc[2, "feature_ret_1"])
    assert out.loc[2, "feature_input_valid"] is True or bool(out.loc[2, "feature_input_valid"])


def test_multi_bar_returns_require_full_valid_lookback() -> None:
    df = _frame(30)
    df.loc[3, "is_synthetic"] = True
    out = add_base_market_features(df, tick_size=0.25)
    assert pd.isna(out.loc[5, "feature_ret_5"])
    assert pd.isna(out.loc[10, "feature_ret_10"])
    assert pd.isna(out.loc[20, "feature_ret_20"])
    assert pd.notna(out.loc[9, "feature_ret_5"])


def test_rolling_features_do_not_cross_session_or_invalid_rows() -> None:
    df = _frame(35)
    df.loc[10, "causal_valid"] = False
    out = add_base_market_features(df, tick_size=0.25)
    assert pd.isna(out.loc[30, "feature_effort_result_30"])

    df2 = _frame(40)
    df2.loc[:19, "session_segment_id"] = "seg_a"
    df2.loc[20:, "session_segment_id"] = "seg_b"
    out2 = add_base_market_features(df2, tick_size=0.25)
    assert pd.isna(out2.loc[25, "feature_realized_range_30"])


def test_invalid_lookback_makes_inside_bar_count_nan() -> None:
    df = _frame(40)
    df.loc[10, "is_synthetic"] = True
    out = add_base_market_features(df, tick_size=0.25)
    assert pd.isna(out.loc[25, "feature_inside_bar_count_20"])
    assert pd.notna(out.loc[31, "feature_inside_bar_count_20"])


def test_invalid_lookback_makes_large_bar_count_nan() -> None:
    df = _frame(140)
    df.loc[100, "valid_ohlcv"] = False
    out = add_base_market_features(df, tick_size=0.25)
    assert pd.isna(out.loc[120, "feature_large_bar_count_30"])


def test_count_style_rolling_features_do_not_treat_invalid_rows_as_zero() -> None:
    df = _frame(140)
    df.loc[100, "roll_window_flag"] = True
    out = add_base_market_features(df, tick_size=0.25)
    assert pd.isna(out.loc[110, "feature_directional_bar_ratio_15"])
    assert pd.isna(out.loc[120, "feature_directional_bar_ratio_30"])
    assert pd.isna(out.loc[120, "feature_bars_above_vwap_30"])
    assert pd.isna(out.loc[120, "feature_bars_below_vwap_30"])
    assert pd.isna(out.loc[120, "feature_session_acceptance_above_mid"])
    assert pd.isna(out.loc[120, "feature_session_acceptance_below_mid"])


def test_breakout_uses_prior_range_excluding_current_bar() -> None:
    df = _frame(25)
    df.loc[:19, "high"] = 105.0
    df.loc[20, "high"] = 110.0
    df.loc[20, "close"] = 104.0
    out = add_base_market_features(df, tick_size=0.25)
    assert out.loc[20, "feature_failed_breakout_above_20"] == True
    assert out.loc[20, "feature_prior_high_20_dist"] == (104.0 - 105.0) / 0.25


def test_session_vwap_and_high_low_use_session_so_far_only() -> None:
    df = _frame(3)
    out = add_base_market_features(df, tick_size=0.25)
    expected_vwap_1 = ((100.0 * 100.0) + (101.0 * 101.0)) / 201.0
    assert out.loc[1, "feature_session_vwap_dist"] == (101.0 - expected_vwap_1) / 0.25
    assert out.loc[1, "feature_session_high_dist"] == (101.0 - 101.5) / 0.25
    assert out.loc[1, "feature_session_low_dist"] == (101.0 - 99.5) / 0.25


def test_opening_range_and_open_drive_require_first_30_valid_rows() -> None:
    df = _frame(35)
    out = add_base_market_features(df, tick_size=0.25)
    assert out.loc[28, "feature_opening_range_30_ready"] == False
    assert out.loc[29, "feature_opening_range_30_ready"] == True
    assert pd.notna(out.loc[29, "feature_opening_range_30_high_dist"])

    df.loc[5, "is_synthetic"] = True
    out_bad = add_base_market_features(df, tick_size=0.25)
    assert out_bad["feature_opening_range_30_ready"].eq(False).all()
    assert out_bad["feature_open_drive_up"].eq(False).all()


def test_validity_does_not_depend_on_target_valid_but_training_valid_does() -> None:
    df = _frame(5)
    df.loc[2, "target_valid"] = False
    for col in ("causal_valid", "valid_ohlcv", "is_synthetic", "roll_window_flag", "boundary_session_flag"):
        df.loc[3, col] = False if col in {"causal_valid", "valid_ohlcv"} else True
    out = add_base_market_features(df, tick_size=0.25)
    assert bool(out.loc[2, "feature_input_valid"]) is True
    assert bool(out.loc[2, "training_row_valid"]) is False
    assert bool(out.loc[3, "feature_input_valid"]) is False


def test_5m_15m_60m_features_use_completed_rows_only() -> None:
    df = _frame(70)
    out = add_base_market_features(df, tick_size=0.25)
    assert out.loc[15, "feature_5m_ret_3"] == (115.0 / 100.0) - 1.0
    assert out.loc[60, "feature_15m_ret_4"] == (160.0 / 100.0) - 1.0
    assert pd.isna(out.loc[59, "feature_60m_trend_slope"])


def test_higher_timeframe_returns_require_full_valid_lookback() -> None:
    df = _frame(130)
    df.loc[10, "roll_window_flag"] = True
    out = add_base_market_features(df, tick_size=0.25)
    assert pd.isna(out.loc[15, "feature_5m_ret_3"])
    assert pd.isna(out.loc[60, "feature_15m_ret_4"])
    assert pd.notna(out.loc[26, "feature_5m_ret_3"])
    assert pd.notna(out.loc[71, "feature_15m_ret_4"])


def test_intermarket_features_use_exact_timestamps_and_no_self_target_columns(tmp_path: Path) -> None:
    root = tmp_path / "labeled"
    for market in ("CL", "ES", "ZN", "6E"):
        df = _frame(70, market=market)
        if market == "ES":
            df["ts"] = df["ts"] + pd.Timedelta(seconds=30)
        path = root / market / "2024.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    base = add_base_market_features(_frame(70, market="CL"), tick_size=0.01)
    out, missing = add_intermarket_features(base, market="CL", year=2024, input_root=root)
    assert out["feature_rel_ret_vs_ES_15"].isna().all()
    assert missing["feature_rel_ret_vs_ES_15"] == 1.0
    assert "target_valid" not in [col for col in out.columns if col.startswith("feature_")]
    assert out["feature_rel_ret_vs_CL_15"].isna().all()


def test_intermarket_returns_require_other_market_full_valid_lookback(tmp_path: Path) -> None:
    root = tmp_path / "labeled"
    for market in ("CL", "ES", "ZN", "6E"):
        df = _frame(80, market=market)
        if market == "ES":
            df.loc[10, "is_synthetic"] = True
        path = root / market / "2024.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    base = add_base_market_features(_frame(80, market="CL"), tick_size=0.01)
    out, _ = add_intermarket_features(base, market="CL", year=2024, input_root=root)
    assert pd.isna(out.loc[15, "feature_rel_ret_vs_ES_15"])
    assert pd.notna(out.loc[26, "feature_rel_ret_vs_ES_15"])


def test_tier1_risk_score_is_usable_without_zero_filling_self_market(tmp_path: Path) -> None:
    root = tmp_path / "labeled"
    for market in ("CL", "ES", "ZN", "6E"):
        path = root / market / "2024.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        _frame(90, market=market).to_parquet(path, index=False)

    base = add_base_market_features(_frame(90, market="CL"), tick_size=0.01)
    out, missing = add_intermarket_features(base, market="CL", year=2024, input_root=root)
    assert out["feature_tier1_risk_on_score_30"].notna().any()
    assert missing["feature_tier1_risk_on_score_30"] < 1.0
    assert out["feature_rel_ret_vs_CL_15"].isna().all()


def test_intermarket_composite_features_use_current_market_leg(tmp_path: Path) -> None:
    root = tmp_path / "labeled"
    for market in ("CL", "ES", "ZN", "6E"):
        path = root / market / "2024.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        _frame(90, market=market).to_parquet(path, index=False)

    es_base = add_base_market_features(_frame(90, market="ES"), tick_size=0.25)
    es_out, _ = add_intermarket_features(es_base, market="ES", year=2024, input_root=root)

    assert es_out["feature_rel_ret_vs_ES_15"].isna().all()
    assert es_out["feature_es_zn_divergence_30"].notna().any()
    assert es_out["feature_cl_es_divergence_30"].notna().any()
    assert es_out["feature_es_zn_risk_regime_30"].notna().any()
    assert es_out["feature_cl_es_macro_divergence_30"].notna().any()

    cl_base = add_base_market_features(_frame(90, market="CL"), tick_size=0.01)
    cl_out, _ = add_intermarket_features(cl_base, market="CL", year=2024, input_root=root)

    assert cl_out["feature_rel_ret_vs_CL_15"].isna().all()
    assert cl_out["feature_cl_es_divergence_30"].notna().any()
    assert cl_out["feature_cl_es_macro_divergence_30"].notna().any()


def test_shock_decay_features_do_not_explode_on_tiny_directional_denominator() -> None:
    df = pd.DataFrame(
        {
            "close": [100.0, 100.1],
            "high": [100.5, 100.74],
            "low": [100.0, 99.9],
        }
    )
    valid = pd.Series([True, True])
    segment = pd.Series(["session", "session"])
    shock = pd.Series([True, False])
    shock_direction = pd.Series([1.0, 0.0])
    true_range = pd.Series([1.0, 0.84])

    retrace, continuation, decay = shock_decay_features(
        df,
        valid,
        segment,
        true_range,
        shock,
        shock_direction,
    )

    assert continuation.iloc[1] == pytest.approx(0.24)
    assert retrace.iloc[1] == 0.0
    assert decay.iloc[1] == pytest.approx(0.92)


def test_registry_excludes_targets_audit_source_and_forbidden_columns() -> None:
    assert validate_registry(FEATURE_COLS) == []
    assert all(col.startswith("feature_") for col in FEATURE_COLS)
    assert not any(col.startswith("target_") for col in FEATURE_COLS)
    for column in (
        "target_fade_long_success_15m",
        "target_fade_short_success_15m",
        "target_fade_success_15m",
        "target_trend_adverse_long_30m",
        "target_trend_favorable_long_30m",
        "target_trend_adverse_short_30m",
        "target_trend_favorable_short_30m",
        "target_trend_danger_long_30m",
        "target_trend_danger_short_30m",
        "target_trend_danger_30m",
    ):
        assert column in REGIME_LABEL_COLUMNS
        assert column in FORBIDDEN_FEATURE_COLUMNS
        assert column not in FEATURE_COLS
    assert "instrument_id" not in FEATURE_COLS
    assert "feature_input_valid" not in FEATURE_COLS
    injected = validate_registry([*FEATURE_COLS, "target_ret_15m"])
    assert injected
    assert any("forbidden columns" in failure for failure in injected)
    for prefix in (
        "future_",
        "path_",
        "cost_",
        "pnl",
        "execution_",
        "entry_",
        "exit_",
        "feature_future_",
    ):
        assert prefix in FORBIDDEN_FEATURE_PREFIXES
    raw_enrichment_injected = validate_registry(
        [*FEATURE_COLS, "status_action_name", "stat_open_interest"]
    )
    assert any("forbidden columns" in failure for failure in raw_enrichment_injected)
    leakage_injected = validate_registry([*FEATURE_COLS, "feature_future_return_15m"])
    assert any("forbidden columns" in failure for failure in leakage_injected)


def _process_fixture(
    tmp_path: Path,
    df: pd.DataFrame,
    *,
    costs_market: str = "ES",
    tick_size: float = 0.25,
) -> tuple[object, Path]:
    input_root = tmp_path / "data" / "labeled"
    output_root = tmp_path / "data" / "feature_matrices" / "baseline"
    input_path = input_root / "ES" / "2024.parquet"
    output_path = output_root / "ES" / "2024.parquet"
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml", costs_market, tick_size)
    input_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(input_path, index=False)
    result = process_file(
        input_path,
        output_path,
        profile="tier_1",
        costs_config=costs_path,
        input_root=input_root,
    )
    return result, output_path


def test_process_file_fails_when_label_contract_fields_are_missing(tmp_path: Path) -> None:
    df = _frame(70).drop(columns=["label_semantics", "cost_source", "cost_provisional"])
    result, output_path = _process_fixture(tmp_path, df)

    assert result.status == "FAIL"
    assert any("missing required Phase 3 label columns" in failure for failure in result.failures)
    assert not output_path.exists()


def test_process_file_fails_when_label_semantics_is_noncanonical(tmp_path: Path) -> None:
    df = _frame(70)
    df["label_semantics"] = "wrong"
    result, output_path = _process_fixture(tmp_path, df)

    assert result.status == "FAIL"
    assert any("noncanonical label_semantics" in failure for failure in result.failures)
    assert not output_path.exists()


def test_process_file_fails_when_costs_are_provisional(tmp_path: Path) -> None:
    df = _frame(70)
    df["cost_provisional"] = True
    result, output_path = _process_fixture(tmp_path, df)

    assert result.status == "FAIL"
    assert any("provisional Phase 3 costs" in failure for failure in result.failures)
    assert not output_path.exists()


@pytest.mark.parametrize("value", [False, pd.NA])
def test_process_file_fails_when_roll_detection_is_unavailable(
    tmp_path: Path,
    value: object,
) -> None:
    df = _frame(70)
    df["roll_detection_available"] = df["roll_detection_available"].astype("object")
    df.loc[5, "roll_detection_available"] = value
    result, output_path = _process_fixture(tmp_path, df)

    assert result.status == "FAIL"
    assert any(
        "roll_detection_available must be true" in failure for failure in result.failures
    )
    assert not output_path.exists()


def test_process_file_fails_when_market_tick_size_is_missing(tmp_path: Path) -> None:
    result, output_path = _process_fixture(tmp_path, _frame(70), costs_market="CL")

    assert result.status == "FAIL"
    assert any("missing tick_size for market: ES" in failure for failure in result.failures)
    assert not output_path.exists()


def test_process_file_writes_matrix_registries_and_reports(tmp_path: Path) -> None:
    input_root = tmp_path / "data" / "labeled"
    output_root = tmp_path / "data" / "feature_matrices" / "baseline"
    reports_root = tmp_path / "reports" / "features_baseline"
    input_path = input_root / "ES" / "2024.parquet"
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    input_path.parent.mkdir(parents=True, exist_ok=True)
    _frame(70).to_parquet(input_path, index=False)

    result = process_file(
        input_path,
        output_root / "ES" / "2024.parquet",
        profile="tier_1",
        costs_config=costs_path,
        input_root=input_root,
    )
    write_reports(
        [result],
        profile="tier_1",
        input_root=input_root,
        output_root=output_root,
        reports_root=reports_root,
        input_selection={
            "profile_input_count": 8,
            "selected_input_count": 1,
            "shard_count": 8,
            "shard_index": 1,
        },
    )

    output = pd.read_parquet(output_root / "ES" / "2024.parquet")
    assert result.status in {"PASS", "WARN"}
    assert set(FEATURE_COLS).issubset(output.columns)
    for column in (
        "target_fade_long_success_15m",
        "target_fade_short_success_15m",
        "target_fade_success_15m",
        "target_trend_adverse_long_30m",
        "target_trend_favorable_long_30m",
        "target_trend_adverse_short_30m",
        "target_trend_favorable_short_30m",
        "target_trend_danger_long_30m",
        "target_trend_danger_short_30m",
        "target_trend_danger_30m",
    ):
        assert column in output.columns
        assert column not in FEATURE_COLS
    assert "feature_input_valid" not in FEATURE_COLS
    assert (output_root / "feature_cols.json").exists()
    assert (output_root / "target_cols.json").exists()
    assert (output_root / "metadata_cols.json").exists()
    assert (output_root / "excluded_cols.json").exists()
    assert (reports_root / "baseline_feature_manifest.json").exists()
    assert (reports_root / "baseline_feature_report.json").exists()
    assert (reports_root / "feature_registry.json").exists()
    assert (reports_root / "feature_correlation_report.csv").exists()
    registry = json.loads((reports_root / "feature_registry.json").read_text())
    assert registry["feature_families"]["feature_ret_1"] == "baseline_ohlcv"
    manifest = json.loads((reports_root / "baseline_feature_manifest.json").read_text())
    report = json.loads((reports_root / "baseline_feature_report.json").read_text())
    for payload in (manifest, report):
        assert payload["input_root"] == input_root.as_posix()
        assert payload["output_root"] == output_root.as_posix()
        assert payload["input_selection"]["profile_input_count"] == 8
        assert payload["input_selection"]["selected_input_count"] == 1
        assert payload["input_selection"]["shard_count"] == 8
        assert payload["input_selection"]["shard_index"] == 1
        assert payload["partial_scope"] is True
        assert payload["authoritative"] is False
        assert payload["expected_input_count"] == 8
        assert payload["selected_input_count"] == 1
        assert payload["actual_input_count"] == 1
        assert len(payload["missing_market_years"]) == 7
        assert payload["config_hash"]
        assert payload["input_file_hashes"][input_path.as_posix()] != "missing"
        assert payload["output_file_hashes"][
            (output_root / "ES" / "2024.parquet").as_posix()
        ] != "missing"


def _feature_result_fixture(tmp_path: Path, market: str, year: int, *, profile: str) -> FeatureResult:
    input_path = tmp_path / "data" / "labeled" / market / f"{year}.parquet"
    output_path = tmp_path / "data" / "feature_matrices" / "baseline" / market / f"{year}.parquet"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"source": [1]}).to_parquet(input_path, index=False)
    frame = pd.DataFrame({column: [0.0] for column in FEATURE_COLS})
    frame["training_row_valid"] = True
    frame.to_parquet(output_path, index=False)
    return FeatureResult(
        profile=profile,
        market=market,
        year=year,
        input_path=input_path.as_posix(),
        output_path=output_path.as_posix(),
        input_rows=1,
        output_rows=1,
        feature_input_valid_rows=1,
        training_row_valid_rows=1,
        target_valid_rows=1,
        feature_count=len(FEATURE_COLS),
    )


def test_full_tier1_feature_manifest_can_be_authoritative(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None
    input_root = tmp_path / "data" / "labeled"
    output_root = tmp_path / "data" / "feature_matrices" / "baseline"
    reports_root = tmp_path / "reports" / "features_baseline"
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    results = [
        _feature_result_fixture(tmp_path, market, year, profile="tier_1")
        for market in scope.markets
        for year in scope.years
    ]

    write_reports(
        results,
        profile="tier_1",
        input_root=input_root,
        output_root=output_root,
        reports_root=reports_root,
        costs_config=costs_path,
        input_selection={
            "profile_input_count": len(results),
            "selected_input_count": len(results),
        },
    )

    manifest = json.loads((reports_root / "baseline_feature_manifest.json").read_text())
    assert manifest["partial_scope"] is False
    assert manifest["authoritative"] is True
    assert manifest["expected_input_count"] == len(results) == 8
    assert manifest["actual_input_count"] == 8
    assert manifest["missing_market_years"] == []


def test_full_tier1_feature_manifest_with_warnings_is_scope_authoritative(tmp_path: Path) -> None:
    scope = load_profile_scope("tier_1", Path("configs/alpha_tiered.yaml"))
    assert scope is not None
    input_root = tmp_path / "data" / "labeled"
    output_root = tmp_path / "data" / "feature_matrices" / "baseline"
    reports_root = tmp_path / "reports" / "features_baseline"
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    results = [
        _feature_result_fixture(tmp_path, market, year, profile="tier_1")
        for market in scope.markets
        for year in scope.years
    ]
    results[0].warnings.append("fixture data-quality warning")

    write_reports(
        results,
        profile="tier_1",
        input_root=input_root,
        output_root=output_root,
        reports_root=reports_root,
        costs_config=costs_path,
        input_selection={
            "profile_input_count": len(results),
            "selected_input_count": len(results),
        },
    )

    manifest = json.loads((reports_root / "baseline_feature_manifest.json").read_text())
    assert manifest["status"] == "WARN"
    assert manifest["partial_scope"] is False
    assert manifest["authoritative"] is True
    assert manifest["failure_count"] == 0


def test_non_tier1_feature_manifest_keeps_compatible_authority_shape(tmp_path: Path) -> None:
    input_root = tmp_path / "data" / "labeled"
    output_root = tmp_path / "data" / "feature_matrices" / "baseline"
    reports_root = tmp_path / "reports" / "features_baseline"
    costs_path = _write_costs(tmp_path / "configs" / "costs.yaml")
    result = _feature_result_fixture(tmp_path, "ES", 2024, profile="tier_0")

    write_reports(
        [result],
        profile="tier_0",
        input_root=input_root,
        output_root=output_root,
        reports_root=reports_root,
        costs_config=costs_path,
    )

    manifest = json.loads((reports_root / "baseline_feature_manifest.json").read_text())
    assert "partial_scope" not in manifest
    assert "authoritative" not in manifest


def test_phase4_coverage_audit_compares_labeled_to_canonical_features(tmp_path: Path) -> None:
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    input_root = tmp_path / "data" / "labeled"
    output_root = tmp_path / "data" / "feature_matrices" / "baseline"
    reports_root = tmp_path / "reports" / "phase4"
    profile_config.parent.mkdir(parents=True, exist_ok=True)
    profile_config.write_text(
        """
paths:
  labeled_root: data/labeled
  feature_matrix_root: null
profiles:
  tier_3_research:
    markets: ["ES", "RTY"]
    years: [2010, 2017]
aliases:
  tier_3: tier_3_research
""".strip(),
        encoding="utf-8",
    )
    for market, year in (("ES", 2010), ("RTY", 2017)):
        path = input_root / market / f"{year}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        _frame(5, market=market, year=year).to_parquet(path, index=False)
    feature_path = output_root / "ES" / "2010.parquet"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    _frame(5).to_parquet(feature_path, index=False)

    audit = build_coverage_audit(
        profile="tier_3",
        input_root=input_root,
        output_root=output_root,
        profile_config=profile_config,
        collect_row_counts=True,
    )
    json_path, csv_path = write_coverage_audit(audit, reports_root)

    assert audit["available_labeled"] == 2
    assert audit["existing_features"] == 1
    assert audit["missing_features"] == 1
    assert audit["missing_tier3_count"] == 1
    assert audit["skipped_count"] == 1
    assert audit["skipped_reasons"] == ["product_unavailable_before_2017"]
    missing = [row for row in audit["rows"] if row["status"] == "missing_feature"]
    assert missing[0]["market"] == "RTY"
    assert missing[0]["year"] == 2017
    assert json_path.exists()
    assert csv_path.exists()

