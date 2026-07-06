#!/usr/bin/env python3
"""Guarded WFA materialization adapter for opening-range acceptance target."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_gates import file_sha256  # noqa: E402
from scripts.phase9_research.es_30m_target_smoke_harness import (  # noqa: E402
    ENTRY_OFFSET_BARS,
    EXIT_OFFSET_BARS,
    TARGET_SPECS,
    load_es_cost_config,
)
from scripts.validation.target_policy_contract import opening_range_acceptance_contract  # noqa: E402

HYPOTHESIS_ID = "opening_range_acceptance_continuation_30m_v1"
SPEC = TARGET_SPECS[HYPOTHESIS_ID]
APPROVAL_TOKEN = "APPROVE_OPENING_RANGE_ACCEPTANCE_WFA_MATERIALIZATION_V1"

STATUS_DRY_RUN_READY = "DRY_RUN_READY_OPENING_RANGE_ACCEPTANCE_WFA_MATERIALIZATION"
STATUS_EXECUTED = "EXECUTED_OPENING_RANGE_ACCEPTANCE_WFA_MATERIALIZATION"
STATUS_NO_GO = "NO_GO_OPENING_RANGE_ACCEPTANCE_WFA_MATERIALIZATION"

DEFAULT_INPUT_ROOT = Path("data/feature_matrices")
DEFAULT_OUTPUT_ROOT = Path("data/feature_matrices/opening_range_acceptance_continuation_30m_v1_wfa_smoke")
DEFAULT_REPORTS_ROOT = Path("reports/pipeline_audit")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")
DEFAULT_MODELS_CONFIG = Path("configs/models_opening_range_acceptance_continuation_30m_v1.yaml")
DEFAULT_REGISTRY = Path("manifests/target_hypotheses/registry.json")
DEFAULT_TRIAL_STATUSES = Path("manifests/target_hypotheses/trial_statuses.jsonl")
DEFAULT_MARKETS = ("ES",)
DEFAULT_YEARS = (2023, 2024)

MODEL_TARGET = "target_sign_with_deadzone"
MODEL_ID = "logistic_opening_range_acceptance_continuation_30m_v1"
REPORT_STEM = "opening_range_acceptance_continuation_30m_v1_wfa_materialization"
FALSE_APPROVAL_FLAGS = (
    "wfa_model_training_approved",
    "wfa_prediction_write_approved",
    "phase8_approved",
    "promotion_approved",
    "paper_live_approved",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _normalize(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def target_policy_contract_payload() -> dict[str, object]:
    return opening_range_acceptance_contract()


def _read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing JSON: {path.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"unreadable JSON: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"JSON is not an object: {path.as_posix()}"
    return payload, None


def _read_yaml_object(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing YAML: {path.as_posix()}"
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return {}, f"unreadable YAML: {path.as_posix()}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"YAML is not an object: {path.as_posix()}"
    return payload, None


def _git_staged_generated_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "data", "reports"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff --cached failed")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _git_ignored_paths(repo_root: Path, paths: Iterable[str]) -> list[str]:
    candidates = sorted({str(path) for path in paths if str(path)})
    if not candidates:
        return []
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=repo_root,
        input=("\n".join(candidates) + "\n").encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "git check-ignore failed")
    stdout = result.stdout.decode("utf-8", errors="replace")
    return sorted(line.strip() for line in stdout.splitlines() if line.strip())


def _check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _parse_csv(value: str | None, *, cast: type = str) -> tuple[Any, ...]:
    if value is None or not value.strip():
        return ()
    return tuple(cast(item.strip()) for item in value.split(",") if item.strip())


def expected_generated_paths(
    *,
    output_root: Path,
    reports_root: Path,
    markets: Iterable[str],
    years: Iterable[int],
    repo_root: Path,
) -> list[str]:
    paths = [
        output_root / market / f"{int(year)}.parquet"
        for market in markets
        for year in years
    ]
    paths.append(output_root / "feature_cols.json")
    paths.append(reports_root / f"{REPORT_STEM}.json")
    paths.append(reports_root / f"{REPORT_STEM}.md")
    return sorted(rel(path, repo_root) for path in paths)


def _existing_files_under(root: Path, repo_root: Path) -> list[str]:
    if not root.exists():
        return []
    if root.is_file():
        return [rel(root, repo_root)]
    return sorted(rel(path, repo_root) for path in root.rglob("*") if path.is_file())


def _feature_cols_path(input_root: Path) -> Path:
    return input_root / "feature_cols.json"


def load_feature_cols(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"feature_cols must be a JSON string list: {path.as_posix()}")
    return list(payload)


def validate_model_config(models_config: Path) -> list[str]:
    payload, error = _read_yaml_object(models_config)
    if error:
        return [error]
    failures: list[str] = []
    policy = payload.get("policy", {})
    if not isinstance(policy, Mapping):
        return ["models policy mapping missing"]
    for key in (
        "random_splits_allowed",
        "final_holdout_tuning_allowed",
        "hyperparameter_tuning_allowed_initially",
    ):
        if policy.get(key) is not False:
            failures.append(f"models policy {key} must be false")
    models = payload.get("models", {})
    if not isinstance(models, Mapping):
        return [*failures, "models mapping missing"]
    enabled = {
        str(model_id): model
        for model_id, model in models.items()
        if isinstance(model, Mapping) and model.get("enabled") is True
    }
    if set(enabled) != {MODEL_ID}:
        failures.append(f"enabled model set must be exactly {[MODEL_ID]}")
        return failures
    model = enabled[MODEL_ID]
    expected = {
        "stage": "phase_7a_linear_controls",
        "family": "logistic_regression",
        "task": "classification",
        "requires_optional_dependency": False,
        "target": MODEL_TARGET,
    }
    for key, value in expected.items():
        if model.get(key) != value:
            failures.append(f"{MODEL_ID}.{key} must be {value!r}")
    return failures


def validate_frozen_status(registry: Path, trial_statuses: Path) -> list[str]:
    failures: list[str] = []
    registry_payload, error = _read_json_object(registry)
    if error:
        return [error]
    hypotheses = registry_payload.get("hypotheses", [])
    if not isinstance(hypotheses, list):
        return ["target registry hypotheses must be a list"]
    row = next((item for item in hypotheses if isinstance(item, Mapping) and item.get("target_hypothesis_id") == HYPOTHESIS_ID), None)
    if row is None:
        failures.append(f"{HYPOTHESIS_ID}: missing from target registry")
    else:
        if row.get("status") != "FROZEN":
            failures.append(f"{HYPOTHESIS_ID}: registry status must be FROZEN")
        if row.get("wfa_allowed") is not True:
            failures.append(f"{HYPOTHESIS_ID}: registry wfa_allowed must be true")
    if not trial_statuses.exists():
        failures.append(f"target trial status ledger missing: {trial_statuses.as_posix()}")
        return failures
    latest: Mapping[str, Any] | None = None
    for raw in trial_statuses.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            failures.append(f"target trial status ledger invalid JSONL: {exc}")
            continue
        if isinstance(event, Mapping) and event.get("hypothesis_id") == HYPOTHESIS_ID:
            latest = event
    if latest is None:
        failures.append(f"{HYPOTHESIS_ID}: missing from target trial status ledger")
    elif latest.get("status") != "FROZEN":
        failures.append(f"{HYPOTHESIS_ID}: latest trial status must be FROZEN")
    return failures


def materialize_wfa_frame(
    frame: pd.DataFrame,
    *,
    cost_config: Mapping[str, float],
    feature_cols: list[str],
) -> pd.DataFrame:
    if any(column.startswith("target_") for column in feature_cols):
        raise ValueError("feature_cols must not contain target-derived columns")
    labeled = SPEC.apply(frame, cost_config, SPEC)
    valid = labeled[SPEC.valid_column].fillna(False).astype(bool)
    causal_valid = labeled.get("causal_valid", pd.Series(False, index=labeled.index)).fillna(False).astype(bool)
    feature_input_valid = labeled.get(
        "feature_input_valid", pd.Series(True, index=labeled.index)
    ).fillna(True).astype(bool)
    entry_price = pd.to_numeric(labeled["open"], errors="coerce").shift(-ENTRY_OFFSET_BARS)
    exit_price = pd.to_numeric(labeled["open"], errors="coerce").shift(-EXIT_OFFSET_BARS)

    labeled["target_valid"] = valid
    labeled[MODEL_TARGET] = pd.to_numeric(labeled[SPEC.direction_column], errors="coerce").fillna(0).astype("int64")
    labeled["target_entry_ts"] = labeled[SPEC.entry_ts_column].where(valid)
    labeled["target_exit_ts"] = labeled[SPEC.exit_ts_column].where(valid)
    labeled["target_entry_price"] = entry_price.where(valid)
    labeled["target_exit_price"] = exit_price.where(valid)
    labeled["training_row_valid"] = (feature_input_valid & causal_valid & valid).astype(bool)
    return labeled


def _write_markdown_report(path: Path, report: Mapping[str, Any]) -> None:
    summary = report.get("summary", {})
    lines = [
        f"# {HYPOTHESIS_ID} WFA Materialization",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Commands executed: `{summary.get('commands_executed')}`",
        f"- Generated outputs: `{summary.get('generated_output_count')}`",
        f"- Failure count: `{summary.get('failure_count')}`",
        "",
        "## Do Not Do",
        "",
        "- Do not run WFA/modeling, Phase 8, promotion, paper, or live execution from this report alone.",
        "- Do not tune thresholds/features/costs/folds/markets/years from this materialization output.",
        "- Require a later separate approval before running the drafted Phase 6 command.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_materialized_outputs(
    *,
    input_root: Path,
    output_root: Path,
    reports_root: Path,
    costs_config: Path,
    markets: Iterable[str],
    years: Iterable[int],
    repo_root: Path,
) -> tuple[list[str], list[str], dict[str, str], int]:
    failures: list[str] = []
    generated: list[str] = []
    output_hashes: dict[str, str] = {}
    feature_cols = load_feature_cols(_feature_cols_path(input_root))
    cost_config = load_es_cost_config(costs_config)
    row_count = 0
    for market in markets:
        for year in years:
            source = input_root / market / f"{int(year)}.parquet"
            destination = output_root / market / f"{int(year)}.parquet"
            try:
                frame = pd.read_parquet(source)
                materialized = materialize_wfa_frame(
                    frame,
                    cost_config=cost_config,
                    feature_cols=feature_cols,
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                materialized.to_parquet(destination, index=False)
                generated.append(rel(destination, repo_root))
                output_hashes[rel(destination, repo_root)] = file_sha256(destination)
                row_count += int(len(materialized))
            except Exception as exc:
                failures.append(
                    f"{market} {int(year)} materialization failed: {type(exc).__name__}: {exc}"
                )
    feature_cols_out = output_root / "feature_cols.json"
    try:
        feature_cols_out.parent.mkdir(parents=True, exist_ok=True)
        feature_cols_out.write_text(json.dumps(feature_cols, indent=2), encoding="utf-8")
        generated.append(rel(feature_cols_out, repo_root))
        output_hashes[rel(feature_cols_out, repo_root)] = file_sha256(feature_cols_out)
    except Exception as exc:
        failures.append(f"feature_cols write failed: {type(exc).__name__}: {exc}")
    return sorted(generated), failures, output_hashes, row_count


def build_report(
    *,
    repo_root: Path = REPO_ROOT,
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    reports_root: Path = DEFAULT_REPORTS_ROOT,
    costs_config: Path = DEFAULT_COSTS_CONFIG,
    models_config: Path = DEFAULT_MODELS_CONFIG,
    registry: Path = DEFAULT_REGISTRY,
    trial_statuses: Path = DEFAULT_TRIAL_STATUSES,
    markets: Iterable[str] = DEFAULT_MARKETS,
    years: Iterable[int] = DEFAULT_YEARS,
    execute: bool = False,
    approval_token: str | None = None,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
    ignored_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    input_root = resolve(repo_root, input_root)
    output_root = resolve(repo_root, output_root)
    reports_root = resolve(repo_root, reports_root)
    costs_config = resolve(repo_root, costs_config)
    models_config = resolve(repo_root, models_config)
    registry = resolve(repo_root, registry)
    trial_statuses = resolve(repo_root, trial_statuses)
    selected_markets = tuple(str(item) for item in markets)
    selected_years = tuple(int(item) for item in years)
    generated_at = generated_at_utc or utc_now()

    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    staged_paths = (
        sorted(staged_generated_paths)
        if staged_generated_paths is not None
        else _git_staged_generated_paths(repo_root)
    )
    expected_paths = expected_generated_paths(
        output_root=output_root,
        reports_root=reports_root,
        markets=selected_markets,
        years=selected_years,
        repo_root=repo_root,
    )
    ignored_paths = (
        sorted(ignored_generated_paths)
        if ignored_generated_paths is not None
        else _git_ignored_paths(repo_root, expected_paths)
    )
    ignored_normalized = {_normalize(path) for path in ignored_paths}
    unignored_paths = [path for path in expected_paths if _normalize(path) not in ignored_normalized]
    existing_expected = [path for path in expected_paths if (repo_root / path).exists()]
    existing_output_tree = _existing_files_under(output_root, repo_root)
    existing_report_paths = [
        rel(path, repo_root)
        for path in (
            reports_root / f"{REPORT_STEM}.json",
            reports_root / f"{REPORT_STEM}.md",
        )
        if path.exists()
    ]

    def add_check(name: str, passed: bool, observed: Any, expected: Any, detail: str) -> None:
        _check(checks, name=name, passed=passed, observed=observed, expected=expected, detail=detail)
        if not passed:
            failures.append(detail)

    add_check(
        "scope_is_exact_es_2023_2024",
        selected_markets == ("ES",) and selected_years == (2023, 2024),
        {"markets": selected_markets, "years": selected_years},
        {"markets": ("ES",), "years": (2023, 2024)},
        "Materialization scope must stay exact ES 2023/2024.",
    )
    input_paths = [input_root / market / f"{year}.parquet" for market in selected_markets for year in selected_years]
    missing_inputs = [rel(path, repo_root) for path in input_paths if not path.exists()]
    add_check(
        "input_matrices_present",
        not missing_inputs,
        missing_inputs,
        [],
        "Required source matrices must exist before materialization.",
    )
    feature_cols_path = _feature_cols_path(input_root)
    add_check(
        "feature_cols_present",
        feature_cols_path.exists(),
        rel(feature_cols_path, repo_root),
        "exists",
        "Input feature_cols.json must exist.",
    )
    if feature_cols_path.exists():
        try:
            feature_cols = load_feature_cols(feature_cols_path)
            target_features = [column for column in feature_cols if column.startswith("target_")]
            add_check(
                "feature_cols_are_feature_only",
                not target_features,
                target_features,
                [],
                "Feature columns must not include target-derived columns.",
            )
        except Exception as exc:
            add_check(
                "feature_cols_parse",
                False,
                type(exc).__name__,
                "valid JSON string list",
                f"feature_cols.json must parse: {exc}",
            )
    add_check(
        "costs_config_present",
        costs_config.exists(),
        rel(costs_config, repo_root),
        "exists",
        "Costs config must exist.",
    )
    model_failures = validate_model_config(models_config)
    add_check(
        "target_model_config_valid",
        not model_failures,
        model_failures,
        [],
        "Target-specific model config must be one fixed logistic classifier using target_sign_with_deadzone.",
    )
    frozen_failures = validate_frozen_status(registry, trial_statuses)
    add_check(
        "target_registry_status_frozen",
        not frozen_failures,
        frozen_failures,
        [],
        "Target registry and latest trial status must be FROZEN before adapter execution.",
    )
    add_check(
        "planned_outputs_ignored_by_git",
        not unignored_paths,
        unignored_paths,
        [],
        "All planned generated data/report outputs must be ignored by git.",
    )
    add_check(
        "generated_artifacts_unstaged",
        not staged_paths,
        staged_paths,
        [],
        "No generated data/report artifacts may be staged.",
    )
    add_check(
        "output_paths_absent_before_execution",
        not existing_expected and not existing_output_tree and not existing_report_paths,
        {
            "existing_expected": existing_expected,
            "existing_output_tree": existing_output_tree,
            "existing_report_paths": existing_report_paths,
        },
        {"existing_expected": [], "existing_output_tree": [], "existing_report_paths": []},
        "Adapter output root and materialization reports must be absent before execution.",
    )
    add_check(
        "execution_approval_token_present_when_execute",
        (not execute) or approval_token == APPROVAL_TOKEN,
        approval_token if execute else None,
        APPROVAL_TOKEN if execute else None,
        "Execution requires the exact materialization approval token.",
    )

    commands_executed = 0
    generated_outputs: list[str] = []
    output_hashes: dict[str, str] = {}
    materialized_row_count = 0
    if execute and not failures:
        commands_executed = 1
        generated_outputs, write_failures, output_hashes, materialized_row_count = _write_materialized_outputs(
            input_root=input_root,
            output_root=output_root,
            reports_root=reports_root,
            costs_config=costs_config,
            markets=selected_markets,
            years=selected_years,
            repo_root=repo_root,
        )
        failures.extend(write_failures)

    status = STATUS_NO_GO
    if not failures and execute:
        status = STATUS_EXECUTED
    elif not failures:
        status = STATUS_DRY_RUN_READY

    summary = {
        "stage": "opening_range_acceptance_wfa_materialization",
        "status": status,
        "hypothesis_id": HYPOTHESIS_ID,
        "commands_planned": 1,
        "commands_executed": commands_executed,
        "approval_token": APPROVAL_TOKEN,
        "markets": list(selected_markets),
        "years": list(selected_years),
        "input_root": rel(input_root, repo_root),
        "output_root": rel(output_root, repo_root),
        "reports_root": rel(reports_root, repo_root),
        "models_config": rel(models_config, repo_root),
        "expected_generated_output_count": len(expected_paths),
        "ignored_expected_generated_output_count": len(expected_paths) - len(unignored_paths),
        "unignored_expected_generated_output_count": len(unignored_paths),
        "existing_expected_generated_output_count": len(existing_expected),
        "staged_generated_path_count": len(staged_paths),
        "generated_output_count": len(generated_outputs),
        "materialized_row_count": materialized_row_count,
        "failure_count": len(failures),
        "wfa_materialization_approved": bool(execute and status == STATUS_EXECUTED),
        **{flag: False for flag in FALSE_APPROVAL_FLAGS},
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "created_at_utc": generated_at,
        "summary": summary,
        "checks": checks,
        "failures": failures,
        "expected_generated_artifacts": expected_paths,
        "unignored_expected_generated_artifacts": unignored_paths,
        "existing_expected_generated_artifacts": existing_expected,
        "staged_generated_artifacts": staged_paths,
        "generated_outputs": generated_outputs,
        "output_file_hashes": output_hashes,
        "target_mapping": {
            "target_valid": SPEC.valid_column,
            MODEL_TARGET: SPEC.direction_column,
            "target_entry_ts": SPEC.entry_ts_column,
            "target_exit_ts": SPEC.exit_ts_column,
            "target_entry_price": f"open.shift(-{ENTRY_OFFSET_BARS})",
            "target_exit_price": f"open.shift(-{EXIT_OFFSET_BARS})",
            "training_row_valid": "feature_input_valid & causal_valid & target_valid",
        },
        "target_policy_contract": target_policy_contract_payload(),
        "do_not_do": [
            "do not run WFA/modeling from this adapter without later separate approval",
            "do not run Phase 8, promotion, paper, or live execution from this adapter",
            "do not tune thresholds/features/costs/folds/markets/years from this output",
        ],
    }
    if status == STATUS_EXECUTED:
        report_json = reports_root / f"{REPORT_STEM}.json"
        report_md = reports_root / f"{REPORT_STEM}.md"
        _write_json(report_json, report)
        _write_markdown_report(report_md, report)
        generated_outputs.extend([rel(report_json, repo_root), rel(report_md, repo_root)])
        report["generated_outputs"] = sorted(generated_outputs)
        report["summary"]["generated_output_count"] = len(generated_outputs)
        _write_json(report_json, report)
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT.as_posix())
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT.as_posix())
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--target-registry", default=DEFAULT_REGISTRY.as_posix())
    parser.add_argument("--target-trial-statuses", default=DEFAULT_TRIAL_STATUSES.as_posix())
    parser.add_argument("--markets", default=",".join(DEFAULT_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in DEFAULT_YEARS))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval-token", default=None)
    parser.add_argument("--print-json", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    report = build_report(
        input_root=Path(args.input_root),
        output_root=Path(args.output_root),
        reports_root=Path(args.reports_root),
        costs_config=Path(args.costs_config),
        models_config=Path(args.models_config),
        registry=Path(args.target_registry),
        trial_statuses=Path(args.target_trial_statuses),
        markets=_parse_csv(args.markets, cast=str),
        years=_parse_csv(args.years, cast=int),
        execute=args.execute,
        approval_token=args.approval_token,
    )
    if args.print_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    summary = report["summary"]
    print(
        f"{summary['status']} opening-range WFA materialization: "
        f"commands_executed={summary['commands_executed']} "
        f"expected_generated_outputs={summary['expected_generated_output_count']} "
        f"generated_outputs={summary['generated_output_count']} "
        f"failures={summary['failure_count']}"
    )
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
