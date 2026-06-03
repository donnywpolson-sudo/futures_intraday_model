from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.common.io_safe import atomic_write_json
from pipeline.common.config import config as flat_config
from pipeline.audit.pipeline_coverage import stage_catalog


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


def write_run_manifest(
    run_id: str,
    config: Any,
    files: list[Path],
    audit_paths: dict[str, str] | None = None,
    out: str | Path | None = None,
    splits: list[dict[str, Any]] | None = None,
    final_acceptance_summary: dict[str, Any] | None = None,
    deployment_readiness: dict[str, Any] | None = None,
    checkpoint_start: dict[str, Any] | None = None,
) -> dict:
    out = Path(out or f"artifacts/run_manifests/{run_id}.json")
    audit_paths = audit_paths or {}
    stage_rows = []
    checkpoint_start = checkpoint_start or {}
    skipped_nums = {
        int(row.get("stage_num"))
        for row in checkpoint_start.get("stage_plan", [])
        if row.get("status") == "SKIPPED_CHECKPOINT"
    }
    for s in stage_catalog():
        outputs = []
        if s.number in {15, 24} and audit_paths.get("output"):
            outputs = [audit_paths["output"]]
        elif s.number in {16, 25} and audit_paths.get("oos_predictions"):
            outputs = [audit_paths["oos_predictions"]]
        elif s.number == 17 and audit_paths.get("execution_trace"):
            outputs = [audit_paths["execution_trace"]]
        elif s.number in {18, 26}:
            outputs = [p for p in [audit_paths.get("metrics"), audit_paths.get("stress")] if p]
        elif s.number in {19, 27} and audit_paths.get("acceptance"):
            outputs = [audit_paths["acceptance"]]
        elif s.number in {22, 23} and audit_paths.get("selector"):
            outputs = [audit_paths["selector"]]
        elif s.number == 14:
            outputs = [str(out)]
        elif s.number in {1, 4, 5, 7, 9, 10, 11, 12, 13, 20, 21}:
            outputs = list(s.output_paths)
        else:
            outputs = list(s.output_paths)
        stage_rows.append({
            "stage_number": s.number,
            "stage_name": s.name,
            "stage_key": s.manifest_key,
            "manifest_key": s.manifest_key,
            "status": "SKIPPED_CHECKPOINT" if s.number in skipped_nums else ("WARN" if s.external_contract else "PASS"),
            "input_paths": list(s.input_paths),
            "output_paths": outputs,
            "report_paths": [p for p in outputs if "reports/" in p or p.endswith("_report.json")],
            "module_or_command": s.module_or_script,
            "callable_or_command": s.callable_or_command,
            "external_contract": s.external_contract,
            "skip_reason": f"checkpoint_start={checkpoint_start.get('start_stage')}" if s.number in skipped_nums else "",
        })
    payload = {
        "run_id": run_id,
        "profile": getattr(config, "active_profile", None) or getattr(flat_config, "ACTIVE_PROFILE", None),
        "config_source": getattr(flat_config, "CONFIG_SOURCE", None),
        "symbols": list(getattr(config, "symbols", [])),
        "data_root": getattr(getattr(config, "data", object()), "root", None),
        "modeling_mode": getattr(getattr(config, "pipeline", object()), "modeling_mode", "unknown"),
        "start_stage": getattr(getattr(config, "pipeline", object()), "start_stage", "raw"),
        "checkpoint_root": checkpoint_start.get("checkpoint_root") or getattr(getattr(config, "pipeline", object()), "checkpoint_root", None),
        "checkpoint_validation_report": f"reports/validation/checkpoint_gate_{checkpoint_start.get('start_stage')}.json" if checkpoint_start.get("start_stage") and checkpoint_start.get("start_stage") != "raw" else "",
        "files": [{"path": str(p), "sha256": _sha256(p)} for p in files],
        "audit_paths": audit_paths,
        "splits": splits or [],
        "stages": stage_rows,
        "final_acceptance_summary": final_acceptance_summary or {},
        "deployment_readiness": deployment_readiness or {},
        "checkpoint_start": checkpoint_start,
        "git_commit": _git_commit(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(out, payload)
    return payload
