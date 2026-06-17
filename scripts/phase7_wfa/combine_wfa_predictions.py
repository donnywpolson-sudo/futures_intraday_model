#!/usr/bin/env python3
"""Combine WFA prediction shards into one prediction artifact."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_hash_or_missing(path: Path) -> str:
    return _file_sha256(path) if path.exists() else "MISSING"


def _file_hash_map(paths: Iterable[Path]) -> dict[str, str]:
    return {_relative_path(path): _file_hash_or_missing(path) for path in paths}


def _manifest_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value)


def _unique_manifest_value(
    manifests: list[dict[str, Any]],
    key: str,
    failures: list[str],
) -> Any:
    values = [manifest.get(key) for manifest in manifests if manifest.get(key) not in (None, "")]
    encoded = {json.dumps(value, sort_keys=True, default=str) for value in values}
    if not values:
        failures.append(f"shard manifests missing {key}")
        return None
    if len(encoded) > 1:
        failures.append(f"shard manifests disagree on {key}")
        return None
    return values[0]


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _manifest_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(Path(item) for item in glob.glob(pattern))
    return sorted({path.resolve() for path in paths})


def _expected_fold_ids(split_plan: Path) -> set[str]:
    manifest = _read_json(split_plan)
    folds = manifest.get("folds", [])
    if not isinstance(folds, list):
        return set()
    return {
        str(fold["fold_id"])
        for fold in folds
        if isinstance(fold, Mapping)
        and fold.get("selection_allowed") is True
        and fold.get("split_group") == "research"
        and "fold_id" in fold
    }


def combine_wfa_prediction_shards(
    *,
    manifest_patterns: list[str],
    run: str,
    predictions_root: Path,
    reports_root: Path,
    split_plan: Path | None = None,
    require_all_folds: bool = False,
) -> dict[str, Any]:
    failures: list[str] = []
    manifests: list[dict[str, Any]] = []
    manifest_paths = _manifest_paths(manifest_patterns)
    if not manifest_paths:
        failures.append("no shard prediction manifests matched")

    prediction_paths: list[Path] = []
    for manifest_path in manifest_paths:
        manifest = _read_json(manifest_path)
        manifests.append(manifest)
        if int(manifest.get("failure_count") or 0) > 0:
            failures.append(f"{_relative_path(manifest_path)} failure_count is nonzero")
        if manifest.get("artifact_evidence_ready") is not True:
            failures.append(f"{_relative_path(manifest_path)} artifact_evidence_ready is not true")
        prediction_path = Path(str(manifest.get("prediction_path", "")))
        if not prediction_path.exists():
            failures.append(f"missing shard prediction parquet: {_relative_path(prediction_path)}")
        else:
            prediction_paths.append(prediction_path)

    frames = [pd.read_parquet(path) for path in prediction_paths] if prediction_paths else []
    output_path = predictions_root / run / "oos_predictions.parquet"
    duplicate_count = 0
    prediction_count = 0
    combined_fold_ids: set[str] = set()
    if frames:
        output = pd.concat(frames, ignore_index=True)
        duplicate_count = int(
            output.duplicated(
                subset=["market", "timestamp", "fold_id", "model_id", "target_name"]
            ).sum()
        )
        if duplicate_count:
            failures.append(f"duplicate combined prediction rows: {duplicate_count}")
        combined_fold_ids = set(output["fold_id"].dropna().astype(str).unique())
        prediction_markets = sorted(output["market"].dropna().astype(str).unique().tolist())
        prediction_years = sorted(int(year) for year in output["year"].dropna().unique())
        if require_all_folds:
            if split_plan is None:
                failures.append("--require-all-folds needs --split-plan")
            else:
                expected = _expected_fold_ids(split_plan)
                missing_folds = sorted(expected - combined_fold_ids)
                extra_folds = sorted(combined_fold_ids - expected)
                if missing_folds:
                    failures.append(f"combined predictions missing folds: {len(missing_folds)}")
                if extra_folds:
                    failures.append(f"combined predictions include extra folds: {len(extra_folds)}")
        if not failures:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = output_path.with_name(f"{output_path.name}.tmp")
            output.to_parquet(tmp_path, index=False)
            tmp_path.replace(output_path)
            prediction_count = int(len(output))
    else:
        prediction_markets = []
        prediction_years = []
        failures.append("no shard prediction rows to combine")

    profile = _unique_manifest_value(manifests, "profile", failures) if manifests else None
    resolved_profile = (
        _unique_manifest_value(manifests, "resolved_profile", failures) if manifests else None
    )
    markets = _unique_manifest_value(manifests, "markets", failures) if manifests else None
    years = _unique_manifest_value(manifests, "years", failures) if manifests else None
    split_plan_profile = (
        _unique_manifest_value(manifests, "split_plan_profile", failures) if manifests else None
    )
    split_plan_resolved_profile = (
        _unique_manifest_value(manifests, "split_plan_resolved_profile", failures)
        if manifests
        else None
    )
    split_plan_config_hash = (
        _unique_manifest_value(manifests, "split_plan_config_hash", failures) if manifests else None
    )
    if profile != split_plan_profile:
        failures.append("shard profile does not match split-plan profile")
    if resolved_profile != split_plan_resolved_profile:
        failures.append("shard resolved_profile does not match split-plan resolved_profile")

    shard_split_plan_path = _manifest_path(
        _unique_manifest_value(manifests, "split_plan_path", failures) if manifests else None
    )
    resolved_split_plan = split_plan or shard_split_plan_path
    split_plan_hash = _file_hash_or_missing(resolved_split_plan) if resolved_split_plan else None
    shard_split_plan_hash = (
        _unique_manifest_value(manifests, "split_plan_hash", failures) if manifests else None
    )
    if split_plan_hash and shard_split_plan_hash and split_plan_hash != shard_split_plan_hash:
        failures.append("shard split_plan_hash does not match combined split plan")

    output_hashes = (
        _file_hash_map([output_path])
        if prediction_count > 0
        else {_relative_path(output_path): "NOT_WRITTEN"}
    )
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "run": run,
        "profile": profile,
        "resolved_profile": resolved_profile,
        "markets": markets,
        "years": years,
        "prediction_path": _relative_path(output_path),
        "prediction_markets": prediction_markets,
        "prediction_years": prediction_years,
        "predictions_root": _relative_path(predictions_root),
        "reports_root": _relative_path(reports_root),
        "split_plan_path": _relative_path(resolved_split_plan) if resolved_split_plan else None,
        "split_plan_hash": split_plan_hash,
        "split_plan_profile": split_plan_profile,
        "split_plan_resolved_profile": split_plan_resolved_profile,
        "split_plan_config_hash": split_plan_config_hash,
        "manifest_patterns": manifest_patterns,
        "shard_manifest_count": len(manifest_paths),
        "shard_prediction_count": sum(int(item.get("prediction_count") or 0) for item in manifests),
        "prediction_count": prediction_count,
        "fold_count": len(combined_fold_ids),
        "duplicate_prediction_count": duplicate_count,
        "input_file_hashes": _file_hash_map(
            [*manifest_paths, *prediction_paths, *([resolved_split_plan] if resolved_split_plan else [])]
        ),
        "output_file_hashes": output_hashes,
        "stale_output_path_exists": False,
        "failure_count": len(failures),
        "failures": failures,
        "artifact_evidence_ready": len(failures) == 0 and prediction_count > 0,
    }
    _write_json(reports_root / f"{run}_predictions_manifest.json", manifest)
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-pattern", action="append", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--predictions-root", default="data/predictions")
    parser.add_argument("--reports-root", default="reports/wfa")
    parser.add_argument("--split-plan", default=None)
    parser.add_argument("--require-all-folds", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    manifest = combine_wfa_prediction_shards(
        manifest_patterns=args.manifest_pattern,
        run=args.run,
        predictions_root=Path(args.predictions_root),
        reports_root=Path(args.reports_root),
        split_plan=Path(args.split_plan) if args.split_plan else None,
        require_all_folds=args.require_all_folds,
    )
    status = "FAIL" if manifest["failure_count"] else "PASS"
    print(
        f"{status} combine WFA predictions: shards={manifest['shard_manifest_count']} "
        f"predictions={manifest['prediction_count']} folds={manifest['fold_count']} "
        f"failures={manifest['failure_count']}"
    )
    return 1 if manifest["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
