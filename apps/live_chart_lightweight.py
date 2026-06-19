#!/usr/bin/env python3
"""Optional Databento live OHLCV chart for research observation only."""

from __future__ import annotations

import argparse
import importlib
import queue
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Sequence, TextIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.databento_auth import resolve_databento_api_key


DEFAULT_DATASET = "GLBX.MDP3"
DEFAULT_SCHEMA = "ohlcv-1m"
DEFAULT_SYMBOLS = "ES.c.0"
DEFAULT_STYPE_IN = "continuous"
DEFAULT_START = "0"
DEFAULT_MAX_RECORDS = 0
DEFAULT_TIMEOUT_SECONDS: float | None = None
API_KEY_ENV = "DATABENTO_API_KEY"
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


def resolve_api_key(env: dict[str, str] | None = None) -> str | None:
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


def drain_chart_queue(
    candle_queue: queue.Queue[dict[str, CandleValue]],
    *,
    chart: object,
    series_factory: Callable[[dict[str, CandleValue]], Any],
    max_records: int,
    timeout_seconds: float | None,
    clock: Callable[[], float] = time.monotonic,
) -> ChartRunResult:
    deadline = None if timeout_seconds is None else clock() + timeout_seconds
    records_updated = 0
    chart_closed = False

    while max_records == 0 or records_updated < max_records:
        if not chart_is_alive(chart):
            chart_closed = True
            break

        if deadline is None:
            wait_seconds = 0.10
        else:
            remaining = deadline - clock()
            if remaining <= 0:
                return ChartRunResult(
                    records_updated,
                    timed_out=True,
                    chart_closed=False,
                )
            wait_seconds = min(0.10, remaining)

        try:
            candle = candle_queue.get(timeout=wait_seconds)
        except queue.Empty:
            continue

        update_chart_candle(
            chart,
            series_factory(candle),
            initialize=records_updated == 0,
        )
        records_updated += 1

    return ChartRunResult(
        records_updated=records_updated,
        timed_out=False,
        chart_closed=chart_closed,
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
        "--start",
        default=DEFAULT_START,
        help="Live replay start. Use 0 for all available intraday replay.",
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
) -> int:
    api_key = resolve_api_key(env)
    if api_key is None:
        print(f"Missing {API_KEY_ENV}; set it before running live chart.", file=stderr)
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

    try:
        chart = chart_factory()
        configure_chart(chart, title=f"{args.symbols} {args.schema}")
        show_chart(chart)

        live = db_module.Live(key=api_key)
        live.subscribe(
            dataset=args.dataset,
            schema=args.schema,
            symbols=parse_symbols(args.symbols),
            stype_in=args.stype_in,
            start=parse_start(args.start),
        )
        live.add_callback(build_record_callback(candle_queue, stderr=stderr))
        live.start()

        result = drain_chart_queue(
            candle_queue,
            chart=chart,
            series_factory=series_factory,
            max_records=args.max_records,
            timeout_seconds=args.timeout_seconds,
        )
        print(
            "Live chart stopped: "
            f"records_updated={result.records_updated} "
            f"timed_out={result.timed_out} chart_closed={result.chart_closed}",
            file=stdout,
        )
        return 0
    except KeyboardInterrupt:
        print("Interrupted; stopping live chart.", file=stderr)
        return 130
    except Exception as exc:
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
