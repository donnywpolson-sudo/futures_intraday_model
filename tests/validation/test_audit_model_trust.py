from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import audit_model_trust as audit


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _feature_report(path: Path) -> Path:
    return _write_json(
        path,
        {
            "status": "PASS_TIER1_CORE_PHASE4_SELF_REFERENCE_CLEANUP_ACTIVE_PLACEMENT",
            "scope": {
                "profile_alias": "tier_1_core",
                "markets": ["ES", "CL", "ZN", "6E"],
                "years": [2023, 2024],
                "market_year_count": 8,
            },
            "active_counts": {
                "expected_feature_parquets": 8,
                "feature_parquets_present": 8,
                "expected_sidecars": 4,
                "sidecars_present": 4,
                "removed_features_present_in_active_feature_cols": [],
            },
        },
    )


def _causal_report(path: Path, *, status: str = "WARN") -> Path:
    return _write_json(
        path,
        {
            "summary": {
                "status": status,
                "active_raw_pair_count": 530,
                "active_causal_pair_count": 518,
                "raw_without_causal_count": 8,
                "local_trade_gap_gate_status_counts": {"NOT_RUN": 512, "SKIPPED": 6},
            },
            "blockers": [
                {
                    "severity": "Medium",
                    "blocker": "Some active raw pairs have no active causal output.",
                    "evidence": ["ES:2025", "ES:2026"],
                }
            ],
        },
    )


def _semantic_report(path: Path) -> Path:
    return _write_json(
        path,
        {
            "classification": "confirmed mismatch",
            "recommended_next_step": "plan-only fix proposal",
        },
    )


def _build_fixture_report(tmp_path: Path, *, causal_status: str = "WARN") -> dict[str, object]:
    feature = _feature_report(tmp_path / "reports" / "feature.json")
    causal = _causal_report(tmp_path / "reports" / "causal.json", status=causal_status)
    semantic = _semantic_report(tmp_path / "reports" / "semantic.json")
    return audit.build_report(
        repo_root=tmp_path,
        run_id="test_run",
        feature_placement_report=feature,
        causal_readiness_report=causal,
        semantic_mismatch_report=semantic,
        predictions_root=tmp_path / "data" / "predictions",
        generated_at_utc="2026-07-06T00:00:00Z",
    )


def test_report_caps_current_scope_at_research_only_without_trial_packet(tmp_path: Path) -> None:
    report = _build_fixture_report(tmp_path)

    assert report["permitted_use_label"] == "research_only"
    assert report["trial_packet"]["status"] == audit.WARN_RESEARCH_ONLY
    assert any(gate["status"] == audit.WARN_RESEARCH_ONLY for gate in report["gates"])


def test_all_catalog_metrics_emit_zero_to_100_scores_and_inadmissible_reasons(
    tmp_path: Path,
) -> None:
    report = _build_fixture_report(tmp_path)
    rankings = report["metric_rankings"]

    assert len(rankings) == len(audit.METRIC_CATALOG)
    assert {row["score_0_100"] for row in rankings} == {0}
    assert {row["admissibility"] for row in rankings} == {audit.INADMISSIBLE}
    assert all("prediction artifacts" in row["reason"] for row in rankings)
    assert report["metric_group_counts"]["return"] == 6
    assert report["metric_group_counts"]["operational_readiness"] == 7


def test_missing_hard_blocker_evidence_does_not_allow_wfa_or_promotion_label(
    tmp_path: Path,
) -> None:
    feature = _feature_report(tmp_path / "reports" / "feature.json")
    missing_causal = tmp_path / "reports" / "missing_causal.json"
    semantic = _semantic_report(tmp_path / "reports" / "semantic.json")

    report = audit.build_report(
        repo_root=tmp_path,
        run_id="missing_causal",
        feature_placement_report=feature,
        causal_readiness_report=missing_causal,
        semantic_mismatch_report=semantic,
        predictions_root=tmp_path / "data" / "predictions",
    )

    assert report["permitted_use_label"] == "research_only"
    gate2 = next(gate for gate in report["gates"] if gate["gate_id"] == 2)
    assert gate2["status"] == audit.WARN_RESEARCH_ONLY
    assert gate2["evidence_label"] == audit.NOT_ESTABLISHED


def test_paper_live_gates_are_not_applicable_for_report_only_research_audit(
    tmp_path: Path,
) -> None:
    report = _build_fixture_report(tmp_path, causal_status="PASS")

    gate13 = next(gate for gate in report["gates"] if gate["gate_id"] == 13)
    gate14 = next(gate for gate in report["gates"] if gate["gate_id"] == 14)
    assert gate13["status"] == audit.NA_WITH_REASON
    assert gate13["reason"]
    assert gate14["status"] == audit.NA_WITH_REASON
    assert "paper/live" in gate14["reason"]


def test_cli_writes_json_and_markdown_reports(tmp_path: Path, capsys) -> None:
    feature = _feature_report(tmp_path / "reports" / "feature.json")
    causal = _causal_report(tmp_path / "reports" / "causal.json")
    semantic = _semantic_report(tmp_path / "reports" / "semantic.json")
    report_root = tmp_path / "reports" / "model_trust_audit" / "cli_run"

    result = audit.main(
        [
            "--repo-root",
            str(tmp_path),
            "--run-id",
            "cli_run",
            "--report-root",
            str(report_root),
            "--feature-placement-report",
            str(feature),
            "--causal-readiness-report",
            str(causal),
            "--semantic-mismatch-report",
            str(semantic),
            "--predictions-root",
            str(tmp_path / "data" / "predictions"),
        ]
    )
    stdout = capsys.readouterr().out
    written = json.loads((report_root / "model_trust_audit.json").read_text(encoding="utf-8"))

    assert result == 0
    assert "permitted_use_label=research_only" in stdout
    assert written["run_id"] == "cli_run"
    assert (report_root / "model_trust_audit.md").is_file()
