#!/usr/bin/env python3
"""ES-only Phase 9 smoke harness for pre-registered 30-minute target candidates.

This harness is target-construction feasibility only. It reads existing feature
matrices, writes bounded smoke reports, and does not run WFA, Phase 8,
promotion, downloads, label/feature rebuilds, or saved-prediction evaluation.
"""

from __future__ import annotations

import argparse
import json
import math
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from scripts.phase7_wfa.run_wfa import (
    DEFAULT_INPUT_ROOT,
    DEFAULT_SPLIT_PLAN,
    _file_hash_map,
    _fold_masks,
    _git_commit,
    _load_market_frame,
    _read_json,
    _relative_path,
    _validate_fold_fields,
    _write_json,
    load_feature_cols,
)
from scripts.phase9_research.es_30m_directional_extension_target_harness import (
    DEFAULT_COSTS_CONFIG,
    DEFAULT_REPORTS_ROOT,
    DEFAULT_TARGET_REGISTRY,
    _bool_col,
    _float_or_none,
    _numeric,
    _parse_csv,
    is_leakage_feature,
    load_es_cost_config,
    select_model_features,
)


DEFAULT_RUN = "es_30m_target_smoke"
DEFAULT_TARGET_TRIAL_STATUSES = Path("manifests/target_hypotheses/trial_statuses.jsonl")
DEFAULT_DISCOVERY_FOLDS = tuple(f"ES_research_{idx:04d}" for idx in range(1, 5))
DEFAULT_CONFIRMATION_FOLDS = tuple(f"ES_research_{idx:04d}" for idx in range(5, 9))
DEFAULT_LOCKED_FOLDS = tuple(f"ES_research_{idx:04d}" for idx in range(9, 13))
DEFAULT_TOP_FRACTION = 0.05
MARKET = "ES"
ENTRY_OFFSET_BARS = 1
EXIT_OFFSET_BARS = 31
HORIZON_BARS = EXIT_OFFSET_BARS - ENTRY_OFFSET_BARS
VWAP_RECLAIM_EXIT_OFFSET_BARS = ENTRY_OFFSET_BARS + 15
VWAP_RECLAIM_HORIZON_BARS = VWAP_RECLAIM_EXIT_OFFSET_BARS - ENTRY_OFFSET_BARS
OPENING_DRIVE_BARS = 15
OPENING_DRIVE_FAILED_FOLLOWTHROUGH_EXIT_OFFSET_BARS = ENTRY_OFFSET_BARS + 15
OPENING_DRIVE_FAILED_FOLLOWTHROUGH_HORIZON_BARS = (
    OPENING_DRIVE_FAILED_FOLLOWTHROUGH_EXIT_OFFSET_BARS - ENTRY_OFFSET_BARS
)
SESSION_COMPRESSION_BOX_BARS = 30
SESSION_COMPRESSION_PRIOR_WINDOWS = 120
SESSION_COMPRESSION_MIN_PRIOR_WINDOWS = 60
SESSION_COMPRESSION_BREAKOUT_BUFFER_TICKS = 1.0
VOLUME_PACE_RANGE_BARS = 60
VOLUME_PACE_MIN_BASELINE_SESSIONS = 20
VOLUME_PACE_BREAKOUT_BUFFER_TICKS = 1.0
VOLUME_PACE_RATIO_MIN = 1.5
LATE_SESSION_RANGE_START_MINUTE = 14 * 60
LATE_SESSION_RANGE_END_MINUTE = 15 * 60
LATE_SESSION_CLOSE_MINUTE = 16 * 60
LATE_SESSION_RANGE_REQUIRED_BARS = 60
LATE_SESSION_THRESHOLD_HORIZON_BARS = 60
LATE_SESSION_BREAKOUT_BUFFER_TICKS = 1.0
VOL_LOOKBACK_BARS = 60
VOL_MIN_PERIODS = 20
VOL_MULTIPLIER = 1.0
OPPORTUNITY_RISK_EDGE_RATIO = 0.25
OPENING_RANGE_BARS = 30
EVALUATION_DIRECTIONAL_NET = "directional_net"
EVALUATION_COMPONENT_RANK = "component_rank"

REQUIRED_COLUMNS = (
    "ts",
    "market",
    "year",
    "session_segment_id",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "causal_valid",
    "valid_ohlcv",
    "inside_session",
    "feature_input_valid",
    "feature_row_valid",
    "training_row_valid",
    "target_valid",
    "target_sign_with_deadzone",
    "is_synthetic",
    "roll_window_flag",
    "boundary_session_flag",
)


@dataclass(frozen=True)
class TargetSpec:
    hypothesis_id: str
    target_family: str
    slug: str
    description: str
    apply: Callable[[pd.DataFrame, Mapping[str, float], "TargetSpec"], pd.DataFrame]
    auxiliary_columns: tuple[str, ...] = ()
    component_model_columns: tuple[str, ...] = ()
    rank_score_column: str | None = None
    evaluation_mode: str = EVALUATION_DIRECTIONAL_NET
    horizon_bars: int = HORIZON_BARS
    threshold_description: str = (
        "max(round-turn cost ticks + min_profit_ticks, prior 60-bar 1m close-diff std * sqrt(30))"
    )

    @property
    def valid_column(self) -> str:
        return f"target_valid_{self.slug}"

    @property
    def direction_column(self) -> str:
        return f"target_direction_{self.slug}"

    @property
    def gross_column(self) -> str:
        return f"target_gross_dollars_{self.slug}"

    @property
    def cost_column(self) -> str:
        return f"target_cost_dollars_{self.slug}"

    @property
    def net_column(self) -> str:
        return f"target_net_dollars_{self.slug}"

    @property
    def nonflat_column(self) -> str:
        return f"target_nonflat_{self.slug}"

    @property
    def entry_ts_column(self) -> str:
        return f"target_entry_ts_{self.slug}"

    @property
    def exit_ts_column(self) -> str:
        return f"target_exit_ts_{self.slug}"

    @property
    def threshold_ticks_column(self) -> str:
        return f"target_threshold_ticks_{self.slug}"

    @property
    def target_columns(self) -> list[str]:
        columns = [
            self.valid_column,
            self.direction_column,
            self.gross_column,
            self.cost_column,
            self.net_column,
            self.nonflat_column,
            self.entry_ts_column,
            self.exit_ts_column,
            self.threshold_ticks_column,
            *self.auxiliary_columns,
        ]
        if self.rank_score_column:
            columns.append(self.rank_score_column)
        return sorted(set(columns), key=columns.index)


def _source_columns(features: Sequence[str]) -> list[str]:
    return sorted(set(features) | set(REQUIRED_COLUMNS))


def _row_valid_mask(frame: pd.DataFrame) -> pd.Series:
    return (
        _bool_col(frame, "causal_valid", False)
        & _bool_col(frame, "valid_ohlcv", True)
        & _bool_col(frame, "inside_session", True)
        & _bool_col(frame, "feature_input_valid", False)
        & _bool_col(frame, "feature_row_valid", True)
        & _bool_col(frame, "training_row_valid", False)
        & _bool_col(frame, "target_valid", False)
        & ~_bool_col(frame, "is_synthetic", False)
        & ~_bool_col(frame, "roll_window_flag", False)
        & ~_bool_col(frame, "boundary_session_flag", False)
        & (_numeric(frame, "open") > 0)
        & (_numeric(frame, "high") > 0)
        & (_numeric(frame, "low") > 0)
        & (_numeric(frame, "close") > 0)
    )


def _path_valid_mask(frame: pd.DataFrame, *, exit_offset_bars: int = EXIT_OFFSET_BARS) -> pd.Series:
    valid = _row_valid_mask(frame)
    session = frame["session_segment_id"].astype("string")
    same_session = pd.Series(True, index=frame.index, dtype=bool)
    full_path_valid = pd.Series(True, index=frame.index, dtype=bool)
    for offset in range(0, exit_offset_bars + 1):
        same_session &= session.shift(-offset).eq(session).fillna(False)
        full_path_valid &= valid.shift(-offset).fillna(False)
    return same_session & full_path_valid


def _prior_horizon_vol_ticks(frame: pd.DataFrame, tick_size: float, *, horizon_bars: int = HORIZON_BARS) -> pd.Series:
    session = frame["session_segment_id"].astype("string")
    close = _numeric(frame, "close")
    one_min_ticks = close.groupby(session, sort=False).diff() / tick_size
    prior_sigma = one_min_ticks.groupby(session, sort=False).transform(
        lambda values: values.rolling(VOL_LOOKBACK_BARS, min_periods=VOL_MIN_PERIODS).std().shift(1)
    )
    return prior_sigma * math.sqrt(horizon_bars)


def _threshold_ticks(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    *,
    horizon_bars: int = HORIZON_BARS,
) -> pd.Series:
    tick_size = float(cost_config["tick_size"])
    floor_ticks = float(cost_config["cost_ticks"]) + float(cost_config["min_profit_ticks"])
    vol_ticks = _prior_horizon_vol_ticks(frame, tick_size, horizon_bars=horizon_bars) * VOL_MULTIPLIER
    return pd.Series(np.maximum(vol_ticks, floor_ticks), index=frame.index, dtype="float64")


def apply_vol_scaled_terminal_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    exit_price = _numeric(out, "open").shift(-EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    threshold_ticks = _threshold_ticks(out, cost_config)
    valid = (
        _path_valid_mask(out)
        & entry_price.notna()
        & exit_price.notna()
        & threshold_ticks.notna()
        & np.isfinite(threshold_ticks)
    )

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])
    cost_ticks = float(cost_config["cost_ticks"])

    gross_ticks = (exit_price - entry_price) / tick_size
    gross_dollars = gross_ticks * tick_value
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & (gross_ticks > threshold_ticks), 1)
    direction = direction.mask(valid & (gross_ticks < -threshold_ticks), -1)
    nonflat = direction.ne(0) & valid
    net_ticks = np.sign(gross_ticks) * (gross_ticks.abs() - cost_ticks).clip(lower=0.0)
    net_dollars = net_ticks * tick_value

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    return out


def apply_triple_barrier_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    threshold_ticks = _threshold_ticks(out, cost_config)
    valid = _path_valid_mask(out) & entry_price.notna() & threshold_ticks.notna() & np.isfinite(threshold_ticks)

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])
    cost_ticks = float(cost_config["cost_ticks"])
    upper = entry_price + threshold_ticks * tick_size
    lower = entry_price - threshold_ticks * tick_size

    direction = pd.Series(0, index=out.index, dtype="int64")
    resolved = pd.Series(False, index=out.index, dtype=bool)
    for offset in range(ENTRY_OFFSET_BARS, EXIT_OFFSET_BARS + 1):
        active = valid & ~resolved
        up_hit = _numeric(out, "high").shift(-offset) >= upper
        down_hit = _numeric(out, "low").shift(-offset) <= lower
        long_hit = active & up_hit & ~down_hit
        short_hit = active & down_hit & ~up_hit
        ambiguous_hit = active & up_hit & down_hit
        direction = direction.mask(long_hit, 1)
        direction = direction.mask(short_hit, -1)
        resolved |= long_hit | short_hit | ambiguous_hit

    nonflat = direction.ne(0) & valid
    gross_ticks = direction.astype(float) * threshold_ticks.where(valid, np.nan)
    gross_dollars = gross_ticks * tick_value
    net_ticks = direction.astype(float) * (threshold_ticks - cost_ticks).clip(lower=0.0)
    net_dollars = net_ticks * tick_value

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    return out


def _prior_session_extremes(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["_target_ts"] = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    out["_target_high"] = _numeric(out, "high")
    out["_target_low"] = _numeric(out, "low")
    summary = (
        out.groupby(["market", "session_segment_id"], dropna=False, sort=False)
        .agg(
            session_start=("_target_ts", "min"),
            session_high=("_target_high", "max"),
            session_low=("_target_low", "min"),
        )
        .reset_index()
        .sort_values(["market", "session_start"], kind="mergesort")
    )
    summary["prior_session_high"] = summary.groupby("market", sort=False)["session_high"].shift(1)
    summary["prior_session_low"] = summary.groupby("market", sort=False)["session_low"].shift(1)
    return summary[["market", "session_segment_id", "prior_session_high", "prior_session_low"]]


def _causal_session_vwap(frame: pd.DataFrame) -> pd.Series:
    session = frame["session_segment_id"].astype("string")
    volume = _numeric(frame, "volume").clip(lower=0.0)
    typical_price = (_numeric(frame, "high") + _numeric(frame, "low") + _numeric(frame, "close")) / 3.0
    price_volume = typical_price * volume
    cumulative_volume = volume.groupby(session, sort=False).cumsum()
    cumulative_price_volume = price_volume.groupby(session, sort=False).cumsum()
    return cumulative_price_volume / cumulative_volume.where(cumulative_volume > 0.0)


def apply_vwap_reversion_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    exit_price = _numeric(out, "open").shift(-EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    session_vwap = _causal_session_vwap(out)
    threshold_ticks = _threshold_ticks(out, cost_config)

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])
    cost_ticks = float(cost_config["cost_ticks"])

    close = _numeric(out, "close")
    distance_ticks = (close - session_vwap) / tick_size
    above_vwap_stretch = distance_ticks > threshold_ticks
    below_vwap_stretch = distance_ticks < -threshold_ticks
    valid = (
        _path_valid_mask(out)
        & (above_vwap_stretch | below_vwap_stretch)
        & entry_price.notna()
        & exit_price.notna()
        & session_vwap.notna()
        & threshold_ticks.notna()
        & np.isfinite(threshold_ticks)
    )

    gross_ticks = (exit_price - entry_price) / tick_size
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & below_vwap_stretch & (gross_ticks > threshold_ticks), 1)
    direction = direction.mask(valid & above_vwap_stretch & (gross_ticks < -threshold_ticks), -1)
    nonflat = direction.ne(0) & valid
    gross_dollars = gross_ticks * tick_value
    net_ticks = np.sign(gross_ticks) * (gross_ticks.abs() - cost_ticks).clip(lower=0.0)
    net_dollars = net_ticks * tick_value

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    return out


def _vwap_reclaim_columns(slug: str) -> dict[str, str]:
    return {
        "session_vwap": f"target_session_vwap_{slug}",
        "event_direction": f"target_event_direction_{slug}",
        "vwap_distance_ticks": f"target_vwap_distance_ticks_{slug}",
        "prior_excursion_side": f"target_prior_excursion_side_{slug}",
        "timeout_exit_ticks": f"target_timeout_exit_ticks_{slug}",
    }


def _prior_session_seen(mask: pd.Series, session: pd.Series) -> pd.Series:
    return mask.groupby(session, sort=False).transform(
        lambda values: values.fillna(False).astype(bool).shift(1, fill_value=False).cummax()
    )


