from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.artifact_freeze.freeze_research_artifacts import (
    build_arg_parser,
    freeze_research_artifacts,
    main,
)


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_freeze_inputs(
    tmp_path: Path,
    *,
    missing_tier3_count: int = 0,
    phase8_overrides: dict[str, object] | None = None,
    anti_overfit_overrides: dict[str, object] | None = None,
) -> dict[str, Path]:
    feature_root = tmp_path / "data" / "feature_matrices" / "baseline"
    for name, payload in {
        "feature_cols.json": ["feature_a"],
        "target_cols.json": ["target_ret_15m"],
        "metadata_cols.json": ["ts", "market"],
        "excluded_cols.json": ["target_valid"],
    }.items():
        _write_json(feature_root / name, payload)
    phase4_audit = _write_json(
        tmp_path / "reports" / "phase4" / "feature_coverage_audit.json",
        {"missing_tier3_count": missing_tier3_count},
    )
    feature_manifest = _write_json(
        tmp_path / "reports" / "phase4" / "baseline_feature_manifest.json",
        {"registry": {"feature_cols": ["feature_a"]}},
    )
    split_plan = _write_json(
        tmp_path / "reports" / "wfa" / "split_plan.json",
        {
            "folds": [
                {
                    "market": "ES",
                    "fold_id": "ES_research_0001",
                    "split_group": "research",
                    "selection_allowed": True,
                }
            ]
        },
    )
    predictions_manifest = _write_json(
        tmp_path / "reports" / "wfa" / "baseline_predictions_manifest.json",
        {
            "failure_count": 0,
            "run": "baseline",
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "stale_output_path_exists": False,
            "artifact_evidence_ready": True,
        },
    )
    phase8_payload: dict[str, object] = {
        "run": "baseline",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "promoted": True,
        "research_alpha_ready": True,
        "model_promotion_allowed": True,
        "blockers": [],
        "failure_count": 0,
        "final_holdout_touched": False,
        "trading_semantics_changed": False,
    }
    if phase8_overrides:
        phase8_payload.update(phase8_overrides)
    phase8_decision = _write_json(
        tmp_path / "reports" / "phase8" / "alpha_promotion_decision.json",
        phase8_payload,
    )
    anti_overfit_payload: dict[str, object] = {
        "profile": "tier_1",
        "robustness_status": "PASS",
        "failures": [],
    }
    if anti_overfit_overrides:
        anti_overfit_payload.update(anti_overfit_overrides)
    anti_overfit = _write_json(
        tmp_path / "reports" / "experiments" / "anti_overfit_audit.json",
        anti_overfit_payload,
    )
    models = _write_json(tmp_path / "configs" / "models.yaml", {"policy": {}})
    costs = _write_json(tmp_path / "configs" / "costs.yaml", {"markets": {}})
    return {
        "feature_root": feature_root,
        "phase4_audit": phase4_audit,
        "feature_manifest": feature_manifest,
        "split_plan": split_plan,
        "predictions_manifest": predictions_manifest,
        "phase8_decision": phase8_decision,
        "anti_overfit": anti_overfit,
        "models": models,
        "costs": costs,
    }


def test_cli_feature_root_has_no_implicit_default() -> None:
    args = build_arg_parser().parse_args(["--freeze-id", "fixture-freeze"])

    assert args.feature_root is None


def test_cli_missing_feature_root_fails_clearly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    freeze_root = tmp_path / "artifacts" / "frozen"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freeze_research_artifacts.py",
            "--freeze-id",
            "fixture-freeze",
            "--freeze-root",
            freeze_root.as_posix(),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 2
    assert "--feature-root is required; pass an explicit feature root" in capsys.readouterr().err
    assert not freeze_root.exists()


def test_cli_accepts_explicit_feature_roots() -> None:
    rebuilt_root = Path("data") / "feature_matrices"
    report_root = Path("reports") / "artifact_freeze" / "features"

    rebuilt_args = build_arg_parser().parse_args(
        ["--freeze-id", "fixture-freeze", "--feature-root", rebuilt_root.as_posix()]
    )
    report_args = build_arg_parser().parse_args(
        ["--freeze-id", "fixture-freeze", "--feature-root", report_root.as_posix()]
    )

    assert Path(rebuilt_args.feature_root).as_posix() == rebuilt_root.as_posix()
    assert Path(report_args.feature_root).as_posix() == report_root.as_posix()


