from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.validation import plan_broad_causal_rebuild as plan


REPO_ROOT = Path(__file__).resolve().parents[2]


def _policy_text() -> str:
    return "\n".join(
        [
            "Human policy decision: `rebuild_new_broad_root`.",
            "data/causally_gated_normalized",
            "data/causally_gated_normalized/{market}/{year}.parquet",
            "legacy roots are evidence only",
            "does not approve broader modeling",
        ]
    )


def _manifest() -> dict[str, object]:
    return {
        "canonical_paths": {
            "raw_parquet_pattern": "data/raw/{market}/{year}.parquet",
            "causal_parquet_pattern": "data/causally_gated_normalized/{market}/{year}.parquet",
        },
        "expected_markets": ["ES", "KE"],
        "expected_years": {
            "default_start_year": 2024,
            "end_year": 2026,
            "market_start_year_overrides": {"KE": 2025},
        },
    }


def test_repo_manifest_expands_to_exact_527_rows_with_overrides() -> None:
    manifest = plan.read_yaml(REPO_ROOT / "configs" / "data_manifest.yaml")

    pairs = plan.expected_pairs(manifest)
    first_year_by_market = {}
    for pair in pairs:
        first_year_by_market.setdefault(pair.market, pair.year)

    assert len(pairs) == 527
    assert first_year_by_market["ES"] == 2010
    assert first_year_by_market["KE"] == 2013
    assert first_year_by_market["RTY"] == 2017
    assert first_year_by_market["SR1"] == 2018
    assert first_year_by_market["SR3"] == 2018
    assert first_year_by_market["TN"] == 2016
    assert first_year_by_market["ZL"] == 2011
    assert first_year_by_market["ZM"] == 2011
    assert pairs[-1].text() == "HE:2026"


def test_build_plan_writes_paths_statuses_required_fields_and_non_approval(tmp_path: Path) -> None:
    manifest_path = tmp_path / "configs" / "data_manifest.yaml"
    policy_path = tmp_path / "reports" / "policy.md"
    manifest_path.parent.mkdir(parents=True)
    policy_path.parent.mkdir(parents=True)
    manifest_path.write_text(yaml.safe_dump(_manifest()), encoding="utf-8")
    policy_path.write_text(_policy_text(), encoding="utf-8")

    output = plan.build_plan(
        repo_root=tmp_path,
        manifest_path=manifest_path,
        policy_path=policy_path,
        generated_at_utc="2026-06-29T00:00:00Z",
        expected_row_count=5,
    )
    rows = {row["pair"]: row for row in output["rows"]}

    assert output["summary"]["expected_rows"] == 5
    assert output["summary"]["future_root"] == plan.FUTURE_ROOT
    assert output["summary"]["status_counts"] == {
        "ready_for_build": 0,
        "deferred_policy_review": 4,
        "excluded_from_phase2": 0,
        "action_required": 1,
    }
    assert rows["ES:2024"]["planned_input_raw_path"] == "data/raw/ES/2024.parquet"
    assert rows["ES:2024"]["planned_output_causal_path"] == (
        "data/causally_gated_normalized/ES/2024.parquet"
    )
    assert rows["ES:2024"]["prebuild_status"] == "action_required"
    assert rows["ES:2025"]["non_research_until_separately_approved"] is True
    assert rows["KE:2025"]["prebuild_status"] == "deferred_policy_review"
    assert "config_hash" in output["required_root_manifest_fields"]
    assert "output_causal_row_count" in output["required_per_row_manifest_fields"]
    assert "does not approve broader modeling" in output["summary"]["non_approval"]
    assert output["summary"]["config_promotion_approved"] is False


def test_write_plan_outputs_json_and_markdown_with_required_text(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    policy_path = tmp_path / "policy.md"
    json_out = tmp_path / "out" / "plan.json"
    md_out = tmp_path / "out" / "plan.md"
    manifest_path.write_text(yaml.safe_dump(_manifest()), encoding="utf-8")
    policy_path.write_text(_policy_text(), encoding="utf-8")
    output = plan.build_plan(
        repo_root=tmp_path,
        manifest_path=manifest_path,
        policy_path=policy_path,
        generated_at_utc="2026-06-29T00:00:00Z",
        expected_row_count=5,
    )

    plan.write_plan(output, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["expected_rows"] == 5
    assert "data/causally_gated_normalized" in markdown
    assert "does not approve broader modeling" in markdown
    assert "config promotion" in markdown


def test_policy_validation_fails_closed_when_decision_is_missing(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    policy_path = tmp_path / "policy.md"
    manifest_path.write_text(yaml.safe_dump(_manifest()), encoding="utf-8")
    policy_path.write_text("legacy roots are evidence only", encoding="utf-8")

    with pytest.raises(ValueError, match="policy artifact missing required text"):
        plan.build_plan(
            repo_root=tmp_path,
            manifest_path=manifest_path,
            policy_path=policy_path,
            expected_row_count=5,
        )
