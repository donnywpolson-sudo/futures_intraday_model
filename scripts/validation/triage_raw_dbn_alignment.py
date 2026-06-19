#!/usr/bin/env python3
"""Triage raw parquet alignment failures without mutating canonical raw data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1A_download.download_databento_raw import (  # noqa: E402
    SCHEMA,
    definition_frame_for_group,
    enrich_with_definition_metadata,
    file_sha256,
)
from scripts.validation.audit_raw_dbn_alignment import (  # noqa: E402
    DEFINITION_COMPARE_COLUMNS,
    RAW_OPTIONAL_AUDIT_COLUMNS,
    RAW_REQUIRED_COLUMNS,
    _index_schema_dbns,
    _read_raw_audit_frame,
    _split_semicolon_values,
    _numeric_equal,
    _series_equal,
)


IDENTITY_COLUMNS = ["ts_event", "open", "high", "low", "close", "volume", "instrument_id"]
METADATA_COLUMNS = ["raw_symbol", "tick_size", "contract_multiplier_or_point_value", "source_sha256"]


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def market_year_key(row: dict[str, Any]) -> tuple[str, int]:
    return str(row["market"]), int(row["year"])


def sorted_keys(rows: Iterable[dict[str, Any]]) -> list[tuple[str, int]]:
    return sorted({market_year_key(row) for row in rows})


def source_hash_mismatch_keys(report: dict[str, Any], *, year: int | None = None) -> list[tuple[str, int]]:
    keys = sorted_keys(report.get("source_hash_mismatches", []))
    return [key for key in keys if year is None or key[1] == year]


def definition_mismatch_keys(report: dict[str, Any]) -> list[tuple[str, int]]:
    return sorted_keys(report.get("definition_join_mismatches", []))


def missing_raw_keys(report: dict[str, Any]) -> list[tuple[str, int]]:
    return sorted_keys(report.get("needs_phase1b_conversion", []))


def _path_interval(path: Path) -> tuple[date, date] | None:
    stem = path.name.removesuffix(".dbn.zst").removesuffix(".dbn")
    parts = stem.split("_")
    if len(parts) != 2:
        return None
    try:
        return date.fromisoformat(parts[0]), date.fromisoformat(parts[1])
    except ValueError:
        return None


def preferred_non_overlapping_paths(paths: Iterable[Path]) -> list[Path]:
    selected: list[Path] = []
    path_list = sorted(paths)
    intervals = {path: _path_interval(path) for path in path_list}
    for path in path_list:
        interval = intervals[path]
        if interval is None:
            selected.append(path)
            continue
        start, end = interval
        contained = False
        for other, other_interval in intervals.items():
            if other == path or other_interval is None:
                continue
            other_start, other_end = other_interval
            if other_start <= start and other_end >= end and (other_start, other_end) != (start, end):
                contained = True
                break
        if not contained:
            selected.append(path)
    return selected


def paths_for_keys(
    keys: Iterable[tuple[str, int]],
    dbn_root: Path,
    *,
    schema: str = SCHEMA,
    prefer_non_overlapping: bool = True,
) -> list[Path]:
    index = _index_schema_dbns(dbn_root, schema)
    paths: list[Path] = []
    for key in sorted(keys):
        key_paths = index.get(key, [])
        if prefer_non_overlapping:
            key_paths = preferred_non_overlapping_paths(key_paths)
        paths.extend(key_paths)
    return sorted(paths)


def build_source_path_report(
    *,
    alignment_report: dict[str, Any],
    dbn_root: Path,
    year: int = 2026,
) -> dict[str, Any]:
    keys = source_hash_mismatch_keys(alignment_report, year=year)
    rows = [
        {"market": market, "year": year_, "paths": [path.as_posix() for path in paths_for_keys([(market, year_)], dbn_root)]}
        for market, year_ in keys
    ]
    return {
        "stage": "raw_alignment_source_hash_path_selection",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "year": year,
        "market_year_count": len(rows),
        "path_count": sum(len(row["paths"]) for row in rows),
        "rows": rows,
        "paths": [path for row in rows for path in row["paths"]],
    }


def build_definition_path_report(
    *,
    alignment_report: dict[str, Any],
    dbn_root: Path,
) -> dict[str, Any]:
    keys = definition_mismatch_keys(alignment_report)
    rows = [
        {"market": market, "year": year, "paths": [path.as_posix() for path in paths_for_keys([(market, year)], dbn_root)]}
        for market, year in keys
    ]
    return {
        "stage": "raw_alignment_definition_path_selection",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_year_count": len(rows),
        "path_count": sum(len(row["paths"]) for row in rows),
        "rows": rows,
        "paths": [path for row in rows for path in row["paths"]],
    }


def _read_identity(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path, columns=IDENTITY_COLUMNS)


def _timestamp_bounds(df: pd.DataFrame) -> tuple[str | None, str | None]:
    if df.empty or "ts_event" not in df.columns:
        return None, None
    ts = pd.to_datetime(df["ts_event"], utc=True, errors="coerce")
    return (
        ts.min().isoformat() if ts.notna().any() else None,
        ts.max().isoformat() if ts.notna().any() else None,
    )


def _identity_difference_count(base: pd.DataFrame, candidate: pd.DataFrame) -> int | None:
    if len(base) != len(candidate):
        return None
    base_norm = base.reset_index(drop=True).copy()
    candidate_norm = candidate.reset_index(drop=True).copy()
    base_norm["ts_event"] = pd.to_datetime(base_norm["ts_event"], utc=True, errors="coerce")
    candidate_norm["ts_event"] = pd.to_datetime(candidate_norm["ts_event"], utc=True, errors="coerce")
    unequal = pd.Series(False, index=base_norm.index)
    for column in IDENTITY_COLUMNS:
        if column == "ts_event":
            equal = base_norm[column].eq(candidate_norm[column])
        elif column in {"open", "high", "low", "close", "volume"}:
            equal = _numeric_equal(base_norm[column], candidate_norm[column])
        else:
            equal = base_norm[column].astype("string").eq(candidate_norm[column].astype("string"))
        unequal = unequal | ~equal.fillna(False)
    return int(unequal.sum())


def _prefix_identity_difference_count(base: pd.DataFrame, candidate: pd.DataFrame) -> int | None:
    n = min(len(base), len(candidate))
    if n == 0:
        return 0 if len(base) == len(candidate) else None
    return _identity_difference_count(base.iloc[:n].reset_index(drop=True), candidate.iloc[:n].reset_index(drop=True))


def _read_existing_columns(path: Path, columns: list[str]) -> pd.DataFrame:
    available = set(pd.read_parquet(path).columns)
    selected = [column for column in columns if column in available]
    return pd.read_parquet(path, columns=selected)


def _metadata_difference_counts(base_path: Path, candidate_path: Path) -> dict[str, int]:
    base = _read_existing_columns(base_path, METADATA_COLUMNS)
    candidate = _read_existing_columns(candidate_path, METADATA_COLUMNS)
    counts: dict[str, int] = {}
    if len(base) != len(candidate):
        return counts
    for column in METADATA_COLUMNS:
        if column not in base.columns or column not in candidate.columns:
            continue
        equal = _series_equal(base[column], candidate[column]) if column in {"raw_symbol", "source_sha256"} else _numeric_equal(base[column], candidate[column])
        count = int((~equal.fillna(False)).sum())
        if count:
            counts[column] = count
    return counts


def _candidate_change_type(
    *,
    base_rows: int,
    candidate_rows: int,
    identity_difference_count: int | None,
    prefix_identity_difference_count: int | None,
    metadata_difference_counts: dict[str, int],
) -> str:
    if base_rows == candidate_rows and identity_difference_count == 0 and not metadata_difference_counts:
        return "unchanged"
    if base_rows == candidate_rows and identity_difference_count == 0 and metadata_difference_counts:
        return "metadata_only"
    if candidate_rows > base_rows and prefix_identity_difference_count == 0:
        return "tail_addition"
    return "row_or_identity_diff"


def compare_candidate_to_raw(
    *,
    keys: Iterable[tuple[str, int]],
    base_root: Path,
    candidate_root: Path,
    dbn_root: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    schema_signatures: set[tuple[str, ...]] = set()
    for market, year in sorted(keys):
        base_path = base_root / market / f"{year}.parquet"
        candidate_path = candidate_root / market / f"{year}.parquet"
        row: dict[str, Any] = {
            "market": market,
            "year": year,
            "base_path": base_path.as_posix(),
            "candidate_path": candidate_path.as_posix(),
            "base_exists": base_path.exists(),
            "candidate_exists": candidate_path.exists(),
        }
        if not base_path.exists() or not candidate_path.exists():
            row["status"] = "missing_input"
            rows.append(row)
            continue
        base = _read_identity(base_path)
        candidate = _read_identity(candidate_path)
        base_first, base_last = _timestamp_bounds(base)
        candidate_first, candidate_last = _timestamp_bounds(candidate)
        candidate_columns = tuple(pd.read_parquet(candidate_path).columns)
        schema_signatures.add(candidate_columns)
        candidate_audit = _read_raw_audit_frame(candidate_path, ["source_sha256"])
        local_hashes = {file_sha256(path) for path in paths_for_keys([(market, year)], dbn_root)}
        candidate_hashes = _split_semicolon_values(candidate_audit["source_sha256"])
        identity_difference_count = _identity_difference_count(base, candidate)
        prefix_identity_difference_count = _prefix_identity_difference_count(base, candidate)
        metadata_difference_counts = _metadata_difference_counts(base_path, candidate_path)
        change_type = _candidate_change_type(
            base_rows=len(base),
            candidate_rows=len(candidate),
            identity_difference_count=identity_difference_count,
            prefix_identity_difference_count=prefix_identity_difference_count,
            metadata_difference_counts=metadata_difference_counts,
        )
        row.update(
            {
                "status": "PASS" if change_type == "unchanged" else "DIFF",
                "change_type": change_type,
                "base_rows": int(len(base)),
                "candidate_rows": int(len(candidate)),
                "row_count_delta": int(len(candidate) - len(base)),
                "identity_difference_count": identity_difference_count,
                "prefix_identity_difference_count": prefix_identity_difference_count,
                "metadata_difference_counts": metadata_difference_counts,
                "base_first_ts": base_first,
                "base_last_ts": base_last,
                "candidate_first_ts": candidate_first,
                "candidate_last_ts": candidate_last,
                "candidate_source_hashes": sorted(candidate_hashes),
                "local_dbn_hashes": sorted(local_hashes),
                "candidate_hashes_match_local_dbn": not (candidate_hashes - local_hashes),
            }
        )
        rows.append(row)
    diff_count = sum(1 for row in rows if row.get("status") != "PASS")
    return {
        "stage": "raw_alignment_candidate_compare",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_root": base_root.as_posix(),
        "candidate_root": candidate_root.as_posix(),
        "dbn_root": dbn_root.as_posix(),
        "market_year_count": len(rows),
        "diff_count": diff_count,
        "schema_signature_count": len(schema_signatures),
        "status": "PASS" if diff_count == 0 and len(schema_signatures) == 1 else "FAIL",
        "rows": rows,
    }


def _definition_paths_and_hashes(dbn_root: Path, key: tuple[str, int]) -> list[dict[str, str]]:
    return [
        {"path": path.as_posix(), "sha256": file_sha256(path)}
        for path in _index_schema_dbns(dbn_root, "definition").get(key, [])
    ]


def _raw_source_paths_and_hashes(df: pd.DataFrame) -> list[dict[str, str]]:
    paths = _split_semicolon_values(df["source_file"]) if "source_file" in df.columns else set()
    hashes = _split_semicolon_values(df["source_sha256"]) if "source_sha256" in df.columns else set()
    rows: list[dict[str, str]] = []
    for path in sorted(paths):
        rows.append({"path": path})
    if not rows:
        rows.append({})
    rows[0]["source_sha256_values"] = ";".join(sorted(hashes))
    return rows


def build_definition_drilldown(
    *,
    alignment_report: dict[str, Any],
    dbn_root: Path,
    raw_root: Path,
) -> dict[str, Any]:
    source_hash_keys = set(source_hash_mismatch_keys(alignment_report))
    rows: list[dict[str, Any]] = []
    for key in sorted_keys(alignment_report.get("definition_join_mismatches", [])):
        market, year = key
        raw_path = raw_root / market / f"{year}.parquet"
        raw = _read_raw_audit_frame(raw_path, RAW_REQUIRED_COLUMNS + RAW_OPTIONAL_AUDIT_COLUMNS)
        definitions, _ = definition_frame_for_group(dbn_root, market, year)
        expected = enrich_with_definition_metadata(raw[["ts_event", "instrument_id"]].copy(), definitions)
        field_rows: list[dict[str, Any]] = []
        for column in DEFINITION_COMPARE_COLUMNS:
            if column not in raw.columns or column not in expected.columns:
                continue
            equal = _series_equal(raw[column], expected[column]) if column == "raw_symbol" else _numeric_equal(raw[column], expected[column])
            mismatch_mask = ~equal.fillna(False)
            if not bool(mismatch_mask.any()):
                continue
            mismatched = raw.loc[mismatch_mask, ["ts_event", "instrument_id", column]].copy()
            expected_mismatched = expected.loc[mismatch_mask, column]
            ts = pd.to_datetime(mismatched["ts_event"], utc=True, errors="coerce")
            instrument_counts = (
                mismatched.assign(_ts=ts)
                .groupby("instrument_id", dropna=False)
                .agg(rows=("instrument_id", "size"), first_ts=("_ts", "min"), last_ts=("_ts", "max"))
                .reset_index()
                .sort_values(["rows", "instrument_id"], ascending=[False, True])
            )
            samples: list[dict[str, Any]] = []
            for idx in list(mismatched.index[:5]):
                samples.append(
                    {
                        "ts_event": str(raw.at[idx, "ts_event"]),
                        "instrument_id": None if pd.isna(raw.at[idx, "instrument_id"]) else str(raw.at[idx, "instrument_id"]),
                        "raw_value": None if pd.isna(raw.at[idx, column]) else str(raw.at[idx, column]),
                        "definition_value": None if pd.isna(expected.at[idx, column]) else str(expected.at[idx, column]),
                    }
                )
            field_rows.append(
                {
                    "field": column,
                    "mismatch_rows": int(mismatch_mask.sum()),
                    "affected_instrument_count": int(mismatched["instrument_id"].nunique(dropna=True)),
                    "first_ts": ts.min().isoformat() if ts.notna().any() else None,
                    "last_ts": ts.max().isoformat() if ts.notna().any() else None,
                    "top_instruments": [
                        {
                            "instrument_id": None if pd.isna(item["instrument_id"]) else str(item["instrument_id"]),
                            "rows": int(item["rows"]),
                            "first_ts": item["first_ts"].isoformat() if pd.notna(item["first_ts"]) else None,
                            "last_ts": item["last_ts"].isoformat() if pd.notna(item["last_ts"]) else None,
                        }
                        for item in instrument_counts.head(10).to_dict("records")
                    ],
                    "samples": samples,
                }
            )
        classification = (
            "requires_candidate_rebuild_check"
            if key in source_hash_keys
            else "raw_metadata_stale_against_current_definition_dbn"
        )
        rows.append(
            {
                "market": market,
                "year": year,
                "classification": classification,
                "raw_path": raw_path.as_posix(),
                "raw_sources": _raw_source_paths_and_hashes(raw),
                "definition_sources": _definition_paths_and_hashes(dbn_root, key),
                "fields": field_rows,
            }
        )
    classifications: dict[str, int] = {}
    for row in rows:
        classification = str(row["classification"])
        classifications[classification] = classifications.get(classification, 0) + 1
    return {
        "stage": "raw_definition_mismatch_drilldown",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dbn_root": dbn_root.as_posix(),
        "raw_root": raw_root.as_posix(),
        "market_year_count": len(rows),
        "classifications": dict(sorted(classifications.items())),
        "rows": rows,
    }


def _metadata_equal(column: str, left: pd.Series, right: pd.Series) -> pd.Series:
    return _series_equal(left, right) if column == "raw_symbol" else _numeric_equal(left, right)


def _value_at(df: pd.DataFrame, idx: int, column: str) -> str | None:
    if column not in df.columns:
        return None
    value = df.at[idx, column]
    return None if pd.isna(value) else str(value)


def _metadata_mismatch_counts(actual: pd.DataFrame, expected: pd.DataFrame, *, row_count: int | None = None) -> dict[str, int]:
    n = min(len(actual), len(expected)) if row_count is None else min(row_count, len(actual), len(expected))
    actual_view = actual.iloc[:n].reset_index(drop=True)
    expected_view = expected.iloc[:n].reset_index(drop=True)
    counts: dict[str, int] = {}
    for column in DEFINITION_COMPARE_COLUMNS:
        if column not in actual_view.columns or column not in expected_view.columns:
            continue
        equal = _metadata_equal(column, actual_view[column], expected_view[column])
        count = int((~equal.fillna(False)).sum())
        if count:
            counts[column] = count
    return counts


def _metadata_diff_counts_between_frames(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, int]:
    n = min(len(left), len(right))
    left_view = left.iloc[:n].reset_index(drop=True)
    right_view = right.iloc[:n].reset_index(drop=True)
    counts: dict[str, int] = {}
    for column in DEFINITION_COMPARE_COLUMNS:
        if column not in left_view.columns or column not in right_view.columns:
            continue
        equal = _metadata_equal(column, left_view[column], right_view[column])
        count = int((~equal.fillna(False)).sum())
        if count:
            counts[column] = count
    return counts


def _root_cause_sample_rows(
    canonical: pd.DataFrame,
    candidate: pd.DataFrame,
    expected: pd.DataFrame,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    n = min(len(canonical), len(candidate), len(expected))
    canonical_view = canonical.iloc[:n].reset_index(drop=True)
    candidate_view = candidate.iloc[:n].reset_index(drop=True)
    expected_view = expected.iloc[:n].reset_index(drop=True)
    samples: list[dict[str, Any]] = []
    for column in DEFINITION_COMPARE_COLUMNS:
        if column not in canonical_view.columns or column not in candidate_view.columns or column not in expected_view.columns:
            continue
        canonical_equal = _metadata_equal(column, canonical_view[column], expected_view[column])
        candidate_equal = _metadata_equal(column, candidate_view[column], expected_view[column])
        canonical_candidate_equal = _metadata_equal(column, canonical_view[column], candidate_view[column])
        sample_mask = ~(canonical_equal & candidate_equal & canonical_candidate_equal).fillna(False)
        for idx in list(canonical_view.index[sample_mask]):
            samples.append(
                {
                    "field": column,
                    "ts_event": _value_at(canonical_view, int(idx), "ts_event"),
                    "instrument_id": _value_at(canonical_view, int(idx), "instrument_id"),
                    "canonical_value": _value_at(canonical_view, int(idx), column),
                    "candidate_value": _value_at(candidate_view, int(idx), column),
                    "definition_value": _value_at(expected_view, int(idx), column),
                }
            )
            if len(samples) >= limit:
                return samples
    return samples


def _classify_definition_root_cause(
    *,
    candidate_change_type: str | None,
    canonical_mismatches: dict[str, int],
    candidate_mismatches: dict[str, int],
    candidate_overlap_mismatches: dict[str, int],
    canonical_candidate_overlap_diff_counts: dict[str, int],
) -> str:
    if not canonical_mismatches and not candidate_mismatches and not candidate_overlap_mismatches:
        return "audit_rule_index_alignment_false_positive"
    if canonical_mismatches and not candidate_mismatches:
        return "candidate_fixes_stale_raw_metadata"
    if (
        candidate_change_type == "tail_addition"
        and not canonical_candidate_overlap_diff_counts
        and candidate_overlap_mismatches
    ):
        return "tail_addition_no_metadata_fix"
    if not canonical_candidate_overlap_diff_counts and candidate_overlap_mismatches:
        return "candidate_unchanged_definition_mismatch"
    return "candidate_changes_but_still_mismatches"


def _preferred_root_cause_sample(
    rows: list[dict[str, Any]],
    *,
    classification: str,
    preferred_key: tuple[str, int],
) -> dict[str, Any] | None:
    matching = [row for row in rows if row.get("classification") == classification]
    for row in matching:
        if (row.get("market"), row.get("year")) == preferred_key:
            return row
    return matching[0] if matching else None


def build_definition_root_cause(
    *,
    alignment_report: dict[str, Any],
    candidate_compare_report: dict[str, Any],
    dbn_root: Path,
    raw_root: Path,
    candidate_root: Path,
) -> dict[str, Any]:
    compare_rows = {market_year_key(row): row for row in candidate_compare_report.get("rows", [])}
    rows: list[dict[str, Any]] = []
    field_mismatch_counts = {"canonical": {}, "candidate": {}, "candidate_overlap": {}}
    read_columns = ["ts_event", "instrument_id", *DEFINITION_COMPARE_COLUMNS]
    for key in definition_mismatch_keys(alignment_report):
        market, year = key
        raw_path = raw_root / market / f"{year}.parquet"
        candidate_path = candidate_root / market / f"{year}.parquet"
        compare_row = compare_rows.get(key, {})
        base_row: dict[str, Any] = {
            "market": market,
            "year": year,
            "raw_path": raw_path.as_posix(),
            "candidate_path": candidate_path.as_posix(),
            "candidate_change_type": compare_row.get("change_type"),
        }
        try:
            canonical = _read_raw_audit_frame(raw_path, read_columns)
            candidate = _read_raw_audit_frame(candidate_path, read_columns)
            definitions, _ = definition_frame_for_group(dbn_root, market, year)
            expected_canonical = enrich_with_definition_metadata(
                canonical[["ts_event", "instrument_id"]].copy(),
                definitions,
            )
            expected_candidate = enrich_with_definition_metadata(
                candidate[["ts_event", "instrument_id"]].copy(),
                definitions,
            )
        except Exception as exc:
            rows.append({**base_row, "classification": "definition_join_rebuild_failed", "failure": str(exc)})
            continue

        canonical_mismatches = _metadata_mismatch_counts(canonical, expected_canonical)
        candidate_mismatches = _metadata_mismatch_counts(candidate, expected_candidate)
        candidate_overlap_mismatches = _metadata_mismatch_counts(
            candidate,
            expected_candidate,
            row_count=len(canonical),
        )
        canonical_candidate_overlap_diff_counts = _metadata_diff_counts_between_frames(canonical, candidate)
        classification = _classify_definition_root_cause(
            candidate_change_type=compare_row.get("change_type"),
            canonical_mismatches=canonical_mismatches,
            candidate_mismatches=candidate_mismatches,
            candidate_overlap_mismatches=candidate_overlap_mismatches,
            canonical_candidate_overlap_diff_counts=canonical_candidate_overlap_diff_counts,
        )
        for bucket, counts in [
            ("canonical", canonical_mismatches),
            ("candidate", candidate_mismatches),
            ("candidate_overlap", candidate_overlap_mismatches),
        ]:
            for field, count in counts.items():
                field_mismatch_counts[bucket][field] = field_mismatch_counts[bucket].get(field, 0) + int(count)
        rows.append(
            {
                **base_row,
                "classification": classification,
                "canonical_rows": int(len(canonical)),
                "candidate_rows": int(len(candidate)),
                "canonical_mismatch_counts": canonical_mismatches,
                "candidate_mismatch_counts": candidate_mismatches,
                "candidate_overlap_mismatch_counts": candidate_overlap_mismatches,
                "canonical_candidate_overlap_diff_counts": canonical_candidate_overlap_diff_counts,
                "sample_rows": _root_cause_sample_rows(canonical, candidate, expected_canonical),
            }
        )

    classifications: dict[str, int] = {}
    for row in rows:
        classification = str(row["classification"])
        classifications[classification] = classifications.get(classification, 0) + 1
    unchanged_sample = _preferred_root_cause_sample(
        rows,
        classification="candidate_unchanged_definition_mismatch",
        preferred_key=("6M", 2012),
    )
    tail_sample = _preferred_root_cause_sample(
        rows,
        classification="tail_addition_no_metadata_fix",
        preferred_key=("HO", 2026),
    )
    return {
        "stage": "raw_definition_root_cause",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dbn_root": dbn_root.as_posix(),
        "raw_root": raw_root.as_posix(),
        "candidate_root": candidate_root.as_posix(),
        "market_year_count": len(rows),
        "classifications": dict(sorted(classifications.items())),
        "field_mismatch_counts": {
            key: dict(sorted(value.items())) for key, value in field_mismatch_counts.items()
        },
        "representative_samples": {
            "unchanged": unchanged_sample,
            "tail_addition": tail_sample,
        },
        "rows": rows,
    }


def build_missing_raw_path_report(
    *,
    alignment_report: dict[str, Any],
    dbn_root: Path,
    raw_root: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for key in sorted_keys(alignment_report.get("needs_phase1b_conversion", [])):
        market, year = key
        raw_path = raw_root / market / f"{year}.parquet"
        if raw_path.exists():
            continue
        paths = paths_for_keys([key], dbn_root)
        rows.append(
            {
                "market": market,
                "year": year,
                "raw_path": raw_path.as_posix(),
                "paths": [path.as_posix() for path in paths],
            }
        )
    return {
        "stage": "raw_alignment_missing_raw_path_selection",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_root": raw_root.as_posix(),
        "dbn_root": dbn_root.as_posix(),
        "market_year_count": len(rows),
        "path_count": sum(len(row["paths"]) for row in rows),
        "rows": rows,
        "paths": [path for row in rows for path in row["paths"]],
    }


def _candidate_row_counts(current_path: Path, candidate_path: Path) -> dict[str, Any]:
    counts: dict[str, Any] = {
        "current_exists": current_path.exists(),
        "candidate_exists": candidate_path.exists(),
    }
    if current_path.exists():
        counts["current_rows"] = int(len(pd.read_parquet(current_path, columns=["ts_event"])))
    if candidate_path.exists():
        counts["candidate_rows"] = int(len(pd.read_parquet(candidate_path, columns=["ts_event"])))
        counts["candidate_sha256"] = file_sha256(candidate_path)
    if counts.get("current_exists") and counts.get("candidate_exists"):
        counts["row_count_delta"] = int(counts["candidate_rows"] - counts["current_rows"])
    return counts


def build_promotion_manifest(
    *,
    alignment_report: dict[str, Any],
    raw_root: Path,
    candidate_2026_root: Path,
    definition_candidate_root: Path,
    missing_candidate_root: Path,
) -> dict[str, Any]:
    source_keys = set(source_hash_mismatch_keys(alignment_report, year=2026))
    definition_keys = set(definition_mismatch_keys(alignment_report))
    missing_keys = set(missing_raw_keys(alignment_report))
    rows: list[dict[str, Any]] = []
    for key in sorted(source_keys | definition_keys | missing_keys):
        market, year = key
        groups = sorted(
            group
            for group, keys in {
                "source_hash_2026": source_keys,
                "definition_mismatch": definition_keys,
                "missing_raw": missing_keys,
            }.items()
            if key in keys
        )
        if key in missing_keys:
            action = "add_missing_raw"
            candidate_root = missing_candidate_root
        elif key in definition_keys:
            action = "replace_with_definition_fix_candidate"
            candidate_root = definition_candidate_root
        else:
            action = "replace_with_2026_refresh_candidate"
            candidate_root = candidate_2026_root
        current_path = raw_root / market / f"{year}.parquet"
        candidate_path = candidate_root / market / f"{year}.parquet"
        counts = _candidate_row_counts(current_path, candidate_path)
        status = "ready" if candidate_path.exists() and (action == "add_missing_raw" or current_path.exists()) else "missing_candidate"
        rows.append(
            {
                "market": market,
                "year": year,
                "action": action,
                "groups": groups,
                "current_path": current_path.as_posix(),
                "candidate_path": candidate_path.as_posix(),
                "status": status,
                **counts,
            }
        )
    return {
        "stage": "raw_alignment_promotion_manifest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "requires_explicit_approval": True,
        "raw_root": raw_root.as_posix(),
        "candidate_2026_root": candidate_2026_root.as_posix(),
        "definition_candidate_root": definition_candidate_root.as_posix(),
        "missing_candidate_root": missing_candidate_root.as_posix(),
        "market_year_count": len(rows),
        "ready_count": sum(1 for row in rows if row["status"] == "ready"),
        "missing_candidate_count": sum(1 for row in rows if row["status"] != "ready"),
        "add_count": sum(1 for row in rows if row["action"] == "add_missing_raw"),
        "replace_count": sum(1 for row in rows if row["action"] != "add_missing_raw"),
        "rows": rows,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {str(report['stage']).replace('_', ' ').title()}", "", f"- Generated: {report['generated_at']}"]
    for key in [
        "status",
        "market_year_count",
        "path_count",
        "diff_count",
        "schema_signature_count",
    ]:
        if key in report:
            lines.append(f"- {key}: {report[key]}")
    if "classifications" in report:
        lines.append(f"- classifications: {report['classifications']}")
    if "field_mismatch_counts" in report:
        lines.append(f"- field_mismatch_counts: {report['field_mismatch_counts']}")
    if "representative_samples" in report:
        samples = report["representative_samples"]
        for name, sample in samples.items():
            if sample:
                lines.append(
                    f"- representative_{name}: {sample.get('market')} {sample.get('year')} "
                    f"{sample.get('classification')}"
                )
    if report.get("rows"):
        lines.extend(["", "## Rows", ""])
        for row in report["rows"][:100]:
            label = f"{row.get('market', '')} {row.get('year', '')}".strip()
            detail = row.get("status") or row.get("classification") or f"paths={len(row.get('paths', []))}"
            lines.append(f"- {label}: {detail}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser("source-paths")
    source.add_argument("--alignment-json", default="reports/raw_ingest/raw_dbn_alignment.json")
    source.add_argument("--dbn-root", default="data/dbn")
    source.add_argument("--year", type=int, default=2026)
    source.add_argument("--json-out", required=True)
    source.add_argument("--md-out")

    definition_paths = subparsers.add_parser("definition-paths")
    definition_paths.add_argument("--alignment-json", default="reports/raw_ingest/raw_dbn_alignment.json")
    definition_paths.add_argument("--dbn-root", default="data/dbn")
    definition_paths.add_argument("--json-out", required=True)
    definition_paths.add_argument("--md-out")

    compare = subparsers.add_parser("compare-candidate")
    compare.add_argument("--alignment-json", default="reports/raw_ingest/raw_dbn_alignment.json")
    compare.add_argument("--base-root", default="data/raw")
    compare.add_argument("--candidate-root", required=True)
    compare.add_argument("--dbn-root", default="data/dbn")
    compare.add_argument("--year", type=int, default=2026)
    compare.add_argument("--key-source", choices=["source_hash", "definition", "missing"], default="source_hash")
    compare.add_argument("--json-out", required=True)
    compare.add_argument("--md-out")

    definition = subparsers.add_parser("definition-drilldown")
    definition.add_argument("--alignment-json", default="reports/raw_ingest/raw_dbn_alignment.json")
    definition.add_argument("--dbn-root", default="data/dbn")
    definition.add_argument("--raw-root", default="data/raw")
    definition.add_argument("--json-out", required=True)
    definition.add_argument("--md-out")

    root_cause = subparsers.add_parser("definition-root-cause")
    root_cause.add_argument("--alignment-json", default="reports/raw_ingest/raw_dbn_alignment.json")
    root_cause.add_argument(
        "--candidate-compare-json",
        default="reports/raw_ingest/raw_alignment_definition_candidate_compare_refresh.json",
    )
    root_cause.add_argument("--dbn-root", default="data/dbn")
    root_cause.add_argument("--raw-root", default="data/raw")
    root_cause.add_argument("--candidate-root", default="data/raw_alignment_candidate_definition_fix")
    root_cause.add_argument("--json-out", required=True)
    root_cause.add_argument("--md-out")

    missing = subparsers.add_parser("missing-paths")
    missing.add_argument("--alignment-json", default="reports/raw_ingest/raw_dbn_alignment.json")
    missing.add_argument("--dbn-root", default="data/dbn")
    missing.add_argument("--raw-root", default="data/raw")
    missing.add_argument("--json-out", required=True)
    missing.add_argument("--md-out")

    promotion = subparsers.add_parser("promotion-manifest")
    promotion.add_argument("--alignment-json", default="reports/raw_ingest/raw_dbn_alignment.json")
    promotion.add_argument("--raw-root", default="data/raw")
    promotion.add_argument("--candidate-2026-root", default="data/raw_alignment_candidate_2026")
    promotion.add_argument("--definition-candidate-root", default="data/raw_alignment_candidate_definition_fix")
    promotion.add_argument("--missing-candidate-root", default="data/raw_alignment_candidate_missing_fill")
    promotion.add_argument("--json-out", required=True)
    promotion.add_argument("--md-out")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    alignment_report = load_report(Path(args.alignment_json))
    if args.command == "source-paths":
        report = build_source_path_report(
            alignment_report=alignment_report,
            dbn_root=Path(args.dbn_root),
            year=int(args.year),
        )
    elif args.command == "definition-paths":
        report = build_definition_path_report(
            alignment_report=alignment_report,
            dbn_root=Path(args.dbn_root),
        )
    elif args.command == "compare-candidate":
        if args.key_source == "definition":
            keys = definition_mismatch_keys(alignment_report)
        elif args.key_source == "missing":
            keys = missing_raw_keys(alignment_report)
        else:
            keys = source_hash_mismatch_keys(alignment_report, year=int(args.year))
        report = compare_candidate_to_raw(
            keys=keys,
            base_root=Path(args.base_root),
            candidate_root=Path(args.candidate_root),
            dbn_root=Path(args.dbn_root),
        )
    elif args.command == "definition-drilldown":
        report = build_definition_drilldown(
            alignment_report=alignment_report,
            dbn_root=Path(args.dbn_root),
            raw_root=Path(args.raw_root),
        )
    elif args.command == "definition-root-cause":
        report = build_definition_root_cause(
            alignment_report=alignment_report,
            candidate_compare_report=load_report(Path(args.candidate_compare_json)),
            dbn_root=Path(args.dbn_root),
            raw_root=Path(args.raw_root),
            candidate_root=Path(args.candidate_root),
        )
    elif args.command == "missing-paths":
        report = build_missing_raw_path_report(
            alignment_report=alignment_report,
            dbn_root=Path(args.dbn_root),
            raw_root=Path(args.raw_root),
        )
    elif args.command == "promotion-manifest":
        report = build_promotion_manifest(
            alignment_report=alignment_report,
            raw_root=Path(args.raw_root),
            candidate_2026_root=Path(args.candidate_2026_root),
            definition_candidate_root=Path(args.definition_candidate_root),
            missing_candidate_root=Path(args.missing_candidate_root),
        )
    else:
        raise SystemExit(f"unsupported command: {args.command}")
    write_json(Path(args.json_out), report)
    if args.md_out:
        write_markdown(Path(args.md_out), report)
    print(
        "stage={stage} status={status} market_years={market_year_count}".format(
            stage=report["stage"],
            status=report.get("status", "OK"),
            market_year_count=report.get("market_year_count", 0),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