def apply_vwap_reclaim_continuation_15m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    session = out["session_segment_id"].astype("string")
    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    exit_price = _numeric(out, "open").shift(-VWAP_RECLAIM_EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-VWAP_RECLAIM_EXIT_OFFSET_BARS)
    session_vwap = _causal_session_vwap(out)
    threshold_ticks = _threshold_ticks(
        out,
        cost_config,
        horizon_bars=VWAP_RECLAIM_HORIZON_BARS,
    )

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])

    close = _numeric(out, "close")
    distance_ticks = (close - session_vwap) / tick_size
    prior_distance_ticks = distance_ticks.groupby(session, sort=False).shift(1)
    had_prior_below_excursion = _prior_session_seen(distance_ticks <= -threshold_ticks, session)
    had_prior_above_excursion = _prior_session_seen(distance_ticks >= threshold_ticks, session)

    long_reclaim = had_prior_below_excursion & prior_distance_ticks.lt(0.0) & distance_ticks.ge(0.0)
    short_reclaim = had_prior_above_excursion & prior_distance_ticks.gt(0.0) & distance_ticks.le(0.0)
    event_direction = pd.Series(0, index=out.index, dtype="int64")
    event_direction = event_direction.mask(long_reclaim, 1)
    event_direction = event_direction.mask(short_reclaim, -1)
    prior_excursion_side = pd.Series(0, index=out.index, dtype="int64")
    prior_excursion_side = prior_excursion_side.mask(long_reclaim, -1)
    prior_excursion_side = prior_excursion_side.mask(short_reclaim, 1)

    signed_exit_ticks = event_direction.astype(float) * ((exit_price - entry_price) / tick_size)
    valid = (
        _path_valid_mask(out, exit_offset_bars=VWAP_RECLAIM_EXIT_OFFSET_BARS)
        & event_direction.ne(0)
        & entry_price.notna()
        & exit_price.notna()
        & session_vwap.notna()
        & threshold_ticks.notna()
        & np.isfinite(threshold_ticks)
        & np.isfinite(signed_exit_ticks)
    )
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & (signed_exit_ticks > threshold_ticks), event_direction)
    nonflat = direction.ne(0) & valid
    gross_dollars = signed_exit_ticks * tick_value
    net_dollars = gross_dollars - cost_dollars
    cols = _vwap_reclaim_columns(spec.slug)

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    out[cols["session_vwap"]] = session_vwap
    out[cols["event_direction"]] = event_direction.where(session_vwap.notna(), 0)
    out[cols["vwap_distance_ticks"]] = distance_ticks.where(session_vwap.notna())
    out[cols["prior_excursion_side"]] = prior_excursion_side.where(event_direction.ne(0), 0)
    out[cols["timeout_exit_ticks"]] = signed_exit_ticks.where(valid)
    return out


def _opening_drive_failed_followthrough_columns(slug: str) -> dict[str, str]:
    return {
        "opening_drive_direction": f"target_opening_drive_direction_{slug}",
        "opening_drive_move_ticks": f"target_opening_drive_move_ticks_{slug}",
        "event_direction": f"target_event_direction_{slug}",
        "failed_followthrough_ticks": f"target_failed_followthrough_ticks_{slug}",
        "timeout_exit_ticks": f"target_timeout_exit_ticks_{slug}",
    }


def apply_opening_drive_failed_followthrough_15m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    keys = [out["market"], out["year"], out["session_segment_id"]]
    session_bar = out.groupby(keys, dropna=False, sort=False).cumcount()
    row_valid = _row_valid_mask(out)

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])

    open_ = _numeric(out, "open")
    high = _numeric(out, "high")
    low = _numeric(out, "low")
    close = _numeric(out, "close")

    opening_drive_bar = session_bar < OPENING_DRIVE_BARS
    opening_drive_valid_bar = opening_drive_bar & row_valid
    opening_valid_count = opening_drive_valid_bar.astype("int64").groupby(
        keys,
        dropna=False,
        sort=False,
    ).transform("sum")
    opening_drive_open = open_.where(session_bar.eq(0)).groupby(keys, dropna=False, sort=False).transform("first")
    opening_drive_close = close.where(session_bar.eq(OPENING_DRIVE_BARS - 1)).groupby(
        keys,
        dropna=False,
        sort=False,
    ).transform("first")
    opening_drive_ready = (
        (session_bar >= OPENING_DRIVE_BARS)
        & (opening_valid_count >= OPENING_DRIVE_BARS)
        & opening_drive_open.notna()
        & opening_drive_close.notna()
    )

    entry_price = open_.shift(-ENTRY_OFFSET_BARS)
    exit_price = open_.shift(-OPENING_DRIVE_FAILED_FOLLOWTHROUGH_EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-OPENING_DRIVE_FAILED_FOLLOWTHROUGH_EXIT_OFFSET_BARS)
    threshold_ticks = _threshold_ticks(
        out,
        cost_config,
        horizon_bars=OPENING_DRIVE_FAILED_FOLLOWTHROUGH_HORIZON_BARS,
    )

    opening_drive_move_ticks = (opening_drive_close - opening_drive_open) / tick_size
    drive_direction = pd.Series(0, index=out.index, dtype="int64")
    drive_direction = drive_direction.mask(
        opening_drive_ready & opening_drive_move_ticks.ge(threshold_ticks),
        1,
    )
    drive_direction = drive_direction.mask(
        opening_drive_ready & opening_drive_move_ticks.le(-threshold_ticks),
        -1,
    )

    post_drive_bar = session_bar >= OPENING_DRIVE_BARS
    prior_post_drive_high = high.where(post_drive_bar).groupby(
        keys,
        dropna=False,
        sort=False,
    ).transform(lambda values: values.cummax().shift(1))
    prior_post_drive_low = low.where(post_drive_bar).groupby(
        keys,
        dropna=False,
        sort=False,
    ).transform(lambda values: values.cummin().shift(1))
    long_failed_ticks = (prior_post_drive_high - opening_drive_close) / tick_size
    short_failed_ticks = (opening_drive_close - prior_post_drive_low) / tick_size
    failed_followthrough_ticks = pd.Series(np.nan, index=out.index, dtype="float64")
    failed_followthrough_ticks = failed_followthrough_ticks.mask(drive_direction.eq(1), long_failed_ticks)
    failed_followthrough_ticks = failed_followthrough_ticks.mask(drive_direction.eq(-1), short_failed_ticks)

    long_drive_failed = (
        drive_direction.eq(1)
        & failed_followthrough_ticks.ge(threshold_ticks)
        & close.le(opening_drive_close)
    )
    short_drive_failed = (
        drive_direction.eq(-1)
        & failed_followthrough_ticks.ge(threshold_ticks)
        & close.ge(opening_drive_close)
    )
    event_direction = pd.Series(0, index=out.index, dtype="int64")
    event_direction = event_direction.mask(long_drive_failed, -1)
    event_direction = event_direction.mask(short_drive_failed, 1)

    signed_exit_ticks = event_direction.astype(float) * ((exit_price - entry_price) / tick_size)
    valid = (
        _path_valid_mask(out, exit_offset_bars=OPENING_DRIVE_FAILED_FOLLOWTHROUGH_EXIT_OFFSET_BARS)
        & event_direction.ne(0)
        & entry_price.notna()
        & exit_price.notna()
        & threshold_ticks.notna()
        & np.isfinite(threshold_ticks)
        & np.isfinite(signed_exit_ticks)
    )
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & (signed_exit_ticks > threshold_ticks), event_direction)
    nonflat = direction.ne(0) & valid
    gross_dollars = signed_exit_ticks * tick_value
    net_dollars = gross_dollars - cost_dollars
    cols = _opening_drive_failed_followthrough_columns(spec.slug)

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    out[cols["opening_drive_direction"]] = drive_direction.where(opening_drive_ready, 0)
    out[cols["opening_drive_move_ticks"]] = opening_drive_move_ticks.where(opening_drive_ready)
    out[cols["event_direction"]] = event_direction.where(opening_drive_ready, 0)
    out[cols["failed_followthrough_ticks"]] = failed_followthrough_ticks.where(event_direction.ne(0))
    out[cols["timeout_exit_ticks"]] = signed_exit_ticks.where(valid)
    return out


def _session_compression_breakout_columns(slug: str) -> dict[str, str]:
    return {
        "box_high": f"target_box_high_{slug}",
        "box_low": f"target_box_low_{slug}",
        "box_range_ticks": f"target_box_range_ticks_{slug}",
        "compression_threshold_ticks": f"target_compression_threshold_ticks_{slug}",
        "event_direction": f"target_event_direction_{slug}",
        "breakout_ticks": f"target_breakout_ticks_{slug}",
        "timeout_exit_ticks": f"target_timeout_exit_ticks_{slug}",
    }


def _rolling_prior_quantile(values: pd.Series, *, window: int, min_periods: int, quantile: float) -> pd.Series:
    return values.shift(1).rolling(window, min_periods=min_periods).quantile(quantile)


def apply_session_compression_breakout_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    keys = [out["market"], out["year"], out["session_segment_id"]]
    row_valid = _row_valid_mask(out)

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])

    open_ = _numeric(out, "open")
    high = _numeric(out, "high")
    low = _numeric(out, "low")
    close = _numeric(out, "close")
    valid_bar_count = row_valid.astype("int64").groupby(keys, dropna=False, sort=False).transform(
        lambda values: values.rolling(
            SESSION_COMPRESSION_BOX_BARS,
            min_periods=SESSION_COMPRESSION_BOX_BARS,
        )
        .sum()
        .shift(1)
    )
    box_high = high.where(row_valid).groupby(keys, dropna=False, sort=False).transform(
        lambda values: values.rolling(
            SESSION_COMPRESSION_BOX_BARS,
            min_periods=SESSION_COMPRESSION_BOX_BARS,
        )
        .max()
        .shift(1)
    )
    box_low = low.where(row_valid).groupby(keys, dropna=False, sort=False).transform(
        lambda values: values.rolling(
            SESSION_COMPRESSION_BOX_BARS,
            min_periods=SESSION_COMPRESSION_BOX_BARS,
        )
        .min()
        .shift(1)
    )
    box_range_ticks = (box_high - box_low) / tick_size
    compression_threshold_ticks = box_range_ticks.groupby(keys, dropna=False, sort=False).transform(
        lambda values: _rolling_prior_quantile(
            values,
            window=SESSION_COMPRESSION_PRIOR_WINDOWS,
            min_periods=SESSION_COMPRESSION_MIN_PRIOR_WINDOWS,
            quantile=0.25,
        )
    )
    compression_ready = (
        valid_bar_count.ge(SESSION_COMPRESSION_BOX_BARS)
        & box_range_ticks.notna()
        & compression_threshold_ticks.notna()
        & box_range_ticks.le(compression_threshold_ticks)
    )
    breakout_buffer = SESSION_COMPRESSION_BREAKOUT_BUFFER_TICKS * tick_size
    long_breakout = compression_ready & close.ge(box_high + breakout_buffer)
    short_breakout = compression_ready & close.le(box_low - breakout_buffer)
    event_direction = pd.Series(0, index=out.index, dtype="int64")
    event_direction = event_direction.mask(long_breakout, 1)
    event_direction = event_direction.mask(short_breakout, -1)
    breakout_ticks = pd.Series(np.nan, index=out.index, dtype="float64")
    breakout_ticks = breakout_ticks.mask(long_breakout, (close - box_high) / tick_size)
    breakout_ticks = breakout_ticks.mask(short_breakout, (box_low - close) / tick_size)

    entry_price = open_.shift(-ENTRY_OFFSET_BARS)
    exit_price = open_.shift(-EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    threshold_ticks = _threshold_ticks(out, cost_config, horizon_bars=HORIZON_BARS)
    signed_exit_ticks = event_direction.astype(float) * ((exit_price - entry_price) / tick_size)
    valid = (
        _path_valid_mask(out)
        & event_direction.ne(0)
        & entry_price.notna()
        & exit_price.notna()
        & threshold_ticks.notna()
        & np.isfinite(threshold_ticks)
        & np.isfinite(signed_exit_ticks)
    )
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & (signed_exit_ticks > threshold_ticks), event_direction)
    nonflat = direction.ne(0) & valid
    gross_dollars = signed_exit_ticks * tick_value
    net_dollars = gross_dollars - cost_dollars
    cols = _session_compression_breakout_columns(spec.slug)

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    out[cols["box_high"]] = box_high.where(compression_ready)
    out[cols["box_low"]] = box_low.where(compression_ready)
    out[cols["box_range_ticks"]] = box_range_ticks.where(compression_ready)
    out[cols["compression_threshold_ticks"]] = compression_threshold_ticks.where(compression_ready)
    out[cols["event_direction"]] = event_direction.where(compression_ready, 0)
    out[cols["breakout_ticks"]] = breakout_ticks.where(event_direction.ne(0))
    out[cols["timeout_exit_ticks"]] = signed_exit_ticks.where(valid)
    return out


def _volume_pace_breakout_columns(slug: str) -> dict[str, str]:
    return {
        "range_high": f"target_range_high_{slug}",
        "range_low": f"target_range_low_{slug}",
        "range_ticks": f"target_range_ticks_{slug}",
        "volume_pace": f"target_volume_pace_{slug}",
        "volume_pace_baseline": f"target_volume_pace_baseline_{slug}",
        "volume_pace_ratio": f"target_volume_pace_ratio_{slug}",
        "event_direction": f"target_event_direction_{slug}",
        "breakout_ticks": f"target_breakout_ticks_{slug}",
        "timeout_exit_ticks": f"target_timeout_exit_ticks_{slug}",
    }


def _prior_session_volume_pace_baseline(
    frame: pd.DataFrame,
    volume_pace: pd.Series,
    session_bar_index: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    ts = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    keys = [frame["market"], frame["year"], frame["session_segment_id"]]
    session_start = ts.groupby(keys, dropna=False, sort=False).transform("min")
    baseline_frame = pd.DataFrame(
        {
            "market": frame["market"],
            "year": frame["year"],
            "session_bar_index": session_bar_index,
            "session_start": session_start,
            "volume_pace": volume_pace,
        },
        index=frame.index,
    ).sort_values(
        ["market", "year", "session_bar_index", "session_start"],
        kind="mergesort",
    )
    grouped = baseline_frame.groupby(
        ["market", "year", "session_bar_index"],
        dropna=False,
        sort=False,
    )
    baseline_frame["prior_session_count"] = grouped.cumcount()
    baseline_frame["volume_pace_baseline"] = grouped["volume_pace"].transform(
        lambda values: values.shift(1)
        .rolling(
            VOLUME_PACE_MIN_BASELINE_SESSIONS,
            min_periods=VOLUME_PACE_MIN_BASELINE_SESSIONS,
        )
        .median()
    )
    baseline_frame = baseline_frame.sort_index()
    return baseline_frame["volume_pace_baseline"], baseline_frame["prior_session_count"]


def apply_volume_pace_breakout_continuation_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    keys = [out["market"], out["year"], out["session_segment_id"]]
    row_valid = _row_valid_mask(out)

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])

    open_ = _numeric(out, "open")
    high = _numeric(out, "high")
    low = _numeric(out, "low")
    close = _numeric(out, "close")
    volume = _numeric(out, "volume").clip(lower=0)
    valid_bar_count = row_valid.astype("int64").groupby(keys, dropna=False, sort=False).transform(
        lambda values: values.rolling(
            VOLUME_PACE_RANGE_BARS,
            min_periods=VOLUME_PACE_RANGE_BARS,
        )
        .sum()
        .shift(1)
    )
    range_high = high.where(row_valid).groupby(keys, dropna=False, sort=False).transform(
        lambda values: values.rolling(
            VOLUME_PACE_RANGE_BARS,
            min_periods=VOLUME_PACE_RANGE_BARS,
        )
        .max()
        .shift(1)
    )
    range_low = low.where(row_valid).groupby(keys, dropna=False, sort=False).transform(
        lambda values: values.rolling(
            VOLUME_PACE_RANGE_BARS,
            min_periods=VOLUME_PACE_RANGE_BARS,
        )
        .min()
        .shift(1)
    )
    range_ticks = (range_high - range_low) / tick_size
    valid_bar_count_so_far = row_valid.astype("int64").groupby(keys, dropna=False, sort=False).cumsum()
    cumulative_volume = volume.where(row_valid, 0.0).groupby(keys, dropna=False, sort=False).cumsum()
    volume_pace = cumulative_volume / valid_bar_count_so_far.where(valid_bar_count_so_far > 0)
    session_bar_index = valid_bar_count_so_far.where(row_valid)
    volume_pace_baseline, prior_session_count = _prior_session_volume_pace_baseline(
        out,
        volume_pace.where(row_valid),
        session_bar_index,
    )
    volume_pace_ratio = volume_pace / volume_pace_baseline.where(volume_pace_baseline > 0)

    range_ready = valid_bar_count.ge(VOLUME_PACE_RANGE_BARS) & range_high.notna() & range_low.notna()
    volume_ready = (
        volume_pace_baseline.gt(0)
        & prior_session_count.ge(VOLUME_PACE_MIN_BASELINE_SESSIONS)
        & volume_pace_ratio.ge(VOLUME_PACE_RATIO_MIN)
    )
    breakout_buffer = VOLUME_PACE_BREAKOUT_BUFFER_TICKS * tick_size
    long_breakout = range_ready & volume_ready & close.ge(range_high + breakout_buffer)
    short_breakout = range_ready & volume_ready & close.le(range_low - breakout_buffer)
    event_direction = pd.Series(0, index=out.index, dtype="int64")
    event_direction = event_direction.mask(long_breakout, 1)
    event_direction = event_direction.mask(short_breakout, -1)
    breakout_ticks = pd.Series(np.nan, index=out.index, dtype="float64")
    breakout_ticks = breakout_ticks.mask(long_breakout, (close - range_high) / tick_size)
    breakout_ticks = breakout_ticks.mask(short_breakout, (range_low - close) / tick_size)

    entry_price = open_.shift(-ENTRY_OFFSET_BARS)
    exit_price = open_.shift(-EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    threshold_ticks = _threshold_ticks(out, cost_config, horizon_bars=HORIZON_BARS)
    signed_exit_ticks = event_direction.astype(float) * ((exit_price - entry_price) / tick_size)
    valid = (
        _path_valid_mask(out)
        & event_direction.ne(0)
        & entry_price.notna()
        & exit_price.notna()
        & threshold_ticks.notna()
        & np.isfinite(threshold_ticks)
        & np.isfinite(signed_exit_ticks)
    )
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & (signed_exit_ticks > threshold_ticks), event_direction)
    nonflat = direction.ne(0) & valid
    gross_dollars = signed_exit_ticks * tick_value
    net_dollars = gross_dollars - cost_dollars
    cols = _volume_pace_breakout_columns(spec.slug)

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    out[cols["range_high"]] = range_high.where(range_ready)
    out[cols["range_low"]] = range_low.where(range_ready)
    out[cols["range_ticks"]] = range_ticks.where(range_ready)
    out[cols["volume_pace"]] = volume_pace.where(row_valid)
    out[cols["volume_pace_baseline"]] = volume_pace_baseline.where(volume_pace_baseline.notna())
    out[cols["volume_pace_ratio"]] = volume_pace_ratio.where(volume_pace_baseline.gt(0))
    out[cols["event_direction"]] = event_direction.where(range_ready & volume_pace_baseline.gt(0), 0)
    out[cols["breakout_ticks"]] = breakout_ticks.where(event_direction.ne(0))
    out[cols["timeout_exit_ticks"]] = signed_exit_ticks.where(valid)
    return out


