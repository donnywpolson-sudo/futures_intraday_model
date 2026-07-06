from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import evaluate_phase2_canonical_promotion_gate as gate


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _touch_candidates(root: Path, pairs: list[tuple[str, int]]) -> None:
    for market, year in pairs:
        path = root / market / f"{year}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder", encoding="utf-8")


def _fixture(
    tmp_path: Path,
    *,
    pairs: list[tuple[str, int]] | None = None,
    promoted_config: bool = False,
) -> dict[str, Path]:
    pairs = pairs or [("ES", 2020), ("CL", 2021)]
    causal_pattern = (
        gate.TARGET_CANONICAL_PATTERN
        if promoted_config
        else "data/archive/tier1_rebuild_v1/{market}/{year}.parquet"
    )
    manifest_path = tmp_path / "configs" / "data_manifest.yaml"
    candidate_root = tmp_path / "data" / "causally_gated_normalized"
    reports_root = (
        tmp_path
        / "reports"
        / "data_audit"
        / "causal_base_rebuild"
        / "broad_manifest_527_rebuild_v1"
    )
    matrix_path = tmp_path / "reports" / "data_manifest" / "master_data_health_matrix.json"
    _write_yaml(
        manifest_path,
        "\n".join(
            [
                "canonical_paths:",
                f"  causal_parquet_pattern: {causal_pattern}",
            ]
        ),
    )
    _touch_candidates(candidate_root, pairs)
    _write_json(
        reports_root / "causal_base_manifest.json",
        {
            "status": "PASS",
            "output_root": "data/causally_gated_normalized",
            "outputs": [{"market": market, "year": year} for market, year in pairs],
        },
    )
    _write_json(
        reports_root / "causal_base_validation.json",
        {
            "status": "PASS",
            "output_root": "data/causally_gated_normalized",
            "files": [{"market": market, "year": year} for market, year in pairs],
        },
    )
    _write_json(
        matrix_path,
        {
            "summary": {
                "expected_rows": 527,
                "current_canonical_causal": {
                    "pattern": "data/causally_gated_normalized/{market}/{year}.parquet",
                    "present_count": 8,
                    "missing_count": 519,
                },
            }
        },
    )
    return {
        "repo_root": tmp_path,
        "manifest_path": manifest_path,
        "candidate_root": candidate_root,
        "reports_root": reports_root,
        "candidate_manifest_path": reports_root / "causal_base_manifest.json",
        "candidate_validation_path": reports_root / "causal_base_validation.json",
        "master_matrix_path": matrix_path,
    }


def _evaluate(paths: dict[str, Path], *, expected_count: int = 2, git_status_lines: list[str] | None = None):
    return gate.evaluate_gate(
        repo_root=paths["repo_root"],
        manifest_path=paths["manifest_path"],
        candidate_root=paths["candidate_root"],
        reports_root=paths["reports_root"],
        candidate_manifest_path=paths["candidate_manifest_path"],
        candidate_validation_path=paths["candidate_validation_path"],
        master_matrix_path=paths["master_matrix_path"],
        expected_candidate_count=expected_count,
        git_status_lines=git_status_lines or [],
        generated_at_utc="2026-06-30T00:00:00Z",
    )


def test_pass_candidate_with_unpromoted_config(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path))

    assert report["summary"]["status"] == gate.CONDITIONAL_GO
    assert report["summary"]["candidate_parquet_count"] == 2
    assert report["summary"]["candidate_manifest_status"] == "PASS"
    assert report["summary"]["candidate_validation_status"] == "PASS"
    assert report["summary"]["config_mutation_performed"] is False
    assert report["summary"]["modeling_approved"] is False


def test_pass_promoted_config_after_candidate_checks(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path, promoted_config=True))

    assert report["summary"]["status"] == gate.PROMOTED_GO
    assert report["summary"]["decision"] == "canonical_config_promoted_candidate_460_confirmed"
    assert report["summary"]["canonical_config_promoted"] is True
    assert report["summary"]["config_mutation_performed"] is False
    assert report["summary"]["promotion_performed"] is False


def test_fails_wrong_parquet_count(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path), expected_count=3)

    assert report["summary"]["status"] == gate.NO_GO
    assert any(check["name"] == "candidate_parquet_count" for check in report["checks"] if check["status"] == "FAIL")


def test_fails_non_pass_manifest_or_validation(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _write_json(paths["candidate_manifest_path"], {"status": "FAIL", "outputs": [{}, {}]})
    _write_json(paths["candidate_validation_path"], {"status": "FAIL", "files": [{}, {}]})

    report = _evaluate(paths)

    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert report["summary"]["status"] == gate.NO_GO
    assert {"manifest_status", "validation_status"} <= failed_names


def test_fails_forbidden_outputs(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path, pairs=[("ES", 2020), ("6M", 2012), ("CL", 2025)]), expected_count=3)

    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert report["summary"]["status"] == gate.NO_GO
    assert "forbidden_6m_2012_absent" in failed_names
    assert "forbidden_2025_absent" in failed_names


def test_fails_missing_candidate_roots(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    missing_root = tmp_path / "missing" / "candidate"

    report = gate.evaluate_gate(
        repo_root=paths["repo_root"],
        manifest_path=paths["manifest_path"],
        candidate_root=missing_root,
        reports_root=tmp_path / "missing" / "reports",
        candidate_manifest_path=paths["candidate_manifest_path"],
        candidate_validation_path=paths["candidate_validation_path"],
        master_matrix_path=paths["master_matrix_path"],
        expected_candidate_count=2,
        git_status_lines=[],
        generated_at_utc="2026-06-30T00:00:00Z",
    )

    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert report["summary"]["status"] == gate.NO_GO
    assert {"candidate_root_exists", "reports_root_exists", "candidate_parquet_count"} <= failed_names


def test_fails_dirty_status_lines(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path), git_status_lines=[" M configs/data_manifest.yaml"])

    assert report["summary"]["status"] == gate.NO_GO
    assert any(check["name"] == "candidate_paths_git_clean" for check in report["checks"] if check["status"] == "FAIL")
