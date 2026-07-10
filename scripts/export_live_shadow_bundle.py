#!/usr/bin/env python3
"""Export a guarded joblib bundle for live shadow inference only."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
from sklearn.exceptions import ConvergenceWarning

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.live_shadow_runner import REQUIRED_TARGETS, normalize_model_bundle
from scripts.phase7_wfa.run_wfa import (
    DEFAULT_INPUT_ROOT,
    DEFAULT_MODELS_CONFIG,
    _build_estimator,
    _file_hash_map,
    _git_commit,
    _load_market_frame,
    _relative_path,
    _required_source_columns,
    _stable_hash,
    _target_series,
    _valid_bool,
    load_model_specs,
    resolve_feature_set,
)
from scripts.validation.enforce_model_trust_gate import (
    DEFAULT_CLOSEOUT_PATH as DEFAULT_MODEL_TRUST_CLOSEOUT,
    DEFAULT_MATRIX_PATH as DEFAULT_MODEL_TRUST_MATRIX,
    enforce_model_trust_gate,
)


DEFAULT_MARKET = "ES"
DEFAULT_FEATURE_SET = Path("manifests/feature_sets/baseline_current.json")
DEFAULT_OUTPUT = Path("models/live_shadow/ES_live_shadow_bundle.joblib")
DEFAULT_MANIFEST_OUTPUT = Path("models/live_shadow/ES_live_shadow_bundle.manifest.json")
DEFAULT_PROMOTION_REPORT = Path("reports/phase8/alpha_promotion_decision.json")
BUNDLE_TYPE = "live_shadow_model_bundle_v1"


@dataclass(frozen=True)
class ExportResult:
    status: str
    output_path: Path
    manifest_path: Path
    row_count: int
    years: list[int]
    target_names: list[str]
    warnings: list[str]


def parse_years(value: str | None) -> list[int] | None:
    if value is None or not value.strip():
        return None
    years = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not years:
        raise argparse.ArgumentTypeError("must include at least one year")
    return years


def discover_years(input_root: Path, market: str) -> list[int]:
    market_root = input_root / market
    if not market_root.exists():
        raise SystemExit(f"missing market feature root: {_relative_path(market_root)}")
    years = sorted(int(path.stem) for path in market_root.glob("*.parquet") if path.stem.isdigit())
    if not years:
        raise SystemExit(f"no feature matrices found under {_relative_path(market_root)}")
    return years


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def validate_export_approval(
    *,
    promotion_report: Path,
    allow_not_promoted_shadow_export: bool,
    approval_note: str,
    model_trust_closeout: Path = DEFAULT_MODEL_TRUST_CLOSEOUT,
    model_trust_matrix: Path = DEFAULT_MODEL_TRUST_MATRIX,
) -> dict[str, Any]:
    note = approval_note.strip()
    if not note:
        raise SystemExit("--approval-note is required")
    report: dict[str, Any] = {}
    if promotion_report.exists():
        report = _read_json(promotion_report)
    promoted = (
        report.get("model_promotion_allowed") is True
        or report.get("promoted") is True
        or report.get("research_alpha_ready") is True
    )
    if promoted:
        approval_status = "promotion_report_allows_shadow_export"
    elif allow_not_promoted_shadow_export:
        approval_status = "explicit_not_promoted_shadow_export"
    else:
        raise SystemExit(
            "model is not promotion-approved; pass --allow-not-promoted-shadow-export "
            "with an explicit --approval-note for paper shadow use only"
        )
    trust_gate = enforce_model_trust_gate(
        repo_root=ROOT,
        closeout_path=model_trust_closeout,
        matrix_path=model_trust_matrix,
        intended_action="paper-live",
    )
    if trust_gate["allowed"] is not True:
        blockers = "; ".join(str(item) for item in trust_gate.get("blockers", [])[:4])
        raise SystemExit(f"model trust gate blocks live shadow export: {blockers}")
    return {
        "approval_status": approval_status,
        "approval_note": note,
        "promotion_report": _relative_path(promotion_report),
        "promotion_report_hash": _file_hash_map([promotion_report])[
            _relative_path(promotion_report)
        ],
        "promotion_report_model_promotion_allowed": report.get("model_promotion_allowed"),
        "promotion_report_promoted": report.get("promoted"),
        "promotion_report_research_alpha_ready": report.get("research_alpha_ready"),
        "model_trust_gate_status": trust_gate["status"],
        "model_trust_gate_allowed": trust_gate["allowed"],
        "model_trust_closeout": trust_gate["source_evidence"]["closeout"]["path"],
        "model_trust_matrix": trust_gate["source_evidence"]["matrix"]["path"],
    }


def _target_specs(models_config: Path) -> tuple[list[Any], dict[str, Any]]:
    specs, config = load_model_specs(models_config)
    by_target = {spec.target: spec for spec in specs}
    missing = [target for target in REQUIRED_TARGETS if target not in by_target]
    if missing:
        raise SystemExit("models config missing required live targets: " + ",".join(missing))
    return [by_target[target] for target in REQUIRED_TARGETS], config


def _train_mask(frame: pd.DataFrame, target: pd.Series) -> pd.Series:
    return (
        _valid_bool(frame, "training_row_valid", False)
        & _valid_bool(frame, "causal_valid", False)
        & _valid_bool(frame, "target_valid", False)
        & target.notna()
    )


def train_estimators(
    frame: pd.DataFrame,
    *,
    feature_cols: list[str],
    specs: Sequence[Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    estimators: dict[str, Any] = {}
    diagnostics: list[dict[str, Any]] = []
    failures: list[str] = []
    for spec in specs:
        target = _target_series(frame, spec)
        train_mask = _train_mask(frame, target)
        train = frame.loc[train_mask]
        y_train = target.loc[train_mask]
        detail: dict[str, Any] = {
            "model_id": spec.model_id,
            "target_name": spec.target,
            "task": spec.task,
            "train_rows": int(len(train)),
            "fit_estimator": None,
            "warnings": [],
        }
        if train.empty:
            failures.append(f"{spec.target}: no valid training rows")
            diagnostics.append(detail)
            continue
        estimator, actual_estimator = _build_estimator(spec, y_train)
        detail["fit_estimator"] = actual_estimator
        if actual_estimator == "dummy_class_prior":
            failures.append(f"{spec.target}: dummy class-prior estimator is not exportable")
            diagnostics.append(detail)
            continue
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            estimator.fit(train[feature_cols], y_train)
        detail["warnings"] = [str(item.message).splitlines()[0] for item in caught]
        if caught:
            failures.append(f"{spec.target}: estimator emitted convergence warning")
            diagnostics.append(detail)
            continue
        estimators[spec.target] = estimator
        diagnostics.append(detail)
    return estimators, diagnostics, failures


def export_live_shadow_bundle(
    *,
    market: str,
    years: Iterable[int],
    input_root: Path,
    feature_set_path: Path,
    models_config: Path,
    output_path: Path,
    manifest_path: Path,
    approval: Mapping[str, Any],
) -> ExportResult:
    feature_set = resolve_feature_set(input_root, feature_set_path=feature_set_path)
    specs, model_config = _target_specs(models_config)
    source_columns = _required_source_columns(feature_set.feature_cols, specs)
    frame, failures, input_paths = _load_market_frame(market, years, input_root, source_columns)
    if frame is None:
        raise SystemExit("; ".join(failures) if failures else "no feature rows loaded")
    if failures:
        raise SystemExit("; ".join(failures))
    estimators, diagnostics, train_failures = train_estimators(
        frame,
        feature_cols=feature_set.feature_cols,
        specs=specs,
    )
    if train_failures:
        raise SystemExit("; ".join(train_failures))
    bundle = {
        "schema_version": 1,
        "bundle_type": BUNDLE_TYPE,
        "shadow_only": True,
        "not_for_trading": True,
        "market": market,
        "years": sorted(int(year) for year in years),
        "feature_cols": feature_set.feature_cols,
        "estimators": estimators,
        "target_names": [spec.target for spec in specs],
        "model_ids": [spec.model_id for spec in specs],
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(),
            "model_config_hash": _stable_hash(model_config),
            "feature_config_hash": feature_set.config_hash,
            **dict(approval),
        },
    }
    normalize_model_bundle(bundle)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib = importlib.import_module("joblib")
    joblib.dump(bundle, output_path)
    manifest = {
        "generated_at": bundle["metadata"]["generated_at"],
        "git_commit": bundle["metadata"]["git_commit"],
        "script_path": _relative_path(Path(__file__)),
        "schema_version": 1,
        "bundle_type": BUNDLE_TYPE,
        "shadow_only": True,
        "not_for_trading": True,
        "market": market,
        "years": sorted(int(year) for year in years),
        "input_root": _relative_path(input_root),
        "feature_set": feature_set.manifest,
        "models_config": _relative_path(models_config),
        "model_config_hash": _stable_hash(model_config),
        "feature_config_hash": feature_set.config_hash,
        "input_file_hashes": _file_hash_map([feature_set_path, models_config, *input_paths]),
        "output_file_hashes": _file_hash_map([output_path]),
        "output_path": _relative_path(output_path),
        "feature_count": len(feature_set.feature_cols),
        "target_names": [spec.target for spec in specs],
        "model_ids": [spec.model_id for spec in specs],
        "row_count": int(len(frame)),
        "diagnostics": diagnostics,
        "approval": dict(approval),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return ExportResult(
        status="PASS",
        output_path=output_path,
        manifest_path=manifest_path,
        row_count=int(len(frame)),
        years=sorted(int(year) for year in years),
        target_names=[spec.target for spec in specs],
        warnings=[],
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", default=DEFAULT_MARKET)
    parser.add_argument("--years", default=None, help="Comma-separated years. Defaults to discovered market years.")
    parser.add_argument("--input-root", default=DEFAULT_INPUT_ROOT.as_posix())
    parser.add_argument("--feature-set", default=DEFAULT_FEATURE_SET.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix())
    parser.add_argument("--manifest-output", default=DEFAULT_MANIFEST_OUTPUT.as_posix())
    parser.add_argument("--promotion-report", default=DEFAULT_PROMOTION_REPORT.as_posix())
    parser.add_argument("--model-trust-closeout", default=DEFAULT_MODEL_TRUST_CLOSEOUT.as_posix())
    parser.add_argument("--model-trust-matrix", default=DEFAULT_MODEL_TRUST_MATRIX.as_posix())
    parser.add_argument("--approval-note", required=True)
    parser.add_argument("--allow-not-promoted-shadow-export", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    input_root = Path(args.input_root)
    years = parse_years(args.years) or discover_years(input_root, str(args.market))
    approval = validate_export_approval(
        promotion_report=Path(args.promotion_report),
        allow_not_promoted_shadow_export=bool(args.allow_not_promoted_shadow_export),
        approval_note=str(args.approval_note),
        model_trust_closeout=Path(args.model_trust_closeout),
        model_trust_matrix=Path(args.model_trust_matrix),
    )
    result = export_live_shadow_bundle(
        market=str(args.market),
        years=years,
        input_root=input_root,
        feature_set_path=Path(args.feature_set),
        models_config=Path(args.models_config),
        output_path=Path(args.output),
        manifest_path=Path(args.manifest_output),
        approval=approval,
    )
    print(
        f"{result.status} live shadow bundle: output={_relative_path(result.output_path)} "
        f"manifest={_relative_path(result.manifest_path)} rows={result.row_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
