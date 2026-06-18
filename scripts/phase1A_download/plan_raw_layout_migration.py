#!/usr/bin/env python3
"""Plan and apply the legacy raw DBN archive layout migration."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


SCHEMA_DIRS = {
    "ohlcv-1m": "ohlcv_1m",
    "definition": "definition",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sidecar_manifest_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.manifest.json")


def _read_manifest(path: Path) -> tuple[dict[str, Any], list[str]]:
    manifest_path = sidecar_manifest_path(path)
    if not manifest_path.exists():
        return {}, ["missing manifest"]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"manifest is not valid JSON: {exc}"]
    if not isinstance(payload, dict):
        return {}, ["manifest payload is not an object"]
    return payload, []


def _target_for(path: Path, target_root: Path, manifest: dict[str, Any]) -> Path | None:
    schema = str(manifest.get("schema", ""))
    schema_dir = SCHEMA_DIRS.get(schema)
    market = str(manifest.get("market", ""))
    start = str(manifest.get("start", ""))
    end = str(manifest.get("end", ""))
    if not schema_dir or not market or not start or not end:
        return None
    year = start[:4]
    return target_root / schema_dir / market / year / f"{start}_{end}.dbn.zst"


def _is_canonical_raw_parquet(path: Path, raw_root: Path) -> bool:
    try:
        parts = path.relative_to(raw_root).parts
    except ValueError:
        return False
    return len(parts) == 2 and path.suffix == ".parquet"


def _dbn_item(path: Path, raw_root: Path, target_root: Path) -> dict[str, Any]:
    manifest, reasons = _read_manifest(path)
    source_hash = file_sha256(path)
    if path.name.endswith(".dbn") and not path.name.endswith(".dbn.zst"):
        reasons.append("legacy DBN file is not .dbn.zst")

    manifest_hash = manifest.get("file_sha256")
    if manifest_hash and manifest_hash != source_hash:
        reasons.append("manifest file_sha256 mismatch")

    target = _target_for(path, target_root, manifest)
    if target is None:
        reasons.append("manifest missing schema/market/start/end")
    elif target.exists():
        if file_sha256(target) == source_hash:
            action = "skip_target_exists_same_hash"
        else:
            action = "unsafe"
            reasons.append("target already exists with different hash")
    else:
        action = "plan_move"

    if reasons:
        action = "unsafe"

    target_path = target.as_posix() if target is not None else None
    manifest_path = sidecar_manifest_path(path)
    target_manifest = sidecar_manifest_path(target) if target is not None else None
    return {
        "source_path": path.as_posix(),
        "source_manifest_path": manifest_path.as_posix(),
        "target_path": target_path,
        "target_manifest_path": target_manifest.as_posix() if target_manifest else None,
        "schema": str(manifest.get("schema", "")),
        "action": action,
        "unsafe_reasons": reasons,
        "manifest_path_update_required": bool(target_path and manifest.get("path") != target_path),
        "source_sha256": source_hash,
        "raw_root": raw_root.as_posix(),
    }


def build_plan(raw_root: Path, target_root: Path) -> dict[str, Any]:
    raw_root = Path(raw_root)
    target_root = Path(target_root)
    items: list[dict[str, Any]] = []
    protected_parquet: list[dict[str, Any]] = []

    for path in sorted(raw_root.rglob("*")) if raw_root.exists() else []:
        if not path.is_file() or path.name.endswith(".manifest.json"):
            continue
        if path.name.endswith(".dbn.zst") or path.name.endswith(".dbn"):
            items.append(_dbn_item(path, raw_root, target_root))
            continue
        if path.suffix == ".parquet":
            canonical = _is_canonical_raw_parquet(path, raw_root)
            protected_parquet.append(
                {
                    "path": path.as_posix(),
                    "action": "protect" if canonical else "unsafe",
                }
            )

    counts = {
        "total": len(items),
        "plan_move": sum(1 for item in items if item["action"] == "plan_move"),
        "unsafe": sum(1 for item in items if item["action"] == "unsafe")
        + sum(1 for item in protected_parquet if item["action"] == "unsafe"),
        "skip_target_exists_same_hash": sum(
            1 for item in items if item["action"] == "skip_target_exists_same_hash"
        ),
        "protected_parquet": sum(1 for item in protected_parquet if item["action"] == "protect"),
        "unsafe_parquet": sum(1 for item in protected_parquet if item["action"] == "unsafe"),
    }
    return {
        "raw_root": raw_root.as_posix(),
        "target_root": target_root.as_posix(),
        "counts": counts,
        "items": items,
        "protected_parquet": protected_parquet,
    }


def apply_migration(plan: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    moved = 0
    if plan.get("counts", {}).get("unsafe", 0):
        return {"applied": False, "moved": 0, "failures": ["plan contains unsafe items"]}

    for item in plan.get("items", []):
        if item.get("action") != "plan_move":
            continue
        source = Path(str(item["source_path"]))
        target = Path(str(item["target_path"]))
        source_manifest = Path(str(item["source_manifest_path"]))
        target_manifest = Path(str(item["target_manifest_path"]))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source.as_posix(), target.as_posix())
            payload = json.loads(source_manifest.read_text(encoding="utf-8"))
            payload["path"] = target.as_posix()
            payload["file_size_bytes"] = target.stat().st_size
            payload["file_sha256"] = file_sha256(target)
            target_manifest.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            source_manifest.unlink()
            moved += 1
        except Exception as exc:  # pragma: no cover - defensive CLI path
            failures.append(f"{source.as_posix()}: {exc}")

    return {"applied": not failures, "moved": moved, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--target-root", default="data/dbn")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    plan = build_plan(Path(args.raw_root), Path(args.target_root))
    if args.apply:
        print(json.dumps(apply_migration(plan), indent=2, sort_keys=True))
    else:
        print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
