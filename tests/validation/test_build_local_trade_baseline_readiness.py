from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pipeline_gates import file_sha256
from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_baseline_readiness as readiness
from scripts.validation import build_local_trade_proof_status_promotion_proposal as proposal_gate


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _source_report(path: str, *, classification: str, status: str = "PASS") -> dict[str, object]:
    return {
        "path": path,
        "sha256": "a" * 64,
        "role": "candidate_recovery_shard"
        if classification == "candidate_derived_review_evidence"
        else "tier1_repaired",
        "root_classification": classification,
        "status": status,
    }


def _proposal_row(market: str, year: int, *, classification: str) -> dict[str, object]:
    causal_root = (
        ledger_gate.CANDIDATE_CAUSAL_ROOT
        if classification == "candidate_derived_review_evidence"
        else ledger_gate.TIER1_CAUSAL_ROOT
    )
    path = f"reports/pipeline_audit/{market}_{year}.json"
    return {
        "market": market,
        "year": year,
        "proposed_proof_status": proposal_gate.PROPOSED_STATUS,
        "proposal_only": True,
        "proof_status_promoted": False,
        "source_report_roles": ["candidate_recovery_shard"],
        "source_classifications": [classification],
        "causal_roots": [causal_root],
        "source_reports": [_source_report(path, classification=classification)],
        "evidence_windows": [
            {
                "report_path": path,
                "window": {"start": "2025-06-18T00:00:00Z", "end": "2026-06-13T00:00:00Z"},
            }
        ],
    }


def _proposal_payload() -> dict[str, object]:
    rows = [
        _proposal_row("ES", 2025, classification="repaired_tier1_convention_evidence"),
        _proposal_row("ES", 2026, classification="repaired_tier1_convention_evidence"),
        _proposal_row("NG", 2025, classification="candidate_derived_review_evidence"),
        _proposal_row("NG", 2026, classification="candidate_derived_review_evidence"),
    ]
    return {
        "summary": {
            "stage": proposal_gate.STAGE,
            "status": proposal_gate.STATUS_READY,
            "decision": proposal_gate.DECISION_REVIEW_ONLY,
            "proposal_row_count": len(rows),
            "uncovered_canonical_market_count": 2,
            "unselected_report_count": 1,
            "excluded_report_count": 1,
            "staged_generated_path_count": 0,
            "proof_status_promoted": False,
            "canonical_promotion_approved": False,
            "generated_artifacts_staged": False,
            "data_mutation_performed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "failure_count": 0,
        },
        "checks": [
            {"name": "input_ledger_review_ready", "status": "PASS"},
            {"name": "proposal_rows_from_accepted_coverage", "status": "PASS"},
        ],
        "proposal_rows": rows,
        "uncovered_canonical_markets": ["NQ", "RTY"],
        "unselected_reports": ["reports/pipeline_audit/NQ_2025.json"],
        "excluded_reports": [],
        "staged_generated_paths": [],
    }


def _write_proposal(tmp_path: Path, payload: dict[str, object] | None = None) -> Path:
    path = tmp_path / "reports" / "pipeline_audit" / "proposal.json"
    _write_json(path, payload or _proposal_payload())
    return path


def _write_prerequisites(
    tmp_path: Path,
    *,
    phase3_filters: bool = False,
    phase4_filters: bool = True,
    missing_ng_cost: bool = False,
    phase3_manifests: bool = True,
) -> None:
    phase3_args = (
        '    parser.add_argument("--markets")\n    parser.add_argument("--years")\n'
        if phase3_filters
        else ""
    )
    phase4_args = (
        '    parser.add_argument("--markets")\n    parser.add_argument("--years")\n'
        if phase4_filters
        else ""
    )
    _write_text(
        tmp_path / "scripts" / "phase3_labels" / "build_labels.py",
        "import argparse\n\ndef build_arg_parser():\n    parser = argparse.ArgumentParser()\n"
        + phase3_args
        + "    return parser\n",
    )
    _write_text(
        tmp_path / "scripts" / "phase4_features" / "build_baseline_features.py",
        "import argparse\n\ndef build_arg_parser():\n    parser = argparse.ArgumentParser()\n"
        + phase4_args
        + "    return parser\n",
    )
    _write_text(
        tmp_path / "configs" / "alpha_tiered.yaml",
        """
profiles:
  tier_3_holdout:
    markets: ["ES", "NG"]
    years: [2025]
  tier_3_forward:
    markets: ["ES", "NG"]
    years: [2026]
""".lstrip(),
    )
    markets = '  ES: {tick_size: 0.25}\n' if missing_ng_cost else '  ES: {tick_size: 0.25}\n  NG: {tick_size: 0.001}\n'
    _write_text(tmp_path / "configs" / "costs.yaml", "markets:\n" + markets)
    if phase3_manifests:
        _write_phase3_manifest_set(tmp_path)


