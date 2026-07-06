#!/usr/bin/env python3
"""Read-only audit-readiness gate for the approved 460-row Phase 2 scope."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation.feature_leakage_guard import forbidden_feature_columns

TARGET_CANONICAL_PATTERN = (
    "data/causally_gated_normalized/{market}/{year}.parquet"
)
CANONICAL_ROOT_REL = "data/causally_gated_normalized"
REPORTS_ROOT_REL = "reports/data_audit/causal_base_rebuild/broad_manifest_527_rebuild_v1"
DEFAULT_DATA_MANIFEST = REPO_ROOT / "configs/data_manifest.yaml"
DEFAULT_CANONICAL_ROOT = REPO_ROOT / CANONICAL_ROOT_REL
DEFAULT_REPORTS_ROOT = REPO_ROOT / REPORTS_ROOT_REL
DEFAULT_PHASE2_MANIFEST = DEFAULT_REPORTS_ROOT / "causal_base_manifest.json"
DEFAULT_PHASE2_VALIDATION = DEFAULT_REPORTS_ROOT / "causal_base_validation.json"
DEFAULT_PROFILE_CONFIG = REPO_ROOT / "configs/alpha_tiered.yaml"
DEFAULT_BUILD_SCRIPT = REPO_ROOT / "scripts/phase2_causal_base/build_causal_base_data.py"
EXPECTED_CANONICAL_COUNT = 460
FORBIDDEN_PAIR = ("6M", 2012)
FORBIDDEN_YEARS = (2025, 2026)
ALLOWED_MIN_YEAR = 2010
ALLOWED_MAX_YEAR = 2024
STATUS_GO = "CONDITIONAL_GO_CANONICAL_PHASE2_460_ONLY"
STATUS_NO_GO = "NO_GO_CANONICAL_PHASE2_460_AUDIT_READINESS"
WARN_NOT_CURRENT_BASELINE = "WARN_NOT_CURRENT_BASELINE"
WARN_NOT_PIT_APPROVED = "WARN_NOT_PIT_APPROVED"
WARN_NOT_RUN = "WARN_NOT_RUN"

OPTIONAL_METADATA_PREFIXES = ("status_", "stat_", "statistics_")
OPTIONAL_METADATA_TERMS = ("settlement", "open_interest", "cleared_volume")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(repo_root: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def _parquet_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(root.rglob("*.parquet"))


def _pair_from_path(path: Path, root: Path) -> tuple[str, int] | None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    if len(relative.parts) != 2 or relative.suffix != ".parquet":
        return None
    try:
        year = int(relative.stem)
    except ValueError:
        return None
    return relative.parts[0], year


def _pairs_from_entries(entries: Any) -> set[tuple[str, int]]:
    pairs: set[tuple[str, int]] = set()
    if not isinstance(entries, list):
        return pairs
    for item in entries:
        if not isinstance(item, dict):
            continue
        market = item.get("market")
        year = item.get("year")
        if isinstance(market, str) and isinstance(year, int):
            pairs.add((market, year))
    return pairs


def _count_list(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


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


def _warn(
    warnings: list[dict[str, Any]],
    *,
    name: str,
    code: str,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    warnings.append(
        {
            "name": name,
            "code": code,
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _load_default_feature_cols(feature_cols: Iterable[str] | None) -> list[str]:
    if feature_cols is not None:
        return list(feature_cols)
    from scripts.phase4_features.build_baseline_features import FEATURE_COLS

    return list(FEATURE_COLS)


def evaluate_readiness(
    *,
    repo_root: Path,
    data_manifest_path: Path,
    canonical_root: Path,
    reports_root: Path,
    phase2_manifest_path: Path,
    phase2_validation_path: Path,
    profile_config_path: Path,
    build_script_path: Path,
    expected_count: int = EXPECTED_CANONICAL_COUNT,
    feature_cols: Iterable[str] | None = None,
    git_head: str | None = None,
    staged_names: list[str] | None = None,
    scoped_status_lines: list[str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    data_manifest = read_yaml(data_manifest_path)
    phase2_manifest = read_json(phase2_manifest_path)
    phase2_validation = read_json(phase2_validation_path)

    checks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    canonical_root_rel = rel(canonical_root, repo_root)
    reports_root_rel = rel(reports_root, repo_root)
    canonical_pattern = str(
        ((data_manifest.get("canonical_paths") or {}).get("causal_parquet_pattern") or "")
    )
    parquet_paths = _parquet_paths(canonical_root)
    filesystem_pairs = {
        pair for path in parquet_paths if (pair := _pair_from_path(path, canonical_root)) is not None
    }
    malformed_paths = [
        rel(path, repo_root)
        for path in parquet_paths
        if _pair_from_path(path, canonical_root) is None
    ]
    manifest_pairs = _pairs_from_entries(phase2_manifest.get("requested_market_years"))
    if not manifest_pairs:
        manifest_pairs = _pairs_from_entries(phase2_manifest.get("outputs"))
    manifest_output_count = _count_list(phase2_manifest.get("outputs"))
    requested_count = _count_list(phase2_manifest.get("requested_market_years"))
    validation_file_count = _count_list(phase2_validation.get("files"))
    validation_summary = (
        phase2_validation.get("summary")
        if isinstance(phase2_validation.get("summary"), dict)
        else {}
    )
    validation_summary_file_count = validation_summary.get("file_count")
    validation_summary_pass_count = validation_summary.get("pass_count")
    validation_summary_fail_count = validation_summary.get("fail_count")
    local_trade_gate_status = validation_summary.get("local_trade_ohlcv_gap_gate_status")
    forbidden_pair_path = canonical_root / FORBIDDEN_PAIR[0] / f"{FORBIDDEN_PAIR[1]}.parquet"
    forbidden_year_counts = {
        year: len(list(canonical_root.rglob(f"{year}.parquet"))) if canonical_root.exists() else 0
        for year in FORBIDDEN_YEARS
    }
    out_of_range_pairs = sorted(
        pair for pair in filesystem_pairs if pair[1] < ALLOWED_MIN_YEAR or pair[1] > ALLOWED_MAX_YEAR
    )
    current_head = git_head or (run_git(repo_root, ["rev-parse", "HEAD"])[0])
    staged = staged_names if staged_names is not None else run_git(repo_root, ["diff", "--cached", "--name-only"])
    scoped_status = (
        scoped_status_lines
        if scoped_status_lines is not None
        else run_git(repo_root, ["status", "--short", "--", "data", "reports", "configs", "models", "predictions"])
    )
    current_script_hash = sha256_file(build_script_path) if build_script_path.exists() else None
    current_profile_config_hash = sha256_file(profile_config_path) if profile_config_path.exists() else None
    current_features = _load_default_feature_cols(feature_cols)
    forbidden_features = forbidden_feature_columns(current_features)

    _check(
        checks,
        name="canonical_config_pattern",
        passed=canonical_pattern == TARGET_CANONICAL_PATTERN,
        observed=canonical_pattern,
        expected=TARGET_CANONICAL_PATTERN,
        detail="The promoted canonical config must point at the approved 460-row root.",
    )
    _check(
        checks,
        name="canonical_root_exists",
        passed=canonical_root.exists() and canonical_root.is_dir(),
        observed=canonical_root_rel,
        expected="existing directory",
        detail="Canonical 460-row root must exist.",
    )
    _check(
        checks,
        name="reports_root_exists",
        passed=reports_root.exists() and reports_root.is_dir(),
        observed=reports_root_rel,
        expected="existing directory",
        detail="Paired Phase 2 reports root must exist.",
    )
    _check(
        checks,
        name="canonical_parquet_count",
        passed=len(parquet_paths) == expected_count,
        observed=len(parquet_paths),
        expected=expected_count,
        detail="Canonical root must contain exactly the approved 460 parquet files.",
    )
    _check(
        checks,
        name="canonical_path_shape",
        passed=not malformed_paths,
        observed=malformed_paths[:20],
        expected=[],
        detail="Canonical parquet paths must be {market}/{year}.parquet under the approved root.",
    )
    _check(
        checks,
        name="canonical_year_range",
        passed=not out_of_range_pairs,
        observed=out_of_range_pairs[:20],
        expected=f"{ALLOWED_MIN_YEAR}-{ALLOWED_MAX_YEAR}",
        detail="Approved canonical audit scope excludes 2025/2026 and any non-research years.",
    )
    _check(
        checks,
        name="forbidden_6m_2012_absent",
        passed=not forbidden_pair_path.exists(),
        observed=forbidden_pair_path.exists(),
        expected=False,
        detail="6M:2012 must remain fail-closed and excluded.",
    )
    for year, count in forbidden_year_counts.items():
        _check(
            checks,
            name=f"forbidden_{year}_absent",
            passed=count == 0,
            observed=count,
            expected=0,
            detail=f"{year} rows remain holdout/forward and out of this remediation scope.",
        )
    _check(
        checks,
        name="manifest_status",
        passed=phase2_manifest.get("status") == "PASS",
        observed=phase2_manifest.get("status"),
        expected="PASS",
        detail="Phase 2 manifest status must be PASS.",
    )
    _check(
        checks,
        name="validation_status",
        passed=phase2_validation.get("status") == "PASS",
        observed=phase2_validation.get("status"),
        expected="PASS",
        detail="Phase 2 validation status must be PASS.",
    )
    _check(
        checks,
        name="manifest_output_root",
        passed=phase2_manifest.get("output_root") == CANONICAL_ROOT_REL,
        observed=phase2_manifest.get("output_root"),
        expected=CANONICAL_ROOT_REL,
        detail="Manifest output root must match the approved canonical root.",
    )
    _check(
        checks,
        name="manifest_reports_root",
        passed=phase2_manifest.get("reports_root") == REPORTS_ROOT_REL,
        observed=phase2_manifest.get("reports_root"),
        expected=REPORTS_ROOT_REL,
        detail="Manifest reports root must match the paired Phase 2 reports root.",
    )
    _check(
        checks,
        name="manifest_output_count",
        passed=manifest_output_count == expected_count,
        observed=manifest_output_count,
        expected=expected_count,
        detail="Manifest outputs must match approved 460-row scope.",
    )
    _check(
        checks,
        name="manifest_requested_count",
        passed=requested_count in {None, expected_count},
        observed=requested_count,
        expected=f"None or {expected_count}",
        detail="Requested market-year scope must not claim broader coverage.",
    )
    _check(
        checks,
        name="validation_file_count",
        passed=validation_file_count == expected_count,
        observed=validation_file_count,
        expected=expected_count,
        detail="Validation files must match approved 460-row scope.",
    )
    _check(
        checks,
        name="validation_summary_file_count",
        passed=validation_summary_file_count == expected_count,
        observed=validation_summary_file_count,
        expected=expected_count,
        detail="Validation summary file_count must match approved 460-row scope.",
    )
    _check(
        checks,
        name="validation_summary_pass_fail",
        passed=validation_summary_pass_count == expected_count and validation_summary_fail_count == 0,
        observed={"pass_count": validation_summary_pass_count, "fail_count": validation_summary_fail_count},
        expected={"pass_count": expected_count, "fail_count": 0},
        detail="Validation summary must pass all approved canonical files.",
    )
    _check(
        checks,
        name="filesystem_matches_manifest_scope",
        passed=not manifest_pairs or filesystem_pairs == manifest_pairs,
        observed={
            "filesystem_only": sorted(filesystem_pairs - manifest_pairs)[:20],
            "manifest_only": sorted(manifest_pairs - filesystem_pairs)[:20],
        },
        expected="filesystem pairs match manifest requested/output pairs",
        detail="Filesystem canonical files must match the manifest-derived 460-row scope.",
    )
    _check(
        checks,
        name="nothing_staged",
        passed=not staged,
        observed=staged,
        expected=[],
        detail="Audit-readiness gate must run with no staged changes.",
    )
    _check(
        checks,
        name="artifact_config_status_clean",
        passed=not scoped_status,
        observed=scoped_status,
        expected=[],
        detail="data/reports/configs/models/predictions must have no tracked or untracked status lines.",
    )
    _check(
        checks,
        name="feature_denylist_clean",
        passed=not forbidden_features,
        observed=forbidden_features,
        expected=[],
        detail="Current baseline feature registry must not include blocked PIT/leakage columns.",
    )

    if phase2_manifest.get("git_commit") != current_head:
        _warn(
            warnings,
            name="manifest_git_commit_current",
            code=WARN_NOT_CURRENT_BASELINE,
            observed=phase2_manifest.get("git_commit"),
            expected=current_head,
            detail="Phase 2 manifest was generated under a different commit; treat as lineage evidence, not current-baseline proof.",
        )
    if phase2_manifest.get("script_hash") != current_script_hash:
        _warn(
            warnings,
            name="manifest_script_hash_current",
            code=WARN_NOT_CURRENT_BASELINE,
            observed=phase2_manifest.get("script_hash"),
            expected=current_script_hash,
            detail="Phase 2 manifest script hash does not match the current builder script.",
        )
    if phase2_manifest.get("config_hash") != current_profile_config_hash:
        _warn(
            warnings,
            name="manifest_config_hash_current",
            code=WARN_NOT_CURRENT_BASELINE,
            observed=phase2_manifest.get("config_hash"),
            expected=current_profile_config_hash,
            detail="Phase 2 manifest config hash does not match the current profile config.",
        )
    if not phase2_manifest.get("generated_at"):
        _warn(
            warnings,
            name="manifest_generated_at_present",
            code=WARN_NOT_CURRENT_BASELINE,
            observed=phase2_manifest.get("generated_at"),
            expected="UTC timestamp",
            detail="Phase 2 manifest lacks a generated timestamp.",
        )
    if local_trade_gate_status != "PASS":
        _warn(
            warnings,
            name="local_trade_ohlcv_gap_gate",
            code=WARN_NOT_RUN if local_trade_gate_status == "NOT_RUN" else "WARN_NOT_PASS",
            observed=local_trade_gate_status,
            expected="PASS",
            detail="Local trade/OHLCV gap proof is not complete for this canonical validation report.",
        )
    _warn(
        warnings,
        name="optional_metadata_pit_approval",
        code=WARN_NOT_PIT_APPROVED,
        observed={
            "blocked_prefixes": OPTIONAL_METADATA_PREFIXES,
            "blocked_terms": OPTIONAL_METADATA_TERMS,
        },
        expected="field-level available_at <= decision_time proof",
        detail="Optional status/statistics/settlement-style metadata remains audit-only until PIT availability is proven.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_GO if not failures else STATUS_NO_GO
    return {
        "summary": {
            "stage": "phase2_460_audit_readiness",
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "approved_scope": "raw/source plus promoted canonical broad_manifest_527_rebuild_v1 460-row Phase 2",
            "canonical_root": canonical_root_rel,
            "reports_root": reports_root_rel,
            "canonical_config_pattern": canonical_pattern,
            "expected_count": expected_count,
            "canonical_parquet_count": len(parquet_paths),
            "manifest_output_count": manifest_output_count,
            "validation_file_count": validation_file_count,
            "validation_summary_file_count": validation_summary_file_count,
            "validation_pass_count": validation_summary_pass_count,
            "validation_fail_count": validation_summary_fail_count,
            "forbidden_6m_2012_present": forbidden_pair_path.exists(),
            "forbidden_year_counts": {str(year): count for year, count in forbidden_year_counts.items()},
            "current_git_head": current_head,
            "manifest_git_commit": phase2_manifest.get("git_commit"),
            "manifest_generated_at": phase2_manifest.get("generated_at"),
            "manifest_script_hash": phase2_manifest.get("script_hash"),
            "current_script_hash": current_script_hash,
            "manifest_config_hash": phase2_manifest.get("config_hash"),
            "current_profile_config_hash": current_profile_config_hash,
            "local_trade_ohlcv_gap_gate_status": local_trade_gate_status,
            "feature_column_count": len(current_features),
            "forbidden_feature_count": len(forbidden_features),
            "failure_count": len(failures),
            "warning_count": len(warnings),
            "data_mutation_performed": False,
            "reports_refreshed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "live_or_paper_execution_approved": False,
        },
        "checks": checks,
        "warnings": warnings,
    }


def render_console(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "phase2_460_audit_readiness "
        f"status={summary['status']} "
        f"canonical_parquet_count={summary['canonical_parquet_count']}/{summary['expected_count']} "
        f"failure_count={summary['failure_count']} "
        f"warning_count={summary['warning_count']}",
    ]
    for check in report["checks"]:
        if check["status"] == "FAIL":
            lines.append(
                f"FAIL {check['name']}: observed={check['observed']!r} expected={check['expected']!r}"
            )
    for warning in report["warnings"]:
        lines.append(
            f"WARN {warning['name']} {warning['code']}: "
            f"observed={warning['observed']!r} expected={warning['expected']!r}"
        )
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--data-manifest", default=str(DEFAULT_DATA_MANIFEST))
    parser.add_argument("--canonical-root", default=str(DEFAULT_CANONICAL_ROOT))
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT))
    parser.add_argument("--phase2-manifest", default=str(DEFAULT_PHASE2_MANIFEST))
    parser.add_argument("--phase2-validation", default=str(DEFAULT_PHASE2_VALIDATION))
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--build-script", default=str(DEFAULT_BUILD_SCRIPT))
    parser.add_argument("--expected-count", type=int, default=EXPECTED_CANONICAL_COUNT)
    parser.add_argument("--json", action="store_true", help="Print the read-only report JSON to stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    report = evaluate_readiness(
        repo_root=repo_root,
        data_manifest_path=resolve_path(repo_root, args.data_manifest),
        canonical_root=resolve_path(repo_root, args.canonical_root),
        reports_root=resolve_path(repo_root, args.reports_root),
        phase2_manifest_path=resolve_path(repo_root, args.phase2_manifest),
        phase2_validation_path=resolve_path(repo_root, args.phase2_validation),
        profile_config_path=resolve_path(repo_root, args.profile_config),
        build_script_path=resolve_path(repo_root, args.build_script),
        expected_count=args.expected_count,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_console(report))
    return 0 if report["summary"]["status"] == STATUS_GO else 1


if __name__ == "__main__":
    raise SystemExit(main())
