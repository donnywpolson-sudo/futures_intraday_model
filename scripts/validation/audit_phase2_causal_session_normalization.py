#!/usr/bin/env python3
"""Read-only hostile audit for Phase 2 causal session-normalized parquet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from scripts.phase2_causal_base.build_causal_base_data import (
    BAR_AVAILABLE_LAG,
    NORMALIZATION_RULE_VERSION,
    OUTPUT_COLUMNS,
    _add_session_edge_flags,
    _session_metadata,
    causal_gate_contract_failures,
    infer_market_year,
    load_session_calendar,
    relative_source_path,
    sha256_file,
)


FORBIDDEN_COLUMN_PREFIXES = (
    "target_",
    "future_",
    "prediction_",
    "pred_",
    "oos_",
    "execution_outcome",
    "realized_",
    "pnl_",
)
PHASE3_HORIZON_OFFSETS = (31, 61)


def _resolve_path(repo_root: Path, raw_path: object) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    return repo_root / path


def _utc_ts(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def _raw_timestamps(raw: pd.DataFrame) -> pd.Series:
    if "ts_event" in raw.columns:
        return _utc_ts(raw["ts_event"])
    if isinstance(raw.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(raw.index, utc=True, errors="coerce"), index=raw.index)
    return pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns, UTC]")


def _discover_causal_files(causal_root: Path) -> list[Path]:
    if causal_root.is_file():
        return [causal_root]
    if not causal_root.exists():
        raise FileNotFoundError(f"causal root missing: {causal_root}")
    return sorted(
        path
        for path in causal_root.glob("*/*.parquet")
        if path.parent.name and path.stem.isdigit()
    )


def _filter_files(
    paths: Iterable[Path],
    *,
    markets: Iterable[str] | None,
    years: Iterable[int] | None,
    max_files: int | None,
) -> list[Path]:
    market_filter = {str(market) for market in markets or []}
    year_filter = {int(year) for year in years or []}
    selected: list[Path] = []
    for path in paths:
        market, year = infer_market_year(path)
        if market_filter and market not in market_filter:
            continue
        if year_filter and int(year) not in year_filter:
            continue
        selected.append(path)
    if max_files is not None:
        selected = selected[:max_files]
    return selected


def _compare_series(
    left: pd.Series,
    right: pd.Series,
    *,
    fill: object = pd.NA,
) -> int:
    left_cmp = left.fillna(fill).astype("string")
    right_cmp = right.fillna(fill).astype("string")
    return int(left_cmp.ne(right_cmp).sum())


def _session_failures(frame: pd.DataFrame, market: str, session_config: Path) -> list[str]:
    failures: list[str] = []
    calendar = load_session_calendar(market, session_config, allow_hardcoded_calendar=False)
    expected = _session_metadata(_utc_ts(frame["ts"]), calendar)
    expected = pd.concat(
        [
            frame[["ts"]].reset_index(drop=True),
            expected,
            frame[["session_segment_id"]].reset_index(drop=True),
        ],
        axis=1,
    )
    expected = _add_session_edge_flags(expected)

    for column in ("inside_session", "session_id", "session_date"):
        observed = frame[column].reset_index(drop=True)
        mismatch_count = _compare_series(observed, expected[column])
        if mismatch_count:
            failures.append(f"session metadata drift {column}: rows={mismatch_count}")

    for column in ("is_session_open", "is_session_close"):
        observed = frame[column].fillna(False).astype(bool).reset_index(drop=True)
        expected_bool = expected[column].fillna(False).astype(bool).reset_index(drop=True)
        mismatch_count = int(observed.ne(expected_bool).sum())
        if mismatch_count:
            failures.append(f"session edge drift {column}: rows={mismatch_count}")

    hardcoded = frame["session_calendar_status"].fillna("").astype(str).str.startswith("hardcoded")
    if bool(hardcoded.any()):
        failures.append(f"hardcoded session calendar status: rows={int(hardcoded.sum())}")
    return failures


def _readiness_failures(frame: pd.DataFrame) -> list[str]:
    failures = causal_gate_contract_failures(frame)
    causal_valid = frame["causal_valid"].fillna(False).astype(bool)
    phase2_ready = frame["phase2_ready"].fillna(False).astype(bool)
    ready_mismatch = phase2_ready.ne(causal_valid)
    if bool(ready_mismatch.any()):
        failures.append(f"phase2_ready mismatch: rows={int(ready_mismatch.sum())}")

    invalid_reason = frame["causal_invalid_reason"].fillna("").astype(str)
    not_ready_reason = frame["phase2_not_ready_reason"].fillna("").astype(str)
    reason_mismatch = not_ready_reason.ne(invalid_reason)
    if bool(reason_mismatch.any()):
        failures.append(
            f"phase2_not_ready_reason mismatch: rows={int(reason_mismatch.sum())}"
        )

    ts = _utc_ts(frame["ts"])
    available = _utc_ts(frame["bar_available_ts"])
    invalid_available = available.isna() | ts.isna() | available.le(ts)
    if bool(invalid_available.any()):
        failures.append(
            "bar_available_ts not strictly after ts: "
            f"rows={int(invalid_available.sum())}"
        )
    wrong_lag = available.ne(ts + BAR_AVAILABLE_LAG).fillna(True)
    if bool(wrong_lag.any()):
        failures.append(f"bar_available_ts lag drift: rows={int(wrong_lag.sum())}")

    version = frame["normalization_rule_version"].fillna("").astype(str)
    wrong_version = version.ne(NORMALIZATION_RULE_VERSION)
    if bool(wrong_version.any()):
        failures.append(
            f"normalization_rule_version drift: rows={int(wrong_version.sum())}"
        )
    return failures


def _synthetic_failures(frame: pd.DataFrame) -> list[str]:
    failures: list[str] = []
    synthetic = frame["is_synthetic"].fillna(False).astype(bool)
    if not bool(synthetic.any()):
        return failures
    synth = frame.loc[synthetic]
    if bool(synth["raw_row_present"].fillna(True).astype(bool).any()):
        failures.append("synthetic rows counted as raw_row_present")
    if bool(synth["phase2_ready"].fillna(True).astype(bool).any()):
        failures.append("synthetic rows marked phase2_ready")
    for column in ("open", "high", "low", "close", "volume"):
        present = pd.to_numeric(synth[column], errors="coerce").notna()
        if bool(present.any()):
            failures.append(f"synthetic rows carry {column} values: rows={int(present.sum())}")
    source_rows = pd.to_numeric(synth["source_row_number"], errors="coerce").notna()
    if bool(source_rows.any()):
        failures.append(
            f"synthetic rows have source_row_number: rows={int(source_rows.sum())}"
        )
    return failures


def _lineage_failures(
    frame: pd.DataFrame,
    *,
    raw_root: Path,
    repo_root: Path,
    market: str,
    year: int,
) -> list[str]:
    failures: list[str] = []
    raw_path = raw_root / market / f"{year}.parquet"
    if not raw_path.exists():
        failures.append(f"raw parquet missing: {relative_source_path(raw_path)}")
        return failures
    raw_hash = sha256_file(raw_path)
    raw = pd.read_parquet(raw_path)
    raw_ts = _raw_timestamps(raw)
    raw = raw.reset_index(drop=True).copy()
    raw["ts"] = raw_ts.reset_index(drop=True)

    raw_present = frame["raw_row_present"].fillna(False).astype(bool)
    raw_rows = frame.loc[raw_present].copy()
    expected_in_year = raw["ts"].ge(pd.Timestamp(f"{year}-01-01", tz="UTC")) & raw[
        "ts"
    ].lt(pd.Timestamp(f"{year + 1}-01-01", tz="UTC"))
    if int(raw_present.sum()) != int(expected_in_year.sum()):
        failures.append(
            "raw-present row count does not match raw in-year rows: "
            f"causal={int(raw_present.sum())} raw={int(expected_in_year.sum())}"
        )

    paths = raw_rows["source_path"].fillna("").astype(str)
    resolved_paths = {_resolve_path(repo_root, path).resolve() for path in set(paths) if path}
    if resolved_paths != {raw_path.resolve()}:
        failures.append(
            "source_path does not resolve to expected raw parquet: "
            f"observed={sorted(str(path) for path in resolved_paths)}"
        )
    hashes = set(raw_rows["source_file_hash"].dropna().astype(str))
    if hashes != {raw_hash}:
        failures.append("source_file_hash does not match raw parquet hash")

    source_row_numbers = pd.to_numeric(raw_rows["source_row_number"], errors="coerce")
    out_of_range = source_row_numbers.isna() | source_row_numbers.lt(0) | source_row_numbers.ge(len(raw))
    if bool(out_of_range.any()):
        failures.append(f"source_row_number out of range: rows={int(out_of_range.sum())}")
        return failures

    for idx, causal_row in raw_rows.iterrows():
        raw_row = raw.iloc[int(causal_row["source_row_number"])]
        if pd.Timestamp(causal_row["ts"]) != pd.Timestamp(raw_row["ts"]):
            failures.append(f"raw lineage timestamp mismatch at output row {idx}")
            break
        for column in ("open", "high", "low", "close", "volume"):
            left = pd.to_numeric(pd.Series([causal_row[column]]), errors="coerce").iloc[0]
            right = pd.to_numeric(pd.Series([raw_row[column]]), errors="coerce").iloc[0]
            if pd.isna(left) and pd.isna(right):
                continue
            if left != right:
                failures.append(
                    f"raw lineage {column} mismatch at output row {idx}"
                )
                return failures
    return failures


def _horizon_overlap_failures(frame: pd.DataFrame) -> list[str]:
    failures: list[str] = []
    if "target_valid" not in frame.columns:
        return failures
    ready = frame["phase2_ready"].fillna(False).astype(bool)
    target_valid = frame["target_valid"].fillna(False).astype(bool)
    for offset in PHASE3_HORIZON_OFFSETS:
        not_ready_path = pd.Series(False, index=frame.index)
        for step in range(0, offset + 1):
            not_ready_path |= ~ready.shift(-step, fill_value=True)
        bad = target_valid & not_ready_path
        if bool(bad.any()):
            failures.append(
                f"target_valid crosses phase2_not_ready path offset={offset}: "
                f"rows={int(bad.sum())}"
            )
    return failures


def audit_file(
    path: Path,
    *,
    raw_root: Path,
    session_config: Path,
    repo_root: Path,
) -> dict[str, Any]:
    market, year = infer_market_year(path)
    failures: list[str] = []
    frame = pd.read_parquet(path)
    missing = [column for column in OUTPUT_COLUMNS if column not in frame.columns]
    if missing:
        failures.append("missing Phase 2 output columns: " + ", ".join(missing))
        return {
            "market": market,
            "year": year,
            "path": relative_source_path(path),
            "status": "FAIL",
            "row_count": len(frame),
            "failure_count": len(failures),
            "failures": failures,
        }

    forbidden = [
        column
        for column in frame.columns
        if any(str(column).startswith(prefix) for prefix in FORBIDDEN_COLUMN_PREFIXES)
    ]
    if forbidden:
        failures.append("forbidden leakage columns present: " + ", ".join(sorted(forbidden)))

    failures.extend(_readiness_failures(frame))
    failures.extend(_synthetic_failures(frame))
    failures.extend(_session_failures(frame, market, session_config))
    failures.extend(
        _lineage_failures(
            frame,
            raw_root=raw_root,
            repo_root=repo_root,
            market=market,
            year=year,
        )
    )
    failures.extend(_horizon_overlap_failures(frame))
    return {
        "market": market,
        "year": year,
        "path": relative_source_path(path),
        "status": "FAIL" if failures else "PASS",
        "row_count": len(frame),
        "phase2_ready_rows": int(frame["phase2_ready"].fillna(False).astype(bool).sum()),
        "synthetic_rows": int(frame["is_synthetic"].fillna(False).astype(bool).sum()),
        "failure_count": len(failures),
        "failures": failures,
    }


def build_report(
    *,
    causal_root: Path,
    raw_root: Path,
    session_config: Path,
    markets: Iterable[str] | None = None,
    years: Iterable[int] | None = None,
    max_files: int | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root or Path.cwd()
    files = _filter_files(
        _discover_causal_files(causal_root),
        markets=markets,
        years=years,
        max_files=max_files,
    )
    rows = [
        audit_file(
            path,
            raw_root=raw_root,
            session_config=session_config,
            repo_root=repo_root,
        )
        for path in files
    ]
    failures = [row for row in rows if row["status"] != "PASS"]
    return {
        "stage": "phase2_causal_session_normalization_audit",
        "status": "FAIL" if failures else "PASS",
        "causal_root": relative_source_path(causal_root),
        "raw_root": relative_source_path(raw_root),
        "session_config": relative_source_path(session_config),
        "normalization_rule_version": NORMALIZATION_RULE_VERSION,
        "file_count": len(rows),
        "pass_count": sum(row["status"] == "PASS" for row in rows),
        "fail_count": len(failures),
        "failure_count": sum(int(row["failure_count"]) for row in rows),
        "files": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 2 Causal Session-Normalization Audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Files checked: `{report['file_count']}`",
        f"- Failures: `{report['failure_count']}`",
        f"- Normalization rule version: `{report['normalization_rule_version']}`",
        "",
        "## Files",
    ]
    for row in report["files"]:
        lines.append(
            f"- `{row['market']} {row['year']}`: `{row['status']}`, "
            f"failures=`{row['failure_count']}`, path=`{row['path']}`"
        )
        for failure in row["failures"]:
            lines.append(f"  - {failure}")
    lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--causal-root", default="data/causally_gated_normalized")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--session-config", default="configs/market_sessions.yaml")
    parser.add_argument("--markets", nargs="+")
    parser.add_argument("--years", nargs="+", type=int)
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    report = build_report(
        causal_root=Path(args.causal_root),
        raw_root=Path(args.raw_root),
        session_config=Path(args.session_config),
        markets=args.markets,
        years=args.years,
        max_files=args.max_files,
    )
    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.md_out:
        md_path = Path(args.md_out)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
