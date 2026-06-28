from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pipeline_gates import file_sha256
from scripts.phase5_wfa.build_wfa_splits import build_arg_parser, build_split_plan, main


def _write_profile_config(path: Path, *, profile: str = "research") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
defaults:
  final_holdout_years: [2025]
profile_defaults:
  tiny:
    train_days: 2
    test_days: 1
    step_days: 1
profiles:
  research:
    intent: test_research
    settings_profile: tiny
    markets: ["ES"]
    years: [2024]
  holdout:
    intent: test_final_holdout
    settings_profile: tiny
    markets: ["ES"]
    years: [2025]
    forbid_research_use: true
  restricted:
    intent: smoke_test
    settings_profile: tiny
    markets: ["ES"]
    years: [2024]
    forbid_research_use: true
  mixed:
    intent: test_mixed
    settings_profile: tiny
    markets: ["ES"]
    years: [2024, 2025]
  mixed_audit:
    intent: test_research
    settings_profile: tiny
    markets: ["ES", "CL"]
    years: [2024]
aliases:
  selected: {profile}
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_models_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
policy:
  random_splits_allowed: false
  final_holdout_tuning_allowed: false
purge:
  entry_lag_bars: 1
  target_horizon_bars: 2
  purge_bars: auto
  resolved_purge_bars: 3
model_selection_reports:
  final_holdout_excluded_from_selection: true
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_matrix(root: Path, *, year: int, start: str, market: str = "ES") -> Path:
    path = root / market / f"{year}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 7 * 24 * 60
    ts = pd.date_range(start, periods=rows, freq="min", tz="UTC")
    pd.DataFrame(
        {
            "ts": ts,
            "market": market,
            "year": year,
            "training_row_valid": True,
            "target_valid": True,
            "feature_input_valid": True,
        }
    ).to_parquet(path, index=False)
    return path


