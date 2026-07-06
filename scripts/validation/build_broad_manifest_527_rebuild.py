#!/usr/bin/env python3
"""Build the approved broad_manifest_527_rebuild_v1 Phase 2 candidates."""

from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
import tempfile
from typing import Any, Callable, Iterable

from scripts.phase2_causal_base import build_causal_base_data as phase2


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_ROOT = Path(
    "reports/data_audit/source_of_truth_lineage/broader_lineage_review_20260628"
)
DEFAULT_INCLUDE = (
    REVIEW_ROOT
    / "broad_manifest_527_rebuild_ready_only_include_460_excluding_6M_2012_vendor_ohlcv_policy.json"
)
DEFAULT_READINESS = (
    REVIEW_ROOT
    / "broad_manifest_527_rebuild_phase2_readiness_460_excluding_6M_2012_sparse_roll_window_policy.json"
)
DEFAULT_RAW_ALIGNMENT = REVIEW_ROOT / "broad_manifest_527_rebuild_all_raw_alignment.json"
DEFAULT_OUTPUT_ROOT = Path("data/causally_gated_normalized")
DEFAULT_REPORTS_ROOT = Path(
    "reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1"
)
DEFAULT_CHECKPOINT = DEFAULT_REPORTS_ROOT / "build_progress.jsonl"
DEFAULT_RESULT_PAYLOADS = DEFAULT_REPORTS_ROOT / "build_result_payloads.jsonl"

EXPECTED_MARKET_YEAR_COUNT = 460
APPROVAL_TOKEN = phase2.BROAD_MANIFEST_527_REBUILD_APPROVAL_TOKEN
MAX_CHUNK_SIZE = phase2.BROAD_MANIFEST_527_REBUILD_MAX_BUILD_MARKET_YEARS
FORBIDDEN_PAIRS = {("6M", 2012)}
FORBIDDEN_YEARS = {2025, 2026}


@dataclass(frozen=True)
class BuildInputs:
    config: Any
    inputs: list[tuple[str, int, Path]]
    selection_metadata: dict[str, Any]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_cwd_failure(prefix: str) -> str | None:
    cwd = Path.cwd().resolve()
    repo_root = REPO_ROOT.resolve()
    if cwd != repo_root:
        return f"{prefix}: must run from repo root {repo_root}; current cwd is {cwd}"
    return None


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _pair_text(pair: tuple[str, int]) -> str:
    return f"{pair[0]}:{pair[1]}"


def _path_is_under_data(path: Path) -> bool:
    data_root = Path("data").resolve()
    try:
        resolved = path.resolve()
        return os.path.commonpath([str(data_root), str(resolved)]) == str(data_root)
    except (OSError, ValueError):
        normalized = path.as_posix().lower().lstrip("./")
        return normalized == "data" or normalized.startswith("data/")


def _checkpoint_writer(path: Path) -> tuple[Any, Callable[[dict[str, Any]], None]]:
    if _path_is_under_data(path):
        raise ValueError(f"checkpoint path must not be under data/**: {path.as_posix()}")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w", encoding="utf-8")

    def write(record: dict[str, Any]) -> None:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()

    return handle, write


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                rows.append(json.loads(text))
    return rows


def _chunked(
    rows: list[tuple[str, int, Path]],
    chunk_size: int,
) -> Iterable[list[tuple[str, int, Path]]]:
    for start in range(0, len(rows), chunk_size):
        yield rows[start : start + chunk_size]


def _count_checkpoint_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _line in handle)


def _parquet_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _path in path.rglob("*.parquet"))


def _last_checkpoint_line(path: Path) -> str:
    if not path.exists():
        return ""
    last = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            last = line.rstrip("\n")
    return last


def _start_monitor_thread(
    *,
    checkpoint_path: Path,
    output_root: Path,
    interval_seconds: int,
    max_stalled_checks: int,
    stop_event: threading.Event,
) -> threading.Thread | None:
    if interval_seconds < 1:
        return None

    def monitor() -> None:
        last_lines = -1
        last_parquet = -1
        stalled = 0
        while not stop_event.wait(interval_seconds):
            lines = _count_checkpoint_lines(checkpoint_path)
            parquet = _parquet_count(output_root)
            last = _last_checkpoint_line(checkpoint_path)
            progressed = lines != last_lines or parquet != last_parquet
            stalled = 0 if progressed else stalled + 1
            last_lines = lines
            last_parquet = parquet
            print(
                f"monitor tick={_utc_now()} checkpoint_lines={lines} "
                f"parquet_count={parquet} stalled_checks={stalled} last={last}",
                flush=True,
            )
            if max_stalled_checks >= 1 and stalled >= max_stalled_checks:
                print(
                    "monitor_stop reason=stalled "
                    f"stalled_checks={stalled} interval_seconds={interval_seconds}",
                    flush=True,
                )
                os._exit(2)

    thread = threading.Thread(target=monitor, name="broad-rebuild-monitor", daemon=True)
    thread.start()
    return thread


def _forbidden_pairs(pairs: Iterable[tuple[str, int]]) -> list[tuple[str, int]]:
    return sorted(
        {
            (market, year)
            for market, year in pairs
            if (market, year) in FORBIDDEN_PAIRS or year in FORBIDDEN_YEARS
        }
    )