def _write_phase3_manifest(
    tmp_path: Path,
    *,
    profile: str,
    root: Path,
    markets: list[str],
    year: int,
    name: str,
) -> None:
    output_hashes = {}
    outputs = []
    for market in markets:
        output_path = tmp_path / root / market / f"{year}.parquet"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(f"{market} {year}".encode("utf-8"))
        output_hashes[output_path.as_posix()] = file_sha256(output_path)
        outputs.append(
            {
                "market": market,
                "year": year,
                "status": "PASS",
                "warning_count": 0,
                "failure_count": 0,
                "failures": [],
            }
        )
    manifest = {
        "stage": "causal_base",
        "status": "PASS",
        "profile": profile,
        "resolved_profile": profile,
        "output_root": (tmp_path / root).as_posix(),
        "warning_count": 0,
        "failure_count": 0,
        "failures": [],
        "summary": {"fail_count": 0, "warn_count": 0},
        "output_file_hashes": output_hashes,
        "outputs": outputs,
    }
    _write_json(tmp_path / "reports" / "causal_base_fixtures" / name / "causal_base_manifest.json", manifest)


def _write_phase3_manifest_set(tmp_path: Path) -> None:
    candidate_root = Path(ledger_gate.CANDIDATE_CAUSAL_ROOT)
    tier1_root = Path(ledger_gate.TIER1_CAUSAL_ROOT)
    _write_phase3_manifest(
        tmp_path,
        profile="tier_3_holdout",
        root=candidate_root,
        markets=["NG"],
        year=2025,
        name="candidate_2025",
    )
    _write_phase3_manifest(
        tmp_path,
        profile="tier_3_forward",
        root=candidate_root,
        markets=["NG"],
        year=2026,
        name="candidate_2026",
    )
    _write_phase3_manifest(
        tmp_path,
        profile="tier_3_holdout",
        root=tier1_root,
        markets=["ES"],
        year=2025,
        name="tier1_2025",
    )
    _write_phase3_manifest(
        tmp_path,
        profile="tier_3_forward",
        root=tier1_root,
        markets=["ES"],
        year=2026,
        name="tier1_2026",
    )


def _build(
    tmp_path: Path,
    *,
    phase3_filters: bool = False,
    missing_ng_cost: bool = False,
    phase3_manifests: bool = True,
    staged: list[str] | None = None,
) -> dict[str, object]:
    _write_prerequisites(
        tmp_path,
        phase3_filters=phase3_filters,
        missing_ng_cost=missing_ng_cost,
        phase3_manifests=phase3_manifests,
    )
    return readiness.build_report(
        repo_root=tmp_path,
        proposal_path=_write_proposal(tmp_path),
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
    )


def test_reports_action_required_when_phase3_lacks_bounded_filters(tmp_path: Path) -> None:
    report = _build(tmp_path, phase3_filters=False)

    assert report["summary"]["status"] == readiness.STATUS_ACTION_REQUIRED
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["action_required_count"] == 1
    assert report["summary"]["baseline_readiness_scope_defined"] is True
    assert report["summary"]["label_build_command_ready"] is False
    assert report["summary"]["feature_matrix_command_ready"] is False
    assert report["summary"]["eligible_causal_root_count"] == 2
    assert report["summary"]["phase3_causal_base_manifest_ready_count"] == 4
    assert report["summary"]["label_build_approved"] is False
    assert report["summary"]["feature_matrix_build_approved"] is False
    assert report["summary"]["modeling_approved"] is False
    assert report["model_eligible_markets"] == ["ES", "NG"]
    assert report["model_eligible_years"] == [2025, 2026]
    assert any(
        check["name"] == "phase3_label_cli_bounded_filters"
        for check in report["checks"]
        if check["status"] == "ACTION_REQUIRED"
    )


