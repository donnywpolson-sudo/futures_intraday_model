from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_proof_status_promotion_proposal as proposal_gate
from scripts.validation import build_local_trade_upstream_manifest_evidence_resolver as resolver


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _source_report(path: str, *, classification: str) -> dict[str, object]:
    return {
        "path": path,
        "sha256": "a" * 64,
        "role": "candidate_recovery_shard"
        if classification == "candidate_derived_review_evidence"
        else "tier1_repaired",
        "root_classification": classification,
        "status": "PASS",
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
            "unselected_report_count": 0,
            "excluded_report_count": 0,
            "staged_generated_path_count": 0,
            "proof_status_promoted": False,
            "canonical_promotion_approved": False,
            "generated_artifacts_staged": False,
            "data_mutation_performed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "failure_count": 0,
        },
        "checks": [{"name": "input_ledger_review_ready", "status": "PASS"}],
        "proposal_rows": rows,
        "uncovered_canonical_markets": ["NQ", "RTY"],
        "unselected_reports": [],
        "excluded_reports": [],
        "staged_generated_paths": [],
    }


def _write_proposal(tmp_path: Path) -> Path:
    path = tmp_path / "reports" / "pipeline_audit" / "proposal.json"
    _write_json(path, _proposal_payload())
    return path


def _write_prerequisites(tmp_path: Path) -> None:
    script = (
        "import argparse\n\n"
        "def build_arg_parser():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument(\"--markets\")\n"
        "    parser.add_argument(\"--years\")\n"
        "    return parser\n"
    )
    _write_text(tmp_path / "scripts" / "phase3_labels" / "build_labels.py", script)
    _write_text(tmp_path / "scripts" / "phase4_features" / "build_baseline_features.py", script)
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
    _write_text(
        tmp_path / "configs" / "costs.yaml",
        "markets:\n  ES: {tick_size: 0.25}\n  NG: {tick_size: 0.001}\n",
    )


def _output_hashes(tmp_path: Path, root: Path, rows: list[tuple[str, int]]) -> dict[str, str]:
    return {
        (tmp_path / root / market / f"{year}.parquet").as_posix(): "b" * 64
        for market, year in rows
    }


def _output_row(market: str, year: int, *, status: str = "PASS", warnings: list[str] | None = None) -> dict[str, object]:
    row_warnings = warnings or []
    return {
        "market": market,
        "year": year,
        "status": status,
        "warning_count": len(row_warnings),
        "failure_count": 0,
        "warnings": row_warnings,
        "failures": [],
    }


def _write_manifest(
    tmp_path: Path,
    *,
    report_dir: str,
    profile: str,
    resolved_profile: str | None,
    status: str,
    root: Path,
    outputs: list[dict[str, object]],
) -> None:
    pairs = [(str(row["market"]), int(row["year"])) for row in outputs]
    warning_count = sum(int(row["warning_count"]) for row in outputs)
    manifest = {
        "stage": "causal_base",
        "status": status,
        "profile": profile,
        "resolved_profile": resolved_profile,
        "output_root": (tmp_path / root).as_posix(),
        "warning_count": warning_count,
        "failure_count": 0,
        "warnings": [],
        "failures": [],
        "summary": {"warn_count": warning_count, "fail_count": 0},
        "output_file_hashes": _output_hashes(tmp_path, root, pairs),
        "outputs": outputs,
    }
    _write_json(tmp_path / "reports" / report_dir / "causal_base_manifest.json", manifest)