def _approved_output_pairs(output_root: Path, approved_pairs: set[tuple[str, int]]) -> list[str]:
    failures: list[str] = []
    if not output_root.exists():
        return failures
    for path in output_root.rglob("*.parquet"):
        try:
            pair = (path.parent.name, int(path.stem))
        except ValueError:
            failures.append(f"unexpected parquet path under output root: {path.as_posix()}")
            continue
        if pair not in approved_pairs:
            failures.append(f"existing parquet is outside approved scope: {path.as_posix()}")
    return failures


def _existing_report_failures(reports_root: Path) -> list[str]:
    if not reports_root.exists():
        return []
    allowed = {"build_progress.jsonl", "build_result_payloads.jsonl"}
    failures: list[str] = []
    for path in reports_root.iterdir():
        if path.name not in allowed:
            failures.append(f"unexpected existing report artifact: {path.as_posix()}")
    return failures


def validate_include(path: Path) -> tuple[list[tuple[str, int]], list[str]]:
    failures: list[str] = []
    try:
        payload = _read_json(path)
        pairs = phase2.load_market_year_include_list(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [], [f"include list invalid: {exc}"]

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        failures.append("include list missing summary object")
        summary = {}
    if len(pairs) != EXPECTED_MARKET_YEAR_COUNT:
        failures.append(
            "include list row count mismatch: "
            f"expected={EXPECTED_MARKET_YEAR_COUNT} observed={len(pairs)}"
        )
    if summary.get("approval_token") != APPROVAL_TOKEN:
        failures.append("include list approval token is missing or stale")
    if summary.get("approved_ready_row_count") != EXPECTED_MARKET_YEAR_COUNT:
        failures.append("include list approved_ready_row_count is not 460")
    if summary.get("build_approved") is not True:
        failures.append("include list does not approve this build gate")
    for key in (
        "broader_modeling_approved",
        "config_promotion_approved",
        "research_use_allowed",
    ):
        if summary.get(key) is not False:
            failures.append(f"include list must keep {key}=false")
    forbidden = _forbidden_pairs(pairs)
    if forbidden:
        failures.append(
            "include list contains forbidden market-years: "
            + ", ".join(_pair_text(pair) for pair in forbidden[:20])
        )
    return pairs, failures


def validate_readiness(path: Path) -> list[str]:
    try:
        payload = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"readiness report invalid: {exc}"]

    checks = {
        "status": "PASS",
        "selected_market_year_count": EXPECTED_MARKET_YEAR_COUNT,
        "checked_market_year_count": EXPECTED_MARKET_YEAR_COUNT,
        "pending_market_year_count": 0,
        "blocker_count": 0,
        "failure_count": 0,
    }
    failures: list[str] = []
    for key, expected in checks.items():
        if payload.get(key) != expected:
            failures.append(
                f"readiness {key} mismatch: expected={expected!r} observed={payload.get(key)!r}"
            )
    return failures