def apply_first_hour_midday_pullback_continuation_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    local_ts = ts.dt.tz_convert("America/Chicago")
    minute_of_day = local_ts.dt.hour * 60 + local_ts.dt.minute
    keys = [out["market"], out["year"], out["session_segment_id"]]
    row_valid = _row_valid_mask(out)

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])

    open_ = _numeric(out, "open")
    high = _numeric(out, "high")
    low = _numeric(out, "low")
    close = _numeric(out, "close")
    session = out["session_segment_id"].astype("string")

    valid_bar_number = row_valid.astype("int64").groupby(keys, dropna=False, sort=False).cumsum()
    first_hour_window = row_valid & valid_bar_number.between(1, 60)
    first_hour_count = first_hour_window.astype("int64").groupby(keys, dropna=False, sort=False).transform("sum")
    first_hour_open = open_.where(row_valid & valid_bar_number.eq(1)).groupby(
        keys,
        dropna=False,
        sort=False,
    ).transform("first")
    first_hour_high = high.where(first_hour_window).groupby(keys, dropna=False, sort=False).transform("max")
    first_hour_low = low.where(first_hour_window).groupby(keys, dropna=False, sort=False).transform("min")
    first_hour_ready = (
        first_hour_count.eq(60)
        & valid_bar_number.gt(60)
        & first_hour_open.notna()
        & first_hour_high.notna()
        & first_hour_low.notna()
    )

    up_move_ticks = (first_hour_high - first_hour_open) / tick_size
    down_move_ticks = (first_hour_open - first_hour_low) / tick_size
    raw_direction = pd.Series(0, index=out.index, dtype="int64")
    raw_direction = raw_direction.mask(up_move_ticks.gt(down_move_ticks), 1)
    raw_direction = raw_direction.mask(down_move_ticks.gt(up_move_ticks), -1)
    first_hour_move_ticks = pd.Series(np.nan, index=out.index, dtype="float64")
    first_hour_move_ticks = first_hour_move_ticks.mask(raw_direction.eq(1), up_move_ticks)
    first_hour_move_ticks = first_hour_move_ticks.mask(raw_direction.eq(-1), down_move_ticks)

    cost_floor_ticks = float(cost_config["cost_ticks"]) + float(cost_config["min_profit_ticks"])
    first_hour_floor_ticks = max(12.0, cost_floor_ticks)
    first_hour_vol_ticks = _prior_horizon_vol_ticks(out, tick_size, horizon_bars=60) * VOL_MULTIPLIER
    first_hour_threshold_ticks = pd.Series(
        np.maximum(first_hour_vol_ticks, first_hour_floor_ticks),
        index=out.index,
        dtype="float64",
    )
    strong_direction = (
        first_hour_ready
        & raw_direction.ne(0)
        & first_hour_move_ticks.notna()
        & first_hour_threshold_ticks.notna()
        & first_hour_move_ticks.ge(first_hour_threshold_ticks)
    )
    first_hour_direction = raw_direction.where(strong_direction, 0)
    first_hour_extreme = pd.Series(np.nan, index=out.index, dtype="float64")
    first_hour_extreme = first_hour_extreme.mask(first_hour_direction.eq(1), first_hour_high)
    first_hour_extreme = first_hour_extreme.mask(first_hour_direction.eq(-1), first_hour_low)

    pullback_depth = pd.Series(np.nan, index=out.index, dtype="float64")
    long_pullback_base = strong_direction & first_hour_direction.eq(1) & up_move_ticks.gt(0.0)
    short_pullback_base = strong_direction & first_hour_direction.eq(-1) & down_move_ticks.gt(0.0)
    pullback_depth = pullback_depth.mask(
        long_pullback_base,
        (first_hour_extreme - close) / (first_hour_extreme - first_hour_open),
    )
    pullback_depth = pullback_depth.mask(
        short_pullback_base,
        (close - first_hour_extreme) / (first_hour_open - first_hour_extreme),
    )
    pullback_qualified = row_valid & pullback_depth.between(0.35, 0.60, inclusive="both")
    previous_pullback_qualified = (
        pullback_qualified.shift(1).fillna(False).astype(bool)
        & session.shift(1).eq(session).fillna(False)
    )
    previous_pullback_depth = pullback_depth.shift(1)

    causal_session_high = high.where(row_valid).groupby(keys, dropna=False, sort=False).cummax()
    causal_session_low = low.where(row_valid).groupby(keys, dropna=False, sort=False).cummin()
    session_midpoint = (causal_session_high + causal_session_low) / 2.0
    midpoint_guard = (
        (first_hour_direction.eq(1) & close.ge(session_midpoint))
        | (first_hour_direction.eq(-1) & close.le(session_midpoint))
    )
    resumption_ticks = first_hour_direction.astype(float) * ((close - close.shift(1)) / tick_size)
    event_window = minute_of_day.ge(11 * 60) & minute_of_day.le(13 * 60 + 30)
    scope = out["market"].astype("string").eq(MARKET) & out["year"].isin([2023, 2024])
    event_ready = (
        scope
        & row_valid
        & event_window
        & strong_direction
        & previous_pullback_qualified
        & midpoint_guard
        & resumption_ticks.ge(1.0)
    )
    event_direction = pd.Series(0, index=out.index, dtype="int64")
    event_direction = event_direction.mask(event_ready, first_hour_direction)

    entry_price = open_.shift(-ENTRY_OFFSET_BARS)
    exit_price = open_.shift(-EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    threshold_ticks = _threshold_ticks(out, cost_config, horizon_bars=HORIZON_BARS)
    signed_exit_ticks = event_direction.astype(float) * ((exit_price - entry_price) / tick_size)
    valid = (
        _path_valid_mask(out)
        & event_direction.ne(0)
        & entry_price.notna()
        & exit_price.notna()
        & threshold_ticks.notna()
        & np.isfinite(threshold_ticks)
        & np.isfinite(signed_exit_ticks)
    )
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & (signed_exit_ticks > threshold_ticks), event_direction)
    nonflat = direction.ne(0) & valid
    gross_dollars = signed_exit_ticks * tick_value
    net_dollars = gross_dollars - cost_dollars
    cols = {
        "first_hour_open": f"target_first_hour_open_{spec.slug}",
        "first_hour_extreme": f"target_first_hour_extreme_{spec.slug}",
        "first_hour_move_ticks": f"target_first_hour_move_ticks_{spec.slug}",
        "first_hour_direction": f"target_first_hour_direction_{spec.slug}",
        "first_hour_threshold_ticks": f"target_first_hour_threshold_ticks_{spec.slug}",
        "pullback_depth": f"target_pullback_depth_{spec.slug}",
        "session_midpoint": f"target_session_midpoint_{spec.slug}",
        "event_direction": f"target_event_direction_{spec.slug}",
        "resumption_ticks": f"target_resumption_ticks_{spec.slug}",
        "timeout_exit_ticks": f"target_timeout_exit_ticks_{spec.slug}",
    }

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    out[cols["first_hour_open"]] = first_hour_open.where(first_hour_ready)
    out[cols["first_hour_extreme"]] = first_hour_extreme.where(strong_direction)
    out[cols["first_hour_move_ticks"]] = first_hour_move_ticks.where(first_hour_ready)
    out[cols["first_hour_direction"]] = first_hour_direction.where(first_hour_ready, 0)
    out[cols["first_hour_threshold_ticks"]] = first_hour_threshold_ticks.where(first_hour_ready)
    out[cols["pullback_depth"]] = previous_pullback_depth.where(event_direction.ne(0))
    out[cols["session_midpoint"]] = session_midpoint.where(row_valid & event_window)
    out[cols["event_direction"]] = event_direction
    out[cols["resumption_ticks"]] = resumption_ticks.where(previous_pullback_qualified & event_window)
    out[cols["timeout_exit_ticks"]] = signed_exit_ticks.where(valid)
    return out


def _late_session_range_resolve_columns(slug: str) -> dict[str, str]:
    return {
        "range_high": f"target_range_high_{slug}",
        "range_low": f"target_range_low_{slug}",
        "range_ticks": f"target_range_ticks_{slug}",
        "event_direction": f"target_event_direction_{slug}",
        "breakout_ticks": f"target_breakout_ticks_{slug}",
        "minutes_to_close": f"target_minutes_to_close_{slug}",
        "close_exit_ticks": f"target_close_exit_ticks_{slug}",
    }


def _minute_of_day_chicago(ts: pd.Series) -> pd.Series:
    local_ts = ts.dt.tz_convert("America/Chicago")
    return local_ts.dt.hour * 60 + local_ts.dt.minute


def _remaining_minutes_threshold_ticks(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    minutes_to_close: pd.Series,
) -> pd.Series:
    tick_size = float(cost_config["tick_size"])
    floor_ticks = float(cost_config["cost_ticks"]) + float(cost_config["min_profit_ticks"])
    keys = [frame["market"], frame["year"], frame["session_segment_id"]]
    close = _numeric(frame, "close")
    one_min_ticks = close.groupby(keys, dropna=False, sort=False).diff() / tick_size
    prior_sigma = one_min_ticks.groupby(keys, dropna=False, sort=False).transform(
        lambda values: values.rolling(VOL_LOOKBACK_BARS, min_periods=VOL_MIN_PERIODS).std().shift(1)
    )
    horizon = minutes_to_close.clip(lower=1.0)
    vol_ticks = prior_sigma * np.sqrt(horizon) * VOL_MULTIPLIER
    return pd.Series(np.maximum(vol_ticks, floor_ticks), index=frame.index, dtype="float64")


def apply_late_session_range_resolve_session_close_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    minute_of_day = _minute_of_day_chicago(ts)
    keys = [out["market"], out["year"], out["session_segment_id"]]
    row_valid = _row_valid_mask(out)

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])

    open_ = _numeric(out, "open")
    high = _numeric(out, "high")
    low = _numeric(out, "low")
    close = _numeric(out, "close")
    range_window = (
        row_valid
        & minute_of_day.ge(LATE_SESSION_RANGE_START_MINUTE)
        & minute_of_day.lt(LATE_SESSION_RANGE_END_MINUTE)
    )
    range_count = range_window.astype("int64").groupby(keys, dropna=False, sort=False).transform("sum")
    range_high = high.where(range_window).groupby(keys, dropna=False, sort=False).transform("max")
    range_low = low.where(range_window).groupby(keys, dropna=False, sort=False).transform("min")
    range_ticks = (range_high - range_low) / tick_size
    range_ready = (
        range_count.eq(LATE_SESSION_RANGE_REQUIRED_BARS)
        & range_high.notna()
        & range_low.notna()
        & range_ticks.notna()
        & range_ticks.gt(0.0)
    )

    candidate_window = (
        row_valid
        & minute_of_day.ge(LATE_SESSION_RANGE_END_MINUTE)
        & minute_of_day.lt(LATE_SESSION_CLOSE_MINUTE)
    )
    breakout_buffer = LATE_SESSION_BREAKOUT_BUFFER_TICKS * tick_size
    long_breakout = range_ready & candidate_window & close.ge(range_high + breakout_buffer)
    short_breakout = range_ready & candidate_window & close.le(range_low - breakout_buffer)
    event_direction = pd.Series(0, index=out.index, dtype="int64")
    event_direction = event_direction.mask(long_breakout, 1)
    event_direction = event_direction.mask(short_breakout, -1)
    breakout_ticks = pd.Series(np.nan, index=out.index, dtype="float64")
    breakout_ticks = breakout_ticks.mask(long_breakout, (close - range_high) / tick_size)
    breakout_ticks = breakout_ticks.mask(short_breakout, (range_low - close) / tick_size)

    session = out["session_segment_id"].astype("string")
    entry_price = open_.shift(-ENTRY_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    entry_same_session = session.shift(-ENTRY_OFFSET_BARS).eq(session).fillna(False)
    entry_row_valid = row_valid.shift(-ENTRY_OFFSET_BARS).fillna(False)
    close_exit_window = row_valid & minute_of_day.eq(LATE_SESSION_CLOSE_MINUTE)
    exit_price = open_.where(close_exit_window).groupby(keys, dropna=False, sort=False).transform("last")
    exit_ts = ts.where(close_exit_window).groupby(keys, dropna=False, sort=False).transform("last")
    minutes_to_close = (exit_ts - entry_ts).dt.total_seconds() / 60.0
    threshold_ticks = _remaining_minutes_threshold_ticks(out, cost_config, minutes_to_close)
    signed_exit_ticks = event_direction.astype(float) * ((exit_price - entry_price) / tick_size)
    valid = (
        row_valid
        & range_ready
        & event_direction.ne(0)
        & entry_same_session
        & entry_row_valid
        & entry_price.notna()
        & exit_price.notna()
        & entry_ts.notna()
        & exit_ts.notna()
        & exit_ts.gt(entry_ts)
        & minutes_to_close.gt(0.0)
        & threshold_ticks.notna()
        & np.isfinite(threshold_ticks)
        & np.isfinite(signed_exit_ticks)
    )
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & (signed_exit_ticks > threshold_ticks), event_direction)
    nonflat = direction.ne(0) & valid
    gross_dollars = signed_exit_ticks * tick_value
    net_dollars = gross_dollars - cost_dollars
    cols = _late_session_range_resolve_columns(spec.slug)

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    out[cols["range_high"]] = range_high.where(range_ready)
    out[cols["range_low"]] = range_low.where(range_ready)
    out[cols["range_ticks"]] = range_ticks.where(range_ready)
    out[cols["event_direction"]] = event_direction.where(range_ready, 0)
    out[cols["breakout_ticks"]] = breakout_ticks.where(event_direction.ne(0))
    out[cols["minutes_to_close"]] = minutes_to_close.where(valid)
    out[cols["close_exit_ticks"]] = signed_exit_ticks.where(valid)
    return out


