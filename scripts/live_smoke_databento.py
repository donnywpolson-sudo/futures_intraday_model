#!/usr/bin/env python3
"""Databento live OHLCV smoke test for research observation only."""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence, TextIO

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.databento_auth import resolve_databento_api_key


DEFAULT_DATASET = "GLBX.MDP3"
DEFAULT_SCHEMA = "ohlcv-1m"
DEFAULT_SYMBOLS = "ES.c.0"
DEFAULT_STYPE_IN = "continuous"
DEFAULT_DBN_OUT_DIR = Path("data/live_raw")
DEFAULT_MAX_RECORDS = 10
DEFAULT_TIMEOUT_SECONDS = 60.0
API_KEY_ENV = "DATABENTO_API_KEY"


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


def safe_filename_part(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")


def default_dbn_path(
    *,
    out_dir: Path,
    dataset: str,
    schema: str,
    symbols: str,
    now: datetime | None = None,
) -> Path:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    name = "_".join(
        [
            "databento_live",
            safe_filename_part(dataset),
            safe_filename_part(schema),
            safe_filename_part(symbols),
            timestamp,
        ]
    )
    return out_dir / f"{name}.dbn"


def import_databento() -> Any:
    return importlib.import_module("databento")


def resolve_api_key(env: dict[str, str] | None = None) -> str | None:
    key = resolve_databento_api_key(env=env, key_name=API_KEY_ENV)
    return key or None


def _value(record: object, *names: str) -> object:
    for name in names:
        if hasattr(record, name):
            attr = getattr(record, name)
            return attr() if callable(attr) else attr
    return None


def format_record(record: object) -> str:
    record_type = type(record).__name__
    ts = _value(record, "pretty_ts_event", "ts_event")
    instrument_id = _value(record, "instrument_id")

    if all(hasattr(record, name) for name in ("open", "high", "low", "close", "volume")):
        return (
            "OHLCV "
            f"ts={ts} instrument_id={instrument_id} "
            f"open={_value(record, 'pretty_open', 'open')} "
            f"high={_value(record, 'pretty_high', 'high')} "
            f"low={_value(record, 'pretty_low', 'low')} "
            f"close={_value(record, 'pretty_close', 'close')} "
            f"volume={_value(record, 'volume')}"
        )

    if hasattr(record, "stype_in_symbol") or record_type == "SymbolMappingMsg":
        return (
            "SYMBOL_MAPPING "
            f"instrument_id={instrument_id} "
            f"stype_in_symbol={_value(record, 'stype_in_symbol')} "
            f"stype_out_symbol={_value(record, 'stype_out_symbol')} "
            f"start={_value(record, 'pretty_start_ts', 'start_ts')} "
            f"end={_value(record, 'pretty_end_ts', 'end_ts')}"
        )

    if hasattr(record, "err") or record_type == "ErrorMsg":
        return (
            "ERROR "
            f"ts={ts} code={_value(record, 'code')} "
            f"err={_value(record, 'err')}"
        )

    if hasattr(record, "msg") or record_type == "SystemMsg":
        return (
            "SYSTEM "
            f"ts={ts} code={_value(record, 'code')} "
            f"msg={_value(record, 'msg')}"
        )

    return f"RECORD type={record_type} ts={ts} instrument_id={instrument_id}"


@dataclass
class LiveSmokeState:
    max_records: int
    stdout: TextIO
    client: Any | None = None
    records_seen: int = 0

    def handle_record(self, record: object) -> None:
        print(format_record(record), file=self.stdout, flush=True)
        self.records_seen += 1
        if self.records_seen >= self.max_records and self.client is not None:
            stop = getattr(self.client, "stop", None)
            if callable(stop):
                stop()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke test Databento live CME Globex data for research/paper "
            "observation only. No orders, broker integration, or live inference."
        )
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--symbols", default=DEFAULT_SYMBOLS)
    parser.add_argument("--stype-in", default=DEFAULT_STYPE_IN)
    parser.add_argument(
        "--start",
        default=None,
        help="Live replay start. Use 0 for intraday replay from start of day.",
    )
    parser.add_argument("--max-records", type=positive_int, default=DEFAULT_MAX_RECORDS)
    parser.add_argument(
        "--timeout-seconds",
        type=nonnegative_float,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--save-dbn",
        action="store_true",
        help="Also write raw live DBN to a timestamped ignored file.",
    )
    parser.add_argument(
        "--dbn-out-dir",
        type=Path,
        default=DEFAULT_DBN_OUT_DIR,
        help="Directory for --save-dbn output.",
    )
    parser.add_argument(
        "--dbn-output",
        type=Path,
        default=None,
        help="Explicit DBN output path used only with --save-dbn.",
    )
    return parser


def run_live_smoke(
    args: argparse.Namespace,
    *,
    db_module: Any | None = None,
    env: dict[str, str] | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    api_key = resolve_api_key(env)
    if api_key is None:
        print(f"Missing {API_KEY_ENV}; set it before running live smoke.", file=stderr)
        return 2

    if db_module is None:
        try:
            db_module = import_databento()
        except ModuleNotFoundError:
            print(
                "Missing databento package; install project requirements before "
                "running live smoke.",
                file=stderr,
            )
            return 2

    symbols = parse_symbols(args.symbols)
    start = parse_start(args.start)
    state = LiveSmokeState(max_records=args.max_records, stdout=stdout)
    live = None

    try:
        live = db_module.Live(key=api_key)
        state.client = live
        live.subscribe(
            dataset=args.dataset,
            schema=args.schema,
            symbols=symbols,
            stype_in=args.stype_in,
            start=start,
        )

        if args.save_dbn:
            dbn_path = args.dbn_output or default_dbn_path(
                out_dir=args.dbn_out_dir,
                dataset=args.dataset,
                schema=args.schema,
                symbols=args.symbols,
            )
            dbn_path.parent.mkdir(parents=True, exist_ok=True)
            live.add_stream(dbn_path)
            print(f"Writing raw DBN to {dbn_path}", file=stderr)

        live.add_callback(state.handle_record)
        live.start()
        live.block_for_close(timeout=args.timeout_seconds)
        return 0
    except KeyboardInterrupt:
        print("Interrupted; stopping live smoke.", file=stderr)
        return 130
    except Exception as exc:  # Databento surfaces SDK/network errors here.
        print(f"Databento live smoke failed: {exc}", file=stderr)
        return 1
    finally:
        if live is not None:
            stop = getattr(live, "stop", None)
            if callable(stop):
                stop()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return run_live_smoke(args)


if __name__ == "__main__":
    raise SystemExit(main())
