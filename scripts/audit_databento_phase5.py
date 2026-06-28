#!/usr/bin/env python3
"""Phase 5 final model-readiness gate."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from scripts.audit_databento_common import (
    AUDIT_STATE_PATH,
    Blocker,
    PhaseResult,
    phase_gate_path,
    read_json_if_exists,
    rel,
    repo_path,
    utc_now,
    write_csv,
    write_json,
    write_phase_outputs,
    write_text,
)


PHASE = "phase5"
FINAL_DIR = "final"
REQUIRED_INPUTS = [
    "reports/data_audit/phase0_folder_triage/phase0_readiness_gate.json",
    "reports/data_audit/phase1_raw_inventory/phase1_readiness_gate.json",
    "reports/data_audit/phase2_raw_validity/phase2_readiness_gate.json",
    "reports/data_audit/phase2_raw_validity/blocker_disposition.csv",
    "reports/data_audit/phase2_raw_validity/blocker_disposition.md",
    "reports/data_audit/phase3_ohlcv_reconstruction/phase3_readiness_gate.json",
    "reports/data_audit/phase3_ohlcv_reconstruction/complete_minute_guard.csv",
    "reports/data_audit/phase3_ohlcv_reconstruction/ohlcv_from_trades_summary.json",
    "reports/data_audit/phase4_lineage/phase4_readiness_gate.json",
    "reports/data_audit/phase4_lineage/medium_blocker_disposition.csv",
    "reports/data_audit/phase4_lineage/medium_blocker_disposition.md",
    "reports/data_audit/phase4_lineage/blockers.csv",
]


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def split_pipe(value: Any) -> list[str]:
    return sorted(part for part in str(value or "").split("|") if part)


def unique_sorted(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if str(value) not in {"", "None", "nan"}})


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def add_blocker(blockers: list[Blocker], blocker: Blocker) -> None:
    key = (blocker.severity, blocker.issue, blocker.evidence)
    if any((item.severity, item.issue, item.evidence) == key for item in blockers):
        return
    blockers.append(blocker)


def required_input_blockers(paths: list[str]) -> list[Blocker]:
    blockers: list[Blocker] = []
    for path_text in paths:
        path = repo_path(path_text)
        if not path.exists():
            blockers.append(
                Blocker(
                    "Severe",
                    PHASE,
                    "required prior audit report missing",
                    path_text,
                    "Re-run or restore the missing prerequisite audit artifact before Phase 5.",
                )
            )
    return blockers


def prior_gate_blockers(gates: dict[int, dict[str, Any]]) -> list[Blocker]:
    blockers: list[Blocker] = []
    for phase, gate in sorted(gates.items()):
        severe = as_int(gate.get("severe_count"))
        if severe:
            blockers.append(
                Blocker(
                    "Severe",
                    f"phase{phase}",
                    f"Phase {phase} gate has Severe blockers",
                    gate.get("blockers_csv", ""),
                    "Stop until all prior Severe blockers are cleared.",
                )
            )
    return blockers


def phase2_overlap_medium(phase2_disposition: list[dict[str, Any]]) -> bool:
    return any(
        row.get("source_issue") == "overlap file starts before previous end"
        and row.get("severity_after") == "Medium"
        for row in phase2_disposition
    )


def disposition_folders(rows: list[dict[str, Any]], field: str, expected: str = "yes") -> list[str]:
    return unique_sorted(row.get("folder") for row in rows if str(row.get(field, "")).lower() == expected)


def accepted_caveat_folders(rows: list[dict[str, Any]]) -> list[str]:
    return unique_sorted(row.get("folder") for row in rows if row.get("disposition") == "accepted_with_caveat")


def stale_or_backup_do_not_use_rows(output_dir: Path, disposition_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in disposition_rows:
        if str(row.get("stale_do_not_use", "")).lower() != "yes":
            continue
        folder = str(row.get("folder", ""))
        if not folder or folder in seen:
            continue
        rows.append(
            {
                "folder": folder,
                "disposition": row.get("disposition", "stale_do_not_use"),
                "severity": row.get("severity_after", "Low"),
                "reason": row.get("decision_rationale", ""),
                "evidence": row.get("evidence", ""),
                "source_report": "reports/data_audit/phase4_lineage/medium_blocker_disposition.csv",
            }
        )
        seen.add(folder)

    stale_rows = read_csv_rows(output_dir / "phase4_lineage" / "stale_derived_outputs.csv")
    for row in stale_rows:
        folder = str(row.get("folder", ""))
        if not folder or folder in seen:
            continue
        if folder in {"data/labeled", "data/feature_matrices", "data/feature_matrices/baseline"}:
            continue
        if "pre_replace" not in folder and "_repair_candidates" not in folder:
            continue
        rows.append(
            {
                "folder": folder,
                "disposition": "stale_do_not_use",
                "severity": "Low",
                "reason": row.get("reason", "stale_or_backup_folder"),
                "evidence": row.get("recommendation", ""),
                "source_report": "reports/data_audit/phase4_lineage/stale_derived_outputs.csv",
            }
        )
        seen.add(folder)
    return rows


def manual_review_rows(
    disposition_rows: list[dict[str, Any]],
    phase4_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in disposition_rows:
        folder = str(row.get("folder", ""))
        if str(row.get("requires_rebuild_before_modeling", "")).lower() == "yes":
            rows.append(
                {
                    "folder": folder,
                    "required_action": "rebuild_before_modeling",
                    "severity": "Medium",
                    "evidence": row.get("evidence", ""),
                    "stop_condition": row.get("next_requirement", "Rebuild before modeling."),
                }
            )
        elif row.get("disposition") == "accepted_with_caveat":
            rows.append(
                {
                    "folder": folder,
                    "required_action": "classify_subfolders_before_use",
                    "severity": row.get("severity_after", "Low"),
                    "evidence": row.get("evidence", ""),
                    "stop_condition": row.get("next_requirement", "Classify subfolders before use."),
                }
            )
    for folder in split_pipe(phase4_summary.get("unknown_derived_folders_list", "")):
        rows.append(
            {
                "folder": folder,
                "required_action": "manual_folder_classification_required",
                "severity": "Low",
                "evidence": "reports/data_audit/phase4_lineage/phase4_readiness_gate.json",
                "stop_condition": "Classify before using as a modeling input.",
            }
        )
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["folder"], row["required_action"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def render_canonical_map(summary: dict[str, Any], do_not_use_count: int, manual_review_count: int) -> str:
    approved = summary["approved_folders"]
    lines = [
        "# Final Canonical Data Map",
        "",
        f"- Canonical raw Databento DBN source: `{summary['canonical_raw_source']}`.",
        "- Current raw parquet derivative: `data/raw` when a downstream parquet stage is required.",
        f"- Approved causal base: `{summary['approved_causal_base']}`.",
        "- Approved final modeling input: none.",
        "- Labels/features rebuild required before modeling: yes.",
        "- Predictions are output artifacts only and are not approved as modeling inputs.",
        f"- Do-not-use folder rows: {do_not_use_count}.",
        f"- Manual-review folder rows: {manual_review_count}.",
        "",
        "## Approved Folders",
        "",
    ]
    lines.extend(f"- `{folder}`" for folder in approved)
    lines.extend(
        [
            "",
            "## Model-Readiness Decision",
            "",
            f"- Model-ready: `{summary['model_ready']}`.",
            "- The causal base is approved within audited scope.",
            "- The final feature/label inputs are not approved until rebuilt or explicitly accepted.",
            "- Sampled validation does not certify full production readiness.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_report(summary: dict[str, Any], blockers: list[Blocker]) -> str:
    lines = [
        "# Final Model-Readiness Gate",
        "",
        f"- Status: `{summary['status']}`",
        f"- Proceed status: `{summary['proceed_status']}`",
        f"- Model-ready: `{summary['model_ready']}`",
        f"- Canonical raw source: `{summary['canonical_raw_source']}`",
        f"- Approved causal base: `{summary['approved_causal_base']}`",
        f"- Approved modeling input: `{summary['approved_modeling_input']}`",
        f"- Labels/features rebuild required: {str(summary['labels_features_rebuild_required']).lower()}",
        f"- Full scan certified: {str(summary['full_scan_certified']).lower()}",
        f"- Raw DBN files found: {summary['raw_dbn_zst_file_count']}",
        f"- Phase 2 sampled files scanned: {summary['files_scanned']}",
        f"- Phase 2 sampled rows scanned: {summary['phase2_rows_scanned']}",
        f"- Phase 3 trade rows scanned: {summary['phase3_trade_rows_scanned']}",
        f"- Reconstructed OHLCV bars: {summary['reconstructed_ohlcv_bars']}",
        f"- OHLCV reconstruction mismatches: {summary['ohlcv_reconstruction_mismatches']}",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(f"- `{blocker.severity}`: {blocker.issue} | {blocker.evidence}" for blocker in blockers)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Do not mark the full pipeline model-ready. The raw source audits have no Severe blockers so far, sampled raw validity and sampled OHLCV reconstruction passed, and the causal base is approved. Labels/features still require rebuild before modeling, and the audit remains sample-only rather than full production certified.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_phase5(args: Any) -> dict[str, Any]:
    started = utc_now()
    output_dir = repo_path(args.output_dir)
    phase_dir = output_dir / FINAL_DIR
    state_dir = output_dir / "state"

    missing_blockers = required_input_blockers(REQUIRED_INPUTS)
    gates: dict[int, dict[str, Any]] = {}
    for phase in range(0, 5):
        path = phase_gate_path(Path(args.output_dir), phase, f"phase{phase}_readiness_gate.json")
        if phase == 5:
            continue
        payload = read_json_if_exists(path)
        if payload is not None:
            gates[phase] = payload

    phase1 = gates.get(1, {})
    phase2 = gates.get(2, {})
    phase3 = gates.get(3, {})
    phase4 = gates.get(4, {})
    phase1_summary = phase1.get("summary", {})
    phase2_summary = phase2.get("summary", {})
    phase3_summary = phase3.get("summary", {})
    phase4_summary = phase4.get("summary", {})

    phase2_disposition = read_csv_rows(output_dir / "phase2_raw_validity" / "blocker_disposition.csv")
    disposition_rows = read_csv_rows(output_dir / "phase4_lineage" / "medium_blocker_disposition.csv")
    phase3_reconstruction = read_json_if_exists(output_dir / "phase3_ohlcv_reconstruction" / "ohlcv_from_trades_summary.json") or {}
    state = read_json_if_exists(repo_path(AUDIT_STATE_PATH)) or {}

    approved_causal_base = "data/causally_gated_normalized"
    approved_causal_rows = [
        row for row in disposition_rows if row.get("folder") == approved_causal_base and row.get("disposition") == "approved_current"
    ]
    if not approved_causal_rows:
        missing_blockers.append(
            Blocker(
                "Severe",
                PHASE,
                "approved causal base disposition missing",
                "reports/data_audit/phase4_lineage/medium_blocker_disposition.csv",
                "Stop until Phase 4 disposition approves or rejects the causal base.",
            )
        )

    rebuild_required = disposition_folders(disposition_rows, "requires_rebuild_before_modeling")
    do_not_use_rows = stale_or_backup_do_not_use_rows(output_dir, disposition_rows)
    manual_rows = manual_review_rows(disposition_rows, phase4_summary)
    approved_folders = unique_sorted(["data/dbn", approved_causal_base])
    accepted_caveats = accepted_caveat_folders(disposition_rows)

    full_scan_certified = bool(state.get("full") is True and state.get("allow_full_scan") is True)
    labels_features_rebuild_required = bool(rebuild_required)
    model_ready = "no_labels_features_rebuild_required" if labels_features_rebuild_required else "sample_only_not_full_scan_certified" if not full_scan_certified else "yes"
    if any(as_int(gate.get("severe_count")) for gate in gates.values()) or missing_blockers:
        model_ready = "no"

    blockers: list[Blocker] = []
    for blocker in missing_blockers:
        add_blocker(blockers, blocker)
    for blocker in prior_gate_blockers(gates):
        add_blocker(blockers, blocker)
    if labels_features_rebuild_required:
        add_blocker(
            blockers,
            Blocker(
                "Medium",
                PHASE,
                "labels/features require rebuild before modeling",
                "reports/data_audit/phase4_lineage/medium_blocker_disposition.csv",
                "Rebuild labels and baseline features from the approved causal base before modeling.",
            ),
        )
    if not full_scan_certified:
        add_blocker(
            blockers,
            Blocker(
                "Medium",
                PHASE,
                "sampled validation cannot certify full production readiness",
                "reports/data_audit/state/audit_state.json full=false allow_full_scan=false",
                "Do not claim production readiness until an approved full scan has completed.",
            ),
        )
    if phase2_overlap_medium(phase2_disposition):
        add_blocker(
            blockers,
            Blocker(
                "Medium",
                PHASE,
                "overlapping raw archive intervals remain unresolved for full production loaders",
                "reports/data_audit/phase2_raw_validity/blocker_disposition.csv",
                "Exclude or deduplicate overlapping archive intervals before full production use.",
            ),
        )
    if do_not_use_rows:
        add_blocker(
            blockers,
            Blocker(
                "Low",
                PHASE,
                "stale or backup do-not-use folders remain present",
                f"reports/data_audit/final/do_not_use_folders.csv count={len(do_not_use_rows)}",
                "Keep these folders out of modeling inputs; Phase 6 may plan quarantine only.",
            ),
        )
    if accepted_caveats:
        add_blocker(
            blockers,
            Blocker(
                "Low",
                PHASE,
                "manual-review folders accepted only with caveats",
                f"reports/data_audit/final/manual_review_required.csv count={len(manual_rows)}",
                "Classify or rebuild before using these folders as modeling inputs.",
            ),
        )
    add_blocker(
        blockers,
        Blocker(
            "Low",
            PHASE,
            "status KE 2013 caveat carried into final readiness",
            "reports/data_audit/phase2_raw_validity/blocker_disposition.md",
            "Keep visible for status-dependent KE 2013 modeling decisions.",
        ),
    )

    severe = sum(1 for blocker in blockers if blocker.severity == "Severe")
    medium = sum(1 for blocker in blockers if blocker.severity == "Medium")
    status = "fail" if severe else "pass_with_medium_blockers" if medium else "pass"
    proceed_status = "no" if severe else "yes with medium blockers" if medium else "yes"
    phase2_rows = as_int(phase2_summary.get("sample_rows_scanned"))
    phase3_rows = as_int(phase3_summary.get("sample_trade_rows_scanned"))
    summary = {
        "phase": PHASE,
        "status": status,
        "proceed_status": proceed_status,
        "model_ready": model_ready,
        "canonical_raw_source": phase1_summary.get("canonical_raw_source", "data/dbn"),
        "approved_causal_base": approved_causal_base if approved_causal_rows else "",
        "approved_modeling_input": "none",
        "approved_folders": approved_folders,
        "accepted_with_caveat_folders": accepted_caveats,
        "labels_features_rebuild_required": labels_features_rebuild_required,
        "labels_features_rebuild_required_folders": rebuild_required,
        "stale_do_not_use_folder_count": len(do_not_use_rows),
        "stale_do_not_use_folders": [row["folder"] for row in do_not_use_rows],
        "manual_review_folder_count": len(manual_rows),
        "manual_review_folders": [row["folder"] for row in manual_rows],
        "full_scan_certified": full_scan_certified,
        "raw_dbn_zst_file_count": as_int(phase1_summary.get("raw_dbn_zst_file_count")),
        "l0_schemas_audited": phase1_summary.get("l0_schemas_found", []),
        "trade_schemas_audited": phase1_summary.get("trade_schemas_found", []),
        "markets_audited": as_int(phase1_summary.get("market_count")),
        "markets": phase1_summary.get("markets", []),
        "years_audited": as_int(phase1_summary.get("year_count")),
        "years": phase1_summary.get("years", []),
        "files_scanned": as_int(phase2_summary.get("sample_files_scanned")),
        "phase2_rows_scanned": phase2_rows,
        "phase3_trade_rows_scanned": phase3_rows,
        "rows_scanned": phase2_rows + phase3_rows,
        "trade_ohlcv_overlap_rows_checked": as_int(phase3_summary.get("sample_raw_ohlcv_bars_checked")),
        "reconstructed_ohlcv_bars": as_int(phase3_reconstruction.get("reconstructed_ohlcv_bars", phase3_summary.get("reconstructed_ohlcv_bars"))),
        "ohlcv_reconstruction_mismatches": as_int(phase3_reconstruction.get("mismatched_bars", phase3_summary.get("mismatched_bars"))),
        "unreadable_files": as_int(phase2_summary.get("unreadable_files", phase1_summary.get("unreadable_metadata_file_count"))),
        "missing_schema_market_years": as_int(phase1_summary.get("missing_expected_coverage_count")),
        "phase_gate_statuses": {f"phase{phase}": gate.get("status", "") for phase, gate in sorted(gates.items())},
        "severe_issue_count": severe,
        "medium_issue_count": medium,
        "low_issue_count": sum(1 for blocker in blockers if blocker.severity == "Low"),
        "source_mutation_check": "not_applicable",
    }

    reports = [
        phase_dir / "blockers.csv",
        phase_dir / "final_audit_summary.json",
        phase_dir / "final_audit_report.md",
        phase_dir / "model_readiness_gate.json",
        phase_dir / "canonical_data_map_final.md",
        phase_dir / "do_not_use_folders.csv",
        phase_dir / "manual_review_required.csv",
    ]
    write_json(phase_dir / "final_audit_summary.json", summary)
    write_text(phase_dir / "final_audit_report.md", render_report(summary, blockers))
    write_text(phase_dir / "canonical_data_map_final.md", render_canonical_map(summary, len(do_not_use_rows), len(manual_rows)))
    write_csv(
        phase_dir / "do_not_use_folders.csv",
        ["folder", "disposition", "severity", "reason", "evidence", "source_report"],
        do_not_use_rows,
    )
    write_csv(
        phase_dir / "manual_review_required.csv",
        ["folder", "required_action", "severity", "evidence", "stop_condition"],
        manual_rows,
    )
    result = PhaseResult(
        phase=PHASE,
        started_at=started,
        finished_at=utc_now(),
        reports=[rel(path) for path in reports],
        blockers=blockers,
        source_mutation_check="not_applicable",
        summary=summary,
        gate_path=phase_dir / "model_readiness_gate.json",
        blockers_csv=phase_dir / "blockers.csv",
    )
    gate = write_phase_outputs(result)
    state_payload = {
        "last_phase": PHASE,
        "last_gate": rel(result.gate_path),
        "updated_at": utc_now(),
        "data_root": str(args.data_root),
        "output_dir": str(args.output_dir),
        "sample": bool(args.sample),
        "full": bool(args.full),
        "allow_full_scan": bool(args.allow_full_scan),
        "gate": gate,
    }
    write_json(state_dir / "audit_state.json", state_payload)
    print(
        "phase5 status={status} severe={severe} medium={medium} low={low} model_ready={model_ready} blockers_csv={blockers}".format(
            status=gate["status"],
            severe=gate["severe_count"],
            medium=gate["medium_count"],
            low=gate["low_count"],
            model_ready=summary["model_ready"],
            blockers=gate["blockers_csv"],
        )
    )
    return gate
