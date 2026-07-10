"""Shared forbidden-feature checks for feature registries and WFA manifests."""

from __future__ import annotations

from collections.abc import Iterable


REGIME_LABEL_COLUMNS = [
    "mae_ticks_15m",
    "mfe_ticks_15m",
    "fade_long_success_15m",
    "fade_short_success_15m",
    "trend_danger_up_30m",
    "trend_danger_down_30m",
    "revert_to_vwap_30m",
    "revert_to_session_mid_30m",
    "diagnostic_valid_15m",
    "diagnostic_ret_15m",
    "diagnostic_ret_ticks_15m",
    "diagnostic_gross_dollars_15m",
    "diagnostic_mfe_long_ticks_15m",
    "diagnostic_mae_long_ticks_15m",
    "diagnostic_mfe_short_ticks_15m",
    "diagnostic_mae_short_ticks_15m",
    "diagnostic_favorable_after_cost_15m",
]

FORBIDDEN_FEATURE_COLUMNS = {
    "ts",
    "market",
    "year",
    "session_id",
    "session_date",
    "session_segment_id",
    "raw_row_present",
    "is_synthetic",
    "causal_valid",
    "valid_ohlcv",
    "inside_session",
    "boundary_session_flag",
    "feature_input_valid",
    "feature_row_valid",
    "training_row_valid",
    "target_valid",
    "target_invalid_reason",
    *REGIME_LABEL_COLUMNS,
    "label_semantics",
    "cost_source",
    "cost_provisional",
    "target_ret_30m",
    "target_ret_ticks_30m",
    "target_ret_60m",
    "target_ret_ticks_60m",
    "target_net_ticks_after_est_cost",
    "target_tradeable_after_cost",
    "bars_since_roll",
    "bars_until_roll",
    "roll_boundary_flag",
    "roll_window_flag",
    "causal_invalid_reason",
    "symbol_change_flag",
    "instrument_id_change_flag",
    "rtype",
    "publisher_id",
    "instrument_id",
    "symbol",
    "source_file",
    "source_sha256",
    "definition_source_file",
    "definition_source_sha256",
    "status_source_file",
    "status_source_sha256",
    "status_stale",
    "source_path",
    "source_file_hash",
    "source_row_number",
    "raw_schema_variant",
    "timestamp_source",
    "metadata_available",
    "roll_detection_available",
    "roll_detection_source",
    "roll_policy_status",
    "synthetic_gap_id",
    "synthetic_gap_size_minutes",
    "synthetic_gap_reason",
    "data_quality_status",
    "data_quality_degraded",
    "session_data_quality_degraded",
    "trainable_data_quality",
    "settlement",
    "settlement_price",
    "open_interest",
    "cleared_volume",
    "statistics_stale",
}

FORBIDDEN_FEATURE_PREFIXES = (
    "target_",
    "future_",
    "path_",
    "cost_",
    "pnl",
    "execution_",
    "entry_",
    "exit_",
    "regime_",
    "diagnostic_",
    "label_",
    "status_",
    "stat_",
    "statistics_",
    "feature_future_",
    "feature_path_",
    "feature_cost_",
    "feature_pnl",
    "feature_execution_",
    "feature_entry_",
    "feature_exit_",
    "feature_label_",
)


def forbidden_feature_columns(feature_cols: Iterable[str]) -> list[str]:
    return [
        col
        for col in feature_cols
        if col in FORBIDDEN_FEATURE_COLUMNS
        or any(col.startswith(prefix) for prefix in FORBIDDEN_FEATURE_PREFIXES)
    ]


def validate_no_forbidden_features(feature_cols: Iterable[str]) -> list[str]:
    forbidden = forbidden_feature_columns(feature_cols)
    return [f"forbidden columns in feature_cols: {forbidden}"] if forbidden else []
