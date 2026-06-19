#!/usr/bin/env python3
"""Databento live OHLCV shadow signal runner.

Research/paper observation only. This script does not place orders, connect to
brokers, or export/train models.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, Sequence, TextIO

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.databento_auth import resolve_databento_api_key
from scripts.phase2_causal_base.build_causal_base_data import (
    _add_roll_fields,
    _build_causal_invalid_reason,
    _session_metadata,
    _valid_ohlcv,
    load_session_calendar,
)
from scripts.phase4_features.build_baseline_features import (
    FEATURE_COLS,
    FEATURE_FAMILIES,
    add_base_market_features,
    resolve_market_tick_size,
)


DEFAULT_DATASET = "GLBX.MDP3"
DEFAULT_SCHEMA = "ohlcv-1m"
DEFAULT_SYMBOLS = "ES.v.0"
DEFAULT_MARKET = "ES"
DEFAULT_STYPE_IN = "continuous"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_BARS = 50
DEFAULT_MIN_FEATURE_BARS = 180
DEFAULT_ROLLING_WINDOW_BARS = 2_000
DEFAULT_SESSION_CONFIG = Path("configs/market_sessions.yaml")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_LOG_DIR = Path("logs/live")
DEFAULT_LONG_SHORT_MARGIN = 0.05
DEFAULT_MIN_FADE_SUCCESS = 0.50
DEFAULT_MAX_TREND_DANGER = 0.50
API_KEY_ENV = "DATABENTO_API_KEY"
FIXED_PRICE_SCALE = 1_000_000_000
UNDEF_PRICE = 9_223_372_036_854_775_807

TARGET_RETURN = "target_ret_15m"
TARGET_DIRECTION = "target_sign_with_deadzone"
TARGET_FADE = "target_fade_success_15m"
TARGET_TREND = "target_trend_danger_30m"
REQUIRED_TARGETS = (TARGET_RETURN, TARGET_DIRECTION, TARGET_FADE, TARGET_TREND)


@dataclass(frozen=True)
class PolicyConfig:
    long_short_margin: float = DEFAULT_LONG_SHORT_MARGIN
    min_fade_success: float = DEFAULT_MIN_FADE_SUCCESS
    max_trend_danger: float = DEFAULT_MAX_TREND_DANGER


@dataclass(frozen=True)
class ModelBundle:
    feature_cols: list[str]
    estimators: Mapping[str, Any]


@dataclass(frozen=True)
class LiveBar:
    ts: pd.Timestamp
    market: str
    symbol: str
    instrument_id: int | None
    publisher_id: int | None
    rtype: int | None
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class ShadowState:
    market: str
    symbol: str
    model_bundle: ModelBundle
    tick_size: float
    session_config: Path
    policy: PolicyConfig
    min_feature_bars: int
    rolling_window_bars: int
    signals_output: Path
    bars_output: Path
    stdout: TextIO
    stderr: TextIO
    max_bars: int
    client: Any | None = None
    bars_seen: int = 0

    def __post_init__(self) -> None:
        self._bars: list[LiveBar] = []

    def handle_record(self, record: object) -> None:
        try:
            bar = ohlcv_record_to_bar(record, market=self.market, symbol=self.symbol)
        except NonOHLCVRecord:
            return
        except Exception as exc:
            print(f"Skipping {type(record).__name__}: {exc}", file=self.stderr)
            return

        self._bars.append(bar)
        if len(self._bars) > self.rolling_window_bars:
            self._bars = self._bars[-self.rolling_window_bars :]
        self.bars_seen += 1

        append_jsonl(self.bars_output, bar_payload(bar))
        signal = build_signal_payload(
            self._bars,
            market=self.market,
            model_bundle=self.model_bundle,
            tick_size=self.tick_size,
            session_config=self.session_config,
            policy=self.policy,
            min_feature_bars=self.min_feature_bars,
        )
        append_jsonl(self.signals_output, signal)
        print(format_signal_line(signal), file=self.stdout, flush=True)

        if self.bars_seen >= self.max_bars and self.client is not None:
            stop = getattr(self.client, "stop", None)
            if callable(stop):
                stop()


class NonOHLCVRecord(ValueError):
    """Raised for live system, error, and mapping messages."""


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return parsed


def nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def parse_start(value: str | None) -> str | int | None:
    if value is None or value == "":
        return None
    if value == "0":
        return 0
    return value


def parse_symbols(value: str) -> str | list[str]:
    symbols = [symbol.strip() for symbol in value.split(",") if symbol.strip()]
    if not symbols:
        raise argparse.ArgumentTypeError("must include at least one symbol")
    if len(symbols) == 1:
        return symbols[0]
    return symbols


def resolve_api_key(env: Mapping[str, str] | None = None) -> str | None:
    key = resolve_databento_api_key(env=env, key_name=API_KEY_ENV)
    return key or None


def import_databento() -> ModuleType:
    return importlib.import_module("databento")


def _value(record: object, name: str) -> object:
    if not hasattr(record, name):
        raise ValueError(f"missing field: {name}")
    attr = getattr(record, name)
    return attr() if callable(attr) else attr


def _optional_int(record: object, name: str) -> int | None:
    if not hasattr(record, name):
        return None
    value = getattr(record, name)
    value = value() if callable(value) else value
    if value is None or pd.isna(value):
        return None
    return int(value)


def fixed_price_to_float(value: object) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError("price is missing or nonnumeric")
    if isinstance(value, int):
        if value == UNDEF_PRICE:
            raise ValueError("price is undefined")
        return value / FIXED_PRICE_SCALE
    if isinstance(value, float):
        if math.isnan(value):
            raise ValueError("price is nan")
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("price is empty")
        return float(stripped)
    raise ValueError(f"unsupported price type: {type(value).__name__}")


def normalize_ts_event(value: object) -> pd.Timestamp:
    if value is None or isinstance(value, bool):
        raise ValueError("ts_event is missing or invalid")
    if isinstance(value, int):
        if abs(value) > 100_000_000_000_000_000:
            return pd.to_datetime(value, unit="ns", utc=True)
        if abs(value) > 100_000_000_000_000:
            return pd.to_datetime(value, unit="us", utc=True)
        if abs(value) > 100_000_000_000:
            return pd.to_datetime(value, unit="ms", utc=True)
        return pd.to_datetime(value, unit="s", utc=True)
    return pd.to_datetime(value, utc=True)


def ohlcv_record_to_bar(record: object, *, market: str, symbol: str) -> LiveBar:
    missing = [
        field
        for field in ("ts_event", "open", "high", "low", "close", "volume")
        if not hasattr(record, field)
    ]
    if missing:
        raise NonOHLCVRecord(
            f"{type(record).__name__} is not an OHLCV record: {','.join(missing)}"
        )
    return LiveBar(
        ts=normalize_ts_event(_value(record, "ts_event")),
        market=market,
        symbol=symbol,
        instrument_id=_optional_int(record, "instrument_id"),
        publisher_id=_optional_int(record, "publisher_id"),
        rtype=_optional_int(record, "rtype"),
        open=fixed_price_to_float(_value(record, "open")),
        high=fixed_price_to_float(_value(record, "high")),
        low=fixed_price_to_float(_value(record, "low")),
        close=fixed_price_to_float(_value(record, "close")),
        volume=int(_value(record, "volume")),
    )


def _json_default(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def append_jsonl(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=_json_default, allow_nan=False) + "\n")


def utc_stamp(clock: Callable[[], datetime] | None = None) -> str:
    now = clock() if clock is not None else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_output_path(
    *,
    log_dir: Path,
    market: str,
    kind: str,
    clock: Callable[[], datetime] | None = None,
) -> Path:
    return log_dir / f"live_shadow_{market}_{kind}_{utc_stamp(clock)}.jsonl"


def load_model_bundle(path: Path) -> ModelBundle:
    joblib = importlib.import_module("joblib")
    payload = joblib.load(path)
    return normalize_model_bundle(payload)


def normalize_model_bundle(payload: object) -> ModelBundle:
    if not isinstance(payload, Mapping):
        raise ValueError("model bundle must be a mapping")
    raw_features = payload.get("feature_cols")
    if not isinstance(raw_features, list) or not all(
        isinstance(item, str) for item in raw_features
    ):
        raise ValueError("model bundle feature_cols must be a list of strings")
    raw_estimators = payload.get("estimators")
    if not isinstance(raw_estimators, Mapping):
        raise ValueError("model bundle estimators must be a mapping")
    missing_targets = [target for target in REQUIRED_TARGETS if target not in raw_estimators]
    if missing_targets:
        raise ValueError("model bundle missing target estimators: " + ",".join(missing_targets))
    unknown_features = sorted(set(raw_features) - set(FEATURE_COLS))
    if unknown_features:
        raise ValueError("model bundle has unknown features: " + ",".join(unknown_features))
    return ModelBundle(
        feature_cols=list(raw_features),
        estimators={str(key): value for key, value in raw_estimators.items()},
    )


def bars_to_raw_frame(bars: Sequence[LiveBar], *, market: str) -> pd.DataFrame:
    rows = [
        {
            "ts": bar.ts,
            "market": market,
            "year": int(bar.ts.year),
            "symbol": bar.symbol,
            "instrument_id": bar.instrument_id,
            "publisher_id": bar.publisher_id,
            "rtype": bar.rtype,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "raw_row_present": True,
            "is_synthetic": False,
            "synthetic_gap_id": pd.NA,
            "synthetic_gap_size_minutes": pd.NA,
            "synthetic_gap_reason": "",
            "data_quality_status": "live",
            "data_quality_degraded": False,
            "source_path": "databento_live",
            "source_file_hash": "LIVE_STREAM",
            "source_row_number": idx,
            "raw_schema_variant": "databento_live_ohlcv",
            "timestamp_source": "ts_event",
        }
        for idx, bar in enumerate(bars)
    ]
    return pd.DataFrame(rows)


def build_live_feature_frame(
    bars: Sequence[LiveBar],
    *,
    market: str,
    tick_size: float,
    session_config: Path,
) -> pd.DataFrame:
    raw = bars_to_raw_frame(bars, market=market)
    if raw.empty:
        return raw
    raw = raw.sort_values("ts", kind="mergesort").reset_index(drop=True)
    raw["valid_ohlcv"] = _valid_ohlcv(raw)
    metadata_available = raw["instrument_id"].notna().any()
    raw["metadata_available"] = bool(metadata_available)
    raw["roll_detection_available"] = bool(metadata_available)
    raw["roll_detection_source"] = np.where(
        metadata_available, "instrument_id", "unavailable"
    )
    raw["roll_policy_status"] = np.where(
        metadata_available, "active", "unavailable_metadata"
    )

    calendar = load_session_calendar(market, session_config, allow_hardcoded_calendar=False)
    session = _session_metadata(raw["ts"], calendar)
    frame = pd.concat([raw, session], axis=1)
    frame["session_calendar_status"] = calendar.status
    frame["holiday_calendar_available"] = calendar.holiday_calendar_available
    frame["early_close_calendar_available"] = calendar.early_close_calendar_available
    frame["calendar_coverage_status"] = calendar.calendar_coverage_status

    frame = _add_roll_fields(frame, roll_window_bars=15)
    frame["boundary_session_flag"] = False
    frame["session_data_quality_degraded"] = False
    session_mask = frame["session_id"].notna()
    if bool(session_mask.any()):
        frame.loc[session_mask, "session_data_quality_degraded"] = (
            frame.loc[session_mask]
            .groupby("session_id", sort=False)["data_quality_degraded"]
            .transform("any")
            .astype(bool)
        )
    frame["trainable_data_quality"] = ~frame["session_data_quality_degraded"].astype(bool)
    frame["causal_valid"] = (
        frame["raw_row_present"]
        & ~frame["is_synthetic"]
        & frame["valid_ohlcv"]
        & frame["inside_session"]
        & frame["trainable_data_quality"]
        & ~frame["roll_window_flag"]
        & ~frame["boundary_session_flag"]
    ).astype(bool)
    frame["causal_invalid_reason"] = _build_causal_invalid_reason(frame, [])
    frame["target_valid"] = False

    features = add_base_market_features(frame, tick_size=tick_size)
    for feature in FEATURE_FAMILIES["tier1_intermarket"] + FEATURE_FAMILIES[
        "tier1_cross_market_regime"
    ]:
        if feature in features.columns:
            features[feature] = np.nan
    return features


def _finite_or_none(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _predict_value(estimator: Any, features: pd.DataFrame) -> float:
    predict = getattr(estimator, "predict", None)
    if not callable(predict):
        raise ValueError("regression estimator missing predict")
    predicted = predict(features)
    return float(np.asarray(predicted, dtype=float)[0])


def _class_probability(
    estimator: Any,
    features: pd.DataFrame,
    positive: object,
) -> float:
    predict_proba = getattr(estimator, "predict_proba", None)
    classes = getattr(estimator, "classes_", None)
    if not callable(predict_proba) or classes is None:
        raise ValueError("classification estimator missing predict_proba/classes_")
    probabilities = np.asarray(predict_proba(features), dtype=float)
    class_values = list(np.asarray(classes))
    if positive not in class_values:
        return math.nan
    idx = class_values.index(positive)
    return float(probabilities[0, idx])


def model_predictions(model_bundle: ModelBundle, row: pd.Series) -> dict[str, float]:
    x = pd.DataFrame([row[model_bundle.feature_cols].to_dict()])
    return {
        "expected_return": _predict_value(model_bundle.estimators[TARGET_RETURN], x),
        "p_long": _class_probability(model_bundle.estimators[TARGET_DIRECTION], x, 1),
        "p_short": _class_probability(model_bundle.estimators[TARGET_DIRECTION], x, -1),
        "p_flat": _class_probability(model_bundle.estimators[TARGET_DIRECTION], x, 0),
        "p_fade_success": _class_probability(model_bundle.estimators[TARGET_FADE], x, 1),
        "p_trend_danger": _class_probability(model_bundle.estimators[TARGET_TREND], x, 1),
    }


def bar_payload(bar: LiveBar) -> dict[str, object]:
    return {
        "timestamp": bar.ts.isoformat(),
        "market": bar.market,
        "symbol": bar.symbol,
        "instrument_id": bar.instrument_id,
        "publisher_id": bar.publisher_id,
        "rtype": bar.rtype,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
    }


def base_block_payload(bar: LiveBar, reasons: list[str]) -> dict[str, object]:
    payload = bar_payload(bar)
    payload.update(
        {
            "signal": "NO_FADE",
            "fade_ok": False,
            "do_not_fade": True,
            "suggested_direction": "FLAT",
            "confidence": 0.0,
            "reason_flags": reasons,
        }
    )
    return payload


def build_signal_payload(
    bars: Sequence[LiveBar],
    *,
    market: str,
    model_bundle: ModelBundle,
    tick_size: float,
    session_config: Path,
    policy: PolicyConfig,
    min_feature_bars: int,
) -> dict[str, object]:
    bar = bars[-1]
    if len(bars) < min_feature_bars:
        return base_block_payload(bar, ["insufficient_feature_warmup"])
    if bar.instrument_id is None:
        return base_block_payload(bar, ["missing_instrument_id"])

    try:
        features = build_live_feature_frame(
            bars,
            market=market,
            tick_size=tick_size,
            session_config=session_config,
        )
    except Exception as exc:
        return base_block_payload(bar, [f"feature_build_error:{type(exc).__name__}"])

    latest = features.iloc[-1]
    if not bool(latest.get("valid_ohlcv", False)):
        return base_block_payload(bar, ["invalid_ohlcv"])
    if not bool(latest.get("inside_session", False)):
        return base_block_payload(bar, ["outside_session"])
    if not bool(latest.get("causal_valid", False)):
        reason = str(latest.get("causal_invalid_reason", "") or "causal_invalid")
        return base_block_payload(bar, [reason])
    if not bool(latest.get("feature_input_valid", False)):
        return base_block_payload(bar, ["feature_input_invalid"])

    try:
        preds = model_predictions(model_bundle, latest)
    except Exception as exc:
        return base_block_payload(bar, [f"model_inference_error:{type(exc).__name__}"])

    p_long = _finite_or_none(preds.get("p_long"))
    p_short = _finite_or_none(preds.get("p_short"))
    p_flat = _finite_or_none(preds.get("p_flat"))
    p_fade_success = _finite_or_none(preds.get("p_fade_success"))
    p_trend_danger = _finite_or_none(preds.get("p_trend_danger"))
    reasons: list[str] = []

    if p_long is None or p_short is None:
        reasons.append("missing_direction_probability")
        direction_signal = 0
        direction_probability = None
    else:
        margin = p_long - p_short
        if margin >= policy.long_short_margin:
            direction_signal = 1
            direction_probability = p_long
        elif margin <= -policy.long_short_margin:
            direction_signal = -1
            direction_probability = p_short
        else:
            direction_signal = 0
            direction_probability = None

    if direction_signal == 0:
        reasons.append("no_direction_edge")
    if direction_probability is None or p_flat is None or direction_probability <= p_flat:
        reasons.append("flat_probability_block")
    fade_ok = p_fade_success is not None and p_fade_success >= policy.min_fade_success
    if not fade_ok:
        reasons.append("fade_filter_block")
    trend_ok = p_trend_danger is not None and p_trend_danger < policy.max_trend_danger
    if not trend_ok:
        reasons.append("trend_danger_block")

    do_not_fade = bool(reasons)
    suggested_direction = "LONG" if direction_signal == 1 else "SHORT" if direction_signal == -1 else "FLAT"
    signal = (
        "LONG_FADE"
        if direction_signal == 1 and not do_not_fade
        else "SHORT_FADE"
        if direction_signal == -1 and not do_not_fade
        else "NO_FADE"
    )
    confidence_parts = [
        direction_probability,
        p_fade_success,
        None if p_trend_danger is None else 1.0 - p_trend_danger,
    ]
    confidence_values = [value for value in confidence_parts if value is not None]
    confidence = float(min(confidence_values)) if len(confidence_values) == 3 else 0.0

    payload = bar_payload(bar)
    payload.update(
        {
            "signal": signal,
            "fade_ok": bool(fade_ok),
            "do_not_fade": do_not_fade,
            "suggested_direction": suggested_direction,
            "confidence": confidence,
            "reason_flags": reasons,
            "expected_return": _finite_or_none(preds.get("expected_return")),
            "p_long": p_long,
            "p_short": p_short,
            "p_flat": p_flat,
            "p_fade_success": p_fade_success,
            "p_trend_danger": p_trend_danger,
        }
    )
    return payload


def format_signal_line(signal: Mapping[str, object]) -> str:
    ts = pd.to_datetime(signal["timestamp"], utc=True).tz_convert("America/Los_Angeles")
    confidence = float(signal.get("confidence") or 0.0)
    return (
        f"{ts:%Y-%m-%d %H:%M:%S %Z} | {signal['market']} | "
        f"signal={signal['signal']} | do_not_fade={signal['do_not_fade']} | "
        f"confidence={confidence:.2f} | reasons={','.join(signal['reason_flags'])}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--symbols", default=DEFAULT_SYMBOLS)
    parser.add_argument("--market", default=DEFAULT_MARKET)
    parser.add_argument("--stype-in", default=DEFAULT_STYPE_IN)
    parser.add_argument("--start", default=None)
    parser.add_argument("--model-bundle", required=True)
    parser.add_argument("--session-config", default=DEFAULT_SESSION_CONFIG.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR.as_posix())
    parser.add_argument("--signals-output", default=None)
    parser.add_argument("--bars-output", default=None)
    parser.add_argument("--max-bars", type=positive_int, default=DEFAULT_MAX_BARS)
    parser.add_argument(
        "--timeout-seconds",
        type=nonnegative_float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--min-feature-bars",
        type=positive_int,
        default=DEFAULT_MIN_FEATURE_BARS,
    )
    parser.add_argument(
        "--rolling-window-bars",
        type=positive_int,
        default=DEFAULT_ROLLING_WINDOW_BARS,
    )
    parser.add_argument(
        "--long-short-margin",
        type=float,
        default=DEFAULT_LONG_SHORT_MARGIN,
    )
    parser.add_argument(
        "--min-fade-success",
        type=float,
        default=DEFAULT_MIN_FADE_SUCCESS,
    )
    parser.add_argument(
        "--max-trend-danger",
        type=float,
        default=DEFAULT_MAX_TREND_DANGER,
    )
    return parser


def run_live_shadow(
    args: argparse.Namespace,
    *,
    env: Mapping[str, str] | None = None,
    db_module: ModuleType | None = None,
    model_loader: Callable[[Path], ModelBundle] = load_model_bundle,
    clock: Callable[[], datetime] | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    api_key = resolve_api_key(env)
    if api_key is None:
        print(f"Missing {API_KEY_ENV}; set it before running live shadow.", file=stderr)
        return 2

    model_bundle_path = Path(args.model_bundle)
    if not model_bundle_path.exists():
        print(f"Missing model bundle: {model_bundle_path}", file=stderr)
        return 2
    try:
        model_bundle = model_loader(model_bundle_path)
    except Exception as exc:
        print(f"Invalid model bundle: {exc}", file=stderr)
        return 2

    if db_module is None:
        try:
            db_module = import_databento()
        except ModuleNotFoundError:
            print("Missing databento package; install project requirements.", file=stderr)
            return 2

    tick_size, tick_failure = resolve_market_tick_size(
        Path(args.costs_config),
        str(args.market),
    )
    if tick_failure or tick_size is None:
        print(tick_failure or f"missing tick_size for market: {args.market}", file=stderr)
        return 2

    log_dir = Path(args.log_dir)
    signals_output = (
        Path(args.signals_output)
        if args.signals_output
        else default_output_path(log_dir=log_dir, market=args.market, kind="signals", clock=clock)
    )
    bars_output = (
        Path(args.bars_output)
        if args.bars_output
        else default_output_path(log_dir=log_dir, market=args.market, kind="bars", clock=clock)
    )
    state = ShadowState(
        market=str(args.market),
        symbol=str(args.symbols),
        model_bundle=model_bundle,
        tick_size=float(tick_size),
        session_config=Path(args.session_config),
        policy=PolicyConfig(
            long_short_margin=float(args.long_short_margin),
            min_fade_success=float(args.min_fade_success),
            max_trend_danger=float(args.max_trend_danger),
        ),
        min_feature_bars=int(args.min_feature_bars),
        rolling_window_bars=int(args.rolling_window_bars),
        signals_output=signals_output,
        bars_output=bars_output,
        stdout=stdout,
        stderr=stderr,
        max_bars=int(args.max_bars),
    )
    live = None
    try:
        live = db_module.Live(key=api_key)
        state.client = live
        live.subscribe(
            dataset=args.dataset,
            schema=args.schema,
            symbols=parse_symbols(args.symbols),
            stype_in=args.stype_in,
            start=parse_start(args.start),
        )
        live.add_callback(state.handle_record)
        live.start()
        live.block_for_close(timeout=args.timeout_seconds)
        return 0
    except KeyboardInterrupt:
        print("Interrupted; stopping live shadow.", file=stderr)
        return 130
    except Exception as exc:
        print(f"Databento live shadow failed: {exc}", file=stderr)
        return 1
    finally:
        if live is not None:
            stop = getattr(live, "stop", None)
            if callable(stop):
                stop()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return run_live_shadow(args)


if __name__ == "__main__":
    raise SystemExit(main())
