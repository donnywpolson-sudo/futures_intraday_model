#!/usr/bin/env python3
"""Phase 0 folder triage for the Databento audit runner."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from scripts.audit_databento_common import (
    Blocker,
    DBN_SCHEMA_PATHS,
    PhaseResult,
    blocker_from_mutation,
    compare_source_manifests,
    phase_gate_path,
    rel,
    repo_path,
    source_manifest_rows,
    utc_now,
    write_csv,
    write_json,
    write_phase_outputs,
    write_source_manifest,
    write_text,
)


PHASE = "phase0"
TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".md", ".txt", ".json", ".toml", ".cfg", ".ini"}
PATH_REFERENCE_RE = re.compile(r"(?:data|reports|configs|scripts|tests|docs)[/\\][A-Za-z0-9_./\\-]+", re.IGNORECASE)
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "build"}
CURRENT_DERIVED_PREFIXES = (
    "data/raw",
    "data/causally_gated_normalized",
    "data/labeled",
    "data/feature_matrices",
    "data/predictions",
    "data/executions",
    "data/frozen_features",
)


def classify_folder(path: Path) -> tuple[str, str]:
    rel_path = path.as_posix().replace("\\", "/")
    if rel_path.startswith("./"):
        rel_path = rel_path[2:]
    rel_lower = rel_path.lower()
    name_lower = path.name.lower()

    if rel_path == "data/dbn" or rel_path.startswith("data/dbn/"):
        if "candidate" in rel_lower or "repair" in rel_lower:
            return "quarantine_candidate", "source-like DBN candidate/repair subtree"
        return "canonical_raw_source", "active source-of-truth DBN subtree"
    if rel_path == "data/archive" or rel_path.startswith("data/archive/"):
        return "stale_legacy", "dead archive evidence; not an active source root"
    rel_parts = rel_path.split("/")
    if len(rel_parts) >= 2 and rel_parts[0] == "data" and rel_parts[1].endswith("_sr_parent_candidate"):
        return "stale_legacy", "legacy parent candidate subtree; canonical DBN source belongs under data/dbn"
    if rel_path.startswith("data/causally_gated_normalized_pre_replace"):
        return "quarantine_candidate", "derived backup subtree pending audit"
    if rel_path in CURRENT_DERIVED_PREFIXES or any(rel_path.startswith(prefix + "/") for prefix in CURRENT_DERIVED_PREFIXES):
        if "pre_replace" in rel_lower or "_repair" in rel_lower or "candidate" in rel_lower:
            return "quarantine_candidate", "derived candidate/backup subtree pending audit"
        return "current_derived", "configured derived/modeling data subtree"
    if rel_path.startswith("reports/") or rel_path.startswith("manifests/"):
        return "report_or_manifest_only", "report or manifest subtree"
    if rel_path.startswith("_archive") or "/_archive" in rel_path or "pre_replace" in name_lower:
        return "stale_legacy", "archive or backup naming"
    if "quarantine" in rel_lower:
        return "quarantine_candidate", "quarantine naming"
    if "duplicate" in rel_lower or "redundant" in rel_lower:
        return "duplicate_or_redundant", "duplicate/redundant naming"
    if rel_path == "data" or rel_path.startswith("data/"):
        return "unsafe_unknown", "data subtree not recognized by current audit policy"
    return "report_or_manifest_only", "non-data folder"


def parse_dbn_market_year_schema(path: Path) -> dict[str, Any]:
    parts = path.as_posix().replace("\\", "/").split("/")
    try:
        dbn_idx = parts.index("dbn")
    except ValueError:
        return {"schema": "", "market": "", "year": ""}
    schema_path = parts[dbn_idx + 1] if len(parts) > dbn_idx + 1 else ""
    schema = next((key for key, value in DBN_SCHEMA_PATHS.items() if value == schema_path), schema_path)
    market = ""
    year = ""
    for part in parts[dbn_idx + 2 :]:
        if re.fullmatch(r"\d{4}", part):
            year = part
            break
        if not market and part not in {"status", "statistics"}:
            market = part
    return {"schema": schema, "market": market, "year": year}


def iter_dirs(root: Path) -> Iterable[Path]:
    for current, dirnames, _filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for dirname in dirnames:
            yield Path(current) / dirname


def top_level_folders(repo_root: Path) -> list[dict[str, Any]]:
    return [
        {"path": rel(path), "name": path.name}
        for path in sorted(repo_root.iterdir())
        if path.is_dir() and path.name not in {".git", ".venv", "__pycache__"}
    ]


def immediate_data_folders(repo_root: Path) -> list[dict[str, Any]]:
    data_root = repo_root / "data"
    if not data_root.exists():
        return []
    return [{"path": rel(path), "name": path.name} for path in sorted(data_root.iterdir()) if path.is_dir()]


def nested_data_looking_folders(repo_root: Path) -> list[dict[str, Any]]:
    tokens = {"data", "dbn", "raw", "candidate", "archive", "quarantine", "manifest", "report"}
    rows: list[dict[str, Any]] = []
    for path in iter_dirs(repo_root):
        rel_path = rel(path)
        lower_tokens = set(re.split(r"[/\\_.-]+", rel_path.lower()))
        if lower_tokens & tokens:
            rows.append({"path": rel_path, "name": path.name})
    return rows


def config_path_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    config_root = repo_root / "configs"
    if not config_root.exists():
        return rows
    for path in sorted(config_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"path|root|market|schema|session|tick|pipeline", text, re.IGNORECASE):
            rows.append({"path": rel(path), "matched_terms": "path/root/market/schema/session/tick/pipeline"})
    return rows


def inventory_folders(repo_root: Path) -> list[dict[str, Any]]:
    data_root = repo_root / "data"
    if not data_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(iter_dirs(data_root)):
        try:
            entries = list(path.iterdir())
        except OSError:
            entries = []
        classification, reason = classify_folder(Path(rel(path)))
        rows.append(
            {
                "path": rel(path),
                "name": path.name,
                "classification": classification,
                "classification_reason": reason,
                "child_dirs": sum(1 for child in entries if child.is_dir()),
                "child_files": sum(1 for child in entries if child.is_file()),
            }
        )
    return rows


def discover_text_references(repo_root: Path) -> list[dict[str, Any]]:
    roots = [repo_root / name for name in ("scripts", "configs", "tests", "docs")]
    roots.extend(path for path in repo_root.glob("*.md") if path.is_file())
    rows: list[dict[str, Any]] = []
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*")) if root.exists() else []
        for path in files:
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                for match in PATH_REFERENCE_RE.findall(line):
                    rows.append(
                        {
                            "file": rel(path),
                            "line": line_no,
                            "reference": match.rstrip(".,;)"),
                            "context": line.strip()[:240],
                        }
                    )
    return rows


def script_data_reference_summary(reference_rows: list[dict[str, Any]], stale_paths: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in reference_rows:
        file_path = str(row["file"])
        if not (file_path.startswith("scripts/") or file_path.startswith("tests/") or file_path.startswith("configs/")):
            continue
        ref = str(row["reference"]).replace("\\", "/")
        rows.append(
            {
                "file": file_path,
                "line": row["line"],
                "reference": ref,
                "active_stale_reference": any(ref == stale or ref.startswith(stale + "/") for stale in stale_paths),
                "context": row["context"],
            }
        )
    return rows


def build_blockers(
    *,
    folder_rows: list[dict[str, Any]],
    reference_summary: list[dict[str, Any]],
    mutation_check: dict[str, Any],
) -> list[Blocker]:
    blockers = blocker_from_mutation(PHASE, mutation_check)
    canonical_source = any(row["path"] == "data/dbn" and row["classification"] == "canonical_raw_source" for row in folder_rows)
    current_derived = any(row["classification"] == "current_derived" for row in folder_rows)
    if not canonical_source:
        blockers.append(
            Blocker(
                "Severe",
                PHASE,
                "canonical raw .dbn.zst source folder not identified",
                "data/dbn missing or not classified as canonical_raw_source",
                "Stop before raw DBN inventory and identify the canonical Databento source root.",
            )
        )
    if not current_derived:
        blockers.append(
            Blocker(
                "Medium",
                PHASE,
                "current derived/modeling input folders not identified",
                "no data folder classified current_derived",
                "Confirm whether derived/modeling inputs are intentionally absent.",
            )
        )
    active_stale = [row for row in reference_summary if row["active_stale_reference"]]
    if active_stale:
        blockers.append(
            Blocker(
                "Severe",
                PHASE,
                "active script/config/test references stale data folder",
                json.dumps(active_stale[:5], sort_keys=True),
                "Fix active stale data references before any model-readiness decision.",
            )
        )
    unsafe = [row for row in folder_rows if row["classification"] == "unsafe_unknown"]
    if unsafe:
        blockers.append(
            Blocker(
                "Medium",
                PHASE,
                "unsafe/unknown data folders require review",
                f"count={len(unsafe)}",
                "Review unsafe_unknown rows before quarantine planning or modeling.",
            )
        )
    return blockers


def render_repo_data_map(
    top_level: list[dict[str, Any]],
    data_dirs: list[dict[str, Any]],
    nested_dirs: list[dict[str, Any]],
    config_rows: list[dict[str, Any]],
) -> str:
    lines = ["# Phase 0 Repo Data Map", "", "## Top-Level Folders", ""]
    lines.extend(f"- `{row['path']}`" for row in top_level)
    lines.extend(["", "## Data Folders", ""])
    lines.extend(f"- `{row['path']}`" for row in data_dirs)
    lines.extend(["", "## Nested Data-Looking Folders", ""])
    lines.extend(f"- `{row['path']}`" for row in nested_dirs[:250])
    lines.extend(["", "## Path/Market/Schema/Session Configs", ""])
    lines.extend(f"- `{row['path']}`" for row in config_rows)
    return "\n".join(lines) + "\n"


def render_canonical_map(folder_rows: list[dict[str, Any]]) -> str:
    counts = Counter(str(row["classification"]) for row in folder_rows)
    lines = [
        "# Proposed Canonical Data Map",
        "",
        "- Canonical raw Databento DBN source: `data/dbn`.",
        "- DBN files under `data/archive` are dead archive evidence, not active source inputs.",
        "- Current derived raw parquet: `data/raw` when present.",
        "- Modeling input: explicit configured path required; no hardcoded derived default is approved.",
        "- Labels/features/predictions are derived outputs, not source evidence.",
        "- Parent/candidate/quarantine-like folders are review targets only; no action is authorized.",
        "",
        "## Classification Counts",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(counts.items()))
    return "\n".join(lines) + "\n"


def render_phase0_report(result: PhaseResult, summary: dict[str, Any]) -> str:
    status = "FAIL" if result.severe_count else "PASS_WITH_MEDIUM_BLOCKERS" if result.medium_count else "PASS"
    lines = [
        "# Phase 0 Folder Triage Report",
        "",
        f"- Status: `{status}`",
        f"- Severe blockers: {result.severe_count}",
        f"- Medium blockers: {result.medium_count}",
        f"- Low blockers: {result.low_count}",
        f"- Source mutation check: `{result.source_mutation_check}`",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in summary.items() if key != "classification_counts")
    lines.extend(["", "## Blockers", ""])
    if result.blockers:
        lines.extend(f"- `{blocker.severity}`: {blocker.issue} ({blocker.evidence})" for blocker in result.blockers)
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def run_phase0(args: Any) -> dict[str, Any]:
    started = utc_now()
    repo_root = repo_path(".")
    output_dir = repo_path(args.output_dir)
    phase_dir = output_dir / "phase0_folder_triage"
    state_dir = output_dir / "state"

    before = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    if not args.dry_run:
        write_source_manifest(state_dir / "source_manifest_before.csv", before)

    top_level = top_level_folders(repo_root)
    data_dirs = immediate_data_folders(repo_root)
    nested_dirs = nested_data_looking_folders(repo_root)
    config_rows = config_path_rows(repo_root)
    folder_rows = inventory_folders(repo_root)
    references = discover_text_references(repo_root)
    stale_paths = {str(row["path"]) for row in folder_rows if row["classification"] == "stale_legacy"}
    reference_summary = script_data_reference_summary(references, stale_paths)
    classification_rows = [
        {"path": row["path"], "classification": row["classification"], "reason": row["classification_reason"]}
        for row in folder_rows
    ]
    stale_rows = [row for row in classification_rows if row["classification"] == "stale_legacy"]
    quarantine_rows = [row for row in classification_rows if row["classification"] == "quarantine_candidate"]
    after = source_manifest_rows(Path(args.data_root), max_files=args.max_files)
    mutation_check = compare_source_manifests(before, after)
    if not args.dry_run:
        write_source_manifest(state_dir / "source_manifest_after.csv", after)
        write_json(state_dir / "source_mutation_check.json", mutation_check)

    counts = Counter(str(row["classification"]) for row in folder_rows)
    summary = {
        "top_level_folder_count": len(top_level),
        "data_folder_count": len(data_dirs),
        "nested_data_looking_folder_count": len(nested_dirs),
        "folder_inventory_count": len(folder_rows),
        "data_path_reference_count": len(references),
        "source_file_manifest_count": len(before),
        "classification_counts": dict(sorted(counts.items())),
        "canonical_raw_source_identified": any(
            row["path"] == "data/dbn" and row["classification"] == "canonical_raw_source"
            for row in folder_rows
        ),
        "current_derived_identified": any(row["classification"] == "current_derived" for row in folder_rows),
        "stale_legacy_count": len(stale_rows),
        "unsafe_unknown_count": sum(1 for row in folder_rows if row["classification"] == "unsafe_unknown"),
        "quarantine_candidate_count": len(quarantine_rows),
        "active_stale_reference_count": sum(1 for row in reference_summary if row["active_stale_reference"]),
    }
    blockers = build_blockers(folder_rows=folder_rows, reference_summary=reference_summary, mutation_check=mutation_check)
    finished = utc_now()
    reports = [
        rel(phase_dir / "repo_data_map.md"),
        rel(phase_dir / "folder_inventory.csv"),
        rel(phase_dir / "folder_inventory_summary.json"),
        rel(phase_dir / "data_path_references.csv"),
        rel(phase_dir / "folder_classification.csv"),
        rel(phase_dir / "proposed_canonical_data_map.md"),
        rel(phase_dir / "stale_data_findings.csv"),
        rel(phase_dir / "quarantine_candidates.csv"),
        rel(phase_dir / "blockers.csv"),
        rel(phase_dir / "phase0_readiness_gate.json"),
        rel(phase_dir / "phase0_folder_triage_report.md"),
    ]
    result = PhaseResult(
        phase=PHASE,
        started_at=started,
        finished_at=finished,
        reports=reports,
        blockers=blockers,
        source_mutation_check=str(mutation_check["source_mutation_check"]),
        summary=summary,
        gate_path=phase_gate_path(Path(args.output_dir), 0, "phase0_readiness_gate.json"),
        blockers_csv=phase_dir / "blockers.csv",
    )

    if args.dry_run:
        payload = {
            "phase": PHASE,
            "dry_run": True,
            "would_write": reports
            + [
                rel(state_dir / "audit_state.json"),
                rel(state_dir / "source_manifest_before.csv"),
                rel(state_dir / "source_manifest_after.csv"),
                rel(state_dir / "source_mutation_check.json"),
            ],
            "summary": summary,
            "source_mutation_check": mutation_check["source_mutation_check"],
            "blocker_counts": {
                "severe": result.severe_count,
                "medium": result.medium_count,
                "low": result.low_count,
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return payload

    write_text(phase_dir / "repo_data_map.md", render_repo_data_map(top_level, data_dirs, nested_dirs, config_rows))
    write_csv(
        phase_dir / "folder_inventory.csv",
        ["path", "name", "classification", "classification_reason", "child_dirs", "child_files"],
        folder_rows,
    )
    write_json(phase_dir / "folder_inventory_summary.json", summary)
    write_csv(phase_dir / "data_path_references.csv", ["file", "line", "reference", "context"], references)
    write_csv(phase_dir / "folder_classification.csv", ["path", "classification", "reason"], classification_rows)
    write_text(phase_dir / "proposed_canonical_data_map.md", render_canonical_map(folder_rows))
    write_csv(phase_dir / "stale_data_findings.csv", ["path", "classification", "reason"], stale_rows)
    write_csv(phase_dir / "quarantine_candidates.csv", ["path", "classification", "reason"], quarantine_rows)
    write_text(phase_dir / "phase0_folder_triage_report.md", render_phase0_report(result, summary))
    gate = write_phase_outputs(result)
    state = {
        "last_phase": PHASE,
        "last_gate": rel(result.gate_path),
        "updated_at": utc_now(),
        "data_root": str(args.data_root),
        "output_dir": str(args.output_dir),
        "schemas": args.schemas or [],
        "markets": args.markets or [],
        "years": args.years or [],
        "sample": bool(args.sample),
        "full": bool(args.full),
        "allow_full_scan": bool(args.allow_full_scan),
        "gate": gate,
    }
    write_json(state_dir / "audit_state.json", state)
    print(
        "phase0 status={status} severe={severe} medium={medium} low={low} blockers_csv={blockers}".format(
            status=gate["status"],
            severe=gate["severe_count"],
            medium=gate["medium_count"],
            low=gate["low_count"],
            blockers=gate["blockers_csv"],
        )
    )
    return gate
