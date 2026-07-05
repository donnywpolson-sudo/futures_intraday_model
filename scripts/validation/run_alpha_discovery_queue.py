#!/usr/bin/env python3
"""Serial queue runner for guarded alpha discovery candidate configs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from scripts.validation import run_alpha_discovery as single_runner


DEFAULT_LOG_ROOT = Path("logs/alpha_discovery_queue")
INFRASTRUCTURE_FAILURE_MARKERS = (
    "approval token",
    "config is marked template=true",
    "config must be a JSON object",
    "expected generated outputs are not ignored by git",
    "git status failed",
    "invalid config JSON",
    "invalid target registry JSON",
    "missing repo coordination file",
    "missing target registry",
    "missing trial-status file",
    "source test command includes forbidden",
    "source test command is not an approved",
    "target registry must contain",
    "unsupported mode",
)


class QueueError(RuntimeError):
    """Raised when the queue runner must fail closed before candidate work."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _as_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _utc_stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise QueueError(f"missing queue file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise QueueError(f"invalid queue JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise QueueError("queue file must be a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _require_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise QueueError(f"queue field {field!r} must be boolean")
    return value


def _is_infrastructure_failure(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in INFRASTRUCTURE_FAILURE_MARKERS)


def _validate_queue(payload: dict[str, Any], *, root: Path) -> tuple[list[dict[str, Any]], bool]:
    if payload.get("schema_version") != 1:
        raise QueueError("queue schema_version must be 1")

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise QueueError("queue candidates must contain at least one entry")

    max_candidates = payload.get("max_candidates", len(candidates))
    if not isinstance(max_candidates, int) or max_candidates <= 0:
        raise QueueError("queue max_candidates must be a positive integer")
    if len(candidates) > max_candidates:
        raise QueueError(
            f"queue has {len(candidates)} candidates but max_candidates is {max_candidates}"
        )

    stop_on_infrastructure_failure = _require_bool(
        payload.get("stop_on_infrastructure_failure", True),
        field="stop_on_infrastructure_failure",
    )

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(candidates, start=1):
        if not isinstance(entry, dict):
            raise QueueError(f"candidate entry {index} must be a JSON object")
        candidate_id = entry.get("id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise QueueError(f"candidate entry {index} field 'id' is required")
        candidate_id = candidate_id.strip()
        if candidate_id in seen_ids:
            raise QueueError(f"duplicate candidate id: {candidate_id}")
        seen_ids.add(candidate_id)

        config = entry.get("config")
        if not isinstance(config, str) or not config.strip():
            raise QueueError(f"candidate {candidate_id} field 'config' is required")
        config_path = _as_path(root, config.strip())
        if not config_path.exists():
            raise QueueError(f"missing config path for candidate {candidate_id}: {config}")

        approved = entry.get("approved", False)
        if not isinstance(approved, bool):
            raise QueueError(f"candidate {candidate_id} field 'approved' must be boolean")

        normalized.append(
            {
                "id": candidate_id,
                "config": config.strip(),
                "approved": approved,
            }
        )

    return normalized, stop_on_infrastructure_failure


def _effective_mode(payload: dict[str, Any], mode_override: str | None) -> str:
    mode = mode_override or str(payload.get("runner_mode", "preflight"))
    if mode not in single_runner.ALLOWED_MODES:
        raise QueueError(
            f"unsupported mode {mode!r}; expected one of {sorted(single_runner.ALLOWED_MODES)}"
        )
    return mode


def _candidate_row(
    *,
    candidate: dict[str, Any],
    index: int,
    mode: str,
    status: str,
    result: dict[str, Any] | None = None,
    failure: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "index": index,
        "candidate_id": candidate["id"],
        "config": candidate["config"],
        "approved": candidate["approved"],
        "mode": mode,
        "status": status,
    }
    if result is not None:
        row["runner_status"] = result.get("status")
        row["result"] = result
    if failure:
        row["failure"] = failure
    return row


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_error_count = sum(1 for row in rows if row["status"] == "CANDIDATE_FAILED")
    infrastructure_failure_count = sum(
        1 for row in rows if row["status"] == "INFRASTRUCTURE_FAILURE"
    )
    discovery_pass_count = sum(
        1
        for row in rows
        if row.get("runner_status") == "DISCOVERY_RUN_CANDIDATE_DISCOVERY_PASS"
    )
    candidate_stopped_count = sum(
        1 for row in rows if row.get("runner_status") == "DISCOVERY_RUN_CANDIDATE_STOPPED"
    )
    review_required_count = sum(
        1 for row in rows if row.get("runner_status") == "DISCOVERY_RUN_REVIEW_REQUIRED"
    )
    command_failed_count = sum(
        1 for row in rows if row.get("runner_status") == "DISCOVERY_RUN_COMMAND_FAILED"
    )
    completed_count = sum(1 for row in rows if row["status"] == "CANDIDATE_COMPLETED")
    return {
        "candidate_count": len(rows),
        "candidate_completed_count": completed_count,
        "candidate_error_count": candidate_error_count,
        "infrastructure_failure_count": infrastructure_failure_count,
        "discovery_pass_count": discovery_pass_count,
        "candidate_stopped_count": candidate_stopped_count,
        "review_required_count": review_required_count,
        "command_failed_count": command_failed_count,
    }


def _queue_status(summary: dict[str, Any]) -> str:
    if summary["infrastructure_failure_count"]:
        return "QUEUE_INFRASTRUCTURE_FAILURE"
    if summary["candidate_error_count"]:
        return "QUEUE_COMPLETED_WITH_CANDIDATE_FAILURES"
    return "QUEUE_COMPLETED"


def run_queue(
    *,
    queue_path: Path,
    root: Path,
    mode_override: str | None,
    approval_token: str | None,
    approve_discovery_run: bool,
    log_root_override: Path | None = None,
) -> dict[str, Any]:
    queue_payload = _read_json(queue_path)
    candidates, stop_on_infrastructure_failure = _validate_queue(queue_payload, root=root)
    mode = _effective_mode(queue_payload, mode_override)
    if mode == "discovery-run":
        if not approve_discovery_run:
            raise QueueError("queue discovery-run requires --approve-discovery-run")
        if not approval_token:
            raise QueueError("queue discovery-run requires --approval-token")
        unapproved = [candidate["id"] for candidate in candidates if not candidate["approved"]]
        if unapproved:
            raise QueueError(f"queue discovery-run has unapproved candidates: {unapproved}")
    else:
        approval_token = None

    configured_log_root = queue_payload.get("log_root", str(DEFAULT_LOG_ROOT))
    if not isinstance(configured_log_root, str) or not configured_log_root.strip():
        raise QueueError("queue log_root must be a non-empty string when provided")
    log_root = log_root_override or _as_path(root, configured_log_root)
    stamp = _utc_stamp()
    row_log_path = log_root / f"alpha_discovery_queue_{stamp}.jsonl"
    summary_path = log_root / f"alpha_discovery_queue_{stamp}.json"

    rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        try:
            config_path = _as_path(root, candidate["config"])
            config = single_runner.load_config(config_path)
            result = single_runner.run_mode(
                config,
                root=root,
                mode=mode,
                approval_token=approval_token,
            )
            row = _candidate_row(
                candidate=candidate,
                index=index,
                mode=mode,
                status="CANDIDATE_COMPLETED",
                result=result,
            )
        except subprocess.TimeoutExpired as exc:
            row = _candidate_row(
                candidate=candidate,
                index=index,
                mode=mode,
                status="CANDIDATE_FAILED",
                failure=f"command timed out after {exc.timeout} seconds",
            )
        except single_runner.RunnerError as exc:
            failure = str(exc)
            status = (
                "INFRASTRUCTURE_FAILURE"
                if _is_infrastructure_failure(failure)
                else "CANDIDATE_FAILED"
            )
            row = _candidate_row(
                candidate=candidate,
                index=index,
                mode=mode,
                status=status,
                failure=failure,
            )
        rows.append(row)
        _append_jsonl(row_log_path, row)
        if row["status"] == "INFRASTRUCTURE_FAILURE" and stop_on_infrastructure_failure:
            break

    summary = _summarize_rows(rows)
    payload = {
        "status": _queue_status(summary),
        "queue_completed": summary["infrastructure_failure_count"] == 0,
        "mode": mode,
        "queue": _relative(root, queue_path),
        "stop_on_infrastructure_failure": stop_on_infrastructure_failure,
        "summary": summary,
        "row_log_path": _relative(root, row_log_path),
        "summary_log_path": _relative(root, summary_path),
        "results": rows,
    }
    _write_json(summary_path, payload)
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, help="JSON queue file to load")
    parser.add_argument("--mode", choices=sorted(single_runner.ALLOWED_MODES))
    parser.add_argument("--log-root", help="ignored log directory for queue summaries")
    parser.add_argument("--approval-token", help="required exact token for discovery-run mode")
    parser.add_argument(
        "--approve-discovery-run",
        action="store_true",
        help="required explicit flag for discovery-run mode",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = repo_root()
    payload: dict[str, Any]
    try:
        queue_path = _as_path(root, args.queue)
        log_root = _as_path(root, args.log_root) if args.log_root else None
        payload = run_queue(
            queue_path=queue_path,
            root=root,
            mode_override=args.mode,
            approval_token=args.approval_token,
            approve_discovery_run=args.approve_discovery_run,
            log_root_override=log_root,
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["status"] == "QUEUE_COMPLETED" else 1
    except QueueError as exc:
        payload = {"status": "FAIL", "failure": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive fail-closed path.
        payload = {"status": "FAIL", "failure": f"unexpected error: {type(exc).__name__}: {exc}"}
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
