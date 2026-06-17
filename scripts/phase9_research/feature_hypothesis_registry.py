#!/usr/bin/env python3
"""Validate the feature hypothesis registry and status ledger."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_REGISTRY = Path("manifests/feature_hypotheses/registry.json")
DEFAULT_TRIAL_STATUSES = Path("manifests/feature_hypotheses/trial_statuses.jsonl")

ALLOWED_STATUSES = (
    "CANDIDATE",
    "DISCOVERY_PASS",
    "CONFIRMATION_PASS",
    "FROZEN",
    "REJECTED",
    "RETIRED",
    "QUARANTINED",
)
WFA_ALLOWED_STATUSES = ("FROZEN",)
TERMINAL_STATUSES = {"REJECTED", "RETIRED", "QUARANTINED"}
EVIDENCE_REQUIRED_STATUSES = {
    "DISCOVERY_PASS",
    "CONFIRMATION_PASS",
    "FROZEN",
    "REJECTED",
    "RETIRED",
    "QUARANTINED",
}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root is not an object: {_relative_path(path)}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _resolve_path(base: Path, raw_path: object) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    return base.parent / path


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return list(value)


def _hypothesis_ids(registry: Mapping[str, Any]) -> set[str]:
    hypotheses = registry.get("hypotheses", [])
    if not isinstance(hypotheses, list):
        return set()
    return {
        str(item.get("hypothesis_id"))
        for item in hypotheses
        if isinstance(item, Mapping) and isinstance(item.get("hypothesis_id"), str)
    }


def _trial_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    trial_ids: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, Mapping) and isinstance(item.get("trial_id"), str):
            trial_ids.add(str(item["trial_id"]))
    return trial_ids


def _csv_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _csv_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _validate_feature_set_manifest(path: Path, feature_set_path: Path, hypothesis_id: str) -> list[str]:
    errors: list[str] = []
    if not feature_set_path.exists():
        return [f"{hypothesis_id}: feature_set_manifest missing: {_relative_path(feature_set_path)}"]
    try:
        payload = _read_json(feature_set_path)
    except Exception as exc:
        return [f"{hypothesis_id}: feature_set_manifest invalid JSON: {exc}"]
    if payload.get("status") != "FROZEN":
        errors.append(f"{hypothesis_id}: feature_set_manifest is not FROZEN")
    if payload.get("allowed_for_wfa") is not True:
        errors.append(f"{hypothesis_id}: feature_set_manifest is not allowed_for_wfa")
    if "features" not in payload and "features_path" not in payload:
        errors.append(f"{hypothesis_id}: feature_set_manifest has no features or features_path")
    if payload.get("feature_count") is not None:
        try:
            count = int(payload["feature_count"])
        except (TypeError, ValueError):
            errors.append(f"{hypothesis_id}: feature_set_manifest feature_count is not an integer")
        else:
            if count <= 0:
                errors.append(f"{hypothesis_id}: feature_set_manifest feature_count is not positive")
    return errors


def register_candidate(
    *,
    registry_path: Path,
    trial_statuses_path: Path,
    hypothesis_id: str,
    description: str,
    feature_family: str,
    profile: str,
    resolved_profile: str | None,
    markets: Sequence[str],
    years: Sequence[int],
    status_reason: str = "Pre-registered candidate; discovery not run.",
    source_reports: Sequence[str] = (),
    next_allowed_actions: Sequence[str] = ("RUN_DISCOVERY_HARNESS",),
    trial_id: str | None = None,
    notes: str = "",
) -> list[str]:
    errors: list[str] = []
    if not registry_path.exists():
        return [f"registry missing: {_relative_path(registry_path)}"]
    if not ID_PATTERN.match(hypothesis_id):
        errors.append("hypothesis_id must match ^[a-z0-9][a-z0-9_-]*$")
    resolved_trial_id = trial_id or f"{hypothesis_id}_candidate"
    if not ID_PATTERN.match(resolved_trial_id):
        errors.append("trial_id must match ^[a-z0-9][a-z0-9_-]*$")
    if not description.strip():
        errors.append("description is required")
    if not feature_family.strip():
        errors.append("feature_family is required")
    clean_markets = [str(market).strip() for market in markets if str(market).strip()]
    if not clean_markets:
        errors.append("at least one market is required")
    clean_years: list[int] = []
    try:
        clean_years = [int(year) for year in years]
    except (TypeError, ValueError):
        errors.append("years must be integers")
    if not clean_years:
        errors.append("at least one year is required")
    if errors:
        return errors

    try:
        registry = _read_json(registry_path)
    except Exception as exc:
        return [f"registry invalid JSON: {exc}"]
    hypotheses = registry.get("hypotheses")
    if not isinstance(hypotheses, list):
        return ["registry hypotheses must be a list"]
    if hypothesis_id in _hypothesis_ids(registry):
        return [f"{hypothesis_id}: duplicate hypothesis_id"]
    if resolved_trial_id in _trial_ids(trial_statuses_path):
        return [f"{resolved_trial_id}: duplicate trial_id"]

    hypotheses.append(
        {
            "hypothesis_id": hypothesis_id,
            "status": "CANDIDATE",
            "wfa_allowed": False,
            "feature_family": feature_family,
            "scope": {
                "profile": profile,
                "resolved_profile": resolved_profile,
                "markets": clean_markets,
                "years": clean_years,
            },
            "description": description,
            "status_reason": status_reason,
            "source_reports": list(source_reports),
            "next_allowed_actions": list(next_allowed_actions),
        }
    )

    registry_errors = validate_registry_payload(registry, registry_path)
    if registry_errors:
        return registry_errors

    _write_json(registry_path, registry)
    event = {
        "schema_version": 1,
        "trial_id": resolved_trial_id,
        "hypothesis_id": hypothesis_id,
        "status": "CANDIDATE",
        "stage": "register_candidate",
        "evidence": list(source_reports),
        "notes": notes or status_reason,
    }
    trial_statuses_path.parent.mkdir(parents=True, exist_ok=True)
    with trial_statuses_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return [
        *validate_registry(registry_path),
        *validate_trial_statuses(trial_statuses_path, registry_path),
    ]


def validate_registry_payload(registry: Mapping[str, Any], path: Path = DEFAULT_REGISTRY) -> list[str]:
    errors: list[str] = []
    if registry.get("schema_version") != 1:
        errors.append("registry schema_version must be 1")

    allowed_statuses = _string_list(registry.get("allowed_statuses"))
    if allowed_statuses is None:
        errors.append("registry allowed_statuses must be a string list")
    elif set(allowed_statuses) != set(ALLOWED_STATUSES):
        errors.append("registry allowed_statuses do not match validator statuses")

    wfa_allowed_statuses = _string_list(registry.get("wfa_allowed_statuses"))
    if wfa_allowed_statuses is None:
        errors.append("registry wfa_allowed_statuses must be a string list")
    elif set(wfa_allowed_statuses) != set(WFA_ALLOWED_STATUSES):
        errors.append("registry wfa_allowed_statuses must be FROZEN only")

    transitions = registry.get("allowed_transitions", {})
    if not isinstance(transitions, Mapping):
        errors.append("registry allowed_transitions must be an object")
    else:
        for status, next_statuses in transitions.items():
            if status not in ALLOWED_STATUSES:
                errors.append(f"transition source has unknown status: {status}")
            values = _string_list(next_statuses)
            if values is None:
                errors.append(f"transition target list is invalid for {status}")
                continue
            unknown = sorted(set(values) - set(ALLOWED_STATUSES))
            if unknown:
                errors.append(f"transition targets unknown statuses for {status}: {unknown}")
            if status in TERMINAL_STATUSES and values:
                errors.append(f"terminal status {status} must not allow transitions")

    hypotheses = registry.get("hypotheses")
    if not isinstance(hypotheses, list):
        return [*errors, "registry hypotheses must be a list"]

    seen: set[str] = set()
    for index, raw_item in enumerate(hypotheses):
        if not isinstance(raw_item, Mapping):
            errors.append(f"hypotheses[{index}] is not an object")
            continue
        hypothesis_id = raw_item.get("hypothesis_id")
        if not isinstance(hypothesis_id, str) or not ID_PATTERN.match(hypothesis_id):
            errors.append(f"hypotheses[{index}] has invalid hypothesis_id")
            continue
        if hypothesis_id in seen:
            errors.append(f"{hypothesis_id}: duplicate hypothesis_id")
        seen.add(hypothesis_id)

        status = raw_item.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{hypothesis_id}: unknown status {status!r}")
        wfa_allowed = raw_item.get("wfa_allowed", False)
        if not isinstance(wfa_allowed, bool):
            errors.append(f"{hypothesis_id}: wfa_allowed must be boolean")
        if wfa_allowed and status not in WFA_ALLOWED_STATUSES:
            errors.append(f"{hypothesis_id}: wfa_allowed requires FROZEN status")

        for field in ("description", "status_reason"):
            value = raw_item.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{hypothesis_id}: {field} must be non-empty text")

        scope = raw_item.get("scope")
        if not isinstance(scope, Mapping):
            errors.append(f"{hypothesis_id}: scope must be an object")
        else:
            markets = scope.get("markets")
            years = scope.get("years")
            if not isinstance(markets, list) or not markets:
                errors.append(f"{hypothesis_id}: scope.markets must be a non-empty list")
            if not isinstance(years, list) or not years:
                errors.append(f"{hypothesis_id}: scope.years must be a non-empty list")

        if status == "FROZEN":
            feature_set = raw_item.get("feature_set_manifest")
            if not isinstance(feature_set, str) or not feature_set:
                errors.append(f"{hypothesis_id}: FROZEN status requires feature_set_manifest")
            else:
                errors.extend(
                    _validate_feature_set_manifest(
                        path,
                        _resolve_path(path, feature_set),
                        hypothesis_id,
                    )
                )
        elif raw_item.get("feature_set_manifest") and wfa_allowed:
            errors.append(f"{hypothesis_id}: non-FROZEN hypothesis cannot be WFA allowed")

    return errors


def validate_registry(path: Path = DEFAULT_REGISTRY) -> list[str]:
    if not path.exists():
        return [f"registry missing: {_relative_path(path)}"]
    try:
        registry = _read_json(path)
    except Exception as exc:
        return [f"registry invalid JSON: {exc}"]
    return validate_registry_payload(registry, path)


def validate_trial_statuses(
    path: Path = DEFAULT_TRIAL_STATUSES,
    registry_path: Path = DEFAULT_REGISTRY,
) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"trial status ledger missing: {_relative_path(path)}"]
    try:
        registry = _read_json(registry_path)
    except Exception as exc:
        return [f"registry invalid JSON for trial validation: {exc}"]
    valid_hypotheses = _hypothesis_ids(registry)
    seen_trials: set[str] = set()
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{_relative_path(path)}:{line_no}: invalid JSONL: {exc}")
            continue
        if not isinstance(item, Mapping):
            errors.append(f"{_relative_path(path)}:{line_no}: entry is not an object")
            continue
        trial_id = item.get("trial_id")
        hypothesis_id = item.get("hypothesis_id")
        status = item.get("status")
        if not isinstance(trial_id, str) or not ID_PATTERN.match(trial_id):
            errors.append(f"{_relative_path(path)}:{line_no}: invalid trial_id")
        elif trial_id in seen_trials:
            errors.append(f"{_relative_path(path)}:{line_no}: duplicate trial_id {trial_id}")
        seen_trials.add(str(trial_id))
        if hypothesis_id not in valid_hypotheses:
            errors.append(f"{_relative_path(path)}:{line_no}: unknown hypothesis_id {hypothesis_id!r}")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{_relative_path(path)}:{line_no}: unknown status {status!r}")
        evidence = item.get("evidence", [])
        if status in EVIDENCE_REQUIRED_STATUSES:
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"{_relative_path(path)}:{line_no}: status {status} requires evidence")
    return errors


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        choices=("validate", "register-candidate"),
        default="validate",
    )
    parser.add_argument("--registry", default=DEFAULT_REGISTRY.as_posix())
    parser.add_argument("--trial-statuses", default=DEFAULT_TRIAL_STATUSES.as_posix())
    parser.add_argument("--hypothesis-id", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--feature-family", default=None)
    parser.add_argument("--profile", default="tier_1")
    parser.add_argument("--resolved-profile", default="tier_1_research")
    parser.add_argument("--markets", default=None)
    parser.add_argument("--years", default=None)
    parser.add_argument(
        "--status-reason",
        default="Pre-registered candidate; discovery not run.",
    )
    parser.add_argument("--source-report", action="append", default=[])
    parser.add_argument("--next-action", action="append", default=["RUN_DISCOVERY_HARNESS"])
    parser.add_argument("--trial-id", default=None)
    parser.add_argument("--notes", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    registry = Path(args.registry)
    trial_statuses = Path(args.trial_statuses)
    if args.command == "register-candidate":
        missing = [
            name
            for name, value in {
                "--hypothesis-id": args.hypothesis_id,
                "--description": args.description,
                "--feature-family": args.feature_family,
                "--markets": args.markets,
                "--years": args.years,
            }.items()
            if not value
        ]
        if missing:
            print("FAIL register candidate:")
            print(f"- missing required arguments: {', '.join(missing)}")
            return 2
        try:
            years = _csv_ints(str(args.years))
        except ValueError as exc:
            print("FAIL register candidate:")
            print(f"- invalid --years: {exc}")
            return 2
        errors = register_candidate(
            registry_path=registry,
            trial_statuses_path=trial_statuses,
            hypothesis_id=str(args.hypothesis_id),
            description=str(args.description),
            feature_family=str(args.feature_family),
            profile=str(args.profile),
            resolved_profile=str(args.resolved_profile) if args.resolved_profile else None,
            markets=_csv_strings(str(args.markets)),
            years=years,
            status_reason=str(args.status_reason),
            source_reports=list(args.source_report),
            next_allowed_actions=list(args.next_action),
            trial_id=args.trial_id,
            notes=str(args.notes),
        )
        if errors:
            print("FAIL register candidate:")
            for error in errors:
                print(f"- {error}")
            return 1
        print(f"PASS registered candidate: {args.hypothesis_id}")
        return 0

    errors = [
        *validate_registry(registry),
        *validate_trial_statuses(trial_statuses, registry),
    ]
    if errors:
        print("FAIL feature hypothesis registry:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS feature hypothesis registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