def apply_prior_extreme_failure_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    out = out.merge(
        _prior_session_extremes(out),
        on=["market", "session_segment_id"],
        how="left",
        validate="many_to_one",
    )
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    exit_price = _numeric(out, "open").shift(-EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    threshold_ticks = _threshold_ticks(out, cost_config)

    high = _numeric(out, "high")
    low = _numeric(out, "low")
    close = _numeric(out, "close")
    prior_high = pd.to_numeric(out["prior_session_high"], errors="coerce")
    prior_low = pd.to_numeric(out["prior_session_low"], errors="coerce")
    high_failure_probe = prior_high.notna() & (high >= prior_high) & (close < prior_high)
    low_failure_probe = prior_low.notna() & (low <= prior_low) & (close > prior_low)
    high_only = high_failure_probe & ~low_failure_probe
    low_only = low_failure_probe & ~high_failure_probe
    valid = (
        _path_valid_mask(out)
        & (high_only | low_only)
        & entry_price.notna()
        & exit_price.notna()
        & threshold_ticks.notna()
        & np.isfinite(threshold_ticks)
    )

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])
    cost_ticks = float(cost_config["cost_ticks"])

    gross_ticks = (exit_price - entry_price) / tick_size
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(valid & low_only & (gross_ticks > threshold_ticks), 1)
    direction = direction.mask(valid & high_only & (gross_ticks < -threshold_ticks), -1)
    nonflat = direction.ne(0) & valid
    gross_dollars = gross_ticks * tick_value
    net_ticks = np.sign(gross_ticks) * (gross_ticks.abs() - cost_ticks).clip(lower=0.0)
    net_dollars = net_ticks * tick_value

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = threshold_ticks.where(valid)
    return out


def _forward_path_extreme(frame: pd.DataFrame, column: str, mode: str) -> pd.Series:
    shifted = [_numeric(frame, column).shift(-offset) for offset in range(ENTRY_OFFSET_BARS, EXIT_OFFSET_BARS + 1)]
    path = pd.concat(shifted, axis=1)
    if mode == "max":
        return path.max(axis=1)
    if mode == "min":
        return path.min(axis=1)
    raise ValueError(f"unknown path extreme mode: {mode}")


def _opening_range_columns(slug: str) -> dict[str, str]:
    return {
        "opening_range_high": f"target_opening_range_high_{slug}",
        "opening_range_low": f"target_opening_range_low_{slug}",
        "event_direction": f"target_event_direction_{slug}",
        "acceptance_distance_ticks": f"target_acceptance_distance_ticks_{slug}",
        "favorable_excursion_ticks": f"target_favorable_excursion_ticks_{slug}",
        "adverse_excursion_ticks": f"target_adverse_excursion_ticks_{slug}",
    }


def _opening_range_event_capture_columns(slug: str) -> dict[str, str]:
    columns = _opening_range_columns(slug)
    columns["timeout_exit_ticks"] = f"target_timeout_exit_ticks_{slug}"
    columns["session_event_number"] = f"target_session_event_number_{slug}"
    return columns


def apply_opening_range_acceptance_continuation_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    keys = [out["market"], out["year"], out["session_segment_id"]]
    session_bar = out.groupby(keys, dropna=False, sort=False).cumcount()
    row_valid = _row_valid_mask(out)
    opening_range_bar = session_bar < OPENING_RANGE_BARS
    opening_range_valid_bar = opening_range_bar & row_valid
    opening_valid_count = opening_range_valid_bar.astype("int64").groupby(keys, dropna=False, sort=False).transform("sum")
    opening_high = _numeric(out, "high").where(opening_range_valid_bar).groupby(keys, dropna=False, sort=False).transform("max")
    opening_low = _numeric(out, "low").where(opening_range_valid_bar).groupby(keys, dropna=False, sort=False).transform("min")
    opening_range_ready = (
        (session_bar >= OPENING_RANGE_BARS)
        & (opening_valid_count >= OPENING_RANGE_BARS)
        & opening_high.notna()
        & opening_low.notna()
    )

    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    future_high = _forward_path_extreme(out, "high", "max")
    future_low = _forward_path_extreme(out, "low", "min")

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])
    cost_ticks = float(cost_config["cost_ticks"])
    threshold_ticks = cost_ticks + float(cost_config["min_profit_ticks"])

    close = _numeric(out, "close")
    long_acceptance = opening_range_ready & (close > opening_high)
    short_acceptance = opening_range_ready & (close < opening_low)
    event_direction = pd.Series(0, index=out.index, dtype="int64")
    event_direction = event_direction.mask(long_acceptance, 1)
    event_direction = event_direction.mask(short_acceptance, -1)
    acceptance_distance = pd.Series(0.0, index=out.index, dtype="float64")
    acceptance_distance = acceptance_distance.mask(long_acceptance, (close - opening_high) / tick_size)
    acceptance_distance = acceptance_distance.mask(short_acceptance, (opening_low - close) / tick_size)

    long_favorable_ticks = (future_high - entry_price) / tick_size
    short_favorable_ticks = (entry_price - future_low) / tick_size
    long_adverse_ticks = (entry_price - future_low) / tick_size
    short_adverse_ticks = (future_high - entry_price) / tick_size
    favorable_ticks = pd.Series(np.nan, index=out.index, dtype="float64")
    favorable_ticks = favorable_ticks.mask(event_direction.gt(0), long_favorable_ticks)
    favorable_ticks = favorable_ticks.mask(event_direction.lt(0), short_favorable_ticks)
    adverse_ticks = pd.Series(np.nan, index=out.index, dtype="float64")
    adverse_ticks = adverse_ticks.mask(event_direction.gt(0), long_adverse_ticks)
    adverse_ticks = adverse_ticks.mask(event_direction.lt(0), short_adverse_ticks)

    valid = (
        _path_valid_mask(out)
        & event_direction.ne(0)
        & entry_price.notna()
        & future_high.notna()
        & future_low.notna()
        & favorable_ticks.notna()
        & np.isfinite(favorable_ticks)
    )
    continuation = valid & (favorable_ticks > threshold_ticks)
    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(continuation, event_direction)
    nonflat = direction.ne(0) & valid
    signed_gross_ticks = event_direction.astype(float) * favorable_ticks
    signed_net_ticks = event_direction.astype(float) * (favorable_ticks - cost_ticks).clip(lower=0.0)
    cols = _opening_range_columns(spec.slug)

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = (signed_gross_ticks * tick_value).where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = (signed_net_ticks * tick_value).where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = pd.Series(threshold_ticks, index=out.index).where(valid)
    out[cols["opening_range_high"]] = opening_high.where(opening_range_ready)
    out[cols["opening_range_low"]] = opening_low.where(opening_range_ready)
    out[cols["event_direction"]] = event_direction.where(opening_range_ready, 0)
    out[cols["acceptance_distance_ticks"]] = acceptance_distance.where(opening_range_ready)
    out[cols["favorable_excursion_ticks"]] = favorable_ticks.where(valid)
    out[cols["adverse_excursion_ticks"]] = adverse_ticks.where(valid)
    return out


def apply_opening_range_acceptance_event_capture_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    keys = [out["market"], out["year"], out["session_segment_id"]]
    session_bar = out.groupby(keys, dropna=False, sort=False).cumcount()
    row_valid = _row_valid_mask(out)
    opening_range_bar = session_bar < OPENING_RANGE_BARS
    opening_range_valid_bar = opening_range_bar & row_valid
    opening_valid_count = opening_range_valid_bar.astype("int64").groupby(keys, dropna=False, sort=False).transform("sum")
    opening_high = _numeric(out, "high").where(opening_range_valid_bar).groupby(keys, dropna=False, sort=False).transform("max")
    opening_low = _numeric(out, "low").where(opening_range_valid_bar).groupby(keys, dropna=False, sort=False).transform("min")
    opening_range_ready = (
        (session_bar >= OPENING_RANGE_BARS)
        & (opening_valid_count >= OPENING_RANGE_BARS)
        & opening_high.notna()
        & opening_low.notna()
    )

    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    exit_price = _numeric(out, "open").shift(-EXIT_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    future_high = _forward_path_extreme(out, "high", "max")
    future_low = _forward_path_extreme(out, "low", "min")

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])
    cost_ticks = float(cost_config["cost_ticks"])

    close = _numeric(out, "close")
    long_acceptance = opening_range_ready & (close > opening_high)
    short_acceptance = opening_range_ready & (close < opening_low)
    event_direction = pd.Series(0, index=out.index, dtype="int64")
    event_direction = event_direction.mask(long_acceptance, 1)
    event_direction = event_direction.mask(short_acceptance, -1)
    raw_event = event_direction.ne(0)
    session_event_number = raw_event.astype("int64").groupby(keys, dropna=False, sort=False).cumsum()
    first_session_event = raw_event & session_event_number.eq(1)

    acceptance_distance = pd.Series(0.0, index=out.index, dtype="float64")
    acceptance_distance = acceptance_distance.mask(long_acceptance, (close - opening_high) / tick_size)
    acceptance_distance = acceptance_distance.mask(short_acceptance, (opening_low - close) / tick_size)

    long_favorable_ticks = (future_high - entry_price) / tick_size
    short_favorable_ticks = (entry_price - future_low) / tick_size
    long_adverse_ticks = (entry_price - future_low) / tick_size
    short_adverse_ticks = (future_high - entry_price) / tick_size
    favorable_ticks = pd.Series(np.nan, index=out.index, dtype="float64")
    favorable_ticks = favorable_ticks.mask(event_direction.gt(0), long_favorable_ticks)
    favorable_ticks = favorable_ticks.mask(event_direction.lt(0), short_favorable_ticks)
    adverse_ticks = pd.Series(np.nan, index=out.index, dtype="float64")
    adverse_ticks = adverse_ticks.mask(event_direction.gt(0), long_adverse_ticks)
    adverse_ticks = adverse_ticks.mask(event_direction.lt(0), short_adverse_ticks)

    valid = (
        _path_valid_mask(out)
        & first_session_event
        & entry_price.notna()
        & exit_price.notna()
        & favorable_ticks.notna()
        & adverse_ticks.notna()
    )
    signed_gross_ticks = event_direction.astype(float) * (exit_price - entry_price) / tick_size
    gross_dollars = signed_gross_ticks * tick_value
    net_dollars = gross_dollars - cost_dollars
    direction = pd.Series(0, index=out.index, dtype="int64").mask(valid, event_direction)
    cols = _opening_range_event_capture_columns(spec.slug)

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = valid.astype(bool)
    out[spec.gross_column] = gross_dollars.where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = net_dollars.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = pd.Series(cost_ticks, index=out.index).where(valid)
    out[cols["opening_range_high"]] = opening_high.where(opening_range_ready)
    out[cols["opening_range_low"]] = opening_low.where(opening_range_ready)
    out[cols["event_direction"]] = event_direction.where(opening_range_ready, 0)
    out[cols["acceptance_distance_ticks"]] = acceptance_distance.where(opening_range_ready)
    out[cols["favorable_excursion_ticks"]] = favorable_ticks.where(valid)
    out[cols["adverse_excursion_ticks"]] = adverse_ticks.where(valid)
    out[cols["timeout_exit_ticks"]] = signed_gross_ticks.where(valid)
    out[cols["session_event_number"]] = session_event_number.where(raw_event)
    return out


def apply_opportunity_risk_asymmetry_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    future_high = _forward_path_extreme(out, "high", "max")
    future_low = _forward_path_extreme(out, "low", "min")

    tick_size = float(cost_config["tick_size"])
    tick_value = float(cost_config["tick_value"])
    cost_dollars = float(cost_config["round_turn_cost_dollars"])
    cost_ticks = float(cost_config["cost_ticks"])
    risk_floor_ticks = cost_ticks + float(cost_config["min_profit_ticks"])

    long_opportunity_ticks = (future_high - entry_price) / tick_size
    long_risk_ticks = (entry_price - future_low) / tick_size
    short_opportunity_ticks = (entry_price - future_low) / tick_size
    short_risk_ticks = (future_high - entry_price) / tick_size
    long_denominator = pd.Series(np.maximum(long_risk_ticks, risk_floor_ticks), index=out.index)
    short_denominator = pd.Series(np.maximum(short_risk_ticks, risk_floor_ticks), index=out.index)
    long_opportunity_risk = long_opportunity_ticks / long_denominator
    short_opportunity_risk = short_opportunity_ticks / short_denominator
    opportunity_risk_edge = long_opportunity_risk - short_opportunity_risk

    valid = (
        _path_valid_mask(out)
        & entry_price.notna()
        & future_high.notna()
        & future_low.notna()
        & np.isfinite(long_opportunity_ticks)
        & np.isfinite(long_risk_ticks)
        & np.isfinite(short_opportunity_ticks)
        & np.isfinite(short_risk_ticks)
        & np.isfinite(long_opportunity_risk)
        & np.isfinite(short_opportunity_risk)
    )
    long_selected = (
        valid
        & (long_opportunity_ticks > risk_floor_ticks)
        & (opportunity_risk_edge >= OPPORTUNITY_RISK_EDGE_RATIO)
    )
    short_selected = (
        valid
        & (short_opportunity_ticks > risk_floor_ticks)
        & (-opportunity_risk_edge >= OPPORTUNITY_RISK_EDGE_RATIO)
    )

    direction = pd.Series(0, index=out.index, dtype="int64")
    direction = direction.mask(long_selected, 1)
    direction = direction.mask(short_selected, -1)
    nonflat = direction.ne(0) & valid
    selected_opportunity_ticks = pd.Series(0.0, index=out.index)
    selected_opportunity_ticks = selected_opportunity_ticks.mask(direction.gt(0), long_opportunity_ticks)
    selected_opportunity_ticks = selected_opportunity_ticks.mask(direction.lt(0), short_opportunity_ticks)
    signed_gross_ticks = direction.astype(float) * selected_opportunity_ticks
    signed_net_ticks = direction.astype(float) * (selected_opportunity_ticks - cost_ticks).clip(lower=0.0)

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = direction
    out[spec.nonflat_column] = nonflat.astype(bool)
    out[spec.gross_column] = (signed_gross_ticks * tick_value).where(valid)
    out[spec.cost_column] = pd.Series(cost_dollars, index=out.index).where(valid)
    out[spec.net_column] = (signed_net_ticks * tick_value).where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = pd.Series(risk_floor_ticks, index=out.index).where(valid)
    out[f"target_long_opportunity_ticks_{spec.slug}"] = long_opportunity_ticks.where(valid)
    out[f"target_long_risk_ticks_{spec.slug}"] = long_risk_ticks.where(valid)
    out[f"target_short_opportunity_ticks_{spec.slug}"] = short_opportunity_ticks.where(valid)
    out[f"target_short_risk_ticks_{spec.slug}"] = short_risk_ticks.where(valid)
    out[f"target_long_opportunity_risk_{spec.slug}"] = long_opportunity_risk.where(valid)
    out[f"target_short_opportunity_risk_{spec.slug}"] = short_opportunity_risk.where(valid)
    out[f"target_opportunity_risk_edge_{spec.slug}"] = opportunity_risk_edge.where(valid)
    return out


