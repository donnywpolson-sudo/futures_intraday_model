#!/usr/bin/env python3
"""Read-only model-trust enforcement gate for broad research or trading actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_RUN_ID = "tier1_core_phase6_full_predictions_20260706"
DEFAULT_MATRIX_PATH = (
    Path("reports")
    / "model_trust_audit"
    / "alpha_evidence_gap_matrix_20260709T034313Z"
    / "alpha_evidence_gap_matrix.json"
)
DEFAULT_CLOSEOUT_PATH = (
    Path("reports")
    / "model_trust_audit"
    / "alpha_evidence_completion_closeout_20260709T035929Z"
    / "alpha_evidence_completion_closeout.json"
)

ACTION_EVIDENCE_WORK = "evidence-work"
ACTION_PREDECLARED_PLAN = "predeclared-research-plan"

EXECUTION_ACTIONS = {
    "target-discovery": "target_discovery",
    "source-tests": "source_tests",
    "wfa-modeling": "wfa_modeling",
    "phase8-refresh": "phase8_refresh",
    "promotion": "promotion",
    "artifact-freeze": "artifact_freeze",
    "final-holdout": "final_holdout",
    "paper-live": "paper",
    "provider-downloads": "provider_downloads",
    "cleanup": "cleanup",
    "staging-commit-push": "staging_commit_push",
    "rescue-tuning": "rescue_tuning",
}

INTENDED_ACTIONS = (
    ACTION_EVIDENCE_WORK,
    ACTION_PREDECLARED_PLAN,
    *EXECUTION_ACTIONS.keys(),
)

CURRENT_LINE_CLOSED_VERDICT = "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
PAUSE_MATRIX_VERDICT = "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE"


class ModelTrustGateError(RuntimeError):
    """Raised when evidence inputs cannot be evaluated."""


def _resolve(repo_root: Path, path: Path | str | None) -> Path | None:
    if path is None:
        return None
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _relative(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "file missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"read error: {exc}"
    if not isinstance(payload, dict):
        return None, "JSON root is not an object"
    return payload, None


def _file_sha256(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_short_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _git_dirty_paths(repo_root: Path) -> tuple[list[str], str | None]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return [], f"git status failed: {exc}"
    if result.returncode != 0:
        return [], (result.stderr or "git status returned nonzero").strip()
    return [line for line in result.stdout.splitlines() if line.strip()], None


def _source_summary(repo_root: Path, path: Path | None, payload: Mapping[str, Any] | None, error: str | None) -> dict[str, Any]:
    return {
        "path": _relative(repo_root, path),
        "available": payload is not None and error is None,
        "read_error": error,
        "sha256": _file_sha256(path),
    }


def _non_approval_for_action(closeout: Mapping[str, Any], action: str) -> bool:
    if action == "paper-live":
        non_approval = closeout.get("non_approval")
        if not isinstance(non_approval, Mapping):
            return False
        return non_approval.get("paper") is True and non_approval.get("live") is True
    field = EXECUTION_ACTIONS[action]
    non_approval = closeout.get("non_approval")
    if not isinstance(non_approval, Mapping):
        return False
    return non_approval.get(field) is True


def _allowed_from_closeout(
    closeout: Mapping[str, Any],
    *,
    intended_action: str,
    blockers: list[str],
) -> bool:
    run_id = closeout.get("run_id")
    if run_id != DEFAULT_RUN_ID:
        blockers.append(f"closeout run_id mismatch: {run_id!r}")
    if closeout.get("verdict") == CURRENT_LINE_CLOSED_VERDICT:
        blockers.append("current model line is closed by alpha evidence closeout")
    if closeout.get("modeling_pause_required") is True:
        blockers.append("modeling pause is required by closeout")
    if closeout.get("promotion_allowed") is False:
        blockers.append("promotion is explicitly disallowed by closeout")

    if intended_action in {ACTION_EVIDENCE_WORK, ACTION_PREDECLARED_PLAN}:
        if closeout.get("future_evidence_work_allowed") is True:
            return True
        blockers.append("future evidence work is not allowed by closeout")
        return False

    if intended_action in EXECUTION_ACTIONS:
        allowed = _non_approval_for_action(closeout, intended_action)
        if not allowed:
            blockers.append(f"{intended_action} is not approved by closeout non_approval policy")
        return allowed and not blockers

    blockers.append(f"unknown intended action: {intended_action}")
    return False


def _allowed_from_matrix(
    matrix: Mapping[str, Any] | None,
    matrix_error: str | None,
    *,
    intended_action: str,
    blockers: list[str],
) -> bool:
    if matrix is None:
        blockers.append(f"alpha evidence matrix unavailable: {matrix_error}")
        return intended_action == ACTION_EVIDENCE_WORK
    if matrix.get("run_id") != DEFAULT_RUN_ID:
        blockers.append(f"matrix run_id mismatch: {matrix.get('run_id')!r}")
    alpha_ready = matrix.get("alpha_evidence_ready") is True
    if not alpha_ready:
        blockers.append("alpha evidence matrix is not ready")
    if matrix.get("verdict") == PAUSE_MATRIX_VERDICT:
        blockers.append("matrix verdict requires modeling pause")

    if intended_action == ACTION_EVIDENCE_WORK:
        return True
    if intended_action == ACTION_PREDECLARED_PLAN:
        return alpha_ready

    blockers.append(f"{intended_action} requires a passing closeout or separate bounded approval")
    return False


def enforce_model_trust_gate(
    *,
    repo_root: Path,
    intended_action: str,
    closeout_path: Path = DEFAULT_CLOSEOUT_PATH,
    matrix_path: Path = DEFAULT_MATRIX_PATH,
    require_clean_worktree: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    resolved_closeout = _resolve(repo_root, closeout_path)
    resolved_matrix = _resolve(repo_root, matrix_path)
    if resolved_closeout is None or resolved_matrix is None:
        raise ModelTrustGateError("closeout and matrix paths are required")

    closeout, closeout_error = _read_json(resolved_closeout)
    matrix, matrix_error = _read_json(resolved_matrix)
    dirty_paths, dirty_error = _git_dirty_paths(repo_root)
    blockers: list[str] = []
    warnings: list[str] = []

    if dirty_error:
        warnings.append(f"could not inspect git status: {dirty_error}")
    if require_clean_worktree and dirty_paths:
        blockers.append("worktree is dirty and --require-clean-worktree was set")

    if closeout is not None:
        allowed = _allowed_from_closeout(
            closeout,
            intended_action=intended_action,
            blockers=blockers,
        )
        evidence_source = "alpha_evidence_completion_closeout"
    else:
        warnings.append(f"alpha evidence closeout unavailable: {closeout_error}")
        allowed = _allowed_from_matrix(
            matrix,
            matrix_error,
            intended_action=intended_action,
            blockers=blockers,
        )
        evidence_source = "alpha_evidence_gap_matrix"

    if require_clean_worktree and dirty_paths:
        allowed = False
    if blockers and intended_action not in {ACTION_EVIDENCE_WORK, ACTION_PREDECLARED_PLAN}:
        allowed = False

    status = "ALLOW_EVIDENCE_WORK_ONLY" if allowed else "BLOCKED_BY_MODEL_TRUST_GATE"
    if allowed and intended_action not in {ACTION_EVIDENCE_WORK, ACTION_PREDECLARED_PLAN}:
        status = "ALLOW_REQUESTED_ACTION"

    return {
        "status": status,
        "allowed": allowed,
        "intended_action": intended_action,
        "evidence_source": evidence_source,
        "blockers": blockers,
        "warnings": warnings,
        "allowed_without_separate_approval": [
            ACTION_EVIDENCE_WORK,
            ACTION_PREDECLARED_PLAN,
        ],
        "forbidden_without_separate_approval": sorted(EXECUTION_ACTIONS),
        "repo": {
            "path": repo_root.as_posix(),
            "git_head": _git_short_head(repo_root),
            "dirty": bool(dirty_paths),
            "dirty_paths": dirty_paths,
        },
        "source_evidence": {
            "closeout": _source_summary(repo_root, resolved_closeout, closeout, closeout_error),
            "matrix": _source_summary(repo_root, resolved_matrix, matrix, matrix_error),
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--closeout", default=DEFAULT_CLOSEOUT_PATH.as_posix())
    parser.add_argument("--matrix", default=DEFAULT_MATRIX_PATH.as_posix())
    parser.add_argument("--intended-action", choices=INTENDED_ACTIONS, required=True)
    parser.add_argument("--require-clean-worktree", action="store_true")
    parser.add_argument("--fail-on-blocked", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = enforce_model_trust_gate(
        repo_root=Path(args.repo_root),
        closeout_path=Path(args.closeout),
        matrix_path=Path(args.matrix),
        intended_action=args.intended_action,
        require_clean_worktree=args.require_clean_worktree,
    )
    if args.print_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"{result['status']} model trust gate: "
            f"action={result['intended_action']} "
            f"allowed={result['allowed']} "
            f"blockers={len(result['blockers'])}"
        )
    if args.fail_on_blocked and not result["allowed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
