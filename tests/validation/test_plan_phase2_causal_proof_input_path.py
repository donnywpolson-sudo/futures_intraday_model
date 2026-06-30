from __future__ import annotations

from pathlib import Path

from scripts.validation import plan_phase2_causal_proof_input_path as gate

from tests.validation.test_reconcile_phase2_local_trade_causal_inputs import (
    _write_causal_pair,
    _write_local_report,
    _write_phase2_fixture,
)


def _evaluate(paths: dict[str, Path], local_report: Path, candidate_roots: list[Path]):
    return gate.evaluate_plan(
        repo_root=paths["repo_root"],
        data_manifest_path=paths["data_manifest_path"],
        canonical_root=paths["canonical_root"],
        reports_root=paths["reports_root"],
        phase2_manifest_path=paths["phase2_manifest_path"],
        phase2_validation_path=paths["phase2_validation_path"],
        profile_config_path=paths["profile_config_path"],
        build_script_path=paths["build_script_path"],
        local_report_paths=[local_report],
        candidate_roots=candidate_roots,
        quarantine_root="data/causal_proof_candidates/test_v1",
        expected_count=2,
        feature_cols=["feature_return_1m"],
        git_head="current-head",
        staged_names=[],
        scoped_status_lines=[],
        generated_at_utc="2026-06-30T00:00:00Z",
    )


def test_no_usable_roots_requires_causal_input_authorization(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    root = tmp_path / "data" / "causally_gated_normalized"

    report = _evaluate(paths, _write_local_report(tmp_path), [root])

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["usable_root_count"] == 0
    assert report["allowed_paths"][1]["status"] == "blocked"
    assert report["allowed_paths"][2]["status"] == "requires_separate_approval"
    assert report["allowed_paths"][2]["authorization"]["expected_output_files"] == 2


def test_one_supplied_usable_root_is_ready_to_authorize(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    root = tmp_path / "data" / "candidate_existing"
    _write_causal_pair(root)

    report = _evaluate(paths, _write_local_report(tmp_path), [root])

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["usable_roots"] == ["data/candidate_existing"]
    assert report["allowed_paths"][1]["status"] == "available"


def test_multiple_usable_roots_require_human_decision(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    first = tmp_path / "data" / "candidate_first"
    second = tmp_path / "data" / "candidate_second"
    _write_causal_pair(first)
    _write_causal_pair(second)

    report = _evaluate(paths, _write_local_report(tmp_path), [first, second])

    assert report["summary"]["status"] == gate.STATUS_MULTIPLE
    assert report["summary"]["usable_root_count"] == 2
    assert report["usable_roots"] == ["data/candidate_first", "data/candidate_second"]


def test_default_roots_with_missing_inputs_stay_no_go(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    default_proof_root = tmp_path / "data" / "causally_gated_normalized"
    default_canonical_root = paths["canonical_root"]

    report = _evaluate(paths, _write_local_report(tmp_path), [default_proof_root, default_canonical_root])

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert report["summary"]["reconciliation_status"] == gate.reconcile_gate.STATUS_MISSING
    assert report["summary"]["usable_root_count"] == 0


def test_planner_does_not_write_quarantine_reports_or_data(tmp_path: Path) -> None:
    paths = _write_phase2_fixture(tmp_path)
    root = tmp_path / "data" / "causally_gated_normalized"
    quarantine_root = tmp_path / "data" / "causal_proof_candidates" / "test_v1"
    local_report = _write_local_report(tmp_path)
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())

    report = gate.evaluate_plan(
        repo_root=paths["repo_root"],
        data_manifest_path=paths["data_manifest_path"],
        canonical_root=paths["canonical_root"],
        reports_root=paths["reports_root"],
        phase2_manifest_path=paths["phase2_manifest_path"],
        phase2_validation_path=paths["phase2_validation_path"],
        profile_config_path=paths["profile_config_path"],
        build_script_path=paths["build_script_path"],
        local_report_paths=[local_report],
        candidate_roots=[root],
        quarantine_root="data/causal_proof_candidates/test_v1",
        expected_count=2,
        feature_cols=["feature_return_1m"],
        git_head="current-head",
        staged_names=[],
        scoped_status_lines=[],
        generated_at_utc="2026-06-30T00:00:00Z",
    )
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())

    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert before == after
    assert not quarantine_root.exists()
    assert report["summary"]["data_mutation_performed"] is False
    assert report["summary"]["reports_refreshed"] is False