def test_ready_when_phase3_and_phase4_have_bounded_filters(tmp_path: Path) -> None:
    report = _build(tmp_path, phase3_filters=True)

    assert report["summary"]["status"] == readiness.STATUS_READY
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["action_required_count"] == 0
    assert report["summary"]["label_build_command_ready"] is True
    assert report["summary"]["feature_matrix_command_ready"] is True
    assert report["summary"]["phase3_causal_base_manifest_ready_count"] == 4
    label_commands = report["command_families"]["label_build_commands_after_phase3_bounded_controls"]
    assert len(label_commands) == 4
    assert any(
        "scripts.phase3_labels.build_labels --profile tier_3_holdout --input-root data/causally_gated_normalized --output-root data/labeled --reports-root reports/labels/local_trade_baseline/data_causally_gated_normalized_2025 --markets ES --years 2025"
        in command
        for command in label_commands
    )
    assert any(
        "scripts.phase3_labels.build_labels --profile tier_3_forward --input-root data/causal_proof_candidates/local_trade_2025_2026_v1 --output-root data/labeled --reports-root reports/labels/local_trade_baseline/data_causal_proof_candidates_local_trade_2025_2026_v1_2026 --markets NG --years 2026"
        in command
        for command in label_commands
    )
    assert "--reports-root reports/features_baseline/local_trade_baseline/2025" in report["command_families"][
        "feature_matrix_build_commands_after_labels"
    ][0]


def test_missing_cost_entry_is_no_go(tmp_path: Path) -> None:
    report = _build(tmp_path, missing_ng_cost=True)

    assert report["summary"]["status"] == readiness.STATUS_NO_GO
    assert report["summary"]["failure_count"] == 1
    assert any(
        check["name"] == "costs_config_covers_eligible_markets"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_missing_phase3_causal_manifests_are_action_required(tmp_path: Path) -> None:
    report = _build(tmp_path, phase3_filters=True, phase3_manifests=False)

    assert report["summary"]["status"] == readiness.STATUS_ACTION_REQUIRED
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["action_required_count"] == 1
    assert report["summary"]["label_build_command_ready"] is False
    assert report["summary"]["feature_matrix_command_ready"] is False
    assert report["summary"]["phase3_causal_base_manifest_ready_count"] == 0
    assert len(report["phase3_causal_base_manifest_failures"]) == 4
    assert any(
        check["name"] == "phase3_causal_base_manifests_ready"
        for check in report["checks"]
        if check["status"] == "ACTION_REQUIRED"
    )


def test_staged_generated_path_blocks_readiness_without_approval_flag(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/pipeline_audit/generated.json"])

    assert report["summary"]["status"] == readiness.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_write_report_keeps_non_approval_text_and_outputs_under_reports(tmp_path: Path) -> None:
    report = _build(tmp_path)
    json_out = tmp_path / "reports" / "pipeline_audit" / "baseline_readiness.json"
    md_out = tmp_path / "reports" / "pipeline_audit" / "baseline_readiness.md"

    readiness.write_report(report, repo_root=tmp_path, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["status"] == readiness.STATUS_ACTION_REQUIRED
    assert payload["summary"]["modeling_approved"] is False
    assert "`label_build_approved`: `false`" in markdown
    assert "baseline readiness assessment only" in markdown
    assert "Phase 3 --markets/--years controls" in markdown


def test_output_path_outside_reports_fails_closed(tmp_path: Path) -> None:
    report = _build(tmp_path)

    with pytest.raises(ValueError, match="output path must be under reports"):
        readiness.write_report(
            report,
            repo_root=tmp_path,
            json_out=tmp_path / "baseline_readiness.json",
            markdown_out=tmp_path / "reports" / "pipeline_audit" / "baseline_readiness.md",
        )
