#!/usr/bin/env python3
"""Fail-closed checks for data-audit universe market-year eligibility."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


USABLE_STATUS = "usable"
BLOCKED_STATUSES = {"quarantined", "diagnostic_only"}
WFA_BLOCKED_FINAL_DECISIONS = {"keep_quarantined_ohlcv_only_evidence_insufficient"}


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class DataAuditUniverse:
    path: Path
    file_hash: str
    status_counts: dict[str, int]
    market_years: dict[tuple[str, int], Mapping[str, Any]]

    def evidence(self) -> dict[str, Any]:
        return {
            "path": relative_path(self.path),
            "file_hash": self.file_hash,
            "status_counts": self.status_counts,
            "allowed_status": USABLE_STATUS,
            "requires_usable_for_wfa": True,
            "blocked_final_decisions": sorted(WFA_BLOCKED_FINAL_DECISIONS),
            "blocked_statuses": sorted(BLOCKED_STATUSES),
        }

    def require_usable(self, market: str, year: int, *, context: str) -> str | None:
        key = (str(market), int(year))
        row = self.market_years.get(key)
        if row is None:
            return f"{context}: missing data-audit universe decision for {key[0]} {key[1]}"
        status = str(row.get("audit_status") or "")
        final_decision = str(row.get("final_decision") or "")
        reason = str(row.get("reason") or row.get("source_reason") or "no reason provided")
        if final_decision in WFA_BLOCKED_FINAL_DECISIONS:
            return (
                f"{context}: data-audit universe blocks {key[0]} {key[1]} "
                f"with final_decision={final_decision!r}: {reason}"
            )
        if row.get("usable_for_wfa") is False:
            return (
                f"{context}: data-audit universe blocks {key[0]} {key[1]} "
                f"with usable_for_wfa=False and audit_status={status!r}: {reason}"
            )
        if status != USABLE_STATUS:
            return (
                f"{context}: data-audit universe blocks {key[0]} {key[1]} "
                f"with audit_status={status!r}: {reason}"
            )
        return None


def load_data_audit_universe(path: Path) -> DataAuditUniverse:
    if not path.exists():
        raise SystemExit(f"missing data-audit universe JSON: {relative_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"invalid data-audit universe JSON {relative_path(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"data-audit universe JSON must be an object: {relative_path(path)}")
    if payload.get("status") != "PASS":
        raise SystemExit(f"data-audit universe status is not PASS: {payload.get('status')!r}")

    rows = payload.get("market_years")
    if not isinstance(rows, list):
        raise SystemExit("data-audit universe missing market_years list")
    market_years: dict[tuple[str, int], Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise SystemExit("data-audit universe contains invalid market_year entry")
        try:
            key = (str(row["market"]), int(row["year"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit("data-audit universe market_year entry missing market/year") from exc
        if key in market_years:
            raise SystemExit(f"duplicate data-audit universe market-year: {key[0]} {key[1]}")
        market_years[key] = row

    summary = payload.get("summary", {})
    counts = summary.get("audit_status_counts", {}) if isinstance(summary, Mapping) else {}
    if not isinstance(counts, Mapping):
        counts = {}
    return DataAuditUniverse(
        path=path,
        file_hash=file_sha256(path),
        status_counts={str(key): int(value) for key, value in counts.items()},
        market_years=market_years,
    )


def data_audit_evidence_matches(
    split_plan_evidence: Mapping[str, Any] | None,
    universe: DataAuditUniverse,
) -> bool:
    if not isinstance(split_plan_evidence, Mapping):
        return False
    return (
        split_plan_evidence.get("path") == universe.evidence()["path"]
        and split_plan_evidence.get("file_hash") == universe.file_hash
    )
