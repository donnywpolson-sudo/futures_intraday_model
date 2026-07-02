#!/usr/bin/env python3
"""Audit canonical raw parquet alignment to local Databento DBN archives."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1A_download.download_databento_raw import (  # noqa: E402
    CME_DATASET,
    SCHEMA,
    archive_entries_for_paths,
    available_start_for_product,
    definition_frame_for_group,
    enrich_with_definition_metadata,
    file_sha256,
    iter_dbn_files,
    iter_range_tasks,
    raw_file_manifest_path,
    schema_path_name,
    validate_raw_file_manifest,
)
from scripts.validation.check_dbn_archive_coverage import (  # noqa: E402
    DEFAULT_REQUIRED_SCHEMA_EXCEPTIONS_CONFIG,
    _profile_markets_and_years,
    load_yaml,
    required_schema_exception_keys,
    resolve_profile_name,
)


RAW_REQUIRED_COLUMNS = [
    "ts_event",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "rtype",
    "publisher_id",
    "instrument_id",
    "symbol",
    "data_quality_status",
    "data_quality_degraded",
    "raw_symbol",
    "tick_size",
    "source_file",
    "source_sha256",
]
RAW_OPTIONAL_AUDIT_COLUMNS = [
    "market",
    "year",
    "contract_multiplier_or_point_value",
    "source_schema",
]
DEFINITION_COMPARE_COLUMNS = ["raw_symbol", "tick_size", "contract_multiplier_or_point_value"]
MAX_HASH_WORKERS = 4
TRADES_SCHEMA = "trades"
TRADES_RECONSTRUCTED_SOURCE_SCHEMA = "trades_reconstructed_ohlcv_1m"


def _schema_root(dbn_root: Path, schema: str) -> Path:
    path_name = schema_path_name(schema)
    if dbn_root.name == path_name:
        return dbn_root
    if dbn_root.name == schema_path_name(SCHEMA):
        return dbn_root if schema == SCHEMA else dbn_root.parent / path_name
    return dbn_root / path_name


def _dbn_file_stem(path: Path) -> str:
    if path.name.endswith(".dbn.zst"):
        return path.name.removesuffix(".dbn.zst")
    return path.name.removesuffix(".dbn")


def _index_ohlcv_dbns(dbn_root: Path) -> dict[tuple[str, int], list[Path]]:
    root = _schema_root(dbn_root, SCHEMA)
    paths = iter_dbn_files(root) if root.exists() else []
    index: dict[tuple[str, int], list[Path]] = {}
    for entry in archive_entries_for_paths(paths, root):
        index.setdefault((entry.product, entry.year), []).append(entry.path)
    return {key: sorted(paths) for key, paths in sorted(index.items())}


def _index_schema_dbns(dbn_root: Path, schema: str) -> dict[tuple[str, int], list[Path]]:
    if schema == SCHEMA:
        return _index_ohlcv_dbns(dbn_root)
    root = _schema_root(dbn_root, schema)
    index: dict[tuple[str, int], list[Path]] = {}
    if not root.exists():
        return index
    for path in iter_dbn_files(root):
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            parts = path.parts
        market: str | None = None
        year: int | None = None
        if len(parts) >= 3 and parts[1].isdigit():
            market = parts[0]
            year = int(parts[1])
        elif len(parts) >= 2:
            stem = _dbn_file_stem(path)
            if stem.isdigit():
                market = parts[0]
                year = int(stem)
        if market is None or year is None:
            continue
        index.setdefault((market, year), []).append(path)
    return {key: sorted(paths) for key, paths in sorted(index.items())}


def _index_raw_files(raw_root: Path) -> dict[tuple[str, int], Path]:
    index: dict[tuple[str, int], Path] = {}
    if not raw_root.exists():
        return index
    for path in sorted(raw_root.glob("*/*.parquet")):
        try:
            year = int(path.stem)
        except ValueError:
            continue
        index[(path.parent.name, year)] = path
    return index


def _expected_market_years(
    *,
    markets: list[str],
    years: list[int],
    dbn_root: Path,
) -> tuple[set[tuple[str, int]], list[dict[str, Any]]]:
    ohlcv_root = _schema_root(dbn_root, SCHEMA)
    configured = {(market, year) for market in markets for year in years}
    if not configured:
        return set(), []
    tasks = iter_range_tasks(
        markets,
        start=f"{min(years)}-01-01",
        end=f"{max(years) + 1}-01-01",
        output_root=ohlcv_root,
        chunk="year",
        mode="download-dbn",
        raw_format="dbn-zstd",
        dataset=CME_DATASET,
        schema=SCHEMA,
    )
    expected = {(task.product, task.year) for task in tasks if task.year in set(years)}
    exemptions: list[dict[str, Any]] = []
    for market, year in sorted(configured - expected):
        available_start = available_start_for_product(CME_DATASET, market, pd.Timestamp(f"{year}-01-01").date())
        exemptions.append(
            {
                "market": market,
                "year": year,
                "reason": "pre_availability",
                "available_start": available_start.isoformat(),
            }
        )
    return expected, exemptions


def _discovery_profile_name(config_path: Path, profile_name: str) -> str | None:
    config = load_yaml(config_path)
    profiles = config.get("profiles", {})
    aliases = config.get("aliases", {})
    if not isinstance(profiles, dict):
        return None
    if not isinstance(aliases, dict):
        aliases = {}
    resolved = resolve_profile_name(profile_name, {str(key): str(value) for key, value in aliases.items()})
    profile = profiles.get(resolved)
    if isinstance(profile, dict) and bool(profile.get("discovery", False)):
        return resolved
    return None


def _parquet_columns(path: Path) -> list[str]:
    try:
        import pyarrow.parquet as pq

        return list(pq.ParquetFile(path).schema.names)
    except Exception:
        return list(pd.read_parquet(path).columns)


def _read_raw_audit_frame(path: Path, columns: Iterable[str]) -> pd.DataFrame:
    available = set(_parquet_columns(path))
    selected = [column for column in columns if column in available]
    return pd.read_parquet(path, columns=selected)


def _split_semicolon_values(series: pd.Series) -> set[str]:
    values: set[str] = set()
    for item in series.dropna().astype(str):
        for part in item.split(";"):
            part = part.strip()
            if part:
                values.add(part)
    return values


def _contains_semicolon_value(series: pd.Series, value: str) -> pd.Series:
    target = str(value)
    return series.fillna("").astype(str).map(
        lambda item: target in {part.strip() for part in item.split(";") if part.strip()}
    )


def _source_file_matches_path(source_file: str, path: Path) -> bool:
    source_path = Path(source_file)
    if not source_path.is_absolute():
        source_path = Path.cwd() / source_path
    try:
        return source_path.resolve() == path.resolve()
    except OSError:
        return source_path.as_posix() == path.as_posix()


def _manifest_request_status(path: Path) -> str | None:
    try:
        payload = json.loads(raw_file_manifest_path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    value = payload.get("request_status")
    return str(value) if value is not None else None


def _validate_trades_reconstructed_source(
    *,
    market: str,
    year: int,
    df: pd.DataFrame,
    row_mask: pd.Series,
    source_hash: str,
    trades_paths: list[Path],
    file_hashes: dict[Path, str] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    row_count = int(row_mask.sum())
    if "source_schema" not in df.columns:
        return None, f"{source_hash}: missing source_schema column"
    source_schemas = _split_semicolon_values(df.loc[row_mask, "source_schema"])
    if source_schemas != {TRADES_RECONSTRUCTED_SOURCE_SCHEMA}:
        return None, f"{source_hash}: source_schema not approved: {sorted(source_schemas)}"
    if "source_file" not in df.columns:
        return None, f"{source_hash}: missing source_file column"

    row_source_files = _split_semicolon_values(df.loc[row_mask, "source_file"])
    candidate_paths = [
        path
        for path in trades_paths
        if any(_source_file_matches_path(source_file, path) for source_file in row_source_files)
    ]
    if not candidate_paths:
        return None, f"{source_hash}: source_file not present in local trades DBN"

    invalid_manifest_failures: list[str] = []
    for path in candidate_paths:
        actual_hash = _cached_file_sha256(path, file_hashes)
        if actual_hash != source_hash:
            continue
        manifest_failures = validate_raw_file_manifest(
            path,
            expected_schema=TRADES_SCHEMA,
            expected_market=market,
            expected_year=year,
            file_sha256_value=actual_hash,
        )
        request_status = _manifest_request_status(path)
        if request_status != "ok":
            manifest_failures.append(f"manifest request_status is {request_status!r}, not 'ok'")
        if manifest_failures:
            invalid_manifest_failures.append(f"{path.as_posix()}: {'; '.join(manifest_failures)}")
            continue
        return {
            "market": market,
            "year": year,
            "source_sha256": source_hash,
            "source_file": path.as_posix(),
            "source_schema": TRADES_RECONSTRUCTED_SOURCE_SCHEMA,
            "row_count": row_count,
            "reason": "local_trades_reconstructed_ohlcv",
        }, None

    if invalid_manifest_failures:
        return None, f"{source_hash}: trades manifest invalid: {' | '.join(invalid_manifest_failures)}"
    return None, f"{source_hash}: source_sha256 not found in referenced local trades DBN"


def _load_repair_manifest(
    repair_manifest_path: Path | None,
    *,
    raw_root: Path,
) -> tuple[dict[str, Any] | None, dict[tuple[str, int, str], dict[str, Any]], list[str]]:
    if repair_manifest_path is None:
        return None, {}, []
    if not repair_manifest_path.exists():
        return None, {}, [f"missing repair manifest: {repair_manifest_path.as_posix()}"]
    try:
        payload = json.loads(repair_manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, {}, [f"unreadable repair manifest {repair_manifest_path.as_posix()}: {exc}"]
    if not isinstance(payload, dict):
        return None, {}, [f"repair manifest is not an object: {repair_manifest_path.as_posix()}"]

    failures: list[str] = []
    if payload.get("status") != "PASS":
        failures.append(f"repair manifest status is {payload.get('status')!r}, not PASS")
    manifest_raw_root = payload.get("raw_root")
    if isinstance(manifest_raw_root, str) and manifest_raw_root:
        if (Path.cwd() / manifest_raw_root).resolve() != raw_root.resolve():
            failures.append(
                "repair manifest raw_root does not match audit raw_root: "
                f"{manifest_raw_root} != {raw_root.as_posix()}"
            )

    rows = payload.get("repairs", payload.get("rows", []))
    if not isinstance(rows, list) or not rows:
        failures.append("repair manifest has no repairs")
        rows = []

    lookup: dict[tuple[str, int, str], dict[str, Any]] = {}
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(f"repair manifest row {idx} is not an object")
            continue
        try:
            market = str(row["market"])
            year = int(row["year"])
            source_sha256 = str(row["source_sha256"])
            source_file = str(row["source_file"])
            row_count = int(row["row_count"])
        except (KeyError, TypeError, ValueError) as exc:
            failures.append(f"repair manifest row {idx} missing required fields: {exc}")
            continue
        if not source_sha256:
            failures.append(f"repair manifest row {idx} has blank source_sha256")
        if not source_file:
            failures.append(f"repair manifest row {idx} has blank source_file")
        if row_count <= 0:
            failures.append(f"repair manifest row {idx} row_count must be positive")
        key = (market, year, source_sha256)
        if key in lookup:
            failures.append(f"duplicate repair manifest key: {market} {year} {source_sha256}")
        lookup[key] = row
    return payload, lookup, failures


def _validate_manifest_paths(
    index: dict[tuple[str, int], list[Path]],
    *,
    schema: str,
    file_hashes: dict[Path, str] | None = None,
) -> list[dict[str, Any]]:
    invalid: list[dict[str, Any]] = []
    for (market, year), paths in sorted(index.items()):
        for path in paths:
            failures = validate_raw_file_manifest(
                path,
                expected_schema=schema,
                expected_market=market,
                expected_year=year,
                file_sha256_value=file_hashes.get(path) if file_hashes is not None else None,
            )
            if failures:
                invalid.append(
                    {
                        "schema": schema,
                        "market": market,
                        "year": year,
                        "path": path.as_posix(),
                        "failures": failures,
                    }
                )
    return invalid


def _dbn_paths_to_hash(*indexes: dict[tuple[str, int], list[Path]]) -> list[Path]:
    paths = {
        path
        for index in indexes
        for group_paths in index.values()
        for path in group_paths
        if raw_file_manifest_path(path).exists()
    }
    return sorted(paths, key=lambda path: path.as_posix())


def _build_file_hash_cache(*indexes: dict[tuple[str, int], list[Path]]) -> dict[Path, str]:
    paths = _dbn_paths_to_hash(*indexes)
    if not paths:
        return {}
    workers = min(MAX_HASH_WORKERS, len(paths))
    if workers == 1:
        return {path: file_sha256(path) for path in paths}
    hashes: dict[Path, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(file_sha256, path): path for path in paths}
        for future in as_completed(futures):
            path = futures[future]
            hashes[path] = future.result()
    return hashes


def _cached_file_sha256(path: Path, file_hashes: dict[Path, str] | None) -> str:
    if file_hashes is not None and path in file_hashes:
        return file_hashes[path]
    return file_sha256(path)


def _validate_raw_schema_and_values(
    *,
    key: tuple[str, int],
    path: Path,
    df: pd.DataFrame,
) -> tuple[list[str], dict[str, Any]]:
    market, year = key
    failures: list[str] = []
    metrics: dict[str, Any] = {"market": market, "year": year, "path": path.as_posix(), "rows": int(len(df))}
    missing = [column for column in RAW_REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        failures.append("missing raw columns: " + ",".join(missing))
        metrics["missing_columns"] = missing
        return failures, metrics
    if df.empty:
        failures.append("empty raw parquet")
        return failures, metrics

    ts = pd.to_datetime(df["ts_event"], utc=True, errors="coerce")
    invalid_ts = int(ts.isna().sum())
    duplicate_ts = int(ts.duplicated().sum())
    if invalid_ts:
        failures.append(f"invalid ts_event rows={invalid_ts}")
    if duplicate_ts:
        failures.append(f"duplicate ts_event rows={duplicate_ts}")
    if not bool(ts.is_monotonic_increasing):
        failures.append("non_monotonic_ts_event")

    prices = df[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")
    bad_ohlc = (
        prices.isna().any(axis=1)
        | volume.isna()
        | prices["high"].lt(prices[["open", "close"]].max(axis=1))
        | prices["low"].gt(prices[["open", "close"]].min(axis=1))
        | prices["high"].lt(prices["low"])
    )
    bad_ohlc_count = int(bad_ohlc.sum())
    negative_volume_count = int(volume.lt(0).fillna(True).sum())
    if bad_ohlc_count:
        failures.append(f"invalid OHLC rows={bad_ohlc_count}")
    if negative_volume_count:
        failures.append(f"negative volume rows={negative_volume_count}")

    for column in ("rtype", "publisher_id", "instrument_id", "symbol", "data_quality_status"):
        null_count = int(df[column].isna().sum())
        if null_count:
            failures.append(f"null {column} rows={null_count}")
    blank_symbol = int(df["symbol"].astype("string").str.strip().eq("").fillna(True).sum())
    if blank_symbol:
        failures.append(f"blank symbol rows={blank_symbol}")
    blank_raw_symbol = int(df["raw_symbol"].astype("string").str.strip().eq("").fillna(True).sum())
    if blank_raw_symbol:
        failures.append(f"blank raw_symbol rows={blank_raw_symbol}")
    tick_size = pd.to_numeric(df["tick_size"], errors="coerce")
    bad_tick_size = int((tick_size.isna() | tick_size.le(0)).sum())
    if bad_tick_size:
        failures.append(f"missing_or_nonpositive_tick_size rows={bad_tick_size}")
    if "market" in df.columns and not df["market"].dropna().astype(str).eq(market).all():
        failures.append("raw market column does not match path")
    if "year" in df.columns:
        raw_year = pd.to_numeric(df["year"], errors="coerce")
        if not raw_year.dropna().eq(year).all():
            failures.append("raw year column does not match path")

    metrics.update(
        {
            "invalid_ts_count": invalid_ts,
            "duplicate_ts_count": duplicate_ts,
            "bad_ohlc_count": bad_ohlc_count,
            "negative_volume_count": negative_volume_count,
        }
    )
    return failures, metrics


def _validate_source_hashes(
    *,
    key: tuple[str, int],
    df: pd.DataFrame,
    ohlcv_paths: list[Path],
    trades_paths: list[Path] | None = None,
    file_hashes: dict[Path, str] | None = None,
    repair_lookup: dict[tuple[str, int, str], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    market, year = key
    if "source_sha256" not in df.columns:
        return {"market": market, "year": year, "failure": "missing source_sha256"}, []
    raw_hashes = _split_semicolon_values(df["source_sha256"])
    local_hashes = {_cached_file_sha256(path, file_hashes) for path in ohlcv_paths}
    missing = sorted(raw_hashes - local_hashes)
    if not missing:
        return None, []

    lookup = repair_lookup or {}
    unapproved: list[str] = []
    repair_failures: list[str] = []
    accepted_repairs: list[dict[str, Any]] = []
    for source_hash in missing:
        repair = lookup.get((market, year, source_hash))
        if repair is None:
            row_mask = _contains_semicolon_value(df["source_sha256"], source_hash)
            accepted_trade_repair, trade_failure = _validate_trades_reconstructed_source(
                market=market,
                year=year,
                df=df,
                row_mask=row_mask,
                source_hash=source_hash,
                trades_paths=trades_paths or [],
                file_hashes=file_hashes,
            )
            if accepted_trade_repair is not None:
                accepted_repairs.append(accepted_trade_repair)
            else:
                unapproved.append(source_hash)
                if trade_failure:
                    repair_failures.append(trade_failure)
            continue
        row_mask = _contains_semicolon_value(df["source_sha256"], source_hash)
        actual_row_count = int(row_mask.sum())
        expected_row_count = int(repair["row_count"])
        if actual_row_count != expected_row_count:
            repair_failures.append(
                f"{source_hash}: row_count {actual_row_count} != manifest {expected_row_count}"
            )
        source_file = str(repair["source_file"])
        if "source_file" not in df.columns:
            repair_failures.append(f"{source_hash}: missing source_file column")
        else:
            row_source_files = _split_semicolon_values(df.loc[row_mask, "source_file"])
            if source_file not in row_source_files:
                repair_failures.append(f"{source_hash}: source_file not present in repaired rows")
        accepted_repairs.append(
            {
                "market": market,
                "year": year,
                "source_sha256": source_hash,
                "source_file": source_file,
                "row_count": actual_row_count,
                "reason": repair.get("reason"),
            }
        )
    if unapproved or repair_failures:
        return {
            "market": market,
            "year": year,
            "raw_hashes_not_found_in_local_ohlcv_dbn": unapproved,
            "repair_manifest_failures": repair_failures,
            "local_ohlcv_dbn_count": len(ohlcv_paths),
        }, []
    return None, accepted_repairs


def _series_equal(left: pd.Series, right: pd.Series) -> pd.Series:
    left_text = left.reset_index(drop=True).astype("string").fillna("")
    right_text = right.reset_index(drop=True).astype("string").fillna("")
    return left_text.eq(right_text)


def _numeric_equal(left: pd.Series, right: pd.Series) -> pd.Series:
    left_num = pd.to_numeric(left.reset_index(drop=True), errors="coerce")
    right_num = pd.to_numeric(right.reset_index(drop=True), errors="coerce")
    both_null = left_num.isna() & right_num.isna()
    return both_null | (left_num.sub(right_num).abs() <= 1e-12)


def _validate_definition_join(
    *,
    key: tuple[str, int],
    dbn_root: Path,
    raw_df: pd.DataFrame,
) -> dict[str, Any] | None:
    market, year = key
    if "ts_event" not in raw_df.columns or "instrument_id" not in raw_df.columns:
        return None
    try:
        definitions, _ = definition_frame_for_group(dbn_root, market, year)
        expected = enrich_with_definition_metadata(raw_df[["ts_event", "instrument_id"]].copy(), definitions)
    except Exception as exc:
        return {"market": market, "year": year, "failure": f"definition join rebuild failed: {exc}"}

    mismatches: dict[str, int] = {}
    samples: list[dict[str, Any]] = []
    for column in DEFINITION_COMPARE_COLUMNS:
        if column not in raw_df.columns or column not in expected.columns:
            continue
        if column == "raw_symbol":
            equal = _series_equal(raw_df[column], expected[column])
        else:
            equal = _numeric_equal(raw_df[column], expected[column])
        mismatch_mask = ~equal.fillna(False)
        count = int(mismatch_mask.sum())
        if count:
            mismatches[column] = count
            sample_idx = list(raw_df.index[mismatch_mask][:3])
            for idx in sample_idx:
                samples.append(
                    {
                        "column": column,
                        "ts_event": str(raw_df.at[idx, "ts_event"]),
                        "instrument_id": str(raw_df.at[idx, "instrument_id"]),
                        "raw_value": None if pd.isna(raw_df.at[idx, column]) else str(raw_df.at[idx, column]),
                        "definition_value": None if pd.isna(expected.at[idx, column]) else str(expected.at[idx, column]),
                    }
                )
    if not mismatches:
        return None
    return {"market": market, "year": year, "mismatch_counts": mismatches, "samples": samples[:10]}


def _row(market_year: tuple[str, int], **extra: Any) -> dict[str, Any]:
    market, year = market_year
    return {"market": market, "year": year, **extra}


def build_report(
    *,
    config_path: Path,
    profile: str,
    dbn_root: Path,
    raw_root: Path,
    skip_definition_join: bool = False,
    repair_manifest_path: Path | None = None,
    expected_only: bool = False,
    required_schema_exceptions_config: Path | None = DEFAULT_REQUIRED_SCHEMA_EXCEPTIONS_CONFIG,
) -> dict[str, Any]:
    ohlcv_index = _index_schema_dbns(dbn_root, SCHEMA)
    definition_index = _index_schema_dbns(dbn_root, "definition")
    status_index = _index_schema_dbns(dbn_root, "status")
    statistics_index = _index_schema_dbns(dbn_root, "statistics")
    trades_index = _index_schema_dbns(dbn_root, TRADES_SCHEMA)
    raw_index = _index_raw_files(raw_root)
    discovery_profile = _discovery_profile_name(config_path, profile)
    if discovery_profile is None:
        resolved_profile, markets, years = _profile_markets_and_years(config_path, profile)
        expected, pre_availability_exemptions = _expected_market_years(
            markets=markets,
            years=years,
            dbn_root=dbn_root,
        )
    else:
        resolved_profile = discovery_profile
        expected = set(raw_index)
        markets = sorted({market for market, _ in expected})
        years = sorted({year for _, year in expected})
        pre_availability_exemptions = []
    status_exception_keys, status_exceptions, exception_failures = required_schema_exception_keys(
        required_schema_exceptions_config,
        schema="status",
    )
    status_exception_keys &= expected
    stale_status_exception_keys = sorted(status_exception_keys & set(status_index))
    for market, year in stale_status_exception_keys:
        exception_failures.append(
            f"required schema exception is stale because status archive is present: {market} {year}"
        )
    if expected_only:
        ohlcv_index = {key: value for key, value in ohlcv_index.items() if key in expected}
        definition_index = {key: value for key, value in definition_index.items() if key in expected}
        status_index = {key: value for key, value in status_index.items() if key in expected}
        statistics_index = {key: value for key, value in statistics_index.items() if key in expected}
        raw_index = {key: value for key, value in raw_index.items() if key in expected}
    file_hashes = _build_file_hash_cache(ohlcv_index, definition_index, status_index, statistics_index)
    repair_manifest, repair_lookup, repair_manifest_failures = _load_repair_manifest(
        repair_manifest_path,
        raw_root=raw_root,
    )

    missing_ohlcv = sorted(expected - set(ohlcv_index))
    missing_definition = sorted(expected - set(definition_index))
    status_complete_keys = set(status_index) | status_exception_keys
    missing_status = sorted(expected - status_complete_keys)
    missing_statistics = sorted(expected - set(statistics_index))
    missing_raw = sorted(expected - set(raw_index))
    complete_required_dbn_keys = (
        set(ohlcv_index) & set(definition_index) & status_complete_keys & set(statistics_index)
    )
    needs_phase1b = [
        _row(key, status="needs_phase1b_conversion")
        for key in missing_raw
        if key in complete_required_dbn_keys
    ]
    raw_only = sorted(set(raw_index) - complete_required_dbn_keys)
    dbn_only_inventory = sorted(complete_required_dbn_keys - set(raw_index))

    invalid_manifests = _validate_manifest_paths(ohlcv_index, schema=SCHEMA, file_hashes=file_hashes)
    invalid_manifests.extend(
        _validate_manifest_paths(definition_index, schema="definition", file_hashes=file_hashes)
    )
    invalid_manifests.extend(
        _validate_manifest_paths(status_index, schema="status", file_hashes=file_hashes)
    )
    invalid_manifests.extend(
        _validate_manifest_paths(statistics_index, schema="statistics", file_hashes=file_hashes)
    )

    raw_schema_failures: list[dict[str, Any]] = []
    source_hash_mismatches: list[dict[str, Any]] = []
    accepted_repair_sources: list[dict[str, Any]] = []
    definition_join_mismatches: list[dict[str, Any]] = []
    raw_file_metrics: list[dict[str, Any]] = []
    definition_join_checked_count = 0
    raw_columns = RAW_REQUIRED_COLUMNS + RAW_OPTIONAL_AUDIT_COLUMNS
    for key, path in sorted(raw_index.items()):
        df = _read_raw_audit_frame(path, raw_columns)
        failures, metrics = _validate_raw_schema_and_values(key=key, path=path, df=df)
        metrics.update(
            {
                "output_path": path.as_posix(),
                "ohlcv_input_paths": [
                    source_path.as_posix() for source_path in ohlcv_index.get(key, [])
                ],
                "definition_paths": [
                    source_path.as_posix()
                    for source_path in definition_index.get(key, [])
                ],
            }
        )
        raw_file_metrics.append(metrics)
        if failures:
            raw_schema_failures.append({**_row(key, path=path.as_posix()), "failures": failures})
        if key in ohlcv_index:
            mismatch, repairs = _validate_source_hashes(
                key=key,
                df=df,
                ohlcv_paths=ohlcv_index[key],
                trades_paths=trades_index.get(key, []),
                file_hashes=file_hashes,
                repair_lookup=repair_lookup,
            )
            if mismatch:
                source_hash_mismatches.append(mismatch)
            accepted_repair_sources.extend(repairs)
        else:
            source_hash_mismatches.append({**_row(key), "failure": "raw has no local OHLCV DBN"})
        if key in definition_index and not failures and not skip_definition_join:
            definition_join_checked_count += 1
            mismatch = _validate_definition_join(key=key, dbn_root=dbn_root, raw_df=df)
            if mismatch:
                definition_join_mismatches.append(mismatch)

    failures: list[str] = []
    if missing_ohlcv:
        failures.append(f"missing OHLCV DBN market-years: {len(missing_ohlcv)}")
    if missing_definition:
        failures.append(f"missing definition DBN market-years: {len(missing_definition)}")
    if missing_status:
        failures.append(f"missing status DBN market-years: {len(missing_status)}")
    if missing_statistics:
        failures.append(f"missing statistics DBN market-years: {len(missing_statistics)}")
    if missing_raw:
        failures.append(f"missing raw parquet market-years: {len(missing_raw)}")
    if invalid_manifests:
        failures.append(f"invalid DBN manifests: {len(invalid_manifests)}")
    if repair_manifest_failures:
        failures.append(f"repair manifest failures: {len(repair_manifest_failures)}")
    if exception_failures:
        failures.append(f"required schema exception failures: {len(exception_failures)}")
    if raw_only:
        failures.append(f"raw-only market-years: {len(raw_only)}")
    if raw_schema_failures:
        failures.append(f"raw schema/value failures: {len(raw_schema_failures)}")
    if source_hash_mismatches:
        failures.append(f"source hash mismatches: {len(source_hash_mismatches)}")
    if definition_join_mismatches:
        failures.append(f"definition join mismatches: {len(definition_join_mismatches)}")

    return {
        "stage": "raw_dbn_alignment_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "audit_completeness": "partial" if skip_definition_join else "full",
        "expected_only": bool(expected_only),
        "definition_join_skipped": bool(skip_definition_join),
        "definition_join_status": "skipped" if skip_definition_join else "checked",
        "definition_join_checked_market_year_count": definition_join_checked_count,
        "failures": failures,
        "dataset": CME_DATASET,
        "profile": profile,
        "resolved_profile": resolved_profile,
        "markets": markets,
        "years": years,
        "dbn_root": dbn_root.as_posix(),
        "raw_root": raw_root.as_posix(),
        "expected_market_year_count": len(expected),
        "pre_availability_exemption_count": len(pre_availability_exemptions),
        "ohlcv_dbn_market_year_count": len(ohlcv_index),
        "definition_dbn_market_year_count": len(definition_index),
        "status_dbn_market_year_count": len(status_index),
        "statistics_dbn_market_year_count": len(statistics_index),
        "raw_market_year_count": len(raw_index),
        "missing_ohlcv_dbn_count": len(missing_ohlcv),
        "missing_definition_dbn_count": len(missing_definition),
        "missing_status_dbn_count": len(missing_status),
        "missing_statistics_dbn_count": len(missing_statistics),
        "status_required_schema_exception_count": len(status_exception_keys),
        "required_schema_exception_failure_count": len(exception_failures),
        "missing_raw_count": len(missing_raw),
        "needs_phase1b_conversion_count": len(needs_phase1b),
        "dbn_only_inventory_count": len(dbn_only_inventory),
        "raw_only_count": len(raw_only),
        "invalid_manifest_count": len(invalid_manifests),
        "repair_manifest_path": repair_manifest_path.as_posix() if repair_manifest_path else None,
        "repair_manifest_hash": file_sha256(repair_manifest_path) if repair_manifest_path else None,
        "repair_manifest_status": repair_manifest.get("status") if repair_manifest else "NOT_PROVIDED",
        "repair_manifest_failure_count": len(repair_manifest_failures),
        "repair_manifest_failures": repair_manifest_failures,
        "required_schema_exceptions_config": (
            required_schema_exceptions_config.as_posix()
            if required_schema_exceptions_config is not None
            else None
        ),
        "required_schema_exceptions": status_exceptions,
        "required_schema_exception_failures": exception_failures,
        "accepted_repair_source_count": len(accepted_repair_sources),
        "accepted_repair_sources": accepted_repair_sources,
        "raw_schema_failure_count": len(raw_schema_failures),
        "source_hash_mismatch_count": len(source_hash_mismatches),
        "definition_join_mismatch_count": len(definition_join_mismatches),
        "pre_availability_exemptions": pre_availability_exemptions,
        "missing_ohlcv_dbn": [_row(key) for key in missing_ohlcv],
        "missing_definition_dbn": [_row(key) for key in missing_definition],
        "missing_status_dbn": [_row(key) for key in missing_status],
        "missing_statistics_dbn": [_row(key) for key in missing_statistics],
        "missing_raw": [_row(key) for key in missing_raw],
        "needs_phase1b_conversion": needs_phase1b,
        "dbn_only_inventory": [_row(key) for key in dbn_only_inventory],
        "raw_only_market_years": [_row(key, path=raw_index[key].as_posix()) for key in raw_only],
        "invalid_manifests": invalid_manifests,
        "raw_schema_failures": raw_schema_failures,
        "source_hash_mismatches": source_hash_mismatches,
        "definition_join_mismatches": definition_join_mismatches,
        "raw_file_metrics": raw_file_metrics,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Raw DBN Alignment Audit",
        "",
        f"- Status: {report['status']}",
        f"- Audit completeness: {report['audit_completeness']}",
        f"- Profile: {report['profile']} -> {report['resolved_profile']}",
        f"- Expected market-years: {report['expected_market_year_count']}",
        f"- Raw market-years: {report['raw_market_year_count']}",
        f"- OHLCV DBN market-years: {report['ohlcv_dbn_market_year_count']}",
        f"- Definition DBN market-years: {report['definition_dbn_market_year_count']}",
        f"- Status DBN market-years: {report['status_dbn_market_year_count']}",
        f"- Statistics DBN market-years: {report['statistics_dbn_market_year_count']}",
        f"- Status required-schema exceptions: {report['status_required_schema_exception_count']}",
        f"- Needs Phase 1B conversion: {report['needs_phase1b_conversion_count']}",
        f"- Raw-only market-years: {report['raw_only_count']}",
        f"- Invalid manifests: {report['invalid_manifest_count']}",
        f"- Repair manifest status: {report['repair_manifest_status']}",
        f"- Repair manifest failures: {report['repair_manifest_failure_count']}",
        f"- Required-schema exception failures: {report['required_schema_exception_failure_count']}",
        f"- Accepted repair sources: {report['accepted_repair_source_count']}",
        f"- Raw schema/value failures: {report['raw_schema_failure_count']}",
        f"- Source hash mismatches: {report['source_hash_mismatch_count']}",
        f"- Definition join status: {report['definition_join_status']}",
        f"- Definition join checked market-years: {report['definition_join_checked_market_year_count']}",
        f"- Definition join mismatches: {report['definition_join_mismatch_count']}",
        "",
        "## Failures",
        "",
    ]
    failures = report.get("failures") or []
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    if report.get("needs_phase1b_conversion"):
        lines.extend(["", "## Phase 1B Conversion Candidates", ""])
        for row in report["needs_phase1b_conversion"][:100]:
            lines.append(f"- {row['market']} {row['year']}")
    if report.get("accepted_repair_sources"):
        lines.extend(["", "## Accepted Repair Sources", ""])
        for row in report["accepted_repair_sources"][:100]:
            lines.append(
                f"- {row['market']} {row['year']} rows={row['row_count']} "
                f"source_file={row['source_file']}"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/alpha_tiered.yaml")
    parser.add_argument("--profile", default="tier_3")
    parser.add_argument("--dbn-root", default="data/dbn")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument(
        "--skip-definition-join",
        action="store_true",
        help="Skip expensive point-in-time definition rebuild checks; report is partial.",
    )
    parser.add_argument(
        "--repair-manifest",
        help="Optional fail-closed manifest that authorizes non-DBN repaired raw row sources.",
    )
    parser.add_argument(
        "--expected-only",
        action="store_true",
        help="Bound smoke scope to profile/discovery expected market-years instead of auditing all files under roots.",
    )
    parser.add_argument(
        "--required-schema-exceptions-config",
        default=DEFAULT_REQUIRED_SCHEMA_EXCEPTIONS_CONFIG.as_posix(),
    )
    parser.add_argument("--disable-required-schema-exceptions", action="store_true")
    parser.add_argument("--json-out", default="reports/raw_ingest/raw_dbn_alignment.json")
    parser.add_argument("--md-out", default="reports/raw_ingest/raw_dbn_alignment.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(
        config_path=Path(args.config),
        profile=str(args.profile),
        dbn_root=Path(args.dbn_root),
        raw_root=Path(args.raw_root),
        skip_definition_join=bool(args.skip_definition_join),
        repair_manifest_path=Path(args.repair_manifest) if args.repair_manifest else None,
        expected_only=bool(args.expected_only),
        required_schema_exceptions_config=(
            None if args.disable_required_schema_exceptions else Path(args.required_schema_exceptions_config)
        ),
    )
    write_json(Path(args.json_out), report)
    write_markdown(Path(args.md_out), report)
    print(
        "status={status} expected={expected_market_year_count} raw={raw_market_year_count} "
        "missing_status={missing_status_dbn_count} "
        "missing_statistics={missing_statistics_dbn_count} "
        "required_exceptions={status_required_schema_exception_count} "
        "exception_failures={required_schema_exception_failure_count} "
        "needs_phase1b={needs_phase1b_conversion_count} raw_only={raw_only_count} "
        "invalid_manifests={invalid_manifest_count} source_hash_mismatches={source_hash_mismatch_count} "
        "definition_join_status={definition_join_status} "
        "definition_join_mismatches={definition_join_mismatch_count}".format(**report)
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
