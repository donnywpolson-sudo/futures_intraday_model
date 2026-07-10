import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.phase5_wfa import build_hardened_wfa_splits as builder
from scripts.pipeline_gates import file_sha256


MARKETS = list(builder.EXPECTED_MARKETS)
YEARS = list(builder.EXPECTED_YEARS)


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_profile_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
defaults:
  final_holdout_years: [2025]
profile_defaults:
  tiny:
    train_days: 365
    test_days: 30
    step_days: 30
profiles:
  tier_1_research:
    intent: core_research
    settings_profile: tiny
    markets: ["6E", "CL", "ES", "ZN"]
    years: [2023, 2024]
aliases:
  tier_1: tier_1_research
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_models_config(path: Path, *, resolved_purge_bars: int = 3) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
policy:
  random_splits_allowed: false
  final_holdout_tuning_allowed: false
purge:
  entry_lag_bars: 1
  target_horizon_bars: 2
  trend_horizon_bars: 2
  purge_bars: auto
  resolved_purge_bars: {resolved_purge_bars}
model_selection_reports:
  final_holdout_excluded_from_selection: true
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_matrix(root: Path, market: str, year: int) -> Path:
    path = root / market / f"{year}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    if year == 2023:
        ts = pd.date_range("2023-01-02T00:00:00Z", periods=24, freq="min")
    else:
        ts = pd.DatetimeIndex(
            list(pd.date_range("2024-06-28T20:00:00Z", periods=24, freq="min"))
            + list(pd.date_range("2024-07-01T00:00:00Z", periods=24, freq="min"))
        )
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


def _write_feature_matrices(root: Path) -> list[Path]:
    return [_write_matrix(root, market, year) for market in MARKETS for year in YEARS]


def _write_feature_manifest(path: Path, input_root: Path, outputs: list[Path]) -> Path:
    return _write_json(
        path,
        {
            "status": "PASS",
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "output_root": input_root.as_posix(),
            "feature_count": 114,
            "failure_count": 0,
            "warning_count": 0,
            "failures": [],
            "warnings": [],
            "summary": {"fail_count": 0, "warn_count": 0},
            "output_file_hashes": {output.as_posix(): file_sha256(output) for output in outputs},
            "outputs": [
                {
                    "market": market,
                    "year": year,
                    "status": "PASS",
                    "failure_count": 0,
                    "warning_count": 0,
                    "failures": [],
                    "warnings": [],
                }
                for market in MARKETS
                for year in YEARS
            ],
        },
    )


def _write_feature_hashes(path: Path, input_root: Path, outputs: list[Path]) -> Path:
    records = [
        {
            "path": output.as_posix(),
            "sha256": file_sha256(output),
            "staged_sha256": file_sha256(output),
            "active_matches_staged": True,
            "backup_matches_pre_active": True,
        }
        for output in outputs
    ]
    records.extend(
        {
            "path": f"data/feature_matrices/{name}",
            "sha256": f"{index + 1:064x}"[-64:],
            "staged_sha256": f"{index + 1:064x}"[-64:],
            "active_matches_staged": True,
            "backup_matches_pre_active": True,
        }
        for index, name in enumerate(
            ["feature_cols.json", "target_cols.json", "metadata_cols.json", "excluded_cols.json"]
        )
    )
    return _write_json(
        path,
        {
            "active_root": input_root.as_posix(),
            "failures": [],
            "records": records,
        },
    )


def _write_label_hashes(path: Path) -> Path:
    return _write_json(
        path,
        {
            "active_root": "data/labeled",
            "failures": [],
            "label_semantics_id": builder.EXPECTED_LABEL_SEMANTICS_ID,
            "records": [
                {
                    "market": market,
                    "year": year,
                    "active_path": f"data/labeled/{market}/{year}.parquet",
                    "active_sha256": f"{len(market) + year:064x}"[-64:],
                    "staged_sha256": f"{len(market) + year:064x}"[-64:],
                    "active_matches_staged": True,
                    "backup_matches_pre_active": True,
                }
                for market in MARKETS
                for year in YEARS
            ],
        },
    )


def _write_data_audit(path: Path) -> Path:
    return _write_json(
        path,
        {
            "status": "PASS",
            "summary": {"audit_status_counts": {"usable": 8}},
            "market_years": [
                {
                    "market": market,
                    "year": year,
                    "audit_status": "usable",
                    "usable_for_wfa": True,
                    "reason": "fixture",
                }
                for market in MARKETS
                for year in YEARS
            ],
        },
    )


def _write_hardening_decision(path: Path, *, status: str = "PASS_SPLIT_HARDENING_DESIGN_FEASIBLE_NO_SPLIT_BUILD") -> Path:
    return _write_json(
        path,
        {
            "status": status,
            "scope": {"markets": MARKETS, "years": YEARS, "market_year_count": 8},
            "summary": {
                "failure_count": 0,
                "hardened_split_design_feasible": True,
                "hardened_split_generation_allowed": False,
                "split_plan_generated": False,
            },
        },
    )


