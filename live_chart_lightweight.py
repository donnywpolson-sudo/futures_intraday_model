#!/usr/bin/env python3
"""Optional Databento live OHLCV chart for research observation only."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import queue
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Mapping, Sequence, TextIO, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.databento_auth import (  # noqa: E402
    load_databento_api_key_from_file,
    resolve_databento_api_key,
)


DEFAULT_DATASET = "GLBX.MDP3"
DEFAULT_SCHEMA = "ohlcv-1m"
DEFAULT_SYMBOLS = "ES.c.0"
DEFAULT_STYPE_IN = "continuous"
DEFAULT_LOOKBACK_HOURS = 168.0
DEFAULT_MAX_RECORDS = 0
DEFAULT_TIMEOUT_SECONDS: float | None = None
DEFAULT_NO_DATA_WARNING_SECONDS = 60.0
DEFAULT_CHART_TIMEFRAME = "1m"
DEFAULT_CHART_TIMEFRAMES = "1m,5m,15m,30m,1h,4h,1d"
DEFAULT_DISPLAY_TZ = "local"
VSCODE_RUN_BUTTON_ARGS = (
    "--historical-backfill",
    "--lookback-hours",
    "168",
    "--timeout-seconds",
    "120",
    "--no-data-warning-seconds",
    "15",
)
VSCODE_RUN_CHILD_ENV = "LIVE_CHART_LIGHTWEIGHT_RUN_CHILD"
VSCODE_ENV_KEYS = ("VSCODE_PID", "VSCODE_CWD", "VSCODE_IPC_HOOK_CLI")
API_KEY_ENV = "DATABENTO_API_KEY"
ROOT_API_KEY_FILE = ROOT / "databento.env"
FIXED_PRICE_SCALE = 1_000_000_000
UNDEF_PRICE = 9_223_372_036_854_775_807
OHLCV_FIELDS = ("ts_event", "open", "high", "low", "close", "volume")
OHLCV_PAYLOAD_FIELDS = ("open", "high", "low", "close", "volume")
ALWAYS_REPORTED_RECORD_TYPE_MARKERS = ("Error",)
TIMEFRAME_PATTERN = re.compile(r"^(\d+)([smhd])$")
START_CLAMP_PATTERN = re.compile(r"Must be\s+([^,\s]+)\s+or later", re.IGNORECASE)
AVAILABLE_END_PATTERN = re.compile(
    r"data available up to\s+['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
CHART_RENDER_BATCH_RECORDS = 2_000
CHART_RENDER_BATCH_WAIT_SECONDS = 0.01
CHART_RENDER_THROTTLE_SECONDS = 0.25
TOPBAR_STATUS_NAME = "status"
LOADING_STATUS_TEXT = "Loading replay candles..."
EXCHANGE_TZ_NAME = "America/Chicago"
RTH_OPEN_HOUR = 8
RTH_OPEN_MINUTE = 30
GLOBEX_OPEN_HOUR = 17
GLOBEX_OPEN_MINUTE = 0
CHART_INSTALL_MESSAGE = (
    'Missing lightweight-charts package; install optional chart support with: '
    'python -m pip install "lightweight-charts>=2.1,<3"'
)
CandleValue = datetime | int | float
SubscriptionStart = datetime | str | int | None


def candle_float(value: CandleValue) -> float:
    return float(cast(Any, value))


def candle_int(value: CandleValue) -> int:
    return int(cast(Any, value))


@dataclass
class ChartStatus:
    records_updated: int = 0
    first_time: datetime | None = None
    latest_time: datetime | None = None
    last_close: float | None = None
    status_line_printed: bool = False


@dataclass
class ChartDisplayState:
    raw_candles: list[dict[str, CandleValue]]
    timeframe: str
    timeframe_seconds: int
    display_tz: tzinfo
    display_tz_name: str
    loading: bool = True
    session_marker_objects: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderStartClamp:
    allowed_start: datetime
    message: str


ChartQueueItem = dict[str, CandleValue] | ProviderStartClamp


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return parsed


def normalize_timeframe(value: str) -> str:
    text = value.strip().lower()
    match = TIMEFRAME_PATTERN.fullmatch(text)
    if match is None:
        raise argparse.ArgumentTypeError("timeframe must look like 1m, 5m, 15m, 1h, 4h, or 1d")
    amount = int(match.group(1))
    if amount <= 0:
        raise argparse.ArgumentTypeError("timeframe amount must be > 0")
    return f"{amount}{match.group(2)}"


def timeframe_seconds(value: str) -> int:
    timeframe = normalize_timeframe(value)
    amount = int(timeframe[:-1])
    unit = timeframe[-1]
    if unit == "s":
        return amount
    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 60 * 60
    if unit == "d":
        return amount * 24 * 60 * 60
    raise argparse.ArgumentTypeError(f"unsupported timeframe unit: {unit}")


def parse_chart_timeframes(value: str) -> tuple[str, ...]:
    timeframes = tuple(
        dict.fromkeys(
            normalize_timeframe(part)
            for part in value.split(",")
            if part.strip()
        )
    )
    if not timeframes:
        raise argparse.ArgumentTypeError("must include at least one chart timeframe")
    return timeframes


def parse_ohlcv_schema_seconds(schema: str) -> int | None:
    prefix = "ohlcv-"
    if not schema.startswith(prefix):
        return None
    try:
        return timeframe_seconds(schema[len(prefix) :])
    except argparse.ArgumentTypeError:
        return None


def validate_chart_timeframe(
    *,
    chart_timeframe: str,
    chart_timeframes: tuple[str, ...],
    schema: str,
) -> str | None:
    if chart_timeframe not in chart_timeframes:
        return (
            f"--chart-timeframe {chart_timeframe!r} must be included in "
            f"--chart-timeframes {','.join(chart_timeframes)!r}."
        )
    source_seconds = parse_ohlcv_schema_seconds(schema)
    if source_seconds is None:
        return None
    for option in chart_timeframes:
        option_seconds = timeframe_seconds(option)
        if option_seconds < source_seconds or option_seconds % source_seconds != 0:
            return (
                f"chart timeframe {option!r} cannot be built from schema {schema!r}; "
                "use the same or a larger multiple of the source OHLCV interval."
            )
    return None


def resolve_display_tz(value: str) -> tuple[tzinfo, str]:
    text = value.strip()
    if not text or text.lower() == "local":
        local_tz = datetime.now().astimezone().tzinfo
        return local_tz or timezone.utc, "local"
    if text.lower() in {"utc", "z"}:
        return timezone.utc, "UTC"
    try:
        return ZoneInfo(text), text
    except ZoneInfoNotFoundError as exc:
        raise argparse.ArgumentTypeError(f"unknown timezone: {value}") from exc


def parse_start(value: str | None) -> str | int | None:
    if value is None or value == "":
        return None
    if value == "0":
        return 0
    return value


def is_vscode_environment(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    if source.get("TERM_PROGRAM", "").lower() == "vscode":
        return True
    return any(bool(source.get(key)) for key in VSCODE_ENV_KEYS)


def resolve_main_argv(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if values:
        return values
    return list(VSCODE_RUN_BUTTON_ARGS)


def should_launch_vscode_run_child(
    raw_args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return (
        not raw_args
        and is_vscode_environment(source)
        and not source.get(VSCODE_RUN_CHILD_ENV)
    )


def launch_vscode_run_child(stderr: TextIO = sys.stderr) -> int:
    env = dict(os.environ)
    env[VSCODE_RUN_CHILD_ENV] = "1"
    command = [sys.executable, str(Path(__file__).resolve()), *VSCODE_RUN_BUTTON_ARGS]
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    previous_handler = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            creationflags=creationflags,
        )
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    try:
        return process.wait()
    except KeyboardInterrupt:
        print(
            "VS Code interrupted the launcher; live chart child process is still running.",
            file=stderr,
        )
        return 0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_window_start(
    args: argparse.Namespace,
    *,
    now: datetime | None = None,
) -> SubscriptionStart:
    current = now or utc_now()
    if args.start is not None:
        return parse_start(args.start)
    if args.lookback_days is not None:
        return current - timedelta(days=args.lookback_days)
    hours = args.lookback_hours or DEFAULT_LOOKBACK_HOURS
    return current - timedelta(hours=hours)


def format_utc_time(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


def format_close(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def display_time_label(value: datetime | None, display_tz: tzinfo) -> str:
    if value is None:
        return "n/a"
    return value.astimezone(display_tz).strftime("%Y-%m-%d %H:%M:%S %Z").strip()


def short_display_time_label(value: datetime | None, display_tz: tzinfo) -> str:
    if value is None:
        return "n/a"
    return value.astimezone(display_tz).strftime("%H:%M")


def format_chart_status(status: ChartStatus) -> str:
    return (
        f"records={status.records_updated} "
        f"first={format_utc_time(status.first_time)} "
        f"latest={format_utc_time(status.latest_time)} "
        f"last_close={format_close(status.last_close)}"
    )


def format_chart_title(
    *,
    symbols: str,
    schema: str,
    mode: str,
    chart_timeframe: str,
    display_tz: tzinfo,
    display_tz_name: str,
    status: ChartStatus | None = None,
) -> str:
    if status is None or status.latest_time is None:
        return f"{symbols} {chart_timeframe} from {schema} | {display_tz_name} display | connecting"
    return (
        f"{symbols} {chart_timeframe} from {schema} | {mode} | "
        f"{display_time_label(status.first_time, display_tz)} to "
        f"{display_time_label(status.latest_time, display_tz)} | "
        f"UTC last={format_utc_time(status.latest_time)}"
    )


def format_topbar_status(
    *,
    symbols: str,
    display: ChartDisplayState,
    status: ChartStatus,
) -> str:
    if display.loading:
        return f"Loading... {status.records_updated:,} bars"
    return (
        f"{symbols} {display.timeframe} | {status.records_updated:,} bars | "
        f"last {short_display_time_label(status.latest_time, display.display_tz)}"
    )


def safe_topbar_text(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ")


def configure_status_text(chart: object, text: str) -> None:
    topbar = getattr(chart, "topbar", None)
    textbox = getattr(topbar, "textbox", None)
    if callable(textbox):
        textbox(TOPBAR_STATUS_NAME, safe_topbar_text(text), align="right")


def update_chart_status_text(chart: object, text: str) -> None:
    topbar = getattr(chart, "topbar", None)
    getter = getattr(topbar, "get", None)
    widget = getter(TOPBAR_STATUS_NAME) if callable(getter) else None
    setter = getattr(widget, "set", None)
    if callable(setter):
        setter(safe_topbar_text(text))


def parse_symbols(value: str) -> str | list[str]:
    symbols = [symbol.strip() for symbol in value.split(",") if symbol.strip()]
    if not symbols:
        raise argparse.ArgumentTypeError("must include at least one symbol")
    if len(symbols) == 1:
        return symbols[0]
    return symbols


def resolve_api_key(env: dict[str, str] | None = None) -> str | None:
    if env is None:
        key = load_databento_api_key_from_file(ROOT_API_KEY_FILE, key_name=API_KEY_ENV)
        if key:
            return key
    key = resolve_databento_api_key(env=env, key_name=API_KEY_ENV)
    return key or None


def fixed_price_to_float(value: object) -> float:
    if value is None:
        raise ValueError("price is missing")
    if isinstance(value, bool):
        raise ValueError("price must be numeric")
    if isinstance(value, int):
        if value == UNDEF_PRICE:
            raise ValueError("price is undefined")
        return value / FIXED_PRICE_SCALE
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("price is empty")
        return float(stripped)
    raise ValueError(f"unsupported price type: {type(value).__name__}")


def normalize_ts_event(value: object) -> datetime:
    """Return a UTC datetime; lightweight_charts misreads numeric seconds as ms."""

    if value is None:
        raise ValueError("ts_event is missing")
    if isinstance(value, bool):
        raise ValueError("ts_event must be a timestamp")
    if isinstance(value, int):
        if value > 100_000_000_000_000_000:
            return datetime.fromtimestamp(value / 1_000_000_000, tz=timezone.utc)
        if value > 100_000_000_000_000:
            return datetime.fromtimestamp(value / 1_000_000, tz=timezone.utc)
        if value > 100_000_000_000:
            return datetime.fromtimestamp(value / 1_000, tz=timezone.utc)
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, float):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("ts_event is empty")
        if text.isdigit():
            return normalize_ts_event(int(text))
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    else:
        raise ValueError(f"unsupported ts_event type: {type(value).__name__}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def floor_timeframe(value: datetime, seconds: int) -> datetime:
    timestamp = int(normalize_ts_event(value).timestamp())
    return datetime.fromtimestamp(timestamp - (timestamp % seconds), tz=timezone.utc)


def chart_display_time(value: object, display_tz: tzinfo) -> datetime:
    utc_value = normalize_ts_event(value)
    return utc_value.astimezone(display_tz).replace(tzinfo=None)


def aggregate_candles(
    candles: Sequence[dict[str, CandleValue]],
    *,
    seconds: int,
) -> list[dict[str, CandleValue]]:
    aggregated: dict[datetime, dict[str, CandleValue]] = {}
    for candle in candles:
        bucket = floor_timeframe(normalize_ts_event(candle["time"]), seconds)
        if bucket not in aggregated:
            aggregated[bucket] = {
                "time": bucket,
                "open": candle_float(candle["open"]),
                "high": candle_float(candle["high"]),
                "low": candle_float(candle["low"]),
                "close": candle_float(candle["close"]),
                "volume": candle_int(candle["volume"]),
            }
            continue

        current = aggregated[bucket]
        current["high"] = max(
            candle_float(current["high"]),
            candle_float(candle["high"]),
        )
        current["low"] = min(
            candle_float(current["low"]),
            candle_float(candle["low"]),
        )
        current["close"] = candle_float(candle["close"])
        current["volume"] = candle_int(current["volume"]) + candle_int(
            candle["volume"]
        )
    return list(aggregated.values())


def candle_for_display(
    candle: dict[str, CandleValue],
    *,
    display_tz: tzinfo,
) -> dict[str, CandleValue]:
    displayed = dict(candle)
    displayed["time"] = chart_display_time(candle["time"], display_tz)
    return displayed


def session_marker_specs(
    display: ChartDisplayState,
    status: ChartStatus,
) -> list[tuple[datetime, str, str]]:
    if display.timeframe == "1d" or status.first_time is None or status.latest_time is None:
        return []
    try:
        exchange_tz = ZoneInfo(EXCHANGE_TZ_NAME)
    except ZoneInfoNotFoundError:
        return []

    first_utc = normalize_ts_event(status.first_time)
    latest_utc = normalize_ts_event(status.latest_time)
    current_day = first_utc.astimezone(exchange_tz).date()
    end_day = latest_utc.astimezone(exchange_tz).date()
    specs: list[tuple[datetime, str, str]] = []

    while current_day <= end_day:
        anchors = (
            (RTH_OPEN_HOUR, RTH_OPEN_MINUTE, "RTH", "#5b8def"),
            (GLOBEX_OPEN_HOUR, GLOBEX_OPEN_MINUTE, "Globex", "#8a94a6"),
        )
        for hour, minute, label, color in anchors:
            exchange_time = datetime(
                current_day.year,
                current_day.month,
                current_day.day,
                hour,
                minute,
                tzinfo=exchange_tz,
            )
            utc_time = exchange_time.astimezone(timezone.utc)
            if first_utc <= utc_time <= latest_utc:
                specs.append((chart_display_time(utc_time, display.display_tz), label, color))
        current_day += timedelta(days=1)
    return specs


def clear_session_markers(display: ChartDisplayState) -> None:
    for marker in display.session_marker_objects:
        delete = getattr(marker, "delete", None)
        if callable(delete):
            try:
                delete()
            except Exception:
                pass
    display.session_marker_objects.clear()


def refresh_session_markers(
    chart: object,
    display: ChartDisplayState,
    status: ChartStatus,
) -> None:
    clear_session_markers(display)
    vertical_line = getattr(chart, "vertical_line", None)
    if not callable(vertical_line):
        return
    for marker_time, label, color in session_marker_specs(display, status):
        try:
            marker = vertical_line(
                marker_time,
                color=color,
                width=1,
                style="dotted",
                text=label,
            )
        except Exception:
            continue
        display.session_marker_objects.append(marker)


def record_value(record: object, name: str) -> object:
    if not hasattr(record, name):
        raise ValueError(f"missing field: {name}")
    value = getattr(record, name)
    return value() if callable(value) else value


def record_error_text(record: object) -> str:
    values: list[str] = []
    for name in ("err", "message", "msg"):
        if not hasattr(record, name):
            continue
        try:
            value = record_value(record, name)
        except Exception:
            continue
        if value:
            values.append(str(value))
    return " ".join(values)


def parse_allowed_start_from_text(value: str) -> datetime | None:
    match = START_CLAMP_PATTERN.search(value)
    if match is None:
        return None
    try:
        return normalize_ts_event(match.group(1))
    except Exception:
        return None


def parse_available_end_from_text(value: str) -> datetime | None:
    match = AVAILABLE_END_PATTERN.search(value)
    if match is None:
        return None
    try:
        return normalize_ts_event(match.group(1))
    except Exception:
        return None


def provider_start_clamp_from_record(record: object) -> ProviderStartClamp | None:
    if "Error" not in type(record).__name__:
        return None
    text = record_error_text(record)
    allowed_start = parse_allowed_start_from_text(text)
    if allowed_start is None:
        return None
    return ProviderStartClamp(allowed_start=allowed_start, message=text)


def ohlcv_record_to_candle(record: object) -> dict[str, CandleValue]:
    missing = missing_ohlcv_fields(record)
    if missing:
        raise ValueError(
            f"{type(record).__name__} is not an OHLCV record; missing fields: "
            + ", ".join(missing)
        )

    return {
        "time": normalize_ts_event(record_value(record, "ts_event")),
        "open": fixed_price_to_float(record_value(record, "open")),
        "high": fixed_price_to_float(record_value(record, "high")),
        "low": fixed_price_to_float(record_value(record, "low")),
        "close": fixed_price_to_float(record_value(record, "close")),
        "volume": int(cast(Any, record_value(record, "volume"))),
    }


def dataframe_row_to_candle(row: object) -> dict[str, CandleValue]:
    return {
        "time": normalize_ts_event(record_value(row, "ts_event")),
        "open": fixed_price_to_float(record_value(row, "open")),
        "high": fixed_price_to_float(record_value(row, "high")),
        "low": fixed_price_to_float(record_value(row, "low")),
        "close": fixed_price_to_float(record_value(row, "close")),
        "volume": int(cast(Any, record_value(row, "volume"))),
    }


def historical_store_to_candles(store: object) -> list[dict[str, CandleValue]]:
    pandas_module = importlib.import_module("pandas")
    to_df = getattr(store, "to_df")
    frame_or_frames = to_df(
        price_type="float",
        pretty_ts=True,
        map_symbols=True,
    )
    if isinstance(frame_or_frames, pandas_module.DataFrame):
        frame = frame_or_frames
    else:
        frames = list(frame_or_frames)
        if not frames:
            return []
        frame = pandas_module.concat(frames, ignore_index=False)

    if frame.empty:
        return []
    if "ts_event" not in frame.columns:
        if isinstance(frame.index, pandas_module.DatetimeIndex):
            frame = frame.reset_index()
            if frame.columns[0] != "ts_event":
                frame = frame.rename(columns={frame.columns[0]: "ts_event"})
        else:
            raise ValueError("historical data has no ts_event column or DatetimeIndex")

    missing = sorted(set(OHLCV_FIELDS) - set(frame.columns))
    if missing:
        raise ValueError(f"historical data missing required columns: {missing}")

    return [
        dataframe_row_to_candle(row)
        for row in frame.sort_values("ts_event", kind="mergesort").itertuples(
            index=False,
        )
    ]


def describe_record_skip(record: object, exc: Exception) -> str:
    return f"Skipping {type(record).__name__}: {exc}"


def missing_ohlcv_fields(record: object) -> list[str]:
    return [field for field in OHLCV_FIELDS if not hasattr(record, field)]


def should_ignore_record(record: object, exc: Exception) -> bool:
    record_type = type(record).__name__
    if any(marker in record_type for marker in ALWAYS_REPORTED_RECORD_TYPE_MARKERS):
        return False
    if "missing fields" not in str(exc):
        return False
    return not any(hasattr(record, field) for field in OHLCV_PAYLOAD_FIELDS)


def import_databento() -> ModuleType:
    return importlib.import_module("databento")


def import_chart_runtime() -> tuple[type[Any], Callable[[dict[str, CandleValue]], Any]]:
    try:
        chart_module = importlib.import_module("lightweight_charts")
    except ModuleNotFoundError as exc:
        if exc.name == "lightweight_charts":
            raise RuntimeError(CHART_INSTALL_MESSAGE) from exc
        raise

    try:
        pandas_module = importlib.import_module("pandas")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing pandas package; install project requirements before running the chart."
        ) from exc

    return chart_module.Chart, pandas_module.Series


def build_record_callback(
    candle_queue: queue.Queue[ChartQueueItem],
    *,
    stderr: TextIO,
    allow_start_clamp: bool = True,
) -> Callable[[object], None]:
    def handle_record(record: object) -> None:
        try:
            candle = ohlcv_record_to_candle(record)
        except Exception as exc:
            start_clamp = (
                provider_start_clamp_from_record(record)
                if allow_start_clamp
                else None
            )
            if start_clamp is not None:
                candle_queue.put(start_clamp)
                return
            if should_ignore_record(record, exc):
                return
            print(describe_record_skip(record, exc), file=stderr)
            return
        candle_queue.put(candle)

    return handle_record


def call_if_available(target: object, name: str, **kwargs: object) -> None:
    method = getattr(target, name, None)
    if not callable(method):
        return
    try:
        method(**kwargs)
    except TypeError:
        method()


def configure_chart(
    chart: object,
    title: str,
    *,
    timeframe_options: Sequence[str] = (),
    selected_timeframe: str | None = None,
    on_timeframe_change: Callable[[object], None] | None = None,
    status_text: str = LOADING_STATUS_TEXT,
) -> None:
    call_if_available(
        chart,
        "layout",
        background_color="#131722",
        text_color="#d1d4dc",
        font_size=12,
        font_family="Arial",
    )
    call_if_available(
        chart,
        "candle_style",
        up_color="#26a69a",
        down_color="#ef5350",
        border_up_color="#26a69a",
        border_down_color="#ef5350",
        wick_up_color="#26a69a",
        wick_down_color="#ef5350",
    )
    call_if_available(
        chart,
        "volume_config",
        up_color="rgba(38, 166, 154, 0.45)",
        down_color="rgba(239, 83, 80, 0.45)",
    )
    call_if_available(
        chart,
        "legend",
        visible=True,
        ohlc=True,
        percent=False,
        color_based_on_candle=True,
        font_size=12,
        font_family="Arial",
    )
    call_if_available(chart, "precision", precision=2)
    call_if_available(
        chart,
        "crosshair",
        vert_color="#9aa4b2",
        horz_color="#9aa4b2",
        vert_style="large_dashed",
        horz_style="large_dashed",
        vert_label_background_color="#2f3542",
        horz_label_background_color="#2f3542",
    )
    call_if_available(
        chart,
        "price_scale",
        scale_margin_top=0.10,
        scale_margin_bottom=0.18,
        border_visible=True,
        border_color="#2a2e39",
        text_color="#d1d4dc",
        minimum_width=80,
    )
    update_chart_title(chart, title)
    configure_timeframe_switcher(
        chart,
        timeframe_options=timeframe_options,
        selected_timeframe=selected_timeframe,
        on_timeframe_change=on_timeframe_change,
    )
    configure_status_text(chart, status_text)


def configure_timeframe_switcher(
    chart: object,
    *,
    timeframe_options: Sequence[str],
    selected_timeframe: str | None,
    on_timeframe_change: Callable[[object], None] | None,
) -> None:
    if not timeframe_options or selected_timeframe is None:
        return
    topbar = getattr(chart, "topbar", None)
    switcher = getattr(topbar, "switcher", None)
    if not callable(switcher):
        return
    switcher(
        "timeframe",
        tuple(timeframe_options),
        default=selected_timeframe,
        func=on_timeframe_change,
    )


def update_chart_title(chart: object, title: str) -> None:
    call_if_available(chart, "watermark", text=title, color="rgba(209, 212, 220, 0.20)")


def show_chart(chart: object) -> None:
    show = getattr(chart, "show", None)
    if not callable(show):
        return
    try:
        show(block=False)
    except TypeError:
        show()


def chart_is_alive(chart: object) -> bool:
    """Best-effort compatibility hook.

    lightweight_charts.Chart 2.1 does not expose a reliable close-state API, so
    real v1 runs are bounded by max records, timeout, and Ctrl+C.
    """

    value = getattr(chart, "is_alive", True)
    return bool(value() if callable(value) else value)


def cleanup_chart(chart: object | None) -> None:
    if chart is None:
        return
    for name in ("exit", "close"):
        method = getattr(chart, name, None)
        if callable(method):
            method()
            return


def update_chart_candle(chart: object, series: object, *, initialize: bool) -> None:
    if initialize:
        set_data = getattr(chart, "set", None)
        to_frame = getattr(series, "to_frame", None)
        if callable(set_data) and callable(to_frame):
            set_data(cast(Any, to_frame()).T)
        return
    cast(Any, chart).update(series)


def replace_chart_candles(
    chart: object,
    candles: Sequence[dict[str, CandleValue]],
    *,
    series_factory: Callable[[dict[str, CandleValue]], Any],
) -> None:
    set_data = getattr(chart, "set", None)
    if not callable(set_data):
        return

    pandas_module = importlib.import_module("pandas")
    frame = pandas_module.DataFrame(candles)
    if not frame.empty:
        frame["time"] = pandas_module.to_datetime(frame["time"])
        if getattr(frame["time"].dt, "tz", None) is not None:
            frame["time"] = frame["time"].dt.tz_localize(None)
        frame["time"] = frame["time"].astype("datetime64[ns]")
    set_data(frame)


def apply_candle_status(status: ChartStatus, candle: dict[str, CandleValue]) -> None:
    candle_time = normalize_ts_event(candle["time"])
    close = candle_float(candle["close"])
    if status.first_time is None:
        status.first_time = candle_time
    status.latest_time = candle_time
    status.last_close = close
    status.records_updated += 1


def append_display_candle(
    display: ChartDisplayState,
    status: ChartStatus,
    candle: dict[str, CandleValue],
) -> None:
    display.raw_candles.append(candle)
    apply_candle_status(status, candle)


def append_display_candle_batch(
    candle_queue: queue.Queue[ChartQueueItem],
    *,
    first_candle: dict[str, CandleValue],
    display: ChartDisplayState,
    status: ChartStatus,
    max_records: int,
) -> bool:
    append_display_candle(display, status, first_candle)
    while (
        status.records_updated < max_records or max_records == 0
    ) and len(display.raw_candles) % CHART_RENDER_BATCH_RECORDS != 0:
        try:
            candle = candle_queue.get(timeout=CHART_RENDER_BATCH_WAIT_SECONDS)
        except queue.Empty:
            return True
        if isinstance(candle, ProviderStartClamp):
            candle_queue.put(candle)
            return False
        append_display_candle(display, status, candle)
    return candle_queue.empty()


def render_chart_display(
    display: ChartDisplayState,
    *,
    chart: object,
    series_factory: Callable[[dict[str, CandleValue]], Any],
    status: ChartStatus,
    symbols: str,
    schema: str,
    mode: str,
    stdout: TextIO,
) -> None:
    aggregated = aggregate_candles(
        display.raw_candles,
        seconds=display.timeframe_seconds,
    )
    display_candles = [
        candle_for_display(candle, display_tz=display.display_tz)
        for candle in aggregated
    ]
    replace_chart_candles(chart, display_candles, series_factory=series_factory)
    refresh_session_markers(chart, display, status)
    update_chart_title(
        chart,
        format_chart_title(
            symbols=symbols,
            schema=schema,
            mode=mode,
            chart_timeframe=display.timeframe,
            display_tz=display.display_tz,
            display_tz_name=display.display_tz_name,
            status=status,
        ),
    )
    update_chart_status_text(
        chart,
        format_topbar_status(symbols=symbols, display=display, status=status),
    )
    emit_status_line(status, stdout)


def emit_status_line(status: ChartStatus, stdout: TextIO) -> None:
    stdout.write("\rLive chart status: " + format_chart_status(status))
    stdout.flush()
    status.status_line_printed = True


def finish_status_line(status: ChartStatus, stdout: TextIO) -> None:
    if status.status_line_printed:
        print(file=stdout)
        status.status_line_printed = False


def apply_chart_candle(
    candle: dict[str, CandleValue],
    *,
    chart: object,
    series_factory: Callable[[dict[str, CandleValue]], Any],
    status: ChartStatus,
    symbols: str,
    schema: str,
    mode: str,
    stdout: TextIO,
    chart_timeframe: str | None = None,
    display_tz: tzinfo = timezone.utc,
    display_tz_name: str = "UTC",
) -> None:
    update_chart_candle(
        chart,
        series_factory(candle_for_display(candle, display_tz=display_tz)),
        initialize=status.records_updated == 0,
    )
    apply_candle_status(status, candle)
    update_chart_title(
        chart,
        format_chart_title(
            symbols=symbols,
            schema=schema,
            mode=mode,
            chart_timeframe=chart_timeframe or schema.removeprefix("ohlcv-"),
            display_tz=display_tz,
            display_tz_name=display_tz_name,
            status=status,
        ),
    )
    emit_status_line(status, stdout)


def stop_live_client(live: object | None) -> None:
    if live is None:
        return

    stop = getattr(live, "stop", None)
    if callable(stop):
        stop()

    wait_for_close = getattr(live, "block_for_close", None)
    if not callable(wait_for_close):
        return

    try:
        wait_for_close(timeout=1.0)
    except TypeError:
        wait_for_close()
    except Exception:
        return


def clear_queue_values(values: queue.Queue[ChartQueueItem]) -> None:
    while True:
        try:
            values.get_nowait()
        except queue.Empty:
            return


def reset_status(status: ChartStatus) -> None:
    status.records_updated = 0
    status.first_time = None
    status.latest_time = None
    status.last_close = None
    status.status_line_printed = False


def build_timeframe_callback(
    timeframe_queue: queue.Queue[str],
) -> Callable[[object], None]:
    def handle_timeframe_change(chart: object) -> None:
        try:
            selected = cast(Any, chart).topbar["timeframe"].value
        except Exception:
            return
        timeframe_queue.put(str(selected))

    return handle_timeframe_change


def drain_timeframe_queue(
    timeframe_queue: queue.Queue[str],
    *,
    display: ChartDisplayState,
    chart_timeframes: Sequence[str],
) -> bool:
    changed = False
    allowed = set(chart_timeframes)
    while True:
        try:
            selected = timeframe_queue.get_nowait()
        except queue.Empty:
            return changed
        if selected not in allowed or selected == display.timeframe:
            continue
        display.timeframe = selected
        display.timeframe_seconds = timeframe_seconds(selected)
        changed = True


def parse_chart_event_message(chart: object, response: str) -> tuple[Callable[..., object], list[str]]:
    name, raw_args = response.split("_~_", 1)
    args = raw_args.split(";;;")
    handlers = getattr(getattr(chart, "win"), "handlers")
    return handlers[name], args


def drain_chart_event_queue(chart: object, stderr: TextIO) -> bool:
    chart_cls = type(chart)
    webview_handler = getattr(chart_cls, "WV", None)
    emit_queue = getattr(webview_handler, "emit_queue", None)
    if emit_queue is None:
        return False

    chart_closed = False
    while not emit_queue.empty():
        response = emit_queue.get()
        if response == "exit":
            exit_chart = getattr(webview_handler, "exit", None)
            if callable(exit_chart):
                exit_chart()
            if hasattr(chart, "is_alive"):
                setattr(chart, "is_alive", False)
            chart_closed = True
            continue

        try:
            func, args = parse_chart_event_message(chart, response)
            if asyncio.iscoroutinefunction(func):
                asyncio.run(func(*args))
            else:
                func(*args)
        except Exception as exc:
            print(f"Chart UI event skipped: {exc}", file=stderr)
    return chart_closed


@dataclass
class ChartRunResult:
    records_updated: int
    timed_out: bool
    chart_closed: bool
    first_time: datetime | None = None
    latest_time: datetime | None = None
    last_close: float | None = None
    no_data_warned: bool = False
    retry_start: datetime | None = None
    provider_message: str | None = None


def chart_result(
    status: ChartStatus,
    *,
    timed_out: bool,
    chart_closed: bool,
    no_data_warned: bool,
    retry_start: datetime | None = None,
    provider_message: str | None = None,
) -> ChartRunResult:
    return ChartRunResult(
        records_updated=status.records_updated,
        timed_out=timed_out,
        chart_closed=chart_closed,
        first_time=status.first_time,
        latest_time=status.latest_time,
        last_close=status.last_close,
        no_data_warned=no_data_warned,
        retry_start=retry_start,
        provider_message=provider_message,
    )


def drain_chart_queue(
    candle_queue: queue.Queue[ChartQueueItem],
    *,
    chart: object,
    series_factory: Callable[[dict[str, CandleValue]], Any],
    display: ChartDisplayState,
    timeframe_queue: queue.Queue[str],
    chart_timeframes: Sequence[str],
    max_records: int,
    timeout_seconds: float | None,
    no_data_warning_seconds: float,
    status: ChartStatus,
    symbols: str,
    schema: str,
    mode: str,
    stdout: TextIO,
    stderr: TextIO,
    clock: Callable[[], float] = time.monotonic,
) -> ChartRunResult:
    started_at = clock()
    deadline = None if timeout_seconds is None else started_at + timeout_seconds
    warning_deadline = (
        None
        if no_data_warning_seconds <= 0 or status.records_updated > 0
        else started_at + no_data_warning_seconds
    )
    chart_closed = False
    no_data_warned = False
    last_render_at = started_at
    pending_render = False

    while max_records == 0 or status.records_updated < max_records:
        if drain_chart_event_queue(chart, stderr):
            chart_closed = True
            break

        if drain_timeframe_queue(
            timeframe_queue,
            display=display,
            chart_timeframes=chart_timeframes,
        ):
            if status.records_updated > 0:
                display.loading = False
            render_chart_display(
                display,
                chart=chart,
                series_factory=series_factory,
                status=status,
                symbols=symbols,
                schema=schema,
                mode=mode,
                stdout=stdout,
            )
            last_render_at = clock()
            pending_render = False

        if not chart_is_alive(chart):
            chart_closed = True
            break

        now = clock()
        if deadline is None:
            wait_seconds = 0.10
        else:
            remaining = deadline - now
            if remaining <= 0:
                return chart_result(
                    status,
                    timed_out=True,
                    chart_closed=False,
                    no_data_warned=no_data_warned,
                )
            wait_seconds = min(0.10, remaining)

        try:
            item = candle_queue.get(timeout=wait_seconds)
        except queue.Empty:
            if pending_render:
                if status.records_updated > 0:
                    display.loading = False
                render_chart_display(
                    display,
                    chart=chart,
                    series_factory=series_factory,
                    status=status,
                    symbols=symbols,
                    schema=schema,
                    mode=mode,
                    stdout=stdout,
                )
                last_render_at = clock()
                pending_render = False
            elif display.loading and status.records_updated > 0:
                display.loading = False
                update_chart_status_text(
                    chart,
                    format_topbar_status(
                        symbols=symbols,
                        display=display,
                        status=status,
                    ),
                )
            if (
                warning_deadline is not None
                and not no_data_warned
                and status.records_updated == 0
                and clock() >= warning_deadline
            ):
                print(
                    "No OHLCV records received after "
                    f"{no_data_warning_seconds:g}s for {symbols} {schema}.",
                    file=stderr,
                )
                no_data_warned = True
            continue

        if isinstance(item, ProviderStartClamp):
            return chart_result(
                status,
                timed_out=False,
                chart_closed=False,
                no_data_warned=no_data_warned,
                retry_start=item.allowed_start,
                provider_message=item.message,
            )

        queue_drained = append_display_candle_batch(
            candle_queue,
            first_candle=item,
            display=display,
            status=status,
            max_records=max_records,
        )
        pending_render = True
        update_chart_status_text(
            chart,
            format_topbar_status(symbols=symbols, display=display, status=status),
        )
        now_after_batch = clock()
        max_records_reached = max_records != 0 and status.records_updated >= max_records
        if (
            queue_drained
            or max_records_reached
            or now_after_batch - last_render_at >= CHART_RENDER_THROTTLE_SECONDS
        ):
            if queue_drained and status.records_updated > 0:
                display.loading = False
            render_chart_display(
                display,
                chart=chart,
                series_factory=series_factory,
                status=status,
                symbols=symbols,
                schema=schema,
                mode=mode,
                stdout=stdout,
            )
            last_render_at = now_after_batch
            pending_render = False

    return chart_result(
        status,
        timed_out=False,
        chart_closed=chart_closed,
        no_data_warned=no_data_warned,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Optional local Databento live OHLCV candlestick chart for "
            "research/paper observation only. No orders, broker integration, "
            "account integration, or live inference."
        )
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--symbols", default=DEFAULT_SYMBOLS)
    parser.add_argument("--stype-in", default=DEFAULT_STYPE_IN)
    parser.add_argument(
        "--chart-timeframe",
        type=normalize_timeframe,
        default=DEFAULT_CHART_TIMEFRAME,
        help="Initial displayed chart timeframe; must be in --chart-timeframes.",
    )
    parser.add_argument(
        "--chart-timeframes",
        default=DEFAULT_CHART_TIMEFRAMES,
        help="Comma-separated topbar chart timeframes built from the source OHLCV feed.",
    )
    parser.add_argument(
        "--display-tz",
        default=DEFAULT_DISPLAY_TZ,
        help="Timezone for chart axis/title display: local, UTC, or an IANA name.",
    )
    window_group = parser.add_mutually_exclusive_group()
    window_group.add_argument(
        "--start",
        default=None,
        help="Live replay start. Use 0 for all available intraday replay.",
    )
    window_group.add_argument(
        "--lookback-hours",
        type=positive_float,
        default=None,
        help="Replay this many hours before now; default is 168.",
    )
    window_group.add_argument(
        "--lookback-days",
        type=positive_float,
        default=None,
        help="Replay this many days before now.",
    )
    parser.add_argument(
        "--max-records",
        type=nonnegative_int,
        default=DEFAULT_MAX_RECORDS,
        help="Maximum OHLCV records to plot before stopping. Use 0 for unlimited.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=nonnegative_float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Maximum runtime after subscription. Omit for no timeout.",
    )
    parser.add_argument(
        "--no-data-warning-seconds",
        type=nonnegative_float,
        default=DEFAULT_NO_DATA_WARNING_SECONDS,
        help="Warn if no OHLCV candles arrive by this many seconds; 0 disables.",
    )
    parser.add_argument(
        "--historical-backfill",
        action="store_true",
        help="Seed bounded windows from Databento Historical before live streaming.",
    )
    return parser


def run_live_chart(
    args: argparse.Namespace,
    *,
    env: dict[str, str] | None = None,
    db_module: ModuleType | None = None,
    chart_factory: Callable[[], object] | None = None,
    series_factory: Callable[[dict[str, CandleValue]], Any] | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    now: datetime | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    api_key = resolve_api_key(env)
    if api_key is None:
        print(f"Missing {API_KEY_ENV}; set it before running live chart.", file=stderr)
        return 2

    current_time = now or utc_now()
    live_start = resolve_window_start(args, now=current_time)
    historical_end = current_time
    if args.historical_backfill and live_start in {None, 0}:
        print(
            "Historical backfill requires a bounded --lookback-hours, "
            "--lookback-days, or timestamp --start.",
            file=stderr,
        )
        return 2

    try:
        chart_timeframes = parse_chart_timeframes(args.chart_timeframes)
        chart_timeframe = normalize_timeframe(args.chart_timeframe)
        display_tz, display_tz_name = resolve_display_tz(args.display_tz)
    except argparse.ArgumentTypeError as exc:
        print(str(exc), file=stderr)
        return 2

    timeframe_error = validate_chart_timeframe(
        chart_timeframe=chart_timeframe,
        chart_timeframes=chart_timeframes,
        schema=args.schema,
    )
    if timeframe_error is not None:
        print(timeframe_error, file=stderr)
        return 2

    if db_module is None:
        try:
            db_module = import_databento()
        except ModuleNotFoundError:
            print(
                "Missing databento package; install project requirements before "
                "running live chart.",
                file=stderr,
            )
            return 2

    if chart_factory is None or series_factory is None:
        try:
            chart_cls, runtime_series_factory = import_chart_runtime()
        except RuntimeError as exc:
            print(str(exc), file=stderr)
            return 2
        chart_factory = chart_factory or chart_cls
        series_factory = series_factory or runtime_series_factory

    timeframe_queue: queue.Queue[str] = queue.Queue()
    live = None
    chart = None
    status = ChartStatus()
    mode = "historical+live" if args.historical_backfill else "live replay"
    display = ChartDisplayState(
        raw_candles=[],
        timeframe=chart_timeframe,
        timeframe_seconds=timeframe_seconds(chart_timeframe),
        display_tz=display_tz,
        display_tz_name=display_tz_name,
    )

    try:
        chart = chart_factory()
        configure_chart(
            chart,
            title=format_chart_title(
                symbols=args.symbols,
                schema=args.schema,
                mode=mode,
                chart_timeframe=display.timeframe,
                display_tz=display.display_tz,
                display_tz_name=display.display_tz_name,
            ),
            timeframe_options=chart_timeframes,
            selected_timeframe=display.timeframe,
            on_timeframe_change=build_timeframe_callback(timeframe_queue),
            status_text=LOADING_STATUS_TEXT,
        )
        show_chart(chart)
        symbols = parse_symbols(args.symbols)

        if args.historical_backfill:
            historical_cls = getattr(db_module, "Historical", None)
            if historical_cls is None:
                raise RuntimeError("Databento Historical client is unavailable.")
            historical = historical_cls(key=api_key)
            historical_request = {
                "dataset": args.dataset,
                "schema": args.schema,
                "symbols": symbols,
                "stype_in": args.stype_in,
                "start": live_start,
                "end": historical_end,
            }
            try:
                store = historical.timeseries.get_range(**historical_request)
            except Exception as exc:
                retry_end = parse_available_end_from_text(str(exc))
                if retry_end is None:
                    raise
                historical_end = retry_end
                historical_request["end"] = historical_end
                store = historical.timeseries.get_range(**historical_request)
            for candle in historical_store_to_candles(store):
                display.raw_candles.append(candle)
                apply_candle_status(status, candle)
            if display.raw_candles:
                render_chart_display(
                    display,
                    chart=chart,
                    series_factory=series_factory,
                    status=status,
                    symbols=args.symbols,
                    schema=args.schema,
                    mode=mode,
                    stdout=stdout,
                )
            live_start = historical_end

        retried_clamped_start = False
        while True:
            candle_queue: queue.Queue[ChartQueueItem] = queue.Queue()
            live = db_module.Live(key=api_key)
            try:
                live.subscribe(
                    dataset=args.dataset,
                    schema=args.schema,
                    symbols=symbols,
                    stype_in=args.stype_in,
                    start=live_start,
                )
            except Exception as exc:
                retry_start = parse_allowed_start_from_text(str(exc))
                if retry_start is None or retried_clamped_start:
                    raise
                stop_live_client(live)
                live = None
                retried_clamped_start = True
                live_start = retry_start
                display.loading = True
                update_chart_status_text(
                    chart,
                    f"{LOADING_STATUS_TEXT} retrying from {format_utc_time(live_start)}",
                )
                continue

            live.add_callback(
                build_record_callback(
                    candle_queue,
                    stderr=stderr,
                    allow_start_clamp=not retried_clamped_start,
                )
            )
            live.start()

            result = drain_chart_queue(
                candle_queue,
                chart=chart,
                series_factory=series_factory,
                display=display,
                timeframe_queue=timeframe_queue,
                chart_timeframes=chart_timeframes,
                max_records=args.max_records,
                timeout_seconds=args.timeout_seconds,
                no_data_warning_seconds=args.no_data_warning_seconds,
                status=status,
                symbols=args.symbols,
                schema=args.schema,
                mode=mode,
                stdout=stdout,
                stderr=stderr,
                clock=clock,
            )
            if result.retry_start is None or retried_clamped_start:
                break

            finish_status_line(status, stdout)
            print(
                "Databento replay start too old; retrying from "
                f"{format_utc_time(result.retry_start)}.",
                file=stdout,
            )
            stop_live_client(live)
            live = None
            clear_queue_values(candle_queue)
            clear_session_markers(display)
            display.raw_candles.clear()
            display.loading = True
            reset_status(status)
            replace_chart_candles(chart, [], series_factory=series_factory)
            update_chart_status_text(
                chart,
                f"{LOADING_STATUS_TEXT} retrying from {format_utc_time(result.retry_start)}",
            )
            live_start = result.retry_start
            retried_clamped_start = True

        finish_status_line(status, stdout)
        print(
            "Live chart stopped: "
            f"records_updated={result.records_updated} "
            f"first={format_utc_time(result.first_time)} "
            f"latest={format_utc_time(result.latest_time)} "
            f"last_close={format_close(result.last_close)} "
            f"timed_out={result.timed_out} chart_closed={result.chart_closed}",
            file=stdout,
        )
        return 0
    except KeyboardInterrupt:
        finish_status_line(status, stdout)
        print("Interrupted; stopping live chart.", file=stderr)
        return 130
    except Exception as exc:
        finish_status_line(status, stdout)
        print(f"Databento live chart failed: {exc}", file=stderr)
        return 1
    finally:
        stop_live_client(live)
        cleanup_chart(chart)


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if should_launch_vscode_run_child(raw_args):
        return launch_vscode_run_child()
    parser = build_arg_parser()
    args = parser.parse_args(resolve_main_argv(raw_args))
    return run_live_chart(args)


if __name__ == "__main__":
    raise SystemExit(main())
