from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sidecar_manifest_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.manifest.json")


def _schema_path_name(schema: str) -> str:
    if schema == "ohlcv-1m":
        return "ohlcv_1m"
    return schema.replace("-", "_")


def _target_path(source: Path, target_root: Path, manifest: dict[str, Any]) -> Path:
    schema = str(manifest.get("schema") or "")
    market = str(manifest.get("market") or source.parent.name)
    start = str(manifest.get("start") or "")
    end = str(manifest.get("end") or "")
    year = start[:4]
    return target_root / _schema_path_name(schema) / market / year / f"{start}_{end}.dbn.zst"


def _safe_manifest(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    manifest_path = sidecar_manifest_path(path)
    if not manifest_path.exists():
        return None, ["missing manifest"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"invalid manifest: {exc}"]
    expected_hash = manifest.get("file_sha256")
    if expected_hash and expected_hash != file_sha256(path):
        return manifest, ["manifest file_sha256 mismatch"]
    return manifest, []


def _new_counts() -> dict[str, int]:
    return {
        "total": 0,
        "plan_move": 0,
        "unsafe": 0,
        "skip_target_exists_same_hash": 0,
        "protected_parquet": 0,
        "unsafe_parquet": 0,
    }


def build_plan(raw_root: Path, target_root: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    protected_parquet: list[dict[str, Any]] = []
    counts = _new_counts()

    for path in sorted(p for p in raw_root.rglob("*") if p.is_file()):
        if path.name.endswith(".manifest.json"):
            continue
        if path.suffix == ".parquet":
            if len(path.relative_to(raw_root).parts) == 2:
                counts["protected_parquet"] += 1
                protected_parquet.append({"source_path": path.as_posix(), "action": "protect"})
            else:
                counts["unsafe"] += 1
                counts["unsafe_parquet"] += 1
                protected_parquet.append({"source_path": path.as_posix(), "action": "unsafe"})
            continue

        if not path.name.endswith(".dbn.zst") and path.suffix != ".dbn":
            continue

        counts["total"] += 1
        manifest, reasons = _safe_manifest(path)
        if not path.name.endswith(".dbn.zst"):
            reasons.append("legacy DBN file is not .dbn.zst")

        target = _target_path(path, target_root, manifest or {}) if manifest else None
        action = "plan_move"
        if target and target.exists():
            if file_sha256(path) == file_sha256(target):
                action = "skip_target_exists_same_hash"
            else:
                reasons.append("target already exists with different hash")

        if reasons:
            action = "unsafe"

        counts[action] += 1
        items.append(
            {
                "source_path": path.as_posix(),
                "manifest_path": sidecar_manifest_path(path).as_posix(),
                "target_path": target.as_posix() if target else None,
                "schema": manifest.get("schema") if manifest else None,
                "action": action,
                "unsafe_reasons": reasons,
                "manifest_path_update_required": bool(
                    target and manifest and manifest.get("path") != target.as_posix()
                ),
            }
        )

    return {
        "raw_root": raw_root.as_posix(),
        "target_root": target_root.as_posix(),
        "counts": counts,
        "items": items,
        "protected_parquet": protected_parquet,
    }


def apply_migration(plan: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    moved = 0
    for item in plan.get("items", []):
        if item.get("action") != "plan_move":
            continue
        source = Path(str(item["source_path"]))
        target = Path(str(item["target_path"]))
        source_manifest = sidecar_manifest_path(source)
        target_manifest = sidecar_manifest_path(target)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            if source_manifest.exists():
                payload = json.loads(source_manifest.read_text(encoding="utf-8"))
                payload["path"] = target.as_posix()
                payload["file_sha256"] = file_sha256(target)
                target_manifest.write_text(json.dumps(payload), encoding="utf-8")
                source_manifest.unlink()
            moved += 1
        except Exception as exc:
            failures.append({"source_path": source.as_posix(), "error": str(exc)})
    return {"applied": not failures, "moved": moved, "failures": failures}
