#!/usr/bin/env python3
"""Build guarded hardened Phase 5 train/validation/test split plans."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.phase5_wfa.build_wfa_splits import (
    DEFAULT_MODELS_CONFIG,
    DEFAULT_PROFILE,
    DEFAULT_PROFILE_CONFIG,
    WfaPolicy,
    _config_hash,
    _file_hash_map,
    _file_sha256,
    _git_commit,
    _read_feature_rows,
    _relative_path,
    accepted_phase4_feature_warning_messages,
    filter_profile_plan,
    load_profile_plan,
    load_wfa_policy,
    resolve_input_paths,
)
from scripts.pipeline_gates import resolve_upstream_manifest_gate
from scripts.validation.data_audit_universe_guard import load_data_audit_universe
from scripts.validation.validate_hardened_wfa_split_plan import (
    DEFAULT_MIN_REQUIRED_BARS,
    DEFAULT_MIN_TEST_ROWS,
    DEFAULT_MIN_TRAIN_ROWS,
    DEFAULT_MIN_VALIDATION_ROWS,
    PASS_STATUS as ACCEPTANCE_PASS_STATUS,
    REPORT_JSON as ACCEPTANCE_JSON,
    REPORT_MD as ACCEPTANCE_MD,
    build_acceptance_report,
    write_report as write_acceptance_report,
)


APPROVAL_TOKEN = "BUILD_HARDENED_PHASE5_SPLIT_V2_TIER1_CORE"
PASS_STATUS = "PASS_HARDENED_PHASE5_SPLIT_PLAN_BUILT_NO_MODELING"
FAIL_STATUS = "FAIL_HARDENED_PHASE5_SPLIT_PLAN_BUILT_NO_MODELING"
EXPECTED_MARKETS = ("6E", "CL", "ES", "ZN")
EXPECTED_YEARS = (2023, 2024)
EXPECTED_LABEL_SEMANTICS_ID = (
    "phase3_labels_v2_next_1m_open_30m_primary_60m_confirm_apex_aware"
)

DEFAULT_REPORTS_ROOT = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_hardened_split_candidate"
)
DEFAULT_FEATURE_MANIFEST = Path(
    "reports/features_baseline/"
    "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "baseline_feature_manifest.json"
)
DEFAULT_FEATURE_PLACEMENT_HASHES = Path(
    "reports/features_baseline/"
    "phase4_v2_apex_30m60m_20260709_tier1_core_active_placement/"
    "post_active_feature_hashes.json"
)
DEFAULT_LABEL_PLACEMENT_HASHES = Path(
    "reports/labels/phase3_v2_apex_30m60m_20260709_active_replacement_decision/"
    "post_replacement_hashes.json"
)
DEFAULT_DATA_AUDIT_UNIVERSE = Path(
    "reports/data_audit/wfa_research/tier1_rebuild_v1/preflight/"
    "data_audit_universe_tier1_rebuild_v1.json"
)
DEFAULT_SPLIT_HARDENING_DECISION = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_split_hardening_decision/"
    "split_hardening_decision.json"
)
DEFAULT_CONTAMINATION_AUDIT = Path(
    "reports/wfa/phase5_v2_apex_30m60m_20260709_tier1_core_contamination_audit/"
    "wfa_split_contamination_audit.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_csv_strings(value: str | None) -> list[str] | None:
    if value is None:
        return None
    values = [item.strip() for item in value.split(",") if item.strip()]
    return values or None


def parse_csv_ints(value: str | None) -> list[int] | None:
    values = parse_csv_strings(value)
    if values is None:
        return None
    return [int(item) for item in values]


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"unreadable JSON {path.as_posix()}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"expected JSON object: {path.as_posix()}")
    return payload


def path_matches(raw: object, expected: Path) -> bool:
    try:
        return Path(str(raw)).expanduser().resolve() == expected.expanduser().resolve()
    except (OSError, TypeError, ValueError):
        return False


def map_hash_for_path(hash_map: object, expected: Path) -> str | None:
    if not isinstance(hash_map, Mapping):
        return None
    for raw_path, raw_hash in hash_map.items():
        if path_matches(raw_path, expected):
            return str(raw_hash)
    return None


def expected_pairs(markets: Sequence[str], years: Sequence[int]) -> list[tuple[str, int]]:
    return [(market, int(year)) for market in markets for year in years]


def require_exact_scope(markets: Sequence[str], years: Sequence[int]) -> None:
    if sorted(markets) != sorted(EXPECTED_MARKETS) or sorted(int(year) for year in years) != list(EXPECTED_YEARS):
        raise SystemExit(
            "hardened split generation is bounded to markets=6E,CL,ES,ZN and years=2023,2024"
        )


def require_approval(*, approve_generation: bool, approval_token: str | None) -> None:
    if not approve_generation or approval_token != APPROVAL_TOKEN:
        raise SystemExit(
            "hardened split generation requires --approve-generation "
            f"--approval-token {APPROVAL_TOKEN}"
        )


def require_no_existing_outputs(reports_root: Path) -> None:
    existing = [
        path.as_posix()
        for path in (
            reports_root / "split_plan.json",
            reports_root / "split_plan.csv",
            reports_root / ACCEPTANCE_JSON,
            reports_root / ACCEPTANCE_MD,
        )
        if path.exists()
    ]
    if existing:
        raise SystemExit(f"refusing to overwrite existing hardened split outputs: {existing}")


def validate_hardening_decision(path: Path, markets: Sequence[str], years: Sequence[int]) -> dict[str, Any]:
    decision = read_json(path)
    summary = decision.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    scope = decision.get("scope")
    scope = scope if isinstance(scope, Mapping) else {}
    failures: list[str] = []
    if decision.get("status") != "PASS_SPLIT_HARDENING_DESIGN_FEASIBLE_NO_SPLIT_BUILD":
        failures.append(f"status={decision.get('status')!r}")
    if int(summary.get("failure_count", -1)) != 0:
        failures.append("failure_count must be 0")
    if summary.get("hardened_split_design_feasible") is not True:
        failures.append("hardened_split_design_feasible must be true")
    if summary.get("hardened_split_generation_allowed") is not False:
        failures.append("hardened_split_generation_allowed must be false before this approved build")
    if summary.get("split_plan_generated") is not False:
        failures.append("split_plan_generated must be false")
    if sorted(scope.get("markets", [])) != sorted(markets):
        failures.append(f"scope markets mismatch: {scope.get('markets')}")
    if sorted(int(year) for year in scope.get("years", [])) != sorted(int(year) for year in years):
        failures.append(f"scope years mismatch: {scope.get('years')}")
    if failures:
        raise SystemExit(f"split-hardening decision gate failed: {'; '.join(failures)}")
    return {
        "path": _relative_path(path),
        "sha256": _file_sha256(path),
        "status": decision.get("status"),
        "summary": dict(summary),
    }


def validate_contamination_audit(path: Path) -> dict[str, Any]:
    audit = read_json(path)
    summary = audit.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    failures: list[str] = []
    if audit.get("status") != "PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD":
        failures.append(f"status={audit.get('status')!r}")
    if summary.get("classification") != "same_fold_rolling_retraining_research_only":
        failures.append(f"classification={summary.get('classification')!r}")
    if summary.get("valid_for_independent_holdout_claims") is not False:
        failures.append("current split must remain non-independent")
    if summary.get("valid_for_same_fold_rolling_retraining_research_evidence") is not True:
        failures.append("same-fold rolling research evidence must remain valid")
    if int(summary.get("failure_count", -1)) != 0:
        failures.append("failure_count must be 0")
    if failures:
        raise SystemExit(f"contamination audit gate failed: {'; '.join(failures)}")
    return {
        "path": _relative_path(path),
        "sha256": _file_sha256(path),
        "status": audit.get("status"),
        "summary": dict(summary),
    }


def validate_data_audit_universe(path: Path, markets: Sequence[str], years: Sequence[int]) -> dict[str, Any]:
    universe = load_data_audit_universe(path)
    expected = set(expected_pairs(markets, years))
    observed = set(universe.market_years)
    if observed != expected:
        raise SystemExit(f"data-audit universe scope mismatch: {sorted(observed)}")
    failures = [
        failure
        for market, year in sorted(expected)
        if (failure := universe.require_usable(market, year, context="hardened split generation"))
    ]
    if failures:
        raise SystemExit("; ".join(failures))
    return universe.evidence()


def validate_hash_reports(
    *,
    input_root: Path,
    feature_hash_path: Path,
    label_hash_path: Path,
    markets: Sequence[str],
    years: Sequence[int],
) -> dict[str, Any]:
    feature_hashes = read_json(feature_hash_path)
    label_hashes = read_json(label_hash_path)
    failures: list[str] = []

    if not path_matches(feature_hashes.get("active_root"), input_root):
        failures.append("feature hash active_root mismatch")
    if feature_hashes.get("failures") not in ([], None):
        failures.append("feature hash report contains failures")
    feature_records = feature_hashes.get("records")
    feature_records = feature_records if isinstance(feature_records, list) else []
    feature_records_by_path = {
        Path(str(record.get("path"))).expanduser().resolve(): record
        for record in feature_records
        if isinstance(record, Mapping) and record.get("path") is not None
    }
    for market, year in expected_pairs(markets, years):
        path = input_root / market / f"{year}.parquet"
        record = feature_records_by_path.get(path.expanduser().resolve())
        if not isinstance(record, Mapping):
            failures.append(f"missing feature hash record: {_relative_path(path)}")
            continue
        if record.get("active_matches_staged") is not True:
            failures.append(f"feature active_matches_staged is not true: {_relative_path(path)}")
        expected_hash = str(record.get("sha256") or record.get("active_sha256") or "")
        if not expected_hash:
            expected_hash = map_hash_for_path(feature_hashes.get("active_tree_hashes_after"), path) or ""
        if expected_hash != _file_sha256(path):
            failures.append(f"feature hash mismatch: {_relative_path(path)}")

    if label_hashes.get("active_root") != "data/labeled":
        failures.append("label hash active_root mismatch")
    if label_hashes.get("failures") not in ([], None):
        failures.append("label hash report contains failures")
    if label_hashes.get("label_semantics_id") != EXPECTED_LABEL_SEMANTICS_ID:
        failures.append("label semantics id mismatch")
    label_records = label_hashes.get("records")
    label_records = label_records if isinstance(label_records, list) else []
    observed_label_pairs = {
        (str(record.get("market")), int(record.get("year")))
        for record in label_records
        if isinstance(record, Mapping) and record.get("market") is not None and record.get("year") is not None
    }
    if observed_label_pairs != set(expected_pairs(markets, years)):
        failures.append(f"label hash pairs mismatch: {sorted(observed_label_pairs)}")
    for record in label_records:
        if isinstance(record, Mapping) and record.get("active_matches_staged") is not True:
            failures.append(f"label active_matches_staged is not true: {record.get('active_path')}")

    if failures:
        raise SystemExit("; ".join(failures))
    return {
        "feature_placement_hashes": {
            "path": _relative_path(feature_hash_path),
            "sha256": _file_sha256(feature_hash_path),
            "market_year_records": len(expected_pairs(markets, years)),
            "record_count": len(feature_records),
        },
        "label_placement_hashes": {
            "path": _relative_path(label_hash_path),
            "sha256": _file_sha256(label_hash_path),
            "record_count": len(label_records),
            "label_semantics_id": label_hashes.get("label_semantics_id"),
        },
    }


def iso(timestamp: pd.Timestamp) -> str:
    return timestamp.isoformat()


def build_market_hardened_fold(
    *,
    market: str,
    frame: pd.DataFrame,
    policy: WfaPolicy,
    min_train_rows: int,
    min_validation_rows: int,
    min_test_rows: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    failures: list[str] = []
    frame = frame.sort_values("ts").reset_index(drop=True)
    eligible = frame.loc[frame["wfa_row_eligible"].astype(bool)].copy()
    cutoff = pd.Timestamp("2024-07-01T00:00:00Z")
    train_candidate = eligible.loc[eligible["year"].astype(int) == 2023]
    validation_candidate = eligible.loc[
        (eligible["year"].astype(int) == 2024) & (eligible["ts"] < cutoff)
    ]
    test_candidate = eligible.loc[
        (eligible["year"].astype(int) == 2024) & (eligible["ts"] >= cutoff)
    ]
    bars = int(policy.resolved_purge_bars)
    if len(train_candidate) <= bars:
        failures.append(f"{market}: not enough train rows for {bars}-bar purge")
    if len(validation_candidate) <= bars:
        failures.append(f"{market}: not enough validation rows for {bars}-bar validation embargo")
    if len(test_candidate) <= bars:
        failures.append(f"{market}: not enough test rows for {bars}-bar test embargo")
    if failures:
        return None, failures

    train = train_candidate.iloc[:-bars]
    validation = validation_candidate.iloc[:-bars]
    test = test_candidate.iloc[:-bars]
    if len(train) < min_train_rows:
        failures.append(f"{market}: train rows after purge below {min_train_rows}")
    if len(validation) < min_validation_rows:
        failures.append(f"{market}: validation rows below {min_validation_rows}")
    if len(test) < min_test_rows:
        failures.append(f"{market}: test rows below {min_test_rows}")
    if failures:
        return None, failures

    fold = {
        "market": market,
        "fold_id": f"{market}_hardened_0001",
        "fold_number": 1,
        "year": 2024,
        "split_group": "hardened_research",
        "train_start": iso(train_candidate["ts"].iloc[0]),
        "train_end": iso(train_candidate["ts"].iloc[-1]),
        "purged_train_end": iso(train["ts"].iloc[-1]),
        "validation_start": iso(validation["ts"].iloc[0]),
        "validation_end": iso(validation["ts"].iloc[-1]),
        "validation_embargo_end": iso(validation_candidate["ts"].iloc[-1]),
        "test_start": iso(test["ts"].iloc[0]),
        "test_end": iso(test["ts"].iloc[-1]),
        "test_embargo_end": iso(test_candidate["ts"].iloc[-1]),
        "train_rows_before_purge": int(len(train_candidate)),
        "train_rows_after_purge": int(len(train)),
        "purged_train_rows": int(len(train_candidate) - len(train)),
        "validation_rows_before_embargo": int(len(validation_candidate)),
        "validation_rows": int(len(validation)),
        "validation_embargo_rows": int(len(validation_candidate) - len(validation)),
        "test_rows_before_embargo": int(len(test_candidate)),
        "test_rows": int(len(test)),
        "test_embargo_rows": int(len(test_candidate) - len(test)),
        "purge_bars": int(policy.purge_bars),
        "resolved_purge_bars": int(policy.resolved_purge_bars),
        "embargo_bars": int(policy.embargo_bars),
        "is_final_holdout": False,
        "final_holdout": False,
        "selection_allowed": True,
        "test_selection_allowed": False,
        "hardened_split_type": "fixed_train_validation_test",
        "independent_test_claim_allowed": True,
        "selection_source": "validation_only",
    }
    return fold, []


def build_hardened_split_plan(
    *,
    profile: str,
    input_root: Path,
    reports_root: Path,
    profile_config: Path,
    models_config: Path,
    feature_manifest: Path,
    feature_placement_hashes: Path,
    label_placement_hashes: Path,
    data_audit_universe_json: Path,
    split_hardening_decision: Path,
    contamination_audit: Path,
    markets: Iterable[str],
    years: Iterable[int],
    approve_generation: bool,
    approval_token: str | None,
    min_train_rows: int = DEFAULT_MIN_TRAIN_ROWS,
    min_validation_rows: int = DEFAULT_MIN_VALIDATION_ROWS,
    min_test_rows: int = DEFAULT_MIN_TEST_ROWS,
    minimum_required_bars: int = DEFAULT_MIN_REQUIRED_BARS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected_markets = [str(market) for market in markets]
    selected_years = [int(year) for year in years]
    require_exact_scope(selected_markets, selected_years)
    require_approval(approve_generation=approve_generation, approval_token=approval_token)
    require_no_existing_outputs(reports_root)

    plan = filter_profile_plan(
        load_profile_plan(profile, profile_config),
        markets=selected_markets,
        years=selected_years,
    )
    if plan.requested_profile != "tier_1" or plan.resolved_profile != "tier_1_research":
        raise SystemExit("hardened split generation requires profile=tier_1 resolved to tier_1_research")
    policy = load_wfa_policy(models_config)
    if policy.resolved_purge_bars < minimum_required_bars or policy.embargo_bars < minimum_required_bars:
        raise SystemExit(f"models purge/embargo must be at least {minimum_required_bars} bars")

    hardening_evidence = validate_hardening_decision(
        split_hardening_decision,
        selected_markets,
        selected_years,
    )
    contamination_evidence = validate_contamination_audit(contamination_audit)
    data_audit_evidence = validate_data_audit_universe(
        data_audit_universe_json,
        selected_markets,
        selected_years,
    )
    hash_evidence = validate_hash_reports(
        input_root=input_root,
        feature_hash_path=feature_placement_hashes,
        label_hash_path=label_placement_hashes,
        markets=selected_markets,
        years=selected_years,
    )
    inputs = resolve_input_paths(plan, input_root)
    feature_manifest_gate = resolve_upstream_manifest_gate(
        manifest_arg=feature_manifest,
        default_manifest_path=feature_manifest,
        search_name="baseline_feature_manifest.json",
        expected_stage=None,
        expected_profile=plan.feature_manifest_profile or plan.requested_profile,
        expected_resolved_profile=plan.feature_manifest_resolved_profile or plan.resolved_profile,
        expected_output_root=input_root,
        expected_market_years=((market, year) for market, year, _ in inputs),
        gate_name="feature_manifest_gate",
        allowed_statuses=("PASS",),
        accepted_warning_messages=accepted_phase4_feature_warning_messages(plan.markets),
    )

    frames_by_market: dict[str, list[pd.DataFrame]] = {market: [] for market in selected_markets}
    failures: list[str] = []
    for market, year, path in inputs:
        frame, failure = _read_feature_rows(path, market, year)
        if failure is not None:
            failures.append(failure)
            continue
        assert frame is not None
        frames_by_market[market].append(frame)

    folds: list[dict[str, Any]] = []
    for market in selected_markets:
        frames = frames_by_market.get(market) or []
        if not frames:
            failures.append(f"{market}: no readable feature matrices")
            continue
        fold, fold_failures = build_market_hardened_fold(
            market=market,
            frame=pd.concat(frames, ignore_index=True),
            policy=policy,
            min_train_rows=min_train_rows,
            min_validation_rows=min_validation_rows,
            min_test_rows=min_test_rows,
        )
        failures.extend(fold_failures)
        if fold is not None:
            folds.append(fold)

    reports_root.mkdir(parents=True, exist_ok=True)
    split_rows = pd.DataFrame(folds)
    split_rows.to_csv(reports_root / "split_plan.csv", index=False)
    hashed_inputs = [path for _, _, path in inputs]
    manifest = {
        "status": PASS_STATUS if not failures else FAIL_STATUS,
        "generated_at": utc_now(),
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "config_hash": _config_hash(
            [
                profile_config,
                models_config,
                feature_manifest,
                feature_placement_hashes,
                label_placement_hashes,
                data_audit_universe_json,
                split_hardening_decision,
                contamination_audit,
            ]
        ),
        "input_file_hashes": _file_hash_map(hashed_inputs),
        "profile": plan.requested_profile,
        "resolved_profile": plan.resolved_profile,
        "input_root": _relative_path(input_root),
        "output_root": _relative_path(reports_root),
        "reports_root": _relative_path(reports_root),
        "markets": selected_markets,
        "years": selected_years,
        "settings_profile": plan.settings_profile,
        "window_policy": {
            "train": "eligible_2023_rows_minus_pre_validation_purge",
            "validation": "eligible_h1_2024_rows_minus_pre_test_embargo",
            "test": "eligible_h2_2024_rows_minus_terminal_test_embargo",
            "split_type": "fixed_train_validation_test",
        },
        "purge_policy": {
            "purge_bars": policy.purge_bars,
            "resolved_purge_bars": policy.resolved_purge_bars,
            "embargo_bars": policy.embargo_bars,
        },
        "final_holdout_policy": {
            "final_holdout_years": plan.final_holdout_years,
            "final_holdout_tuning_allowed": policy.final_holdout_tuning_allowed,
            "final_holdout_excluded_from_selection": policy.final_holdout_excluded_from_selection,
            "final_holdout_rows_allowed": False,
        },
        "hardening_decision_gate": hardening_evidence,
        "contamination_audit_gate": contamination_evidence,
        "data_audit_universe": data_audit_evidence,
        "feature_manifest_gate": feature_manifest_gate.evidence,
        "active_hash_evidence": hash_evidence,
        "fold_count": len(folds),
        "fold_count_by_market": split_rows.groupby("market").size().to_dict() if folds else {},
        "warning_count": 0,
        "failure_count": len(failures),
        "failures": failures,
        "modeling_allowed": False,
        "prediction_materialization_allowed": False,
        "phase8_refresh_allowed": False,
        "folds": folds,
    }
    split_plan_path = reports_root / "split_plan.json"
    split_plan_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    acceptance = build_acceptance_report(
        split_plan=manifest,
        split_plan_path=split_plan_path,
        reports_root=reports_root,
        markets=selected_markets,
        years=selected_years,
        min_train_rows=min_train_rows,
        min_validation_rows=min_validation_rows,
        min_test_rows=min_test_rows,
        minimum_required_bars=minimum_required_bars,
    )
    write_acceptance_report(acceptance, reports_root)
    return manifest, acceptance


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--input-root", default="data/feature_matrices")
    parser.add_argument("--reports-root", default=DEFAULT_REPORTS_ROOT.as_posix())
    parser.add_argument("--profile-config", default=DEFAULT_PROFILE_CONFIG.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--feature-manifest", default=DEFAULT_FEATURE_MANIFEST.as_posix())
    parser.add_argument("--feature-placement-hashes", default=DEFAULT_FEATURE_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--label-placement-hashes", default=DEFAULT_LABEL_PLACEMENT_HASHES.as_posix())
    parser.add_argument("--data-audit-universe-json", default=DEFAULT_DATA_AUDIT_UNIVERSE.as_posix())
    parser.add_argument("--split-hardening-decision", default=DEFAULT_SPLIT_HARDENING_DECISION.as_posix())
    parser.add_argument("--contamination-audit", default=DEFAULT_CONTAMINATION_AUDIT.as_posix())
    parser.add_argument("--markets", default=",".join(EXPECTED_MARKETS))
    parser.add_argument("--years", default=",".join(str(year) for year in EXPECTED_YEARS))
    parser.add_argument("--approve-generation", action="store_true")
    parser.add_argument("--approval-token", default=None)
    parser.add_argument("--min-train-rows", type=int, default=DEFAULT_MIN_TRAIN_ROWS)
    parser.add_argument("--min-validation-rows", type=int, default=DEFAULT_MIN_VALIDATION_ROWS)
    parser.add_argument("--min-test-rows", type=int, default=DEFAULT_MIN_TEST_ROWS)
    parser.add_argument("--minimum-required-bars", type=int, default=DEFAULT_MIN_REQUIRED_BARS)
    args = parser.parse_args(argv)

    manifest, acceptance = build_hardened_split_plan(
        profile=args.profile,
        input_root=Path(args.input_root),
        reports_root=Path(args.reports_root),
        profile_config=Path(args.profile_config),
        models_config=Path(args.models_config),
        feature_manifest=Path(args.feature_manifest),
        feature_placement_hashes=Path(args.feature_placement_hashes),
        label_placement_hashes=Path(args.label_placement_hashes),
        data_audit_universe_json=Path(args.data_audit_universe_json),
        split_hardening_decision=Path(args.split_hardening_decision),
        contamination_audit=Path(args.contamination_audit),
        markets=parse_csv_strings(args.markets) or list(EXPECTED_MARKETS),
        years=parse_csv_ints(args.years) or list(EXPECTED_YEARS),
        approve_generation=args.approve_generation,
        approval_token=args.approval_token,
        min_train_rows=args.min_train_rows,
        min_validation_rows=args.min_validation_rows,
        min_test_rows=args.min_test_rows,
        minimum_required_bars=args.minimum_required_bars,
    )
    success = (
        manifest["failure_count"] == 0
        and acceptance["status"] == ACCEPTANCE_PASS_STATUS
    )
    print(
        f"phase5_hardened_split_builder status={manifest['status']} "
        f"folds={manifest['fold_count']} failures={manifest['failure_count']} "
        f"acceptance={acceptance['status']} reports_root={manifest['reports_root']}"
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