def _write_manifest_evidence(tmp_path: Path) -> None:
    candidate_root = Path(ledger_gate.CANDIDATE_CAUSAL_ROOT)
    tier1_root = Path(ledger_gate.TIER1_CAUSAL_ROOT)
    _write_manifest(
        tmp_path,
        report_dir="pipeline_audit/causal_proof_candidates/local_trade_2025_2026_v1",
        profile="all_raw",
        resolved_profile="all_raw",
        status="PASS",
        root=candidate_root,
        outputs=[_output_row("NG", 2025), _output_row("NG", 2026)],
    )
    _write_manifest(
        tmp_path,
        report_dir="causal_base_tier3_2025",
        profile="tier_3_holdout",
        resolved_profile=None,
        status="WARN",
        root=tier1_root,
        outputs=[
            _output_row("ES", 2025, status="WARN", warnings=["synthetic threshold breached"]),
        ],
    )
    _write_manifest(
        tmp_path,
        report_dir="causal_base_tier3_2026",
        profile="tier_3_forward",
        resolved_profile=None,
        status="WARN",
        root=tier1_root,
        outputs=[
            _output_row("ES", 2026, status="WARN", warnings=["degraded threshold breached"]),
        ],
    )


def _build(tmp_path: Path, *, staged: list[str] | None = None) -> dict[str, object]:
    _write_prerequisites(tmp_path)
    _write_manifest_evidence(tmp_path)
    return resolver.build_report(
        repo_root=tmp_path,
        proposal_path=_write_proposal(tmp_path),
        generated_at_utc="2026-07-02T00:00:00Z",
        staged_generated_paths=staged or [],
        expected_eligible_market_count=2,
        expected_proof_status_market_year_count=4,
    )


def test_classifies_candidate_projection_and_repaired_warning_paths(tmp_path: Path) -> None:
    report = _build(tmp_path)

    assert report["summary"]["status"] == resolver.STATUS_PLAN_READY
    assert report["summary"]["blocked_group_count"] == 4
    assert report["summary"]["candidate_projection_feasible_count"] == 2
    assert report["summary"]["repaired_warning_evidence_required_count"] == 2
    assert report["summary"]["generated_report_written"] is False
    assert report["summary"]["generated_output_count"] == 0
    assert report["summary"]["manifest_projection_approved"] is False
    assert report["summary"]["label_build_approved"] is False
    assert report["baseline_readiness_summary"]["status"] == "ACTION_REQUIRED_LOCAL_TRADE_BASELINE_READINESS"

    candidate_groups = [
        group for group in report["groups"] if group["classification"] == resolver.CLASS_CANDIDATE_PROJECTION
    ]
    assert {group["year"] for group in candidate_groups} == {2025, 2026}
    assert all(group["manifest_profile"] == "all_raw" for group in candidate_groups)
    assert all(group["approval_required"] is True for group in candidate_groups)

    warning_groups = [group for group in report["groups"] if group["classification"] == resolver.CLASS_REPAIRED_WARNING]
    assert {group["year"] for group in warning_groups} == {2025, 2026}
    assert any(
        "synthetic threshold breached" in blocker["warnings"]
        for group in warning_groups
        for blocker in group["warning_blockers"]
        if blocker["scope"] == "ES:2025"
    )
    assert all(group["metadata_blockers"] for group in warning_groups)


def test_staged_generated_path_is_no_go_without_approval_flag(tmp_path: Path) -> None:
    report = _build(tmp_path, staged=["reports/pipeline_audit/generated.json"])

    assert report["summary"]["status"] == resolver.STATUS_NO_GO
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["staged_generated_path_count"] == 1
    assert report["summary"]["failure_count"] >= 1
    assert any(
        check["name"] == "current_staged_generated_artifacts_absent"
        for check in report["checks"]
        if check["status"] == "FAIL"
    )


def test_cli_is_console_only_and_writes_no_resolver_report(tmp_path: Path, capsys) -> None:
    _write_prerequisites(tmp_path)
    _write_manifest_evidence(tmp_path)
    proposal = _write_proposal(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)

    exit_code = resolver.main(
        [
            "--repo-root",
            str(tmp_path),
            "--proposal",
            str(proposal),
            "--expected-eligible-market-count",
            "2",
            "--expected-proof-status-market-year-count",
            "4",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"{resolver.STAGE} status={resolver.STATUS_PLAN_READY}" in output
    assert "generated_outputs=0" in output
    assert not list((tmp_path / "reports").glob(f"**/{resolver.STAGE}*"))
