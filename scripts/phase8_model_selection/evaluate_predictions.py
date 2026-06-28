#!/usr/bin/env python3
"""Evaluate saved WFA predictions with deterministic policy and cost diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
import yaml


DEFAULT_PREDICTIONS = Path("data") / "predictions" / "baseline" / "oos_predictions.parquet"
DEFAULT_PREDICTIONS_MANIFEST = Path("reports/wfa/baseline_predictions_manifest.json")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_MODELS_CONFIG = Path("configs/models.yaml")
DEFAULT_METRICS_ROOT = Path("reports/metrics")
DEFAULT_MODEL_SELECTION_ROOT = Path("reports/model_selection")
DEFAULT_PHASE8_ROOT = Path("reports/phase8")
DEFAULT_RUN = "baseline"
NO_CALIBRATION_ID = "no_calibration"
EXECUTION_POLICY_NAME = "max_one_contract_non_overlapping_target_window"
EXECUTION_REALISM = "research_non_overlapping_target_window_execution_policy"

POLICY_REQUIRED_TARGETS = {
    "expected_return": ("target_ret_15m", "y_pred_calibrated"),
    "direction": ("target_sign_with_deadzone", "p_long"),
    "fade": ("target_fade_success_15m", "p_fade_success"),
    "trend": ("target_trend_danger_30m", "p_trend_danger"),
}
PREDICTION_REQUIRED_COLUMNS = {
    "market",
    "year",
    "fold_id",
    "timestamp",
    "split_group",
    "model_id",
    "model_family",
    "target_name",
    "prediction_type",
    "y_true",
    "y_pred_raw",
    "y_pred_calibrated",
    "p_long",
    "p_short",
    "p_flat",
    "p_fade_success",
    "p_trend_danger",
    "calibration_id",
    "model_config_hash",
    "feature_config_hash",
    "execution_open",
    "execution_close",
    "target_valid",
}
PREDICTION_KEY_CANDIDATES = [
    "market",
    "year",
    "fold_id",
    "timestamp",
    "session_id",
    "session_segment_id",
    "split_group",
    "execution_open",
    "execution_close",
    "target_entry_ts",
    "target_exit_ts",
    "minutes_until_session_close",
]


@dataclass(frozen=True)
class PolicyConfig:
    long_short_margin: float
    min_fade_success: float
    max_trend_danger: float
    raw_return_prediction_direct_trading_allowed: bool = False
    p_trend_danger_blocks_fade_trades: bool = False
    p_fade_success_allows_fade_trades: bool = True


@dataclass(frozen=True)
class PromotionGateConfig:
    min_gross_return_dollars: float
    min_net_return_dollars: float
    min_net_sharpe_like: float
    max_cost_drag_to_abs_gross: float
    max_turnover_per_bar: float
    min_trade_count: int
    min_market_count: int = 2
    min_traded_market_count: int = 2
    min_fold_count: int = 4
    min_traded_fold_count: int = 4
    min_oos_span_days: float = 30.0
    max_single_market_trade_share: float = 0.75
    max_single_fold_trade_share: float = 0.50
    require_positive_net_all_markets: bool = True
    require_positive_net_all_folds: bool = True


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _read_bool_config(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return default


def load_policy_config(
    models_config: Path,
    *,
    long_short_margin: float,
    min_fade_success: float,
    max_trend_danger: float,
) -> PolicyConfig:
    models = _read_yaml(models_config)
    position_policy = models.get("position_policy", {})
    if not isinstance(position_policy, Mapping):
        position_policy = {}
    return PolicyConfig(
        long_short_margin=long_short_margin,
        min_fade_success=min_fade_success,
        max_trend_danger=max_trend_danger,
        raw_return_prediction_direct_trading_allowed=_read_bool_config(
            position_policy.get("raw_return_prediction_direct_trading_allowed"),
            False,
        ),
        p_trend_danger_blocks_fade_trades=_read_bool_config(
            position_policy.get("p_trend_danger_blocks_fade_trades"),
            False,
        ),
        p_fade_success_allows_fade_trades=_read_bool_config(
            position_policy.get("p_fade_success_allows_fade_trades"),
            True,
        ),
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return _safe_float(value)
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    return str(value)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, default=_json_default, allow_nan=False),
        encoding="utf-8",
    )


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_hash_or_missing(path: Path) -> str:
    return _file_sha256(path) if path.exists() else "MISSING"


def _file_hash_map(paths: Iterable[Path]) -> dict[str, str]:
    return {_relative_path(path): _file_hash_or_missing(path) for path in paths}


def _normalized_path(path: Path | str) -> str:
    raw = Path(path).expanduser()
    return raw.resolve().as_posix()


def _manifest_path(path_value: object) -> Path | None:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def _parquet_row_count(path: Path) -> int:
    import pyarrow.parquet as pq

    return int(pq.ParquetFile(path).metadata.num_rows)


def _manifest_hash_lookup(
    hashes: object,
    artifact_path: Path,
) -> tuple[str | None, bool]:
    if not isinstance(hashes, Mapping) or not hashes:
        return None, False
    expected = _normalized_path(artifact_path)
    for raw_path, raw_hash in hashes.items():
        if not isinstance(raw_path, str):
            continue
        if _normalized_path(raw_path) == expected:
            return str(raw_hash), True
    return None, True


def _scope_list(value: object, *, cast_type: type = str) -> list[Any] | None:
    if not isinstance(value, list):
        return None
    try:
        return sorted(cast_type(item) for item in value)
    except (TypeError, ValueError):
        return None


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sum_float(values: pd.Series) -> float:
    return float(pd.to_numeric(values, errors="coerce").fillna(0.0).sum())


def _mean_float(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return _safe_float(numeric.mean()) if not numeric.empty else None


def _std_float(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return _safe_float(numeric.std(ddof=0)) if len(numeric) > 1 else 0.0 if len(numeric) == 1 else None


def _sharpe_like(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if numeric.empty:
        return None
    std = float(numeric.std(ddof=0))
    if std <= 0.0:
        return None
    return float(numeric.mean() / std * math.sqrt(len(numeric)))


def _max_drawdown(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if numeric.empty:
        return None
    equity = numeric.cumsum()
    drawdown = equity - equity.cummax()
    return float(drawdown.min())


def _prediction_manifest_failures(
    manifest: Mapping[str, Any],
    *,
    predictions_path: Path,
    predictions: pd.DataFrame,
    run: str,
) -> list[str]:
    failures: list[str] = []
    if not manifest:
        failures.append("prediction manifest missing or unreadable")
        return failures
    if int(manifest.get("failure_count") or 0) > 0:
        failures.append("prediction manifest failure_count is nonzero")

    manifest_prediction_path = _manifest_path(manifest.get("prediction_path"))
    if manifest_prediction_path is None:
        failures.append("prediction manifest prediction_path missing")
    elif _normalized_path(manifest_prediction_path) != _normalized_path(predictions_path):
        failures.append(
            "prediction manifest prediction_path does not match CLI predictions path: "
            f"manifest={manifest_prediction_path.as_posix()} cli={predictions_path.as_posix()}"
        )

    if not predictions_path.exists():
        failures.append(f"prediction parquet missing: {_relative_path(predictions_path)}")
    output_hashes = manifest.get("output_file_hashes")
    actual_hash, hash_mapping_present = _manifest_hash_lookup(output_hashes, predictions_path)
    if not hash_mapping_present:
        failures.append("prediction manifest output_file_hashes missing")
    elif actual_hash is None:
        failures.append(
            "prediction manifest output_file_hashes missing prediction path: "
            f"{predictions_path.as_posix()}"
        )
    elif actual_hash in {"MISSING", "NOT_WRITTEN"}:
        failures.append(f"prediction manifest output hash is {actual_hash}")
    elif predictions_path.exists() and actual_hash != _file_sha256(predictions_path):
        failures.append("prediction manifest output hash does not match prediction parquet")

    if "prediction_count" not in manifest:
        failures.append("prediction manifest prediction_count missing")
    elif int(manifest.get("prediction_count") or 0) <= 0:
        failures.append("prediction manifest prediction_count is zero")
    elif predictions_path.exists() and int(manifest["prediction_count"]) != _parquet_row_count(predictions_path):
        failures.append("prediction manifest prediction_count does not match prediction parquet row count")

    if "stale_output_path_exists" not in manifest:
        failures.append("prediction manifest stale_output_path_exists missing")
    elif manifest.get("stale_output_path_exists") is True:
        failures.append("prediction manifest flags stale output")
    if "artifact_evidence_ready" not in manifest:
        failures.append("prediction manifest artifact_evidence_ready missing")
    elif manifest.get("artifact_evidence_ready") is not True:
        failures.append("prediction manifest artifact_evidence_ready is false")

    if manifest.get("run") != run:
        failures.append(
            f"prediction manifest run mismatch: manifest={manifest.get('run')!r} cli={run!r}"
        )

    profile = manifest.get("profile")
    resolved_profile = manifest.get("resolved_profile")
    split_profile = manifest.get("split_plan_profile")
    split_resolved_profile = manifest.get("split_plan_resolved_profile")
    for field, value in (
        ("profile", profile),
        ("resolved_profile", resolved_profile),
        ("split_plan_profile", split_profile),
        ("split_plan_resolved_profile", split_resolved_profile),
    ):
        if not isinstance(value, str) or not value:
            failures.append(f"prediction manifest {field} missing")
    if isinstance(profile, str) and isinstance(split_profile, str) and profile != split_profile:
        failures.append("prediction manifest profile does not match split-plan profile")
    if (
        isinstance(resolved_profile, str)
        and isinstance(split_resolved_profile, str)
        and resolved_profile != split_resolved_profile
    ):
        failures.append("prediction manifest resolved_profile does not match split-plan resolved_profile")

    manifest_markets = _scope_list(manifest.get("markets"), cast_type=str)
    manifest_years = _scope_list(manifest.get("years"), cast_type=int)
    prediction_markets = _scope_list(manifest.get("prediction_markets"), cast_type=str)
    prediction_years = _scope_list(manifest.get("prediction_years"), cast_type=int)
    if manifest_markets is None:
        failures.append("prediction manifest markets missing or invalid")
    if manifest_years is None:
        failures.append("prediction manifest years missing or invalid")
    if prediction_markets is None:
        failures.append("prediction manifest prediction_markets missing or invalid")
    if prediction_years is None:
        failures.append("prediction manifest prediction_years missing or invalid")
    if not predictions.empty and {"market", "year"} <= set(predictions.columns):
        actual_markets = sorted(predictions["market"].dropna().astype(str).unique().tolist())
        actual_years = sorted(int(year) for year in predictions["year"].dropna().unique())
        if prediction_markets is not None and actual_markets != prediction_markets:
            failures.append("prediction manifest prediction_markets do not match prediction parquet")
        if prediction_years is not None and actual_years != prediction_years:
            failures.append("prediction manifest prediction_years do not match prediction parquet")
        if manifest_markets is not None and not set(actual_markets).issubset(set(manifest_markets)):
            failures.append("prediction parquet markets are outside manifest markets")
        if manifest_years is not None and not set(actual_years).issubset(set(manifest_years)):
            failures.append("prediction parquet years are outside manifest years")

    split_plan_path = _manifest_path(manifest.get("split_plan_path"))
    if split_plan_path is None:
        failures.append("prediction manifest split_plan_path missing")
    elif not split_plan_path.exists():
        failures.append(f"prediction manifest split_plan_path missing file: {split_plan_path.as_posix()}")
    split_plan_hash = manifest.get("split_plan_hash")
    if not isinstance(split_plan_hash, str) or not split_plan_hash:
        failures.append("prediction manifest split_plan_hash missing")
    elif split_plan_path is not None and split_plan_path.exists() and split_plan_hash != _file_sha256(split_plan_path):
        failures.append("prediction manifest split_plan_hash does not match current split plan")
    input_hash, input_hash_mapping_present = _manifest_hash_lookup(
        manifest.get("input_file_hashes"),
        split_plan_path or Path("__missing_split_plan__"),
    )
    if not input_hash_mapping_present:
        failures.append("prediction manifest input_file_hashes missing")
    elif input_hash is None:
        failures.append("prediction manifest input_file_hashes missing split plan path")
    elif isinstance(split_plan_hash, str) and input_hash != split_plan_hash:
        failures.append("prediction manifest split_plan_hash does not match input_file_hashes")
    if not isinstance(manifest.get("split_plan_config_hash"), str) or not manifest.get("split_plan_config_hash"):
        failures.append("prediction manifest split_plan_config_hash missing")
    return failures


def _load_cost_markets(costs_config: Path) -> tuple[dict[str, Mapping[str, Any]], dict[str, Any]]:
    config = _read_yaml(costs_config)
    markets = config.get("markets", {})
    if not isinstance(markets, Mapping):
        return {}, config
    return {str(key): value for key, value in markets.items() if isinstance(value, Mapping)}, config


def _validate_prediction_columns(predictions: pd.DataFrame) -> list[str]:
    missing = sorted(PREDICTION_REQUIRED_COLUMNS - set(predictions.columns))
    return [f"prediction parquet missing required columns: {missing}"] if missing else []


def _first_non_null(frame: pd.DataFrame, key_cols: list[str], value_cols: list[str]) -> pd.DataFrame:
    available = key_cols + [col for col in value_cols if col in frame.columns]
    subset = frame[available].copy()
    return subset.groupby(key_cols, dropna=False, as_index=False).first()


def _apply_non_overlapping_execution_policy(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    out = frame.copy()
    failures: list[str] = []
    out["target_entry_ts"] = pd.to_datetime(
        out["target_entry_ts"] if "target_entry_ts" in out.columns else pd.NaT,
        errors="coerce",
        utc=True,
    )
    out["target_exit_ts"] = pd.to_datetime(
        out["target_exit_ts"] if "target_exit_ts" in out.columns else pd.NaT,
        errors="coerce",
        utc=True,
    )
    out["execution_policy"] = EXECUTION_POLICY_NAME
    out["blocked_by_execution_overlap"] = False
    out["execution_run_id"] = None
    out["position"] = 0

    candidate_trades = out["candidate_position"].ne(0)
    missing_windows = candidate_trades & (
        out["target_entry_ts"].isna() | out["target_exit_ts"].isna()
    )
    if bool(missing_windows.any()):
        failures.append(
            "policy executable signals missing target_entry_ts/target_exit_ts: "
            f"{int(missing_windows.sum())}"
        )
    inverted_windows = candidate_trades & out["target_exit_ts"].lt(out["target_entry_ts"])
    if bool(inverted_windows.any()):
        failures.append(
            "policy executable signals with target_exit_ts before target_entry_ts: "
            f"{int(inverted_windows.sum())}"
        )
    if failures:
        return out, failures

    sort_cols = [
        column
        for column in ("market", "fold_id", "target_entry_ts", "timestamp")
        if column in out.columns
    ]
    out = out.sort_values(sort_cols).reset_index(drop=True)
    group_cols = [column for column in ("market", "fold_id") if column in out.columns]
    for keys, group in out.groupby(group_cols, dropna=False, sort=False):
        last_exit: pd.Timestamp | None = None
        run_number = 0
        key_text = "|".join(str(item) for item in (keys if isinstance(keys, tuple) else (keys,)))
        for index, row in group.iterrows():
            candidate_position = int(row["candidate_position"])
            if candidate_position == 0:
                continue
            entry_ts = row["target_entry_ts"]
            exit_ts = row["target_exit_ts"]
            if last_exit is not None and entry_ts < last_exit:
                out.at[index, "blocked_by_execution_overlap"] = True
                out.at[index, "policy_reason"] = "execution_overlap_block"
                continue
            run_number += 1
            out.at[index, "position"] = candidate_position
            out.at[index, "execution_run_id"] = f"{key_text}|exec_{run_number:06d}"
            last_exit = exit_ts
    return out, failures


def build_policy_frame(
    predictions: pd.DataFrame,
    costs_config: Path,
    policy: PolicyConfig,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    costs_by_market, _ = _load_cost_markets(costs_config)
    key_cols = [column for column in PREDICTION_KEY_CANDIDATES if column in predictions.columns]
    base = predictions[key_cols].drop_duplicates().copy()
    if base.empty:
        return base, ["no prediction rows available for policy evaluation"], warnings

    expected_target, _ = POLICY_REQUIRED_TARGETS["expected_return"]
    expected = predictions[predictions["target_name"] == expected_target]
    if expected.empty:
        failures.append(f"missing policy target predictions: {expected_target}")
    else:
        expected_values = _first_non_null(expected, key_cols, ["y_pred_calibrated", "y_true"])
        expected_values = expected_values.rename(
            columns={
                "y_pred_calibrated": "expected_return",
                "y_true": "observed_return_target",
            }
        )
        base = base.merge(expected_values, on=key_cols, how="left")

    direction_target, _ = POLICY_REQUIRED_TARGETS["direction"]
    direction = predictions[predictions["target_name"] == direction_target]
    if direction.empty:
        failures.append(f"missing policy target predictions: {direction_target}")
    else:
        direction_values = _first_non_null(
            direction,
            key_cols,
            ["p_long", "p_short", "p_flat", "y_true"],
        )
        direction_values = direction_values.rename(columns={"y_true": "observed_direction_target"})
        base = base.merge(direction_values, on=key_cols, how="left")

    fade_target, _ = POLICY_REQUIRED_TARGETS["fade"]
    fade = predictions[predictions["target_name"] == fade_target]
    if fade.empty:
        failures.append(f"missing policy target predictions: {fade_target}")
    else:
        fade_values = _first_non_null(fade, key_cols, ["p_fade_success", "y_true"])
        fade_values = fade_values.rename(columns={"y_true": "observed_fade_success_target"})
        base = base.merge(fade_values, on=key_cols, how="left")

    trend_target, _ = POLICY_REQUIRED_TARGETS["trend"]
    trend = predictions[predictions["target_name"] == trend_target]
    if trend.empty:
        failures.append(f"missing policy target predictions: {trend_target}")
    else:
        trend_values = _first_non_null(trend, key_cols, ["p_trend_danger", "y_true"])
        trend_values = trend_values.rename(columns={"y_true": "observed_trend_danger_target"})
        base = base.merge(trend_values, on=key_cols, how="left")

    if failures:
        return base, failures, warnings

    for column in (
        "execution_open",
        "execution_close",
        "p_long",
        "p_short",
        "p_flat",
        "p_fade_success",
        "p_trend_danger",
        "expected_return",
    ):
        base[column] = pd.to_numeric(base[column], errors="coerce")

    missing_prices = base["execution_open"].isna() | base["execution_close"].isna()
    if bool(missing_prices.any()):
        failures.append(f"policy rows with missing execution prices: {int(missing_prices.sum())}")

    base["direction_margin"] = base["p_long"] - base["p_short"]
    base["direction_signal"] = 0
    base.loc[base["direction_margin"] >= policy.long_short_margin, "direction_signal"] = 1
    base.loc[base["direction_margin"] <= -policy.long_short_margin, "direction_signal"] = -1
    base["base_position"] = base["direction_signal"].astype(int)
    base["direction_probability"] = np.where(
        base["base_position"].eq(1),
        base["p_long"],
        np.where(base["base_position"].eq(-1), base["p_short"], np.nan),
    )
    base["direction_beats_flat"] = base["direction_probability"] > base["p_flat"]
    base["fade_allowed"] = base["p_fade_success"].ge(policy.min_fade_success).fillna(False)
    trend_danger_condition = base["p_trend_danger"].isna() | base["p_trend_danger"].ge(
        policy.max_trend_danger
    )
    base["trend_danger_block"] = (
        trend_danger_condition if policy.p_trend_danger_blocks_fade_trades else False
    )
    base["no_direction_signal"] = base["base_position"].eq(0)
    base["blocked_by_flat_probability"] = (
        base["base_position"].ne(0) & ~base["direction_beats_flat"].fillna(False)
    )
    base["blocked_by_fade_filter"] = base["base_position"].ne(0) & ~base["fade_allowed"]
    base["blocked_by_trend_danger"] = base["base_position"].ne(0) & base["trend_danger_block"]
    base["candidate_position"] = np.where(
        base["direction_beats_flat"].fillna(False)
        & base["fade_allowed"]
        & ~base["trend_danger_block"],
        base["base_position"],
        0,
    ).astype(int)
    base["candidate_trade_count"] = base["candidate_position"].ne(0).astype(int)
    base["policy_reason"] = "trade"
    base.loc[base["base_position"].eq(0), "policy_reason"] = "no_direction_edge"
    base.loc[base["blocked_by_fade_filter"], "policy_reason"] = "fade_filter_block"
    base.loc[base["blocked_by_trend_danger"], "policy_reason"] = "trend_danger_block"
    base.loc[base["blocked_by_flat_probability"], "policy_reason"] = "flat_probability_block"

    point_values: dict[str, float] = {}
    round_turn_costs: dict[str, float] = {}
    tick_values: dict[str, float] = {}
    slippage_ticks: dict[str, float] = {}
    missing_cost_markets: list[str] = []
    for market in sorted(str(value) for value in base["market"].dropna().unique()):
        market_costs = costs_by_market.get(market)
        point_value = _safe_float(market_costs.get("point_value") if market_costs else None)
        round_turn = _safe_float(
            market_costs.get("round_turn_cost_dollars") if market_costs else None
        )
        tick_value = _safe_float(market_costs.get("tick_value") if market_costs else None)
        slippage = _safe_float(
            market_costs.get("slippage_ticks_per_side") if market_costs else None
        )
        if point_value is None or round_turn is None:
            missing_cost_markets.append(market)
            continue
        point_values[market] = point_value
        round_turn_costs[market] = round_turn
        if tick_value is not None:
            tick_values[market] = tick_value
        if slippage is not None:
            slippage_ticks[market] = slippage
    if missing_cost_markets:
        failures.append(f"missing usable costs for markets: {missing_cost_markets}")

    base["point_value"] = base["market"].map(point_values)
    base["round_turn_cost_dollars"] = base["market"].map(round_turn_costs)
    base["tick_value"] = base["market"].map(tick_values)
    base["slippage_ticks_per_side"] = base["market"].map(slippage_ticks).fillna(0.0)
    base["price_move"] = base["execution_close"] - base["execution_open"]
    base["candidate_gross_dollars"] = (
        base["candidate_position"] * base["price_move"] * base["point_value"]
    )
    base["candidate_cost_dollars"] = np.where(
        base["candidate_position"].ne(0),
        base["round_turn_cost_dollars"],
        0.0,
    )
    base["candidate_net_dollars"] = base["candidate_gross_dollars"] - base["candidate_cost_dollars"]

    base, execution_failures = _apply_non_overlapping_execution_policy(base)
    failures.extend(execution_failures)

    base["gross_dollars"] = base["position"] * base["price_move"] * base["point_value"]
    base["cost_dollars"] = np.where(base["position"].ne(0), base["round_turn_cost_dollars"], 0.0)
    base["slippage_cost_dollars"] = np.where(
        base["position"].ne(0),
        2.0 * base["slippage_ticks_per_side"] * base["tick_value"].fillna(0.0),
        0.0,
    )
    base["commission_cost_dollars"] = np.maximum(
        base["cost_dollars"] - base["slippage_cost_dollars"],
        0.0,
    )
    base["net_dollars"] = base["gross_dollars"] - base["cost_dollars"]
    base["trade_count"] = base["position"].ne(0).astype(int)
    base["long_count"] = base["position"].eq(1).astype(int)
    base["short_count"] = base["position"].eq(-1).astype(int)
    base["flat_count"] = base["position"].eq(0).astype(int)

    sort_cols = [column for column in ("market", "fold_id", "timestamp") if column in base.columns]
    base = base.sort_values(sort_cols).reset_index(drop=True)
    group_cols = [column for column in ("market", "fold_id") if column in base.columns]
    previous_position = base.groupby(group_cols, dropna=False)["position"].shift(1).fillna(0)
    base["position_change_abs"] = (base["position"] - previous_position).abs()
    base["round_turns_per_bar"] = base["trade_count"].astype(float)
    warnings.append(
        "policy economics use max-one-contract non-overlapping target-window execution; "
        "partial fills, order rejection, latency, and capacity remain outside Phase 8"
    )
    return base, failures, warnings


def _policy_summary(frame: pd.DataFrame, scope: str, key_values: Mapping[str, Any]) -> dict[str, Any]:
    rows = int(len(frame))
    timestamps = (
        pd.to_datetime(frame["timestamp"], utc=True, errors="coerce").dropna()
        if "timestamp" in frame
        else pd.Series(dtype="datetime64[ns, UTC]")
    )
    first_timestamp = timestamps.min() if not timestamps.empty else None
    last_timestamp = timestamps.max() if not timestamps.empty else None
    oos_span_days = (
        float((last_timestamp - first_timestamp).total_seconds() / 86400.0)
        if first_timestamp is not None and last_timestamp is not None
        else None
    )
    gross = _sum_float(frame["gross_dollars"]) if "gross_dollars" in frame else 0.0
    cost = _sum_float(frame["cost_dollars"]) if "cost_dollars" in frame else 0.0
    net = _sum_float(frame["net_dollars"]) if "net_dollars" in frame else 0.0
    position_changes = (
        float(frame["position_change_abs"].sum()) if "position_change_abs" in frame else 0.0
    )
    trade_count = int(frame["trade_count"].sum()) if "trade_count" in frame else 0
    candidate_trade_count = (
        int(frame["candidate_trade_count"].sum()) if "candidate_trade_count" in frame else trade_count
    )
    winning_trades = frame.loc[frame["trade_count"].eq(1), "net_dollars"] if trade_count else pd.Series(dtype=float)
    return {
        "scope": scope,
        **dict(key_values),
        "row_count": rows,
        "trade_count": trade_count,
        "candidate_trade_count": candidate_trade_count,
        "blocked_by_execution_overlap": int(frame["blocked_by_execution_overlap"].sum())
        if "blocked_by_execution_overlap" in frame
        else 0,
        "long_count": int(frame["long_count"].sum()) if "long_count" in frame else 0,
        "short_count": int(frame["short_count"].sum()) if "short_count" in frame else 0,
        "flat_count": int(frame["flat_count"].sum()) if "flat_count" in frame else rows,
        "first_timestamp": first_timestamp.isoformat() if first_timestamp is not None else None,
        "last_timestamp": last_timestamp.isoformat() if last_timestamp is not None else None,
        "oos_span_days": oos_span_days,
        "gross_return_dollars": gross,
        "cost_dollars": cost,
        "net_return_dollars": net,
        "avg_gross_dollars_per_row": _mean_float(frame["gross_dollars"]) if "gross_dollars" in frame else None,
        "avg_net_dollars_per_row": _mean_float(frame["net_dollars"]) if "net_dollars" in frame else None,
        "gross_sharpe_like": _sharpe_like(frame["gross_dollars"]) if "gross_dollars" in frame else None,
        "net_sharpe_like": _sharpe_like(frame["net_dollars"]) if "net_dollars" in frame else None,
        "max_drawdown_dollars": _max_drawdown(frame["net_dollars"]) if "net_dollars" in frame else None,
        "cost_drag_to_abs_gross": cost / abs(gross) if abs(gross) > 0.0 else None,
        "turnover_per_bar": (
            position_changes / rows if rows and "position_change_abs" in frame else None
        ),
        "position_change_abs_sum": position_changes,
        "slippage_cost_dollars": _sum_float(frame["slippage_cost_dollars"])
        if "slippage_cost_dollars" in frame
        else 0.0,
        "commission_cost_dollars": _sum_float(frame["commission_cost_dollars"])
        if "commission_cost_dollars" in frame
        else 0.0,
        "round_turns_per_bar": float(trade_count) / rows if rows else None,
        "win_rate_net_positive": (
            float(winning_trades.gt(0.0).mean()) if trade_count and not winning_trades.empty else None
        ),
        "blocked_by_fade_filter": int(frame["blocked_by_fade_filter"].sum())
        if "blocked_by_fade_filter" in frame
        else 0,
        "blocked_by_flat_probability": int(frame["blocked_by_flat_probability"].sum())
        if "blocked_by_flat_probability" in frame
        else 0,
        "blocked_by_trend_danger": int(frame["blocked_by_trend_danger"].sum())
        if "blocked_by_trend_danger" in frame
        else 0,
        "no_direction_signal": int(frame["no_direction_signal"].sum())
        if "no_direction_signal" in frame
        else 0,
    }


def build_policy_metrics(policy_frame: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    summaries: list[dict[str, Any]] = []
    if not policy_frame.empty and "gross_dollars" in policy_frame.columns:
        summaries.append(_policy_summary(policy_frame, "overall", {}))
        for market, group in policy_frame.groupby("market", dropna=False):
            summaries.append(_policy_summary(group, "market", {"market": market}))
        for fold_id, group in policy_frame.groupby("fold_id", dropna=False):
            summaries.append(_policy_summary(group, "fold", {"fold_id": fold_id}))
        for (market, fold_id), group in policy_frame.groupby(["market", "fold_id"], dropna=False):
            summaries.append(
                _policy_summary(group, "market_fold", {"market": market, "fold_id": fold_id})
            )
        for reason, group in policy_frame.groupby("policy_reason", dropna=False):
            summaries.append(_policy_summary(group, "policy_reason", {"policy_reason": reason}))

    summary_frame = pd.DataFrame(summaries)
    group_cols = ["market", "fold_id"]
    turnover_records: list[dict[str, Any]] = []
    if not policy_frame.empty and "position_change_abs" in policy_frame.columns:
        for (market, fold_id), group in policy_frame.groupby(group_cols, dropna=False):
            rows = int(len(group))
            turnover_records.append(
                {
                    "market": market,
                    "fold_id": fold_id,
                    "row_count": rows,
                    "trade_count": int(group["trade_count"].sum()),
                    "position_change_abs_sum": float(group["position_change_abs"].sum()),
                    "turnover_per_bar": float(group["position_change_abs"].sum()) / rows
                    if rows
                    else None,
                    "round_turns_per_bar": float(group["trade_count"].sum()) / rows if rows else None,
                    "average_abs_position": float(group["position"].abs().mean()) if rows else None,
                }
            )
    turnover_frame = pd.DataFrame(turnover_records)
    overall = summaries[0] if summaries else _policy_summary(policy_frame, "overall", {})
    return {"overall": overall, "summaries": summaries}, summary_frame, turnover_frame


def evaluate_promotion_gate(
    policy_metrics: Mapping[str, Any],
    gate_config: PromotionGateConfig,
) -> dict[str, Any]:
    overall = policy_metrics.get("overall", {})
    summaries = policy_metrics.get("summaries", [])
    blockers: list[str] = []

    gross_return = _safe_float(overall.get("gross_return_dollars"))
    if gross_return is None or gross_return < gate_config.min_gross_return_dollars:
        blockers.append(
            f"gross_return_dollars {gross_return} below minimum "
            f"{gate_config.min_gross_return_dollars}"
        )

    net_return = _safe_float(overall.get("net_return_dollars"))
    if net_return is None or net_return < gate_config.min_net_return_dollars:
        blockers.append(
            f"net_return_dollars {net_return} below minimum {gate_config.min_net_return_dollars}"
        )

    net_sharpe = _safe_float(overall.get("net_sharpe_like"))
    if net_sharpe is None or net_sharpe < gate_config.min_net_sharpe_like:
        blockers.append(
            f"net_sharpe_like {net_sharpe} below minimum {gate_config.min_net_sharpe_like}"
        )

    cost_drag = _safe_float(overall.get("cost_drag_to_abs_gross"))
    if cost_drag is None or cost_drag > gate_config.max_cost_drag_to_abs_gross:
        blockers.append(
            f"cost_drag_to_abs_gross {cost_drag} above maximum "
            f"{gate_config.max_cost_drag_to_abs_gross}"
        )

    turnover = _safe_float(overall.get("turnover_per_bar"))
    if turnover is None or turnover > gate_config.max_turnover_per_bar:
        blockers.append(
            f"turnover_per_bar {turnover} above maximum {gate_config.max_turnover_per_bar}"
        )

    trade_count = _safe_int(overall.get("trade_count")) or 0
    if trade_count < gate_config.min_trade_count:
        blockers.append(f"trade_count {trade_count} below minimum {gate_config.min_trade_count}")

    oos_span_days = _safe_float(overall.get("oos_span_days"))
    if oos_span_days is None or oos_span_days < gate_config.min_oos_span_days:
        blockers.append(
            f"oos_span_days {oos_span_days} below minimum {gate_config.min_oos_span_days}"
        )

    if isinstance(summaries, list):
        market_summaries = [
            item
            for item in summaries
            if isinstance(item, Mapping) and item.get("scope") == "market"
        ]
        fold_summaries = [
            item for item in summaries if isinstance(item, Mapping) and item.get("scope") == "fold"
        ]
        market_count = len(market_summaries)
        if market_count < gate_config.min_market_count:
            blockers.append(
                f"market_count {market_count} below minimum {gate_config.min_market_count}"
            )
        traded_markets = [
            item for item in market_summaries if (_safe_int(item.get("trade_count")) or 0) > 0
        ]
        if len(traded_markets) < gate_config.min_traded_market_count:
            blockers.append(
                f"traded_market_count {len(traded_markets)} below minimum "
                f"{gate_config.min_traded_market_count}"
            )
        market_trade_counts = [
            _safe_int(item.get("trade_count")) or 0 for item in market_summaries
        ]
        market_trade_total = sum(market_trade_counts)
        if market_trade_total > 0:
            max_market_share = max(market_trade_counts) / market_trade_total
            if max_market_share > gate_config.max_single_market_trade_share:
                blockers.append(
                    f"single_market_trade_share {max_market_share} above maximum "
                    f"{gate_config.max_single_market_trade_share}"
                )

        fold_count = len(fold_summaries)
        if fold_count < gate_config.min_fold_count:
            blockers.append(f"fold_count {fold_count} below minimum {gate_config.min_fold_count}")
        traded_folds = [
            item for item in fold_summaries if (_safe_int(item.get("trade_count")) or 0) > 0
        ]
        if len(traded_folds) < gate_config.min_traded_fold_count:
            blockers.append(
                f"traded_fold_count {len(traded_folds)} below minimum "
                f"{gate_config.min_traded_fold_count}"
            )
        fold_trade_counts = [_safe_int(item.get("trade_count")) or 0 for item in fold_summaries]
        fold_trade_total = sum(fold_trade_counts)
        if fold_trade_total > 0:
            max_fold_share = max(fold_trade_counts) / fold_trade_total
            if max_fold_share > gate_config.max_single_fold_trade_share:
                blockers.append(
                    f"single_fold_trade_share {max_fold_share} above maximum "
                    f"{gate_config.max_single_fold_trade_share}"
                )

        if gate_config.require_positive_net_all_markets:
            bad_markets = sorted(
                str(item.get("market"))
                for item in market_summaries
                if (_safe_float(item.get("net_return_dollars")) or 0.0) <= 0.0
            )
            if bad_markets:
                blockers.append(f"nonpositive net_return_dollars for markets: {bad_markets}")
        if gate_config.require_positive_net_all_folds:
            bad_folds = sorted(
                str(item.get("fold_id"))
                for item in fold_summaries
                if (_safe_float(item.get("net_return_dollars")) or 0.0) <= 0.0
            )
            if bad_folds:
                blockers.append(f"nonpositive net_return_dollars for folds: {bad_folds}")

    return {
        "gate_name": "research_alpha_promotion_gate",
        "gate_config": asdict(gate_config),
        "research_alpha_ready": not blockers,
        "model_promotion_allowed": not blockers,
        "promotion_blocker_count": len(blockers),
        "promotion_blockers": blockers,
    }


def _score_column_for_target(frame: pd.DataFrame, target_name: str) -> pd.Series:
    if target_name == "target_fade_success_15m":
        return pd.to_numeric(frame["p_fade_success"], errors="coerce")
    if target_name == "target_trend_danger_30m":
        return pd.to_numeric(frame["p_trend_danger"], errors="coerce")
    if target_name == "target_sign_with_deadzone":
        p_long = pd.to_numeric(frame["p_long"], errors="coerce").fillna(0.0)
        p_short = pd.to_numeric(frame["p_short"], errors="coerce").fillna(0.0)
        return p_long - p_short
    return pd.to_numeric(frame["y_pred_calibrated"], errors="coerce")


def _direction_accuracy(frame: pd.DataFrame) -> float | None:
    p_long = pd.to_numeric(frame["p_long"], errors="coerce")
    p_short = pd.to_numeric(frame["p_short"], errors="coerce")
    p_flat = pd.to_numeric(frame["p_flat"], errors="coerce")
    if p_long.isna().all() or p_short.isna().all() or p_flat.isna().all():
        return None
    stacked = np.vstack(
        [
            p_short.fillna(-np.inf).to_numpy(),
            p_flat.fillna(-np.inf).to_numpy(),
            p_long.fillna(-np.inf).to_numpy(),
        ]
    ).T
    classes = np.array([-1, 0, 1])
    predicted = classes[np.argmax(stacked, axis=1)]
    actual = pd.to_numeric(frame["y_true"], errors="coerce").to_numpy()
    mask = np.isfinite(actual)
    if not bool(mask.any()):
        return None
    return float((predicted[mask] == actual[mask]).mean())


def build_model_comparison(predictions: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    group_cols = ["model_id", "model_family", "target_name", "market", "fold_id"]
    for keys, group in predictions.groupby(group_cols, dropna=False):
        model_id, model_family, target_name, market, fold_id = keys
        y_true = pd.to_numeric(group["y_true"], errors="coerce")
        score = _score_column_for_target(group, str(target_name))
        record: dict[str, Any] = {
            "model_id": model_id,
            "model_family": model_family,
            "target_name": target_name,
            "market": market,
            "fold_id": fold_id,
            "row_count": int(len(group)),
            "prediction_type": group["prediction_type"].dropna().astype(str).iloc[0]
            if group["prediction_type"].notna().any()
            else None,
            "prediction_mean": _mean_float(score),
            "prediction_std": _std_float(score),
            "target_mean": _mean_float(y_true),
            "target_std": _std_float(y_true),
            "model_config_hash": group["model_config_hash"].dropna().astype(str).iloc[0]
            if group["model_config_hash"].notna().any()
            else None,
            "feature_config_hash": group["feature_config_hash"].dropna().astype(str).iloc[0]
            if group["feature_config_hash"].notna().any()
            else None,
            "calibration_ids": ",".join(sorted(group["calibration_id"].dropna().astype(str).unique())),
        }
        aligned = pd.DataFrame({"y_true": y_true, "score": score}).dropna()
        if not aligned.empty:
            errors = aligned["score"] - aligned["y_true"]
            record["mse"] = float(np.mean(np.square(errors)))
            record["mae"] = float(np.mean(np.abs(errors)))
            target_values = set(aligned["y_true"].unique().tolist())
            if target_values.issubset({0, 1}) and aligned["score"].between(0.0, 1.0).all():
                record["brier_score"] = float(np.mean(np.square(errors)))
        if target_name == "target_sign_with_deadzone":
            record["direction_accuracy"] = _direction_accuracy(group)
        records.append(record)
    return pd.DataFrame(records).sort_values(group_cols).reset_index(drop=True)


def build_calibration_report(predictions: pd.DataFrame, models_config: dict[str, Any]) -> dict[str, Any]:
    calibration = models_config.get("calibration", {})
    if not isinstance(calibration, Mapping):
        calibration = {}
    calibration_ids = sorted(predictions["calibration_id"].dropna().astype(str).unique())
    status = (
        "NO_CALIBRATION_APPLIED"
        if calibration_ids == [calibration.get("no_calibration_marker", NO_CALIBRATION_ID)]
        else "MIXED_OR_EXTERNAL_CALIBRATION_IDS"
    )
    curves: list[dict[str, Any]] = []
    for target_name in ("target_fade_success_15m", "target_trend_danger_30m"):
        target_frame = predictions[predictions["target_name"] == target_name].copy()
        if target_frame.empty:
            continue
        target_frame["score"] = _score_column_for_target(target_frame, target_name)
        target_frame["actual"] = pd.to_numeric(target_frame["y_true"], errors="coerce")
        target_frame = target_frame.dropna(subset=["score", "actual"])
        if target_frame.empty:
            continue
        target_frame["bin"] = pd.cut(
            target_frame["score"].clip(0.0, 1.0),
            bins=np.linspace(0.0, 1.0, 11),
            include_lowest=True,
        )
        for (market, fold_id, bin_value), group in target_frame.groupby(
            ["market", "fold_id", "bin"],
            dropna=False,
            observed=False,
        ):
            if group.empty:
                continue
            curves.append(
                {
                    "target_name": target_name,
                    "market": market,
                    "fold_id": fold_id,
                    "score_bin": str(bin_value),
                    "row_count": int(len(group)),
                    "mean_score": _mean_float(group["score"]),
                    "observed_rate": _mean_float(group["actual"]),
                }
            )
    return {
        "status": status,
        "calibration_ids": calibration_ids,
        "no_calibration_marker": calibration.get("no_calibration_marker", NO_CALIBRATION_ID),
        "test_fold_fit_allowed": calibration.get("test_fold_fit_allowed", False),
        "final_holdout_fit_allowed": calibration.get("final_holdout_fit_allowed", False),
        "preserve_raw_and_calibrated_scores": calibration.get(
            "preserve_raw_and_calibrated_scores", True
        ),
        "calibration_curve_count": len(curves),
        "calibration_curves": curves,
    }


def evaluate_predictions(
    *,
    predictions_path: Path,
    predictions_manifest: Path | None,
    costs_config: Path,
    models_config: Path,
    metrics_root: Path,
    model_selection_root: Path,
    run: str,
    policy: PolicyConfig,
    promotion_gate: PromotionGateConfig,
    phase8_root: Path | None = None,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    resolved_phase8_root = phase8_root or metrics_root.parent / "phase8"
    failures: list[str] = []
    warnings: list[str] = []
    models = _read_yaml(models_config)
    manifest = _read_json(predictions_manifest) if predictions_manifest else {}
    if not predictions_path.exists():
        failures.append(f"prediction parquet missing: {_relative_path(predictions_path)}")
        predictions = pd.DataFrame()
    else:
        predictions = pd.read_parquet(predictions_path)
        failures.extend(_validate_prediction_columns(predictions))
    manifest_failures = (
        _prediction_manifest_failures(
            manifest,
            predictions_path=predictions_path,
            predictions=predictions,
            run=run,
        )
        if predictions_manifest
        else ["prediction manifest required"]
    )
    failures.extend(manifest_failures)
    final_holdout_touched = (
        "split_group" in predictions.columns
        and predictions["split_group"].astype(str).eq("final_holdout").any()
    )
    if final_holdout_touched:
        failures.append("final_holdout predictions cannot be used for Phase 8 selection or calibration")

    if failures:
        policy_frame = pd.DataFrame()
        policy_metrics, summary_frame, turnover_frame = build_policy_metrics(policy_frame)
        model_comparison = pd.DataFrame()
        calibration_report = build_calibration_report(predictions, models) if not predictions.empty else {}
    else:
        policy_frame, policy_failures, policy_warnings = build_policy_frame(
            predictions,
            costs_config,
            policy,
        )
        failures.extend(policy_failures)
        warnings.extend(policy_warnings)
        policy_metrics, summary_frame, turnover_frame = build_policy_metrics(policy_frame)
        model_comparison = build_model_comparison(predictions)
        calibration_report = build_calibration_report(predictions, models)
    promotion_gate_report = evaluate_promotion_gate(policy_metrics, promotion_gate)
    if failures:
        promotion_gate_report["research_alpha_ready"] = False
        promotion_gate_report["model_promotion_allowed"] = False
        promotion_gate_report["promotion_blockers"] = [
            "structural evaluation failures must be resolved before model promotion",
            *promotion_gate_report["promotion_blockers"],
        ]
        promotion_gate_report["promotion_blocker_count"] = len(
            promotion_gate_report["promotion_blockers"]
        )

    metrics_root.mkdir(parents=True, exist_ok=True)
    model_selection_root.mkdir(parents=True, exist_ok=True)
    resolved_phase8_root.mkdir(parents=True, exist_ok=True)
    metrics_json_path = metrics_root / f"{run}_metrics.json"
    metrics_csv_path = metrics_root / f"{run}_metrics.csv"
    turnover_path = metrics_root / "turnover_diagnostics.csv"
    model_comparison_path = model_selection_root / "model_comparison.csv"
    model_selection_report_path = model_selection_root / "model_selection_report.json"
    calibration_report_path = model_selection_root / "calibration_report.json"
    phase8_metrics_path = resolved_phase8_root / "metrics.json"
    alpha_decision_path = resolved_phase8_root / "alpha_promotion_decision.json"

    if not summary_frame.empty:
        summary_frame.to_csv(metrics_csv_path, index=False)
    else:
        pd.DataFrame([_policy_summary(pd.DataFrame(), "overall", {})]).to_csv(
            metrics_csv_path,
            index=False,
        )
    turnover_frame.to_csv(turnover_path, index=False)
    model_comparison.to_csv(model_comparison_path, index=False)

    policy_report = {
        "generated_at": generated_at,
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "run": run,
        "input_root": _relative_path(predictions_path.parent),
        "output_root": _relative_path(metrics_root),
        "prediction_path": _relative_path(predictions_path),
        "predictions_manifest_path": _relative_path(predictions_manifest)
        if predictions_manifest
        else None,
        "costs_config": _relative_path(costs_config),
        "models_config": _relative_path(models_config),
        "input_file_hashes": _file_hash_map(
            [path for path in (predictions_path, costs_config, models_config) if path is not None]
        ),
        "prediction_manifest_hash": _file_hash_or_missing(predictions_manifest)
        if predictions_manifest
        else None,
        "policy_config": asdict(policy),
        "prediction_count": int(len(predictions)),
        "policy_row_count": int(policy_metrics["overall"].get("row_count") or 0),
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "research_policy_metrics_ready": len(failures) == 0,
        "research_alpha_ready": promotion_gate_report["research_alpha_ready"],
        "model_promotion_allowed": promotion_gate_report["model_promotion_allowed"],
        "final_holdout_touched": bool(final_holdout_touched),
        "trading_semantics_changed": False,
        "promotion_gate": promotion_gate_report,
        "live_execution_ready": False,
        "execution_realism": EXECUTION_REALISM,
        "execution_policy": EXECUTION_POLICY_NAME,
        "live_execution_blockers": [
            "policy uses saved OOS predictions, not a live signal router",
            "costs use fixed round-turn assumptions after target-window netting",
            "partial fills, order rejection, latency, and capacity remain outside this report",
            "contract-specific execution mapping remains outside this report",
        ],
        "metrics": policy_metrics,
    }
    _write_json(metrics_json_path, policy_report)
    _write_json(phase8_metrics_path, policy_report)

    selection_report = {
        "generated_at": generated_at,
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "run": run,
        "input_root": _relative_path(predictions_path.parent),
        "output_root": _relative_path(model_selection_root),
        "prediction_path": _relative_path(predictions_path),
        "prediction_manifest_path": _relative_path(predictions_manifest)
        if predictions_manifest
        else None,
        "models_config": _relative_path(models_config),
        "model_config_hash": _stable_hash(models),
        "prediction_manifest_artifact_evidence_ready": not manifest_failures,
        "selection_status": "NOT_SELECTED_BASELINE_DIAGNOSTICS_ONLY",
        "selected_model_id": None,
        "selection_reason": (
            "baseline diagnostics and deterministic policy metrics are produced; "
            "no model is promoted or tuned by this script"
        ),
        "final_holdout_excluded_from_selection": True,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "policy_config": asdict(policy),
        "promotion_gate": promotion_gate_report,
        "research_alpha_ready": promotion_gate_report["research_alpha_ready"],
        "model_promotion_allowed": promotion_gate_report["model_promotion_allowed"],
        "policy_metrics_overall": policy_metrics["overall"],
        "model_comparison_path": _relative_path(model_comparison_path),
        "policy_metrics_path": _relative_path(metrics_json_path),
        "calibration_report_path": _relative_path(calibration_report_path),
        "live_execution_ready": False,
        "execution_realism": EXECUTION_REALISM,
        "execution_policy": EXECUTION_POLICY_NAME,
    }
    _write_json(model_selection_report_path, selection_report)

    calibration_payload = {
        "generated_at": generated_at,
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "run": run,
        "input_root": _relative_path(predictions_path.parent),
        "output_root": _relative_path(model_selection_root),
        "prediction_path": _relative_path(predictions_path),
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        **calibration_report,
    }
    _write_json(calibration_report_path, calibration_payload)
    market_summaries = [
        item
        for item in policy_metrics.get("summaries", [])
        if isinstance(item, Mapping) and item.get("scope") == "market"
    ]
    fold_summaries = [
        item
        for item in policy_metrics.get("summaries", [])
        if isinstance(item, Mapping) and item.get("scope") == "fold"
    ]
    alpha_decision = {
        "generated_at": generated_at,
        "run": run,
        "profile": manifest.get("profile"),
        "resolved_profile": manifest.get("resolved_profile"),
        "promoted": bool(promotion_gate_report["model_promotion_allowed"]),
        "research_alpha_ready": promotion_gate_report["research_alpha_ready"],
        "model_promotion_allowed": promotion_gate_report["model_promotion_allowed"],
        "promotion_gate": promotion_gate_report,
        "blockers": promotion_gate_report["promotion_blockers"],
        "costed_oos": policy_metrics["overall"],
        "markets": market_summaries,
        "folds": fold_summaries,
        "final_holdout_touched": bool(final_holdout_touched),
        "used_final_holdout_for_tuning": False,
        "trading_semantics_changed": False,
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
    }
    _write_json(alpha_decision_path, alpha_decision)
    return {
        "failure_count": len(failures),
        "warning_count": len(warnings),
        "failures": failures,
        "warnings": warnings,
        "metrics_path": metrics_json_path,
        "metrics_csv_path": metrics_csv_path,
        "turnover_path": turnover_path,
        "model_comparison_path": model_comparison_path,
        "model_selection_report_path": model_selection_report_path,
        "calibration_report_path": calibration_report_path,
        "phase8_metrics_path": phase8_metrics_path,
        "alpha_promotion_decision_path": alpha_decision_path,
        "policy_metrics": policy_metrics,
        "promotion_gate": promotion_gate_report,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions",
        default=None,
        help="Explicit prediction parquet path. Required; no data/predictions default is used.",
    )
    parser.add_argument("--predictions-manifest", default=DEFAULT_PREDICTIONS_MANIFEST.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--metrics-root", default=DEFAULT_METRICS_ROOT.as_posix())
    parser.add_argument("--model-selection-root", default=DEFAULT_MODEL_SELECTION_ROOT.as_posix())
    parser.add_argument("--phase8-root", default=DEFAULT_PHASE8_ROOT.as_posix())
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--long-short-margin", type=float, default=0.05)
    parser.add_argument("--min-fade-success", type=float, default=0.50)
    parser.add_argument("--max-trend-danger", type=float, default=0.50)
    parser.add_argument("--min-gross-return-dollars", type=float, default=1.0)
    parser.add_argument("--min-net-return-dollars", type=float, default=1.0)
    parser.add_argument("--min-net-sharpe-like", type=float, default=0.0)
    parser.add_argument("--max-cost-drag-to-abs-gross", type=float, default=1.0)
    parser.add_argument("--max-turnover-per-bar", type=float, default=0.10)
    parser.add_argument("--min-trade-count", type=int, default=100)
    parser.add_argument("--min-market-count", type=int, default=2)
    parser.add_argument("--min-traded-market-count", type=int, default=2)
    parser.add_argument("--min-fold-count", type=int, default=4)
    parser.add_argument("--min-traded-fold-count", type=int, default=4)
    parser.add_argument("--min-oos-span-days", type=float, default=30.0)
    parser.add_argument("--max-single-market-trade-share", type=float, default=0.75)
    parser.add_argument("--max-single-fold-trade-share", type=float, default=0.50)
    parser.add_argument(
        "--allow-negative-net-market",
        action="store_true",
        help="Do not block promotion when a market has nonpositive net dollars.",
    )
    parser.add_argument(
        "--allow-negative-net-fold",
        action="store_true",
        help="Do not block promotion when a fold has nonpositive net dollars.",
    )
    parser.add_argument(
        "--require-promotion-ready",
        action="store_true",
        help="Return nonzero when structural diagnostics pass but promotion gates fail.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if not args.predictions:
        parser.error("--predictions is required; pass an explicit prediction parquet path")
    result = evaluate_predictions(
        predictions_path=Path(args.predictions),
        predictions_manifest=Path(args.predictions_manifest)
        if args.predictions_manifest
        else None,
        costs_config=Path(args.costs_config),
        models_config=Path(args.models_config),
        metrics_root=Path(args.metrics_root),
        model_selection_root=Path(args.model_selection_root),
        phase8_root=Path(args.phase8_root),
        run=args.run,
        policy=load_policy_config(
            Path(args.models_config),
            long_short_margin=args.long_short_margin,
            min_fade_success=args.min_fade_success,
            max_trend_danger=args.max_trend_danger,
        ),
        promotion_gate=PromotionGateConfig(
            min_gross_return_dollars=args.min_gross_return_dollars,
            min_net_return_dollars=args.min_net_return_dollars,
            min_net_sharpe_like=args.min_net_sharpe_like,
            max_cost_drag_to_abs_gross=args.max_cost_drag_to_abs_gross,
            max_turnover_per_bar=args.max_turnover_per_bar,
            min_trade_count=args.min_trade_count,
            min_market_count=args.min_market_count,
            min_traded_market_count=args.min_traded_market_count,
            min_fold_count=args.min_fold_count,
            min_traded_fold_count=args.min_traded_fold_count,
            min_oos_span_days=args.min_oos_span_days,
            max_single_market_trade_share=args.max_single_market_trade_share,
            max_single_fold_trade_share=args.max_single_fold_trade_share,
            require_positive_net_all_markets=not args.allow_negative_net_market,
            require_positive_net_all_folds=not args.allow_negative_net_fold,
        ),
    )
    overall = result["policy_metrics"]["overall"]
    promotion = result["promotion_gate"]
    print(
        "FAIL" if result["failure_count"] else "PASS",
        "model diagnostics:",
        f"rows={overall.get('row_count', 0)}",
        f"trades={overall.get('trade_count', 0)}",
        f"net_dollars={overall.get('net_return_dollars', 0.0)}",
        f"alpha_ready={promotion['research_alpha_ready']}",
        f"failures={result['failure_count']}",
    )
    if args.require_promotion_ready and not promotion["model_promotion_allowed"]:
        return 1
    return 1 if result["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
