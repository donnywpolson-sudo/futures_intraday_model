from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.validation import build_holdout_forward_evidence as gate
from scripts.validation import validate_broad_causal_raw_source_readiness as raw_readiness


MARKETS = [f"M{i:02d}" for i in range(33)]


def _write_config(
    path: Path,
    *,
    holdout_markets: list[str] | None = None,
    forward_markets: list[str] | None = None,
    holdout_years: list[int] | None = None,
    forward_years: list[int] | None = None,
    holdout_forbid_research_use: bool = True,
    forward_forbid_research_use: bool = True,
) -> None:
    payload = {
        "profiles": {
            "tier_3_holdout": {
                "markets": holdout_markets or MARKETS,
                "years": holdout_years or [2025],
                "forbid_research_use": holdout_forbid_research_use,
            },
            "tier_3_forward": {
                "markets": forward_markets or MARKETS,
                "years": forward_years or [2026],
                "forbid_research_use": forward_forbid_research_use,
            },
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _ready_raw(**kwargs: object) -> dict[str, object]:
    row = kwargs["row"]
    assert isinstance(row, dict)
    return {
        "market": row["market"],
        "year": row["year"],
        "pair": row["pair"],
        "readiness_status": raw_readiness.READY_STATUS,
        "blockers": [],
    }


def _passing_phase2(**kwargs: object) -> dict[str, object]:
    return {
        "phase2_status": "PASS",
        "raw_rows": 10,
        "output_rows": 10,
        "warnings": [],
        "failures": [],
        "diagnostic_warnings": [],
    }


def test_build_evidence_classifies_33_holdout_and_33_forward_rows(tmp_path: Path) -> None:
    config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_config(config)

    report = gate.build_evidence(
        repo_root=tmp_path,
        alpha_config_path=config,
        input_root=tmp_path / "data" / "raw",
        output_root=tmp_path / "data" / "causally_gated_normalized",
        generated_at_utc="2026-06-30T00:00:00Z",
        raw_inspector=_ready_raw,
        phase2_inspector=_passing_phase2,
    )

    assert report["summary"]["status"] == "PASS"
    assert report["summary"]["holdout_count"] == 33
    assert report["summary"]["forward_count"] == 33
    assert report["summary"]["blocked_count"] == 0
    assert report["summary"]["not_checked_count"] == 0
    for flag in (
        "data_mutation_performed",
        "parquet_output_written",
        "build_approved",
        "research_use_allowed",
        "modeling_approved",
        "wfa_approved",
        "metrics_approved",
        "predictions_approved",
        "promotion_approved",
        "config_promotion_approved",
    ):
        assert report["summary"][flag] is False

    forward_rows = [row for row in report["rows"] if row["bucket"] == gate.FORWARD_CANDIDATE]
    assert len(forward_rows) == 33
    assert all("partial/current-year forward caveat" in row["reasons"] for row in forward_rows)
    assert all(row["research_use_allowed"] is False for row in report["rows"])


def test_rejects_profile_without_research_use_lock(tmp_path: Path) -> None:
    config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_config(config, holdout_forbid_research_use=False)

    with pytest.raises(ValueError, match="forbid_research_use"):
        gate.build_evidence(
            repo_root=tmp_path,
            alpha_config_path=config,
            input_root=tmp_path / "data" / "raw",
            output_root=tmp_path / "data" / "causally_gated_normalized",
            raw_inspector=_ready_raw,
            phase2_inspector=_passing_phase2,
        )


def test_rejects_wrong_holdout_year(tmp_path: Path) -> None:
    config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_config(config, holdout_years=[2024])

    with pytest.raises(ValueError, match="expected \\[2025\\]"):
        gate.build_evidence(
            repo_root=tmp_path,
            alpha_config_path=config,
            input_root=tmp_path / "data" / "raw",
            output_root=tmp_path / "data" / "causally_gated_normalized",
            raw_inspector=_ready_raw,
            phase2_inspector=_passing_phase2,
        )


def test_rejects_duplicate_markets(tmp_path: Path) -> None:
    config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_config(config, holdout_markets=[*MARKETS[:-1], MARKETS[-2]])

    with pytest.raises(ValueError, match="duplicate markets"):
        gate.build_evidence(
            repo_root=tmp_path,
            alpha_config_path=config,
            input_root=tmp_path / "data" / "raw",
            output_root=tmp_path / "data" / "causally_gated_normalized",
            raw_inspector=_ready_raw,
            phase2_inspector=_passing_phase2,
        )


def test_rejects_non_66_scope(tmp_path: Path) -> None:
    config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_config(config, holdout_markets=MARKETS[:-1])

    with pytest.raises(ValueError, match="market_count=32"):
        gate.build_evidence(
            repo_root=tmp_path,
            alpha_config_path=config,
            input_root=tmp_path / "data" / "raw",
            output_root=tmp_path / "data" / "causally_gated_normalized",
            raw_inspector=_ready_raw,
            phase2_inspector=_passing_phase2,
        )


def test_rejects_existing_holdout_or_forward_candidate_outputs(tmp_path: Path) -> None:
    config = tmp_path / "configs" / "alpha_tiered.yaml"
    output_root = tmp_path / "data" / "causally_gated_normalized"
    existing = output_root / MARKETS[0] / "2025.parquet"
    _write_config(config)
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("not a parquet file", encoding="utf-8")

    with pytest.raises(ValueError, match="existing 2025/2026 candidate outputs"):
        gate.build_evidence(
            repo_root=tmp_path,
            alpha_config_path=config,
            input_root=tmp_path / "data" / "raw",
            output_root=output_root,
            raw_inspector=_ready_raw,
            phase2_inspector=_passing_phase2,
        )


def test_scope_validation_rejects_6m_2012() -> None:
    with pytest.raises(ValueError, match="6M:2012"):
        gate.validate_scope_rows(
            [{"pair": "6M:2012", "market": "6M", "year": 2012}],
            max_rows=1,
        )