def _write_feature_manifest(
    path: Path,
    *,
    profile: str,
    resolved_profile: str,
    output_root: Path,
    output_path: Path,
    status: str = "PASS",
    warning_count: int = 0,
    warnings: list[str] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    output_warnings = list(warnings or [])
    payload = {
        "status": status,
        "profile": profile,
        "resolved_profile": resolved_profile,
        "output_root": output_root.as_posix(),
        "warning_count": warning_count,
        "failure_count": 0,
        "failures": [],
        "warnings": [],
        "summary": {"fail_count": 0, "warn_count": warning_count},
        "output_file_hashes": {output_path.as_posix(): file_sha256(output_path)},
        "outputs": [
            {
                "market": "ES",
                "year": 2024,
                "status": status,
                "warning_count": warning_count,
                "failure_count": 0,
                "failures": [],
                "warnings": output_warnings,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _feature_root(tmp_path: Path) -> Path:
    return tmp_path / "data" / "feature_matrices" / "baseline"


def _write_data_audit_universe(
    path: Path,
    *,
    audit_status: str,
    market: str = "ES",
    year: int = 2024,
    final_decision: str | None = None,
    usable_for_wfa: bool | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, object] = {
        "market": market,
        "year": year,
        "audit_status": audit_status,
        "reason": "fixture",
    }
    if final_decision is not None:
        row["final_decision"] = final_decision
    if usable_for_wfa is not None:
        row["usable_for_wfa"] = usable_for_wfa
    path.write_text(
        json.dumps(
            {
                "status": "PASS",
                "summary": {"audit_status_counts": {audit_status: 1}},
                "market_years": [row],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_mixed_data_audit_universe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "PASS",
                "summary": {"audit_status_counts": {"diagnostic_only": 1, "usable": 1}},
                "market_years": [
                    {
                        "market": "ES",
                        "year": 2024,
                        "audit_status": "usable",
                        "reason": "fixture",
                    },
                    {
                        "market": "CL",
                        "year": 2024,
                        "audit_status": "diagnostic_only",
                        "reason": "fixture diagnostic",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_input_root_has_no_implicit_default() -> None:
    args = build_arg_parser().parse_args([])

    assert args.input_root is None


def test_cli_missing_input_root_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["build_wfa_splits"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2
    assert "--input-root is required; pass an explicit feature root" in capsys.readouterr().err


def test_cli_accepts_explicit_feature_roots(tmp_path: Path) -> None:
    rebuilt_root = Path("data/feature_matrices/baseline_tier1_rebuild_v1")
    report_root = tmp_path / "reports" / "wfa" / "feature_matrix_fixture"

    rebuilt_args = build_arg_parser().parse_args(["--input-root", rebuilt_root.as_posix()])
    report_args = build_arg_parser().parse_args(["--input-root", report_root.as_posix()])

    assert Path(rebuilt_args.input_root).as_posix() == rebuilt_root.as_posix()
    assert Path(report_args.input_root).as_posix() == report_root.as_posix()


def test_build_split_plan_rejects_warn_feature_manifest(tmp_path: Path) -> None:
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    feature_root = _feature_root(tmp_path)
    matrix = _write_matrix(feature_root, year=2024, start="2024-01-01T00:00:00Z")
    manifest = _write_feature_manifest(
        tmp_path / "reports" / "features" / "baseline_feature_manifest.json",
        profile="research",
        resolved_profile="research",
        output_root=feature_root,
        output_path=matrix,
        status="WARN",
        warning_count=1,
    )

    with pytest.raises(SystemExit) as exc:
        build_split_plan(
            profile="research",
            input_root=feature_root,
            reports_root=tmp_path / "reports" / "wfa",
            profile_config=profile_config,
            models_config=models_config,
            feature_manifest=manifest,
        )

    assert "feature_manifest_gate failed" in str(exc.value)


def test_build_split_plan_accepts_zero_failure_feature_manifest_with_accepted_warning(
    tmp_path: Path,
) -> None:
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    feature_root = _feature_root(tmp_path)
    matrix = _write_matrix(feature_root, year=2024, start="2024-01-01T00:00:00Z")
    warning = "features fully unavailable: feature_rel_ret_vs_ES_15,feature_corr_vs_ES_60"
    manifest = _write_feature_manifest(
        tmp_path / "reports" / "features" / "baseline_feature_manifest.json",
        profile="research",
        resolved_profile="research",
        output_root=feature_root,
        output_path=matrix,
        status="WARN",
        warning_count=1,
        warnings=[warning],
    )

    result = build_split_plan(
        profile="research",
        input_root=feature_root,
        reports_root=tmp_path / "reports" / "wfa",
        profile_config=profile_config,
        models_config=models_config,
        feature_manifest=manifest,
    )

    assert result["failure_count"] == 0
    assert result["feature_manifest_gate"]["status"] == "PASS"
    assert result["feature_manifest_gate"]["upstream_status"] == "WARN"
    assert result["feature_manifest_gate"]["accepted_warnings"] == [warning]


def test_build_split_plan_accepts_passed_feature_manifest(tmp_path: Path) -> None:
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    feature_root = _feature_root(tmp_path)
    matrix = _write_matrix(feature_root, year=2024, start="2024-01-01T00:00:00Z")
    manifest_path = _write_feature_manifest(
        tmp_path / "reports" / "features" / "baseline_feature_manifest.json",
        profile="research",
        resolved_profile="research",
        output_root=feature_root,
        output_path=matrix,
    )

    manifest = build_split_plan(
        profile="research",
        input_root=feature_root,
        reports_root=tmp_path / "reports" / "wfa",
        profile_config=profile_config,
        models_config=models_config,
        feature_manifest=manifest_path,
    )

    assert manifest["feature_manifest_gate"]["status"] == "PASS"
    assert manifest["failure_count"] == 0


def test_build_split_plan_auto_uses_phase4_default_features_baseline_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    profile_config = _write_profile_config(Path("configs") / "alpha_tiered.yaml")
    models_config = _write_models_config(Path("configs") / "models.yaml")
    feature_root = Path("data") / "feature_matrices" / "baseline"
    matrix = _write_matrix(feature_root, year=2024, start="2024-01-01T00:00:00Z")
    _write_feature_manifest(
        Path("reports") / "features_baseline" / "baseline_feature_manifest.json",
        profile="research",
        resolved_profile="research",
        output_root=feature_root,
        output_path=matrix,
    )

    manifest = build_split_plan(
        profile="research",
        input_root=feature_root,
        reports_root=Path("reports") / "wfa",
        profile_config=profile_config,
        models_config=models_config,
        feature_manifest="auto",
    )

    assert manifest["feature_manifest_gate"]["status"] == "PASS"
    assert (
        manifest["feature_manifest_gate"]["manifest_path"]
        == "reports/features_baseline/baseline_feature_manifest.json"
    )


def test_build_split_plan_enforces_purge_and_writes_manifest(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    _write_matrix(input_root, year=2024, start="2024-01-01T00:00:00Z")

    manifest = build_split_plan(
        profile="selected",
        input_root=input_root,
        reports_root=reports_root,
        profile_config=profile_config,
        models_config=models_config,
    )

    assert manifest["failure_count"] == 0
    assert manifest["input_root"] == input_root.as_posix()
    assert manifest["output_root"] == reports_root.as_posix()
    assert manifest["fold_count"] > 0
    assert (reports_root / "split_plan.csv").exists()
    assert (reports_root / "split_plan.json").exists()

    first = manifest["folds"][0]
    assert first["market"] == "ES"
    assert first["split_group"] == "research"
    assert first["train_rows_before_purge"] > first["train_rows_after_purge"] > 0
    assert first["purged_train_rows"] == 3
    assert first["test_rows"] > 0
    assert first["resolved_purge_bars"] == 3
    assert first["embargo_bars"] == 3
    assert pd.Timestamp(first["purged_train_end"]) < pd.Timestamp(first["test_start"])
    assert first["selection_allowed"] is True

    saved = json.loads((reports_root / "split_plan.json").read_text(encoding="utf-8"))
    assert saved["fold_count_by_market"] == {"ES": manifest["fold_count"]}
    assert saved["final_holdout_policy"]["final_holdout_excluded_from_selection"] is True
    assert saved["data_audit_universe"] is None


def test_build_split_plan_records_data_audit_universe_evidence(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    data_audit = _write_data_audit_universe(
        tmp_path / "reports" / "pipeline_audit" / "universe.json",
        audit_status="usable",
    )
    _write_matrix(input_root, year=2024, start="2024-01-01T00:00:00Z")

    manifest = build_split_plan(
        profile="selected",
        input_root=input_root,
        reports_root=reports_root,
        profile_config=profile_config,
        models_config=models_config,
        data_audit_universe_json=data_audit,
    )

    assert manifest["failure_count"] == 0
    assert manifest["data_audit_universe"]["status_counts"] == {"usable": 1}
    assert manifest["data_audit_universe"]["file_hash"]


def test_build_split_plan_accepts_wfa_usable_caveat_data_audit_universe(
    tmp_path: Path,
) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    data_audit = _write_data_audit_universe(
        tmp_path / "reports" / "pipeline_audit" / "universe.json",
        audit_status="usable",
        final_decision="acceptable_with_caveat_ohlcv_empty_minutes_assumed",
        usable_for_wfa=True,
    )
    _write_matrix(input_root, year=2024, start="2024-01-01T00:00:00Z")

    manifest = build_split_plan(
        profile="selected",
        input_root=input_root,
        reports_root=reports_root,
        profile_config=profile_config,
        models_config=models_config,
        data_audit_universe_json=data_audit,
    )

    assert manifest["failure_count"] == 0
    assert manifest["fold_count"] > 0
    assert manifest["skipped_input_count"] == 0


@pytest.mark.parametrize("profile", ["tier_1", "tier_1_research"])
def test_tier1_build_split_plan_requires_data_audit_universe_json(
    tmp_path: Path,
    profile: str,
) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")

    with pytest.raises(SystemExit, match="Tier 1 WFA split-plan generation requires"):
        build_split_plan(
            profile=profile,
            input_root=input_root,
            reports_root=reports_root,
            profile_config=Path("configs/alpha_tiered.yaml"),
            models_config=models_config,
        )


@pytest.mark.parametrize("audit_status", ["quarantined", "diagnostic_only"])
def test_build_split_plan_blocks_non_usable_data_audit_market_year(
    tmp_path: Path,
    audit_status: str,
) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    data_audit = _write_data_audit_universe(
        tmp_path / "reports" / "pipeline_audit" / "universe.json",
        audit_status=audit_status,
    )
    _write_matrix(input_root, year=2024, start="2024-01-01T00:00:00Z")

    manifest = build_split_plan(
        profile="selected",
        input_root=input_root,
        reports_root=reports_root,
        profile_config=profile_config,
        models_config=models_config,
        data_audit_universe_json=data_audit,
    )

    assert manifest["failure_count"] > 0
    assert "data-audit universe blocked all market-years" in " ".join(manifest["failures"])
    assert manifest["fold_count"] == 0
    assert f"audit_status={audit_status!r}" in manifest["skipped_inputs"][0]["detail"]


def test_build_split_plan_guard_skips_non_usable_market_without_failing_when_usable_market_has_folds(
    tmp_path: Path,
) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(
        tmp_path / "configs" / "alpha_tiered.yaml",
        profile="mixed_audit",
    )
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    data_audit = _write_mixed_data_audit_universe(
        tmp_path / "reports" / "pipeline_audit" / "universe.json",
    )
    _write_matrix(input_root, year=2024, start="2024-01-01T00:00:00Z", market="ES")
    _write_matrix(input_root, year=2024, start="2024-01-01T00:00:00Z", market="CL")

    manifest = build_split_plan(
        profile="selected",
        input_root=input_root,
        reports_root=reports_root,
        profile_config=profile_config,
        models_config=models_config,
        data_audit_universe_json=data_audit,
    )

    assert manifest["failure_count"] == 0
    assert manifest["fold_count"] > 0
    assert manifest["fold_count_by_market"] == {"ES": manifest["fold_count"]}
    assert manifest["skipped_input_count"] == 1
    assert manifest["skipped_inputs"][0]["market"] == "CL"
    assert manifest["skipped_inputs"][0]["reason"] == "data_audit_universe_not_usable"
    assert "audit_status='diagnostic_only'" in manifest["skipped_inputs"][0]["detail"]


def test_final_holdout_profile_blocks_without_explicit_allow(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(
        tmp_path / "configs" / "alpha_tiered.yaml",
        profile="holdout",
    )
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    _write_matrix(input_root, year=2025, start="2025-01-01T00:00:00Z")

    with pytest.raises(SystemExit, match="requires --allow-final-holdout"):
        build_split_plan(
            profile="selected",
            input_root=input_root,
            reports_root=reports_root,
            profile_config=profile_config,
            models_config=models_config,
        )

    assert not (reports_root / "split_plan.json").exists()
    assert not (reports_root / "split_plan.csv").exists()


def test_final_holdout_profile_is_tagged_and_excluded_from_selection_with_allow(
    tmp_path: Path,
) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(
        tmp_path / "configs" / "alpha_tiered.yaml",
        profile="holdout",
    )
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    _write_matrix(input_root, year=2025, start="2025-01-01T00:00:00Z")

    manifest = build_split_plan(
        profile="selected",
        input_root=input_root,
        reports_root=reports_root,
        profile_config=profile_config,
        models_config=models_config,
        allow_final_holdout=True,
    )

    assert manifest["failure_count"] == 0
    fold = manifest["folds"][0]
    assert fold["split_group"] == "final_holdout"
    assert fold["is_final_holdout"] is True
    assert fold["selection_allowed"] is False
    assert manifest["final_holdout_policy"]["final_holdout_tuning_allowed"] is False


def test_restricted_non_holdout_profile_is_not_tagged_as_forward(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(
        tmp_path / "configs" / "alpha_tiered.yaml",
        profile="restricted",
    )
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    _write_matrix(input_root, year=2024, start="2024-01-01T00:00:00Z")

    manifest = build_split_plan(
        profile="selected",
        input_root=input_root,
        reports_root=reports_root,
        profile_config=profile_config,
        models_config=models_config,
    )

    assert manifest["failure_count"] == 0
    fold = manifest["folds"][0]
    assert fold["split_group"] == "restricted"
    assert fold["selection_allowed"] is False


def test_mixed_research_and_final_holdout_years_fail(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(
        tmp_path / "configs" / "alpha_tiered.yaml",
        profile="mixed",
    )
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    _write_matrix(input_root, year=2024, start="2024-01-01T00:00:00Z")
    _write_matrix(input_root, year=2025, start="2025-01-01T00:00:00Z")

    manifest = build_split_plan(
        profile="selected",
        input_root=input_root,
        reports_root=reports_root,
        profile_config=profile_config,
        models_config=models_config,
    )

    assert manifest["failure_count"] == 1
    assert "mixes research and final-holdout years" in manifest["failures"][0]


def test_random_split_policy_is_rejected(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    text = models_config.read_text(encoding="utf-8")
    models_config.write_text(text.replace("random_splits_allowed: false", "random_splits_allowed: true"), encoding="utf-8")

    with pytest.raises(SystemExit, match="random splits"):
        build_split_plan(
            profile="selected",
            input_root=input_root,
            reports_root=reports_root,
            profile_config=profile_config,
            models_config=models_config,
        )


def test_product_unavailable_years_are_skipped_not_failed(tmp_path: Path) -> None:
    input_root = _feature_root(tmp_path)
    reports_root = tmp_path / "reports" / "wfa"
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    profile_config.parent.mkdir(parents=True, exist_ok=True)
    profile_config.write_text(
        """
defaults:
  final_holdout_years: [2025]
profile_defaults:
  tiny:
    train_days: 2
    test_days: 1
    step_days: 1
profiles:
  research:
    intent: test_research
    settings_profile: tiny
    markets: ["RTY"]
    years: [2010, 2017]
aliases:
  selected: research
""".strip(),
        encoding="utf-8",
    )
    models_config = _write_models_config(tmp_path / "configs" / "models.yaml")
    path = input_root / "RTY" / "2017.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 7 * 24 * 60
    ts = pd.date_range("2017-01-01T00:00:00Z", periods=rows, freq="min", tz="UTC")
    pd.DataFrame(
        {
            "ts": ts,
            "market": "RTY",
            "year": 2017,
            "training_row_valid": True,
            "target_valid": True,
            "feature_input_valid": True,
        }
    ).to_parquet(path, index=False)

    manifest = build_split_plan(
        profile="selected",
        input_root=input_root,
        reports_root=reports_root,
        profile_config=profile_config,
        models_config=models_config,
    )

    assert manifest["failure_count"] == 0
    assert manifest["skipped_input_count"] == 1
    assert manifest["skipped_inputs"][0]["reason"] == "product_unavailable_before_2017"
