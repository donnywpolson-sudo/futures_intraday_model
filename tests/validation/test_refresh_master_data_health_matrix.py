from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.validation import refresh_master_data_health_matrix as refresh


def _manifest() -> dict[str, object]:
    return {
        "canonical_paths": {
            "causal_parquet_pattern": "data/causally_gated_normalized/{market}/{year}.parquet"
        },
        "expected_markets": ["ES", "KE"],
        "expected_years": {
            "default_start_year": 2020,
            "end_year": 2021,
            "market_start_year_overrides": {"KE": 2021},
        },
    }


def test_expected_pairs_order_and_current_causal_detection(tmp_path: Path) -> None:
    pairs = refresh.expected_pairs(_manifest())
    (tmp_path / "data" / "causally_gated_normalized" / "ES").mkdir(parents=True)
    (tmp_path / "data" / "causally_gated_normalized" / "ES" / "2020.parquet").write_text("x", encoding="utf-8")
    present = refresh.current_causal_pairs(
        tmp_path,
        "data/causally_gated_normalized/{market}/{year}.parquet",
        pairs,
    )

    assert [pair.text() for pair in pairs] == ["ES:2020", "ES:2021", "KE:2021"]
    assert [pair.text() for pair in sorted(present)] == ["ES:2020"]


def test_parse_handoff_scope_expands_ranges() -> None:
    text = """
## Older Section

## Latest Global Phase 1-2 Completion Reconciliation Result

- Verified campaign rows:
  - `canonical_phase2_pass`: 2 rows (`SR1 2020`, `SR3 2020`)
  - `fail_closed_with_decision_packet`: 4 rows (`ZC 2019-2021`, `ZW 2024`)
  - `unresolved`: 0 rows

## Remaining Blockers
"""
    scope = refresh.parse_handoff_scope(text)

    assert [pair.text() for pair in scope["canonical_phase2_pass"]] == ["SR1:2020", "SR3:2020"]
    assert [pair.text() for pair in scope["fail_closed_with_decision_packet"]] == [
        "ZC:2019",
        "ZC:2020",
        "ZC:2021",
        "ZW:2024",
    ]
    assert scope["unresolved"] == []


def test_refresh_updates_stale_causal_count(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    matrix_path = tmp_path / "reports" / "data_manifest" / "master_data_health_matrix.json"
    summary_path = tmp_path / "reports" / "data_manifest" / "master_data_health_summary.md"
    raw_audit_path = tmp_path / "reports" / "raw_readiness" / "raw_enriched_optional_schema_audit.json"
    phase2_plan_path = tmp_path / "reports" / "phase_restart" / "batch_phase2_build_exclusion_plan.json"
    handoff_path = tmp_path / "CODEX_HANDOFF.md"
    causal_dir = tmp_path / "data" / "causally_gated_normalized" / "ES"
    causal_dir.mkdir(parents=True)
    (causal_dir / "2020.parquet").write_text("x", encoding="utf-8")
    matrix_path.parent.mkdir(parents=True)
    raw_audit_path.parent.mkdir(parents=True)
    phase2_plan_path.parent.mkdir(parents=True)
    manifest_path.write_text(yaml.safe_dump(_manifest()), encoding="utf-8")
    matrix_path.write_text(
        json.dumps(
            {
                "summary": {
                    "generated_at_utc": "old",
                    "schema_presence_counts": {"causal_parquet_present": 2},
                },
                "rows": [
                    _row("ES", 2020, causal=True, status=True),
                    _row("ES", 2021, causal=True, status=False),
                    _row("KE", 2021, causal=False, status=True),
                ],
            }
        ),
        encoding="utf-8",
    )
    raw_audit_path.write_text(
        json.dumps({"status": "PASS", "file_count": 3, "row_count": 10, "summary": {"schema_failure_count": 0}}),
        encoding="utf-8",
    )
    phase2_plan_path.write_text(
        json.dumps(
            {
                "counts": {
                    "accepted_rows_for_future_bounded_phase2_build_approval": 1,
                    "deferred_excluded_rows": 1,
                    "accepted_rows_with_pre_build_raw_evidence_prerequisite": 0,
                    "phase2_build_commands_run": 0,
                    "cleanup_commands_run": 0,
                }
            }
        ),
        encoding="utf-8",
    )
    handoff_path.write_text(
        """
## Latest Global Phase 1-2 Completion Reconciliation Result

- Verified campaign rows:
  - `canonical_phase2_pass`: 1 rows (`ES 2020`)
  - `fail_closed_with_decision_packet`: 1 rows (`KE 2021`)
  - `unresolved`: 0 rows
""",
        encoding="utf-8",
    )

    output = refresh.refresh(
        repo_root=tmp_path,
        manifest_path=manifest_path,
        matrix_path=matrix_path,
        summary_path=summary_path,
        raw_audit_path=raw_audit_path,
        phase2_plan_path=phase2_plan_path,
        handoff_path=handoff_path,
        generated_at_utc="now",
    )

    rows = {row["pair"]: row for row in output["rows"]}
    assert output["summary"]["schema_presence_counts"]["causal_parquet_present"] == 1
    assert output["summary"]["stale_causal_coverage_correction"] == {
        "prior_matrix_causal_parquet_present": 2,
        "current_canonical_causal_present": 1,
        "difference": -1,
        "prior_matrix_generated_at_utc": "old",
    }
    assert rows["ES:2020"]["causal_parquet_present"] == "True"
    assert rows["ES:2021"]["causal_parquet_present"] == "False"
    assert "Current canonical `causal_parquet_present`: 1/3" in summary_path.read_text(encoding="utf-8")


def _row(market: str, year: int, *, causal: bool, status: bool) -> dict[str, str]:
    return {
        "market": market,
        "year": str(year),
        "pair": f"{market}:{year}",
        "health_class": "OK_SOURCE_PRESENT",
        "raw_parquet_present": "True",
        "causal_parquet_present": "True" if causal else "False",
        "ohlcv_1m_dbn_present": "True",
        "definition_dbn_present": "True",
        "statistics_dbn_present": "True",
        "status_dbn_present": "True" if status else "False",
    }
