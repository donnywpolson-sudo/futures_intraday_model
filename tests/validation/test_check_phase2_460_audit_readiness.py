from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import check_phase2_460_audit_readiness as gate


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
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
    canonical_pattern: str = gate.TARGET_CANONICAL_PATTERN,
    local_trade_gate_status: str = "NOT_RUN",
) -> dict[str, Path]:
    pairs = pairs or [("ES", 2020), ("CL", 2021)]
    data_manifest_path = tmp_path / "configs" / "data_manifest.yaml"
    canonical_root = tmp_path / gate.CANONICAL_ROOT_REL
    reports_root = tmp_path / gate.REPORTS_ROOT_REL
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    build_script = tmp_path / "scripts" / "phase2_causal_base" / "build_causal_base_data.py"
    _write_text(
        data_manifest_path,
        "\n".join(["canonical_paths:", f"  causal_parquet_pattern: {canonical_pattern}"]),
    )
    _write_text(profile_config, "default_profile: tier_3_research\n")
    _write_text(build_script, "print('builder')\n")
    _touch_candidates(canonical_root, pairs)
    _write_json(
        reports_root / "causal_base_manifest.json",
        {
            "status": "PASS",
            "generated_at": "2026-06-30T00:00:00Z",
            "git_commit": "current-head",
            "script_path": "scripts/phase2_causal_base/build_causal_base_data.py",
            "script_hash": gate.sha256_file(build_script),
            "config_hash": gate.sha256_file(profile_config),
            "output_root": gate.CANONICAL_ROOT_REL,
            "reports_root": gate.REPORTS_ROOT_REL,
            "requested_market_years": [{"market": market, "year": year} for market, year in pairs],
            "outputs": [{"market": market, "year": year} for market, year in pairs],
        },
    )
    _write_json(
        reports_root / "causal_base_validation.json",
        {
            "status": "PASS",
            "files": [{"market": market, "year": year} for market, year in pairs],
            "summary": {
                "file_count": len(pairs),
                "pass_count": len(pairs),
                "fail_count": 0,
                "local_trade_ohlcv_gap_gate_status": local_trade_gate_status,
            },
        },
    )
    return {
        "repo_root": tmp_path,
        "data_manifest_path": data_manifest_path,
        "canonical_root": canonical_root,
        "reports_root": reports_root,
        "phase2_manifest_path": reports_root / "causal_base_manifest.json",
        "phase2_validation_path": reports_root / "causal_base_validation.json",
        "profile_config_path": profile_config,
        "build_script_path": build_script,
    }


def _evaluate(
    paths: dict[str, Path],
    *,
    expected_count: int = 2,
    feature_cols: list[str] | None = None,
    staged_names: list[str] | None = None,
    scoped_status_lines: list[str] | None = None,
):
    return gate.evaluate_readiness(
        repo_root=paths["repo_root"],
        data_manifest_path=paths["data_manifest_path"],
        canonical_root=paths["canonical_root"],
        reports_root=paths["reports_root"],
        phase2_manifest_path=paths["phase2_manifest_path"],
        phase2_validation_path=paths["phase2_validation_path"],
        profile_config_path=paths["profile_config_path"],
        build_script_path=paths["build_script_path"],
        expected_count=expected_count,
        feature_cols=feature_cols or ["feature_return_1m", "feature_volume_z"],
        git_head="current-head",
        staged_names=staged_names or [],
        scoped_status_lines=scoped_status_lines or [],
        generated_at_utc="2026-06-30T00:00:00Z",
    )


def test_passes_approved_460_scope_with_known_warnings(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path))

    assert report["summary"]["status"] == gate.STATUS_GO
    assert report["summary"]["failure_count"] == 0
    warning_names = {warning["name"] for warning in report["warnings"]}
    assert "local_trade_ohlcv_gap_gate" in warning_names
    assert "optional_metadata_pit_approval" in warning_names


def test_passes_without_local_trade_warning_when_gate_passes(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path, local_trade_gate_status="PASS"))

    assert report["summary"]["status"] == gate.STATUS_GO
    warning_names = {warning["name"] for warning in report["warnings"]}
    assert "local_trade_ohlcv_gap_gate" not in warning_names
    assert "optional_metadata_pit_approval" in warning_names


def test_fails_wrong_canonical_config_pattern(tmp_path: Path) -> None:
    report = _evaluate(
        _fixture(
            tmp_path,
            canonical_pattern="data/causal_base_candidates/tier1_rebuild_v1/{market}/{year}.parquet",
        )
    )

    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert "canonical_config_pattern" in failed_names


def test_fails_wrong_parquet_count(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path), expected_count=3)

    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert "canonical_parquet_count" in failed_names


def test_fails_forbidden_scope_rows(tmp_path: Path) -> None:
    paths = _fixture(tmp_path, pairs=[("ES", 2020), ("6M", 2012), ("CL", 2025)])
    report = _evaluate(paths, expected_count=3)

    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert "forbidden_6m_2012_absent" in failed_names
    assert "forbidden_2025_absent" in failed_names
    assert "canonical_year_range" in failed_names


def test_fails_filesystem_manifest_scope_mismatch(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    _write_json(
        paths["phase2_manifest_path"],
        {
            "status": "PASS",
            "generated_at": "2026-06-30T00:00:00Z",
            "git_commit": "current-head",
            "script_hash": gate.sha256_file(paths["build_script_path"]),
            "config_hash": gate.sha256_file(paths["profile_config_path"]),
            "output_root": gate.CANONICAL_ROOT_REL,
            "reports_root": gate.REPORTS_ROOT_REL,
            "requested_market_years": [{"market": "ES", "year": 2020}, {"market": "NQ", "year": 2021}],
            "outputs": [{"market": "ES", "year": 2020}, {"market": "NQ", "year": 2021}],
        },
    )

    report = _evaluate(paths)

    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert "filesystem_matches_manifest_scope" in failed_names


def test_fails_staged_or_artifact_status_lines(tmp_path: Path) -> None:
    report = _evaluate(
        _fixture(tmp_path),
        staged_names=["configs/data_manifest.yaml"],
        scoped_status_lines=[" M reports/data_manifest/master_data_health_summary.md"],
    )

    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert "nothing_staged" in failed_names
    assert "artifact_config_status_clean" in failed_names


def test_fails_feature_denylist_violation(tmp_path: Path) -> None:
    report = _evaluate(_fixture(tmp_path), feature_cols=["feature_return_1m", "status_action_name"])

    failed_names = {check["name"] for check in report["checks"] if check["status"] == "FAIL"}
    assert report["summary"]["status"] == gate.STATUS_NO_GO
    assert "feature_denylist_clean" in failed_names


def test_warns_for_stale_manifest_hashes(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    manifest = json.loads(paths["phase2_manifest_path"].read_text(encoding="utf-8"))
    manifest["git_commit"] = "old-head"
    manifest["script_hash"] = "old-script"
    manifest["config_hash"] = "old-config"
    _write_json(paths["phase2_manifest_path"], manifest)

    report = _evaluate(paths)

    assert report["summary"]["status"] == gate.STATUS_GO
    warning_names = {warning["name"] for warning in report["warnings"]}
    assert "manifest_git_commit_current" in warning_names
    assert "manifest_script_hash_current" in warning_names
    assert "manifest_config_hash_current" in warning_names