def test_freeze_research_artifacts_writes_manifest_after_guards_pass(tmp_path: Path) -> None:
    paths = _write_freeze_inputs(tmp_path)

    manifest = freeze_research_artifacts(
        freeze_id="fixture-freeze",
        freeze_root=tmp_path / "artifacts" / "frozen",
        feature_root=paths["feature_root"],
        phase4_audit_path=paths["phase4_audit"],
        split_plan_path=paths["split_plan"],
        predictions_manifest_path=paths["predictions_manifest"],
        phase8_decision_path=paths["phase8_decision"],
        anti_overfit_audit_path=paths["anti_overfit"],
        models_config=paths["models"],
        costs_config=paths["costs"],
        feature_manifest_path=paths["feature_manifest"],
    )

    assert manifest["frozen"] is True
    assert manifest["failure_count"] == 0
    assert manifest["final_holdout_touched"] is False
    assert manifest["used_final_holdout_for_tuning"] is False
    assert manifest["phase8_promoted"] is True
    assert manifest["phase8_model_promotion_allowed"] is True
    assert manifest["phase8_blockers"] == []
    assert manifest["anti_overfit_status"] == "PASS"
    frozen_manifest = tmp_path / "artifacts" / "frozen" / "fixture-freeze" / "manifest.json"
    assert frozen_manifest.exists()


def test_freeze_refuses_incomplete_tier3_features(tmp_path: Path) -> None:
    paths = _write_freeze_inputs(tmp_path, missing_tier3_count=1)

    manifest = freeze_research_artifacts(
        freeze_id="bad-freeze",
        freeze_root=tmp_path / "artifacts" / "frozen",
        feature_root=paths["feature_root"],
        phase4_audit_path=paths["phase4_audit"],
        split_plan_path=paths["split_plan"],
        predictions_manifest_path=paths["predictions_manifest"],
        phase8_decision_path=paths["phase8_decision"],
        anti_overfit_audit_path=paths["anti_overfit"],
        models_config=paths["models"],
        costs_config=paths["costs"],
        feature_manifest_path=paths["feature_manifest"],
    )

    assert manifest["frozen"] is False
    assert manifest["failure_count"] > 0
    assert "Tier-3 Phase 4 incomplete" in " ".join(manifest["failures"])


@pytest.mark.parametrize(
    ("phase8_overrides", "expected"),
    [
        ({"promoted": False}, "Phase 8 decision promoted is not true"),
        ({"model_promotion_allowed": False}, "model_promotion_allowed is not true"),
        ({"blockers": ["net negative"]}, "Phase 8 decision blockers are not empty"),
        ({"profile": "tier_2"}, "Phase 8 decision profile mismatch"),
    ],
)
def test_freeze_rejects_unpromoted_blocked_or_profile_mismatched_phase8(
    tmp_path: Path,
    phase8_overrides: dict[str, object],
    expected: str,
) -> None:
    paths = _write_freeze_inputs(tmp_path, phase8_overrides=phase8_overrides)

    manifest = freeze_research_artifacts(
        freeze_id="bad-phase8",
        freeze_root=tmp_path / "artifacts" / "frozen",
        feature_root=paths["feature_root"],
        phase4_audit_path=paths["phase4_audit"],
        split_plan_path=paths["split_plan"],
        predictions_manifest_path=paths["predictions_manifest"],
        phase8_decision_path=paths["phase8_decision"],
        anti_overfit_audit_path=paths["anti_overfit"],
        models_config=paths["models"],
        costs_config=paths["costs"],
        feature_manifest_path=paths["feature_manifest"],
    )

    assert manifest["frozen"] is False
    assert expected in " ".join(manifest["failures"])


def test_freeze_rejects_failed_anti_overfit_audit(tmp_path: Path) -> None:
    paths = _write_freeze_inputs(
        tmp_path,
        anti_overfit_overrides={"robustness_status": "FAIL", "failures": ["sparse"]},
    )

    manifest = freeze_research_artifacts(
        freeze_id="bad-anti-overfit",
        freeze_root=tmp_path / "artifacts" / "frozen",
        feature_root=paths["feature_root"],
        phase4_audit_path=paths["phase4_audit"],
        split_plan_path=paths["split_plan"],
        predictions_manifest_path=paths["predictions_manifest"],
        phase8_decision_path=paths["phase8_decision"],
        anti_overfit_audit_path=paths["anti_overfit"],
        models_config=paths["models"],
        costs_config=paths["costs"],
        feature_manifest_path=paths["feature_manifest"],
    )

    assert manifest["frozen"] is False
    assert "anti-overfit audit status is not PASS" in " ".join(manifest["failures"])
