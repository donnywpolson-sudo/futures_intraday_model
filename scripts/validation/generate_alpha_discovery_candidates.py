#!/usr/bin/env python3
"""Generate preflight-only alpha discovery candidate configs and one queue file."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from scripts.phase9_research.es_30m_target_smoke_harness import TARGET_SPECS
from scripts.validation import run_alpha_discovery as single_runner


HARD_MAX_CANDIDATES = 100
CANONICAL_REGISTRY = Path("manifests/target_hypotheses/registry.json")
CANONICAL_TRIAL_STATUSES = Path("manifests/target_hypotheses/trial_statuses.jsonl")
ID_PLACEHOLDER = "replace_with_registered_candidate_id"
RUN_PLACEHOLDER = "replace_with_bounded_run_name"
SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class GeneratorError(RuntimeError):
    """Raised when candidate generation must fail closed."""


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


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GeneratorError(f"missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GeneratorError(f"invalid {label} JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise GeneratorError(f"{label} must be a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _require_string(payload: dict[str, Any], key: str, *, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GeneratorError(f"{label} field {key!r} is required")
    return value.strip()


def _require_safe_token(value: str, *, field: str) -> None:
    if not SAFE_TOKEN_RE.fullmatch(value):
        raise GeneratorError(
            f"{field} must match {SAFE_TOKEN_RE.pattern!r}; got {value!r}"
        )


def _assert_under(root: Path, path: Path, base: Path, *, field: str) -> None:
    resolved = path.resolve()
    resolved_base = base.resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError as exc:
        rel_base = _relative(root, resolved_base)
        raise GeneratorError(f"{field} must be under {rel_base}: {_relative(root, path)}") from exc


def _assert_under_root(root: Path, path: Path, *, field: str) -> None:
    _assert_under(root, path, root, field=field)


def _assert_under_configs(root: Path, path: Path, *, field: str) -> None:
    _assert_under(root, path, root / "configs", field=field)


def _is_canonical_path(root: Path, value: str, canonical_path: Path) -> bool:
    return _as_path(root, value).resolve() == (root / canonical_path).resolve()


def _require_canonical_path(root: Path, value: Any, *, field: str, canonical_path: Path) -> None:
    if not isinstance(value, str) or not value.strip():
        raise GeneratorError(f"{field} must be a non-empty canonical path")
    if not _is_canonical_path(root, value.strip(), canonical_path):
        raise GeneratorError(
            f"{field} must be {_relative(root, root / canonical_path)}; got {value!r}"
        )


def _require_canonical_config_paths(config: dict[str, Any], *, root: Path, candidate_id: str) -> None:
    if "target_registry" in config:
        _require_canonical_path(
            root,
            config["target_registry"],
            field=f"{candidate_id} target_registry",
            canonical_path=CANONICAL_REGISTRY,
        )
    if "target_trial_statuses" in config:
        _require_canonical_path(
            root,
            config["target_trial_statuses"],
            field=f"{candidate_id} target_trial_statuses",
            canonical_path=CANONICAL_TRIAL_STATUSES,
        )

    command = config.get("discovery_command")
    if not isinstance(command, list):
        return
    for flag, canonical_path in (
        ("--target-registry", CANONICAL_REGISTRY),
        ("--target-trial-statuses", CANONICAL_TRIAL_STATUSES),
    ):
        for index, part in enumerate(command):
            if part != flag:
                continue
            if index + 1 >= len(command):
                raise GeneratorError(f"{candidate_id} discovery_command {flag} is missing a value")
            _require_canonical_path(
                root,
                command[index + 1],
                field=f"{candidate_id} discovery_command {flag}",
                canonical_path=canonical_path,
            )


def _replace_placeholders(value: Any, *, candidate_id: str, run: str) -> Any:
    if isinstance(value, str):
        return value.replace(ID_PLACEHOLDER, candidate_id).replace(RUN_PLACEHOLDER, run)
    if isinstance(value, list):
        return [
            _replace_placeholders(item, candidate_id=candidate_id, run=run)
            for item in value
        ]
    if isinstance(value, dict):
        return {
            _replace_placeholders(key, candidate_id=candidate_id, run=run): _replace_placeholders(
                item,
                candidate_id=candidate_id,
                run=run,
            )
            for key, item in value.items()
        }
    return value


def _normalize_candidates(payload: dict[str, Any]) -> tuple[int, list[dict[str, str]]]:
    max_candidates = payload.get("max_candidates")
    if not isinstance(max_candidates, int) or max_candidates <= 0:
        raise GeneratorError("spec field 'max_candidates' must be a positive integer")
    if max_candidates > HARD_MAX_CANDIDATES:
        raise GeneratorError(
            f"spec max_candidates {max_candidates} exceeds hard cap {HARD_MAX_CANDIDATES}"
        )

    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise GeneratorError("spec candidates must contain at least one entry")
    if len(raw_candidates) > max_candidates:
        raise GeneratorError(
            f"spec has {len(raw_candidates)} candidates but max_candidates is {max_candidates}"
        )
    if len(raw_candidates) > HARD_MAX_CANDIDATES:
        raise GeneratorError(
            f"spec has {len(raw_candidates)} candidates but hard cap is {HARD_MAX_CANDIDATES}"
        )

    candidates: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw_candidates, start=1):
        if not isinstance(entry, dict):
            raise GeneratorError(f"candidate entry {index} must be a JSON object")
        candidate_id = _require_string(entry, "id", label=f"candidate entry {index}")
        run = _require_string(entry, "run", label=f"candidate {candidate_id}")
        _require_safe_token(candidate_id, field=f"candidate {candidate_id} id")
        _require_safe_token(run, field=f"candidate {candidate_id} run")
        if candidate_id in seen_ids:
            raise GeneratorError(f"duplicate candidate id: {candidate_id}")
        seen_ids.add(candidate_id)
        candidates.append({"id": candidate_id, "run": run})
    return max_candidates, candidates


def _registry_entry(registry: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    rows = registry.get("hypotheses")
    if not isinstance(rows, list):
        raise GeneratorError("canonical target registry hypotheses must be a list")
    matches = [
        item
        for item in rows
        if isinstance(item, dict) and item.get("target_hypothesis_id") == candidate_id
    ]
    if len(matches) != 1:
        raise GeneratorError(
            f"expected exactly one canonical registry entry for {candidate_id!r}; found {len(matches)}"
        )
    return matches[0]


def _trial_status_entries(path: Path, candidate_id: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise GeneratorError(f"missing canonical trial-status ledger: {path}")
    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GeneratorError(
                f"invalid canonical trial-status JSONL line {line_number}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise GeneratorError(f"canonical trial-status line {line_number} is not an object")
        if payload.get("hypothesis_id") == candidate_id:
            entries.append(payload)
    return entries


def _validate_canonical_candidate(candidate_id: str, *, root: Path) -> None:
    if candidate_id not in TARGET_SPECS:
        raise GeneratorError(
            f"{candidate_id!r} is not supported by the ES 30m target smoke harness"
        )

    registry = _read_json(root / CANONICAL_REGISTRY, label="canonical target registry")
    entry = _registry_entry(registry, candidate_id)
    target_spec = TARGET_SPECS[candidate_id]
    failures: list[str] = []

    if entry.get("status") != "CANDIDATE":
        failures.append("registry status must be CANDIDATE")
    if entry.get("wfa_allowed") is not False:
        failures.append("registry wfa_allowed must be false")
    if entry.get("source_reports") != []:
        failures.append("registry source_reports must be empty before discovery")
    if entry.get("target_family") != target_spec.target_family:
        failures.append(f"registry target_family must be {target_spec.target_family}")

    scope = entry.get("scope")
    if not isinstance(scope, dict):
        failures.append("registry scope must be an object")
    else:
        if scope.get("profile") != "tier_1":
            failures.append("registry scope.profile must be tier_1")
        if scope.get("markets") != ["ES"]:
            failures.append("registry scope.markets must be ['ES']")
        if scope.get("years") != [2023, 2024]:
            failures.append("registry scope.years must be [2023, 2024]")

    trial_entries = _trial_status_entries(root / CANONICAL_TRIAL_STATUSES, candidate_id)
    if not trial_entries:
        failures.append("candidate is missing from canonical trial-status ledger")
    else:
        latest = trial_entries[-1]
        if latest.get("status") != "CANDIDATE":
            failures.append("latest trial status must be CANDIDATE")
        if latest.get("stage") != "register_candidate":
            failures.append("latest trial stage must be register_candidate")
        if latest.get("evidence") != []:
            failures.append("latest trial evidence must be empty before discovery")

    if failures:
        raise GeneratorError(
            f"{candidate_id} is not canonical Phase 9 target-discovery ready: "
            + "; ".join(failures)
        )


def _generated_config(
    template: dict[str, Any],
    *,
    root: Path,
    candidate_id: str,
    run: str,
) -> dict[str, Any]:
    config = copy.deepcopy(template)
    config.pop("template", None)
    config = _replace_placeholders(config, candidate_id=candidate_id, run=run)
    if not isinstance(config, dict):
        raise GeneratorError(f"generated config for {candidate_id} is not a JSON object")
    config["runner_mode"] = "preflight"
    if config.get("hypothesis_id") != candidate_id:
        raise GeneratorError(f"generated config hypothesis_id must be {candidate_id}")
    _require_canonical_config_paths(config, root=root, candidate_id=candidate_id)
    single_runner.validate_runner_config(config, mode="preflight")
    single_runner.validate_runner_config(config, mode="discovery-packet")
    return config


def generate_from_spec(*, spec_path: Path, root: Path) -> dict[str, Any]:
    spec = _read_json(spec_path, label="candidate generation spec")
    if spec.get("schema_version") != 1:
        raise GeneratorError("spec schema_version must be 1")

    batch_id = _require_string(spec, "batch_id", label="spec")
    _require_safe_token(batch_id, field="batch_id")
    template_path = _as_path(root, _require_string(spec, "template_config", label="spec"))
    output_config_dir = _as_path(root, _require_string(spec, "output_config_dir", label="spec"))
    output_queue = _as_path(root, _require_string(spec, "output_queue", label="spec"))
    _assert_under_root(root, template_path, field="template_config")
    _assert_under_configs(root, output_config_dir, field="output_config_dir")
    _assert_under_configs(root, output_queue, field="output_queue")

    max_candidates, candidates = _normalize_candidates(spec)
    template = _read_json(template_path, label="template config")
    for candidate in candidates:
        _validate_canonical_candidate(candidate["id"], root=root)

    generated_configs: list[tuple[Path, dict[str, Any]]] = []
    queue_entries: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate["id"]
        config_path = output_config_dir / f"alpha_discovery_runner.{candidate_id}.json"
        _assert_under_configs(root, config_path, field=f"candidate {candidate_id} config")
        config = _generated_config(
            template,
            root=root,
            candidate_id=candidate_id,
            run=candidate["run"],
        )
        generated_configs.append((config_path, config))
        queue_entries.append(
            {
                "id": candidate_id,
                "config": _relative(root, config_path),
                "approved": False,
            }
        )

    queue = {
        "schema_version": 1,
        "runner_mode": "preflight",
        "max_candidates": max_candidates,
        "stop_on_infrastructure_failure": True,
        "log_root": "logs/alpha_discovery_queue",
        "candidates": queue_entries,
    }

    outputs = [path for path, _ in generated_configs] + [output_queue]
    existing = [_relative(root, path) for path in outputs if path.exists()]
    if existing:
        raise GeneratorError(f"output file already exists; refusing overwrite: {existing}")

    for path, config in generated_configs:
        _write_json(path, config)
    _write_json(output_queue, queue)

    return {
        "status": "GENERATOR_COMPLETED",
        "generated": True,
        "batch_id": batch_id,
        "candidate_count": len(candidates),
        "max_candidates": max_candidates,
        "mode": "preflight",
        "config_paths": [_relative(root, path) for path, _ in generated_configs],
        "queue_path": _relative(root, output_queue),
        "writes_restricted_to_configs": True,
        "registry_status_mutated": False,
        "reports_data_models_or_logs_written": False,
        "canonical_candidate_gate": "passed",
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate-candidates",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--spec", required=True, help="candidate generation spec JSON")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = repo_root()
    try:
        spec_path = _as_path(root, args.spec)
        payload = generate_from_spec(spec_path=spec_path, root=root)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except GeneratorError as exc:
        print(json.dumps({"status": "FAIL", "failure": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    except single_runner.RunnerError as exc:
        print(json.dumps({"status": "FAIL", "failure": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fail-closed path.
        payload = {"status": "FAIL", "failure": f"unexpected error: {type(exc).__name__}: {exc}"}
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
