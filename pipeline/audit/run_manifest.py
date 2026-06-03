from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.common.io_safe import atomic_write_json


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def write_run_manifest(run_id: str, config: Any, files: list[Path], audit_paths: dict[str, str] | None = None, out: str | Path | None = None) -> dict:
    out = Path(out or f"artifacts/run_manifests/{run_id}.json")
    payload = {
        "run_id": run_id,
        "profile": getattr(config, "active_profile", None),
        "symbols": list(getattr(config, "symbols", [])),
        "data_root": getattr(getattr(config, "data", object()), "root", None),
        "files": [{"path": str(p), "sha256": _sha256(p)} for p in files],
        "audit_paths": audit_paths or {},
        "git_commit": _git_commit(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(out, payload)
    return payload
