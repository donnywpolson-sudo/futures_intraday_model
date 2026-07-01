#!/usr/bin/env python3
"""Run the broad manifest rebuild one market-year at a time until completion."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVAL_TOKEN = (
    "APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6M_2012_"
    "ROLL_MATURITY_ONLY_UNDER_VENDOR_OHLCV_POLICY"
)
EXPECTED_MARKET_YEAR_COUNT = 460
INCLUDE = Path(
    "reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628/"
    "broad_manifest_527_rebuild_ready_only_include_460_excluding_6M_2012_vendor_ohlcv_policy.json"
)
CHECKPOINT = Path(
    "reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1/"
    "build_progress.jsonl"
)
PAYLOADS = Path(
    "reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1/"
    "build_result_payloads.jsonl"
)
OUTPUT_ROOT = Path("data/causal_base_candidates/broad_manifest_527_rebuild_v1")
REPORTS_ROOT = Path("reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1")
MANIFEST = REPORTS_ROOT / "causal_base_manifest.json"
DEFAULT_LOG = Path(
    "reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1_monitor/"
    "step_loop.log"
)


def _repo_path(path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _line_count(path: Path) -> int:
    path = _repo_path(path)
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _line in handle)


def _parquet_count(path: Path) -> int:
    path = _repo_path(path)
    if not path.exists():
        return 0
    return sum(1 for _path in path.rglob("*.parquet"))


def _last_line(path: Path) -> str:
    path = _repo_path(path)
    if not path.exists():
        return ""
    last = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            last = line.rstrip("\n")
    return last


def _write(log_path: Path, text: str) -> None:
    path = _repo_path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip("\n") + "\n")
        handle.flush()


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    target = _repo_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _read_payload_rows() -> list[dict[str, Any]]:
    path = _repo_path(PAYLOADS)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def _done_pairs() -> dict[tuple[str, int], dict[str, Any]]:
    done: dict[tuple[str, int], dict[str, Any]] = {}
    for payload in _read_payload_rows():
        done[(str(payload.get("market")), int(payload.get("year")))] = payload
    return done


def _include_rows() -> list[dict[str, Any]]:
    payload = json.loads(_repo_path(INCLUDE).read_text(encoding="utf-8"))
    rows = payload.get("market_years")
    if not isinstance(rows, list) or len(rows) != EXPECTED_MARKET_YEAR_COUNT:
        raise ValueError("include file must contain exactly 460 market_years")
    return rows


def _result_json(market: str, year: int) -> Path:
    return Path(tempfile.gettempdir()) / f"broad_manifest_527_{market}_{year}.json"


def _record_result_json(
    *,
    result_json: Path,
    child_returncode: int | None,
    processed_before_step: int,
) -> tuple[bool, str]:
    if not result_json.exists():
        return False, "result_json_missing"
    payload = json.loads(result_json.read_text(encoding="utf-8"))
    market = str(payload.get("market"))
    year = int(payload.get("year"))
    pair = (market, year)
    if pair in _done_pairs():
        result_json.unlink(missing_ok=True)
        return True, f"already_recorded {market}:{year}"
    failures = payload.get("failures") or []
    warnings = payload.get("warnings") or []
    output_path = _repo_path(str(payload.get("output_path")))
    if failures:
        return False, f"result_has_failures {market}:{year} failure_count={len(failures)}"
    if not output_path.exists():
        return False, f"output_missing {output_path.as_posix()}"
    _append_jsonl(PAYLOADS, payload)
    _append_jsonl(
        CHECKPOINT,
        {
            "stage": "broad_manifest_527_build_market_year",
            "market": market,
            "year": year,
            "status": payload.get("status"),
            "raw_rows": payload.get("raw_rows"),
            "output_rows": payload.get("output_rows"),
            "synthetic_rows": payload.get("synthetic_rows"),
            "warning_count": len(warnings),
            "failure_count": len(failures),
            "input_path": payload.get("input_path"),
            "output_path": payload.get("output_path"),
            "processed_market_year_count": processed_before_step + 1,
            "child_returncode": child_returncode,
        },
    )
    result_json.unlink(missing_ok=True)
    return True, f"recorded {market}:{year}"


def _write_checker(log_path: Path, returncode: int | None) -> None:
    _write(
        log_path,
        "checker "
        f"at={datetime.now().isoformat()} rc={returncode} "
        f"payload_count={_line_count(PAYLOADS)} "
        f"parquet_count={_parquet_count(OUTPUT_ROOT)} "
        f"last={_last_line(CHECKPOINT)}",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broad-build-approval-token", required=True)
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--log-file", default=str(DEFAULT_LOG))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if Path.cwd().resolve() != REPO_ROOT.resolve():
        print(
            f"FAIL step_loop: must run from repo root {REPO_ROOT}; "
            f"current cwd is {Path.cwd().resolve()}",
            flush=True,
        )
        return 1
    if args.broad_build_approval_token != APPROVAL_TOKEN:
        print("FAIL step_loop: missing or incorrect broad build approval token", flush=True)
        return 1
    if args.interval_seconds < 1:
        print("FAIL step_loop: --interval-seconds must be >= 1", flush=True)
        return 1

    log_path = Path(args.log_file)
    last_tick = 0.0
    _write(
        log_path,
        f"step_loop_start at={datetime.now().isoformat()} interval_seconds={args.interval_seconds}",
    )
    while True:
        done = _done_pairs()
        include_rows = _include_rows()
        if len(done) > EXPECTED_MARKET_YEAR_COUNT:
            _write(log_path, "step_loop_end status=FAIL reason=too_many_payloads")
            return 1
        if len(done) == EXPECTED_MARKET_YEAR_COUNT:
            command = [
                sys.executable,
                "-m",
                "scripts.validation.build_broad_manifest_527_rebuild",
                "--one-market-year-per-invocation",
                "--resume-existing-partial",
                "--broad-build-approval-token",
                args.broad_build_approval_token,
            ]
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )
            if completed.stdout:
                _write(log_path, completed.stdout)
            if completed.stderr:
                _write(log_path, completed.stderr)
            _write_checker(log_path, completed.returncode)
            if completed.returncode != 0:
                _write(log_path, f"step_loop_end status=FAIL rc={completed.returncode}")
                return int(completed.returncode)
            if _repo_path(MANIFEST).exists():
                _write(log_path, "step_loop_end status=PASS")
                return 0
            time.sleep(5)
            continue

        next_row = None
        for row in include_rows:
            pair = (str(row.get("market")), int(row.get("year")))
            if pair not in done:
                next_row = row
                break
        if next_row is None:
            _write(log_path, "step_loop_end status=FAIL reason=payload_include_mismatch")
            return 1

        market = str(next_row["market"])
        year = int(next_row["year"])
        input_path = Path("data/raw") / market / f"{year}.parquet"
        output_path = OUTPUT_ROOT / market / f"{year}.parquet"
        result_json = _result_json(market, year)

        recovered, reason = _record_result_json(
            result_json=result_json,
            child_returncode=None,
            processed_before_step=len(done),
        )
        if recovered:
            _write(log_path, f"salvaged_existing_result {reason}")
            _write_checker(log_path, 0)
            continue

        _append_jsonl(
            CHECKPOINT,
            {
                "stage": "broad_manifest_527_build_market_year_start",
                "market": market,
                "year": year,
                "input_path": input_path.as_posix(),
                "output_path": output_path.as_posix(),
                "started_at_utc": _utc_now(),
                "step_mode": True,
                "python_direct_single": True,
                "processed_before_step": len(done),
            },
        )
        command = [
            sys.executable,
            "-X",
            "faulthandler",
            "-m",
            "scripts.validation.build_broad_manifest_527_rebuild",
            "--single-input-path",
            input_path.as_posix(),
            "--single-output-path",
            output_path.as_posix(),
            "--single-result-json",
            result_json.as_posix(),
            "--profile",
            "all_raw",
            "--profile-config",
            "configs/alpha_tiered.yaml",
            "--session-config",
            "configs/market_sessions.yaml",
            "--broad-build-approval-token",
            args.broad_build_approval_token,
        ]
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        if completed.stdout:
            _write(log_path, completed.stdout)
        if completed.stderr:
            _write(log_path, completed.stderr)

        recorded, reason = _record_result_json(
            result_json=result_json,
            child_returncode=completed.returncode,
            processed_before_step=len(done),
        )
        returncode = 0 if recorded else completed.returncode
        now = time.time()
        if (
            now - last_tick >= args.interval_seconds
            or returncode != 0
            or _repo_path(MANIFEST).exists()
        ):
            last_tick = now
            _write_checker(log_path, returncode)
        if recorded:
            if completed.returncode != 0:
                _write(
                    log_path,
                    "completed_result_with_nonzero_child_rc "
                    f"rc={completed.returncode} {reason}",
                )
            continue
        if completed.returncode != 0 and reason == "result_json_missing":
            _write(
                log_path,
                f"transient_retry at={datetime.now().isoformat()} "
                f"rc={completed.returncode} pair={market}:{year} result_json_missing=true",
            )
            time.sleep(5)
            continue
        _write(
            log_path,
            f"step_loop_end status=FAIL rc={completed.returncode} pair={market}:{year} reason={reason}",
        )
        return int(completed.returncode or 1)


if __name__ == "__main__":
    raise SystemExit(main())
