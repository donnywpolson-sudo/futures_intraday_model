#!/usr/bin/env python3
"""Report-only diagnosis for a single roll-maturity readiness blocker."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.phase2_causal_base.build_causal_base_data import (
    _roll_maturity_backsteps,
    _vendor_continuous_roll_backstep_identity_evidence,
)


ALLOWED_DISPOSITION_TOKENS = [
    "KEEP_6M_2012_FAIL_CLOSED_NO_BUILD",
    "APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY",
    "APPROVE_6M_2012_ACCEPTED_ROLL_MATURITY_EXCEPTION_FOR_BROAD_PREFLIGHT_ONLY",
    "APPROVE_6M_2012_LOCAL_ROLL_MATURITY_CODE_REPAIR_ONLY",
    "APPROVE_6M_2012_RAW_REBUILD_AFTER_LOCAL_ROLL_METADATA_CODE_REPAIR_ONLY",
]

TIMESTAMP_COLUMNS = ("ts", "ts_event", "datetime_utc", "datetime", "timestamp", "time")
ROLL_COLUMNS = {"ts", "instrument_id", "raw_symbol", "maturity_year", "maturity_month"}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bool_sum(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return int(series.fillna(False).astype(bool).sum())
    if pd.api.types.is_numeric_dtype(series):
        return int(pd.to_numeric(series, errors="coerce").fillna(0).ne(0).sum())
    return int(series.fillna(False).astype(str).str.lower().isin({"1", "true", "yes", "y"}).sum())


def _unique_values(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    return sorted(str(value) for value in frame[column].dropna().astype(str).unique())


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_blocker(readiness: dict[str, Any], market: str, year: int) -> dict[str, Any]:
    for blocker in readiness.get("blockers") or []:
        if str(blocker.get("market")) == market and int(blocker.get("year") or 0) == year:
            return blocker
    return {}


def _normalize_for_roll(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    if "ts" not in frame.columns:
        for column in TIMESTAMP_COLUMNS:
            if column in frame.columns:
                frame["ts"] = pd.to_datetime(frame[column], utc=True, errors="coerce")
                break
    return frame


def _disposition_call(
    *,
    raw_readable: bool,
    missing_columns: list[str],
    computed_count: int,
    readiness_count: int,
    computed_available: bool,
    vendor_identity_status: str | None = None,
) -> str:
    if not raw_readable:
        return "unreadable_raw_or_readiness_evidence"
    if missing_columns:
        return "missing_roll_metadata_columns"
    if not computed_available or computed_count != readiness_count:
        return "readiness_logic_disagrees_with_raw"
    if vendor_identity_status == "PASS":
        return "vendor_continuous_roll_backstep_policy_mismatch"
    return "roll_maturity_backstep_confirmed_in_raw"


def build_report(
    *,
    market: str,
    year: int,
    raw_root: Path,
    readiness_json: Path,
) -> dict[str, Any]:
    raw_path = raw_root / market / f"{year}.parquet"
    failures: list[str] = []
    raw_readable = False
    raw_frame = pd.DataFrame()
    readiness: dict[str, Any] = {}
    blocker: dict[str, Any] = {}

    if not raw_path.exists():
        failures.append(f"missing raw parquet: {_relative_path(raw_path)}")
    if not readiness_json.exists():
        failures.append(f"missing readiness JSON: {_relative_path(readiness_json)}")

    if not failures:
        try:
            raw_frame = pd.read_parquet(raw_path)
            readiness = _read_json(readiness_json)
            blocker = _find_blocker(readiness, market, year)
            if not blocker:
                failures.append(f"missing readiness blocker for {market}:{year}")
            raw_readable = not failures
        except Exception as exc:  # pragma: no cover - defensive report-only boundary.
            failures.append(f"unreadable raw or readiness evidence: {type(exc).__name__}: {exc}")

    normalized = _normalize_for_roll(raw_frame) if raw_readable else raw_frame
    missing_columns = sorted(ROLL_COLUMNS - set(normalized.columns)) if raw_readable else []
    computed_available = False
    computed_count = 0
    computed_examples: list[dict[str, Any]] = []
    if raw_readable and not missing_columns:
        computed_available, computed_count, computed_examples = _roll_maturity_backsteps(normalized)

    readiness_count = int(blocker.get("roll_maturity_backstep_count") or 0)
    vendor_identity_evidence: dict[str, Any] = {}
    if raw_readable and not missing_columns and computed_available and computed_count == readiness_count:
        vendor_identity_evidence = _vendor_continuous_roll_backstep_identity_evidence(
            normalized,
            raw_path,
            market=market,
            year=year,
            backstep_count=computed_count,
        )
    call = _disposition_call(
        raw_readable=raw_readable,
        missing_columns=missing_columns,
        computed_count=computed_count,
        readiness_count=readiness_count,
        computed_available=computed_available,
        vendor_identity_status=str(vendor_identity_evidence.get("status") or ""),
    )

    status = (
        "PASS"
        if call
        in {
            "roll_maturity_backstep_confirmed_in_raw",
            "vendor_continuous_roll_backstep_policy_mismatch",
        }
        else "FAIL"
    )
    return {
        "stage": "roll_maturity_blocker_diagnosis",
        "status": status,
        "policy": "REPORT_ONLY_NO_PROVIDER_NO_DATA_MUTATION",
        "generated_at_utc": _utc_now(),
        "market": market,
        "year": year,
        "raw_path": _relative_path(raw_path),
        "raw_row_count": int(len(raw_frame)) if raw_readable else 0,
        "raw_sha256": _sha256(raw_path) if raw_readable else None,
        "readiness_json": _relative_path(readiness_json),
        "readiness_status": readiness.get("status"),
        "readiness_top_blocker_reason": blocker.get("top_blocker_reason"),
        "readiness_warnings": list(blocker.get("warnings") or []),
        "readiness_roll_examples": list(blocker.get("roll_maturity_backstep_examples") or []),
        "readiness_roll_maturity_backstep_count": readiness_count,
        "computed_roll_sequence_available": computed_available,
        "computed_backstep_count": computed_count,
        "computed_backstep_examples": computed_examples,
        "computed_matches_readiness": computed_count == readiness_count and computed_available,
        "vendor_continuous_identity_evidence": vendor_identity_evidence,
        "missing_roll_metadata_columns": missing_columns,
        "source_files": _unique_values(raw_frame, "source_file") if raw_readable else [],
        "status_missing_rows": _bool_sum(raw_frame, "status_missing") if raw_readable else 0,
        "statistics_missing_rows": _bool_sum(raw_frame, "statistics_missing") if raw_readable else 0,
        "disposition_call": call,
        "allowed_disposition_tokens": ALLOWED_DISPOSITION_TOKENS,
        "selected_disposition": "NONE_SELECTED",
        "forbidden_actions_performed": {
            "provider_or_network_call": False,
            "data_mutation": False,
            "config_mutation": False,
            "broad_build": False,
        },
        "failures": failures,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Roll Maturity Blocker Diagnosis",
        "",
        f"- Status: `{report['status']}`.",
        f"- Market/year: `{report['market']}:{report['year']}`.",
        f"- Disposition call: `{report['disposition_call']}`.",
        f"- Readiness reason: `{report.get('readiness_top_blocker_reason')}`.",
        f"- Computed backsteps: `{report.get('computed_backstep_count')}`.",
        f"- Readiness backsteps: `{report.get('readiness_roll_maturity_backstep_count')}`.",
        f"- Computed matches readiness: `{str(report.get('computed_matches_readiness')).lower()}`.",
        f"- Vendor continuous identity: `{report.get('vendor_continuous_identity_evidence', {}).get('status', 'NOT_RUN')}`.",
        f"- Raw rows: `{report.get('raw_row_count')}`.",
        f"- Status missing rows: `{report.get('status_missing_rows')}`.",
        f"- Statistics missing rows: `{report.get('statistics_missing_rows')}`.",
        "",
        "## Safety",
        "",
        "- Provider/network call: `false`.",
        "- Data mutation: `false`.",
        "- Config mutation: `false`.",
        "- Broad build: `false`.",
        "",
    ]
    return "\n".join(lines)


def _validate_selected_disposition(selected_disposition: str) -> str:
    if selected_disposition == "NONE_SELECTED":
        return selected_disposition
    if selected_disposition not in ALLOWED_DISPOSITION_TOKENS:
        raise ValueError(f"unsupported selected disposition: {selected_disposition}")
    return selected_disposition


def build_disposition_request(
    report: dict[str, Any],
    *,
    diagnosis_path: Path,
    selected_disposition: str = "NONE_SELECTED",
) -> dict[str, Any]:
    selected = _validate_selected_disposition(selected_disposition)
    is_fail_closed_resolution = selected == "KEEP_6M_2012_FAIL_CLOSED_NO_BUILD"
    return {
        "stage": "broad_manifest_527_rebuild_6M_2012_roll_maturity_disposition_request",
        "status": (
            "RESOLVED_6M_2012_FAIL_CLOSED_NO_BUILD"
            if is_fail_closed_resolution
            else "AWAITING_HUMAN_6M_2012_DISPOSITION"
        ),
        "generated_at_utc": _utc_now(),
        "market": report["market"],
        "year": report["year"],
        "blocked_pair": f"{report['market']}:{report['year']}",
        "selected_disposition": selected,
        "allowed_disposition_tokens": ALLOWED_DISPOSITION_TOKENS,
        "recommended_default": (
            selected
            if is_fail_closed_resolution
            else "KEEP_6M_2012_FAIL_CLOSED_NO_BUILD"
            if report.get("disposition_call") != "roll_maturity_backstep_confirmed_in_raw"
            else "APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_420_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY"
        ),
        "diagnosis": _relative_path(diagnosis_path),
        "diagnosis_status": report.get("status"),
        "diagnosis_disposition_call": report.get("disposition_call"),
        "readiness_top_blocker_reason": report.get("readiness_top_blocker_reason"),
        "computed_backstep_count": report.get("computed_backstep_count"),
        "computed_backstep_examples": report.get("computed_backstep_examples"),
        "build_execution_allowed_now": False,
        "broader_modeling_approved": False,
        "config_promotion_approved": False,
        "research_use_allowed": False,
        "forbidden_actions_performed": report["forbidden_actions_performed"],
    }


def render_disposition_request_markdown(request: dict[str, Any]) -> str:
    lines = [
        "# 6M:2012 Roll Maturity Disposition Request",
        "",
        f"- Status: `{request['status']}`.",
        f"- Selected disposition: `{request['selected_disposition']}`.",
        f"- Recommended default: `{request['recommended_default']}`.",
        f"- Diagnosis: `{request['diagnosis']}`.",
        f"- Diagnosis call: `{request['diagnosis_disposition_call']}`.",
        f"- Build execution allowed now: `{str(request['build_execution_allowed_now']).lower()}`.",
        "",
        "## Allowed exact disposition tokens",
        "",
        *[f"- `{token}`" for token in request["allowed_disposition_tokens"]],
        "",
        "## Safety flags",
        "",
        f"- broader_modeling_approved=`{str(request['broader_modeling_approved']).lower()}`",
        f"- config_promotion_approved=`{str(request['config_promotion_approved']).lower()}`",
        f"- research_use_allowed=`{str(request['research_use_allowed']).lower()}`",
        "",
    ]
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", default="6M")
    parser.add_argument("--year", type=int, default=2012)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--readiness-json", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out")
    parser.add_argument("--disposition-request-json-out")
    parser.add_argument("--disposition-request-md-out")
    parser.add_argument("--selected-disposition", default="NONE_SELECTED")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    json_out = Path(args.json_out)
    report = build_report(
        market=args.market,
        year=args.year,
        raw_root=Path(args.raw_root),
        readiness_json=Path(args.readiness_json),
    )
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_out:
        md_out = Path(args.md_out)
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_markdown(report), encoding="utf-8")

    if args.disposition_request_json_out:
        try:
            request = build_disposition_request(
                report,
                diagnosis_path=json_out,
                selected_disposition=args.selected_disposition,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        request_json = Path(args.disposition_request_json_out)
        request_json.parent.mkdir(parents=True, exist_ok=True)
        request_json.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.disposition_request_md_out:
            request_md = Path(args.disposition_request_md_out)
            request_md.parent.mkdir(parents=True, exist_ok=True)
            request_md.write_text(render_disposition_request_markdown(request), encoding="utf-8")

    print(
        json.dumps(
            {
                "stage": report["stage"],
                "status": report["status"],
                "disposition_call": report["disposition_call"],
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
