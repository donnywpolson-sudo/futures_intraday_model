#!/usr/bin/env python3
"""Report-only active-root readiness review for data/raw -> causal data."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = REPO_ROOT / "reports/data_audit/current_state/data_current_state_20260705T153606Z.json"
DEFAULT_RAW_ALIGNMENT = (
    REPO_ROOT / "reports/data_audit/current_state/post_sr_replacement_all_raw_dbn_alignment_20260705.json"
)
DEFAULT_SR_REPLACEMENT = (
    REPO_ROOT / "reports/data_audit/sr1_sr3_2020_parent_sidecar_raw_replacement_20260705.json"
)
DEFAULT_BROAD_MANIFEST = (
    REPO_ROOT / "reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1/causal_base_manifest.json"
)
DEFAULT_BROAD_VALIDATION = (
    REPO_ROOT / "reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1/causal_base_validation.json"
)
DEFAULT_LOCAL_TRADE_MANIFEST = (
    REPO_ROOT / "reports/pipeline_audit/causal_proof_candidates/local_trade_2025_2026_v1/causal_base_manifest.json"
)
DEFAULT_SIX_ROW_REBUILD_MANIFEST = (
    REPO_ROOT
    / "reports/data_audit/causal_base_rebuild/active_root_six_stale_raw_rebuild_20260705/causal_base_manifest.json"
)
DEFAULT_SIX_ROW_REBUILD_VALIDATION = (
    REPO_ROOT
    / "reports/data_audit/current_state/active_root_six_causal_rebuild_validation_20260705.json"
)
DEFAULT_RAW_ROOT = REPO_ROOT / "data/raw"
DEFAULT_CAUSAL_ROOT = REPO_ROOT / "data/causally_gated_normalized"
DEFAULT_JSON_OUT = (
    REPO_ROOT / "reports/data_audit/current_state/active_root_raw_to_causal_readiness_20260705.json"
)
DEFAULT_MARKDOWN_OUT = DEFAULT_JSON_OUT.with_suffix(".md")

NO_MUTATION_TEXT = (
    "Report-only review. No provider/network calls, data mutation, cleanup/archive, "
    "DBN sidecar canonicalization, labels, features, WFA, predictions, modeling, "
    "commit, push, paper, or live work is approved or performed."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def pair_text(pair: tuple[str, int]) -> str:
    return f"{pair[0]}:{pair[1]}"


def pair_from_path(path: Path, root: Path) -> tuple[str, int] | None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    if len(relative.parts) != 2 or relative.suffix.lower() != ".parquet":
        return None
    try:
        return relative.parts[0], int(relative.stem)
    except ValueError:
        return None


def parquet_pairs(root: Path) -> dict[tuple[str, int], Path]:
    if not root.exists():
        return {}
    output: dict[tuple[str, int], Path] = {}
    for path in sorted(root.rglob("*.parquet")):
        pair = pair_from_path(path, root)
        if pair is not None:
            output[pair] = path
    return output


def row_count(path: Path) -> int | None:
    try:
        return int(pq.ParquetFile(path).metadata.num_rows)
    except Exception:  # noqa: BLE001 - report must fail closed without crashing.
        return None


def rows_by_pair(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    output: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        market = row.get("market")
        year = row.get("year")
        if isinstance(market, str) and isinstance(year, int):
            output[(market, year)] = row
    return output


def approved_scope_exclusions(path: Path | None) -> dict[tuple[str, int], dict[str, Any]]:
    if path is None:
        return {}
    payload = read_json(path)
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("approved exclusions report missing summary")

    failures: list[str] = []
    if str(summary.get("status", "")).upper() not in {
        "PASS_APPROVED_ACTIVE_CAUSAL_SCOPE_EXCLUSIONS_NO_RAW_DELETE",
        "PASS_APPROVED_ACTIVE_CAUSAL_SCOPE_EXCLUSION_NO_RAW_DELETE",
    }:
        failures.append(f"approved exclusions status={summary.get('status')!r}")
    for flag in (
        "provider_network_calls",
        "data_mutation_performed",
        "raw_deletion_approved",
        "raw_deletion_performed",
        "causal_rebuild_approved",
        "causal_parquet_writes",
        "labels_features_wfa_predictions_modeling_approved",
        "commit_push_paper_live_approved",
    ):
        if summary.get(flag) is True:
            failures.append(f"{flag} must not be true")

    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        failures.append("approved exclusions rows must be a non-empty list")

    output: dict[tuple[str, int], dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                failures.append("approved exclusion row is not an object")
                continue
            market = row.get("market")
            year = row.get("year")
            disposition = row.get("disposition")
            if not isinstance(market, str) or not isinstance(year, int):
                failures.append(f"approved exclusion row missing market/year: {row!r}")
                continue
            if disposition != "exclude_from_active_causal_scope_no_raw_delete":
                failures.append(f"approved exclusion disposition invalid for {market}:{year}")
                continue
            pair = (market, year)
            if pair in output:
                failures.append(f"duplicate approved exclusion pair: {pair_text(pair)}")
            output[pair] = row

    if failures:
        raise ValueError("approved exclusions validation failed: " + "; ".join(failures))
    return output


def output_hashes_by_pair(
    output_hashes: dict[str, str],
    *,
    active_causal_root: Path,
    repo_root: Path,
) -> dict[tuple[str, int], dict[str, str]]:
    mapped: dict[tuple[str, int], dict[str, str]] = {}
    for historical_path, expected_hash in output_hashes.items():
        parts = Path(historical_path).parts
        if len(parts) < 2:
            continue
        market = parts[-2]
        try:
            year = int(Path(parts[-1]).stem)
        except ValueError:
            continue
        active_path = active_causal_root / market / f"{year}.parquet"
        mapped[(market, year)] = {
            "historical_output_path": historical_path,
            "active_output_path": rel(active_path, repo_root),
            "expected_output_sha256": expected_hash,
        }
    return mapped


def evidence_group(
    *,
    name: str,
    manifest: dict[str, Any],
    validation: dict[str, Any] | None,
    manifest_path: Path,
    validation_path: Path | None,
    active_causal_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    rows = rows_by_pair(manifest.get("outputs", []) or validation.get("files", []) if validation else manifest.get("outputs", []))
    input_hashes = manifest.get("input_file_hashes")
    if not isinstance(input_hashes, dict) and validation is not None:
        input_hashes = validation.get("input_file_hashes")
    output_hashes = manifest.get("output_file_hashes")
    if not isinstance(output_hashes, dict) and validation is not None:
        output_hashes = validation.get("output_file_hashes")
    if not isinstance(input_hashes, dict):
        input_hashes = {}
    if not isinstance(output_hashes, dict):
        output_hashes = {}
    return {
        "name": name,
        "manifest_path": rel(manifest_path, repo_root),
        "manifest_status": manifest.get("status"),
        "validation_path": rel(validation_path, repo_root) if validation_path else None,
        "validation_status": validation.get("status") if validation else None,
        "manifest_output_root": manifest.get("output_root"),
        "validation_output_root": validation.get("output_root") if validation else None,
        "manifest_generated_at": manifest.get("generated_at"),
        "validation_generated_at": validation.get("generated_at") if validation else None,
        "summary": manifest.get("summary"),
        "rows": rows,
        "input_hashes": input_hashes,
        "output_hashes": output_hashes_by_pair(
            output_hashes,
            active_causal_root=active_causal_root,
            repo_root=repo_root,
        ),
        "local_trade_gap_gate_status": (manifest.get("summary") or {}).get("local_trade_ohlcv_gap_gate_status"),
        "historical_candidate_root": str(manifest.get("output_root") or "").startswith(
            ("data/causal_base_candidates", "data/causal_proof_candidates")
        ),
    }


def _hash_cache_get(cache: dict[Path, str], path: Path) -> str:
    cached = cache.get(path)
    if cached is not None:
        return cached
    digest = sha256_file(path)
    cache[path] = digest
    return digest


def build_report(
    *,
    repo_root: Path,
    ledger_path: Path,
    raw_alignment_path: Path,
    sr_replacement_path: Path,
    broad_manifest_path: Path,
    broad_validation_path: Path,
    local_trade_manifest_path: Path,
    six_row_rebuild_manifest_path: Path,
    six_row_rebuild_validation_path: Path,
    raw_root: Path,
    causal_root: Path,
    approved_exclusions_path: Path | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    ledger = read_json(ledger_path)
    raw_alignment = read_json(raw_alignment_path)
    sr_replacement = read_json(sr_replacement_path)
    broad_manifest = read_json(broad_manifest_path)
    broad_validation = read_json(broad_validation_path)
    local_trade_manifest = read_json(local_trade_manifest_path)
    six_row_rebuild_manifest = read_json(six_row_rebuild_manifest_path)
    six_row_rebuild_validation = read_json(six_row_rebuild_validation_path)

    raw_pairs = parquet_pairs(raw_root)
    causal_pairs = parquet_pairs(causal_root)
    raw_pair_set = set(raw_pairs)
    causal_pair_set = set(causal_pairs)
    exclusions = approved_scope_exclusions(approved_exclusions_path)
    approved_exclusion_pairs = set(exclusions)

    groups = [
        evidence_group(
            name="broad_manifest_527_rebuild_v1",
            manifest=broad_manifest,
            validation=broad_validation,
            manifest_path=broad_manifest_path,
            validation_path=broad_validation_path,
            active_causal_root=causal_root,
            repo_root=repo_root,
        ),
        evidence_group(
            name="active_root_six_stale_raw_rebuild_20260705",
            manifest=six_row_rebuild_manifest,
            validation=six_row_rebuild_validation,
            manifest_path=six_row_rebuild_manifest_path,
            validation_path=six_row_rebuild_validation_path,
            active_causal_root=causal_root,
            repo_root=repo_root,
        ),
        evidence_group(
            name="local_trade_2025_2026_v1",
            manifest=local_trade_manifest,
            validation=None,
            manifest_path=local_trade_manifest_path,
            validation_path=None,
            active_causal_root=causal_root,
            repo_root=repo_root,
        ),
    ]
    pair_to_group: dict[tuple[str, int], dict[str, Any]] = {}
    duplicate_evidence_pairs: list[str] = []
    for group in groups:
        for pair in group["output_hashes"]:
            if pair in pair_to_group:
                duplicate_evidence_pairs.append(pair_text(pair))
            pair_to_group[pair] = group

    hash_cache: dict[Path, str] = {}
    covered_pairs = set(pair_to_group)
    missing_active_causal: list[dict[str, Any]] = []
    active_causal_hash_mismatches: list[dict[str, Any]] = []
    active_causal_row_mismatches: list[dict[str, Any]] = []
    stale_raw_input_hashes: list[dict[str, Any]] = []
    covered_rows: list[dict[str, Any]] = []

    for pair in sorted(covered_pairs):
        group = pair_to_group[pair]
        expected = group["output_hashes"][pair]
        active_path = causal_root / pair[0] / f"{pair[1]}.parquet"
        source_row = group["rows"].get(pair, {})
        expected_rows = source_row.get("output_rows")
        raw_path_text = str(source_row.get("input_path") or f"data/raw/{pair[0]}/{pair[1]}.parquet")
        raw_path = resolve_path(repo_root, raw_path_text)
        raw_expected_hash = group["input_hashes"].get(raw_path_text) or source_row.get("source_file_hash")

        active_present = active_path.is_file()
        active_hash = _hash_cache_get(hash_cache, active_path) if active_present else None
        active_rows = row_count(active_path) if active_present else None
        raw_present = raw_path.is_file()
        raw_hash = _hash_cache_get(hash_cache, raw_path) if raw_present else None
        raw_hash_matches = bool(raw_expected_hash and raw_hash == raw_expected_hash)
        causal_hash_matches = bool(active_hash and active_hash == expected["expected_output_sha256"])
        row_matches = expected_rows is None or active_rows == expected_rows

        row = {
            "pair": pair_text(pair),
            "market": pair[0],
            "year": pair[1],
            "evidence_group": group["name"],
            "historical_output_path": expected["historical_output_path"],
            "active_causal_path": expected["active_output_path"],
            "active_causal_present": active_present,
            "active_causal_sha256": active_hash,
            "expected_causal_sha256": expected["expected_output_sha256"],
            "active_causal_hash_matches_evidence": causal_hash_matches,
            "active_causal_rows": active_rows,
            "expected_causal_rows": expected_rows,
            "active_causal_rows_match_evidence": row_matches,
            "raw_path": raw_path_text,
            "current_raw_present": raw_present,
            "current_raw_sha256": raw_hash,
            "evidence_raw_sha256": raw_expected_hash,
            "current_raw_hash_matches_evidence": raw_hash_matches,
            "evidence_status": source_row.get("status"),
            "local_trade_gap_gate_status": source_row.get("local_trade_gap_gate_status")
            or group.get("local_trade_gap_gate_status"),
        }
        covered_rows.append(row)

        if not active_present:
            missing_active_causal.append(row)
        elif not causal_hash_matches:
            active_causal_hash_mismatches.append(row)
        if active_present and not row_matches:
            active_causal_row_mismatches.append(row)
        if raw_expected_hash and raw_present and not raw_hash_matches:
            stale_raw_input_hashes.append(row)

    raw_without_causal_all = sorted(raw_pair_set - causal_pair_set)
    approved_raw_without_causal_exclusions = sorted(
        (raw_pair_set - causal_pair_set) & approved_exclusion_pairs
    )
    raw_without_causal = sorted((raw_pair_set - causal_pair_set) - approved_exclusion_pairs)
    invalid_approved_exclusions = sorted(approved_exclusion_pairs - (raw_pair_set - causal_pair_set))
    causal_without_raw = sorted(causal_pair_set - raw_pair_set)
    causal_without_evidence = sorted(causal_pair_set - covered_pairs)
    evidence_without_active = sorted(covered_pairs - causal_pair_set)

    local_trade_gate_counts = Counter(
        str(row.get("local_trade_gap_gate_status") or "UNKNOWN") for row in covered_rows
    )
    historical_group_count = sum(1 for group in groups if group["historical_candidate_root"])
    blockers: list[dict[str, Any]] = []
    if raw_alignment.get("status") != "PASS":
        blockers.append(
            {
                "severity": "Severe",
                "blocker": "Raw/DBN alignment is not PASS.",
                "evidence": raw_alignment.get("status"),
            }
        )
    if sr_replacement.get("status") != "PASS":
        blockers.append(
            {
                "severity": "Severe",
                "blocker": "SR1/SR3 replacement report is not PASS.",
                "evidence": sr_replacement.get("status"),
            }
        )
    non_pass_evidence = [
        {
            "name": group["name"],
            "manifest_status": group["manifest_status"],
            "validation_status": group["validation_status"],
        }
        for group in groups
        if group["manifest_status"] != "PASS"
        or (group["validation_status"] is not None and group["validation_status"] != "PASS")
    ]
    if non_pass_evidence:
        blockers.append(
            {
                "severity": "Severe",
                "blocker": "One or more causal evidence reports are not PASS.",
                "evidence": non_pass_evidence,
            }
        )
    if missing_active_causal or active_causal_hash_mismatches or active_causal_row_mismatches:
        blockers.append(
            {
                "severity": "Severe",
                "blocker": "Active causal files do not match their historical validation evidence.",
                "evidence": {
                    "missing_active_causal_count": len(missing_active_causal),
                    "active_causal_hash_mismatch_count": len(active_causal_hash_mismatches),
                    "active_causal_row_mismatch_count": len(active_causal_row_mismatches),
                },
            }
        )
    if stale_raw_input_hashes:
        blockers.append(
            {
                "severity": "Medium",
                "blocker": "Some active causal files were built from raw hashes that differ from current active raw.",
                "evidence": [row["pair"] for row in stale_raw_input_hashes],
            }
        )
    if raw_without_causal:
        blockers.append(
            {
                "severity": "Medium",
                "blocker": "Some active raw pairs have no active causal output and no approved active-scope exclusion.",
                "evidence": [pair_text(pair) for pair in raw_without_causal],
            }
        )
    if invalid_approved_exclusions:
        blockers.append(
            {
                "severity": "Severe",
                "blocker": "Approved active-scope exclusions do not match raw-without-causal rows.",
                "evidence": [pair_text(pair) for pair in invalid_approved_exclusions],
            }
        )
    if causal_without_evidence:
        blockers.append(
            {
                "severity": "Severe",
                "blocker": "Some active causal files have no accepted historical validation evidence.",
                "evidence": [pair_text(pair) for pair in causal_without_evidence],
            }
        )
    if local_trade_gate_counts.get("NOT_RUN", 0):
        blockers.append(
            {
                "severity": "Medium",
                "blocker": "Local trade/OHLCV gap gate remains NOT_RUN in causal evidence.",
                "evidence": dict(sorted(local_trade_gate_counts.items())),
            }
        )
    if historical_group_count:
        blockers.append(
            {
                "severity": "Low",
                "blocker": "Causal evidence reports still name historical/candidate output roots.",
                "evidence": [
                    {
                        "name": group["name"],
                        "manifest_output_root": group["manifest_output_root"],
                    }
                    for group in groups
                    if group["historical_candidate_root"]
                ],
            }
        )

    severe_count = sum(1 for item in blockers if item["severity"] == "Severe")
    medium_count = sum(1 for item in blockers if item["severity"] == "Medium")
    status = "FAIL" if severe_count else "WARN" if medium_count or blockers else "PASS"

    return {
        "summary": {
            "stage": "active_root_raw_to_causal_readiness_review",
            "status": status,
            "generated_at_utc": generated_at_utc or utc_now(),
            "raw_root": rel(raw_root, repo_root),
            "causal_root": rel(causal_root, repo_root),
            "raw_alignment_status": raw_alignment.get("status"),
            "raw_alignment_expected_market_year_count": raw_alignment.get("expected_market_year_count"),
            "raw_alignment_raw_market_year_count": raw_alignment.get("raw_market_year_count"),
            "raw_alignment_source_hash_mismatch_count": raw_alignment.get("source_hash_mismatch_count"),
            "raw_alignment_definition_join_mismatch_count": raw_alignment.get("definition_join_mismatch_count"),
            "sr_replacement_status": sr_replacement.get("status"),
            "active_raw_pair_count": len(raw_pairs),
            "active_scope_raw_pair_count": len(raw_pairs) - len(approved_raw_without_causal_exclusions),
            "active_causal_pair_count": len(causal_pairs),
            "historical_evidence_pair_count": len(covered_pairs),
            "active_causal_with_evidence_count": len(causal_pair_set & covered_pairs),
            "raw_without_causal_count": len(raw_without_causal),
            "raw_without_causal_all_count": len(raw_without_causal_all),
            "approved_active_scope_exclusion_count": len(approved_raw_without_causal_exclusions),
            "invalid_approved_active_scope_exclusion_count": len(invalid_approved_exclusions),
            "causal_without_raw_count": len(causal_without_raw),
            "causal_without_evidence_count": len(causal_without_evidence),
            "evidence_without_active_count": len(evidence_without_active),
            "active_causal_hash_mismatch_count": len(active_causal_hash_mismatches),
            "active_causal_row_mismatch_count": len(active_causal_row_mismatches),
            "stale_raw_input_hash_count": len(stale_raw_input_hashes),
            "local_trade_gap_gate_status_counts": dict(sorted(local_trade_gate_counts.items())),
            "blocker_count": len(blockers),
            "severe_blocker_count": severe_count,
            "medium_blocker_count": medium_count,
            "data_access": "read_existing_json_and_parquet_metadata_plus_sha256_hashes",
            "data_mutation_performed": False,
            "provider_network_calls": False,
            "cleanup_archive_approved": False,
            "causal_rebuild_approved": False,
            "labels_features_wfa_predictions_modeling_approved": False,
            "commit_push_paper_live_approved": False,
            "non_approval": NO_MUTATION_TEXT,
        },
        "input_evidence": {
            "ledger": rel(ledger_path, repo_root),
            "ledger_sha256": sha256_file(ledger_path),
            "raw_alignment": rel(raw_alignment_path, repo_root),
            "raw_alignment_sha256": sha256_file(raw_alignment_path),
            "sr_replacement": rel(sr_replacement_path, repo_root),
            "sr_replacement_sha256": sha256_file(sr_replacement_path),
            "broad_manifest": rel(broad_manifest_path, repo_root),
            "broad_manifest_sha256": sha256_file(broad_manifest_path),
            "broad_validation": rel(broad_validation_path, repo_root),
            "broad_validation_sha256": sha256_file(broad_validation_path),
            "local_trade_manifest": rel(local_trade_manifest_path, repo_root),
            "local_trade_manifest_sha256": sha256_file(local_trade_manifest_path),
            "six_row_rebuild_manifest": rel(six_row_rebuild_manifest_path, repo_root),
            "six_row_rebuild_manifest_sha256": sha256_file(six_row_rebuild_manifest_path),
            "six_row_rebuild_validation": rel(six_row_rebuild_validation_path, repo_root),
            "six_row_rebuild_validation_sha256": sha256_file(six_row_rebuild_validation_path),
            "approved_exclusions": rel(approved_exclusions_path, repo_root)
            if approved_exclusions_path
            else None,
            "approved_exclusions_sha256": sha256_file(approved_exclusions_path)
            if approved_exclusions_path
            else None,
            "accepted_decision_count": len(ledger.get("accepted_decisions", [])),
        },
        "evidence_groups": [
            {
                "name": group["name"],
                "manifest_path": group["manifest_path"],
                "manifest_status": group["manifest_status"],
                "validation_path": group["validation_path"],
                "validation_status": group["validation_status"],
                "manifest_output_root": group["manifest_output_root"],
                "validation_output_root": group["validation_output_root"],
                "historical_candidate_root": group["historical_candidate_root"],
                "evidence_pair_count": len(group["output_hashes"]),
                "local_trade_gap_gate_status": group["local_trade_gap_gate_status"],
            }
            for group in groups
        ],
        "blockers": blockers,
        "raw_without_causal": [
            {"pair": pair_text(pair), "market": pair[0], "year": pair[1], "raw_path": rel(raw_pairs[pair], repo_root)}
            for pair in raw_without_causal
        ],
        "approved_active_scope_exclusions": [
            {
                "pair": pair_text(pair),
                "market": pair[0],
                "year": pair[1],
                "raw_path": rel(raw_pairs[pair], repo_root),
                "reason": exclusions[pair].get("reason"),
            }
            for pair in approved_raw_without_causal_exclusions
        ],
        "invalid_approved_active_scope_exclusions": [
            {
                "pair": pair_text(pair),
                "market": pair[0],
                "year": pair[1],
                "raw_path": rel(raw_pairs[pair], repo_root) if pair in raw_pairs else None,
                "causal_path": rel(causal_pairs[pair], repo_root) if pair in causal_pairs else None,
            }
            for pair in invalid_approved_exclusions
        ],
        "causal_without_raw": [
            {"pair": pair_text(pair), "market": pair[0], "year": pair[1], "causal_path": rel(causal_pairs[pair], repo_root)}
            for pair in causal_without_raw
        ],
        "causal_without_evidence": [
            {"pair": pair_text(pair), "market": pair[0], "year": pair[1], "causal_path": rel(causal_pairs[pair], repo_root)}
            for pair in causal_without_evidence
        ],
        "evidence_without_active": [
            {"pair": pair_text(pair), "market": pair[0], "year": pair[1]}
            for pair in evidence_without_active
        ],
        "stale_raw_input_hash_rows": [
            {
                "pair": row["pair"],
                "evidence_group": row["evidence_group"],
                "raw_path": row["raw_path"],
                "current_raw_sha256": row["current_raw_sha256"],
                "evidence_raw_sha256": row["evidence_raw_sha256"],
                "active_causal_path": row["active_causal_path"],
            }
            for row in stale_raw_input_hashes
        ],
        "active_causal_hash_mismatch_rows": [
            {
                "pair": row["pair"],
                "evidence_group": row["evidence_group"],
                "active_causal_path": row["active_causal_path"],
                "active_causal_sha256": row["active_causal_sha256"],
                "expected_causal_sha256": row["expected_causal_sha256"],
            }
            for row in active_causal_hash_mismatches
        ],
        "active_causal_row_mismatch_rows": [
            {
                "pair": row["pair"],
                "evidence_group": row["evidence_group"],
                "active_causal_path": row["active_causal_path"],
                "active_causal_rows": row["active_causal_rows"],
                "expected_causal_rows": row["expected_causal_rows"],
            }
            for row in active_causal_row_mismatches
        ],
        "recommended_next_step": (
            "Use this refreshed report as current causal-root planning evidence; keep unapproved raw-without-causal "
            "pairs deferred until a separate bounded policy disposition is approved."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Active Root Raw To Causal Readiness Review",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        f"- Status: `{summary['status']}`.",
        f"- Raw root: `{summary['raw_root']}`.",
        f"- Causal root: `{summary['causal_root']}`.",
        f"- Active raw pairs: {summary['active_raw_pair_count']}.",
        f"- Active-scope raw pairs after approved exclusions: {summary['active_scope_raw_pair_count']}.",
        f"- Active causal pairs: {summary['active_causal_pair_count']}.",
        f"- Historical evidence pairs: {summary['historical_evidence_pair_count']}.",
        f"- Active causal with evidence: {summary['active_causal_with_evidence_count']}.",
        f"- Raw without causal: {summary['raw_without_causal_count']}.",
        f"- Approved active-scope exclusions: {summary['approved_active_scope_exclusion_count']}.",
        f"- Causal without raw: {summary['causal_without_raw_count']}.",
        f"- Causal without evidence: {summary['causal_without_evidence_count']}.",
        f"- Active causal hash mismatches vs evidence: {summary['active_causal_hash_mismatch_count']}.",
        f"- Active causal row mismatches vs evidence: {summary['active_causal_row_mismatch_count']}.",
        f"- Stale raw-input hashes vs causal evidence: {summary['stale_raw_input_hash_count']}.",
        f"- Local trade/OHLCV gap gate counts: `{json.dumps(summary['local_trade_gap_gate_status_counts'], sort_keys=True)}`.",
        f"- Data access: `{summary['data_access']}`.",
        "",
        "## Non-Approval",
        "",
        f"- {summary['non_approval']}",
        "- `data_mutation_performed`: false.",
        "- `causal_rebuild_approved`: false.",
        "- `labels_features_wfa_predictions_modeling_approved`: false.",
        "- `commit_push_paper_live_approved`: false.",
        "",
        "## Evidence Groups",
        "",
        "| group | status | pairs | output root | historical root | local-trade gate |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for group in report["evidence_groups"]:
        lines.append(
            "| "
            f"{group['name']} | "
            f"`{group['manifest_status']}` | "
            f"{group['evidence_pair_count']} | "
            f"`{group['manifest_output_root']}` | "
            f"{str(group['historical_candidate_root']).lower()} | "
            f"`{group['local_trade_gap_gate_status']}` |"
        )
    lines.extend(["", "## Blockers", ""])
    if report["blockers"]:
        for blocker in report["blockers"]:
            lines.append(
                f"- `{blocker['severity']}`: {blocker['blocker']} Evidence: "
                f"`{json.dumps(blocker['evidence'], sort_keys=True)}`."
            )
    else:
        lines.append("- None.")
    lines.extend(["", "## Stale Raw Input Hash Rows", ""])
    if report["stale_raw_input_hash_rows"]:
        lines.extend(
            [
                "| pair | evidence group | raw path | active causal path |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in report["stale_raw_input_hash_rows"]:
            lines.append(
                "| "
                f"{row['pair']} | "
                f"{row['evidence_group']} | "
                f"`{row['raw_path']}` | "
                f"`{row['active_causal_path']}` |"
            )
    else:
        lines.append("- None.")
    lines.extend(["", "## Raw Without Active Causal", ""])
    if report["raw_without_causal"]:
        lines.extend(["| pair | raw path |", "| --- | --- |"])
        for row in report["raw_without_causal"]:
            lines.append(f"| {row['pair']} | `{row['raw_path']}` |")
    else:
        lines.append("- None.")
    lines.extend(["", "## Approved Active-Scope Exclusions", ""])
    if report["approved_active_scope_exclusions"]:
        lines.extend(["| pair | raw path | reason |", "| --- | --- | --- |"])
        for row in report["approved_active_scope_exclusions"]:
            lines.append(f"| {row['pair']} | `{row['raw_path']}` | {row.get('reason') or ''} |")
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Recommended Next Step",
            "",
            f"- {report['recommended_next_step']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: dict[str, Any], *, json_out: Path, markdown_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--raw-alignment", default=str(DEFAULT_RAW_ALIGNMENT))
    parser.add_argument("--sr-replacement", default=str(DEFAULT_SR_REPLACEMENT))
    parser.add_argument("--broad-manifest", default=str(DEFAULT_BROAD_MANIFEST))
    parser.add_argument("--broad-validation", default=str(DEFAULT_BROAD_VALIDATION))
    parser.add_argument("--local-trade-manifest", default=str(DEFAULT_LOCAL_TRADE_MANIFEST))
    parser.add_argument("--six-row-rebuild-manifest", default=str(DEFAULT_SIX_ROW_REBUILD_MANIFEST))
    parser.add_argument("--six-row-rebuild-validation", default=str(DEFAULT_SIX_ROW_REBUILD_VALIDATION))
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--causal-root", default=str(DEFAULT_CAUSAL_ROOT))
    parser.add_argument("--approved-exclusions", default=None)
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    try:
        report = build_report(
            repo_root=repo_root,
            ledger_path=resolve_path(repo_root, args.ledger),
            raw_alignment_path=resolve_path(repo_root, args.raw_alignment),
            sr_replacement_path=resolve_path(repo_root, args.sr_replacement),
            broad_manifest_path=resolve_path(repo_root, args.broad_manifest),
            broad_validation_path=resolve_path(repo_root, args.broad_validation),
            local_trade_manifest_path=resolve_path(repo_root, args.local_trade_manifest),
            six_row_rebuild_manifest_path=resolve_path(repo_root, args.six_row_rebuild_manifest),
            six_row_rebuild_validation_path=resolve_path(repo_root, args.six_row_rebuild_validation),
            raw_root=resolve_path(repo_root, args.raw_root),
            causal_root=resolve_path(repo_root, args.causal_root),
            approved_exclusions_path=resolve_path(repo_root, args.approved_exclusions)
            if args.approved_exclusions
            else None,
        )
    except ValueError as exc:
        print(f"FAIL active_root_raw_to_causal_readiness_review: {exc}")
        return 1
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    write_report(report, json_out=json_out, markdown_out=markdown_out)
    summary = report["summary"]
    print(
        "active_root_raw_to_causal_readiness_review "
        f"status={summary['status']} "
        f"active_raw_pairs={summary['active_raw_pair_count']} "
        f"active_causal_pairs={summary['active_causal_pair_count']} "
        f"stale_raw_input_hash_count={summary['stale_raw_input_hash_count']} "
        f"raw_without_causal_count={summary['raw_without_causal_count']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0 if summary["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
