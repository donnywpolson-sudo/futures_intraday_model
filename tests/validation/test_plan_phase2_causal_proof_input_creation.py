from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.validation import plan_phase2_causal_proof_input_creation as gate
from scripts.validation import plan_phase2_causal_proof_input_path as path_gate


UNCOVERED_MARKETS = [
    "6A",
    "6B",
    "6C",
    "6J",
    "6M",
    "GC",
    "HE",
    "HG",
    "HO",
    "KE",
    "LE",
    "NG",
    "NQ",
    "RB",
    "RTY",
    "SI",
    "SR1",
    "SR3",
    "TN",
    "UB",
    "YM",
    "ZB",
    "ZC",
    "ZF",
    "ZL",
    "ZM",
    "ZS",
    "ZT",
    "ZW",
]


def _fake_path_plan(*, uncovered_markets: list[str] | None = None, status: str = path_gate.STATUS_NO_GO):
    uncovered_markets = uncovered_markets or UNCOVERED_MARKETS
    return {
        "summary": {
            "status": status,
            "uncovered_market_count": len(uncovered_markets),
            "expected_causal_file_count": len(uncovered_markets) * 2,
        },
        "uncovered_markets": uncovered_markets,
        "usable_roots": [],
    }


def _patch_path_plan(monkeypatch, payload: dict[str, Any]) -> None:
    def fake_evaluate_plan(**_kwargs):
        return payload

    monkeypatch.setattr(gate.path_gate, "evaluate_plan", fake_evaluate_plan)


def _evaluate(tmp_path: Path):
    return gate.evaluate_plan(
        repo_root=tmp_path,
        output_root=tmp_path / gate.DEFAULT_OUTPUT_ROOT,
        reports_root=tmp_path / gate.DEFAULT_REPORTS_ROOT,
        data_manifest_path=tmp_path / "configs" / "data_manifest.yaml",
        canonical_root=tmp_path / "data" / "canonical",
        phase2_reports_root=tmp_path / "reports" / "phase2",
        phase2_manifest_path=tmp_path / "reports" / "phase2" / "causal_base_manifest.json",
        phase2_validation_path=tmp_path / "reports" / "phase2" / "causal_base_validation.json",
        profile_config_path=tmp_path / "configs" / "alpha_tiered.yaml",
        build_script_path=tmp_path / "scripts" / "phase2_causal_base" / "build_causal_base_data.py",
        local_report_paths=[tmp_path / "reports" / "pipeline_audit" / "local_trade.json"],
        generated_at_utc="2026-06-30T00:00:00Z",
    )


def test_ready_plan_contains_exact_29_by_2025_2026_include_list(tmp_path: Path, monkeypatch) -> None:
    _patch_path_plan(monkeypatch, _fake_path_plan())

    report = _evaluate(tmp_path)

    assert report["summary"]["status"] == gate.STATUS_READY
    assert report["summary"]["include_row_count"] == 58
    assert report["include_list_rows"][0] == {"market": "6A", "year": 2025}
    assert report["include_list_rows"][1] == {"market": "6A", "year": 2026}
    assert report["include_list_rows"][-1] == {"market": "ZW", "year": 2026}


def test_existing_covered_markets_are_excluded_from_include_list(tmp_path: Path, monkeypatch) -> None:
    _patch_path_plan(monkeypatch, _fake_path_plan())

    report = _evaluate(tmp_path)
    markets = {row["market"] for row in report["include_list_rows"]}

    assert {"6E", "CL", "ES", "ZN"}.isdisjoint(markets)
    assert set(UNCOVERED_MARKETS) == markets


def test_generated_output_root_is_noncanonical(tmp_path: Path, monkeypatch) -> None:
    _patch_path_plan(monkeypatch, _fake_path_plan())

    report = _evaluate(tmp_path)

    assert report["summary"]["output_root"] == gate.DEFAULT_OUTPUT_ROOT
    assert "causal_base_candidates/broad_manifest_527_rebuild_v1" not in report["summary"]["output_root"]
    assert any(check["name"] == "output_root_is_quarantine_noncanonical" and check["status"] == "PASS" for check in report["checks"])


def test_command_template_excludes_broad_build_loop_files(tmp_path: Path, monkeypatch) -> None:
    _patch_path_plan(monkeypatch, _fake_path_plan())

    report = _evaluate(tmp_path)

    assert "scripts\\phase2_causal_base\\build_causal_base_data.py" in report["command_text"]
    for term in gate.EXCLUDED_RUNNER_TERMS:
        assert term not in report["command_text"]


def test_planner_does_not_write_reports_or_data(tmp_path: Path, monkeypatch) -> None:
    _patch_path_plan(monkeypatch, _fake_path_plan())
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())

    report = _evaluate(tmp_path)
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file())

    assert report["summary"]["status"] == gate.STATUS_READY
    assert before == after
    assert report["summary"]["data_mutation_performed"] is False
    assert report["summary"]["reports_refreshed"] is False


def test_existing_output_artifacts_block_plan(tmp_path: Path, monkeypatch) -> None:
    _patch_path_plan(monkeypatch, _fake_path_plan())
    output_file = tmp_path / gate.DEFAULT_OUTPUT_ROOT / "6A" / "2025.parquet"
    output_file.parent.mkdir(parents=True)
    output_file.write_text("existing artifact", encoding="utf-8")

    report = _evaluate(tmp_path)

    assert report["summary"]["status"] == gate.STATUS_BLOCKED
    assert any(check["name"] == "output_root_empty_or_absent" and check["status"] == "FAIL" for check in report["checks"])
