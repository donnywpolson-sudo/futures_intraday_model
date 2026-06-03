from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.common.io_safe import atomic_write_json


def hash_file(path: str | Path) -> str | None:
    path = Path(path)
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_paths(paths: list[str | Path]) -> str:
    h = hashlib.sha256()
    for raw in sorted(str(p) for p in paths if p):
        p = Path(raw)
        h.update(raw.encode("utf-8"))
        if p.is_file():
            h.update((hash_file(p) or "").encode("utf-8"))
        elif p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.name != child.with_suffix(child.suffix + ".metadata.json").name:
                    h.update(str(child.as_posix()).encode("utf-8"))
                    h.update((hash_file(child) or "").encode("utf-8"))
    return h.hexdigest()


def config_hash(config: Any, sections: list[str] | None = None) -> str:
    sections = sections or ["target", "features", "execution", "walkforward", "pipeline"]
    payload = {}
    for s in sections:
        obj = getattr(config, s, None)
        if obj is None:
            continue
        payload[s] = obj.model_dump() if hasattr(obj, "model_dump") else getattr(obj, "__dict__", str(obj))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def code_hash(paths: list[str | Path]) -> str:
    return hash_paths([p for p in paths if Path(p).exists()])


def metadata_path(artifact: str | Path) -> Path:
    return Path(str(artifact) + ".metadata.json")


def build_cache_metadata(
    artifact_path: str | Path,
    *,
    source_stage: str,
    output_stage: str,
    source_paths: list[str | Path],
    config: Any,
    config_sections: list[str] | None = None,
    code_paths: list[str | Path] | None = None,
    modeling_mode: str | None = None,
    symbol: str | None = None,
    year: str | int | None = None,
    split_id: str | int | None = None,
    train_start: Any = None,
    train_end: Any = None,
    test_start: Any = None,
    test_end: Any = None,
    trusted_for_reuse: bool = True,
    backfilled: bool = False,
) -> dict[str, Any]:
    src_hash = hash_paths(source_paths)
    cfg_hash = config_hash(config, config_sections)
    c_hash = code_hash(code_paths or [])
    mode = modeling_mode or getattr(getattr(config, "pipeline", object()), "modeling_mode", "unknown")
    material = {
        "artifact_path": str(artifact_path),
        "source_stage": source_stage,
        "output_stage": output_stage,
        "source_manifest_hash": src_hash,
        "source_paths": [str(p) for p in source_paths],
        "config_hash": cfg_hash,
        "code_version_hash": c_hash,
        "modeling_mode": mode,
        "symbol": symbol,
        "year": year,
        "split_id": split_id,
        "train_start": str(train_start) if train_start is not None else None,
        "train_end": str(train_end) if train_end is not None else None,
        "test_start": str(test_start) if test_start is not None else None,
        "test_end": str(test_end) if test_end is not None else None,
        "trusted_for_reuse": bool(trusted_for_reuse),
        "backfilled": bool(backfilled),
    }
    material["cache_key"] = hashlib.sha256(json.dumps(material, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    material["created_at_utc"] = datetime.now(timezone.utc).isoformat()
    return material


def write_cache_metadata(artifact_path: str | Path, metadata: dict[str, Any]) -> None:
    atomic_write_json(metadata_path(artifact_path), metadata)


def read_cache_metadata(artifact_path: str | Path) -> dict[str, Any] | None:
    p = metadata_path(artifact_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def cache_is_fresh(artifact_path: str | Path, expected: dict[str, Any], config: Any | None = None) -> tuple[bool, str]:
    if config is not None and not getattr(getattr(config, "io", object()), "skip_completed", True):
        return False, "skip_completed=false"
    if not Path(artifact_path).exists():
        return False, "missing artifact"
    actual = read_cache_metadata(artifact_path)
    if actual is None:
        return False, "missing metadata"
    if actual.get("trusted_for_reuse") is False:
        return False, "untrusted backfill"
    for key in ["source_manifest_hash", "config_hash", "code_version_hash", "modeling_mode", "source_stage", "output_stage", "cache_key"]:
        if actual.get(key) != expected.get(key):
            if key == "source_manifest_hash":
                return False, "missing source" if not expected.get(key) else "source mismatch"
            if key == "config_hash":
                return False, "config mismatch"
            return False, f"{key} mismatch"
    return True, "fresh"
