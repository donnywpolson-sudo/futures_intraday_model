from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.validation import run_local_trade_ohlcv_split as runner


def _args(tmp_path: Path, *extra: str) -> object:
    parser = runner.build_arg_parser()
    return parser.parse_args(
        [
            "--market",
            "HO",
            "--year",
            "2026",
            "--causal-root",
            str(tmp_path / "data" / "causal_proof_candidates" / "local_trade_2025_2026_v1"),
            "--reports-root",
            str(tmp_path / "reports" / "pipeline_audit" / "local_trade_shards"),
            *extra,
        ]
    )


def _write_report(path: Path, status: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": status}) + "\n", encoding="utf-8")


def test_year_windows_are_clipped_to_local_trade_access(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"

    shards_2025 = runner.build_split_shards(market="HO", year=2025, reports_root=reports_root)
    shards_2026 = runner.build_split_shards(market="HO", year=2026, reports_root=reports_root)

    assert shards_2025[0].window == {"start": "2025-06-18", "end": "2025-06-25"}
    assert shards_2025[-1].end.isoformat() == "2026-01-01"
    assert shards_2026[0].window == {"start": "2026-01-01", "end": "2026-01-08"}
    assert shards_2026[-1].end.isoformat() == "2026-06-13"


def test_shard_index_selects_exact_week_and_expected_paths(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"

    shard = runner.build_split_shards(
        market="HO",
        year=2026,
        reports_root=reports_root,
        shard_index=4,
    )[0]

    assert shard.label == "HO_2026_w04"
    assert shard.window == {"start": "2026-01-22", "end": "2026-01-29"}
    assert shard.json_out == reports_root / "HO_2026_split_v1" / "HO_2026_w04_20260122_20260129.json"
    assert shard.md_out.name == "HO_2026_w04_20260122_20260129.md"
    assert shard.progress_jsonl.name == "HO_2026_w04_20260122_20260129.progress.jsonl"


def test_audit_command_carries_scope_paths_and_budgets(tmp_path: Path) -> None:
    args = _args(tmp_path, "--shard-index", "4")
    shard = runner.build_split_shards(
        market="HO",
        year=2026,
        reports_root=Path(args.reports_root),
        shard_index=4,
    )[0]

    command = runner.build_audit_command(args, shard)

    assert command[:3] == [runner.sys.executable, "-m", runner.AUDIT_MODULE]
    assert command[command.index("--markets") + 1] == "HO"
    assert command[command.index("--start") + 1] == "2026-01-22"
    assert command[command.index("--end") + 1] == "2026-01-29"
    assert command[command.index("--causal-root") + 1] == str(args.causal_root)
    assert command[command.index("--max-gap-windows") + 1] == "10000"
    assert command[command.index("--max-trade-rows-scanned") + 1] == "200000000"
    assert command[command.index("--max-archives-read") + 1] == "2"
    assert command[command.index("--max-runtime-seconds") + 1] == "900.0"


def test_dry_run_writes_summary_without_calling_child(tmp_path: Path) -> None:
    args = _args(tmp_path, "--shard-index", "4", "--dry-run")

    def fail_child(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("child should not run")

    summary = runner.run_split(args, run_child=fail_child)
    summary_path = Path(summary["summary_out"])
    progress_path = Path(summary["runner_progress_jsonl"])
    events = [json.loads(line)["event"] for line in progress_path.read_text(encoding="utf-8").splitlines()]

    assert summary["status"] == "DRY_RUN"
    assert summary["processed_shards"][0]["label"] == "HO_2026_w04"
    assert summary_path.exists()
    assert events == ["runner_started", "shard_dry_run", "runner_finished"]


def test_existing_pass_report_is_skipped_and_next_shard_runs(tmp_path: Path) -> None:
    args = _args(tmp_path, "--start", "2026-01-01", "--end", "2026-01-15")
    first_shard = runner.build_split_shards(
        market="HO",
        year=2026,
        reports_root=Path(args.reports_root),
        start="2026-01-01",
        end="2026-01-15",
    )[0]
    _write_report(first_shard.json_out, "PASS")
    seen_commands: list[list[str]] = []

    def pass_child(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        seen_commands.append(command)
        json_out = Path(command[command.index("--json-out") + 1])
        _write_report(json_out, "PASS")
        return subprocess.CompletedProcess(command, 0, stdout="ok\n", stderr="")

    summary = runner.run_split(args, run_child=pass_child)

    assert summary["status"] == "PASS"
    assert [row["label"] for row in summary["skipped_shards"]] == ["HO_2026_w01"]
    assert [row["label"] for row in summary["processed_shards"]] == ["HO_2026_w02"]
    assert len(seen_commands) == 1


def test_existing_non_pass_report_blocks_without_rerun(tmp_path: Path) -> None:
    args = _args(tmp_path, "--start", "2026-01-01", "--end", "2026-01-08")
    shard = runner.build_split_shards(
        market="HO",
        year=2026,
        reports_root=Path(args.reports_root),
        start="2026-01-01",
        end="2026-01-08",
    )[0]
    _write_report(shard.json_out, "FAIL")

    def fail_child(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("child should not run")

    summary = runner.run_split(args, run_child=fail_child)

    assert summary["status"] == "FAIL"
    assert summary["failed_shards"][0]["label"] == "HO_2026_w01"
    assert "existing non-PASS report status=FAIL" in summary["failed_shards"][0]["reason"]


def test_child_failure_stops_runner(tmp_path: Path) -> None:
    args = _args(tmp_path, "--start", "2026-01-01", "--end", "2026-01-15")

    def fail_child(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        json_out = Path(command[command.index("--json-out") + 1])
        _write_report(json_out, "FAIL")
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="failed\n")

    summary = runner.run_split(args, run_child=fail_child)

    assert summary["status"] == "FAIL"
    assert [row["label"] for row in summary["failed_shards"]] == ["HO_2026_w01"]
    assert summary["failed_shards"][0]["returncode"] == 1
    assert summary["failed_shards"][0]["report_status"] == "FAIL"


def test_invalid_window_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside local trades access window"):
        runner.build_split_shards(
            market="HO",
            year=2026,
            reports_root=tmp_path,
            start="2024-01-01",
            end="2024-01-08",
        )
