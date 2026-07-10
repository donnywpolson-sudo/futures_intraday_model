from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import joblib
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import export_live_shadow_bundle as exporter
from scripts.live_shadow_runner import REQUIRED_TARGETS, normalize_model_bundle


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_model_trust_inputs(tmp_path: Path, *, allow_paper_live: bool = True) -> tuple[Path, Path]:
    closeout = _write_json(
        tmp_path / "model_trust" / "closeout.json",
        {
            "run_id": "tier1_core_phase6_full_predictions_20260706",
            "verdict": "MODEL_TRUST_READY" if allow_paper_live else "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE",
            "modeling_pause_required": not allow_paper_live,
            "promotion_allowed": allow_paper_live,
            "non_approval": {
                "paper": allow_paper_live,
                "live": allow_paper_live,
            },
        },
    )
    matrix = _write_json(
        tmp_path / "model_trust" / "matrix.json",
        {
            "run_id": "tier1_core_phase6_full_predictions_20260706",
            "alpha_evidence_ready": allow_paper_live,
            "verdict": "READY" if allow_paper_live else "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE",
        },
    )
    return closeout, matrix


def test_cli_help_runs_when_invoked_by_script_path() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_live_shadow_bundle.py"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "--approval-note" in result.stdout


def _write_models_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
policy:
  random_splits_allowed: false
  final_holdout_tuning_allowed: false
  hyperparameter_tuning_allowed_initially: false
models:
  ridge_return_v1:
    stage: phase_7a_linear_controls
    family: ridge_regression
    task: regression
    target: target_ret_15m
    enabled: true
    requires_optional_dependency: false
  logistic_direction_v1:
    stage: phase_7a_linear_controls
    family: logistic_regression
    task: classification
    target: target_sign_with_deadzone
    enabled: true
    requires_optional_dependency: false
  logistic_fade_success_v1:
    stage: phase_7a_linear_controls
    family: logistic_regression
    task: classification
    target: target_fade_success_15m
    enabled: true
    requires_optional_dependency: false
  logistic_trend_adverse_long_v1:
    stage: phase_7a_linear_controls
    family: logistic_regression
    task: classification
    target: target_trend_adverse_long_30m
    enabled: true
    requires_optional_dependency: false
  logistic_trend_adverse_short_v1:
    stage: phase_7a_linear_controls
    family: logistic_regression
    task: classification
    target: target_trend_adverse_short_30m
    enabled: true
    requires_optional_dependency: false
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_feature_set(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "feature_set_id": "fixture_live_shadow_features",
                "status": "FROZEN",
                "allowed_for_wfa": True,
                "feature_count": 1,
                "features": ["feature_ret_1"],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_feature_matrix(root: Path, *, market: str = "ES", year: int = 2024) -> Path:
    ts = pd.date_range(f"{year}-01-01T00:00:00Z", periods=90, freq="h")
    signal = [float((idx % 9) - 4) for idx in range(len(ts))]
    path = root / market / f"{year}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "ts": ts,
            "market": market,
            "year": year,
            "session_id": "session",
            "session_segment_id": "segment",
            "causal_valid": True,
            "target_valid": True,
            "feature_input_valid": True,
            "training_row_valid": True,
            "close": 100.0,
            "target_entry_ts": ts + pd.Timedelta(minutes=1),
            "target_exit_ts": ts + pd.Timedelta(minutes=16),
            "target_entry_price": 100.25,
            "target_exit_price": 100.50,
            "minutes_until_session_close": 60.0,
            "feature_ret_1": signal,
            "target_ret_15m": [value * 0.001 for value in signal],
            "target_sign_with_deadzone": [-1, 0, 1] * 30,
            "target_fade_success_15m": [idx % 2 == 0 for idx in range(len(ts))],
            "target_trend_adverse_long_30m": [idx % 3 == 0 for idx in range(len(ts))],
            "target_trend_adverse_short_30m": [idx % 3 == 1 for idx in range(len(ts))],
        }
    ).to_parquet(path, index=False)
    return path


def test_approval_guard_requires_promotion_or_explicit_shadow_override(tmp_path: Path) -> None:
    closeout, matrix = _write_model_trust_inputs(tmp_path)

    with pytest.raises(SystemExit, match="not promotion-approved"):
        exporter.validate_export_approval(
            promotion_report=tmp_path / "missing.json",
            allow_not_promoted_shadow_export=False,
            approval_note="paper shadow only",
            model_trust_closeout=closeout,
            model_trust_matrix=matrix,
        )

    approval = exporter.validate_export_approval(
        promotion_report=tmp_path / "missing.json",
        allow_not_promoted_shadow_export=True,
        approval_note="paper shadow only",
        model_trust_closeout=closeout,
        model_trust_matrix=matrix,
    )

    assert approval["approval_status"] == "explicit_not_promoted_shadow_export"
    assert approval["approval_note"] == "paper shadow only"
    assert approval["model_trust_gate_allowed"] is True


def test_model_trust_gate_blocks_shadow_export_even_with_override(tmp_path: Path) -> None:
    closeout, matrix = _write_model_trust_inputs(tmp_path, allow_paper_live=False)

    with pytest.raises(SystemExit, match="model trust gate blocks live shadow export"):
        exporter.validate_export_approval(
            promotion_report=tmp_path / "missing.json",
            allow_not_promoted_shadow_export=True,
            approval_note="paper shadow only",
            model_trust_closeout=closeout,
            model_trust_matrix=matrix,
        )


def test_export_writes_joblib_bundle_and_manifest(tmp_path: Path) -> None:
    input_root = tmp_path / "features"
    feature_set = _write_feature_set(tmp_path / "feature_set.json")
    models_config = _write_models_config(tmp_path / "models.yaml")
    _write_feature_matrix(input_root)
    output = tmp_path / "models" / "bundle.joblib"
    manifest = tmp_path / "models" / "bundle.manifest.json"

    result = exporter.export_live_shadow_bundle(
        market="ES",
        years=[2024],
        input_root=input_root,
        feature_set_path=feature_set,
        models_config=models_config,
        output_path=output,
        manifest_path=manifest,
        approval={
            "approval_status": "explicit_not_promoted_shadow_export",
            "approval_note": "fixture paper shadow only",
        },
    )

    assert result.status == "PASS"
    assert output.exists()
    assert manifest.exists()
    bundle = joblib.load(output)
    normalized = normalize_model_bundle(bundle)
    assert normalized.feature_cols == ["feature_ret_1"]
    assert sorted(normalized.estimators) == sorted(REQUIRED_TARGETS)
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["bundle_type"] == exporter.BUNDLE_TYPE
    assert manifest_payload["shadow_only"] is True
    assert manifest_payload["not_for_trading"] is True
    assert manifest_payload["target_names"] == list(REQUIRED_TARGETS)
    assert manifest_payload["approval"]["approval_note"] == "fixture paper shadow only"
