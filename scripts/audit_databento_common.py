#!/usr/bin/env python3
"""Shared helpers for the staged Databento data audit runner."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = Path("reports/data_audit")
DEFAULT_DATA_ROOT = Path("data/dbn")
AUDIT_STATE_PATH = Path("reports/data_audit/state/audit_state.json")

REQUIRED_GATE_KEYS = {
    "phase",
    "status",
    "proceed_status",
    "severe_count",
    "medium_count",
    "low_count",
    "blockers_csv",
    "reports",
    "started_at",
    "finished_at",
    "source_mutation_check",
    "summary",
}

PHASES: dict[int, str] = {
    0: "folder triage",
    1: "raw DBN inventory",
    2: "sampled/raw source validity audit",
    3: "OHLCV-from-trades reconstruction",
    4: "derived lineage and raw-vs-derived audit",
    5: "final model-readiness gate",
    6: "quarantine plan only, no execution",
}

DBN_SCHEMA_PATHS = {
    "definition": "definition",
    "ohlcv-1m": "ohlcv_1m",
    "ohlcv-1s": "ohlcv_1s",
    "ohlcv-1h": "ohlcv_1h",
    "ohlcv-1d": "ohlcv_1d",
    "statistics": "statistics",
    "status": "status",
    "trades": "trades",
    "mbp-1": "mbp-1",
}


@dataclass(frozen=True)
class Blocker:
    severity: str
    phase: str
    issue: str
    evidence: str = ""
    recommendation: str = ""


@dataclass
class PhaseResult:
    phase: str
    started_at: str
    finished_at: str
    reports: list[str]
    blockers: list[Blocker] = field(default_factory=list)
    source_mutation_check: str = "not_applicable"
    summary: dict[str, Any] = field(default_factory=dict)
    gate_path: Path | None = None
    blockers_csv: Path | None = None

    @property
    def severe_count(self) -> int:
        return sum(1 for blocker in self.blockers if blocker.severity == "Severe")

    @property
    def medium_count(self) -> int:
        return sum(1 for blocker in self.blockers if blocker.severity == "Medium")

    @property
    def low_count(self) -> int:
        return sum(1 for blocker in self.blockers if blocker.severity == "Low")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def rel(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return candidate.as_posix()


def ensure_allowed_write(path: Path, allowed_roots: Iterable[Path] | None = None) -> None:
    roots = list(allowed_roots or [Path("reports/data_audit")])
    resolved = path.resolve()
    for root in roots:
        root_resolved = repo_path(root).resolve()
        if resolved == root_resolved or root_resolved in resolved.parents:
            return
    raise ValueError(f"write path is outside allowed audit outputs: {path}")


def write_json(
    path: Path,
    payload: dict[str, Any],
    *,
    allowed_roots: Iterable[Path] | None = None,
) -> None:
    ensure_allowed_write(path, allowed_roots)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str, *, allowed_roots: Iterable[Path] | None = None) -> None:
    ensure_allowed_write(path, allowed_roots)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
    *,
    allowed_roots: Iterable[Path] | None = None,
) -> None:
    ensure_allowed_write(path, allowed_roots)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_list_arg(values: list[str] | None) -> list[str]:
    items: list[str] = []
    for value in values or []:
        items.extend(part.strip() for part in str(value).split(",") if part.strip())
    return items


def parse_years(values: list[str] | None) -> list[int]:
    years: list[int] = []
    for value in parse_list_arg(values):
        if "-" in value:
            start, end = value.split("-", 1)
            years.extend(range(int(start), int(end) + 1))
        else:
            years.append(int(value))
    return sorted(set(years))


def phase_name(phase: int) -> str:
    if phase not in PHASES:
        raise ValueError(f"unsupported phase: {phase}")
    return f"phase{phase}"


def gate_status(blockers: list[Blocker]) -> tuple[str, str]:
    severe = sum(1 for blocker in blockers if blocker.severity == "Severe")
    medium = sum(1 for blocker in blockers if blocker.severity == "Medium")
    if severe:
        return "fail", "no"
    if medium:
        return "pass_with_medium_blockers", "yes with medium blockers"
    return "pass", "yes"


def validate_gate_payload(payload: dict[str, Any]) -> None:
    missing = REQUIRED_GATE_KEYS - set(payload)
    if missing:
        raise ValueError(f"gate missing keys: {sorted(missing)}")
    if payload["status"] not in {"pass", "pass_with_medium_blockers", "fail"}:
        raise ValueError("invalid gate status")
    if payload["proceed_status"] not in {"yes", "yes with medium blockers", "no"}:
        raise ValueError("invalid gate proceed_status")
    for key in ("severe_count", "medium_count", "low_count"):
        if not isinstance(payload[key], int) or payload[key] < 0:
            raise ValueError(f"invalid gate count: {key}")
    if payload["source_mutation_check"] not in {"pass", "fail", "not_applicable"}:
        raise ValueError("invalid source_mutation_check")


def gate_payload(result: PhaseResult) -> dict[str, Any]:
    status, proceed = gate_status(result.blockers)
    payload = {
        "phase": result.phase,
        "status": status,
        "proceed_status": proceed,
        "severe_count": result.severe_count,
        "medium_count": result.medium_count,
        "low_count": result.low_count,
        "blockers_csv": rel(result.blockers_csv) if result.blockers_csv else "",
        "reports": result.reports,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "source_mutation_check": result.source_mutation_check,
        "summary": result.summary,
    }
    validate_gate_payload(payload)
    return payload


def write_blockers_csv(path: Path, blockers: list[Blocker]) -> None:
    rows = [
        {
            "severity": blocker.severity,
            "phase": blocker.phase,
            "issue": blocker.issue,
            "evidence": blocker.evidence,
            "recommendation": blocker.recommendation,
        }
        for blocker in blockers
    ]
    write_csv(path, ["severity", "phase", "issue", "evidence", "recommendation"], rows)


def write_phase_outputs(result: PhaseResult) -> dict[str, Any]:
    if result.blockers_csv is not None:
        write_blockers_csv(result.blockers_csv, result.blockers)
    if result.gate_path is None:
        raise ValueError("phase result missing gate_path")
    payload = gate_payload(result)
    write_json(result.gate_path, payload)
    return payload


def discover_dbn_zst_files(data_root: Path, *, max_files: int | None = None) -> list[Path]:
    root = repo_path(data_root)
    if not root.exists():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*.dbn.zst")):
        if path.is_file():
            files.append(path)
            if max_files is not None and len(files) >= max_files:
                break
    return files


def source_manifest_rows(data_root: Path, *, max_files: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in discover_dbn_zst_files(data_root, max_files=max_files):
        stat = path.stat()
        rows.append(
            {
                "path": rel(path),
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sample_hash": "",
            }
        )
    return rows


def write_source_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, ["path", "size_bytes", "mtime_ns", "sample_hash"], rows)


def compare_source_manifests(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    before_by_path = {str(row["path"]): row for row in before}
    after_by_path = {str(row["path"]): row for row in after}
    before_paths = set(before_by_path)
    after_paths = set(after_by_path)
    added = sorted(after_paths - before_paths)
    removed = sorted(before_paths - after_paths)
    changed: list[dict[str, Any]] = []
    for path in sorted(before_paths & after_paths):
        before_row = before_by_path[path]
        after_row = after_by_path[path]
        diffs = {
            key: {"before": before_row.get(key), "after": after_row.get(key)}
            for key in ("size_bytes", "mtime_ns", "sample_hash")
            if str(before_row.get(key)) != str(after_row.get(key))
        }
        if diffs:
            changed.append({"path": path, "diffs": diffs})
    status = "fail" if added or removed or changed else "pass"
    return {
        "status": status,
        "source_mutation_check": "fail" if status == "fail" else "pass",
        "before_count": len(before),
        "after_count": len(after),
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def phase_gate_path(output_dir: Path, phase: int, filename: str) -> Path:
    if phase == 0:
        return repo_path(output_dir) / "phase0_folder_triage" / filename
    if phase == 1:
        return repo_path(output_dir) / "phase1_raw_inventory" / filename
    if phase == 2:
        return repo_path(output_dir) / "phase2_raw_validity" / filename
    if phase == 3:
        return repo_path(output_dir) / "phase3_ohlcv_reconstruction" / filename
    if phase == 4:
        return repo_path(output_dir) / "phase4_lineage" / filename
    return repo_path(output_dir) / f"phase{phase}" / filename


def gate_passes(path: Path) -> bool:
    payload = read_json_if_exists(path)
    if payload is None:
        return False
    return payload.get("status") in {"pass", "pass_with_medium_blockers"} and payload.get("proceed_status") != "no"


def blocker_from_mutation(phase: str, mutation_check: dict[str, Any]) -> list[Blocker]:
    if mutation_check.get("source_mutation_check") != "fail":
        return []
    return [
        Blocker(
            severity="Severe",
            phase=phase,
            issue="source data mutation detected",
            evidence=json.dumps(
                {
                    "added": mutation_check.get("added", [])[:5],
                    "removed": mutation_check.get("removed", [])[:5],
                    "changed": mutation_check.get("changed", [])[:5],
                },
                sort_keys=True,
            ),
            recommendation="Stop audit and independently verify source data before modeling.",
        )
    ]