def select_build_inputs(
    *,
    profile: str,
    raw_root: Path,
    raw_alignment_report: Path,
    profile_config: Path,
    session_config: Path,
    include_path: Path,
    include_pairs: list[tuple[str, int]],
) -> BuildInputs:
    raw_alignment_failures = phase2.raw_alignment_guard_failures(
        report_path=raw_alignment_report,
        raw_root=raw_root,
        profile=profile,
        profile_config_path=profile_config,
    )
    if raw_alignment_failures:
        raise ValueError("raw alignment guard failed: " + "; ".join(raw_alignment_failures))

    config = phase2.load_causal_base_config(profile_config, profile)
    raw_alignment = _read_json(raw_alignment_report)
    selection = phase2.select_phase2_inputs(
        profile=profile,
        raw_root=raw_root,
        raw_alignment=raw_alignment,
        profile_config_path=profile_config,
        include_market_years=include_pairs,
        include_list_path=include_path,
    )
    if selection.failures:
        raise ValueError("input selection failed: " + "; ".join(selection.failures))
    if len(selection.inputs) != EXPECTED_MARKET_YEAR_COUNT:
        raise ValueError(
            "selected input count mismatch: "
            f"expected={EXPECTED_MARKET_YEAR_COUNT} observed={len(selection.inputs)}"
        )
    return BuildInputs(
        config=config,
        inputs=selection.inputs,
        selection_metadata=selection.metadata,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="all_raw")
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT))
    parser.add_argument("--profile-config", default="configs/alpha_tiered.yaml")
    parser.add_argument("--session-config", default="configs/market_sessions.yaml")
    parser.add_argument("--raw-alignment-report", default=str(DEFAULT_RAW_ALIGNMENT))
    parser.add_argument("--market-year-include-list", default=str(DEFAULT_INCLUDE))
    parser.add_argument("--readiness-report", default=str(DEFAULT_READINESS))
    parser.add_argument("--checkpoint-jsonl", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--result-payloads-jsonl", default=str(DEFAULT_RESULT_PAYLOADS))
    parser.add_argument("--chunk-size", type=int, default=MAX_CHUNK_SIZE)
    parser.add_argument("--monitor-interval-seconds", type=int, default=0)
    parser.add_argument("--monitor-max-stalled-checks", type=int, default=20)
    parser.add_argument("--single-timeout-seconds", type=int, default=900)
    parser.add_argument(
        "--direct-batch-size",
        type=int,
        default=0,
        help=(
            "Process the next N approved market-years directly in this process, "
            "append result payloads immediately, and exit. N must be 1..25."
        ),
    )
    parser.add_argument("--broad-build-approval-token", required=True)
    parser.add_argument("--single-input-path", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--single-output-path", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--single-result-json", default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--one-market-year-per-invocation",
        action="store_true",
        help=(
            "Process only the next unprocessed approved market-year, append its "
            "result payload, and exit. When all payloads exist, finalize reports."
        ),
    )
    parser.add_argument(
        "--loop-one-market-year-until-complete",
        action="store_true",
        help=(
            "Repeat the one-market-year resume path in this process until the "
            "manifest exists or --max-loop-steps is reached."
        ),
    )
    parser.add_argument(
        "--max-loop-steps",
        type=int,
        default=0,
        help="Maximum one-market-year loop iterations; 0 means no explicit limit.",
    )
    parser.add_argument(
        "--resume-existing-partial",
        action="store_true",
        help=(
            "Allow retry when the protected output root contains only already "
            "approved partial parquet outputs and the reports root contains no "
            "manifest/validation artifact."
        ),
    )
    return parser


def _preflight_failures(args: argparse.Namespace) -> tuple[list[tuple[str, int]], list[str]]:
    failures: list[str] = []
    if args.broad_build_approval_token != APPROVAL_TOKEN:
        failures.append("missing or incorrect broad build approval token")
    if args.chunk_size < 1:
        failures.append("--chunk-size must be >= 1")
    if args.chunk_size > MAX_CHUNK_SIZE:
        failures.append(f"--chunk-size must be <= {MAX_CHUNK_SIZE}")
    if args.monitor_interval_seconds < 0:
        failures.append("--monitor-interval-seconds must be >= 0")
    if args.monitor_max_stalled_checks < 1:
        failures.append("--monitor-max-stalled-checks must be >= 1")
    if args.single_timeout_seconds < 1:
        failures.append("--single-timeout-seconds must be >= 1")

    output_root = Path(args.output_root)
    reports_root = Path(args.reports_root)
    checkpoint = Path(args.checkpoint_jsonl)
    result_payloads = Path(args.result_payloads_jsonl)
    if _path_is_under_data(checkpoint):
        failures.append(f"checkpoint path must not be under data/**: {checkpoint.as_posix()}")
    if _path_is_under_data(result_payloads):
        failures.append(
            f"result payload path must not be under data/**: {result_payloads.as_posix()}"
        )

    include_pairs, include_failures = validate_include(Path(args.market_year_include_list))
    failures.extend(include_failures)
    failures.extend(validate_readiness(Path(args.readiness_report)))
    approved_pairs = set(include_pairs)
    if output_root.exists() and not args.resume_existing_partial:
        failures.append(f"output root already exists: {output_root.as_posix()}")
    if reports_root.exists() and not args.resume_existing_partial:
        failures.append(f"reports root already exists: {reports_root.as_posix()}")
    if args.resume_existing_partial:
        failures.extend(_approved_output_pairs(output_root, approved_pairs))
        failures.extend(_existing_report_failures(reports_root))
    return include_pairs, failures


def _write_reports(
    *,
    results: list[Any],
    args: argparse.Namespace,
    output_root: Path,
    reports_root: Path,
    build_inputs: BuildInputs,
    local_trade_gap_gate: dict[str, Any] | None,
) -> None:
    phase2.write_reports(
        results,
        reports_root,
        args.profile,
        Path(args.profile_config),
        input_root=Path(args.raw_root),
        output_root=output_root,
        local_trade_gap_gate=local_trade_gap_gate,
        selection_metadata=build_inputs.selection_metadata,
        allow_broad_build_after_readiness_pass=True,
        broad_build_approval_token=args.broad_build_approval_token,
    )


def _validation_result_from_dict(payload: dict[str, Any]) -> Any:
    field_names = {field.name for field in fields(phase2.ValidationResult)}
    kwargs = {key: value for key, value in payload.items() if key in field_names}
    return phase2.ValidationResult(**kwargs)


def _run_single_market_year(args: argparse.Namespace) -> int:
    if args.broad_build_approval_token != APPROVAL_TOKEN:
        print("FAIL single_market_year: missing or incorrect broad build approval token")
        return 1
    try:
        result = phase2.process_file(
            Path(args.single_input_path),
            Path(args.single_output_path),
            profile=args.profile,
            roll_window_bars=phase2.DEFAULT_ROLL_WINDOW_BARS,
            profile_config_path=Path(args.profile_config),
            session_config_path=Path(args.session_config),
            allow_broad_build_after_readiness_pass=True,
            broad_build_approval_token=args.broad_build_approval_token,
        )
        result_path = Path(args.single_result_json)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"{result.status} {result.market} {result.year}: raw={result.raw_rows} "
            f"out={result.output_rows} synthetic={result.synthetic_rows} "
            f"warnings={len(result.warnings)} failures={len(result.failures)}",
            flush=True,
        )
        return 0 if not result.failures else 1
    except BaseException as exc:
        print(
            "FAIL single_market_year: "
            f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            flush=True,
        )
        return 1


def _run_single_subprocess(
    *,
    args: argparse.Namespace,
    input_path: Path,
    output_path: Path,
    result_json: Path,
) -> subprocess.CompletedProcess[str]:
    command = [
        os.sys.executable,
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
        args.profile,
        "--profile-config",
        args.profile_config,
        "--session-config",
        args.session_config,
        "--broad-build-approval-token",
        args.broad_build_approval_token,
    ]
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=args.single_timeout_seconds,
    )


