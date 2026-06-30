from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.validation import audit_tier_research_ladder as audit
from scripts.validation import validate_broad_causal_raw_source_readiness as raw_readiness


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _alpha_config() -> dict[str, object]:
    return {
        "profiles": {
            "tier_1_research": {"years": [2023, 2024], "markets": ["ES"]},
            "tier_1_holdout": {
                "years": [2025],
                "markets": ["ES"],
                "forbid_research_use": True,
            },
            "tier_1_forward": {
                "years": [2026],
                "markets": ["ES"],
                "forbid_research_use": True,
            },
            "tier_2_research": {"years": [2018, 2019, 2020, 2021, 2022, 2023, 2024], "markets": ["ES"]},
            "tier_2_holdout": {
                "years": [2025],
                "markets": ["ES"],
                "forbid_research_use": True,
            },
            "tier_2_forward": {
                "years": [2026],
                "markets": ["ES"],
                "forbid_research_use": True,
            },
            "tier_3_research": {"years": [2010, 2011, 2012, 2023, 2024], "markets": ["ES", "6M"]},
            "tier_3_holdout": {
                "years": [2025],
                "markets": ["ES"],
                "forbid_research_use": True,
            },
            "tier_3_forward": {
                "years": [2026],
                "markets": ["ES"],
                "forbid_research_use": True,
            },
        }
    }


def _prebuild_rows() -> list[dict[str, object]]:
    return [
        _row("ES", 2024, "action_required"),
        _row("6M", 2012, "action_required"),
        _row("ES", 2025, "deferred_policy_review"),
        _row("ES", 2026, "deferred_policy_review"),
    ]


def _row(market: str, year: int, status: str) -> dict[str, object]:
    return {
        "market": market,
        "year": year,
        "pair": f"{market}:{year}",
        "planned_input_raw_path": f"data/raw/{market}/{year}.parquet",
        "planned_output_causal_path": (
            f"data/causal_base_candidates/broad_manifest_527_rebuild_v1/{market}/{year}.parquet"
        ),
        "prebuild_status": status,
    }


def _raw_report() -> dict[str, object]:
    return {
        "rows": [
            {
                "market": "ES",
                "year": 2024,
                "pair": "ES:2024",
                "readiness_status": raw_readiness.READY_STATUS,
                "blockers": [],
            },
            {
                "market": "6M",
                "year": 2012,
                "pair": "6M:2012",
                "readiness_status": raw_readiness.READY_STATUS,
                "blockers": [],
            },
        ]
    }


def _fake_raw_inspector(**kwargs: object) -> dict[str, object]:
    row = kwargs["row"]
    assert isinstance(row, dict)
    return {
        "market": row["market"],
        "year": row["year"],
        "pair": row["pair"],
        "readiness_status": raw_readiness.READY_STATUS,
        "blockers": [],
        "raw_read_performed": True,
    }


def _fake_phase2_inspector(**kwargs: object) -> dict[str, object]:
    row = kwargs["row"]
    assert isinstance(row, dict)
    return {
        "phase2_status": "PASS",
        "raw_rows": 10,
        "output_rows": 10,
        "warnings": [],
        "failures": [],
    }


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "alpha": tmp_path / "configs" / "alpha_tiered.yaml",
        "manifest": tmp_path / "configs" / "data_manifest.yaml",
        "prebuild": tmp_path / "reports" / "prebuild.json",
        "raw": tmp_path / "reports" / "raw.json",
        "include": tmp_path / "reports" / "include.json",
        "readiness": tmp_path / "reports" / "readiness.json",
        "output_root": tmp_path / "data" / "causal_base_candidates" / "broad_manifest_527_rebuild_v1",
    }
    _write_yaml(paths["alpha"], _alpha_config())
    _write_yaml(paths["manifest"], {"source_profile": "configs/alpha_tiered.yaml::profiles.tier_3_research"})
    _write_json(paths["prebuild"], {"rows": _prebuild_rows()})
    _write_json(paths["raw"], _raw_report())
    _write_json(paths["include"], {"market_years": [{"market": "ES", "year": 2024}]})
    _write_json(
        paths["readiness"],
        {
            "status": "PASS",
            "selected_market_year_count": 1,
            "checked_market_year_count": 1,
        },
    )
    return paths


def test_build_audit_buckets_research_holdout_forward_and_blocked(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    report = audit.build_audit(
        repo_root=tmp_path,
        alpha_config_path=paths["alpha"],
        data_manifest_path=paths["manifest"],
        prebuild_plan_path=paths["prebuild"],
        raw_readiness_path=paths["raw"],
        final_include_path=paths["include"],
        final_readiness_path=paths["readiness"],
        output_root=paths["output_root"],
        generated_at_utc="2026-06-30T00:00:00Z",
        raw_inspector=_fake_raw_inspector,
        phase2_inspector=_fake_phase2_inspector,
    )
    rows = {row["pair"]: row for row in report["rows"]}

    assert report["summary"]["bucket_counts"] == {
        audit.RESEARCH_VALID: 1,
        audit.LOCKED_HOLDOUT_CANDIDATE: 1,
        audit.FORWARD_CANDIDATE: 1,
        audit.BLOCKED: 1,
        audit.NOT_CHECKED: 0,
    }
    assert rows["ES:2024"]["research_use_allowed"] is True
    assert rows["ES:2025"]["holdout_use_only"] is True
    assert rows["ES:2026"]["forward_use_only"] is True
    assert "partial/current-year" in rows["ES:2026"]["reasons"][0]
    assert rows["6M:2012"]["bucket"] == audit.BLOCKED
    assert report["summary"]["research_use_allowed_for_holdout_forward"] is False


def test_build_audit_keeps_deferred_not_checked_when_phase2_skipped(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    report = audit.build_audit(
        repo_root=tmp_path,
        alpha_config_path=paths["alpha"],
        data_manifest_path=paths["manifest"],
        prebuild_plan_path=paths["prebuild"],
        raw_readiness_path=paths["raw"],
        final_include_path=paths["include"],
        final_readiness_path=paths["readiness"],
        output_root=paths["output_root"],
        inspect_deferred_phase2=False,
        raw_inspector=_fake_raw_inspector,
    )

    assert report["summary"]["bucket_counts"][audit.NOT_CHECKED] == 2
    assert report["summary"]["deferred_phase2_checked"] == 0


def test_write_report_outputs_json_and_markdown(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    report = audit.build_audit(
        repo_root=tmp_path,
        alpha_config_path=paths["alpha"],
        data_manifest_path=paths["manifest"],
        prebuild_plan_path=paths["prebuild"],
        raw_readiness_path=paths["raw"],
        final_include_path=paths["include"],
        final_readiness_path=paths["readiness"],
        output_root=paths["output_root"],
        raw_inspector=_fake_raw_inspector,
        phase2_inspector=_fake_phase2_inspector,
    )
    json_out = tmp_path / "out" / "audit.json"
    md_out = tmp_path / "out" / "audit.md"

    audit.write_report(report, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["stage"] == "tier_research_ladder_adversarial_audit"
    assert "2025 holdout rows must not influence" in markdown
    assert "does not approve config promotion" in markdown
