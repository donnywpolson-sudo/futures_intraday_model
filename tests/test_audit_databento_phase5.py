from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

from scripts import audit_databento_common as common
from scripts.audit_databento_phase5 import (
    APPROVED_TIER1_CAUSAL_BASE,
    LEGACY_CAUSAL_BASE,
    REQUIRED_INPUTS,
    run_phase5,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _gate(phase: str, summary: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "phase": phase,
        "status": "pass",
        "proceed_status": "yes",
        "severe_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "blockers_csv": "",
        "reports": [],
        "started_at": "2026-06-28T00:00:00Z",
        "finished_at": "2026-06-28T00:00:01Z",
        "source_mutation_check": "pass",
        "summary": summary or {},
    }


def test_phase5_uses_rebuilt_causal_root_with_legacy_phase4_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    root = tmp_path / "reports" / "data_audit"
    for rel_path in REQUIRED_INPUTS:
        path = tmp_path / rel_path
        if path.suffix == ".csv":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n", encoding="utf-8")

    _write_json(
        root / "phase0_folder_triage" / "phase0_readiness_gate.json",
        _gate("phase0"),
    )
    _write_json(
        root / "phase1_raw_inventory" / "phase1_readiness_gate.json",
        _gate("phase1", {"canonical_raw_source": "data/dbn"}),
    )
    _write_json(
        root / "phase2_raw_validity" / "phase2_readiness_gate.json",
        _gate("phase2", {"sample_rows_scanned": 10, "sample_files_scanned": 2}),
    )
    _write_csv(
        root / "phase2_raw_validity" / "blocker_disposition.csv",
        ["source_issue", "severity_after"],
        [],
    )
    _write_json(
        root / "phase3_ohlcv_reconstruction" / "phase3_readiness_gate.json",
        _gate("phase3", {"sample_trade_rows_scanned": 3}),
    )
    _write_json(
        root / "phase3_ohlcv_reconstruction" / "ohlcv_from_trades_summary.json",
        {"reconstructed_ohlcv_bars": 1, "mismatched_bars": 0},
    )
    _write_json(
        root / "phase4_lineage" / "phase4_readiness_gate.json",
        _gate("phase4", {"unknown_derived_folders_list": ""}),
    )
    _write_csv(
        root / "phase4_lineage" / "medium_blocker_disposition.csv",
        [
            "folder",
            "disposition",
            "requires_rebuild_before_modeling",
            "severity_after",
            "stale_do_not_use",
            "evidence",
            "decision_rationale",
            "next_requirement",
        ],
        [
            {
                "folder": LEGACY_CAUSAL_BASE,
                "disposition": "approved_current",
                "requires_rebuild_before_modeling": "no",
                "severity_after": "none",
                "stale_do_not_use": "no",
                "evidence": "legacy Phase 4 causal evidence",
                "decision_rationale": "retained as historical evidence",
                "next_requirement": "",
            }
        ],
    )
    _write_json(root / "state" / "audit_state.json", {"full": False, "allow_full_scan": False})

    gate = run_phase5(
        SimpleNamespace(
            output_dir="reports/data_audit",
            data_root="data/dbn",
            sample=True,
            full=False,
            allow_full_scan=False,
        )
    )

    summary = gate["summary"]
    assert gate["severe_count"] == 0
    assert summary["approved_causal_base"] == APPROVED_TIER1_CAUSAL_BASE
    assert summary["legacy_causal_base"] == LEGACY_CAUSAL_BASE
    assert summary["legacy_causal_base_classification"] == "retired_legacy_policy_reference"
    assert summary["approved_folders"] == ["data/causal_base_candidates/tier1_rebuild_v1", "data/dbn"]
