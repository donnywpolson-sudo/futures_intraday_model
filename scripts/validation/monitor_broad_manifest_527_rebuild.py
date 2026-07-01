#!/usr/bin/env python3
"""Run the broad manifest rebuild with periodic progress checks."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from scripts.validation import build_broad_manifest_527_rebuild as build_runner


DEFAULT_MONITOR_ROOT = Path(
    "reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1_monitor"
)


def _count_checkpoint_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _line in handle)


def _last_checkpoint_line(path: Path) -> str:
    if not path.exists():
        return ""
    last = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            last = line.rstrip("\n")
    return last


def _parquet_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _path in path.rglob("*.parquet"))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--max-stalled-checks", type=int, default=20)
    parser.add_argument("--monitor-root", default=str(DEFAULT_MONITOR_ROOT))
    parser.add_argument(
        "--build-arg",
        action="append",
        default=[],
        help="Additional argument forwarded to build_broad_manifest_527_rebuild.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    cwd_failure = build_runner._repo_cwd_failure("FAIL monitor")
    if cwd_failure:
        print(cwd_failure, flush=True)
        return 1
    args = build_arg_parser().parse_args(argv)
    if args.interval_seconds < 1:
        print("FAIL monitor: --interval-seconds must be >= 1", flush=True)
        return 1
    if args.max_stalled_checks < 1:
        print("FAIL monitor: --max-stalled-checks must be >= 1", flush=True)
        return 1

    monitor_root = Path(args.monitor_root)
    monitor_root.mkdir(parents=True, exist_ok=True)
    stdout_path = monitor_root / "build_stdout.log"
    stderr_path = monitor_root / "build_stderr.log"
    checkpoint = build_runner.DEFAULT_CHECKPOINT
    output_root = build_runner.DEFAULT_OUTPUT_ROOT

    command = [
        sys.executable,
        "-m",
        "scripts.validation.build_broad_manifest_527_rebuild",
        *args.build_arg,
    ]
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        proc = subprocess.Popen(
            command,
            cwd=build_runner.REPO_ROOT,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
        print(
            "monitor_start "
            f"build_pid={proc.pid} interval_seconds={args.interval_seconds} "
            f"max_stalled_checks={args.max_stalled_checks}",
            flush=True,
        )
        last_lines = -1
        last_parquet = -1
        stalled = 0
        while proc.poll() is None:
            time.sleep(args.interval_seconds)
            lines = _count_checkpoint_lines(checkpoint)
            parquet = _parquet_count(output_root)
            last = _last_checkpoint_line(checkpoint)
            progressed = lines != last_lines or parquet != last_parquet
            stalled = 0 if progressed else stalled + 1
            last_lines = lines
            last_parquet = parquet
            print(
                f"monitor tick={datetime.now().isoformat()} build_pid={proc.pid} "
                f"running=True checkpoint_lines={lines} parquet_count={parquet} "
                f"stalled_checks={stalled} last={last}",
                flush=True,
            )
            if stalled >= args.max_stalled_checks:
                print(
                    f"monitor_stop reason=stalled build_pid={proc.pid} "
                    f"stalled_checks={stalled}",
                    flush=True,
                )
                proc.kill()
                break

        return_code = proc.wait()
    lines = _count_checkpoint_lines(checkpoint)
    parquet = _parquet_count(output_root)
    print(
        f"monitor_end build_pid={proc.pid} exit_code={return_code} "
        f"checkpoint_lines={lines} parquet_count={parquet} "
        f"stdout={stdout_path.as_posix()} stderr={stderr_path.as_posix()}",
        flush=True,
    )
    if stdout_path.exists():
        tail = stdout_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
        for line in tail:
            print(line, flush=True)
    if stderr_path.exists():
        tail = stderr_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        for line in tail:
            print(line, flush=True)
    return int(return_code)


if __name__ == "__main__":
    raise SystemExit(main())
