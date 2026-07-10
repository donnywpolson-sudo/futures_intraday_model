#!/usr/bin/env python3
"""Build a report-only workspace commit-scope inventory.

This command classifies the current dirty worktree into reviewable scopes. It
does not stage, commit, push, clean up, move, delete, revert, run data/model
commands, run WFA/modeling, generate predictions, refresh Phase 8, call
providers/network, promote, freeze, holdout, paper/live, or read parquet/model
artifacts.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from scripts.validation import build_master_audit_run_status as inventory


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE = "workspace_commit_scope_plan"
PASS_STATUS = "PASS_WORKSPACE_COMMIT_SCOPE_PLAN_REPORT_ONLY"
FAIL_STATUS = "FAIL_WORKSPACE_COMMIT_SCOPE_PLAN_REPORT_ONLY"

DEFAULT_REPORTS_ROOT = Path("reports/repo_hygiene/workspace_commit_scope_20260709")
REPORT_JSON = "workspace_commit_scope_plan.json"
REPORT_MD = "workspace_commit_scope_plan.md"

REQUIRED_INPUTS = {
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "master_audit": Path("MASTER_AUDIT.md"),
    "master_audit_closeout": Path(
        "reports/master_audit/master_audit_closeout_20260709/master_audit_closeout.json"
    ),
}

PROTECTED_OUTPUT_ROOTS = ("data/", "configs/", "scripts/", "models/", "predictions/")

NON_APPROVAL = {
    "data_model_commands_executed": False,
    "wfa_modeling_executed": False,
    "prediction_generation_executed": False,
    "phase8_refresh_executed": False,
    "provider_network_calls_executed": False,
    "promotion_executed": False,
    "artifact_freeze_executed": False,
    "final_holdout_executed": False,
    "paper_live_executed": False,
    "cleanup_executed": False,
    "staging_executed": False,
    "commit_executed": False,
    "push_executed": False,
    "delete_move_rename_revert_executed": False,
    "parquet_or_model_artifact_read_executed": False,
}


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    return inventory.resolve_path(repo_root, path)


def rel(path: Path, repo_root: Path) -> str:
    return inventory.rel(path, repo_root)


def read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    return inventory.read_json_object(path)


def dotted_get(payload: Mapping[str, Any] | None, dotted_key: str) -> Any:
    return inventory.dotted_get(payload, dotted_key)


def parse_status_line(line: str) -> dict[str, str] | None:
    if len(line) < 4:
        return None
    marker = line[:2]
    path_text = line[3:].strip()
    if not path_text:
        return None
    if " -> " in path_text:
        path_text = path_text.split(" -> ", 1)[1]
    return {
        "raw": line,
        "status": marker.strip() or marker,
        "path": path_text.replace("\\", "/"),
    }


def parse_status_lines(status_lines: Sequence[str]) -> list[dict[str, str]]:
    return [parsed for line in status_lines if (parsed := parse_status_line(line))]


def classify_path(path: str) -> tuple[str, str, bool]:
    normalized = path.replace("\\", "/").rstrip("/")
    closeout_paths = {
        "scripts/validation/build_workspace_commit_scope_plan.py",
        "tests/validation/test_build_workspace_commit_scope_plan.py",
        "scripts/validation/build_master_audit_closeout.py",
        "tests/validation/test_build_master_audit_closeout.py",
    }
    if normalized in closeout_paths or normalized.startswith(
        "reports/repo_hygiene/workspace_commit_scope_20260709"
    ) or normalized.startswith("reports/master_audit/master_audit_closeout_20260709"):
        return (
            "workspace_or_master_audit_closeout_scope",
            "Review with repo-hygiene/Master Audit closeout scope; do not auto-stage.",
            True,
        )
    if normalized.startswith("reports/master_audit/") or (
        normalized.startswith("scripts/validation/build_master_audit_")
        or normalized.startswith("tests/validation/test_build_master_audit_")
        or normalized == "MASTER_AUDIT.md"
    ):
        return (
            "master_audit_report_only_suite",
            "Review as the completed Master Audit report-only suite.",
            False,
        )
    if normalized in {"AGENTS.md", "AUDIT.md", "CODEX_HANDOFF.md", "PROJECT_OUTLINE.md"}:
        return (
            "coordination_docs",
            "Review as coordination documentation; verify source-of-truth alignment.",
            False,
        )
    if normalized.startswith("configs/"):
        return (
            "config_changes",
            "Review separately because config changes can stale source-hash evidence.",
            False,
        )
    if normalized.startswith("scripts/prop_account_simulation") or normalized.startswith(
        "tests/prop_account_simulation"
    ) or normalized.startswith("configs/prop_rules") or normalized.startswith(
        "docs/apex_50k"
    ) or normalized.endswith("test_prop_account_rules.py") or normalized.endswith(
        "prop_account_rules.py"
    ):
        return (
            "prop_account_simulation",
            "Review as isolated prop-account simulator/connector work.",
            False,
        )
    if normalized.startswith("scripts/phase5_wfa/") or "hardened" in normalized or any(
        token in normalized
        for token in (
            "build_phase5_v2",
            "build_phase6_hardened",
            "build_phase7_hardened",
            "validate_hardened_wfa_split_plan",
        )
    ):
        return (
            "hardened_split_decision_work",
            "Review as hardened split/design/preflight work; do not run WFA.",
            False,
        )
    if any(
        token in normalized
        for token in (
            "audit_final_feature_matrix_leakage",
            "audit_phase2_causal_session_normalization",
            "audit_wfa_split_contamination",
            "build_target_timing_audit",
            "build_phase5_v2_wfa_preflight_decision",
        )
    ):
        return (
            "report_only_evidence_audits",
            "Review as report-only evidence audit work.",
            False,
        )
    if any(
        token in normalized
        for token in (
            "build_execution_realism_primary_evidence_intake",
            "build_markov_regime_es_intraday_diagnostic",
            "enforce_model_trust_gate",
            "markov_regime",
        )
    ):
        return (
            "execution_realism_and_diagnostic_work",
            "Review as model-trust evidence intake or diagnostic work.",
            False,
        )
    if normalized == "scripts/export_live_shadow_bundle.py" or normalized.startswith("tests/live/"):
        return (
            "live_shadow_export_work",
            "Review separately; live/paper readiness remains blocked by closeout.",
            False,
        )
    if normalized.startswith("scripts/phase") or normalized.startswith("tests/phase"):
        return (
            "phase_pipeline_code_changes",
            "Review separately because these can affect protected quant logic.",
            False,
        )
    if normalized.startswith("scripts/validation/") or normalized.startswith("tests/validation/"):
        return (
            "validation_guard_changes",
            "Review as validation/guard changes; avoid broad behavioral assumptions.",
            False,
        )
    if normalized.startswith("docs/"):
        return (
            "docs_and_design_packets",
            "Review as documentation/design packet work.",
            False,
        )
    if normalized.startswith("reports/"):
        return (
            "generated_or_report_artifacts",
            "Generated/report artifacts should remain unstaged unless explicitly approved.",
            False,
        )
    return (
        "manual_review_required",
        "No specific bucket matched; require human review before staging.",
        False,
    )


def required_input_evidence(
    *,
    repo_root: Path,
    dirty_map: Mapping[str, str],
    paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    json_fields = {
        "master_audit_closeout": {
            "status": "status",
            "failure_count": "summary.failure_count",
            "closeout_classification": "summary.closeout_classification",
            "full_master_audit_accepted": "summary.full_master_audit_accepted",
            "model_trust_ready": "summary.model_trust_ready",
            "promotion_allowed": "summary.promotion_allowed",
            "artifact_freeze_ready": "summary.artifact_freeze_ready",
            "final_holdout_ready": "summary.final_holdout_ready",
            "paper_live_ready": "summary.paper_live_ready",
            "production_ready": "summary.production_ready",
        }
    }
    return [
        inventory.evidence_file(
            repo_root=repo_root,
            relative_path=path,
            json_fields=json_fields.get(name),
            dirty_map=dirty_map,
        )
        for name, path in paths.items()
    ]


def load_required_payloads(
    repo_root: Path,
    paths: Mapping[str, Path],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    payloads: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for name, path in paths.items():
        resolved = resolve_path(repo_root, path)
        if resolved.suffix.lower() != ".json":
            continue
        payload, error = read_json_object(resolved)
        if error:
            failures.append(f"required JSON input unavailable: {path.as_posix()} ({error})")
        elif payload is not None:
            payloads[name] = payload
    return payloads, failures


def build_classified_entries(status_entries: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    classified: list[dict[str, Any]] = []
    for entry in status_entries:
        bucket, guidance, closeout_scope = classify_path(entry["path"])
        generated_caution = (
            entry["path"].startswith("reports/")
            or entry["path"].startswith("data/")
            or bucket == "generated_or_report_artifacts"
        )
        classified.append(
            {
                "path": entry["path"],
                "status": entry["status"],
                "raw_status_line": entry["raw"],
                "bucket": bucket,
                "guidance": guidance,
                "likely_current_scope": closeout_scope,
                "generated_or_data_artifact_caution": generated_caution,
                "auto_stage_allowed": False,
                "human_review_required": True,
            }
        )
    return classified


def grouped_counts(entries: Sequence[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(entry.get(key)) for entry in entries).items()))


def build_commit_scopes(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(str(entry["bucket"]), []).append(dict(entry))
    scopes: list[dict[str, Any]] = []
    for bucket, bucket_entries in sorted(grouped.items()):
        paths = sorted(entry["path"] for entry in bucket_entries)
        scopes.append(
            {
                "bucket": bucket,
                "path_count": len(paths),
                "paths": paths,
                "recommended_action": bucket_entries[0]["guidance"],
                "auto_stage_allowed": False,
                "commit_candidate": bucket not in {"manual_review_required", "generated_or_report_artifacts"},
                "requires_human_review_before_staging": True,
            }
        )
    return scopes


def validate_closeout(closeout: Mapping[str, Any] | None) -> list[str]:
    if not closeout:
        return ["Master Audit closeout payload is missing"]
    summary = closeout.get("summary")
    if not isinstance(summary, Mapping):
        return ["Master Audit closeout summary is missing"]
    failures: list[str] = []
    expected = {
        "status": "PASS_MASTER_AUDIT_CLOSEOUT_REPORT_ONLY",
        "summary.failure_count": 0,
        "summary.closeout_classification": "REPORT_ONLY_CLOSEOUT_BLOCKED_NOT_READY",
        "summary.full_master_audit_accepted": False,
        "summary.model_trust_ready": False,
        "summary.promotion_allowed": False,
        "summary.artifact_freeze_ready": False,
        "summary.final_holdout_ready": False,
        "summary.paper_live_ready": False,
        "summary.production_ready": False,
    }
    for dotted_key, expected_value in expected.items():
        actual = closeout.get(dotted_key) if "." not in dotted_key else dotted_get(closeout, dotted_key)
        if actual != expected_value:
            failures.append(
                f"Master Audit closeout field {dotted_key} expected {expected_value!r}, got {actual!r}"
            )
    return failures


def validate_classification(entries: Sequence[Mapping[str, Any]], raw_count: int) -> list[str]:
    failures: list[str] = []
    paths = [str(entry["path"]) for entry in entries]
    if len(entries) != raw_count:
        failures.append(f"classified entry count {len(entries)} does not match git status count {raw_count}")
    duplicates = sorted(path for path, count in Counter(paths).items() if count > 1)
    if duplicates:
        failures.append(f"duplicate path classifications found: {duplicates}")
    unclassified = sorted(
        entry["path"] for entry in entries if entry.get("bucket") == "manual_review_required"
    )
    if unclassified:
        failures.append(f"manual-review-only unclassified paths require bucket update: {unclassified}")
    if any(entry.get("auto_stage_allowed") is not False for entry in entries):
        failures.append("at least one path was incorrectly marked auto-stage allowed")
    return failures


def build_report(
    *,
    repo_root: Path,
    reports_root: Path,
    generated_at_utc: str | None = None,
    git_status_lines: Sequence[str] | None = None,
    required_input_overrides: Mapping[str, Path] | None = None,
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
    status_entries = parse_status_lines(status_lines)
    classified_entries = build_classified_entries(status_entries)
    payloads, input_failures = load_required_payloads(repo_root, paths)
    evidence = required_input_evidence(repo_root=repo_root, dirty_map=dirty_map, paths=paths)
    failures = list(input_failures)
    for item in evidence:
        if not item.get("exists") or item.get("read_error"):
            failures.append(f"required input unavailable: {item.get('path')}")
    failures.extend(validate_closeout(payloads.get("master_audit_closeout")))
    failures.extend(validate_classification(classified_entries, len(status_entries)))
    output_rel = rel(reports_root, repo_root)
    if output_rel == "." or output_rel.startswith(PROTECTED_OUTPUT_ROOTS):
        failures.append(f"invalid report output root for workspace commit-scope plan: {output_rel}")
    status = PASS_STATUS if not failures else FAIL_STATUS
    scopes = build_commit_scopes(classified_entries)
    return {
        "stage": STAGE,
        "status": status,
        "generated_at_utc": generated_at_utc or inventory.utc_now(),
        "scope": {
            "operation": "workspace_commit_scope_plan_report_only",
            "reports_root": output_rel,
            "evidence_mode": "git_status_and_existing_json_md_only",
            "data_model_command_scope": "none",
            "cleanup_stage_commit_push_scope": "none",
        },
        "summary": {
            "failure_count": len(failures),
            "git_status_entry_count": len(status_entries),
            "classified_entry_count": len(classified_entries),
            "commit_scope_count": len(scopes),
            "bucket_counts": grouped_counts(classified_entries, "bucket"),
            "status_marker_counts": grouped_counts(classified_entries, "status"),
            "manual_review_required_count": len(classified_entries),
            "auto_stage_allowed_count": 0,
            "generated_or_data_artifact_caution_count": sum(
                1 for entry in classified_entries if entry["generated_or_data_artifact_caution"]
            ),
            "master_audit_closeout_status": dotted_get(payloads.get("master_audit_closeout"), "status"),
            "master_audit_closeout_classification": dotted_get(
                payloads.get("master_audit_closeout"), "summary.closeout_classification"
            ),
            "full_master_audit_accepted": False,
            "model_trust_ready": False,
            "promotion_allowed": False,
            "artifact_freeze_ready": False,
            "final_holdout_ready": False,
            "paper_live_ready": False,
            "production_ready": False,
            **dict(NON_APPROVAL),
        },
        "input_evidence": evidence,
        "git_status": {
            "returncode": git_returncode,
            "error": git_error,
            "short_lines": status_lines,
        },
        "classified_entries": classified_entries,
        "commit_scopes": scopes,
        "non_approval": dict(NON_APPROVAL),
        "generated_artifact_policy": {
            "default": "remain_unstaged_unless_explicitly_approved",
            "applies_to": ["reports/**", "data/**", "logs/**", "model artifacts", "prediction artifacts"],
        },
        "pass_fail_criteria": {
            "pass": [
                "required coordination and closeout evidence is readable",
                "every git status entry is classified exactly once",
                "no path is marked auto-stage allowed",
                "Master Audit closeout remains blocked/not-ready",
                "report writes only the approved JSON/MD artifacts",
            ],
            "fail": [
                "missing/unreadable required evidence",
                "unclassified or duplicate dirty path classification",
                "any recommendation to auto-stage or auto-commit",
                "closeout state is upgraded or contradicted",
                "output root is outside the approved reports tree",
            ],
        },
        "failures": failures,
        "outputs": {
            "json": rel(reports_root / REPORT_JSON, repo_root),
            "markdown": rel(reports_root / REPORT_MD, repo_root),
        },
        "recommended_next_action": (
            "Review the generated commit scopes and choose exactly one human-approved staging "
            "scope before any git add/commit command."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Workspace Commit-Scope Plan",
        "",
        f"- Status: `{report['status']}`",
        f"- Failures: `{summary['failure_count']}`",
        f"- Git status entries: `{summary['git_status_entry_count']}`",
        f"- Classified entries: `{summary['classified_entry_count']}`",
        f"- Commit scopes: `{summary['commit_scope_count']}`",
        f"- Auto-stage allowed: `{summary['auto_stage_allowed_count']}`",
        f"- Master Audit closeout: `{summary['master_audit_closeout_classification']}`",
        f"- Model-trust ready: `{summary['model_trust_ready']}`",
        f"- Promotion allowed: `{summary['promotion_allowed']}`",
        f"- Artifact freeze ready: `{summary['artifact_freeze_ready']}`",
        f"- Final holdout ready: `{summary['final_holdout_ready']}`",
        f"- Paper/live ready: `{summary['paper_live_ready']}`",
        "",
        "## Commit Scopes",
        "",
        "| Scope | Paths | Recommendation |",
        "| --- | ---: | --- |",
    ]
    for scope in report["commit_scopes"]:
        lines.append(
            f"| `{scope['bucket']}` | `{scope['path_count']}` | {scope['recommended_action']} |"
        )
    lines.extend(["", "## Classified Paths", ""])
    for entry in report["classified_entries"]:
        lines.append(
            "- `{path}` status=`{status}` bucket=`{bucket}` auto_stage=`{auto}` caution=`{caution}`".format(
                path=entry["path"],
                status=entry["status"],
                bucket=entry["bucket"],
                auto=entry["auto_stage_allowed"],
                caution=entry["generated_or_data_artifact_caution"],
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
            "- This plan did not stage, commit, push, clean up, delete, move, rename, revert, run data/model commands, run WFA/modeling, generate predictions, refresh Phase 8, call providers/network, promote, freeze, run final holdout, run paper/live, or read parquet/model artifacts.",
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
        f"entries={report['summary']['classified_entry_count']} "
        f"json={rel(json_path, repo_root)} md={rel(md_path, repo_root)}"
    )
    return 0 if report["status"] == PASS_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