def _finalize_from_payloads(
    *,
    args: argparse.Namespace,
    build_inputs: BuildInputs,
    payloads: list[dict[str, Any]],
    output_root: Path,
    reports_root: Path,
) -> int:
    payload_by_pair = {
        (str(payload.get("market")), int(payload.get("year"))): payload
        for payload in payloads
    }
    ordered_payloads = [
        payload_by_pair[(market, year)]
        for market, year, _input_path in build_inputs.inputs
    ]
    results = [_validation_result_from_dict(payload) for payload in ordered_payloads]
    output_count = len(list(output_root.rglob("*.parquet")))
    if output_count != EXPECTED_MARKET_YEAR_COUNT:
        print(
            "FAIL broad_manifest_527_build: output count mismatch "
            f"outputs={output_count} expected={EXPECTED_MARKET_YEAR_COUNT}",
            flush=True,
        )
        return 1

    local_trade_gap_gate = None
    if phase2.profile_requires_local_trade_gap_gate(args.profile, Path(args.profile_config)):
        local_trade_gap_gate = phase2.build_local_trade_ohlcv_gap_gate(
            markets=sorted({result.market for result in results}),
            raw_root=Path(args.raw_root),
            causal_root=output_root,
            reports_root=reports_root,
            profile_config_path=Path(args.profile_config),
        )
    else:
        print("local_trade_ohlcv_gap_gate status=SKIPPED")

    _write_reports(
        results=results,
        args=args,
        output_root=output_root,
        reports_root=reports_root,
        build_inputs=build_inputs,
        local_trade_gap_gate=local_trade_gap_gate,
    )

    manifest_path = reports_root / "causal_base_manifest.json"
    validation_path = reports_root / "causal_base_validation.json"
    manifest = _read_json(manifest_path)
    validation = _read_json(validation_path)
    outputs = manifest.get("outputs")
    failures: list[str] = []
    if manifest.get("status") != "PASS":
        failures.append(f"manifest status is {manifest.get('status')!r}")
    if validation.get("status") != "PASS":
        failures.append(f"validation status is {validation.get('status')!r}")
    if not isinstance(outputs, list) or len(outputs) != EXPECTED_MARKET_YEAR_COUNT:
        failures.append("manifest output count mismatch")
    forbidden_outputs = [
        output_root / market / f"{year}.parquet"
        for market, year in sorted(FORBIDDEN_PAIRS)
        if (output_root / market / f"{year}.parquet").exists()
    ]
    forbidden_outputs.extend(output_root.glob("*/2025.parquet"))
    forbidden_outputs.extend(output_root.glob("*/2026.parquet"))
    if forbidden_outputs:
        failures.append(
            "forbidden outputs exist: "
            + ", ".join(path.as_posix() for path in forbidden_outputs[:20])
        )
    if failures:
        for failure in failures:
            print(f"FAIL broad_manifest_527_build: {failure}", flush=True)
        return 1
    _append_jsonl(
        Path(args.checkpoint_jsonl),
        {
            "stage": "broad_manifest_527_build_summary",
            "status": "PASS",
            "processed_market_year_count": len(results),
            "output_file_count": output_count,
            "manifest_path": manifest_path.as_posix(),
            "validation_path": validation_path.as_posix(),
        },
    )
    print(
        "broad_manifest_527_build "
        f"status=PASS outputs={output_count} manifest={manifest_path.as_posix()}",
        flush=True,
    )
    return 0