def _opportunity_risk_component_columns(slug: str) -> dict[str, str]:
    return {
        "long_opportunity_ticks": f"target_long_opportunity_ticks_{slug}",
        "long_risk_ticks": f"target_long_risk_ticks_{slug}",
        "short_opportunity_ticks": f"target_short_opportunity_ticks_{slug}",
        "short_risk_ticks": f"target_short_risk_ticks_{slug}",
        "long_opportunity_risk": f"target_long_opportunity_risk_{slug}",
        "short_opportunity_risk": f"target_short_opportunity_risk_{slug}",
        "opportunity_risk_edge": f"target_opportunity_risk_edge_{slug}",
        "best_opportunity_risk": f"target_best_opportunity_risk_{slug}",
    }


def apply_opportunity_risk_component_rank_30m_target(
    frame: pd.DataFrame,
    cost_config: Mapping[str, float],
    spec: TargetSpec,
) -> pd.DataFrame:
    out = frame.sort_values("ts", kind="mergesort").reset_index(drop=True).copy()
    ts = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    entry_price = _numeric(out, "open").shift(-ENTRY_OFFSET_BARS)
    entry_ts = ts.shift(-ENTRY_OFFSET_BARS)
    exit_ts = ts.shift(-EXIT_OFFSET_BARS)
    future_high = _forward_path_extreme(out, "high", "max")
    future_low = _forward_path_extreme(out, "low", "min")

    tick_size = float(cost_config["tick_size"])
    risk_floor_ticks = float(cost_config["cost_ticks"]) + float(cost_config["min_profit_ticks"])
    cols = _opportunity_risk_component_columns(spec.slug)

    long_opportunity_ticks = (future_high - entry_price) / tick_size
    long_risk_ticks = (entry_price - future_low) / tick_size
    short_opportunity_ticks = (entry_price - future_low) / tick_size
    short_risk_ticks = (future_high - entry_price) / tick_size
    long_denominator = pd.Series(np.maximum(long_risk_ticks, risk_floor_ticks), index=out.index)
    short_denominator = pd.Series(np.maximum(short_risk_ticks, risk_floor_ticks), index=out.index)
    long_opportunity_risk = long_opportunity_ticks / long_denominator
    short_opportunity_risk = short_opportunity_ticks / short_denominator
    opportunity_risk_edge = long_opportunity_risk - short_opportunity_risk
    best_opportunity_risk = pd.Series(
        np.maximum(long_opportunity_risk, short_opportunity_risk),
        index=out.index,
        dtype="float64",
    )

    valid = (
        _path_valid_mask(out)
        & entry_price.notna()
        & future_high.notna()
        & future_low.notna()
        & np.isfinite(long_opportunity_ticks)
        & np.isfinite(long_risk_ticks)
        & np.isfinite(short_opportunity_ticks)
        & np.isfinite(short_risk_ticks)
        & np.isfinite(long_opportunity_risk)
        & np.isfinite(short_opportunity_risk)
        & np.isfinite(best_opportunity_risk)
    )
    best_side = pd.Series(0, index=out.index, dtype="int64")
    best_side = best_side.mask(valid & (long_opportunity_risk > short_opportunity_risk), 1)
    best_side = best_side.mask(valid & (short_opportunity_risk > long_opportunity_risk), -1)

    out[spec.valid_column] = valid.astype(bool)
    out[spec.direction_column] = best_side
    out[spec.nonflat_column] = best_side.ne(0) & valid
    out[spec.gross_column] = best_opportunity_risk.where(valid)
    out[spec.cost_column] = pd.Series(0.0, index=out.index).where(valid)
    out[spec.net_column] = best_opportunity_risk.where(valid)
    out[spec.entry_ts_column] = entry_ts.where(valid)
    out[spec.exit_ts_column] = exit_ts.where(valid)
    out[spec.threshold_ticks_column] = pd.Series(risk_floor_ticks, index=out.index).where(valid)
    out[cols["long_opportunity_ticks"]] = long_opportunity_ticks.where(valid)
    out[cols["long_risk_ticks"]] = long_risk_ticks.where(valid)
    out[cols["short_opportunity_ticks"]] = short_opportunity_ticks.where(valid)
    out[cols["short_risk_ticks"]] = short_risk_ticks.where(valid)
    out[cols["long_opportunity_risk"]] = long_opportunity_risk.where(valid)
    out[cols["short_opportunity_risk"]] = short_opportunity_risk.where(valid)
    out[cols["opportunity_risk_edge"]] = opportunity_risk_edge.where(valid)
    out[spec.rank_score_column or cols["best_opportunity_risk"]] = best_opportunity_risk.where(valid)
    return out


TARGET_SPECS: dict[str, TargetSpec] = {
    "vol_scaled_terminal_30m_v1": TargetSpec(
        hypothesis_id="vol_scaled_terminal_30m_v1",
        target_family="es_vol_scaled_terminal_30m",
        slug="vol_scaled_terminal_30m",
        description=(
            "ES-only 30-minute terminal direction target using next-open entry, "
            "30-minute exit, and a causal rolling-volatility-scaled deadzone."
        ),
        apply=apply_vol_scaled_terminal_30m_target,
    ),
    "triple_barrier_30m_v1": TargetSpec(
        hypothesis_id="triple_barrier_30m_v1",
        target_family="es_triple_barrier_30m",
        slug="triple_barrier_30m",
        description=(
            "ES-only 30-minute first-touch target using next-open entry and "
            "causal rolling-volatility-scaled profit/stop barriers."
        ),
        apply=apply_triple_barrier_30m_target,
    ),
    "prior_extreme_failure_30m_v1": TargetSpec(
        hypothesis_id="prior_extreme_failure_30m_v1",
        target_family="es_prior_extreme_failure_30m",
        slug="prior_extreme_failure_30m",
        description=(
            "ES-only 30-minute target conditioned on probing a completed prior-session "
            "high/low, closing back inside, and then moving in the failure direction."
        ),
        apply=apply_prior_extreme_failure_30m_target,
    ),
    "vwap_reversion_30m_v1": TargetSpec(
        hypothesis_id="vwap_reversion_30m_v1",
        target_family="es_vwap_reversion_30m",
        slug="vwap_reversion_30m",
        description=(
            "ES-only 30-minute target conditioned on stretching away from causal "
            "same-session VWAP and then moving back toward VWAP."
        ),
        apply=apply_vwap_reversion_30m_target,
    ),
    "vwap_reclaim_continuation_15m_v1": TargetSpec(
        hypothesis_id="vwap_reclaim_continuation_15m_v1",
        target_family="es_vwap_reclaim_continuation_15m",
        slug="vwap_reclaim_continuation_15m",
        description=(
            "ES-only 15-minute continuation target conditioned on a causal excursion "
            "away from same-session VWAP followed by a reclaim through VWAP."
        ),
        apply=apply_vwap_reclaim_continuation_15m_target,
        auxiliary_columns=tuple(_vwap_reclaim_columns("vwap_reclaim_continuation_15m").values()),
        horizon_bars=VWAP_RECLAIM_HORIZON_BARS,
        threshold_description=(
            "max(round-turn cost ticks + min_profit_ticks, prior 60-bar 1m "
            "close-diff std * sqrt(15)); event requires causal VWAP excursion "
            "and reclaim before next-open entry"
        ),
    ),
    "opening_drive_failed_followthrough_15m_v1": TargetSpec(
        hypothesis_id="opening_drive_failed_followthrough_15m_v1",
        target_family="es_opening_drive_failed_followthrough_15m",
        slug="opening_drive_failed_followthrough_15m",
        description=(
            "ES-only 15-minute reversal target conditioned on a completed causal "
            "same-session opening drive followed by a failed continuation attempt "
            "in the drive direction."
        ),
        apply=apply_opening_drive_failed_followthrough_15m_target,
        auxiliary_columns=tuple(
            _opening_drive_failed_followthrough_columns("opening_drive_failed_followthrough_15m").values()
        ),
        horizon_bars=OPENING_DRIVE_FAILED_FOLLOWTHROUGH_HORIZON_BARS,
        threshold_description=(
            "max(round-turn cost ticks + min_profit_ticks, prior 60-bar 1m "
            "close-diff std * sqrt(15)); event requires completed first 15 "
            "session bars, prior continuation attempt, failed followthrough, "
            "next-open entry, and fixed 15-minute timeout exit"
        ),
    ),
    "session_compression_breakout_30m_v1": TargetSpec(
        hypothesis_id="session_compression_breakout_30m_v1",
        target_family="es_session_compression_breakout_30m",
        slug="session_compression_breakout_30m",
        description=(
            "ES-only 30-minute continuation target conditioned on a completed "
            "causal same-session compression box followed by a breakout from "
            "that box."
        ),
        apply=apply_session_compression_breakout_30m_target,
        auxiliary_columns=tuple(_session_compression_breakout_columns("session_compression_breakout_30m").values()),
        threshold_description=(
            "max(round-turn cost ticks + min_profit_ticks, prior 60-bar 1m "
            "close-diff std * sqrt(30)); event requires prior completed "
            "30-bar compression box range <= causal rolling 25th percentile "
            "of prior 120 boxes with minimum 60 boxes, then a one-tick break "
            "outside the box, next-open entry, and fixed 30-minute timeout exit"
        ),
    ),
    "volume_pace_breakout_continuation_30m_v1": TargetSpec(
        hypothesis_id="volume_pace_breakout_continuation_30m_v1",
        target_family="es_volume_pace_breakout_continuation_30m",
        slug="volume_pace_breakout_continuation_30m",
        description=(
            "ES-only 30-minute continuation target conditioned on a completed "
            "causal prior 60-bar same-session range break confirmed by elevated "
            "causal volume pace."
        ),
        apply=apply_volume_pace_breakout_continuation_30m_target,
        auxiliary_columns=tuple(
            _volume_pace_breakout_columns("volume_pace_breakout_continuation_30m").values()
        ),
        threshold_description=(
            "max(round-turn cost ticks + min_profit_ticks, prior 60-bar 1m "
            "close-diff std * sqrt(30)); event requires a completed prior "
            "60-bar same-session range, one-tick close break, same-session-bar "
            "volume pace ratio >= 1.5 versus median of at least 20 prior "
            "sessions, next-open entry, and fixed 30-minute timeout exit"
        ),
    ),
    "first_hour_midday_pullback_continuation_30m_v1": TargetSpec(
        hypothesis_id="first_hour_midday_pullback_continuation_30m_v1",
        target_family="es_first_hour_midday_pullback_continuation_30m",
        slug="first_hour_midday_pullback_continuation_30m",
        description=(
            "ES-only 2023-2024 30-minute continuation target conditioned on a "
            "strong first-hour directional move followed by a controlled midday "
            "pullback and one-tick resumption in the first-hour direction."
        ),
        apply=apply_first_hour_midday_pullback_continuation_30m_target,
        auxiliary_columns=(
            "target_first_hour_open_first_hour_midday_pullback_continuation_30m",
            "target_first_hour_extreme_first_hour_midday_pullback_continuation_30m",
            "target_first_hour_move_ticks_first_hour_midday_pullback_continuation_30m",
            "target_first_hour_direction_first_hour_midday_pullback_continuation_30m",
            "target_first_hour_threshold_ticks_first_hour_midday_pullback_continuation_30m",
            "target_pullback_depth_first_hour_midday_pullback_continuation_30m",
            "target_session_midpoint_first_hour_midday_pullback_continuation_30m",
            "target_event_direction_first_hour_midday_pullback_continuation_30m",
            "target_resumption_ticks_first_hour_midday_pullback_continuation_30m",
            "target_timeout_exit_ticks_first_hour_midday_pullback_continuation_30m",
        ),
        threshold_description=(
            "label threshold = max(round-turn cost ticks + min_profit_ticks, "
            "prior 60-bar 1m close-diff std * sqrt(30)); first-hour strength "
            "requires max(12 ticks, round-turn cost ticks + min_profit_ticks, "
            "prior 60-bar 1m close-diff std * sqrt(60)); event requires first "
            "60 valid same-session bars, 35%-60% pullback depth, 11:00 through "
            "13:30 America/Chicago window, causal session-midpoint guard, "
            "one-tick resumption, next-open entry, and fixed 30-minute "
            "same-session timeout exit"
        ),
    ),
    "late_session_range_resolve_session_close_v1": TargetSpec(
        hypothesis_id="late_session_range_resolve_session_close_v1",
        target_family="es_late_session_range_resolve_session_close",
        slug="late_session_range_resolve_session_close",
        description=(
            "ES-only session-close continuation target conditioned on a completed "
            "14:00-15:00 America/Chicago late-session range and a post-15:00 "
            "break from that range."
        ),
        apply=apply_late_session_range_resolve_session_close_target,
        auxiliary_columns=tuple(
            _late_session_range_resolve_columns("late_session_range_resolve_session_close").values()
        ),
        horizon_bars=LATE_SESSION_THRESHOLD_HORIZON_BARS,
        threshold_description=(
            "session-close exit; completed 14:00-15:00 America/Chicago same-session "
            "range; event requires one-tick close break after 15:00 and before "
            "the configured regular close; next-open entry; configured same-session "
            "regular-close exit; max(round-turn cost ticks + min_profit_ticks, "
            "prior 60-bar 1m close-diff std * sqrt(minutes_until_close))"
        ),
    ),
    "opportunity_risk_asymmetry_30m_v1": TargetSpec(
        hypothesis_id="opportunity_risk_asymmetry_30m_v1",
        target_family="es_opportunity_risk_asymmetry_30m",
        slug="opportunity_risk_asymmetry_30m",
        description=(
            "ES-only 30-minute target comparing future path opportunity versus adverse "
            "path risk from the next-open entry, with a fixed cost-plus-profit risk floor."
        ),
        apply=apply_opportunity_risk_asymmetry_30m_target,
        auxiliary_columns=(
            "target_long_opportunity_ticks_opportunity_risk_asymmetry_30m",
            "target_long_risk_ticks_opportunity_risk_asymmetry_30m",
            "target_short_opportunity_ticks_opportunity_risk_asymmetry_30m",
            "target_short_risk_ticks_opportunity_risk_asymmetry_30m",
            "target_long_opportunity_risk_opportunity_risk_asymmetry_30m",
            "target_short_opportunity_risk_opportunity_risk_asymmetry_30m",
            "target_opportunity_risk_edge_opportunity_risk_asymmetry_30m",
        ),
        threshold_description=(
            "risk floor = round-turn cost ticks + min_profit_ticks; direction requires "
            f"opportunity/risk edge >= {OPPORTUNITY_RISK_EDGE_RATIO}"
        ),
    ),
    "opportunity_risk_component_rank_30m_v1": TargetSpec(
        hypothesis_id="opportunity_risk_component_rank_30m_v1",
        target_family="es_opportunity_risk_component_rank_30m",
        slug="opportunity_risk_component_rank_30m",
        description=(
            "ES-only 30-minute component-rank target that models future long/short "
            "opportunity and risk ticks first, then ranks setup quality by the predicted "
            "best opportunity/risk score before any directional promotion."
        ),
        apply=apply_opportunity_risk_component_rank_30m_target,
        auxiliary_columns=(
            "target_long_opportunity_ticks_opportunity_risk_component_rank_30m",
            "target_long_risk_ticks_opportunity_risk_component_rank_30m",
            "target_short_opportunity_ticks_opportunity_risk_component_rank_30m",
            "target_short_risk_ticks_opportunity_risk_component_rank_30m",
            "target_long_opportunity_risk_opportunity_risk_component_rank_30m",
            "target_short_opportunity_risk_opportunity_risk_component_rank_30m",
            "target_opportunity_risk_edge_opportunity_risk_component_rank_30m",
        ),
        component_model_columns=(
            "target_long_opportunity_ticks_opportunity_risk_component_rank_30m",
            "target_long_risk_ticks_opportunity_risk_component_rank_30m",
            "target_short_opportunity_ticks_opportunity_risk_component_rank_30m",
            "target_short_risk_ticks_opportunity_risk_component_rank_30m",
        ),
        rank_score_column="target_best_opportunity_risk_opportunity_risk_component_rank_30m",
        evaluation_mode=EVALUATION_COMPONENT_RANK,
        threshold_description=(
            "component-rank only: risk floor = round-turn cost ticks + min_profit_ticks; "
            "no long/short/flat threshold is forced at discovery"
        ),
    ),
    "opening_range_acceptance_continuation_30m_v1": TargetSpec(
        hypothesis_id="opening_range_acceptance_continuation_30m_v1",
        target_family="es_opening_range_acceptance_continuation_30m",
        slug="opening_range_acceptance_continuation_30m",
        description=(
            "ES-only 30-minute continuation target conditioned on close acceptance "
            "outside the completed first 30 session bars' opening range."
        ),
        apply=apply_opening_range_acceptance_continuation_30m_target,
        auxiliary_columns=tuple(_opening_range_columns("opening_range_acceptance_continuation_30m").values()),
        threshold_description=(
            "completed first 30 session bars; event close outside opening range; "
            "future favorable path excursion must exceed round-turn cost ticks + min_profit_ticks"
        ),
    ),
    "opening_range_acceptance_continuation_event_capture_30m_v2": TargetSpec(
        hypothesis_id="opening_range_acceptance_continuation_event_capture_30m_v2",
        target_family="es_opening_range_acceptance_continuation_event_capture_30m",
        slug="opening_range_acceptance_event_capture_30m",
        description=(
            "ES-only 30-minute fixed-timeout event-capture target using the first "
            "post-opening-range acceptance event per session."
        ),
        apply=apply_opening_range_acceptance_event_capture_30m_target,
        auxiliary_columns=tuple(
            _opening_range_event_capture_columns("opening_range_acceptance_event_capture_30m").values()
        ),
        threshold_description=(
            "completed first 30 session bars; first event close outside opening range; "
            "next-open entry; fixed 30-minute timeout exit; net dollars subtract round-turn cost"
        ),
    ),
}