def _write_contamination_audit(path: Path) -> Path:
    return _write_json(
        path,
        {
            "status": "PASS_RESEARCH_ONLY_WFA_SPLIT_GUARD",
            "summary": {
                "classification": "same_fold_rolling_retraining_research_only",
                "failure_count": 0,
                "valid_for_independent_holdout_claims": False,
                "valid_for_same_fold_rolling_retraining_research_evidence": True,
            },
        },
    )


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.chdir(tmp_path)
    input_root = Path("data/feature_matrices")
    outputs = _write_feature_matrices(input_root)
    paths = {
        "input_root": input_root,
        "reports_root": Path("reports/wfa/hardened"),
        "profile_config": _write_profile_config(Path("configs/alpha_tiered.yaml")),
        "models_config": _write_models_config(Path("configs/models.yaml")),
        "feature_manifest": _write_feature_manifest(Path("reports/features/baseline_feature_manifest.json"), input_root, outputs),
        "feature_hashes": _write_feature_hashes(Path("reports/features/post_active_feature_hashes.json"), input_root, outputs),
        "label_hashes": _write_label_hashes(Path("reports/labels/post_replacement_hashes.json")),
        "data_audit": _write_data_audit(Path("reports/data_audit/universe.json")),
        "hardening": _write_hardening_decision(Path("reports/wfa/hardening/split_hardening_decision.json")),
        "contamination": _write_contamination_audit(Path("reports/wfa/contamination/wfa_split_contamination_audit.json")),
    }
    return paths


def _build(paths: dict[str, Path]) -> tuple[dict[str, object], dict[str, object]]:
    return builder.build_hardened_split_plan(
        profile="tier_1",
        input_root=paths["input_root"],
        reports_root=paths["reports_root"],
        profile_config=paths["profile_config"],
        models_config=paths["models_config"],
        feature_manifest=paths["feature_manifest"],
        feature_placement_hashes=paths["feature_hashes"],
        label_placement_hashes=paths["label_hashes"],
        data_audit_universe_json=paths["data_audit"],
        split_hardening_decision=paths["hardening"],
        contamination_audit=paths["contamination"],
        markets=MARKETS,
        years=YEARS,
        approve_generation=True,
        approval_token=builder.APPROVAL_TOKEN,
        min_train_rows=10,
        min_validation_rows=10,
        min_test_rows=10,
        minimum_required_bars=3,
    )


def test_builds_hardened_split_candidate_without_modeling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)

    manifest, acceptance = _build(paths)

    assert manifest["status"] == builder.PASS_STATUS
    assert manifest["fold_count"] == 4
    assert manifest["fold_count_by_market"] == {market: 1 for market in MARKETS}
    assert acceptance["status"] == builder.ACCEPTANCE_PASS_STATUS
    assert acceptance["summary"]["modeling_allowed"] is False
    assert (paths["reports_root"] / "split_plan.json").exists()
    assert (paths["reports_root"] / "split_plan.csv").exists()
    assert (paths["reports_root"] / builder.ACCEPTANCE_JSON).exists()
    assert (paths["reports_root"] / builder.ACCEPTANCE_MD).exists()
    fold = manifest["folds"][0]
    assert fold["selection_source"] == "validation_only"
    assert fold["independent_test_claim_allowed"] is True
    assert fold["validation_end"] < fold["validation_embargo_end"] < fold["test_start"]


def test_refuses_without_approval_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)

    with pytest.raises(SystemExit, match="requires --approve-generation"):
        builder.build_hardened_split_plan(
            profile="tier_1",
            input_root=paths["input_root"],
            reports_root=paths["reports_root"],
            profile_config=paths["profile_config"],
            models_config=paths["models_config"],
            feature_manifest=paths["feature_manifest"],
            feature_placement_hashes=paths["feature_hashes"],
            label_placement_hashes=paths["label_hashes"],
            data_audit_universe_json=paths["data_audit"],
            split_hardening_decision=paths["hardening"],
            contamination_audit=paths["contamination"],
            markets=MARKETS,
            years=YEARS,
            approve_generation=False,
            approval_token=None,
            minimum_required_bars=3,
        )


def test_refuses_scope_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)

    with pytest.raises(SystemExit, match="bounded to markets"):
        builder.build_hardened_split_plan(
            profile="tier_1",
            input_root=paths["input_root"],
            reports_root=paths["reports_root"],
            profile_config=paths["profile_config"],
            models_config=paths["models_config"],
            feature_manifest=paths["feature_manifest"],
            feature_placement_hashes=paths["feature_hashes"],
            label_placement_hashes=paths["label_hashes"],
            data_audit_universe_json=paths["data_audit"],
            split_hardening_decision=paths["hardening"],
            contamination_audit=paths["contamination"],
            markets=[*MARKETS, "NQ"],
            years=YEARS,
            approve_generation=True,
            approval_token=builder.APPROVAL_TOKEN,
            minimum_required_bars=3,
        )


def test_refuses_stale_hardening_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    _write_hardening_decision(paths["hardening"], status="FAIL_SPLIT_HARDENING_DECISION_BLOCKED_NO_SPLIT_BUILD")

    with pytest.raises(SystemExit, match="split-hardening decision gate failed"):
        _build(paths)


def test_refuses_feature_hash_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    payload = json.loads(paths["feature_hashes"].read_text(encoding="utf-8"))
    payload["records"][0]["sha256"] = "0" * 64
    _write_json(paths["feature_hashes"], payload)

    with pytest.raises(SystemExit, match="feature hash mismatch"):
        _build(paths)


def test_refuses_existing_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    _write_json(paths["reports_root"] / "split_plan.json", {"existing": True})

    with pytest.raises(SystemExit, match="refusing to overwrite"):
        _build(paths)
