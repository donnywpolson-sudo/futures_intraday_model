from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation.data_audit_universe_guard import load_data_audit_universe


def _write_universe(path: Path, rows: list[dict[str, object]], *, status: str = "PASS") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for row in rows:
        audit_status = str(row["audit_status"])
        counts[audit_status] = counts.get(audit_status, 0) + 1
    path.write_text(
        json.dumps(
            {
                "status": status,
                "summary": {"audit_status_counts": counts},
                "market_years": rows,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_guard_allows_usable_market_year(tmp_path: Path) -> None:
    path = _write_universe(
        tmp_path / "universe.json",
        [{"market": "ES", "year": 2024, "audit_status": "usable", "reason": "ok"}],
    )

    universe = load_data_audit_universe(path)

    assert universe.require_usable("ES", 2024, context="test") is None
    assert universe.evidence()["status_counts"] == {"usable": 1}


@pytest.mark.parametrize("status", ["quarantined", "diagnostic_only"])
def test_guard_blocks_non_usable_market_year(tmp_path: Path, status: str) -> None:
    path = _write_universe(
        tmp_path / "universe.json",
        [{"market": "ES", "year": 2024, "audit_status": status, "reason": "blocked"}],
    )

    universe = load_data_audit_universe(path)
    failure = universe.require_usable("ES", 2024, context="test")

    assert failure is not None
    assert f"audit_status={status!r}" in failure


def test_guard_blocks_false_usable_for_wfa(tmp_path: Path) -> None:
    path = _write_universe(
        tmp_path / "universe.json",
        [
            {
                "market": "ES",
                "year": 2024,
                "audit_status": "usable",
                "usable_for_wfa": False,
                "reason": "diagnostic only",
            }
        ],
    )

    universe = load_data_audit_universe(path)
    failure = universe.require_usable("ES", 2024, context="test")

    assert failure is not None
    assert "usable_for_wfa=False" in failure


def test_guard_blocks_legacy_quarantined_final_decision_marked_usable(tmp_path: Path) -> None:
    path = _write_universe(
        tmp_path / "universe.json",
        [
            {
                "market": "ES",
                "year": 2024,
                "audit_status": "usable",
                "final_decision": "keep_quarantined_ohlcv_only_evidence_insufficient",
                "reason": "legacy caveat",
            }
        ],
    )

    universe = load_data_audit_universe(path)
    failure = universe.require_usable("ES", 2024, context="test")

    assert failure is not None
    assert "final_decision='keep_quarantined_ohlcv_only_evidence_insufficient'" in failure


@pytest.mark.parametrize(
    "final_decision",
    [
        "acceptable_with_caveat_ohlcv_empty_minutes_assumed",
        "accept_with_caveat_ohlcv_empty_minutes_assumed",
    ],
)
def test_guard_allows_caveat_final_decision_marked_wfa_usable(
    tmp_path: Path,
    final_decision: str,
) -> None:
    path = _write_universe(
        tmp_path / "universe.json",
        [
            {
                "market": "ES",
                "year": 2024,
                "audit_status": "usable",
                "usable_for_wfa": True,
                "final_decision": final_decision,
                "reason": "assumption-only no-trade convention",
            }
        ],
    )

    universe = load_data_audit_universe(path)

    assert universe.require_usable("ES", 2024, context="test") is None


def test_guard_blocks_caveat_final_decision_without_explicit_wfa_usable(
    tmp_path: Path,
) -> None:
    path = _write_universe(
        tmp_path / "universe.json",
        [
            {
                "market": "ES",
                "year": 2024,
                "audit_status": "usable",
                "final_decision": "acceptable_with_caveat_ohlcv_empty_minutes_assumed",
                "reason": "assumption-only no-trade convention",
            }
        ],
    )

    universe = load_data_audit_universe(path)
    failure = universe.require_usable("ES", 2024, context="test")

    assert failure is not None
    assert "usable_for_wfa must be true" in failure


def test_guard_blocks_caveat_final_decision_marked_diagnostic_only(
    tmp_path: Path,
) -> None:
    path = _write_universe(
        tmp_path / "universe.json",
        [
            {
                "market": "ES",
                "year": 2024,
                "audit_status": "diagnostic_only",
                "usable_for_wfa": True,
                "final_decision": "acceptable_with_caveat_ohlcv_empty_minutes_assumed",
                "reason": "assumption-only no-trade convention",
            }
        ],
    )

    universe = load_data_audit_universe(path)
    failure = universe.require_usable("ES", 2024, context="test")

    assert failure is not None
    assert "audit_status='diagnostic_only'" in failure


def test_guard_blocks_missing_market_year(tmp_path: Path) -> None:
    path = _write_universe(
        tmp_path / "universe.json",
        [{"market": "ES", "year": 2024, "audit_status": "usable", "reason": "ok"}],
    )

    universe = load_data_audit_universe(path)
    failure = universe.require_usable("ES", 2023, context="test")

    assert failure == "test: missing data-audit universe decision for ES 2023"


def test_guard_fails_closed_when_universe_status_is_not_pass(tmp_path: Path) -> None:
    path = _write_universe(
        tmp_path / "universe.json",
        [{"market": "ES", "year": 2024, "audit_status": "usable", "reason": "ok"}],
        status="FAIL",
    )

    with pytest.raises(SystemExit, match="status is not PASS"):
        load_data_audit_universe(path)
