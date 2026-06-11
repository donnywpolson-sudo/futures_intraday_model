"""Shared Phase 1 raw Databento contract constants."""

from __future__ import annotations

VENDOR = "databento"
REQUIRED_DATASET = "GLBX.MDP3"
REQUIRED_SCHEMAS = ("ohlcv-1m", "definition")
SCHEMA_PATHS = {"ohlcv-1m": "ohlcv_1m", "definition": "definition"}
EXPECTED_ENCODING = "dbn"
EXPECTED_COMPRESSION = "zstd"

REQUIRED_OHLCV_FIELDS = [
    "ts_event",
    "rtype",
    "publisher_id",
    "instrument_id",
    "open",
    "high",
    "low",
    "close",
    "volume",
]

REQUIRED_MANIFEST_FIELDS = [
    "vendor",
    "dataset",
    "schema",
    "market",
    "symbols_requested",
    "start",
    "end",
    "stype_in",
    "stype_out",
    "encoding",
    "compression",
    "downloaded_at",
    "path",
    "file_size_bytes",
    "file_sha256",
    "job_id",
    "api_client_version",
    "request_status",
]

DEFINITION_METADATA_FIELDS = [
    "ts_recv",
    "ts_event",
    "rtype",
    "publisher_id",
    "instrument_id",
    "raw_symbol",
    "security_update_action",
    "instrument_class",
    "security_type",
    "min_price_increment",
    "display_factor",
    "expiration",
    "activation",
    "unit_of_measure_qty",
    "unit_of_measure",
    "currency",
    "settl_currency",
    "exchange",
    "group",
    "asset",
    "maturity_year",
    "maturity_month",
    "maturity_day",
    "maturity_week",
    "contract_multiplier",
    "min_lot_size",
    "min_trade_vol",
    "raw_instrument_id",
    "market_segment_id",
    "match_algorithm",
    "price_display_format",
    "main_fraction",
    "sub_fraction",
    "leg_count",
    "leg_index",
    "leg_instrument_id",
    "leg_raw_symbol",
]

REQUIRED_DEFINITION_FIELDS = [
    "instrument_id",
    "raw_symbol",
    "min_price_increment",
]