def run_one_market_year(args: argparse.Namespace) -> int:
    include_pairs, failures = _preflight_failures(args)
    if failures:
        for failure in failures:
            print(f"FAIL broad_manifest_527_build: {failure}")
        return 1

    output_root = Path(args.output_root)
    reports_root = Path(args.reports_root)
    try:
        build_inputs = select_build_inputs(
            profile=args.profile,
            raw_root=Path(args.raw_root),
            raw_alignment_report=Path(args.raw_alignment_report),
            profile_config=Path(args.profile_config),
            session_config=Path(args.session_config),
            include_path=Path(args.market_year_include_list),
            include_pairs=include_pairs,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL broad_manifest_527_build: {exc}")
        return 1

    payload_path = Path(args.result_payloads_jsonl)
    payloads = _read_jsonl(payload_path)
    payload_by_pair = {
        (str(payload.get("market")), int(payload.get("year"))): payload
        for payload in payloads
    }
    done_pairs = set(payload_by_pair)
    if len(done_pairs) > EXPECTED_MARKET_YEAR_COUNT:
        print("FAIL broad_manifest_527_build: too many result payloads")
        return 1
    if done_pairs and done_pairs - set(include_pairs):
        print("FAIL broad_manifest_527_build: result payload outside approved scope")
        return 1

    next_item = None
    for market, year, input_path in build_inputs.inputs:
        if (market, year) not in done_pairs:
            next_item = (market, year, input_path)
            break
    if next_item is None:
        return _finalize_from_payloads(
            args=args,
            build_inputs=build_inputs,
            payloads=[payload_by_pair[(m, y)] for m, y, _p in build_inputs.inputs],
            output_root=output_root,
            reports_root=reports_root,
        )

    market, year, input_path = next_item
    output_path = output_root / market / f"{year}.parquet"
    _append_jsonl(
        Path(args.checkpoint_jsonl),
        {
            "stage": "broad_manifest_527_build_market_year_start",
            "market": market,
            "year": year,
            "input_path": input_path.as_posix(),
            "output_path": output_path.as_posix(),
            "started_at_utc": _utc_now(),
            "step_mode": True,
            "processed_before_step": len(done_pairs),
        },
    )
    with tempfile.TemporaryDirectory(prefix="broad_manifest_527_step_") as temp_dir:
        result_json = Path(temp_dir) / f"{market}_{year}.json"
        try:
            completed = _run_single_subprocess(
                args=args,
                input_path=input_path,
                output_path=output_path,
                result_json=result_json,
            )
        except subprocess.TimeoutExpired as exc:
            _append_jsonl(
                Path(args.checkpoint_jsonl),
                {
                    "stage": "broad_manifest_527_build_summary",
                    "status": "FAIL",
                    "market": market,
                    "year": year,
                    "reason": "single_market_year_timeout",
                    "timeout_seconds": args.single_timeout_seconds,
                    "stdout": exc.stdout,
                    "stderr": exc.stderr,
                },
            )
            print(f"FAIL broad_manifest_527_build: {market}:{year} timeout")
            return 1
        if completed.returncode != 0 or not result_json.exists():
            _append_jsonl(
                Path(args.checkpoint_jsonl),
                {
                    "stage": "broad_manifest_527_build_summary",
                    "status": "FAIL",
                    "market": market,
                    "year": year,
                    "reason": "single_market_year_failed",
                    "returncode": completed.returncode,
                    "stdout_tail": completed.stdout.splitlines()[-20:],
                    "stderr_tail": completed.stderr.splitlines()[-40:],
                },
            )
            print(
                f"FAIL broad_manifest_527_build: {market}:{year} "
                f"subprocess rc={completed.returncode}",
                flush=True,
            )
            if completed.stdout:
                print(completed.stdout, flush=True)
            if completed.stderr:
                print(completed.stderr, flush=True)
            return 1
        payload = _read_json(result_json)
    failures = payload.get("failures") or []
    warnings = payload.get("warnings") or []
    if failures:
        print(f"FAIL broad_manifest_527_build: {market}:{year} validation failures")
        return 1
    _append_jsonl(payload_path, payload)
    _append_jsonl(
        Path(args.checkpoint_jsonl),
        {
            "stage": "broad_manifest_527_build_market_year",
            "market": payload.get("market"),
            "year": payload.get("year"),
            "status": payload.get("status"),
            "raw_rows": payload.get("raw_rows"),
            "output_rows": payload.get("output_rows"),
            "synthetic_rows": payload.get("synthetic_rows"),
            "warning_count": len(warnings),
            "failure_count": len(failures),
            "input_path": payload.get("input_path"),
            "output_path": payload.get("output_path"),
            "processed_market_year_count": len(done_pairs) + 1,
        },
    )
    print(completed.stdout.rstrip(), flush=True)
    if len(done_pairs) + 1 == EXPECTED_MARKET_YEAR_COUNT:
        return _finalize_from_payloads(
            args=args,
            build_inputs=build_inputs,
            payloads=[
                *(payload_by_pair[(m, y)] for m, y, _p in build_inputs.inputs if (m, y) in payload_by_pair),
                payload,
            ],
            output_root=output_root,
            reports_root=reports_root,
        )
    return 0


def run_one_market_year_loop(args: argparse.Namespace) -> int:
    if args.max_loop_steps < 0:
        print("FAIL broad_manifest_527_build: --max-loop-steps must be >= 0")
        return 1
    steps = 0
    last_tick = 0.0
    reports_root = Path(args.reports_root)
    manifest_path = reports_root / "causal_base_manifest.json"
    while True:
        rc = run_one_market_year(args)
        steps += 1
        now = time.monotonic()
        if args.monitor_interval_seconds and now - last_tick >= args.monitor_interval_seconds:
            last_tick = now
            print(
                "loop_checker "
                f"tick={_utc_now()} rc={rc} steps={steps} "
                f"payload_count={len(_read_jsonl(Path(args.result_payloads_jsonl)))} "
                f"parquet_count={_parquet_count(Path(args.output_root))} "
                f"last={_last_checkpoint_line(Path(args.checkpoint_jsonl))}",
                flush=True,
            )
        if rc != 0:
            return rc
        if manifest_path.exists():
            return 0
        if args.max_loop_steps and steps >= args.max_loop_steps:
            print(
                "broad_manifest_527_loop "
                f"status=PAUSED steps={steps} "
                f"payload_count={len(_read_jsonl(Path(args.result_payloads_jsonl)))} "
                f"parquet_count={_parquet_count(Path(args.output_root))}",
                flush=True,
            )
            return 0


def run_direct_batch(args: argparse.Namespace) -> int:
    if args.direct_batch_size < 1 or args.direct_batch_size > MAX_CHUNK_SIZE:
        print(f"FAIL broad_manifest_527_build: --direct-batch-size must be 1..{MAX_CHUNK_SIZE}")
        return 1
    include_pairs, failures = _preflight_failures(args)
    if failures:
        for failure in failures:
            print(f"FAIL broad_manifest_527_build: {failure}")
        return 1

    output_root = Path(args.output_root)
    reports_root = Path(args.reports_root)
    try:
        build_inputs = select_build_inputs(
            profile=args.profile,
            raw_root=Path(args.raw_root),
            raw_alignment_report=Path(args.raw_alignment_report),
            profile_config=Path(args.profile_config),
            session_config=Path(args.session_config),
            include_path=Path(args.market_year_include_list),
            include_pairs=include_pairs,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL broad_manifest_527_build: {exc}")
        return 1

    payload_path = Path(args.result_payloads_jsonl)
    payloads = _read_jsonl(payload_path)
    payload_by_pair = {
        (str(payload.get("market")), int(payload.get("year"))): payload
        for payload in payloads
    }
    done_pairs = set(payload_by_pair)
    approved_pairs = set(include_pairs)
    if done_pairs and done_pairs - approved_pairs:
        print("FAIL broad_manifest_527_build: result payload outside approved scope")
        return 1

    remaining = [
        (market, year, input_path)
        for market, year, input_path in build_inputs.inputs
        if (market, year) not in done_pairs
    ]
    if not remaining:
        return _finalize_from_payloads(
            args=args,
            build_inputs=build_inputs,
            payloads=[payload_by_pair[(m, y)] for m, y, _p in build_inputs.inputs],
            output_root=output_root,
            reports_root=reports_root,
        )

    processed = 0
    last_tick = time.monotonic()
    for market, year, input_path in remaining[: args.direct_batch_size]:
        output_path = output_root / market / f"{year}.parquet"
        _append_jsonl(
            Path(args.checkpoint_jsonl),
            {
                "stage": "broad_manifest_527_build_market_year_start",
                "market": market,
                "year": year,
                "input_path": input_path.as_posix(),
                "output_path": output_path.as_posix(),
                "started_at_utc": _utc_now(),
                "direct_batch": True,
                "processed_before_step": len(done_pairs),
            },
        )
        try:
            result = phase2.process_file(
                input_path,
                output_path,
                profile=args.profile,
                roll_window_bars=phase2.DEFAULT_ROLL_WINDOW_BARS,
                profile_config_path=Path(args.profile_config),
                session_config_path=Path(args.session_config),
                allow_broad_build_after_readiness_pass=True,
                broad_build_approval_token=args.broad_build_approval_token,
            )
        except BaseException as exc:
            _append_jsonl(
                Path(args.checkpoint_jsonl),
                {
                    "stage": "broad_manifest_527_build_summary",
                    "status": "FAIL",
                    "market": market,
                    "year": year,
                    "reason": "direct_batch_exception",
                    "exception_type": type(exc).__name__,
                    "exception": str(exc),
                },
            )
            print(
                "FAIL broad_manifest_527_build: "
                f"{market}:{year} {type(exc).__name__}: {exc}\n{traceback.format_exc()}",
                flush=True,
            )
            return 1
        payload = result.to_dict()
        failures = payload.get("failures") or []
        warnings = payload.get("warnings") or []
        if failures:
            _append_jsonl(
                Path(args.checkpoint_jsonl),
                {
                    "stage": "broad_manifest_527_build_summary",
                    "status": "FAIL",
                    "market": market,
                    "year": year,
                    "reason": "validation_result_failures",
                    "failure_count": len(failures),
                },
            )
            print(f"FAIL broad_manifest_527_build: {market}:{year} validation failures")
            return 1
        _append_jsonl(payload_path, payload)
        done_pairs.add((market, year))
        processed += 1
        _append_jsonl(
            Path(args.checkpoint_jsonl),
            {
                "stage": "broad_manifest_527_build_market_year",
                "market": payload.get("market"),
                "year": payload.get("year"),
                "status": payload.get("status"),
                "raw_rows": payload.get("raw_rows"),
                "output_rows": payload.get("output_rows"),
                "synthetic_rows": payload.get("synthetic_rows"),
                "warning_count": len(warnings),
                "failure_count": len(failures),
                "input_path": payload.get("input_path"),
                "output_path": payload.get("output_path"),
                "processed_market_year_count": len(done_pairs),
                "direct_batch": True,
            },
        )
        print(
            f"{payload.get('status')} {market} {year}: "
            f"raw={payload.get('raw_rows')} out={payload.get('output_rows')} "
            f"synthetic={payload.get('synthetic_rows')} "
            f"warnings={len(warnings)} failures={len(failures)}",
            flush=True,
        )
        gc.collect()
        now = time.monotonic()
        if args.monitor_interval_seconds and now - last_tick >= args.monitor_interval_seconds:
            last_tick = now
            print(
                "direct_batch_checker "
                f"tick={_utc_now()} processed={processed} "
                f"payload_count={len(done_pairs)} "
                f"parquet_count={_parquet_count(output_root)} "
                f"last={_last_checkpoint_line(Path(args.checkpoint_jsonl))}",
                flush=True,
            )

    payloads = _read_jsonl(payload_path)
    payload_by_pair = {
        (str(payload.get("market")), int(payload.get("year"))): payload
        for payload in payloads
    }
    if len(payload_by_pair) == EXPECTED_MARKET_YEAR_COUNT:
        return _finalize_from_payloads(
            args=args,
            build_inputs=build_inputs,
            payloads=[payload_by_pair[(m, y)] for m, y, _p in build_inputs.inputs],
            output_root=output_root,
            reports_root=reports_root,
        )
    print(
        "broad_manifest_527_direct_batch "
        f"status=PAUSED processed={processed} "
        f"payload_count={len(payload_by_pair)} "
        f"parquet_count={_parquet_count(output_root)}",
        flush=True,
    )
    return 0


def run(args: argparse.Namespace) -> int:
    include_pairs, failures = _preflight_failures(args)
    if failures:
        for failure in failures:
            print(f"FAIL broad_manifest_527_build: {failure}")
        return 1

    output_root = Path(args.output_root)
    reports_root = Path(args.reports_root)
    stop_monitor = threading.Event()
    monitor_thread = _start_monitor_thread(
        checkpoint_path=Path(args.checkpoint_jsonl),
        output_root=output_root,
        interval_seconds=args.monitor_interval_seconds,
        max_stalled_checks=args.monitor_max_stalled_checks,
        stop_event=stop_monitor,
    )
    try:
        build_inputs = select_build_inputs(
            profile=args.profile,
            raw_root=Path(args.raw_root),
            raw_alignment_report=Path(args.raw_alignment_report),
            profile_config=Path(args.profile_config),
            session_config=Path(args.session_config),
            include_path=Path(args.market_year_include_list),
            include_pairs=include_pairs,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL broad_manifest_527_build: {exc}")
        return 1

    checkpoint_handle = None
    try:
        checkpoint_handle, write_checkpoint = _checkpoint_writer(Path(args.checkpoint_jsonl))
    except ValueError as exc:
        print(f"FAIL broad_manifest_527_build: {exc}")
        return 1

    processed_count = 0
    local_trade_gap_gate: dict[str, Any] | None = None
    try:
        result_payloads: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="broad_manifest_527_results_") as temp_dir:
            result_dir = Path(temp_dir)
            write_checkpoint(
                {
                    "stage": "broad_manifest_527_build_start",
                    "generated_at_utc": _utc_now(),
                    "selected_market_year_count": len(build_inputs.inputs),
                    "expected_market_year_count": EXPECTED_MARKET_YEAR_COUNT,
                    "chunk_size": args.chunk_size,
                    "output_root": output_root.as_posix(),
                    "reports_root": reports_root.as_posix(),
                    "include_path": Path(args.market_year_include_list).as_posix(),
                    "readiness_report": Path(args.readiness_report).as_posix(),
                    "single_process_per_market_year": True,
                }
            )

            for chunk_index, chunk in enumerate(
                _chunked(build_inputs.inputs, args.chunk_size),
                start=1,
            ):
                write_checkpoint(
                    {
                        "stage": "broad_manifest_527_build_chunk_start",
                        "chunk_index": chunk_index,
                        "chunk_size": len(chunk),
                        "processed_before_chunk": processed_count,
                    }
                )
                chunk_failures = 0
                for market, year, input_path in chunk:
                    output_path = output_root / market / f"{year}.parquet"
                    result_json = result_dir / f"{market}_{year}.json"
                    write_checkpoint(
                        {
                            "stage": "broad_manifest_527_build_market_year_start",
                            "market": market,
                            "year": year,
                            "input_path": input_path.as_posix(),
                            "output_path": output_path.as_posix(),
                            "started_at_utc": _utc_now(),
                        }
                    )
                    try:
                        completed = _run_single_subprocess(
                            args=args,
                            input_path=input_path,
                            output_path=output_path,
                            result_json=result_json,
                        )
                    except subprocess.TimeoutExpired as exc:
                        write_checkpoint(
                            {
                                "stage": "broad_manifest_527_build_summary",
                                "status": "FAIL",
                                "processed_market_year_count": processed_count,
                                "market": market,
                                "year": year,
                                "reason": "single_market_year_timeout",
                                "timeout_seconds": args.single_timeout_seconds,
                                "stdout": exc.stdout,
                                "stderr": exc.stderr,
                            }
                        )
                        print(
                            "FAIL broad_manifest_527_build: "
                            f"{market}:{year} timed out after "
                            f"{args.single_timeout_seconds}s",
                            flush=True,
                        )
                        return 1
                    if completed.returncode != 0 or not result_json.exists():
                        write_checkpoint(
                            {
                                "stage": "broad_manifest_527_build_summary",
                                "status": "FAIL",
                                "processed_market_year_count": processed_count,
                                "market": market,
                                "year": year,
                                "reason": "single_market_year_failed",
                                "returncode": completed.returncode,
                                "stdout_tail": completed.stdout.splitlines()[-20:],
                                "stderr_tail": completed.stderr.splitlines()[-40:],
                            }
                        )
                        print(
                            "FAIL broad_manifest_527_build: "
                            f"{market}:{year} subprocess rc={completed.returncode}",
                            flush=True,
                        )
                        if completed.stdout:
                            print(completed.stdout, flush=True)
                        if completed.stderr:
                            print(completed.stderr, flush=True)
                        return 1
                    result_payload = _read_json(result_json)
                    result_payloads.append(result_payload)
                    failures = result_payload.get("failures") or []
                    warnings = result_payload.get("warnings") or []
                    failure_count = len(failures)
                    chunk_failures += failure_count
                    processed_count += 1
                    write_checkpoint(
                        {
                            "stage": "broad_manifest_527_build_market_year",
                            "market": result_payload.get("market"),
                            "year": result_payload.get("year"),
                            "status": result_payload.get("status"),
                            "raw_rows": result_payload.get("raw_rows"),
                            "output_rows": result_payload.get("output_rows"),
                            "synthetic_rows": result_payload.get("synthetic_rows"),
                            "warning_count": len(warnings),
                            "failure_count": failure_count,
                            "input_path": result_payload.get("input_path"),
                            "output_path": result_payload.get("output_path"),
                        }
                    )
                    print(completed.stdout.rstrip(), flush=True)
                    if failures:
                        write_checkpoint(
                            {
                                "stage": "broad_manifest_527_build_summary",
                                "status": "FAIL",
                                "processed_market_year_count": processed_count,
                                "failure_count": failure_count,
                                "reason": "validation_result_failures",
                            }
                        )
                        return 1
                write_checkpoint(
                    {
                        "stage": "broad_manifest_527_build_chunk_summary",
                        "chunk_index": chunk_index,
                        "processed_market_year_count": processed_count,
                        "chunk_failure_count": chunk_failures,
                    }
                )

            output_count = len(list(output_root.rglob("*.parquet")))
            if (
                processed_count != EXPECTED_MARKET_YEAR_COUNT
                or output_count != EXPECTED_MARKET_YEAR_COUNT
            ):
                write_checkpoint(
                    {
                        "stage": "broad_manifest_527_build_summary",
                        "status": "FAIL",
                        "processed_market_year_count": processed_count,
                        "output_file_count": output_count,
                        "reason": "output_count_mismatch",
                    }
                )
                print(
                    "FAIL broad_manifest_527_build: output count mismatch "
                    f"processed={processed_count} outputs={output_count} "
                    f"expected={EXPECTED_MARKET_YEAR_COUNT}"
                )
                return 1

            results = [
                _validation_result_from_dict(payload) for payload in result_payloads
            ]
            if phase2.profile_requires_local_trade_gap_gate(args.profile, Path(args.profile_config)):
                local_trade_gap_gate = phase2.build_local_trade_ohlcv_gap_gate(
                    markets=sorted({result.market for result in results}),
                    raw_root=Path(args.raw_root),
                    causal_root=output_root,
                    reports_root=reports_root,
                    profile_config_path=Path(args.profile_config),
                )
            else:
                print("local_trade_ohlcv_gap_gate status=SKIPPED")

            _write_reports(
                results=results,
                args=args,
                output_root=output_root,
                reports_root=reports_root,
                build_inputs=build_inputs,
                local_trade_gap_gate=local_trade_gap_gate,
            )

        manifest_path = reports_root / "causal_base_manifest.json"
        validation_path = reports_root / "causal_base_validation.json"
        manifest = _read_json(manifest_path)
        validation = _read_json(validation_path)
        post_failures: list[str] = []
        outputs = manifest.get("outputs")
        if manifest.get("status") != "PASS":
            post_failures.append(f"manifest status is {manifest.get('status')!r}")
        if validation.get("status") != "PASS":
            post_failures.append(f"validation status is {validation.get('status')!r}")
        if not isinstance(outputs, list) or len(outputs) != EXPECTED_MARKET_YEAR_COUNT:
            post_failures.append("manifest output count mismatch")
        forbidden_outputs = [
            output_root / market / f"{year}.parquet"
            for market, year in sorted(FORBIDDEN_PAIRS)
            if (output_root / market / f"{year}.parquet").exists()
        ]
        forbidden_outputs.extend(output_root.glob("*/2025.parquet"))
        forbidden_outputs.extend(output_root.glob("*/2026.parquet"))
        if forbidden_outputs:
            post_failures.append(
                "forbidden outputs exist: "
                + ", ".join(path.as_posix() for path in forbidden_outputs[:20])
            )
        if post_failures:
            write_checkpoint(
                {
                    "stage": "broad_manifest_527_build_summary",
                    "status": "FAIL",
                    "processed_market_year_count": len(results),
                    "output_file_count": output_count,
                    "failures": post_failures,
                }
            )
            for failure in post_failures:
                print(f"FAIL broad_manifest_527_build: {failure}")
            return 1

        write_checkpoint(
            {
                "stage": "broad_manifest_527_build_summary",
                "status": "PASS",
                "processed_market_year_count": len(results),
                "output_file_count": output_count,
                "manifest_path": manifest_path.as_posix(),
                "validation_path": validation_path.as_posix(),
            }
        )
        print(
            "broad_manifest_527_build "
            f"status=PASS outputs={output_count} manifest={manifest_path.as_posix()}",
            flush=True,
        )
        return 0
    finally:
        stop_monitor.set()
        if monitor_thread is not None:
            monitor_thread.join(timeout=5)
        if checkpoint_handle is not None:
            checkpoint_handle.close()


def main(argv: list[str] | None = None) -> int:
    cwd_failure = _repo_cwd_failure("FAIL broad_manifest_527_build")
    if cwd_failure:
        print(cwd_failure)
        return 1
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    single_args = [
        args.single_input_path,
        args.single_output_path,
        args.single_result_json,
    ]
    if any(single_args):
        if not all(single_args):
            parser.error(
                "--single-input-path, --single-output-path, and "
                "--single-result-json must be provided together"
            )
        code = _run_single_market_year(args)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    if args.direct_batch_size:
        code = run_direct_batch(args)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    if args.one_market_year_per_invocation:
        return run_one_market_year(args)
    if args.loop_one_market_year_until_complete:
        return run_one_market_year_loop(args)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