def validate_target_hypothesis_registered(
    spec: TargetSpec,
    registry_path: Path = DEFAULT_TARGET_REGISTRY,
    stage: str = "discovery",
) -> list[str]:
    if not registry_path.exists():
        return [f"target registry missing: {_relative_path(registry_path)}"]
    try:
        payload = _read_json(registry_path)
    except Exception as exc:
        return [f"target registry invalid JSON: {exc}"]
    rows = payload.get("hypotheses", [])
    if not isinstance(rows, list):
        return ["target registry hypotheses must be a list"]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("target_hypothesis_id") != spec.hypothesis_id:
            continue
        failures: list[str] = []
        expected_status = {
            "discovery": "CANDIDATE",
            "confirmation": "DISCOVERY_PASS",
            "locked": "CONFIRMATION_PASS",
        }.get(stage)
        if expected_status is None:
            failures.append(f"{spec.hypothesis_id}: unknown smoke stage {stage}")
        elif row.get("status") != expected_status:
            failures.append(f"{spec.hypothesis_id}: expected {expected_status} status before {stage} smoke run")
        if row.get("wfa_allowed") is not False:
            failures.append(f"{spec.hypothesis_id}: wfa_allowed must be false before freeze")
        if row.get("target_family") != spec.target_family:
            failures.append(f"{spec.hypothesis_id}: target_family must be {spec.target_family}")
        if stage == "discovery" and row.get("source_reports") != []:
            failures.append(f"{spec.hypothesis_id}: discovery source_reports must be empty before discovery smoke")
        scope = row.get("scope", {})
        if not isinstance(scope, Mapping):
            failures.append(f"{spec.hypothesis_id}: scope must be an object")
        else:
            if scope.get("markets") != [MARKET]:
                failures.append(f"{spec.hypothesis_id}: scope.markets must be ['ES']")
            if scope.get("years") != [2023, 2024]:
                failures.append(f"{spec.hypothesis_id}: scope.years must be [2023, 2024]")
        return failures
    return [f"{spec.hypothesis_id}: missing from target hypothesis registry"]


def validate_target_trial_status_registered(
    spec: TargetSpec,
    trial_statuses_path: Path = DEFAULT_TARGET_TRIAL_STATUSES,
    stage: str = "discovery",
) -> list[str]:
    if not trial_statuses_path.exists():
        return [f"target trial status ledger missing: {_relative_path(trial_statuses_path)}"]
    expected_status = {
        "discovery": "CANDIDATE",
        "confirmation": "DISCOVERY_PASS",
        "locked": "CONFIRMATION_PASS",
    }.get(stage)
    if expected_status is None:
        return [f"{spec.hypothesis_id}: unknown smoke stage {stage}"]
    entries: list[Mapping[str, Any]] = []
    errors: list[str] = []
    for line_no, raw_line in enumerate(trial_statuses_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{_relative_path(trial_statuses_path)}:{line_no}: invalid JSONL: {exc}")
            continue
        if not isinstance(item, Mapping):
            errors.append(f"{_relative_path(trial_statuses_path)}:{line_no}: entry is not an object")
            continue
        if item.get("hypothesis_id") == spec.hypothesis_id:
            entries.append(item)
    if errors:
        return errors
    if not entries:
        return [f"{spec.hypothesis_id}: missing from target trial status ledger"]
    latest = entries[-1]
    failures: list[str] = []
    if latest.get("status") != expected_status:
        failures.append(f"{spec.hypothesis_id}: expected latest trial status {expected_status} before {stage} smoke run")
    evidence = latest.get("evidence", [])
    if stage == "discovery":
        if latest.get("stage") != "register_candidate":
            failures.append(f"{spec.hypothesis_id}: expected latest trial stage register_candidate before discovery")
        if evidence != []:
            failures.append(f"{spec.hypothesis_id}: discovery evidence must be empty before discovery smoke")
    elif not isinstance(evidence, list) or not evidence:
        failures.append(f"{spec.hypothesis_id}: {expected_status} trial status requires evidence before {stage}")
    return failures


def non_overlapping_events(frame: pd.DataFrame, spec: TargetSpec) -> tuple[pd.DataFrame, int]:
    valid = frame.loc[frame[spec.valid_column].astype(bool)].copy()
    selected_indices: list[int] = []
    skipped = 0
    for _, group in valid.groupby(["market", "year", "session_segment_id"], dropna=False, sort=False):
        group = group.sort_values(spec.entry_ts_column, kind="mergesort")
        last_exit: pd.Timestamp | None = None
        for row in group.itertuples():
            entry_ts = getattr(row, spec.entry_ts_column)
            exit_ts = getattr(row, spec.exit_ts_column)
            if pd.isna(entry_ts) or pd.isna(exit_ts) or exit_ts <= entry_ts:
                skipped += 1
                continue
            if last_exit is not None and entry_ts <= last_exit:
                skipped += 1
                continue
            selected_indices.append(int(row.Index))
            last_exit = exit_ts
    events = frame.loc[selected_indices].sort_values(
        ["market", "year", spec.entry_ts_column],
        kind="mergesort",
    )
    return events.reset_index(drop=True), skipped


def duplicate_target_overlap(events: pd.DataFrame, spec: TargetSpec) -> dict[str, Any]:
    if events.empty:
        return {"available": False, "overlap_with_current_15m_deadzone": None}
    new_nonflat = events[spec.nonflat_column].astype(bool)
    current_nonflat = pd.to_numeric(events["target_sign_with_deadzone"], errors="coerce").fillna(0).ne(0)
    denominator = int(new_nonflat.sum())
    overlap = int((new_nonflat & current_nonflat).sum())
    return {
        "available": True,
        "new_nonflat_count": denominator,
        "current_15m_nonflat_count": int(current_nonflat.sum()),
        "overlap_count": overlap,
        "overlap_with_current_15m_deadzone": float(overlap / denominator) if denominator else None,
        "max_allowed_overlap": 0.80,
    }


def class_balance(events: pd.DataFrame, spec: TargetSpec) -> dict[str, Any]:
    total = int(len(events))
    direction = pd.to_numeric(events[spec.direction_column], errors="coerce").fillna(0)
    counts = {
        "long": int((direction > 0).sum()),
        "short": int((direction < 0).sum()),
        "flat": int((direction == 0).sum()),
    }
    rates = {key: float(value / total) if total else None for key, value in counts.items()}
    return {"event_count": total, "counts": counts, "rates": rates}


def target_distribution_summary(events: pd.DataFrame, spec: TargetSpec) -> dict[str, Any]:
    columns = [spec.gross_column, spec.net_column, spec.threshold_ticks_column, *spec.auxiliary_columns]
    summary: dict[str, Any] = {}
    for column in columns:
        if column not in events.columns:
            continue
        values = pd.to_numeric(events[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty:
            summary[column] = {"count": 0}
            continue
        quantiles = values.quantile([0.05, 0.25, 0.50, 0.75, 0.95])
        summary[column] = {
            "count": int(len(values)),
            "mean": _float_or_none(values.mean()),
            "std": _float_or_none(values.std()),
            "min": _float_or_none(values.min()),
            "p05": _float_or_none(quantiles.loc[0.05]),
            "p25": _float_or_none(quantiles.loc[0.25]),
            "p50": _float_or_none(quantiles.loc[0.50]),
            "p75": _float_or_none(quantiles.loc[0.75]),
            "p95": _float_or_none(quantiles.loc[0.95]),
            "max": _float_or_none(values.max()),
        }
    return summary


def _fit_estimator() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=1.0)),
        ]
    )


def _correlation(prediction: pd.Series, target: pd.Series, method: str) -> float | None:
    aligned = pd.DataFrame({"prediction": prediction, "target": target}).replace([np.inf, -np.inf], np.nan)
    aligned = aligned.dropna()
    if len(aligned) < 2:
        return None
    if aligned["prediction"].nunique(dropna=True) < 2 or aligned["target"].nunique(dropna=True) < 2:
        return None
    return _float_or_none(aligned["prediction"].corr(aligned["target"], method=method))


def _regression_diagnostics(prediction: pd.Series, target: pd.Series) -> dict[str, Any]:
    aligned = pd.DataFrame({"prediction": prediction, "target": target}).replace([np.inf, -np.inf], np.nan)
    aligned = aligned.dropna()
    if len(aligned) < 2:
        return {"available": False, "reason": "too_few_rows", "scored_rows": int(len(aligned))}
    residual = aligned["prediction"] - aligned["target"]
    centered = aligned["target"] - aligned["target"].mean()
    total_sum_squares = float((centered**2).sum())
    r2 = None if total_sum_squares <= 0.0 else 1.0 - float((residual**2).sum()) / total_sum_squares
    return {
        "available": True,
        "scored_rows": int(len(aligned)),
        "prediction_std": _float_or_none(aligned["prediction"].std()),
        "target_std": _float_or_none(aligned["target"].std()),
        "r2": _float_or_none(r2),
        "pearson": _correlation(aligned["prediction"], aligned["target"], "pearson"),
        "spearman": _correlation(aligned["prediction"], aligned["target"], "spearman"),
        "mae": _float_or_none(residual.abs().mean()),
        "rmse": _float_or_none(math.sqrt(float((residual**2).mean()))),
    }


