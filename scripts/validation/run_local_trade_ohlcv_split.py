#!/usr/bin/env python3
"""Run bounded local trade/OHLCV gap proof shards."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.validation.audit_local_trade_ohlcv_gaps import (
    DEFAULT_MAX_RUNTIME_SECONDS,
    LOCAL_TRADES_SCHEMA_ACCESS_END,
    LOCAL_TRADES_SCHEMA_ACCESS_START,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_MODULE = "scripts.validation.audit_local_trade_ohlcv_gaps"
DEFAULT_REPORTS_ROOT = Path("reports/pipeline_audit/local_trade_shards_20250618_20260613")
DEFAULT_PROFILES = ("tier_3_holdout", "tier_3_forward")
DEFAULT_WINDOW_DAYS = 7
DEFAULT_MAX_SHARDS = 1
DEFAULT_MAX_GAP_WINDOWS = 10_000
DEFAULT_MAX_TRADE_ROWS_SCANNED = 200_000_000
DEFAULT_MAX_ARCHIVES_READ = 2


RunChild = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class SplitShard:
    index: int
    market: str
    year: int
    start: date
    end: date
    json_out: Path
    md_out: Path
    progress_jsonl: Path

    @property
    def label(self) -> str:
        return f"{self.market}_{self.year}_w{self.index:02d}"

    @property
    def window(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_path(path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError(f"invalid date {value!r}; expected YYYY-MM-DD") from exc


def _access_start() -> date:
    return _parse_date(LOCAL_TRADES_SCHEMA_ACCESS_START)


def _access_end() -> date:
    return _parse_date(LOCAL_TRADES_SCHEMA_ACCESS_END)


def _default_year_window(year: int) -> tuple[date, date]:
    start = max(date(year, 1, 1), _access_start())
    end = min(date(year + 1, 1, 1), _access_end())
    if start >= end:
        raise ValueError(
            f"year {year} is outside local trades access window "
            f"[{_access_start().isoformat()}, {_access_end().isoformat()})"
        )
    return start, end


def _validate_window(start: date, end: date) -> None:
    if start >= end:
        raise ValueError("--start must be before --end")
    if start < _access_start() or end > _access_end():
        raise ValueError(
            "requested split window "
            f"[{start.isoformat()}, {end.isoformat()}) is outside local trades access "
            f"window [{_access_start().isoformat()}, {_access_end().isoformat()})"
        )


def _split_dir(reports_root: Path, market: str, year: int) -> Path:
    return reports_root / f"{market}_{year}_split_v1"


def _shard_stem(shard_index: int, market: str, year: int, start: date, end: date) -> str:
    return f"{market}_{year}_w{shard_index:02d}_{start:%Y%m%d}_{end:%Y%m%d}"


def build_split_shards(
    *,
    market: str,
    year: int,
    reports_root: Path,
    start: str | None = None,
    end: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    shard_index: int | None = None,
) -> list[SplitShard]:
    if window_days < 1:
        raise ValueError("--window-days must be >= 1")
    if shard_index is not None and shard_index < 1:
        raise ValueError("--shard-index must be >= 1")

    default_start, default_end = _default_year_window(year)
    start_date = _parse_date(start) if start else default_start
    end_date = _parse_date(end) if end else default_end
    _validate_window(start_date, end_date)

    split_dir = _split_dir(reports_root, market, year)
    shards: list[SplitShard] = []
    cursor = start_date
    index = 1
    while cursor < end_date:
        shard_end = min(cursor + timedelta(days=window_days), end_date)
        stem = _shard_stem(index, market, year, cursor, shard_end)
        if shard_index is None or index == shard_index:
            shards.append(
                SplitShard(
                    index=index,
                    market=market,
                    year=year,
                    start=cursor,
                    end=shard_end,
                    json_out=split_dir / f"{stem}.json",
                    md_out=split_dir / f"{stem}.md",
                    progress_jsonl=split_dir / f"{stem}.progress.jsonl",
                )
            )
        cursor = shard_end
        index += 1

    if shard_index is not None and not shards:
        raise ValueError(f"--shard-index {shard_index} is outside the selected split window")
    return shards


def _read_json_status(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return "UNREADABLE"
    if not isinstance(payload, dict):
        return "UNREADABLE"
    return str(payload.get("status") or "MISSING_STATUS")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"generated_at_utc": _utc_now(), **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _tail_lines(value: str, count: int = 20) -> list[str]:
    lines = [line for line in value.splitlines() if line.strip()]
    return lines[-count:]


def _optional_flag(command: list[str], flag: str, value: object | None) -> None:
    if value is not None:
        command.extend([flag, str(value)])


def build_audit_command(args: argparse.Namespace, shard: SplitShard) -> list[str]:
    command = [
        sys.executable,
        "-m",
        AUDIT_MODULE,
        "--profile-config",
        str(args.profile_config),
        "--profiles",
        *[str(profile) for profile in args.profiles],
        "--markets",
        str(args.market),
        "--start",
        shard.start.isoformat(),
        "--end",
        shard.end.isoformat(),
        "--dbn-root",
        str(args.dbn_root),
        "--raw-root",
        str(args.raw_root),
        "--causal-root",
        str(args.causal_root),
        "--json-out",
        _relative_path(shard.json_out),
        "--md-out",
        _relative_path(shard.md_out),
        "--progress-jsonl",
        _relative_path(shard.progress_jsonl),
        "--chunk-size",
        str(args.chunk_size),
        "--max-gap-windows",
        str(args.max_gap_windows),
        "--max-trade-rows-scanned",
        str(args.max_trade_rows_scanned),
        "--max-archives-read",
        str(args.max_archives_read),
        "--max-runtime-seconds",
        str(args.max_runtime_seconds),
    ]
    _optional_flag(command, "--raw-overlay-root", args.raw_overlay_root)
    return command


def _child_timeout(args: argparse.Namespace) -> float:
    if args.child_timeout_seconds is not None:
        return float(args.child_timeout_seconds)
    return float(args.max_runtime_seconds) + 60.0


def _shard_record(shard: SplitShard) -> dict[str, Any]:
    return {
        "index": shard.index,
        "label": shard.label,
        "window": shard.window,
        "json_out": _relative_path(shard.json_out),
        "md_out": _relative_path(shard.md_out),
        "progress_jsonl": _relative_path(shard.progress_jsonl),
    }


def run_split(args: argparse.Namespace, *, run_child: RunChild = subprocess.run) -> dict[str, Any]:
    if args.max_shards < 1:
        raise ValueError("--max-shards must be >= 1")

    reports_root = _repo_path(args.reports_root)
    shards = build_split_shards(
        market=str(args.market),
        year=int(args.year),
        reports_root=reports_root,
        start=args.start,
        end=args.end,
        window_days=int(args.window_days),
        shard_index=args.shard_index,
    )
    summary_out = _repo_path(
        args.summary_out
        if args.summary_out
        else _split_dir(reports_root, str(args.market), int(args.year))
        / f"{args.market}_{args.year}_split_runner_summary.json"
    )
    runner_progress = _repo_path(
        args.runner_progress_jsonl
        if args.runner_progress_jsonl
        else _split_dir(reports_root, str(args.market), int(args.year))
        / f"{args.market}_{args.year}_split_runner.progress.jsonl"
    )
    runner_progress.parent.mkdir(parents=True, exist_ok=True)
    runner_progress.write_text("", encoding="utf-8")

    started_at = _utc_now()
    summary: dict[str, Any] = {
        "stage": "local_trade_ohlcv_split_runner",
        "status": "PASS",
        "generated_at_utc": started_at,
        "market": str(args.market),
        "year": int(args.year),
        "dry_run": bool(args.dry_run),
        "rerun_existing": bool(args.rerun_existing),
        "profiles": [str(profile) for profile in args.profiles],
        "causal_root": str(args.causal_root),
        "reports_root": _relative_path(reports_root),
        "summary_out": _relative_path(summary_out),
        "runner_progress_jsonl": _relative_path(runner_progress),
        "command_family": f"{sys.executable} -m {AUDIT_MODULE}",
        "selected_window": {
            "start": shards[0].start.isoformat(),
            "end": shards[-1].end.isoformat(),
            "window_days": int(args.window_days),
        },
        "scan_limits": {
            "max_gap_windows": int(args.max_gap_windows),
            "max_trade_rows_scanned": int(args.max_trade_rows_scanned),
            "max_archives_read": int(args.max_archives_read),
            "max_runtime_seconds": float(args.max_runtime_seconds),
            "child_timeout_seconds": _child_timeout(args),
            "max_shards": int(args.max_shards),
        },
        "planned_shard_count": len(shards),
        "processed_shards": [],
        "skipped_shards": [],
        "failed_shards": [],
        "provider_or_network_call": False,
        "raw_data_mutated": False,
        "generated_reports_mutated": False,
    }
    _append_jsonl(
        runner_progress,
        {
            "event": "runner_started",
            "market": args.market,
            "year": int(args.year),
            "planned_shard_count": len(shards),
            "dry_run": bool(args.dry_run),
        },
    )

    executable_count = 0
    for shard in shards:
        existing_status = _read_json_status(shard.json_out)
        if existing_status == "PASS" and not args.rerun_existing:
            record = {**_shard_record(shard), "status": "SKIPPED_EXISTING_PASS"}
            summary["skipped_shards"].append(record)
            _append_jsonl(runner_progress, {"event": "shard_skipped", **record})
            continue
        if existing_status is not None and not args.rerun_existing:
            record = {
                **_shard_record(shard),
                "status": "FAIL",
                "reason": f"existing non-PASS report status={existing_status}",
            }
            summary["failed_shards"].append(record)
            _append_jsonl(runner_progress, {"event": "shard_blocked_existing_report", **record})
            break
        if executable_count >= int(args.max_shards):
            break

        command = build_audit_command(args, shard)
        record = {**_shard_record(shard), "command": command}
        if args.dry_run:
            summary["processed_shards"].append({**record, "status": "DRY_RUN"})
            _append_jsonl(runner_progress, {"event": "shard_dry_run", **_shard_record(shard)})
            executable_count += 1
            continue

        executable_count += 1
        _append_jsonl(runner_progress, {"event": "shard_started", **_shard_record(shard)})
        try:
            completed = run_child(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                timeout=_child_timeout(args),
            )
        except subprocess.TimeoutExpired as exc:
            failed = {
                **record,
                "status": "FAIL",
                "reason": f"child timeout after {_child_timeout(args)} seconds",
                "stdout_tail": _tail_lines(exc.stdout or ""),
                "stderr_tail": _tail_lines(exc.stderr or ""),
            }
            summary["failed_shards"].append(failed)
            _append_jsonl(runner_progress, {"event": "shard_failed", **failed})
            break

        report_status = _read_json_status(shard.json_out)
        child_record = {
            **record,
            "returncode": int(completed.returncode),
            "report_status": report_status,
            "stdout_tail": _tail_lines(completed.stdout),
            "stderr_tail": _tail_lines(completed.stderr),
        }
        if completed.returncode == 0 and report_status == "PASS":
            passed = {**child_record, "status": "PASS"}
            summary["processed_shards"].append(passed)
            summary["generated_reports_mutated"] = True
            _append_jsonl(runner_progress, {"event": "shard_finished", **passed})
            continue

        failed = {
            **child_record,
            "status": "FAIL",
            "reason": "child failed or did not write a PASS report",
        }
        summary["failed_shards"].append(failed)
        summary["generated_reports_mutated"] = True
        _append_jsonl(runner_progress, {"event": "shard_failed", **failed})
        break

    if args.dry_run:
        summary["status"] = "DRY_RUN"
    elif summary["failed_shards"]:
        summary["status"] = "FAIL"
    else:
        summary["status"] = "PASS"
    summary["completed_at_utc"] = _utc_now()
    _append_jsonl(
        runner_progress,
        {
            "event": "runner_finished",
            "status": summary["status"],
            "processed_shard_count": len(summary["processed_shards"]),
            "skipped_shard_count": len(summary["skipped_shards"]),
            "failed_shard_count": len(summary["failed_shards"]),
        },
    )
    _write_json(summary_out, summary)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", required=True)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--max-shards", type=int, default=DEFAULT_MAX_SHARDS)
    parser.add_argument("--profile-config", default="configs/alpha_tiered.yaml")
    parser.add_argument("--profiles", nargs="+", default=list(DEFAULT_PROFILES))
    parser.add_argument("--dbn-root", default="data/dbn")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--raw-overlay-root")
    parser.add_argument("--causal-root", required=True)
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--summary-out")
    parser.add_argument("--runner-progress-jsonl")
    parser.add_argument("--chunk-size", type=int, default=250_000)
    parser.add_argument("--max-gap-windows", type=int, default=DEFAULT_MAX_GAP_WINDOWS)
    parser.add_argument("--max-trade-rows-scanned", type=int, default=DEFAULT_MAX_TRADE_ROWS_SCANNED)
    parser.add_argument("--max-archives-read", type=int, default=DEFAULT_MAX_ARCHIVES_READ)
    parser.add_argument("--max-runtime-seconds", type=float, default=DEFAULT_MAX_RUNTIME_SECONDS)
    parser.add_argument("--child-timeout-seconds", type=float)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rerun-existing", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        summary = run_split(args)
    except ValueError as exc:
        parser.error(str(exc))
    print(
        "status={status} market={market} year={year} processed={processed} "
        "skipped={skipped} failed={failed} summary={summary}".format(
            status=summary["status"],
            market=summary["market"],
            year=summary["year"],
            processed=len(summary["processed_shards"]),
            skipped=len(summary["skipped_shards"]),
            failed=len(summary["failed_shards"]),
            summary=summary["summary_out"],
        )
    )
    return 0 if summary["status"] in {"PASS", "DRY_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
