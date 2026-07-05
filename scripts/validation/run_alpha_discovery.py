#!/usr/bin/env python3
"""Guarded batch runner for bounded alpha discovery steps.

The runner is intentionally conservative. It can preflight a candidate, run
source tests, draft an approval packet, or execute one explicitly approved
discovery-smoke command. It does not advance through downstream research gates.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ALLOWED_MODES = {
    "preflight",
    "source-tests",
    "discovery-packet",
    "discovery-run",
    "review",
}
DEFAULT_REGISTRY = Path("manifests/target_hypotheses/registry.json")
DEFAULT_TRIAL_STATUSES = Path("manifests/target_hypotheses/trial_statuses.jsonl")
DISCOVERY_MODULE_PREFIX = "scripts.phase9_research."
REQUIRED_CONTRACT_FIELDS = (
    "payoff_basis",
    "entry_rule",
    "exit_or_capture_rule",
    "horizon_bars",
    "cost_threshold_source",
    "required_compatible_policy",
    "compatible_policy_evaluation_basis",
)
FORBIDDEN_BY_DEFAULT = (
    "confirmation smoke",
    "locked smoke",
    "WFA/modeling",
    "Phase 8 diagnostics",
    "tuning",
    "promotion",
    "registry/status mutation",
    "staging",
    "commit",
    "push",
    "paper trading",
    "live trading",
)


class RunnerError(RuntimeError):
    """Raised when the guarded runner must fail closed."""


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
    return dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def load_config(config_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunnerError(f"missing config: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise RunnerError(f"invalid config JSON: {config_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RunnerError("config must be a JSON object")
    return payload


def _require_string(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RunnerError(f"config field {key!r} is required")
    return value.strip()


def validate_runner_config(config: dict[str, Any], *, mode: str) -> None:
    if mode not in ALLOWED_MODES:
        raise RunnerError(f"unsupported mode {mode!r}; expected one of {sorted(ALLOWED_MODES)}")
    if config.get("template") is True:
        raise RunnerError("config is marked template=true; copy it and fill real candidate values first")
    _require_string(config, "hypothesis_id")
    _require_string(config, "market")
    _require_string(config, "profile")
    _require_string(config, "stage")
    timeout = config.get("timeout_seconds")
    if not isinstance(timeout, int) or timeout <= 0:
        raise RunnerError("timeout_seconds must be a positive integer")
    validate_target_policy_contract(config.get("target_policy_contract"))
    if mode in {"source-tests", "discovery-packet", "discovery-run"}:
        validate_source_test_commands(config.get("source_test_commands", []))
    if mode in {"discovery-packet", "discovery-run"}:
        validate_discovery_command(config.get("discovery_command"), _require_string(config, "hypothesis_id"))


def validate_target_policy_contract(contract: Any) -> None:
    if not isinstance(contract, dict):
        raise RunnerError("target_policy_contract is required")
    missing = [field for field in REQUIRED_CONTRACT_FIELDS if field not in contract]
    if missing:
        raise RunnerError(f"target_policy_contract missing fields: {missing}")
    compatible = contract.get("compatible_policy_evaluation_basis")
    if not isinstance(compatible, list) or not all(isinstance(item, str) for item in compatible):
        raise RunnerError("target_policy_contract.compatible_policy_evaluation_basis must be a string list")
    required = str(contract.get("required_compatible_policy", ""))
    if required and required not in compatible:
        raise RunnerError("required_compatible_policy must appear in compatible_policy_evaluation_basis")
    payoff_basis = str(contract.get("payoff_basis"))
    if payoff_basis == "path_favorable_excursion" and "fixed_horizon_exit" in compatible:
        raise RunnerError("path-favorable targets cannot declare fixed_horizon_exit as compatible evidence")


def validate_source_test_commands(commands: Any) -> None:
    if not isinstance(commands, list) or not commands:
        raise RunnerError("source_test_commands must contain at least one pytest command")
    for command in commands:
        if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
            raise RunnerError("each source test command must be a string list")
        if command[:3] != ["python", "-m", "pytest"]:
            raise RunnerError(f"source test command is not an approved pytest command: {command}")
        forbidden = {"data", "reports", "models", "--lf", "--ff"}
        if any(part in forbidden for part in command):
            raise RunnerError(f"source test command includes forbidden broad/generated scope: {command}")


def validate_discovery_command(command: Any, hypothesis_id: str) -> None:
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        raise RunnerError("discovery_command must be a string list")
    if len(command) < 3 or command[0:2] != ["python", "-m"]:
        raise RunnerError("discovery_command must start with python -m")
    if not command[2].startswith(DISCOVERY_MODULE_PREFIX):
        raise RunnerError("discovery_command must call a scripts.phase9_research module")
    if "--hypothesis-id" not in command:
        raise RunnerError("discovery_command must include --hypothesis-id")
    index = command.index("--hypothesis-id")
    if index + 1 >= len(command) or command[index + 1] != hypothesis_id:
        raise RunnerError("discovery_command --hypothesis-id must match config hypothesis_id")
    if "--stage" not in command or command[command.index("--stage") + 1] != "discovery":
        raise RunnerError("discovery_command must be stage discovery")
    if "--folds" not in command:
        raise RunnerError("discovery_command must declare bounded folds")


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            text=True,
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except Exception:
        process.kill()


def _run_capture(argv: list[str], *, cwd: Path, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    creationflags = 0
    start_new_session = sys.platform != "win32"
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        argv,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
        start_new_session=start_new_session,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        timeout_exc = subprocess.TimeoutExpired(exc.cmd or argv, exc.timeout, output=stdout, stderr=stderr)
        raise timeout_exc from exc
    return subprocess.CompletedProcess(argv, process.returncode, stdout=stdout, stderr=stderr)


def _read_registry(root: Path, registry_path: Path) -> dict[str, Any]:
    path = _as_path(root, registry_path)
    if not path.exists():
        raise RunnerError(f"missing target registry: {_relative(root, path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RunnerError(f"invalid target registry JSON: {_relative(root, path)}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("hypotheses"), list):
        raise RunnerError("target registry must contain a hypotheses list")
    return payload


def _registry_entry(registry: dict[str, Any], hypothesis_id: str) -> dict[str, Any]:
    matches = [
        item
        for item in registry["hypotheses"]
        if isinstance(item, dict) and item.get("target_hypothesis_id") == hypothesis_id
    ]
    if len(matches) != 1:
        raise RunnerError(f"expected exactly one registry entry for {hypothesis_id!r}; found {len(matches)}")
    return matches[0]


def _read_trial_statuses(root: Path, path: Path, hypothesis_id: str) -> list[dict[str, Any]]:
    resolved = _as_path(root, path)
    if not resolved.exists():
        raise RunnerError(f"missing trial-status file: {_relative(root, resolved)}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RunnerError(f"invalid trial-status JSONL line {line_number}: {exc}") from exc
        if payload.get("hypothesis_id") == hypothesis_id:
            rows.append(payload)
    return rows


def _git_status(root: Path) -> list[str]:
    result = _run_capture(["git", "status", "--short"], cwd=root)
    if result.returncode != 0:
        raise RunnerError(f"git status failed: {result.stderr.strip() or result.stdout.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def _path_is_ignored(root: Path, path: Path) -> bool:
    result = _run_capture(["git", "check-ignore", "-q", _relative(root, path)], cwd=root)
    return result.returncode == 0


def _expected_outputs(config: dict[str, Any], root: Path) -> list[Path]:
    outputs = config.get("expected_outputs", [])
    if not isinstance(outputs, list) or not all(isinstance(item, str) for item in outputs):
        raise RunnerError("expected_outputs must be a string list")
    return [_as_path(root, item) for item in outputs]


def _candidate_decision_flags(decision: Any) -> dict[str, Any]:
    decision_text = decision if isinstance(decision, str) and decision else None
    return {
        "candidate_decision": decision_text,
        "candidate_passed": decision_text == "DISCOVERY_PASS",
        "candidate_stopped": bool(decision_text and decision_text.startswith("STOP_")),
        "target_smoke_is_tradability_proof": False,
    }


def _read_discovery_json_summaries(root: Path, outputs: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    summaries: list[dict[str, Any]] = []
    failures: list[str] = []
    for path in outputs:
        if path.suffix.lower() != ".json" or not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{_relative(root, path)}: invalid JSON: {exc}")
            continue
        decision_flags = _candidate_decision_flags(payload.get("decision"))
        summaries.append(
            {
                "path": _relative(root, path),
                "decision": payload.get("decision"),
                "failure_count": payload.get("failure_count"),
                "stage": payload.get("stage"),
                **decision_flags,
            }
        )
    return summaries, failures


def _verify_expected_outputs(
    config: dict[str, Any],
    *,
    root: Path,
    require_absent: bool,
) -> dict[str, Any]:
    stale: list[str] = []
    not_ignored: list[str] = []
    present: list[str] = []
    for output in _expected_outputs(config, root):
        rel = _relative(root, output)
        if output.exists():
            present.append(rel)
            if require_absent:
                stale.append(rel)
        if not _path_is_ignored(root, output):
            not_ignored.append(rel)
    if stale:
        raise RunnerError(f"expected outputs already exist; stop before overwrite: {stale}")
    if not_ignored:
        raise RunnerError(f"expected generated outputs are not ignored by git: {not_ignored}")
    return {"expected_output_count": len(_expected_outputs(config, root)), "present_outputs": present}


def preflight(
    config: dict[str, Any],
    *,
    root: Path,
    require_outputs_absent: bool = True,
    require_candidate_ready: bool = True,
) -> dict[str, Any]:
    hypothesis_id = _require_string(config, "hypothesis_id")
    registry_path = Path(config.get("target_registry", str(DEFAULT_REGISTRY)))
    trial_statuses_path = Path(config.get("target_trial_statuses", str(DEFAULT_TRIAL_STATUSES)))
    for required in ("AGENTS.md", "PROJECT_OUTLINE.md", "CODEX_HANDOFF.md"):
        if not (root / required).exists():
            raise RunnerError(f"missing repo coordination file: {required}")
    registry = _read_registry(root, registry_path)
    entry = _registry_entry(registry, hypothesis_id)
    if require_candidate_ready and entry.get("status") != "CANDIDATE":
        raise RunnerError(
            f"registry status for {hypothesis_id!r} is {entry.get('status')!r}; "
            "discovery runner requires a CANDIDATE"
        )
    if require_candidate_ready and bool(entry.get("wfa_allowed")):
        raise RunnerError("discovery runner requires wfa_allowed=false before target smoke")
    trials = _read_trial_statuses(root, trial_statuses_path, hypothesis_id)
    discovery_trials = [
        item
        for item in trials
        if "discovery" in str(item.get("stage", "")).lower()
        or "discovery" in str(item.get("trial_id", "")).lower()
    ]
    if require_candidate_ready and discovery_trials:
        raise RunnerError("trial-status evidence already contains discovery work for this hypothesis")
    outputs = _verify_expected_outputs(config, root=root, require_absent=require_outputs_absent)
    status_lines = _git_status(root)
    return {
        "status": "PREFLIGHT_PASS",
        "hypothesis_id": hypothesis_id,
        "registry_status": entry.get("status"),
        "wfa_allowed": bool(entry.get("wfa_allowed")),
        "trial_status_rows": len(trials),
        "discovery_trial_status_rows": len(discovery_trials),
        "git_status_line_count": len(status_lines),
        "dirty_worktree_accepted_for_review": bool(status_lines),
        **outputs,
        "target_policy_contract_payoff_basis": config["target_policy_contract"].get("payoff_basis"),
        "target_smoke_is_tradability_proof": False,
    }


def run_source_tests(config: dict[str, Any], *, root: Path) -> dict[str, Any]:
    commands = config.get("source_test_commands", [])
    results = []
    for command in commands:
        completed = _run_capture(command, cwd=root, timeout=int(config["timeout_seconds"]))
        results.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
                "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
            }
        )
        if completed.returncode != 0:
            raise RunnerError(f"source test command failed: {command}")
    return {"status": "SOURCE_TESTS_PASS", "command_count": len(results), "commands": results}


def approval_packet(config: dict[str, Any], *, root: Path) -> dict[str, Any]:
    expected_outputs = [_relative(root, path) for path in _expected_outputs(config, root)]
    forbidden = config.get("forbidden_actions") or list(FORBIDDEN_BY_DEFAULT)
    return {
        "status": "DISCOVERY_PACKET_READY",
        "hypothesis_id": config["hypothesis_id"],
        "exact_command": config["discovery_command"],
        "timeout_seconds": config["timeout_seconds"],
        "expected_outputs": expected_outputs,
        "pass_fail_review_required": [
            "read generated JSON first",
            "cross-check generated MD once",
            "do not rely only on process exit code",
            "do not treat target smoke as tradability proof",
        ],
        "hard_gates": {
            "target_policy_contract_required": True,
            "target_smoke_is_tradability_proof": False,
            "policy_aligned_economics_required_later": True,
        },
        "forbidden_actions": forbidden,
        "stop_condition": "stop after one bounded discovery smoke and one JSON/MD review",
        "approval_required": {
            "flag": "--approve-discovery-run",
            "token": config["approval_token"],
        },
    }


def run_discovery_once(config: dict[str, Any], *, root: Path, approval_token: str | None) -> dict[str, Any]:
    if approval_token != config.get("approval_token"):
        raise RunnerError("discovery-run requires the exact configured approval token")
    command = list(config["discovery_command"])
    completed = _run_capture(command, cwd=root, timeout=int(config["timeout_seconds"]))
    output_paths = _expected_outputs(config, root)
    missing = [_relative(root, path) for path in output_paths if not path.exists()]
    json_summaries, json_read_failures = _read_discovery_json_summaries(root, output_paths)
    decision_flags = _candidate_decision_flags(
        json_summaries[0]["decision"] if json_summaries else None
    )
    if completed.returncode != 0:
        status = "DISCOVERY_RUN_COMMAND_FAILED"
    elif missing or json_read_failures or not json_summaries:
        status = "DISCOVERY_RUN_REVIEW_REQUIRED"
    elif decision_flags["candidate_passed"]:
        status = "DISCOVERY_RUN_CANDIDATE_DISCOVERY_PASS"
    elif decision_flags["candidate_stopped"]:
        status = "DISCOVERY_RUN_CANDIDATE_STOPPED"
    else:
        status = "DISCOVERY_RUN_REVIEW_REQUIRED"
    return {
        "status": status,
        "command": command,
        "returncode": completed.returncode,
        "command_succeeded": completed.returncode == 0,
        "missing_outputs": missing,
        "json_summaries": json_summaries,
        "json_read_failures": json_read_failures,
        **decision_flags,
        "stdout_tail": "\n".join(completed.stdout.splitlines()[-40:]),
        "stderr_tail": "\n".join(completed.stderr.splitlines()[-40:]),
        "rerun_allowed": False,
    }


def review_outputs(config: dict[str, Any], *, root: Path) -> dict[str, Any]:
    outputs = _expected_outputs(config, root)
    json_outputs = [path for path in outputs if path.suffix.lower() == ".json"]
    md_outputs = [path for path in outputs if path.suffix.lower() == ".md"]
    if not json_outputs:
        raise RunnerError("review mode requires at least one expected JSON output")
    missing = [_relative(root, path) for path in outputs if not path.exists()]
    if missing:
        raise RunnerError(f"review outputs are missing: {missing}")
    summaries, json_read_failures = _read_discovery_json_summaries(root, json_outputs)
    if json_read_failures:
        raise RunnerError(f"review JSON read failures: {json_read_failures}")
    md_checks = []
    for path in md_outputs:
        text = path.read_text(encoding="utf-8")
        md_checks.append(
            {
                "path": _relative(root, path),
                "has_do_not_do": "Do Not" in text or "do not" in text,
                "line_count": len(text.splitlines()),
            }
        )
    return {
        "status": "REVIEW_COMPLETE",
        "json_summaries": summaries,
        "md_checks": md_checks,
    }


def _write_log(log_root: Path | None, payload: dict[str, Any]) -> str | None:
    if log_root is None:
        return None
    log_root.mkdir(parents=True, exist_ok=True)
    path = log_root / f"alpha_discovery_{_utc_stamp()}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def run_mode(config: dict[str, Any], *, root: Path, mode: str, approval_token: str | None) -> dict[str, Any]:
    validate_runner_config(config, mode=mode)
    if mode == "review":
        preflight_result = preflight(
            config,
            root=root,
            require_outputs_absent=False,
            require_candidate_ready=False,
        )
        review = review_outputs(config, root=root)
        return {"status": review["status"], "preflight": preflight_result, "review": review}

    preflight_result = preflight(config, root=root, require_outputs_absent=True)
    if mode == "preflight":
        return {"status": preflight_result["status"], "preflight": preflight_result}
    if mode == "source-tests":
        source = run_source_tests(config, root=root)
        return {"status": source["status"], "preflight": preflight_result, "source_tests": source}
    if mode == "discovery-packet":
        packet = approval_packet(config, root=root)
        return {"status": packet["status"], "preflight": preflight_result, "packet": packet}
    if mode == "discovery-run":
        discovery = run_discovery_once(config, root=root, approval_token=approval_token)
        review = None
        if not discovery["missing_outputs"]:
            review = review_outputs(config, root=root)
        return {
            "status": discovery["status"],
            "preflight": preflight_result,
            "discovery": discovery,
            "review": review,
        }
    raise RunnerError(f"unhandled mode {mode}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="JSON runner config to load")
    parser.add_argument("--mode", choices=sorted(ALLOWED_MODES), help="override runner_mode in config")
    parser.add_argument("--log-root", help="ignored log directory for JSON run summaries")
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
    log_root = _as_path(root, args.log_root) if args.log_root else None
    payload: dict[str, Any]
    try:
        config_path = _as_path(root, args.config)
        config = load_config(config_path)
        mode = args.mode or str(config.get("runner_mode", "preflight"))
        if mode == "discovery-run" and not args.approve_discovery_run:
            raise RunnerError("discovery-run requires --approve-discovery-run")
        payload = {
            "status": "RUNNER_COMPLETED",
            "runner_completed": True,
            "mode": mode,
            "config": _relative(root, config_path),
            "result": run_mode(
                config,
                root=root,
                mode=mode,
                approval_token=args.approval_token if args.approve_discovery_run else None,
            ),
        }
        log_path = _write_log(log_root, payload)
        if log_path:
            payload["log_path"] = _relative(root, Path(log_path))
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except subprocess.TimeoutExpired as exc:
        payload = {"status": "FAIL", "failure": f"command timed out after {exc.timeout} seconds"}
    except RunnerError as exc:
        payload = {"status": "FAIL", "failure": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive fail-closed path.
        payload = {"status": "FAIL", "failure": f"unexpected error: {type(exc).__name__}: {exc}"}
    log_path = _write_log(log_root, payload)
    if log_path:
        payload["log_path"] = _relative(root, Path(log_path))
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
