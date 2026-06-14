from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.artifact_freeze.freeze_research_artifacts import freeze_research_artifacts


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_freeze_inputs(tmp_path: Path, *, missing_tier3_count: int = 0) -> dict[str, Path]:
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
            "stale_output_path_exists": False,
            "artifact_evidence_ready": True,
        },
    )
    phase8_decision = _write_json(
        tmp_path / "reports" / "phase8" / "alpha_promotion_decision.json",
        {"promoted": False, "blockers": ["net negative"], "final_holdout_touched": False, "trading_semantics_changed": False},
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
        "models": models,
        "costs": costs,
    }


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
        models_config=paths["models"],
        costs_config=paths["costs"],
        feature_manifest_path=paths["feature_manifest"],
    )

    assert manifest["frozen"] is True
    assert manifest["failure_count"] == 0
    assert manifest["final_holdout_touched"] is False
    assert manifest["used_final_holdout_for_tuning"] is False
    assert manifest["phase8_promoted"] is False
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
        models_config=paths["models"],
        costs_config=paths["costs"],
        feature_manifest_path=paths["feature_manifest"],
    )

    assert manifest["frozen"] is False
    assert manifest["failure_count"] > 0
    assert "Tier-3 Phase 4 incomplete" in " ".join(manifest["failures"])
