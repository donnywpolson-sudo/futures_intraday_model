#!/usr/bin/env python3
"""Interactive Phase 9 alpha-discovery wizard."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from scripts.phase9_research.es_30m_target_smoke_harness import TARGET_SPECS
from scripts.validation import alpha_discovery_autopsy as autopsy
from scripts.validation import generate_alpha_discovery_candidates as generator
from scripts.validation import run_alpha_discovery_queue as queue_runner


SAFE_REPORT_STAMP = autopsy.SAFE_REPORT_STAMP
APPROVAL_PHRASE = "RUN_PHASE9_DISCOVERY_ONCE"
DEFAULT_DISCOVERY_MAX_CANDIDATES = 10
ABSOLUTE_DISCOVERY_MAX_CANDIDATES = 100
DISCOVERY_TIMEOUT_SECONDS = 900
DISCOVERY_ACKNOWLEDGEMENT = "I understand this cannot promote, tune, deploy, or prove alpha."
SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class WizardError(RuntimeError):
    """Raised when the wizard must stop before unsafe work."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise WizardError(f"missing launcher file: {path}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(_read_bytes(path)).hexdigest()


def _quote_ps(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def launcher_template_path(root: Path) -> Path:
    return root / "RUN_ALPHA_DISCOVERY.bat"


def default_desktop_launcher_path(root: Path) -> Path:
    return root.parent / "RUN_ALPHA_DISCOVERY.bat"


def _remediation(root: Path, launcher_path: Path, template_path: Path) -> dict[str, str]:
    review_command = (
        "Compare-Object "
        f"(Get-Content -Raw -LiteralPath {_quote_ps(launcher_path)}) "
        f"(Get-Content -Raw -LiteralPath {_quote_ps(template_path)})"
    )
    replacement_command = (
        "Copy-Item "
        f"-LiteralPath {_quote_ps(template_path)} "
        f"-Destination {_quote_ps(launcher_path)} -Force"
    )
    return {
        "review_command": review_command,
        "replacement_warning": "OVERWRITES DESKTOP LAUNCHER - run only after review.",
        "replacement_command": replacement_command,
    }


def launcher_self_check(*, root: Path, launcher_path: Path) -> dict[str, Any]:
    template_path = launcher_template_path(root)
    template_text = _read_bytes(template_path).decode("utf-8", errors="replace")
    launcher_text = _read_bytes(launcher_path).decode("utf-8", errors="replace")
    template_hash = _sha256(template_path)
    launcher_hash = _sha256(launcher_path)
    required_markers = (
        "scripts.validation.run_alpha_discovery_wizard",
        "--self-check",
        "--generate-candidates",
        "scripts.validation.run_alpha_discovery_queue",
        "scripts.validation.run_alpha_discovery",
    )
    missing_markers = [marker for marker in required_markers if marker not in template_text]
    if missing_markers:
        raise WizardError(f"launcher template is missing required route markers: {missing_markers}")
    if template_hash != launcher_hash or template_text != launcher_text:
        remediation = _remediation(root, launcher_path, template_path)
        raise WizardError(
            "Desktop launcher self-check failed: content hash mismatch. "
            f"launcher_path={launcher_path}; template_path={template_path}; "
            f"expected_hash={template_hash}; detected_hash={launcher_hash}; "
            f"review_command={remediation['review_command']}; "
            f"{remediation['replacement_warning']} "
            f"replacement_command={remediation['replacement_command']}"
        )
    return {
        "status": "LAUNCHER_SELF_CHECK_PASS",
        "launcher_path": str(launcher_path),
        "template_path": str(template_path),
        "hash": template_hash,
        "no_arg_route": "scripts.validation.run_alpha_discovery_wizard",
        "static_check_only": True,
    }


def _safe_token(value: str, *, field: str) -> str:
    value = value.strip()
    if not SAFE_TOKEN_RE.fullmatch(value):
        raise WizardError(f"{field} must match {SAFE_TOKEN_RE.pattern!r}")
    return value


def _ready_candidates(root: Path) -> list[str]:
    ready: list[str] = []
    for candidate_id in sorted(TARGET_SPECS):
        try:
            generator._validate_canonical_candidate(candidate_id, root=root)
        except generator.GeneratorError:
            continue
        ready.append(candidate_id)
    return ready


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WizardError(f"missing queue file for discovery approval: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WizardError(f"invalid queue JSON for discovery approval: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WizardError("queue file for discovery approval must be a JSON object")
    return payload


def _spec_for_batch(*, batch_id: str, candidates: list[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "batch_id": batch_id,
        "template_config": "configs/alpha_discovery_runner.example.json",
        "output_config_dir": f"configs/alpha_discovery_generated/{batch_id}",
        "output_queue": f"configs/alpha_discovery_generated/alpha_discovery_queue.{batch_id}.json",
        "max_candidates": generator.HARD_MAX_CANDIDATES,
        "candidates": [
            {
                "id": candidate_id,
                "run": f"{batch_id}_{candidate_id}",
            }
            for candidate_id in candidates
        ],
    }


def _select_candidates(ready: list[str]) -> list[str]:
    print("Ready canonical candidates:")
    for candidate_id in ready:
        print(f"  {candidate_id}")
    selection = input("Select candidates: all, comma-separated IDs, or cancel: ").strip()
    if selection.lower() == "cancel":
        raise WizardError("cancelled by user")
    if selection.lower() == "all":
        return ready
    selected = [item.strip() for item in selection.split(",") if item.strip()]
    unknown = [item for item in selected if item not in ready]
    if unknown:
        raise WizardError(f"selected candidates are not canonical-ready: {unknown}")
    if not selected:
        raise WizardError("no candidates selected")
    return selected


def _approved_queue_path(root: Path, batch_id: str) -> Path:
    return root / "configs" / "alpha_discovery_generated" / f"alpha_discovery_queue.{batch_id}.approved.json"


def _approved_queue_copy(*, root: Path, queue_path: Path, batch_id: str) -> Path:
    approved_path = _approved_queue_path(root, batch_id)
    if approved_path.exists():
        raise WizardError(f"approved queue already exists; refusing overwrite: {_relative(root, approved_path)}")
    payload = copy.deepcopy(_read_json(queue_path))
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise WizardError("queue candidates must contain at least one entry before discovery approval")
    for entry in candidates:
        if not isinstance(entry, dict):
            raise WizardError("queue candidate entries must be JSON objects before discovery approval")
        entry["approved"] = True
    payload["runner_mode"] = "discovery-run"
    payload["log_root"] = f"logs/alpha_discovery_queue/{batch_id}"
    payload["discovery_approval"] = {
        "approval_phrase": APPROVAL_PHRASE,
        "candidate_count": len(candidates),
        "max_discovery_candidates": min(DEFAULT_DISCOVERY_MAX_CANDIDATES, len(candidates)),
        "timeout_cap_seconds": DISCOVERY_TIMEOUT_SECONDS,
        "approved_by_wizard": True,
    }
    _write_json(approved_path, payload)
    return approved_path


def _discovery_command(*, root: Path, batch_id: str, approved_queue_path: Path, candidate_count: int) -> list[str]:
    return [
        str(default_desktop_launcher_path(root)),
        "--queue",
        _relative(root, approved_queue_path),
        "--mode",
        "discovery-run",
        "--approve-discovery-run",
        "--approval-token",
        APPROVAL_PHRASE,
        "--max-discovery-candidates",
        str(min(DEFAULT_DISCOVERY_MAX_CANDIDATES, candidate_count)),
        "--log-root",
        f"logs/alpha_discovery_queue/{batch_id}",
    ]


def _print_discovery_prompt(
    *,
    root: Path,
    batch_id: str,
    approved_queue_path: Path,
    candidate_count: int,
) -> list[str]:
    command = _discovery_command(
        root=root,
        batch_id=batch_id,
        approved_queue_path=approved_queue_path,
        candidate_count=candidate_count,
    )
    print("Optional bounded discovery-run")
    print(f"Candidate count: {candidate_count}")
    print(f"Default discovery candidate bound: {DEFAULT_DISCOVERY_MAX_CANDIDATES}")
    print(f"Absolute discovery candidate cap: {ABSOLUTE_DISCOVERY_MAX_CANDIDATES}")
    print(f"Timeout cap seconds: {DISCOVERY_TIMEOUT_SECONDS}")
    print(f"Logs: logs/alpha_discovery_queue/{batch_id}")
    print(f"Reports: reports/pipeline_audit/alpha_discovery/{batch_id}")
    print("Stop condition: infrastructure failure, timeout, missing JSON, nonzero wrapper error, unapproved output path, or malformed candidate decision.")
    print("Forbidden actions: WFA, Phase 8, promotion, deployment evidence, registry/status mutation, staging, commits, pushes.")
    print("Exact command:")
    print(" ".join(command))
    return command


def _maybe_run_discovery(
    *,
    root: Path,
    batch_id: str,
    queue_path: Path,
    candidate_count: int,
    generation: dict[str, Any],
) -> dict[str, Any] | None:
    if candidate_count > DEFAULT_DISCOVERY_MAX_CANDIDATES:
        print(
            f"Discovery-run skipped: candidate count {candidate_count} exceeds default bound "
            f"{DEFAULT_DISCOVERY_MAX_CANDIDATES}."
        )
        return None
    choice = input("Run optional bounded discovery now? Type discovery to continue, or skip: ").strip()
    if choice.lower() != "discovery":
        return None
    approved_queue_path = _approved_queue_path(root, batch_id)
    _print_discovery_prompt(
        root=root,
        batch_id=batch_id,
        approved_queue_path=approved_queue_path,
        candidate_count=candidate_count,
    )
    acknowledgement = input(f"Type exact acknowledgement [{DISCOVERY_ACKNOWLEDGEMENT}]: ").strip()
    if acknowledgement != DISCOVERY_ACKNOWLEDGEMENT:
        raise WizardError("discovery acknowledgement was not provided")
    approval_phrase = input(f"Type approval phrase [{APPROVAL_PHRASE}]: ").strip()
    if approval_phrase != APPROVAL_PHRASE:
        raise WizardError("discovery approval phrase did not match")
    approved_queue_path = _approved_queue_copy(root=root, queue_path=queue_path, batch_id=batch_id)
    discovery = queue_runner.run_queue(
        queue_path=approved_queue_path,
        root=root,
        mode_override="discovery-run",
        approval_token=APPROVAL_PHRASE,
        approve_discovery_run=True,
        log_root_override=root / "logs" / "alpha_discovery_queue" / batch_id,
        max_discovery_candidates=min(DEFAULT_DISCOVERY_MAX_CANDIDATES, candidate_count),
    )
    discovery_autopsy = autopsy.write_autopsy(
        root=root,
        batch_id=batch_id,
        queue_result=discovery,
        generation_result={
            **generation,
            "approved_queue_path": _relative(root, approved_queue_path),
        },
        report_root=root / "reports" / "pipeline_audit" / "alpha_discovery_autopsy" / batch_id / "discovery",
    )
    return {
        "approved_queue_path": _relative(root, approved_queue_path),
        "command": _discovery_command(
            root=root,
            batch_id=batch_id,
            approved_queue_path=approved_queue_path,
            candidate_count=candidate_count,
        ),
        "result": {
            "status": discovery["status"],
            "summary": discovery["summary"],
        },
        "autopsy": discovery_autopsy,
    }


def run_wizard(*, root: Path, launcher_path: Path) -> dict[str, Any]:
    self_check = launcher_self_check(root=root, launcher_path=launcher_path)
    print(SAFE_REPORT_STAMP)
    print("Phase 9 Alpha Discovery Wizard")
    print("Blocked actions: no WFA, no Phase 8, no promotion, no deployment evidence, no registry/status mutation, no staging, no commits, no pushes.")
    acknowledgement = input("Type ACK to continue: ").strip()
    if acknowledgement != "ACK":
        raise WizardError("wizard acknowledgement was not provided")
    ready = _ready_candidates(root)
    if not ready:
        return {
            "status": "NO_CANONICAL_CANDIDATES",
            "launcher_self_check": self_check,
            "message": "Separate candidate registration is required first.",
        }
    selected = _select_candidates(ready)
    if len(selected) > generator.HARD_MAX_CANDIDATES:
        raise WizardError(f"selected candidates exceed hard cap {generator.HARD_MAX_CANDIDATES}")
    batch_id = _safe_token(input("Batch id: "), field="batch_id")
    spec = _spec_for_batch(batch_id=batch_id, candidates=selected)
    spec_path = root / "configs" / "alpha_discovery_wizard" / f"alpha_discovery_candidates.{batch_id}.json"
    if spec_path.exists():
        raise WizardError(f"batch spec already exists; refusing overwrite: {_relative(root, spec_path)}")
    _write_json(spec_path, spec)
    generation = generator.generate_from_spec(spec_path=spec_path, root=root)
    queue_path = root / str(generation["queue_path"])
    preflight = queue_runner.run_queue(
        queue_path=queue_path,
        root=root,
        mode_override="preflight",
        approval_token=None,
        approve_discovery_run=False,
    )
    readiness_autopsy = autopsy.write_autopsy(
        root=root,
        batch_id=batch_id,
        queue_result=preflight,
        generation_result=generation,
        report_root=root / "reports" / "pipeline_audit" / "alpha_discovery_autopsy" / batch_id / "readiness",
    )
    discovery = _maybe_run_discovery(
        root=root,
        batch_id=batch_id,
        queue_path=queue_path,
        candidate_count=int(generation["candidate_count"]),
        generation=generation,
    )
    status = "WIZARD_DISCOVERY_COMPLETE" if discovery is not None else "WIZARD_PREFLIGHT_COMPLETE"
    return {
        "status": status,
        "launcher_self_check": self_check,
        "generation": generation,
        "preflight": {
            "status": preflight["status"],
            "summary": preflight["summary"],
        },
        "readiness_autopsy": readiness_autopsy,
        "discovery": discovery,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true", help="run static launcher self-check and exit")
    parser.add_argument("--launcher-path", help="path to the launcher that invoked the wizard")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = repo_root()
    launcher_path = Path(args.launcher_path) if args.launcher_path else default_desktop_launcher_path(root)
    try:
        if args.self_check:
            payload = launcher_self_check(root=root, launcher_path=launcher_path)
        else:
            payload = run_wizard(root=root, launcher_path=launcher_path)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except (WizardError, generator.GeneratorError, queue_runner.QueueError, autopsy.AutopsyError) as exc:
        print(json.dumps({"status": "FAIL", "failure": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fail-closed path.
        payload = {"status": "FAIL", "failure": f"unexpected error: {type(exc).__name__}: {exc}"}
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