def _auxiliary_target_metrics(
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: Sequence[str],
    spec: TargetSpec,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for column in spec.auxiliary_columns:
        if column not in train.columns or column not in test.columns:
            metrics[column] = {"available": False, "reason": "missing_column"}
            continue
        y_train = pd.to_numeric(train[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
        y_test = pd.to_numeric(test[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
        train_mask = y_train.notna()
        test_mask = y_test.notna()
        if int(train_mask.sum()) < 2 or int(test_mask.sum()) < 2:
            metrics[column] = {
                "available": False,
                "reason": "too_few_rows",
                "train_rows": int(train_mask.sum()),
                "test_rows": int(test_mask.sum()),
            }
            continue
        if y_train.loc[train_mask].nunique(dropna=True) < 2:
            metrics[column] = {
                "available": False,
                "reason": "constant_train_target",
                "train_rows": int(train_mask.sum()),
                "test_rows": int(test_mask.sum()),
            }
            continue
        estimator = _fit_estimator()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            estimator.fit(train.loc[train_mask, list(features)], y_train.loc[train_mask])
        prediction = pd.Series(
            estimator.predict(test.loc[test_mask, list(features)]),
            index=test.loc[test_mask].index,
            dtype="float64",
        )
        diagnostic = _regression_diagnostics(prediction, y_test.loc[test_mask])
        diagnostic["train_rows"] = int(train_mask.sum())
        diagnostic["test_rows"] = int(test_mask.sum())
        diagnostic["warning_count"] = len(caught)
        diagnostic["warnings"] = [str(item.message).splitlines()[0] for item in caught]
        metrics[column] = diagnostic
    return metrics


def _fit_single_target_prediction(
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: Sequence[str],
    column: str,
) -> tuple[pd.Series | None, dict[str, Any]]:
    if column not in train.columns or column not in test.columns:
        return None, {"available": False, "reason": "missing_column"}
    y_train = pd.to_numeric(train[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    y_test = pd.to_numeric(test[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    train_mask = y_train.notna()
    test_mask = y_test.notna()
    if int(train_mask.sum()) < 2 or int(test_mask.sum()) < 2:
        return None, {
            "available": False,
            "reason": "too_few_rows",
            "train_rows": int(train_mask.sum()),
            "test_rows": int(test_mask.sum()),
        }
    if y_train.loc[train_mask].nunique(dropna=True) < 2:
        return None, {
            "available": False,
            "reason": "constant_train_target",
            "train_rows": int(train_mask.sum()),
            "test_rows": int(test_mask.sum()),
        }
    estimator = _fit_estimator()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        estimator.fit(train.loc[train_mask, list(features)], y_train.loc[train_mask])
    prediction = pd.Series(
        estimator.predict(test.loc[test_mask, list(features)]),
        index=test.loc[test_mask].index,
        dtype="float64",
    )
    diagnostic = _regression_diagnostics(prediction, y_test.loc[test_mask])
    diagnostic["train_rows"] = int(train_mask.sum())
    diagnostic["test_rows"] = int(test_mask.sum())
    diagnostic["warning_count"] = len(caught)
    diagnostic["warnings"] = [str(item.message).splitlines()[0] for item in caught]
    return prediction, diagnostic


def _fold_metrics_component_rank(
    *,
    fold: Mapping[str, Any],
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: Sequence[str],
    spec: TargetSpec,
    top_fraction: float,
) -> tuple[dict[str, Any], pd.DataFrame]:
    cols = _opportunity_risk_component_columns(spec.slug)
    required_prediction_columns = {
        "long_opportunity_ticks": cols["long_opportunity_ticks"],
        "long_risk_ticks": cols["long_risk_ticks"],
        "short_opportunity_ticks": cols["short_opportunity_ticks"],
        "short_risk_ticks": cols["short_risk_ticks"],
    }
    predictions: dict[str, pd.Series] = {}
    component_metrics: dict[str, Any] = {}
    for name, column in required_prediction_columns.items():
        prediction, diagnostic = _fit_single_target_prediction(train, test, features, column)
        component_metrics[column] = diagnostic
        if prediction is not None:
            predictions[name] = prediction

    rank_score_column = spec.rank_score_column or cols["best_opportunity_risk"]
    scored = test.copy()
    if set(predictions) == set(required_prediction_columns):
        predicted = pd.DataFrame(
            {
                "pred_long_opportunity_ticks": predictions["long_opportunity_ticks"],
                "pred_long_risk_ticks": predictions["long_risk_ticks"],
                "pred_short_opportunity_ticks": predictions["short_opportunity_ticks"],
                "pred_short_risk_ticks": predictions["short_risk_ticks"],
                "risk_floor_ticks": pd.to_numeric(test[spec.threshold_ticks_column], errors="coerce"),
                "realized_rank_score": pd.to_numeric(test[rank_score_column], errors="coerce"),
                "actual_best_side": pd.to_numeric(test[spec.direction_column], errors="coerce").fillna(0),
            }
        )
        predicted = predicted.replace([np.inf, -np.inf], np.nan).dropna()
        long_denominator = np.maximum(
            predicted["pred_long_risk_ticks"].clip(lower=0.0),
            predicted["risk_floor_ticks"],
        )
        short_denominator = np.maximum(
            predicted["pred_short_risk_ticks"].clip(lower=0.0),
            predicted["risk_floor_ticks"],
        )
        predicted["pred_long_opportunity_risk"] = predicted["pred_long_opportunity_ticks"].clip(lower=0.0) / long_denominator
        predicted["pred_short_opportunity_risk"] = (
            predicted["pred_short_opportunity_ticks"].clip(lower=0.0) / short_denominator
        )
        predicted["prediction"] = np.maximum(
            predicted["pred_long_opportunity_risk"],
            predicted["pred_short_opportunity_risk"],
        )
        predicted["predicted_best_side"] = np.select(
            [
                predicted["pred_long_opportunity_risk"] > predicted["pred_short_opportunity_risk"],
                predicted["pred_short_opportunity_risk"] > predicted["pred_long_opportunity_risk"],
            ],
            [1.0, -1.0],
            default=0.0,
        )
        scored = scored.join(
            predicted[
                [
                    "prediction",
                    "predicted_best_side",
                    "realized_rank_score",
                    "actual_best_side",
                    "pred_long_opportunity_risk",
                    "pred_short_opportunity_risk",
                ]
            ],
            how="inner",
        )
    else:
        scored = scored.iloc[0:0].copy()
        scored["prediction"] = pd.Series(dtype="float64")
        scored["predicted_best_side"] = pd.Series(dtype="float64")
        scored["realized_rank_score"] = pd.Series(dtype="float64")
        scored["actual_best_side"] = pd.Series(dtype="float64")

    scored = scored.replace([np.inf, -np.inf], np.nan).dropna(subset=["prediction", "realized_rank_score"])
    top_count = int(math.ceil(len(scored) * top_fraction)) if len(scored) else 0
    top = scored.nlargest(top_count, "prediction") if top_count else scored.iloc[0:0].copy()
    baseline_avg_rank_score = _float_or_none(scored["realized_rank_score"].mean()) if len(scored) else None
    top_avg_rank_score = _float_or_none(top["realized_rank_score"].mean()) if len(top) else None
    top_rank_score_uplift = (
        None
        if baseline_avg_rank_score is None or top_avg_rank_score is None
        else float(top_avg_rank_score - baseline_avg_rank_score)
    )
    top_total_rank_score_uplift = (
        None if top_rank_score_uplift is None else float(top_rank_score_uplift * len(top))
    )
    comparable_side = scored["predicted_best_side"].ne(0) & scored["actual_best_side"].ne(0)
    best_side_accuracy = (
        float(scored.loc[comparable_side, "predicted_best_side"].eq(scored.loc[comparable_side, "actual_best_side"]).mean())
        if comparable_side.any()
        else None
    )
    metric = {
        "fold_id": str(fold["fold_id"]),
        "market": str(fold.get("market", "")),
        "evaluation_mode": EVALUATION_COMPONENT_RANK,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "scored_rows": int(len(scored)),
        "top_fraction": float(top_fraction),
        "top_rows": int(len(top)),
        "prediction_std": _float_or_none(scored["prediction"].std()) if len(scored) else None,
        "spearman_prediction_target": _correlation(scored["prediction"], scored["realized_rank_score"], "spearman"),
        "primary_regression_diagnostics": _regression_diagnostics(
            scored["prediction"],
            scored["realized_rank_score"],
        ),
        "component_target_metrics": component_metrics,
        "auxiliary_target_metrics": component_metrics,
        "best_side_accuracy": best_side_accuracy,
        "top_avg_rank_score": top_avg_rank_score,
        "baseline_avg_rank_score": baseline_avg_rank_score,
        "top_rank_score_uplift": _float_or_none(top_rank_score_uplift),
        "top_total_rank_score": _float_or_none(top["realized_rank_score"].sum()) if len(top) else None,
        "top_total_rank_score_uplift": _float_or_none(top_total_rank_score_uplift),
        "top_long_count": int((top.get("predicted_best_side", pd.Series(dtype="float64")) > 0).sum()),
        "top_short_count": int((top.get("predicted_best_side", pd.Series(dtype="float64")) < 0).sum()),
        "warning_count": sum(int(item.get("warning_count") or 0) for item in component_metrics.values()),
        "warnings": [
            warning
            for item in component_metrics.values()
            for warning in item.get("warnings", [])
        ],
    }
    return metric, top


def _fold_metrics(
    *,
    fold: Mapping[str, Any],
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: Sequence[str],
    spec: TargetSpec,
    top_fraction: float,
) -> tuple[dict[str, Any], pd.DataFrame]:
    if spec.evaluation_mode == EVALUATION_COMPONENT_RANK:
        return _fold_metrics_component_rank(
            fold=fold,
            train=train,
            test=test,
            features=features,
            spec=spec,
            top_fraction=top_fraction,
        )

    y_train = pd.to_numeric(train[spec.net_column], errors="coerce")
    y_test = pd.to_numeric(test[spec.net_column], errors="coerce")
    estimator = _fit_estimator()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        estimator.fit(train[list(features)], y_train)
    prediction = pd.Series(estimator.predict(test[list(features)]), index=test.index, dtype="float64")
    position = np.sign(prediction).astype(float)
    gross = pd.to_numeric(test[spec.gross_column], errors="coerce")
    cost = pd.to_numeric(test[spec.cost_column], errors="coerce").fillna(0.0)
    realized_gross = position * gross
    realized_net = realized_gross - np.where(position.ne(0), cost, 0.0)
    scored = test.copy()
    scored["prediction"] = prediction
    scored["position"] = position
    scored["realized_gross_dollars"] = realized_gross
    scored["realized_net_dollars"] = realized_net
    scored = scored.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["prediction", spec.net_column, "realized_net_dollars"]
    )
    top_count = int(math.ceil(len(scored) * top_fraction)) if len(scored) else 0
    top = (
        scored.assign(abs_prediction=scored["prediction"].abs()).nlargest(top_count, "abs_prediction")
        if top_count
        else scored.iloc[0:0].copy()
    )
    actual_direction = pd.to_numeric(scored[spec.direction_column], errors="coerce").fillna(0)
    signable = scored["position"].ne(0) & actual_direction.ne(0)
    signed_accuracy = (
        float(scored.loc[signable, "position"].eq(actual_direction.loc[signable]).mean())
        if signable.any()
        else None
    )
    warning_text = [str(item.message).splitlines()[0] for item in caught]
    metric = {
        "fold_id": str(fold["fold_id"]),
        "market": str(fold.get("market", "")),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "scored_rows": int(len(scored)),
        "top_fraction": float(top_fraction),
        "top_rows": int(len(top)),
        "prediction_std": _float_or_none(prediction.std()),
        "spearman_prediction_target": _correlation(prediction, y_test, "spearman"),
        "signed_nonflat_accuracy": signed_accuracy,
        "top_total_gross_dollars": _float_or_none(top["realized_gross_dollars"].sum()),
        "top_total_net_dollars": _float_or_none(top["realized_net_dollars"].sum()),
        "top_avg_net_dollars": _float_or_none(top["realized_net_dollars"].mean()),
        "top_long_count": int((top["position"] > 0).sum()),
        "top_short_count": int((top["position"] < 0).sum()),
        "warning_count": len(warning_text),
        "warnings": warning_text,
        "primary_regression_diagnostics": _regression_diagnostics(prediction, y_test),
        "auxiliary_target_metrics": _auxiliary_target_metrics(train, test, features, spec),
    }
    return metric, top


def stage_folds(stage: str, fold_ids: Sequence[str] | None = None) -> list[str]:
    if fold_ids:
        return list(fold_ids)
    if stage == "discovery":
        return list(DEFAULT_DISCOVERY_FOLDS)
    if stage == "confirmation":
        return list(DEFAULT_CONFIRMATION_FOLDS)
    if stage == "locked":
        return list(DEFAULT_LOCKED_FOLDS)
    raise SystemExit(f"unknown stage: {stage}")


def _selected_folds(split_manifest: Mapping[str, Any], fold_ids: Sequence[str]) -> list[Mapping[str, Any]]:
    raw_folds = split_manifest.get("folds", [])
    if not isinstance(raw_folds, list):
        raise SystemExit("split plan folds must be a list")
    by_id = {str(fold.get("fold_id")): fold for fold in raw_folds if isinstance(fold, Mapping)}
    missing = [fold_id for fold_id in fold_ids if fold_id not in by_id]
    if missing:
        raise SystemExit(f"requested folds missing from split plan: {missing}")
    failures: list[str] = []
    selected: list[Mapping[str, Any]] = []
    for fold_id in fold_ids:
        fold = by_id[fold_id]
        failures.extend(_validate_fold_fields(fold))
        if str(fold.get("market")) != MARKET:
            failures.append(f"{fold_id}: expected ES market")
        if str(fold.get("split_group")) != "research":
            failures.append(f"{fold_id}: expected research split_group")
        if fold.get("selection_allowed") is not True:
            failures.append(f"{fold_id}: selection_allowed must be true")
        if fold.get("final_holdout") is True or fold.get("is_final_holdout") is True:
            failures.append(f"{fold_id}: final holdout folds are forbidden")
        selected.append(fold)
    if failures:
        raise SystemExit("; ".join(failures))
    return selected


def stage_summary(fold_metrics: Sequence[Mapping[str, Any]], expected_fold_count: int) -> dict[str, Any]:
    evaluation_mode = next(
        (str(item.get("evaluation_mode")) for item in fold_metrics if item.get("evaluation_mode")),
        EVALUATION_DIRECTIONAL_NET,
    )
    top_rows = sum(int(item.get("top_rows") or 0) for item in fold_metrics)
    pred_stds = [float(item["prediction_std"]) for item in fold_metrics if item.get("prediction_std") is not None]
    if evaluation_mode == EVALUATION_COMPONENT_RANK:
        top_rank_score = sum(float(item.get("top_total_rank_score") or 0.0) for item in fold_metrics)
        top_rank_uplift = sum(float(item.get("top_total_rank_score_uplift") or 0.0) for item in fold_metrics)
        scored_rows = sum(int(item.get("scored_rows") or 0) for item in fold_metrics)
        baseline_total = sum(
            float(item.get("baseline_avg_rank_score") or 0.0) * int(item.get("scored_rows") or 0)
            for item in fold_metrics
        )
        return {
            "evaluation_mode": evaluation_mode,
            "expected_fold_count": int(expected_fold_count),
            "fold_count": int(len(fold_metrics)),
            "test_rows": sum(int(item.get("test_rows") or 0) for item in fold_metrics),
            "scored_rows": int(scored_rows),
            "top_rows": int(top_rows),
            "top_total_rank_score": float(top_rank_score),
            "top_avg_rank_score": float(top_rank_score / top_rows) if top_rows else None,
            "baseline_avg_rank_score": float(baseline_total / scored_rows) if scored_rows else None,
            "top_total_rank_score_uplift": float(top_rank_uplift),
            "top_avg_rank_score_uplift": float(top_rank_uplift / top_rows) if top_rows else None,
            "positive_rank_uplift_fold_count": sum(
                1 for item in fold_metrics if float(item.get("top_rank_score_uplift") or 0.0) > 0.0
            ),
            "min_prediction_std": min(pred_stds) if pred_stds else None,
        }

    top_net = sum(float(item.get("top_total_net_dollars") or 0.0) for item in fold_metrics)
    return {
        "evaluation_mode": evaluation_mode,
        "expected_fold_count": int(expected_fold_count),
        "fold_count": int(len(fold_metrics)),
        "test_rows": sum(int(item.get("test_rows") or 0) for item in fold_metrics),
        "scored_rows": sum(int(item.get("scored_rows") or 0) for item in fold_metrics),
        "top_rows": int(top_rows),
        "top_total_net_dollars": float(top_net),
        "top_avg_net_dollars": float(top_net / top_rows) if top_rows else None,
        "positive_top_net_fold_count": sum(
            1 for item in fold_metrics if float(item.get("top_total_net_dollars") or 0.0) > 0.0
        ),
        "min_prediction_std": min(pred_stds) if pred_stds else None,
    }


def evaluate_stage_gates(report: Mapping[str, Any]) -> dict[str, Any]:
    failures = list(report.get("failures", []))
    gates: list[dict[str, Any]] = [
        {
            "gate": "registry_inputs_and_schema",
            "pass": not failures,
            "failure_decision": "STOP_INPUT_FAILURE",
            "failures": failures,
        }
    ]
    summary = report["stage_summary"]
    evaluation_mode = str(report.get("evaluation_mode") or summary.get("evaluation_mode") or EVALUATION_DIRECTIONAL_NET)
    if evaluation_mode == EVALUATION_COMPONENT_RANK:
        event_count = int(report.get("event_count") or 0)
        gates.append(
            {
                "gate": "minimum_rank_event_count",
                "pass": event_count >= 1000,
                "failure_decision": "STOP_UNDERPOWERED",
                "event_count": event_count,
                "min_event_count": 1000,
            }
        )
        unstable = []
        if summary["fold_count"] != summary["expected_fold_count"]:
            unstable.append("missing_fold_metrics")
        if summary["top_rows"] <= 0:
            unstable.append("no_top_rows")
        if summary["min_prediction_std"] is None or float(summary["min_prediction_std"]) <= 0.0:
            unstable.append("constant_predictions")
        if int(summary["positive_rank_uplift_fold_count"]) < max(1, math.ceil(summary["expected_fold_count"] / 2)):
            unstable.append("too_few_positive_rank_uplift_folds")
        gates.append(
            {
                "gate": "stable_rank_uplift_folds",
                "pass": not unstable,
                "failure_decision": "STOP_UNSTABLE_RANK_UPLIFT",
                "failures": unstable,
            }
        )
        gates.append(
            {
                "gate": "positive_stage_rank_uplift",
                "pass": float(summary["top_total_rank_score_uplift"]) > 0.0,
                "failure_decision": f"STOP_{str(report['stage']).upper()}_NONPOSITIVE_RANK_UPLIFT",
                "top_total_rank_score_uplift": summary["top_total_rank_score_uplift"],
            }
        )
        decision = f"{str(report['stage']).upper()}_PASS"
        for gate in gates:
            if not gate["pass"]:
                decision = str(gate["failure_decision"])
                break
        return {"decision": decision, "gates": gates}

    balance = report["class_balance"]
    counts = balance["counts"]
    rates = balance["rates"]
    class_failures = [
        name
        for name in ("long", "short", "flat")
        if int(counts.get(name, 0)) < 1000 or float(rates.get(name) or 0.0) < 0.01
    ]
    gates.append(
        {
            "gate": "no_class_collapse",
            "pass": not class_failures,
            "failure_decision": "STOP_CLASS_COLLAPSE",
            "failures": class_failures,
            "min_count": 1000,
            "min_rate": 0.01,
        }
    )
    overlap = report["duplicate_target_overlap"].get("overlap_with_current_15m_deadzone")
    gates.append(
        {
            "gate": "not_duplicate_of_current_15m_deadzone",
            "pass": overlap is not None and float(overlap) <= 0.80,
            "failure_decision": "STOP_DUPLICATE_TARGET",
            "overlap": overlap,
            "max_allowed_overlap": 0.80,
        }
    )
    unstable = []
    if summary["fold_count"] != summary["expected_fold_count"]:
        unstable.append("missing_fold_metrics")
    if summary["top_rows"] <= 0:
        unstable.append("no_top_rows")
    if summary["min_prediction_std"] is None or float(summary["min_prediction_std"]) <= 0.0:
        unstable.append("constant_predictions")
    if int(summary["positive_top_net_fold_count"]) < max(1, math.ceil(summary["expected_fold_count"] / 2)):
        unstable.append("too_few_positive_folds")
    gates.append(
        {
            "gate": "stable_stage_folds",
            "pass": not unstable,
            "failure_decision": "STOP_UNSTABLE_FOLDS",
            "failures": unstable,
        }
    )
    gates.append(
        {
            "gate": "positive_stage_net",
            "pass": float(summary["top_total_net_dollars"]) > 0.0,
            "failure_decision": f"STOP_{str(report['stage']).upper()}_NEGATIVE_NET",
            "top_total_net_dollars": summary["top_total_net_dollars"],
        }
    )
    decision = f"{str(report['stage']).upper()}_PASS"
    for gate in gates:
        if not gate["pass"]:
            decision = str(gate["failure_decision"])
            break
    return {"decision": decision, "gates": gates}


def _markdown_report(report: Mapping[str, Any]) -> str:
    summary = report["stage_summary"]
    evaluation_mode = str(report.get("evaluation_mode") or summary.get("evaluation_mode") or EVALUATION_DIRECTIONAL_NET)
    lines = [
        f"# {report['hypothesis_id']} ES 30m Target Smoke",
        "",
        f"- run: {report['run']}",
        f"- hypothesis_id: {report['hypothesis_id']}",
        f"- stage: {report['stage']}",
        f"- decision: {report['decision']}",
        "- output_type: target-construction smoke only",
        "- executable_pnl: false",
        "- wfa: false",
        "",
        "## Gates",
        "",
        "| gate | pass |",
        "| --- | --- |",
    ]
    for gate in report["gates"]:
        lines.append(f"| {gate['gate']} | {gate['pass']} |")
    if evaluation_mode == EVALUATION_COMPONENT_RANK:
        summary_lines = [
            "",
            "## Stage Summary",
            "",
            f"- folds: {summary['fold_count']} / {summary['expected_fold_count']}",
            f"- top_rows: {summary['top_rows']}",
            f"- top_avg_rank_score: {summary['top_avg_rank_score']}",
            f"- baseline_avg_rank_score: {summary['baseline_avg_rank_score']}",
            f"- top_avg_rank_score_uplift: {summary['top_avg_rank_score_uplift']}",
            f"- positive_rank_uplift_fold_count: {summary['positive_rank_uplift_fold_count']}",
        ]
    else:
        summary_lines = [
            "",
            "## Stage Summary",
            "",
            f"- folds: {summary['fold_count']} / {summary['expected_fold_count']}",
            f"- top_rows: {summary['top_rows']}",
            f"- top_total_net_dollars: {summary['top_total_net_dollars']:.2f}",
            f"- positive_top_net_fold_count: {summary['positive_top_net_fold_count']}",
        ]
    lines.extend(
        [
            *summary_lines,
            "",
            "## Class Balance",
            "",
            f"- counts: {report['class_balance']['counts']}",
            f"- rates: {report['class_balance']['rates']}",
            "",
            "## Target Distribution",
            "",
            "| column | count | mean | p05 | p50 | p95 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for column, values in report.get("target_distribution", {}).items():
        lines.append(
            "| {column} | {count} | {mean} | {p05} | {p50} | {p95} |".format(
                column=column,
                count=values.get("count", 0),
                mean="NA" if values.get("mean") is None else f"{float(values['mean']):.6f}",
                p05="NA" if values.get("p05") is None else f"{float(values['p05']):.6f}",
                p50="NA" if values.get("p50") is None else f"{float(values['p50']):.6f}",
                p95="NA" if values.get("p95") is None else f"{float(values['p95']):.6f}",
            )
        )
    lines.extend(
        [
            "",
            "## Duplicate Target Overlap",
            "",
            f"- overlap_with_current_15m_deadzone: {report['duplicate_target_overlap'].get('overlap_with_current_15m_deadzone')}",
            "",
            "## Fold Metrics",
            "",
        ]
    )
    if evaluation_mode == EVALUATION_COMPONENT_RANK:
        lines.extend(
            [
                "| fold | top_rows | top_rank | baseline_rank | uplift | pred_std | spearman |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in report["fold_metrics"]:
            pred_std = row["prediction_std"]
            spearman = row["spearman_prediction_target"]
            lines.append(
                "| {fold} | {top_rows} | {top_rank} | {baseline_rank} | {uplift} | {pred_std} | {spearman} |".format(
                    fold=row["fold_id"],
                    top_rows=row["top_rows"],
                    top_rank=(
                        "NA" if row.get("top_avg_rank_score") is None else f"{float(row['top_avg_rank_score']):.6f}"
                    ),
                    baseline_rank=(
                        "NA"
                        if row.get("baseline_avg_rank_score") is None
                        else f"{float(row['baseline_avg_rank_score']):.6f}"
                    ),
                    uplift=(
                        "NA"
                        if row.get("top_rank_score_uplift") is None
                        else f"{float(row['top_rank_score_uplift']):.6f}"
                    ),
                    pred_std="NA" if pred_std is None else f"{float(pred_std):.6f}",
                    spearman="NA" if spearman is None else f"{float(spearman):.6f}",
                )
            )
    else:
        lines.extend(
            [
                "| fold | top_rows | top_net | pred_std | spearman |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in report["fold_metrics"]:
            pred_std = row["prediction_std"]
            spearman = row["spearman_prediction_target"]
            lines.append(
                "| {fold} | {top_rows} | {top_net:.2f} | {pred_std} | {spearman} |".format(
                    fold=row["fold_id"],
                    top_rows=row["top_rows"],
                    top_net=float(row["top_total_net_dollars"] or 0.0),
                    pred_std="NA" if pred_std is None else f"{float(pred_std):.6f}",
                    spearman="NA" if spearman is None else f"{float(spearman):.6f}",
                )
            )
    if any(row.get("auxiliary_target_metrics") for row in report["fold_metrics"]):
        lines.extend(
            [
                "",
                "## Auxiliary Target Diagnostics",
                "",
                "| fold | target | r2 | pearson | spearman | mae | rmse |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in report["fold_metrics"]:
            for column, diagnostic in row.get("auxiliary_target_metrics", {}).items():
                if not diagnostic.get("available"):
                    continue
                lines.append(
                    "| {fold} | {column} | {r2} | {pearson} | {spearman} | {mae} | {rmse} |".format(
                        fold=row["fold_id"],
                        column=column,
                        r2="NA" if diagnostic.get("r2") is None else f"{float(diagnostic['r2']):.6f}",
                        pearson=(
                            "NA" if diagnostic.get("pearson") is None else f"{float(diagnostic['pearson']):.6f}"
                        ),
                        spearman=(
                            "NA" if diagnostic.get("spearman") is None else f"{float(diagnostic['spearman']):.6f}"
                        ),
                        mae="NA" if diagnostic.get("mae") is None else f"{float(diagnostic['mae']):.6f}",
                        rmse="NA" if diagnostic.get("rmse") is None else f"{float(diagnostic['rmse']):.6f}",
                    )
                )
    lines.extend(
        [
            "",
            "## Do Not Do",
            "",
            "- Do not run confirmation unless discovery decision is DISCOVERY_PASS.",
            "- Do not run locked unless confirmation decision is CONFIRMATION_PASS.",
            "- Do not run WFA, Phase 8, promotion, downloads, or artifact freeze from this result.",
            "- Do not tune thresholds, features, costs, or fold selection after seeing this report.",
            "",
        ]
    )
    return "\n".join(lines)


def _report_paths(reports_root: Path, run: str, hypothesis_id: str, stage: str) -> tuple[Path, Path]:
    stem = f"{run}_{hypothesis_id}_{stage}_smoke"
    return reports_root / f"{stem}.md", reports_root / f"{stem}.json"


def run_harness(
    *,
    hypothesis_id: str,
    run: str = DEFAULT_RUN,
    stage: str = "discovery",
    input_root: Path = DEFAULT_INPUT_ROOT,
    split_plan: Path = DEFAULT_SPLIT_PLAN,
    reports_root: Path = DEFAULT_REPORTS_ROOT,
    costs_config: Path = DEFAULT_COSTS_CONFIG,
    target_registry: Path = DEFAULT_TARGET_REGISTRY,
    target_trial_statuses: Path = DEFAULT_TARGET_TRIAL_STATUSES,
    feature_cols_path: Path | None = None,
    fold_ids: Sequence[str] | None = None,
    top_fraction: float = DEFAULT_TOP_FRACTION,
    write_reports: bool = True,
) -> dict[str, Any]:
    if hypothesis_id not in TARGET_SPECS:
        raise SystemExit(f"unknown target hypothesis: {hypothesis_id}")
    if not 0.0 < top_fraction <= 1.0:
        raise SystemExit("--top-fraction must be in (0, 1]")
    spec = TARGET_SPECS[hypothesis_id]
    selected_fold_ids = stage_folds(stage, fold_ids)
    registry_failures = validate_target_hypothesis_registered(spec, target_registry, stage=stage)
    trial_status_failures = validate_target_trial_status_registered(spec, target_trial_statuses, stage=stage)
    cost_config = load_es_cost_config(costs_config)
    feature_cols, resolved_feature_cols = load_feature_cols(input_root, feature_cols_path)
    model_features = select_model_features(feature_cols)
    if not model_features:
        raise SystemExit("no non-leaking feature columns available")
    split_manifest = _read_json(split_plan)
    folds = _selected_folds(split_manifest, selected_fold_ids)
    years = [2023, 2024]
    frame, load_failures, matrix_paths = _load_market_frame(
        MARKET,
        years,
        input_root,
        _source_columns(model_features),
    )
    failures = [*registry_failures, *trial_status_failures, *load_failures]
    if frame is None:
        raise SystemExit("; ".join(failures) if failures else "no ES feature frame loaded")
    labeled = spec.apply(frame, cost_config, spec)
    events, skipped_overlap_count = non_overlapping_events(labeled, spec)
    fold_metrics: list[dict[str, Any]] = []
    top_rows: list[pd.DataFrame] = []
    if not events.empty:
        target = pd.to_numeric(events[spec.net_column], errors="coerce")
        for fold in folds:
            train_mask, test_mask = _fold_masks(events, fold, target)
            train = events.loc[train_mask].copy()
            test = events.loc[test_mask].copy()
            if train.empty or test.empty:
                failures.append(f"{fold['fold_id']}: empty train or test rows")
                continue
            if train["ts"].max() >= test["ts"].min():
                failures.append(f"{fold['fold_id']}: train/test timestamp overlap")
                continue
            metric, selected_top = _fold_metrics(
                fold=fold,
                train=train,
                test=test,
                features=model_features,
                spec=spec,
                top_fraction=top_fraction,
            )
            fold_metrics.append(metric)
            top_rows.append(selected_top)

    md_path, json_path = _report_paths(reports_root, run, hypothesis_id, stage)
    hash_paths = [target_registry, target_trial_statuses, split_plan, costs_config, resolved_feature_cols, *matrix_paths]
    report: dict[str, Any] = {
        "run": run,
        "hypothesis_id": hypothesis_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "stage": stage,
        "harness_type": "phase9_es_30m_target_construction_smoke_only",
        "evaluation_mode": spec.evaluation_mode,
        "not_wfa": True,
        "not_phase8": True,
        "uses_saved_predictions": False,
        "scope": {
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "markets": [MARKET],
            "years": years,
            "fold_ids": selected_fold_ids,
        },
        "input_paths": {
            "target_registry": _relative_path(target_registry),
            "target_trial_statuses": _relative_path(target_trial_statuses),
            "input_root": _relative_path(input_root),
            "split_plan": _relative_path(split_plan),
            "costs_config": _relative_path(costs_config),
            "feature_cols": _relative_path(resolved_feature_cols),
        },
        "input_hashes": _file_hash_map(hash_paths),
        "label_definition": {
            "description": spec.description,
            "entry": "next 1-minute open",
            "horizon_minutes": spec.horizon_bars,
            "threshold": spec.threshold_description,
            "validity": "same session segment, no synthetic/invalid/boundary/roll path, existing target/feature validity true",
        },
        "target_columns": spec.target_columns,
        "event_count": int(len(events)),
        "skipped_overlap_count": int(skipped_overlap_count),
        "class_balance": class_balance(events, spec) if not events.empty else {"event_count": 0, "counts": {}, "rates": {}},
        "target_distribution": target_distribution_summary(events, spec),
        "duplicate_target_overlap": duplicate_target_overlap(events, spec),
        "model": {
            "family": "ridge_component_regressions" if spec.evaluation_mode == EVALUATION_COMPONENT_RANK else "ridge_regression",
            "alpha": 1.0,
        },
        "model_feature_count": len(model_features),
        "top_fraction": float(top_fraction),
        "fold_metrics": fold_metrics,
        "stage_summary": stage_summary(fold_metrics, len(folds)),
        "failures": failures,
        "failure_count": len(failures),
        "report_paths": {"markdown": _relative_path(md_path), "json": _relative_path(json_path)},
    }
    gate_result = evaluate_stage_gates(report)
    report["decision"] = gate_result["decision"]
    report["gates"] = gate_result["gates"]
    if write_reports:
        reports_root.mkdir(parents=True, exist_ok=True)
        _write_json(json_path, report)
        md_path.write_text(_markdown_report(report), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypothesis-id", choices=sorted(TARGET_SPECS), required=True)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--stage", choices=["discovery", "confirmation", "locked"], default="discovery")
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT.as_posix())
    parser.add_argument("--split-plan", default=DEFAULT_SPLIT_PLAN.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--target-registry", default=DEFAULT_TARGET_REGISTRY.as_posix())
    parser.add_argument("--target-trial-statuses", default=DEFAULT_TARGET_TRIAL_STATUSES.as_posix())
    parser.add_argument("--feature-cols", default=None)
    parser.add_argument("--folds", default=None)
    parser.add_argument("--top-fraction", type=float, default=DEFAULT_TOP_FRACTION)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    report = run_harness(
        hypothesis_id=args.hypothesis_id,
        run=args.run,
        stage=args.stage,
        input_root=Path(args.input_root),
        split_plan=Path(args.split_plan),
        reports_root=Path(args.reports_root),
        costs_config=Path(args.costs_config),
        target_registry=Path(args.target_registry),
        target_trial_statuses=Path(args.target_trial_statuses),
        feature_cols_path=Path(args.feature_cols) if args.feature_cols else None,
        fold_ids=_parse_csv(args.folds),
        top_fraction=args.top_fraction,
        write_reports=True,
    )
    summary = report["stage_summary"]
    if report.get("evaluation_mode") == EVALUATION_COMPONENT_RANK:
        payload = {
            "run": report["run"],
            "hypothesis_id": report["hypothesis_id"],
            "stage": report["stage"],
            "decision": report["decision"],
            "top_avg_rank_score_uplift": summary["top_avg_rank_score_uplift"],
            "positive_rank_uplift_fold_count": summary["positive_rank_uplift_fold_count"],
            "failure_count": report["failure_count"],
            "report_paths": report["report_paths"],
        }
    else:
        payload = {
            "run": report["run"],
            "hypothesis_id": report["hypothesis_id"],
            "stage": report["stage"],
            "decision": report["decision"],
            "top_total_net_dollars": summary["top_total_net_dollars"],
            "positive_top_net_fold_count": summary["positive_top_net_fold_count"],
            "failure_count": report["failure_count"],
            "report_paths": report["report_paths"],
        }
    print(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if report["decision"] == "STOP_INPUT_FAILURE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
