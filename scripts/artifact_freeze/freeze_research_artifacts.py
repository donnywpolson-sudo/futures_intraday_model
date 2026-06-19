#!/usr/bin/env python3
"""Freeze research artifacts before any final-holdout evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_FREEZE_ROOT = Path("artifacts/frozen")
DEFAULT_FEATURE_ROOT = Path("data/feature_matrices/baseline")
DEFAULT_WFA_ROOT = Path("reports/wfa")
DEFAULT_PHASE4_AUDIT = Path("reports/phase4/feature_coverage_audit.json")
DEFAULT_PHASE8_DECISION = Path("reports/phase8/alpha_promotion_decision.json")
DEFAULT_ANTI_OVERFIT_AUDIT = Path("reports/experiments/anti_overfit_audit.json")
DEFAULT_MODELS_CONFIG = Path("configs/models.yaml")
DEFAULT_COSTS_CONFIG = Path("configs/costs.yaml")


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_or_missing(path: Path) -> str:
    return _file_sha256(path) if path.exists() else "MISSING"


def _hash_map(paths: Iterable[Path]) -> dict[str, str]:
    return {_relative_path(path): _hash_or_missing(path) for path in paths}


def _copy_target(freeze_dir: Path, source: Path) -> Path:
    try:
        relative = source.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        relative = Path(source.name)
    return freeze_dir / relative


def _git_output(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _registry_paths(feature_root: Path) -> list[Path]:
    return [
        feature_root / "feature_cols.json",
        feature_root / "target_cols.json",
        feature_root / "metadata_cols.json",
        feature_root / "excluded_cols.json",
    ]


def _validate_split_plan(split_plan: Mapping[str, Any]) -> list[str]:
    folds = split_plan.get("folds", [])
    if not isinstance(folds, list) or not folds:
        return ["research split plan has no folds"]
    failures: list[str] = []
    research_folds = [
        fold
        for fold in folds
        if isinstance(fold, Mapping)
        and fold.get("split_group") == "research"
        and fold.get("selection_allowed") is True
    ]
    if not research_folds:
        failures.append("research folds missing")
    if any(
        isinstance(fold, Mapping)
        and fold.get("split_group") == "final_holdout"
        and fold.get("selection_allowed") is True
        for fold in folds
    ):
        failures.append("final-holdout fold is selection_allowed")
    return failures


def _validate_phase8_decision(
    phase8_decision: Mapping[str, Any],
    predictions_manifest: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if phase8_decision.get("promoted") is not True:
        failures.append("Phase 8 decision promoted is not true")
    if phase8_decision.get("model_promotion_allowed") is not True:
        failures.append("Phase 8 decision model_promotion_allowed is not true")
    blockers = phase8_decision.get("blockers")
    if not isinstance(blockers, list):
        failures.append("Phase 8 decision blockers are missing or invalid")
    elif blockers:
        failures.append("Phase 8 decision blockers are not empty")
    if int(phase8_decision.get("failure_count") or 0) > 0:
        failures.append("Phase 8 decision failure_count is nonzero")

    for field in ("run", "profile", "resolved_profile"):
        phase8_value = phase8_decision.get(field)
        manifest_value = predictions_manifest.get(field)
        if not isinstance(phase8_value, str) or not phase8_value:
            failures.append(f"Phase 8 decision {field} missing")
        if not isinstance(manifest_value, str) or not manifest_value:
            failures.append(f"predictions manifest {field} missing")
        elif isinstance(phase8_value, str) and phase8_value != manifest_value:
            failures.append(
                f"Phase 8 decision {field} mismatch: phase8={phase8_value!r} "
                f"predictions_manifest={manifest_value!r}"
            )
    return failures


def _validate_anti_overfit_audit(
    anti_overfit_audit: Mapping[str, Any],
    predictions_manifest: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    status = anti_overfit_audit.get("robustness_status", anti_overfit_audit.get("status"))
    if status != "PASS":
        failures.append(f"anti-overfit audit status is not PASS: {status!r}")
    audit_failures = anti_overfit_audit.get("failures")
    if not isinstance(audit_failures, list):
        failures.append("anti-overfit audit failures are missing or invalid")
    elif audit_failures:
        failures.append("anti-overfit audit failures are not empty")
    audit_profile = anti_overfit_audit.get("profile")
    manifest_profile = predictions_manifest.get("profile")
    if audit_profile is not None and audit_profile != manifest_profile:
        failures.append(
            f"anti-overfit audit profile mismatch: audit={audit_profile!r} "
            f"predictions_manifest={manifest_profile!r}"
        )
    return failures


def _validate_schema(feature_root: Path, feature_manifest: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    registries = _registry_paths(feature_root)
    missing = [path for path in registries if not path.exists()]
    if missing:
        return [
            "feature registry files missing: "
            + ",".join(_relative_path(path) for path in missing)
        ]
    feature_cols = json.loads(registries[0].read_text(encoding="utf-8"))
    target_cols = json.loads(registries[1].read_text(encoding="utf-8"))
    excluded_cols = json.loads(registries[3].read_text(encoding="utf-8"))
    if not isinstance(feature_cols, list) or not feature_cols:
        failures.append("feature_cols registry is empty or invalid")
    if not isinstance(target_cols, list) or not target_cols:
        failures.append("target_cols registry is empty or invalid")
    if not isinstance(excluded_cols, list):
        failures.append("excluded_cols registry is invalid")
    manifest_registry = feature_manifest.get("registry", {}) if feature_manifest else {}
    if isinstance(manifest_registry, Mapping):
        manifest_features = manifest_registry.get("feature_cols")
        if isinstance(manifest_features, list) and manifest_features != feature_cols:
            failures.append("feature manifest schema does not match feature_cols registry")
    return failures


def validate_freeze_inputs(
    *,
    feature_root: Path = DEFAULT_FEATURE_ROOT,
    phase4_audit_path: Path = DEFAULT_PHASE4_AUDIT,
    split_plan_path: Path = DEFAULT_WFA_ROOT / "split_plan.json",
    predictions_manifest_path: Path = DEFAULT_WFA_ROOT / "baseline_predictions_manifest.json",
    phase8_decision_path: Path = DEFAULT_PHASE8_DECISION,
    anti_overfit_audit_path: Path = DEFAULT_ANTI_OVERFIT_AUDIT,
    feature_manifest_path: Path = Path("reports/phase4/baseline_feature_manifest.json"),
) -> list[str]:
    failures: list[str] = []
    phase4_audit = _read_json(phase4_audit_path)
    if not phase4_audit:
        failures.append(f"missing Phase 4 coverage audit: {_relative_path(phase4_audit_path)}")
    elif int(phase4_audit.get("missing_tier3_count") or 0) > 0:
        failures.append(
            f"Tier-3 Phase 4 incomplete: missing_tier3_count={phase4_audit.get('missing_tier3_count')}"
        )

    failures.extend(_validate_split_plan(_read_json(split_plan_path)))

    predictions_manifest = _read_json(predictions_manifest_path)
    if not predictions_manifest:
        failures.append(f"missing predictions manifest: {_relative_path(predictions_manifest_path)}")
    else:
        if int(predictions_manifest.get("failure_count") or 0) > 0:
            failures.append("predictions manifest failure_count is nonzero")
        if predictions_manifest.get("stale_output_path_exists") is True:
            failures.append("predictions manifest flags stale output")
        if predictions_manifest.get("artifact_evidence_ready") is not True:
            failures.append("predictions manifest artifact_evidence_ready is not true")

    phase8_decision = _read_json(phase8_decision_path)
    if not phase8_decision:
        failures.append(f"missing Phase 8 decision: {_relative_path(phase8_decision_path)}")
    else:
        failures.extend(_validate_phase8_decision(phase8_decision, predictions_manifest))
        if phase8_decision.get("final_holdout_touched") is True:
            failures.append("final holdout was touched before freeze")
        if phase8_decision.get("trading_semantics_changed") is True:
            failures.append("trading semantics changed before freeze")

    anti_overfit_audit = _read_json(anti_overfit_audit_path)
    if not anti_overfit_audit:
        failures.append(f"missing anti-overfit audit: {_relative_path(anti_overfit_audit_path)}")
    else:
        failures.extend(_validate_anti_overfit_audit(anti_overfit_audit, predictions_manifest))

    failures.extend(_validate_schema(feature_root, _read_json(feature_manifest_path)))
    return failures


def freeze_research_artifacts(
    *,
    freeze_id: str,
    freeze_root: Path = DEFAULT_FREEZE_ROOT,
    feature_root: Path = DEFAULT_FEATURE_ROOT,
    phase4_audit_path: Path = DEFAULT_PHASE4_AUDIT,
    split_plan_path: Path = DEFAULT_WFA_ROOT / "split_plan.json",
    predictions_manifest_path: Path = DEFAULT_WFA_ROOT / "baseline_predictions_manifest.json",
    phase8_decision_path: Path = DEFAULT_PHASE8_DECISION,
    anti_overfit_audit_path: Path = DEFAULT_ANTI_OVERFIT_AUDIT,
    models_config: Path = DEFAULT_MODELS_CONFIG,
    costs_config: Path = DEFAULT_COSTS_CONFIG,
    feature_manifest_path: Path = Path("reports/phase4/baseline_feature_manifest.json"),
) -> dict[str, Any]:
    failures = validate_freeze_inputs(
        feature_root=feature_root,
        phase4_audit_path=phase4_audit_path,
        split_plan_path=split_plan_path,
        predictions_manifest_path=predictions_manifest_path,
        phase8_decision_path=phase8_decision_path,
        anti_overfit_audit_path=anti_overfit_audit_path,
        feature_manifest_path=feature_manifest_path,
    )
    freeze_dir = freeze_root / freeze_id
    if failures:
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "freeze_id": freeze_id,
            "frozen": False,
            "failure_count": len(failures),
            "failures": failures,
        }
        _write_json(freeze_dir / "manifest.json", manifest)
        return manifest

    copy_sources = [
        *_registry_paths(feature_root),
        phase4_audit_path,
        split_plan_path,
        predictions_manifest_path,
        phase8_decision_path,
        anti_overfit_audit_path,
        models_config,
        costs_config,
    ]
    copy_map: dict[str, str] = {}
    for source in copy_sources:
        target = _copy_target(freeze_dir, source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copy_map[_relative_path(source)] = _relative_path(target)

    phase8_decision = _read_json(phase8_decision_path)
    predictions_manifest = _read_json(predictions_manifest_path)
    anti_overfit_audit = _read_json(anti_overfit_audit_path)
    anti_overfit_status = anti_overfit_audit.get(
        "robustness_status", anti_overfit_audit.get("status")
    )
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "freeze_id": freeze_id,
        "frozen": True,
        "failure_count": 0,
        "failures": [],
        "feature_root": _relative_path(feature_root),
        "frozen_root": _relative_path(freeze_dir),
        "run": predictions_manifest.get("run"),
        "profile": predictions_manifest.get("profile"),
        "resolved_profile": predictions_manifest.get("resolved_profile"),
        "copied_artifacts": copy_map,
        "source_hashes": _hash_map(copy_sources),
        "git": {
            "commit": _git_output(["rev-parse", "HEAD"]),
            "status_short": _git_output(["status", "--short"]),
        },
        "phase8_promoted": phase8_decision.get("promoted"),
        "phase8_model_promotion_allowed": phase8_decision.get("model_promotion_allowed"),
        "phase8_blockers": phase8_decision.get("blockers", []),
        "phase8_run": phase8_decision.get("run"),
        "phase8_profile": phase8_decision.get("profile"),
        "phase8_resolved_profile": phase8_decision.get("resolved_profile"),
        "anti_overfit_status": anti_overfit_status,
        "anti_overfit_failures": anti_overfit_audit.get("failures", []),
        "final_holdout_touched": False,
        "final_holdout_consumes_frozen_only": True,
        "used_final_holdout_for_tuning": False,
    }
    _write_json(freeze_dir / "manifest.json", manifest)
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-id", required=True)
    parser.add_argument("--freeze-root", default=DEFAULT_FREEZE_ROOT.as_posix())
    parser.add_argument("--feature-root", default=DEFAULT_FEATURE_ROOT.as_posix())
    parser.add_argument("--phase4-audit", default=DEFAULT_PHASE4_AUDIT.as_posix())
    parser.add_argument("--split-plan", default=(DEFAULT_WFA_ROOT / "split_plan.json").as_posix())
    parser.add_argument(
        "--predictions-manifest",
        default=(DEFAULT_WFA_ROOT / "baseline_predictions_manifest.json").as_posix(),
    )
    parser.add_argument("--phase8-decision", default=DEFAULT_PHASE8_DECISION.as_posix())
    parser.add_argument("--anti-overfit-audit", default=DEFAULT_ANTI_OVERFIT_AUDIT.as_posix())
    parser.add_argument("--models-config", default=DEFAULT_MODELS_CONFIG.as_posix())
    parser.add_argument("--costs-config", default=DEFAULT_COSTS_CONFIG.as_posix())
    parser.add_argument("--feature-manifest", default="reports/phase4/baseline_feature_manifest.json")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    manifest = freeze_research_artifacts(
        freeze_id=args.freeze_id,
        freeze_root=Path(args.freeze_root),
        feature_root=Path(args.feature_root),
        phase4_audit_path=Path(args.phase4_audit),
        split_plan_path=Path(args.split_plan),
        predictions_manifest_path=Path(args.predictions_manifest),
        phase8_decision_path=Path(args.phase8_decision),
        anti_overfit_audit_path=Path(args.anti_overfit_audit),
        models_config=Path(args.models_config),
        costs_config=Path(args.costs_config),
        feature_manifest_path=Path(args.feature_manifest),
    )
    status = "PASS" if manifest["failure_count"] == 0 else "FAIL"
    print(f"{status} freeze {args.freeze_id}: failures={manifest['failure_count']}")
    return 1 if manifest["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
