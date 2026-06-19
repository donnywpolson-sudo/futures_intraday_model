#!/usr/bin/env python3
"""Optional Databento live OHLCV chart for research observation only."""

from __future__ import annotations

import argparse
import importlib
import queue
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Sequence, TextIO

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.databento_auth import (
    load_databento_api_key_from_file,
    resolve_databento_api_key,
)


DEFAULT_DATASET = "GLBX.MDP3"
DEFAULT_SCHEMA = "ohlcv-1m"
DEFAULT_SYMBOLS = "ES.c.0"
DEFAULT_STYPE_IN = "continuous"
DEFAULT_LOOKBACK_HOURS = 6.0
DEFAULT_MAX_RECORDS = 0
DEFAULT_TIMEOUT_SECONDS: float | None = None
DEFAULT_NO_DATA_WARNING_SECONDS = 60.0
API_KEY_ENV = "DATABENTO_API_KEY"
ROOT_API_KEY_FILE = ROOT / "databento.env"
FIXED_PRICE_SCALE = 1_000_000_000
UNDEF_PRICE = 9_223_372_036_854_775_807
OHLCV_FIELDS = ("ts_event", "open", "high", "low", "close", "volume")
OHLCV_PAYLOAD_FIELDS = ("open", "high", "low", "close", "volume")
ALWAYS_REPORTED_RECORD_TYPE_MARKERS = ("Error",)
CHART_INSTALL_MESSAGE = (
    'Missing lightweight-charts package; install optional chart support with: '
    'python -m pip install "lightweight-charts>=2.1,<3"'
)
CandleValue = datetime | int | float
SubscriptionStart = datetime | str | int | None


@dataclass
class ChartStatus:
    records_updated: int = 0
    first_time: datetime | None = None
    latest_time: datetime | None = None
    last_close: float | None = None
    status_line_printed: bool = False


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


def parse_start(value: str | None) -> str | int | None:
    if value is None or value == "":
        return None
    if value == "0":
        return 0
    return value


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
    status: ChartStatus | None = None,
) -> str:
    if status is None or status.latest_time is None:
        return f"{symbols} {schema} | connecting"
    return (
        f"{symbols} {schema} | {mode} | "
        f"first={format_utc_time(status.first_time)} "
        f"last={format_utc_time(status.latest_time)}"
    )


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


def record_value(record: object, name: str) -> object:
    if not hasattr(record, name):
        raise ValueError(f"missing field: {name}")
    value = getattr(record, name)
    return value() if callable(value) else value


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
        "volume": int(record_value(record, "volume")),
    }


def dataframe_row_to_candle(row: object) -> dict[str, CandleValue]:
    return {
        "time": normalize_ts_event(record_value(row, "ts_event")),
        "open": fixed_price_to_float(record_value(row, "open")),
        "high": fixed_price_to_float(record_value(row, "high")),
        "low": fixed_price_to_float(record_value(row, "low")),
        "close": fixed_price_to_float(record_value(row, "close")),
        "volume": int(record_value(row, "volume")),
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
    candle_queue: queue.Queue[dict[str, CandleValue]],
    *,
    stderr: TextIO,
) -> Callable[[object], None]:
    def handle_record(record: object) -> None:
        try:
            candle = ohlcv_record_to_candle(record)
        except Exception as exc:
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


def configure_chart(chart: object, title: str) -> None:
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
    call_if_available(chart, "legend", visible=True)
    update_chart_title(chart, title)


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
            set_data(to_frame().T)
            return
    chart.update(series)


def apply_candle_status(status: ChartStatus, candle: dict[str, CandleValue]) -> None:
    candle_time = normalize_ts_event(candle["time"])
    close = float(candle["close"])
    if status.first_time is None:
        status.first_time = candle_time
    status.latest_time = candle_time
    status.last_close = close
    status.records_updated += 1


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
) -> None:
    update_chart_candle(
        chart,
        series_factory(candle),
        initialize=status.records_updated == 0,
    )
    apply_candle_status(status, candle)
    update_chart_title(
        chart,
        format_chart_title(symbols=symbols, schema=schema, mode=mode, status=status),
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


@dataclass
class ChartRunResult:
    records_updated: int
    timed_out: bool
    chart_closed: bool
    first_time: datetime | None = None
    latest_time: datetime | None = None
    last_close: float | None = None
    no_data_warned: bool = False


def chart_result(
    status: ChartStatus,
    *,
    timed_out: bool,
    chart_closed: bool,
    no_data_warned: bool,
) -> ChartRunResult:
    return ChartRunResult(
        records_updated=status.records_updated,
        timed_out=timed_out,
        chart_closed=chart_closed,
        first_time=status.first_time,
        latest_time=status.latest_time,
        last_close=status.last_close,
        no_data_warned=no_data_warned,
    )


def drain_chart_queue(
    candle_queue: queue.Queue[dict[str, CandleValue]],
    *,
    chart: object,
    series_factory: Callable[[dict[str, CandleValue]], Any],
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

    while max_records == 0 or status.records_updated < max_records:
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
            candle = candle_queue.get(timeout=wait_seconds)
        except queue.Empty:
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

        apply_chart_candle(
            candle,
            chart=chart,
            series_factory=series_factory,
            status=status,
            symbols=symbols,
            schema=schema,
            mode=mode,
            stdout=stdout,
        )

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
        help="Replay this many hours before now; default is 6.",
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

    candle_queue: queue.Queue[dict[str, CandleValue]] = queue.Queue()
    live = None
    chart = None
    status = ChartStatus()
    mode = "historical+live" if args.historical_backfill else "live replay"

    try:
        chart = chart_factory()
        configure_chart(
            chart,
            title=format_chart_title(
                symbols=args.symbols,
                schema=args.schema,
                mode=mode,
            ),
        )
        show_chart(chart)
        symbols = parse_symbols(args.symbols)

        if args.historical_backfill:
            historical_cls = getattr(db_module, "Historical", None)
            if historical_cls is None:
                raise RuntimeError("Databento Historical client is unavailable.")
            historical = historical_cls(key=api_key)
            store = historical.timeseries.get_range(
                dataset=args.dataset,
                schema=args.schema,
                symbols=symbols,
                stype_in=args.stype_in,
                start=live_start,
                end=historical_end,
            )
            for candle in historical_store_to_candles(store):
                apply_chart_candle(
                    candle,
                    chart=chart,
                    series_factory=series_factory,
                    status=status,
                    symbols=args.symbols,
                    schema=args.schema,
                    mode=mode,
                    stdout=stdout,
                )
            live_start = historical_end

        live = db_module.Live(key=api_key)
        live.subscribe(
            dataset=args.dataset,
            schema=args.schema,
            symbols=symbols,
            stype_in=args.stype_in,
            start=live_start,
        )
        live.add_callback(build_record_callback(candle_queue, stderr=stderr))
        live.start()

        result = drain_chart_queue(
            candle_queue,
            chart=chart,
            series_factory=series_factory,
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
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run_live_chart(args)


if __name__ == "__main__":
    raise SystemExit(main())
