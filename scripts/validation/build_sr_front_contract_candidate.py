#!/usr/bin/env python3
"""Build SR1/SR3 front-contract raw candidates from parent OHLCV DBNs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

import pandas as pd

from scripts.phase1A_download.download_databento_raw import (
    CME_DATASET,
    ORDERED_OUTPUT_COLUMNS,
    SCHEMA,
    STATISTICS_ENRICHMENT_COLUMNS,
    STATUS_ENRICHMENT_COLUMNS,
    definition_frame_for_group,
    enrich_with_definition_metadata,
    enrich_with_statistics_metadata,
    enrich_with_status_metadata,
    file_sha256,
    load_optional_schema_frame_for_group,
    optional_schema_match_summary,
    store_to_required_dataframe,
    validate_raw_file_manifest,
    write_required_dataframe_parquet,
)
from scripts.validation.audit_sr_roll_repair_sources import build_report as build_source_audit


DEFAULT_CANDIDATE_DBN_ROOT = Path("data/dbn_sr_parent_candidate")
DEFAULT_SIDECAR_DBN_ROOT = Path("data/dbn")
DEFAULT_OUTPUT_ROOT = Path("data/raw_sr_front_contract_candidate")
DEFAULT_REPORTS_ROOT = Path("reports/sr_roll_parent_candidate")
DEFAULT_MARKETS = ("SR1", "SR3")
DEFAULT_YEARS = tuple(range(2018, 2027))
RAW_ALIGNMENT_NAME = "sr_front_contract_candidate_raw_alignment.json"
MANIFEST_NAME = "sr_front_contract_candidate_manifest.json"
QUARTERLY_MONTH_CODES = frozenset("HMUZ")
QUARTERLY_CHAIN_MARKETS = frozenset({"SR3"})


class DatabentoStore(Protocol):
    def to_df(self, *args: Any, **kwargs: Any) -> pd.DataFrame | list[pd.DataFrame]:
        ...


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dbn-root", default=str(DEFAULT_CANDIDATE_DBN_ROOT))
    parser.add_argument("--sidecar-dbn-root", default=str(DEFAULT_SIDECAR_DBN_ROOT))
    parser.add_argument("--definition-dbn-root", default=None)
    parser.add_argument("--status-dbn-root", default=None)
    parser.add_argument("--statistics-dbn-root", default=None)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT))
    parser.add_argument("--markets", nargs="+", default=list(DEFAULT_MARKETS))
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    parser.add_argument(
        "--exclude-market-years",
        nargs="*",
        default=[],
        help="Market-years to skip, formatted as MARKET:YEAR, e.g. SR3:2018.",
    )
    parser.add_argument("--profile", default="tier_3")
    parser.add_argument("--resolved-profile", default="tier_3_research")
    parser.add_argument("--overwrite-candidate", action="store_true")
    return parser


def _parse_excluded_market_years(values: Iterable[str]) -> set[tuple[str, int]]:
    excluded: set[tuple[str, int]] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if ":" not in text:
            raise ValueError(f"invalid excluded market-year {text!r}; expected MARKET:YEAR")
        market, year_text = text.split(":", 1)
        market = market.strip()
        if not market:
            raise ValueError(f"invalid excluded market-year {text!r}; missing market")
        try:
            year = int(year_text)
        except ValueError as exc:
            raise ValueError(
                f"invalid excluded market-year {text!r}; year must be an integer"
            ) from exc
        excluded.add((market, year))
    return excluded


def _ohlcv_paths(candidate_dbn_root: Path, market: str, year: int) -> list[Path]:
    roots = [
        candidate_dbn_root / "ohlcv_1m" / market / str(year),
        candidate_dbn_root / market / str(year),
    ]
    for root in roots:
        if root.exists():
            return sorted(root.glob("*.dbn.zst"))
    return []


def _load_ohlcv_frame(paths: Iterable[Path], market: str, year: int) -> pd.DataFrame:
    import databento as db

    frames: list[pd.DataFrame] = []
    for path in paths:
        failures = validate_raw_file_manifest(
            path,
            expected_schema=SCHEMA,
            expected_market=market,
            expected_year=year,
        )
        if failures:
            raise ValueError(
                f"OHLCV manifest validation failed for {path.as_posix()}: "
                + "; ".join(failures)
            )
        store = db.DBNStore.from_file(path)
        frames.append(store_to_required_dataframe(store))
    if not frames:
        raise ValueError(f"missing parent OHLCV DBN files for {market} {year}")
    return (
        pd.concat(frames, ignore_index=True)
        .sort_values("ts_event", kind="mergesort")
        .reset_index(drop=True)
    )


def _contract_metadata(definitions: pd.DataFrame) -> pd.DataFrame:
    required = {"instrument_id", "raw_symbol", "expiration", "maturity_year", "maturity_month"}
    missing = sorted(required - set(definitions.columns))
    if missing:
        raise ValueError("definition metadata missing fields: " + ",".join(missing))

    frame = definitions.copy()
    frame["_definition_ts"] = pd.to_datetime(frame["ts_event"], utc=True, errors="coerce")
    if "activation" in frame.columns:
        activation = pd.to_datetime(frame["activation"], utc=True, errors="coerce")
    else:
        activation = pd.Series(pd.NaT, index=frame.index)
    frame["_active_from"] = activation.fillna(frame["_definition_ts"])
    frame["_expiration"] = pd.to_datetime(frame["expiration"], utc=True, errors="coerce")
    frame["_maturity_ordinal"] = (
        pd.to_numeric(frame["maturity_year"], errors="coerce") * 12
        + pd.to_numeric(frame["maturity_month"], errors="coerce")
    )
    frame = frame.dropna(
        subset=[
            "instrument_id",
            "raw_symbol",
            "_active_from",
            "_expiration",
            "_maturity_ordinal",
        ]
    ).copy()
    if frame.empty:
        raise ValueError("definition metadata has no usable contracts")

    frame["instrument_id"] = pd.to_numeric(frame["instrument_id"], errors="raise").astype("int64")
    frame["_maturity_ordinal"] = frame["_maturity_ordinal"].astype("int64")
    grouped = (
        frame.sort_values(["instrument_id", "_definition_ts"], kind="mergesort")
        .groupby("instrument_id", sort=False)
        .agg(
            raw_symbol=("raw_symbol", "last"),
            active_from=("_active_from", "min"),
            expiration=("_expiration", "max"),
            maturity_ordinal=("_maturity_ordinal", "last"),
        )
        .reset_index()
    )
    return grouped


def _is_quarterly_raw_symbol(raw_symbol: object, market: str) -> bool:
    text = str(raw_symbol).strip()
    if len(text) != len(market) + 2 or not text.startswith(market):
        return False
    return text[len(market)] in QUARTERLY_MONTH_CODES


def _contract_universe_definitions(
    definitions: pd.DataFrame,
    market: str,
) -> tuple[pd.DataFrame, set[int], str]:
    if "instrument_class" not in definitions.columns:
        raise ValueError("definition metadata missing field: instrument_class")
    frame = definitions.loc[definitions["instrument_class"].astype("string").eq("F")].copy()
    if frame.empty:
        raise ValueError("definition metadata has no outright futures instruments")
    policy = "outright_futures"
    if market in QUARTERLY_CHAIN_MARKETS:
        frame = frame.loc[
            frame["raw_symbol"].map(lambda value: _is_quarterly_raw_symbol(value, market))
        ].copy()
        policy = "quarterly_outright_futures"
        if frame.empty:
            raise ValueError(
                f"definition metadata has no quarterly outright futures instruments for {market}"
            )
    instrument_ids = set(
        pd.to_numeric(frame["instrument_id"], errors="coerce")
        .dropna()
        .astype("int64")
        .tolist()
    )
    if not instrument_ids:
        raise ValueError("definition metadata has no usable outright instrument ids")
    return frame, instrument_ids, policy


def _front_instrument_by_timestamp(
    timestamps: Iterable[pd.Timestamp],
    contracts: pd.DataFrame,
) -> dict[pd.Timestamp, int]:
    front: dict[pd.Timestamp, int] = {}
    ordered = contracts.sort_values(
        ["expiration", "maturity_ordinal", "raw_symbol", "instrument_id"],
        kind="mergesort",
    )
    for ts in sorted(set(timestamps)):
        active = ordered.loc[
            ordered["active_from"].le(ts) & ordered["expiration"].ge(ts)
        ]
        if not active.empty:
            front[ts] = int(active.iloc[0]["instrument_id"])
    return front


def _maturity_backstep_count(frame: pd.DataFrame) -> int:
    maturity_year = pd.to_numeric(frame["maturity_year"], errors="coerce").astype("float64")
    maturity_month = pd.to_numeric(frame["maturity_month"], errors="coerce").astype("float64")
    maturity = maturity_year * 12 + maturity_month
    return int(maturity.diff().lt(0).sum())


def build_front_contract_candidate_frame(
    *,
    ohlcv: pd.DataFrame,
    definitions: pd.DataFrame,
    status: pd.DataFrame | None,
    statistics: pd.DataFrame | None,
    market: str,
    year: int,
    source_files: list[str],
    source_hashes: list[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    work = ohlcv.copy()
    work["ts_event"] = pd.to_datetime(work["ts_event"], utc=True, errors="coerce")
    work = work[work["ts_event"].notna()].copy()
    if work.empty:
        raise ValueError(f"no OHLCV rows for {market} {year}")

    raw_parent_ohlcv_rows = int(len(work))
    all_instrument_ids = pd.to_numeric(work["instrument_id"], errors="coerce")
    full_outright_defs = definitions.loc[
        definitions["instrument_class"].astype("string").eq("F")
    ].copy()
    full_outright_ids = set(
        pd.to_numeric(full_outright_defs["instrument_id"], errors="coerce")
        .dropna()
        .astype("int64")
        .tolist()
    )
    non_outright_mask = ~all_instrument_ids.isin(full_outright_ids)
    full_outright_rows = int((~non_outright_mask).sum())
    dropped_non_outright = int(non_outright_mask.sum())

    contract_definitions, contract_instrument_ids, contract_universe_policy = (
        _contract_universe_definitions(definitions, market)
    )
    work_instrument_ids = pd.to_numeric(work["instrument_id"], errors="coerce")
    universe_mask = work_instrument_ids.isin(contract_instrument_ids)
    dropped_non_contract_universe = int((~universe_mask & ~non_outright_mask).sum())
    work = work.loc[universe_mask].copy()
    if work.empty:
        raise ValueError(f"no eligible contract-universe OHLCV rows for {market} {year}")

    contracts = _contract_metadata(contract_definitions)
    timestamps = pd.to_datetime(work["ts_event"], utc=True, errors="coerce")
    front_by_ts = _front_instrument_by_timestamp(timestamps.dropna().tolist(), contracts)

    front_ids = timestamps.map(front_by_ts)
    instrument_ids = pd.to_numeric(work["instrument_id"], errors="coerce")
    selected = work.loc[front_ids.eq(instrument_ids)].copy()
    dropped_deferred = int(front_ids.notna().sum() - len(selected))
    dropped_no_front = int(front_ids.isna().sum())

    if selected.empty:
        raise ValueError(f"front-contract selection produced no rows for {market} {year}")
    duplicate_ts = int(selected.duplicated("ts_event", keep=False).sum())
    if duplicate_ts:
        raise ValueError(f"front-contract selection has duplicate timestamps: {duplicate_ts}")

    selected = selected.sort_values("ts_event", kind="mergesort").reset_index(drop=True)
    selected = enrich_with_definition_metadata(selected, contract_definitions)
    backsteps = _maturity_backstep_count(selected)
    if backsteps:
        raise ValueError(f"front-contract maturity sequence moved backward: {backsteps}")

    selected = enrich_with_status_metadata(selected, status)
    selected = enrich_with_statistics_metadata(selected, statistics)
    selected["datetime_utc"] = pd.to_datetime(selected["ts_event"], utc=True, errors="coerce")
    selected["market"] = market
    selected["year"] = year
    selected["source_schema"] = SCHEMA
    selected["source_dataset"] = CME_DATASET
    selected["source_file"] = ";".join(source_files)
    selected["source_sha256"] = ";".join(source_hashes)

    readiness_cols = [
        "datetime_utc",
        "market",
        "year",
        "raw_symbol",
        "tick_size",
        "contract_multiplier_or_point_value",
        "expiration",
        "maturity_year",
        "maturity_month",
        "source_schema",
        "source_dataset",
        "source_file",
        "source_sha256",
    ]
    output_columns = (
        ORDERED_OUTPUT_COLUMNS
        + [col for col in readiness_cols if col in selected.columns and col not in ORDERED_OUTPUT_COLUMNS]
        + [
            col
            for col in [*STATUS_ENRICHMENT_COLUMNS, *STATISTICS_ENRICHMENT_COLUMNS]
            if col in selected.columns and col not in ORDERED_OUTPUT_COLUMNS
        ]
    )
    selected = selected[output_columns].copy()

    def _missing_by_symbol(flag: str) -> list[dict[str, Any]]:
        if flag not in selected.columns or "raw_symbol" not in selected.columns:
            return []
        missing = selected.loc[selected[flag].fillna(True).astype(bool)]
        if missing.empty:
            return []
        counts = missing["raw_symbol"].astype(str).value_counts().head(20)
        return [
            {"raw_symbol": str(symbol), "rows": int(rows)}
            for symbol, rows in counts.items()
        ]

    selected_symbol_counts = [
        {"raw_symbol": str(symbol), "rows": int(rows)}
        for symbol, rows in selected["raw_symbol"].astype(str).value_counts().head(20).items()
    ] if "raw_symbol" in selected.columns else []
    metrics = {
        "raw_parent_ohlcv_rows": raw_parent_ohlcv_rows,
        "outright_ohlcv_rows": full_outright_rows,
        "contract_universe_ohlcv_rows": int(len(work)),
        "contract_universe_policy": contract_universe_policy,
        "dropped_non_outright_rows": dropped_non_outright,
        "dropped_non_contract_universe_rows": dropped_non_contract_universe,
        "candidate_rows": int(len(selected)),
        "dropped_deferred_contract_rows": dropped_deferred,
        "dropped_no_active_front_rows": dropped_no_front,
        "duplicate_timestamp_rows": duplicate_ts,
        "maturity_backstep_count": backsteps,
        "selected_symbol_counts": selected_symbol_counts,
        "status_missing_rows": (
            int(selected["status_missing"].fillna(True).astype(bool).sum())
            if "status_missing" in selected.columns
            else None
        ),
        "status_missing_by_symbol": _missing_by_symbol("status_missing"),
        "statistics_missing_rows": (
            int(selected["statistics_missing"].fillna(True).astype(bool).sum())
            if "statistics_missing" in selected.columns
            else None
        ),
        "statistics_missing_by_symbol": _missing_by_symbol("statistics_missing"),
        "optional_schema_match_summary": optional_schema_match_summary(
            selected,
            ("status", "statistics"),
        ),
    }
    return selected, metrics


def _write_raw_alignment_manifest(
    path: Path,
    *,
    profile: str,
    resolved_profile: str,
    candidate_dbn_root: Path,
    sidecar_dbn_root: Path | None = None,
    definition_dbn_root: Path | None = None,
    status_dbn_root: Path | None = None,
    statistics_dbn_root: Path | None = None,
    output_root: Path,
    rows: list[dict[str, Any]],
    failures: list[str],
    excluded_market_years: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    effective_sidecar_root = sidecar_dbn_root or candidate_dbn_root
    effective_definition_root = definition_dbn_root or effective_sidecar_root
    effective_status_root = status_dbn_root or effective_sidecar_root
    effective_statistics_root = statistics_dbn_root or effective_sidecar_root
    markets = sorted({str(row["market"]) for row in rows})
    years = sorted({int(row["year"]) for row in rows})
    market_years = [
        {"market": str(row["market"]), "year": int(row["year"])}
        for row in sorted(rows, key=lambda item: (str(item["market"]), int(item["year"])))
    ]
    status = "PASS" if not failures and rows else "FAIL"
    report = {
        "stage": "raw_dbn_alignment_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "audit_completeness": "full",
        "definition_join_skipped": False,
        "definition_join_status": "checked",
        "definition_join_checked_market_year_count": len(rows),
        "failures": failures,
        "dataset": CME_DATASET,
        "profile": profile,
        "resolved_profile": resolved_profile,
        "markets": markets,
        "years": years,
        "market_years": market_years,
        "excluded_market_years": excluded_market_years or [],
        "dbn_root": candidate_dbn_root.as_posix(),
        "sidecar_dbn_root": effective_sidecar_root.as_posix(),
        "definition_dbn_root": effective_definition_root.as_posix(),
        "status_dbn_root": effective_status_root.as_posix(),
        "statistics_dbn_root": effective_statistics_root.as_posix(),
        "raw_root": output_root.as_posix(),
        "expected_market_year_count": len(rows),
        "pre_availability_exemption_count": 0,
        "ohlcv_dbn_market_year_count": len(rows),
        "definition_dbn_market_year_count": len(rows),
        "raw_market_year_count": len(rows),
        "missing_ohlcv_dbn_count": 0,
        "missing_definition_dbn_count": 0,
        "missing_raw_count": 0,
        "needs_phase1b_conversion_count": 0,
        "dbn_only_inventory_count": 0,
        "raw_only_count": 0,
        "invalid_manifest_count": 0,
        "raw_schema_failure_count": 0,
        "source_hash_mismatch_count": 0,
        "definition_join_mismatch_count": 0,
        "pre_availability_exemptions": [],
        "missing_ohlcv_dbn": [],
        "missing_definition_dbn": [],
        "missing_raw": [],
        "needs_phase1b_conversion": [],
        "dbn_only_inventory": [],
        "raw_only_market_years": [],
        "invalid_manifests": [],
        "raw_schema_failures": [],
        "source_hash_mismatches": [],
        "definition_join_mismatches": [],
        "raw_file_metrics": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return report


def build_candidate_outputs(
    *,
    candidate_dbn_root: Path,
    sidecar_dbn_root: Path,
    definition_dbn_root: Path | None = None,
    status_dbn_root: Path | None = None,
    statistics_dbn_root: Path | None = None,
    output_root: Path,
    reports_root: Path,
    markets: list[str],
    years: list[int],
    profile: str,
    resolved_profile: str,
    excluded_market_years: set[tuple[str, int]] | None = None,
    overwrite_candidate: bool = False,
) -> dict[str, Any]:
    excluded_market_years = excluded_market_years or set()
    effective_definition_root = definition_dbn_root or sidecar_dbn_root
    effective_status_root = status_dbn_root or sidecar_dbn_root
    effective_statistics_root = statistics_dbn_root or sidecar_dbn_root
    source_audit = build_source_audit(
        dbn_root=candidate_dbn_root,
        sidecar_dbn_root=sidecar_dbn_root,
        definition_dbn_root=effective_definition_root,
        status_dbn_root=effective_status_root,
        statistics_dbn_root=effective_statistics_root,
        markets=markets,
        years=years,
    )
    reports_root.mkdir(parents=True, exist_ok=True)
    if source_audit["status"] != "PASS":
        report = {
            "stage": "sr_front_contract_candidate_build",
            "status": "FAIL",
            "source_audit": source_audit,
            "outputs": [],
            "failures": ["source audit failed; no candidate raw files written"],
        }
        (reports_root / MANIFEST_NAME).write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        return report

    outputs: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    failures: list[str] = []
    selected_market_years = [
        (market, year)
        for market in markets
        for year in years
        if (market, year) not in excluded_market_years
    ]
    skipped_market_years = [
        {"market": market, "year": year, "reason": "explicit_candidate_exclusion"}
        for market, year in sorted(excluded_market_years)
        if market in set(markets) and year in set(years)
    ]
    for market, year in selected_market_years:
        output_path = output_root / market / f"{year}.parquet"
        if output_path.exists() and not overwrite_candidate:
            failures.append(
                f"candidate output already exists; rerun with --overwrite-candidate: "
                f"{output_path.as_posix()}"
            )
            continue
        try:
            paths = _ohlcv_paths(candidate_dbn_root, market, year)
            source_files = [path.as_posix() for path in paths]
            source_hashes = [file_sha256(path) for path in paths]
            ohlcv = _load_ohlcv_frame(paths, market, year)
            definitions, definition_paths = definition_frame_for_group(
                effective_definition_root,
                market,
                year,
            )
            status_frame = load_optional_schema_frame_for_group(
                effective_status_root,
                "status",
                market,
                year,
                policy="require",
            )
            statistics_frame = load_optional_schema_frame_for_group(
                effective_statistics_root,
                "statistics",
                market,
                year,
                policy="require",
            )
            candidate, metrics = build_front_contract_candidate_frame(
                ohlcv=ohlcv,
                definitions=definitions,
                status=status_frame.frame,
                statistics=statistics_frame.frame,
                market=market,
                year=year,
                source_files=source_files,
                source_hashes=source_hashes,
            )
            diagnostics.append({"market": market, "year": year, **metrics})
            status_missing = int(metrics.get("status_missing_rows") or 0)
            statistics_missing = int(metrics.get("statistics_missing_rows") or 0)
            if status_missing or statistics_missing:
                failures.append(
                    f"{market} {year}: sidecar enrichment incomplete: "
                    f"status_missing_rows={status_missing} "
                    f"statistics_missing_rows={statistics_missing} "
                    f"status_missing_by_symbol={metrics.get('status_missing_by_symbol', [])} "
                    f"statistics_missing_by_symbol={metrics.get('statistics_missing_by_symbol', [])}"
                )
                continue
            write_required_dataframe_parquet(candidate, output_path)
            output_hash = file_sha256(output_path)
            outputs.append(
                {
                    "market": market,
                    "year": year,
                    "status": "PASS",
                    "output_path": output_path.as_posix(),
                    "output_hash": output_hash,
                    "ohlcv_input_paths": source_files,
                    "definition_paths": [path.as_posix() for path in definition_paths],
                    "status_paths": [path.as_posix() for path in status_frame.paths],
                    "statistics_paths": [path.as_posix() for path in statistics_frame.paths],
                    **metrics,
                }
            )
        except Exception as exc:
            failures.append(f"{market} {year}: {exc}")

    alignment = _write_raw_alignment_manifest(
        reports_root / RAW_ALIGNMENT_NAME,
        profile=profile,
        resolved_profile=resolved_profile,
        candidate_dbn_root=candidate_dbn_root,
        sidecar_dbn_root=sidecar_dbn_root,
        definition_dbn_root=effective_definition_root,
        status_dbn_root=effective_status_root,
        statistics_dbn_root=effective_statistics_root,
        output_root=output_root,
        rows=outputs,
        failures=failures,
        excluded_market_years=skipped_market_years,
    )
    report = {
        "stage": "sr_front_contract_candidate_build",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures and outputs else "FAIL",
        "source_audit": source_audit,
        "candidate_dbn_root": candidate_dbn_root.as_posix(),
        "sidecar_dbn_root": sidecar_dbn_root.as_posix(),
        "definition_dbn_root": effective_definition_root.as_posix(),
        "status_dbn_root": effective_status_root.as_posix(),
        "statistics_dbn_root": effective_statistics_root.as_posix(),
        "output_root": output_root.as_posix(),
        "raw_alignment_manifest": (reports_root / RAW_ALIGNMENT_NAME).as_posix(),
        "raw_alignment_status": alignment["status"],
        "output_count": len(outputs),
        "outputs": outputs,
        "diagnostics": diagnostics,
        "excluded_market_years": skipped_market_years,
        "failures": failures,
        "next_action": (
            "Run bounded Phase 2 readiness using the candidate raw root and "
            "candidate raw-alignment manifest."
            if not failures and outputs
            else "Fix candidate source/build failures before Phase 2 readiness."
        ),
    }
    (reports_root / MANIFEST_NAME).write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        excluded_market_years = _parse_excluded_market_years(args.exclude_market_years)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    report = build_candidate_outputs(
        candidate_dbn_root=Path(args.candidate_dbn_root),
        sidecar_dbn_root=Path(args.sidecar_dbn_root),
        definition_dbn_root=Path(args.definition_dbn_root) if args.definition_dbn_root else None,
        status_dbn_root=Path(args.status_dbn_root) if args.status_dbn_root else None,
        statistics_dbn_root=(
            Path(args.statistics_dbn_root) if args.statistics_dbn_root else None
        ),
        output_root=Path(args.output_root),
        reports_root=Path(args.reports_root),
        markets=[str(market) for market in args.markets],
        years=[int(year) for year in args.years],
        profile=str(args.profile),
        resolved_profile=str(args.resolved_profile),
        excluded_market_years=excluded_market_years,
        overwrite_candidate=bool(args.overwrite_candidate),
    )
    print(
        f"{report['status']} SR front-contract candidate build: "
        f"outputs={report.get('output_count', 0)} failures={len(report.get('failures', []))}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
