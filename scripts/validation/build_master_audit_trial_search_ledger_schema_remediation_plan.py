#!/usr/bin/env python3
"""Build a report-only trial/search ledger schema remediation plan.

This command reads existing local registry, ledger, WFA, Phase 8, statistical,
and Master Audit evidence. It writes a candidate remediation map only; it does
not mutate experiment ledgers, target registries, trial-status ledgers, data,
models, predictions, promotion artifacts, commits, or remotes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory
from scripts.validation import build_master_audit_trial_ledger_search_path_reconciliation as trial


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "master_audit_trial_search_ledger_schema_remediation_plan"
PASS_STATUS = "PASS_MASTER_AUDIT_TRIAL_SEARCH_LEDGER_SCHEMA_REMEDIATION_PLAN_REPORT_ONLY"
FAIL_STATUS = "FAIL_MASTER_AUDIT_TRIAL_SEARCH_LEDGER_SCHEMA_REMEDIATION_PLAN_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path(
    "reports/master_audit/master_audit_trial_search_ledger_schema_remediation_plan_20260710"
)
REPORT_JSON = "master_audit_trial_search_ledger_schema_remediation_plan.json"
REPORT_MD = "master_audit_trial_search_ledger_schema_remediation_plan.md"

UPSTREAM_RECONCILIATION = trial.DEFAULT_REPORTS_ROOT / trial.REPORT_JSON
EXPERIMENT_LEDGER = trial.EXPERIMENT_LEDGER
TARGET_REGISTRY = trial.TARGET_REGISTRY
TARGET_TRIAL_STATUSES = trial.TARGET_TRIAL_STATUSES
WFA_REPORT = Path(
    "reports/wfa/tier1_core_phase6_full_predictions_20260706/"
    "tier1_core_phase6_full_predictions_20260706_wfa_report.json"
)
PREDICTIONS_MANIFEST = Path(
    "reports/wfa/tier1_core_phase6_full_predictions_20260706/"
    "tier1_core_phase6_full_predictions_20260706_predictions_manifest.json"
)
PHASE8_METRICS = Path("reports/phase8/tier1_core_phase6_full_predictions_20260706/metrics.json")
PHASE8_PROMOTION = Path(
    "reports/phase8/tier1_core_phase6_full_predictions_20260706/alpha_promotion_decision.json"
)
STATISTICAL_SUMMARY = trial.STATISTICAL_SUMMARY
ALPHA_GAP_MATRIX = trial.ALPHA_GAP_MATRIX
ALPHA_COMPLETION_CLOSEOUT = trial.ALPHA_COMPLETION_CLOSEOUT
RUN_STATUS = trial.RUN_STATUS
ADVERSARIAL_AUDIT = trial.ADVERSARIAL_AUDIT

REQUIRED_INPUTS = {
    "upstream_reconciliation": UPSTREAM_RECONCILIATION,
    "experiment_ledger": EXPERIMENT_LEDGER,
    "target_registry": TARGET_REGISTRY,
    "target_trial_statuses": TARGET_TRIAL_STATUSES,
    "wfa_report": WFA_REPORT,
    "predictions_manifest": PREDICTIONS_MANIFEST,
    "phase8_metrics": PHASE8_METRICS,
    "phase8_promotion": PHASE8_PROMOTION,
    "statistical_summary": STATISTICAL_SUMMARY,
    "alpha_gap_matrix": ALPHA_GAP_MATRIX,
    "alpha_completion_closeout": ALPHA_COMPLETION_CLOSEOUT,
    "run_status": RUN_STATUS,
    "adversarial_audit": ADVERSARIAL_AUDIT,
}

REQUIRED_FIELDS = tuple(trial.SEARCH_COMPLETENESS_FIELDS)
UNRESOLVED = "UNRESOLVED_LOCAL_EVIDENCE_MISSING"
NOT_APPLICABLE = "NOT_APPLICABLE_WITH_REASON"
EXPECTED_EXPERIMENT_LEDGER_ROWS = 4
EXPECTED_REGISTRY_HYPOTHESES = 17
EXPECTED_TRIAL_STATUS_ROWS = 22
EXPECTED_REGISTRY_JSON_SOURCE_REFS = 21
EXPECTED_PRESENT_REGISTRY_JSON_SOURCE_REFS = 7
EXPECTED_MISSING_REGISTRY_JSON_SOURCE_REFS = 14

NON_APPROVAL = {
    "data_model_commands_executed": False,
    "wfa_modeling_executed": False,
    "predictions_executed": False,
    "phase8_refresh_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "freeze_executed": False,
    "holdout_executed": False,
    "paper_live_executed": False,
    "cleanup_executed": False,
    "gap_map_generation_executed": False,
    "ledger_backfill_executed": False,
    "staging_commit_push_executed": False,
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def read_jsonl_objects(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    return trial.read_jsonl_objects(path)


def unresolved(reason: str, evidence_paths: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "status": UNRESOLVED,
        "reason": reason,
        "evidence_paths": list(evidence_paths),
    }


def not_applicable(reason: str, evidence_paths: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "status": NOT_APPLICABLE,
        "reason": reason,
        "evidence_paths": list(evidence_paths),
    }


def is_unresolved(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("status") == UNRESOLVED


def check(
    checks: list[dict[str, Any]],
    failures: list[str],
    *,
    name: str,
    passed: bool,
    failure: str,
    evidence: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "failure": None if passed else failure,
            "evidence": list(evidence),
            "details": dict(details or {}),
        }
    )
    if not passed:
        failures.append(failure)


def load_payloads(
    *,
    repo_root: Path,
    paths: Mapping[str, Path],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    payloads: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for name, relative_path in paths.items():
        if Path(relative_path).suffix.lower() != ".json":
            continue
        payload, error = read_json_object(resolve_path(repo_root, relative_path))
        if error:
            failures.append(f"required JSON input unavailable: {relative_path.as_posix()} ({error})")
        elif payload is not None:
            payloads[name] = payload
    return payloads, failures


def input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    json_fields: dict[str, dict[str, str]] = {
        "upstream_reconciliation": {
            "status": "status",
            "trial_ledger_search_path_complete": "summary.trial_ledger_search_path_complete",
            "pbo_status": "summary.pbo_status",
            "deflated_sharpe_status": "summary.deflated_sharpe_status",
            "multiple_testing_status": "summary.multiple_testing_status",
            "statistical_validity_ready": "summary.statistical_validity_ready",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
        },
        "wfa_report": {
            "run": "run",
            "profile": "profile",
            "fold_count": "fold_count",
            "prediction_count": "prediction_count",
        },
        "predictions_manifest": {
            "run": "run",
            "prediction_count": "prediction_count",
            "prediction_artifact_written": "prediction_artifact_written",
            "prediction_path": "prediction_path",
        },
        "phase8_metrics": {
            "run": "run",
            "net_return_dollars": "metrics.overall.net_return_dollars",
            "trade_count": "metrics.overall.trade_count",
        },
        "phase8_promotion": {
            "run": "run",
            "promoted": "promoted",
            "research_alpha_ready": "research_alpha_ready",
            "model_promotion_allowed": "model_promotion_allowed",
        },
        "statistical_summary": {
            "status": "status",
            "statistical_validity_ready": "statistical_validity_ready",
        },
        "alpha_gap_matrix": {
            "status": "status",
            "alpha_evidence_ready": "alpha_evidence_ready",
        },
        "alpha_completion_closeout": {
            "status": "status",
            "future_modeling_allowed": "future_modeling_allowed",
            "promotion_allowed": "promotion_allowed",
        },
        "run_status": {
            "status": "status",
            "current_line_classification": "summary.current_line_classification",
        },
    }
    return [
        inventory.evidence_file(
            repo_root=repo_root,
            relative_path=relative_path,
            json_fields=json_fields.get(name),
            dirty_map=dirty_map,
        )
        for name, relative_path in paths.items()
    ]


def registry_rows(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    return trial.registry_hypotheses(payload)


def registry_json_source_report_refs(
    *,
    registry: Sequence[Mapping[str, Any]],
    repo_root: Path,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in registry:
        hypothesis_id = str(row.get("target_hypothesis_id") or "")
        source_reports = row.get("source_reports")
        if not isinstance(source_reports, list):
            continue
        for item in source_reports:
            if not isinstance(item, str) or not item.endswith(".json"):
                continue
            key = (hypothesis_id, item)
            if key in seen:
                continue
            seen.add(key)
            exists = resolve_path(repo_root, item).is_file()
            refs.append(
                {
                    "hypothesis_id": hypothesis_id,
                    "path": item,
                    "exists": exists,
                    "resolution": "PRESENT_LOCAL_EVIDENCE"
                    if exists
                    else UNRESOLVED,
                    "reason": None
                    if exists
                    else "registry-referenced JSON source report is absent locally",
                }
            )
    return refs


def load_source_reports(
    *,
    repo_root: Path,
    refs: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    payloads: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for ref in refs:
        path = str(ref.get("path") or "")
        if not ref.get("exists"):
            continue
        payload, error = read_json_object(resolve_path(repo_root, path))
        if error:
            failures.append(f"source report parse failure: {path} ({error})")
        elif payload is not None:
            payloads[path] = payload
    return payloads, failures


def first_json_evidence(row: Mapping[str, Any]) -> str | None:
    evidence = row.get("evidence")
    if not isinstance(evidence, list):
        return None
    for item in evidence:
        if isinstance(item, str) and item.endswith(".json"):
            return item
    return None


def registry_source_reports_for_hypothesis(
    *,
    registry: Sequence[Mapping[str, Any]],
    hypothesis_id: str,
) -> list[str]:
    for row in registry:
        if row.get("target_hypothesis_id") == hypothesis_id:
            source_reports = row.get("source_reports")
            if isinstance(source_reports, list):
                return [str(item) for item in source_reports if isinstance(item, str)]
    return []


def source_report_row_values(
    *,
    source_path: str | None,
    source_payloads: Mapping[str, Mapping[str, Any]],
    evidence_paths: Sequence[str],
) -> dict[str, Any]:
    if source_path is None:
        reason = "trial-status row has no JSON source report evidence"
        return {
            "run_id": unresolved(reason, evidence_paths),
            "data_hashes": unresolved(reason, evidence_paths),
            "prediction_hashes": unresolved(reason, evidence_paths),
            "config_hashes": unresolved(reason, evidence_paths),
            "model_family": unresolved(reason, evidence_paths),
            "feature_family": unresolved(reason, evidence_paths),
            "target_label_family": unresolved(reason, evidence_paths),
            "thresholds": unresolved(reason, evidence_paths),
            "policy_variants": unresolved(reason, evidence_paths),
            "seed_policy": unresolved(reason, evidence_paths),
            "hyperparameter_budget": unresolved(reason, evidence_paths),
            "primary_metric": unresolved(reason, evidence_paths),
            "stop_rule": unresolved(reason, evidence_paths),
            "predeclaration_timestamp": unresolved(reason, evidence_paths),
            "source_report_resolution": UNRESOLVED,
        }
    source = source_payloads.get(source_path)
    if source is None:
        reason = "referenced JSON source report is absent or unreadable locally"
        return {
            "run_id": unresolved(reason, [source_path]),
            "data_hashes": unresolved(reason, [source_path]),
            "prediction_hashes": unresolved(reason, [source_path]),
            "config_hashes": unresolved(reason, [source_path]),
            "model_family": unresolved(reason, [source_path]),
            "feature_family": unresolved(reason, [source_path]),
            "target_label_family": unresolved(reason, [source_path]),
            "thresholds": unresolved(reason, [source_path]),
            "policy_variants": unresolved(reason, [source_path]),
            "seed_policy": unresolved(reason, [source_path]),
            "hyperparameter_budget": unresolved(reason, [source_path]),
            "primary_metric": unresolved(reason, [source_path]),
            "stop_rule": unresolved(reason, [source_path]),
            "predeclaration_timestamp": unresolved(reason, [source_path]),
            "source_report_resolution": UNRESOLVED,
        }

    input_hashes = source.get("input_hashes") if isinstance(source.get("input_hashes"), Mapping) else {}
    config_hashes = {
        str(key): value
        for key, value in input_hashes.items()
        if str(key).startswith("configs/")
        or str(key).startswith("manifests/")
        or str(key).endswith(".json")
    }
    stage_summary = source.get("stage_summary") if isinstance(source.get("stage_summary"), Mapping) else {}
    gates = source.get("gates") if isinstance(source.get("gates"), list) else []
    model = source.get("model") if isinstance(source.get("model"), Mapping) else {}
    input_paths = source.get("input_paths") if isinstance(source.get("input_paths"), Mapping) else {}
    scope = source.get("scope") if isinstance(source.get("scope"), Mapping) else {}
    return {
        "run_id": source.get("run") or unresolved("source report has no run field", [source_path]),
        "data_hashes": dict(input_hashes) if input_hashes else unresolved(
            "source report has no input_hashes", [source_path]
        ),
        "prediction_hashes": not_applicable(
            "source-packet target smoke records uses_saved_predictions=false",
            [source_path],
        )
        if source.get("uses_saved_predictions") is False
        else unresolved("source report does not prove prediction hashes", [source_path]),
        "config_hashes": dict(config_hashes)
        if config_hashes
        else unresolved("source report has no config/manifest hashes", [source_path]),
        "model_family": model.get("family") or unresolved(
            "source report has no model.family", [source_path]
        ),
        "feature_family": input_paths.get("feature_cols")
        or unresolved("source report has no explicit feature family", [source_path]),
        "target_label_family": {
            "label_definition": source.get("label_definition"),
            "target_columns": source.get("target_columns"),
        },
        "thresholds": dotted_get(source, "label_definition.threshold")
        or unresolved("source report has no label threshold", [source_path]),
        "policy_variants": {
            "evaluation_mode": source.get("evaluation_mode"),
            "top_fraction": source.get("top_fraction"),
            "scope": dict(scope),
        },
        "seed_policy": unresolved("source-packet report does not record seed policy", [source_path]),
        "hyperparameter_budget": unresolved(
            "source-packet report does not record hyperparameter budget",
            [source_path],
        ),
        "primary_metric": {
            "stage_summary": dict(stage_summary),
            "event_count": source.get("event_count"),
            "failure_count": source.get("failure_count"),
        },
        "stop_rule": {
            "decision": source.get("decision"),
            "gates": gates,
        },
        "predeclaration_timestamp": source.get("created_at_utc")
        or unresolved("source report has no created_at_utc", [source_path]),
        "source_report_resolution": "PRESENT_LOCAL_EVIDENCE",
    }


def build_trial_status_candidate_rows(
    *,
    registry: Sequence[Mapping[str, Any]],
    trial_status_rows: Sequence[Mapping[str, Any]],
    source_payloads: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(trial_status_rows, start=1):
        hypothesis_id = str(row.get("hypothesis_id") or "")
        evidence = [str(item) for item in row.get("evidence", []) if isinstance(item, str)]
        registry_reports = registry_source_reports_for_hypothesis(
            registry=registry,
            hypothesis_id=hypothesis_id,
        )
        source_path = first_json_evidence(row)
        source_values = source_report_row_values(
            source_path=source_path,
            source_payloads=source_payloads,
            evidence_paths=evidence,
        )
        candidate = {
            "row_id": f"trial_status_{index:03d}",
            "row_origin": "target_trial_statuses",
            "trial_id": row.get("trial_id")
            or unresolved("trial-status row has no trial_id", evidence),
            "hypothesis_id": hypothesis_id
            or unresolved("trial-status row has no hypothesis_id", evidence),
            "stage": row.get("stage") or unresolved(
                "trial-status row has no stage",
                evidence,
            ),
            "status": row.get("status") or unresolved(
                "trial-status row has no status",
                evidence,
            ),
            "search_family_id": unresolved(
                "current local evidence does not record search_family_id",
                evidence + registry_reports,
            ),
            "multiple_testing_family_id": unresolved(
                "current local evidence does not record multiple_testing_family_id",
                evidence + registry_reports,
            ),
            "evidence_paths": evidence
            if evidence
            else unresolved("trial-status row has no evidence paths", registry_reports),
            "registry_source_reports": registry_reports,
            "notes": row.get("notes"),
        }
        candidate.update(source_values)
        rows.append(candidate)
    return rows


def build_experiment_candidate_rows(
    *,
    experiment_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(experiment_rows, start=1):
        evidence_paths = [
            str(row.get("audit_report_path"))
        ] if isinstance(row.get("audit_report_path"), str) else []
        configs = row.get("configs") if isinstance(row.get("configs"), list) else []
        rows.append(
            {
                "row_id": f"experiment_ledger_{index:03d}",
                "row_origin": "experiment_ledger",
                "trial_id": f"experiment_ledger_row_{index:03d}",
                "hypothesis_id": unresolved(
                    "legacy experiment ledger row has no hypothesis_id",
                    evidence_paths,
                ),
                "run_id": row.get("audit_report_path")
                or unresolved("legacy experiment ledger row has no audit_report_path", []),
                "stage": "legacy_experiment_ledger",
                "status": "PASS" if row.get("passed") is True else "FAIL_OR_BLOCKED",
                "search_family_id": unresolved(
                    "legacy experiment ledger row has no search_family_id",
                    evidence_paths,
                ),
                "multiple_testing_family_id": unresolved(
                    "legacy experiment ledger row has no multiple_testing_family_id",
                    evidence_paths,
                ),
                "data_hashes": unresolved(
                    "legacy experiment ledger row has no data hashes",
                    evidence_paths,
                ),
                "prediction_hashes": unresolved(
                    "legacy experiment ledger row has no prediction hashes",
                    evidence_paths,
                ),
                "config_hashes": configs
                if configs
                else unresolved("legacy experiment ledger row has no configs", evidence_paths),
                "model_family": unresolved(
                    "legacy experiment ledger row has no model family",
                    evidence_paths,
                ),
                "feature_family": unresolved(
                    "legacy experiment ledger row has no feature family",
                    evidence_paths,
                ),
                "target_label_family": unresolved(
                    "legacy experiment ledger row has no target/label family",
                    evidence_paths,
                ),
                "thresholds": unresolved(
                    "legacy experiment ledger row has no threshold/policy variant metadata",
                    evidence_paths,
                ),
                "policy_variants": {
                    "cost_assumptions": row.get("cost_assumptions"),
                    "profile": row.get("profile"),
                    "markets": row.get("markets"),
                    "years": row.get("years"),
                },
                "seed_policy": unresolved(
                    "legacy experiment ledger row has no seed policy",
                    evidence_paths,
                ),
                "hyperparameter_budget": unresolved(
                    "legacy experiment ledger row has no hyperparameter budget",
                    evidence_paths,
                ),
                "primary_metric": {
                    "net_return_dollars": row.get("net_return_dollars"),
                    "gross_return_dollars": row.get("gross_return_dollars"),
                    "trades": row.get("trades"),
                    "passed": row.get("passed"),
                    "robustness_status": row.get("robustness_status"),
                },
                "stop_rule": {
                    "pass_fail_reason": row.get("pass_fail_reason"),
                    "robustness_checks": row.get("robustness_checks"),
                },
                "evidence_paths": evidence_paths
                if evidence_paths
                else unresolved("legacy experiment ledger row has no evidence path", []),
                "predeclaration_timestamp": row.get("timestamp")
                or unresolved("legacy experiment ledger row has no timestamp", evidence_paths),
            }
        )
    return rows


def artifact_hashes(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, Mapping) else {}


def phase8_overall_metrics(metrics: Mapping[str, Any] | None) -> Mapping[str, Any]:
    overall = dotted_get(metrics, "metrics.overall")
    return overall if isinstance(overall, Mapping) else {}


def build_current_run_candidate_row(
    *,
    wfa: Mapping[str, Any] | None,
    predictions: Mapping[str, Any] | None,
    metrics: Mapping[str, Any] | None,
    promotion: Mapping[str, Any] | None,
    statistical: Mapping[str, Any] | None,
) -> dict[str, Any]:
    evidence_paths = [
        WFA_REPORT.as_posix(),
        PREDICTIONS_MANIFEST.as_posix(),
        PHASE8_METRICS.as_posix(),
        PHASE8_PROMOTION.as_posix(),
        STATISTICAL_SUMMARY.as_posix(),
    ]
    wfa = wfa or {}
    predictions = predictions or {}
    metrics = metrics or {}
    promotion = promotion or {}
    statistical = statistical or {}
    model_risk_gate = predictions.get("model_risk_gate")
    if not isinstance(model_risk_gate, Mapping):
        model_risk_gate = {}
    model_families = model_risk_gate.get("model_families")
    model_ids = model_risk_gate.get("model_ids")
    model_rows = wfa.get("models") if isinstance(wfa.get("models"), list) else []
    targets = sorted(
        {
            str(item.get("target"))
            for item in model_rows
            if isinstance(item, Mapping) and item.get("target")
        }
    )
    promotion_gate = promotion.get("promotion_gate")
    if not isinstance(promotion_gate, Mapping):
        promotion_gate = {}
    promotion_metric_gate = promotion.get("promotion_metric_gate")
    if not isinstance(promotion_metric_gate, Mapping):
        promotion_metric_gate = {}
    required_checks = trial.required_stat_checks(statistical)
    return {
        "row_id": "current_wfa_phase8_statistical_run_001",
        "row_origin": "current_wfa_phase8_statistical_run",
        "trial_id": "tier1_core_phase6_full_predictions_20260706_current_line",
        "hypothesis_id": unresolved(
            "current WFA/Phase8/statistical run is not linked to a target hypothesis ID",
            evidence_paths,
        ),
        "run_id": wfa.get("run") or predictions.get("run") or promotion.get("run"),
        "stage": "phase6_phase8_statistical_current_line",
        "status": "FAIL_CLOSED_NO_ALPHA_EVIDENCE",
        "search_family_id": unresolved(
            "current WFA/Phase8/statistical reports do not record search_family_id",
            evidence_paths,
        ),
        "multiple_testing_family_id": unresolved(
            "current WFA/Phase8/statistical reports do not record multiple_testing_family_id",
            evidence_paths,
        ),
        "data_hashes": artifact_hashes(predictions, "input_file_hashes")
        or unresolved("prediction manifest has no input_file_hashes", evidence_paths),
        "prediction_hashes": artifact_hashes(predictions, "output_file_hashes")
        or unresolved("prediction manifest has no output_file_hashes", evidence_paths),
        "config_hashes": {
            "model_config_hash": predictions.get("model_config_hash"),
            "feature_config_hash": predictions.get("feature_config_hash"),
            "profile_config_hash": predictions.get("profile_config_hash"),
            "split_plan_config_hash": predictions.get("split_plan_config_hash"),
        },
        "model_family": model_families
        if model_families
        else [item.get("family") for item in model_rows if isinstance(item, Mapping)],
        "model_ids": model_ids,
        "feature_family": wfa.get("matrix")
        or unresolved("WFA report has no matrix/feature family", evidence_paths),
        "target_label_family": targets
        if targets
        else unresolved("WFA report has no model target list", evidence_paths),
        "thresholds": promotion_gate.get("gate_config")
        or unresolved("Phase 8 report has no promotion gate config", evidence_paths),
        "policy_variants": {
            "promotion_gate": promotion_gate,
            "promotion_metric_gate": promotion_metric_gate,
        },
        "seed_policy": model_risk_gate.get("seed_policy")
        or unresolved("prediction manifest has no seed policy", evidence_paths),
        "hyperparameter_budget": model_risk_gate.get("hyperparameter_budget")
        or unresolved("prediction manifest has no hyperparameter budget", evidence_paths),
        "primary_metric": {
            "phase8_overall": dict(phase8_overall_metrics(metrics)),
            "prediction_count": predictions.get("prediction_count"),
            "policy_trade_count": statistical.get("policy_trade_count"),
        },
        "stop_rule": {
            "promoted": promotion.get("promoted"),
            "research_alpha_ready": promotion.get("research_alpha_ready"),
            "model_promotion_allowed": promotion.get("model_promotion_allowed"),
            "promotion_blockers": dotted_get(
                promotion,
                "promotion_gate.promotion_blockers",
            ),
            "statistical_required_checks": dict(required_checks),
        },
        "evidence_paths": evidence_paths,
        "predeclaration_timestamp": unresolved(
            "current WFA/Phase8/statistical run has no predeclaration timestamp",
            evidence_paths,
        ),
    }


def row_missing_required_fields(row: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in row:
            missing.append(field)
    return missing


def unresolved_field_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for field in REQUIRED_FIELDS:
            if is_unresolved(row.get(field)):
                counts[field] += 1
    return dict(sorted(counts.items()))


def validate_candidate_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    source_report_refs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    row_failures: list[dict[str, Any]] = []
    failure_messages: list[str] = []
    for row in rows:
        missing = row_missing_required_fields(row)
        if missing:
            row_failures.append({"row_id": row.get("row_id"), "missing_fields": missing})
    if row_failures:
        failure_messages.append(f"candidate rows missing required fields: {row_failures}")
    missing_refs = [
        str(ref.get("path"))
        for ref in source_report_refs
        if ref.get("exists") is False
    ]
    unresolved_paths = {
        str(ref.get("path"))
        for ref in source_report_refs
        if ref.get("resolution") == UNRESOLVED
    }
    silent = sorted(set(missing_refs) - unresolved_paths)
    if silent:
        failure_messages.append(
            "missing registry JSON source reports were not explicitly marked unresolved: "
            f"{silent}"
        )
    return row_failures, failure_messages


def find_bucket(payload: Mapping[str, Any] | None, bucket_id: str) -> Mapping[str, Any]:
    return trial.find_bucket(payload, bucket_id)


def find_closeout_bucket(payload: Mapping[str, Any] | None, bucket_id: str) -> Mapping[str, Any]:
    return trial.find_closeout_bucket(payload, bucket_id)


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_input_overrides: Mapping[str, Path] | None = None,
    source_report_ref_overrides: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    reports_root = resolve_path(repo_root, reports_root).resolve()
    paths = dict(REQUIRED_INPUTS)
    if required_input_overrides:
        paths.update(required_input_overrides)
    if git_status_lines is None:
        git_status = inventory.collect_git_status(repo_root)
        status_lines = list(git_status["status_lines"])
        git_error = git_status["error"]
        git_returncode = git_status["returncode"]
    else:
        status_lines = list(git_status_lines)
        git_error = None
        git_returncode = 0
    dirty_map = inventory.build_dirty_path_map(status_lines)
    evidence_rows = input_evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    payloads, payload_failures = load_payloads(repo_root=repo_root, paths=paths)
    experiment_rows, experiment_errors = read_jsonl_objects(
        resolve_path(repo_root, paths["experiment_ledger"])
    )
    trial_status_rows, trial_status_errors = read_jsonl_objects(
        resolve_path(repo_root, paths["target_trial_statuses"])
    )
    registry = registry_rows(payloads.get("target_registry"))
    source_refs = list(source_report_ref_overrides) if source_report_ref_overrides is not None else (
        registry_json_source_report_refs(registry=registry, repo_root=repo_root)
    )
    source_payloads, source_failures = load_source_reports(repo_root=repo_root, refs=source_refs)
    candidate_rows = (
        build_trial_status_candidate_rows(
            registry=registry,
            trial_status_rows=trial_status_rows,
            source_payloads=source_payloads,
        )
        + build_experiment_candidate_rows(experiment_rows=experiment_rows)
        + [
            build_current_run_candidate_row(
                wfa=payloads.get("wfa_report"),
                predictions=payloads.get("predictions_manifest"),
                metrics=payloads.get("phase8_metrics"),
                promotion=payloads.get("phase8_promotion"),
                statistical=payloads.get("statistical_summary"),
            )
        ]
    )
    candidate_row_failures, candidate_validation_failures = validate_candidate_rows(
        rows=candidate_rows,
        source_report_refs=source_refs,
    )
    output_rel = rel(reports_root, repo_root)
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    required_paths = {path.as_posix() for path in paths.values()}
    present_paths = {
        str(item.get("path")) for item in evidence_rows if item.get("exists")
    }
    missing_paths = sorted(required_paths - present_paths)
    check(
        checks,
        failures,
        name="required_input_files_present",
        passed=not missing_paths,
        failure=f"missing required schema-remediation inputs: {missing_paths}",
        evidence=sorted(required_paths),
        details={"missing_paths": missing_paths},
    )
    check(
        checks,
        failures,
        name="output_root_report_only",
        passed=output_rel.startswith("reports/master_audit/") and not output_rel.endswith("/"),
        failure=f"invalid report output root: {output_rel}",
        details={"reports_root": output_rel},
    )
    upstream = payloads.get("upstream_reconciliation")
    check(
        checks,
        failures,
        name="upstream_reconciliation_passes_and_remains_blocked",
        passed=upstream is not None
        and upstream.get("status") == trial.PASS_STATUS
        and dotted_get(upstream, "summary.trial_ledger_search_path_complete") is False
        and dotted_get(upstream, "summary.pbo_status") == "FAIL_MISSING_TRIAL_LOG"
        and dotted_get(upstream, "summary.deflated_sharpe_status") == "FAIL_MISSING_TRIAL_LOG"
        and dotted_get(upstream, "summary.multiple_testing_status") == "FAIL_MISSING_TRIAL_LOG"
        and dotted_get(upstream, "summary.statistical_validity_ready") is False
        and dotted_get(upstream, "summary.model_trust_ready") is False
        and dotted_get(upstream, "summary.promotion_allowed") is False,
        failure="upstream trial-ledger/search-path reconciliation is missing, failed, or no longer blocked",
        evidence=[UPSTREAM_RECONCILIATION.as_posix()],
        details={
            "status": None if upstream is None else upstream.get("status"),
            "summary": None if upstream is None else upstream.get("summary"),
        },
    )
    registry_ids = {
        str(row.get("target_hypothesis_id"))
        for row in registry
        if row.get("target_hypothesis_id")
    }
    unknown_trial_hypotheses = trial.unknown_trial_hypotheses(
        trial_rows=trial_status_rows,
        registry_ids=registry_ids,
    )
    check(
        checks,
        failures,
        name="registry_and_ledgers_parse_with_expected_counts",
        passed=not experiment_errors
        and not trial_status_errors
        and len(experiment_rows) == EXPECTED_EXPERIMENT_LEDGER_ROWS
        and len(registry) == EXPECTED_REGISTRY_HYPOTHESES
        and len(trial_status_rows) == EXPECTED_TRIAL_STATUS_ROWS
        and not unknown_trial_hypotheses,
        failure="experiment ledger, target registry, or target trial statuses failed parse/count/identity checks",
        evidence=[
            EXPERIMENT_LEDGER.as_posix(),
            TARGET_REGISTRY.as_posix(),
            TARGET_TRIAL_STATUSES.as_posix(),
        ],
        details={
            "experiment_row_count": len(experiment_rows),
            "registry_hypothesis_count": len(registry),
            "trial_status_row_count": len(trial_status_rows),
            "experiment_errors": list(experiment_errors),
            "trial_status_errors": list(trial_status_errors),
            "unknown_trial_hypotheses": unknown_trial_hypotheses,
        },
    )
    present_source_refs = [ref for ref in source_refs if ref.get("exists") is True]
    missing_source_refs = [ref for ref in source_refs if ref.get("exists") is False]
    check(
        checks,
        failures,
        name="registry_source_report_reference_counts_preserved",
        passed=len(source_refs) == EXPECTED_REGISTRY_JSON_SOURCE_REFS
        and len(present_source_refs) == EXPECTED_PRESENT_REGISTRY_JSON_SOURCE_REFS
        and len(missing_source_refs) == EXPECTED_MISSING_REGISTRY_JSON_SOURCE_REFS
        and all(ref.get("resolution") == UNRESOLVED for ref in missing_source_refs),
        failure=(
            "registry JSON source-report reference counts changed or missing refs were not "
            "explicitly unresolved"
        ),
        evidence=[TARGET_REGISTRY.as_posix()],
        details={
            "json_source_report_ref_count": len(source_refs),
            "present_json_source_report_ref_count": len(present_source_refs),
            "missing_json_source_report_ref_count": len(missing_source_refs),
            "missing_json_source_reports": [ref.get("path") for ref in missing_source_refs],
        },
    )
    check(
        checks,
        failures,
        name="candidate_rows_are_schema_complete",
        passed=not candidate_row_failures,
        failure="candidate trial/search ledger rows are missing required fields",
        details={
            "candidate_row_count": len(candidate_rows),
            "row_failures": candidate_row_failures,
            "required_fields": list(REQUIRED_FIELDS),
        },
    )
    check(
        checks,
        failures,
        name="missing_or_insufficient_evidence_is_explicit",
        passed=not candidate_validation_failures
        and any(
            is_unresolved(row.get("search_family_id"))
            or is_unresolved(row.get("multiple_testing_family_id"))
            for row in candidate_rows
        ),
        failure="missing source or search-path evidence was silently inferred",
        details={
            "candidate_validation_failures": candidate_validation_failures,
            "unresolved_field_counts": unresolved_field_counts(candidate_rows),
        },
    )
    statistical = payloads.get("statistical_summary")
    required_checks = trial.required_stat_checks(statistical)
    pbo = required_checks.get("pbo", {})
    deflated = required_checks.get("deflated_sharpe", {})
    multiple = required_checks.get("multiple_testing_adjustment", {})
    matrix = payloads.get("alpha_gap_matrix")
    closeout = payloads.get("alpha_completion_closeout")
    check(
        checks,
        failures,
        name="pbo_deflated_sharpe_multiple_testing_remain_blocked",
        passed=statistical is not None
        and statistical.get("status") == "FAIL"
        and statistical.get("statistical_validity_ready") is False
        and pbo.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and deflated.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and multiple.get("status") == "FAIL_MISSING_TRIAL_LOG"
        and find_bucket(matrix, "statistical_pbo").get("status") == "MISSING_EVIDENCE"
        and find_bucket(matrix, "statistical_deflated_sharpe").get("status")
        == "MISSING_EVIDENCE"
        and find_bucket(matrix, "statistical_multiple_testing").get("status")
        == "MISSING_EVIDENCE"
        and find_closeout_bucket(closeout, "statistical_pbo").get("closeout_classification")
        == "missing_required_evidence"
        and find_closeout_bucket(closeout, "statistical_deflated_sharpe").get(
            "closeout_classification"
        )
        == "missing_required_evidence"
        and find_closeout_bucket(closeout, "statistical_multiple_testing").get(
            "closeout_classification"
        )
        == "missing_required_evidence",
        failure="PBO, Deflated Sharpe, or multiple-testing was upgraded or no longer blocked",
        evidence=[
            STATISTICAL_SUMMARY.as_posix(),
            ALPHA_GAP_MATRIX.as_posix(),
            ALPHA_COMPLETION_CLOSEOUT.as_posix(),
        ],
        details={
            "pbo": dict(pbo),
            "deflated_sharpe": dict(deflated),
            "multiple_testing": dict(multiple),
        },
    )
    promotion = payloads.get("phase8_promotion")
    run_status = payloads.get("run_status")
    check(
        checks,
        failures,
        name="readiness_and_non_approval_flags_remain_false",
        passed=promotion is not None
        and promotion.get("promoted") is False
        and promotion.get("research_alpha_ready") is False
        and promotion.get("model_promotion_allowed") is False
        and dotted_get(run_status, "summary.data_model_commands_executed") is False
        and dotted_get(run_status, "summary.wfa_modeling_executed") is False
        and dotted_get(run_status, "summary.predictions_executed") is False
        and dotted_get(run_status, "summary.provider_network_calls_executed") is False
        and dotted_get(run_status, "summary.promotion_or_freeze_or_holdout_executed")
        is False
        and dotted_get(run_status, "summary.paper_or_live_executed") is False
        and all(value is False for value in NON_APPROVAL.values()),
        failure="readiness, promotion, or forbidden execution flag was upgraded",
        evidence=[PHASE8_PROMOTION.as_posix(), RUN_STATUS.as_posix()],
        details={
            "promotion": {
                "promoted": None if promotion is None else promotion.get("promoted"),
                "research_alpha_ready": None
                if promotion is None
                else promotion.get("research_alpha_ready"),
                "model_promotion_allowed": None
                if promotion is None
                else promotion.get("model_promotion_allowed"),
            },
            "non_approval": dict(NON_APPROVAL),
        },
    )
    for item in evidence_rows:
        if item.get("path") in required_paths and item.get("read_error"):
            failures.append(str(item["read_error"]))
    failures.extend(payload_failures)
    failures.extend(experiment_errors)
    failures.extend(trial_status_errors)
    failures.extend(source_failures)
    failures.extend(candidate_validation_failures)
    failures = list(dict.fromkeys(failures))
    status = PASS_STATUS if not failures else FAIL_STATUS
    unresolved_counts = unresolved_field_counts(candidate_rows)
    summary = {
        "status": status,
        "failure_count": len(failures),
        "check_count": len(checks),
        "passed_check_count": sum(1 for item in checks if item["status"] == "PASS"),
        "failed_check_count": sum(1 for item in checks if item["status"] == "FAIL"),
        "trial_search_ledger_schema_remediation_plan_ready": status == PASS_STATUS,
        "trial_ledger_search_path_complete": False,
        "pbo_status": "FAIL_MISSING_TRIAL_LOG",
        "deflated_sharpe_status": "FAIL_MISSING_TRIAL_LOG",
        "multiple_testing_status": "FAIL_MISSING_TRIAL_LOG",
        "pbo_applicability_ready": False,
        "deflated_sharpe_applicability_ready": False,
        "multiple_testing_applicability_ready": False,
        "statistical_validity_ready": False,
        "model_trust_ready": False,
        "promotion_allowed": False,
        "paper_live_ready": False,
        "production_ready": False,
        "experiment_ledger_row_count": len(experiment_rows),
        "target_registry_hypothesis_count": len(registry),
        "target_trial_status_row_count": len(trial_status_rows),
        "candidate_trial_search_ledger_row_count": len(candidate_rows),
        "registry_json_source_report_ref_count": len(source_refs),
        "present_registry_json_source_report_ref_count": len(present_source_refs),
        "missing_registry_json_source_report_ref_count": len(missing_source_refs),
        "required_fields": list(REQUIRED_FIELDS),
        "unresolved_field_counts": unresolved_counts,
        "candidate_row_origins": dict(sorted(Counter(row.get("row_origin") for row in candidate_rows).items())),
        "current_git_status_short_count": len(status_lines),
        "git_status_error": git_error,
        "git_status_returncode": git_returncode,
        **dict(NON_APPROVAL),
    }
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "master_audit_trial_search_ledger_schema_remediation_plan_report_only",
            "evidence_mode": "existing_local_registry_ledger_report_json_jsonl_md_only",
            "reports_root": output_rel,
            "ledger_mutation_scope": "none",
            "data_model_scope": "none",
            "provider_scope": "none",
            "allowed_inputs": [
                rel(resolve_path(repo_root, path), repo_root) for path in paths.values()
            ],
        },
        "summary": summary,
        "input_evidence": evidence_rows,
        "source_report_reference_inventory": list(source_refs),
        "candidate_trial_search_ledger_rows": candidate_rows,
        "checks": checks,
        "failures": failures,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "non_approval": dict(NON_APPROVAL),
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Plan any ledger backfill only after reviewing this row-by-row candidate "
            "map; do not mutate ledgers, run data/model commands, refresh Phase 8, "
            "or upgrade statistical validity without separate approval."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Master Audit Trial/Search Ledger Schema Remediation Plan",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Checks: `{summary['passed_check_count']}` passed, `{summary['failed_check_count']}` failed",
        f"- Candidate rows: `{summary['candidate_trial_search_ledger_row_count']}`",
        f"- Trial-ledger/search-path complete: `{summary['trial_ledger_search_path_complete']}`",
        f"- Registry JSON source-report refs: `{summary['registry_json_source_report_ref_count']}` total, `{summary['present_registry_json_source_report_ref_count']}` present, `{summary['missing_registry_json_source_report_ref_count']}` missing",
        f"- PBO applicability ready: `{summary['pbo_applicability_ready']}`",
        f"- Deflated Sharpe applicability ready: `{summary['deflated_sharpe_applicability_ready']}`",
        f"- Multiple-testing applicability ready: `{summary['multiple_testing_applicability_ready']}`",
        f"- Statistical-validity ready: `{summary['statistical_validity_ready']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        "",
        "## Required Fields",
        "",
        f"- `{summary['required_fields']}`",
        "",
        "## Unresolved Field Counts",
        "",
        f"- `{summary['unresolved_field_counts']}`",
        "",
        "## Source Report References",
        "",
        "| Hypothesis | Path | Exists | Resolution |",
        "| --- | --- | --- | --- |",
    ]
    for item in report["source_report_reference_inventory"]:
        lines.append(
            "| `{hypothesis}` | `{path}` | `{exists}` | `{resolution}` |".format(
                hypothesis=item.get("hypothesis_id"),
                path=item.get("path"),
                exists=item.get("exists"),
                resolution=item.get("resolution"),
            )
        )
    lines.extend(["", "## Candidate Rows", ""])
    for row in report["candidate_trial_search_ledger_rows"]:
        lines.append(
            "- `{row_id}` origin=`{origin}` trial=`{trial}` hypothesis=`{hypothesis}` stage=`{stage}` status=`{status}`".format(
                row_id=row.get("row_id"),
                origin=row.get("row_origin"),
                trial=row.get("trial_id"),
                hypothesis=row.get("hypothesis_id"),
                stage=row.get("stage"),
                status=row.get("status"),
            )
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Failure |", "| --- | --- | --- |"])
    for item in report["checks"]:
        lines.append(
            "| `{name}` | `{status}` | {failure} |".format(
                name=item["name"],
                status=item["status"],
                failure=item.get("failure") or "",
            )
        )
    lines.extend(["", "## Failures", ""])
    failures = report.get("failures", [])
    lines.extend([f"- {failure}" for failure in failures] or ["- None"])
    lines.extend(
        [
            "",
            "## Non-Execution Statement",
            "",
            "- This remediation plan did not mutate experiment ledgers, target registries, target trial-status ledgers, data, models, predictions, Phase 8 outputs, provider state, promotion state, artifact freeze state, final holdout state, paper/live state, cleanup state, staging, commits, pushes, or gap maps.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: Mapping[str, Any], reports_root: Path) -> tuple[Path, Path]:
    reports_root.mkdir(parents=True, exist_ok=True)
    json_path = reports_root / REPORT_JSON
    md_path = reports_root / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report) + "\n", encoding="utf-8")
    return json_path, md_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    reports_root = resolve_path(repo_root, args.reports_root)
    report = build_report(repo_root=repo_root, reports_root=reports_root)
    json_path, md_path = write_report(report, reports_root)
    print(
        f"{STAGE} status={report['status']} failures={report['summary']['failure_count']} "
        f"candidate_rows={report['summary']['candidate_trial_search_ledger_row_count']} "
        f"missing_source_reports="
        f"{report['summary']['missing_registry_json_source_report_ref_count']} "
        f"trial_ledger_search_path_complete="
        f"{report['summary']['trial_ledger_search_path_complete']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
