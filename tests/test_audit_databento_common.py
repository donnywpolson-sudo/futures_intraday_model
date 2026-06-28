from __future__ import annotations

from pathlib import Path

from scripts.audit_databento_common import (
    Blocker,
    PhaseResult,
    compare_source_manifests,
    discover_dbn_zst_files,
    gate_payload,
    parse_years,
    source_manifest_rows,
    validate_gate_payload,
)


def test_dbn_zst_discovery_and_manifest_rows(tmp_path: Path) -> None:
    root = tmp_path / "data" / "dbn"
    target = root / "ohlcv_1m" / "ES" / "2026" / "2026-01-01_2026-01-02.dbn.zst"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"fake")

    files = discover_dbn_zst_files(root)
    rows = source_manifest_rows(root)

    assert files == [target]
    assert rows[0]["path"].endswith("2026-01-01_2026-01-02.dbn.zst")
    assert rows[0]["size_bytes"] == 4


def test_source_mutation_guard_detects_metadata_change() -> None:
    before = [{"path": "data/dbn/a.dbn.zst", "size_bytes": 1, "mtime_ns": 10, "sample_hash": ""}]
    after = [{"path": "data/dbn/a.dbn.zst", "size_bytes": 2, "mtime_ns": 10, "sample_hash": ""}]

    result = compare_source_manifests(before, after)

    assert result["source_mutation_check"] == "fail"
    assert result["changed"][0]["path"] == "data/dbn/a.dbn.zst"


def test_gate_payload_validation_counts_blockers() -> None:
    phase = PhaseResult(
        phase="phase0",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        reports=["reports/data_audit/phase0_folder_triage/report.md"],
        blockers=[Blocker("Medium", "phase0", "review", "evidence")],
        source_mutation_check="pass",
        summary={},
        blockers_csv=Path("reports/data_audit/phase0_folder_triage/blockers.csv"),
        gate_path=Path("reports/data_audit/phase0_folder_triage/phase0_readiness_gate.json"),
    )

    payload = gate_payload(phase)
    validate_gate_payload(payload)

    assert payload["status"] == "pass_with_medium_blockers"
    assert payload["proceed_status"] == "yes with medium blockers"
    assert payload["medium_count"] == 1
    assert payload["blockers_csv"] == "reports/data_audit/phase0_folder_triage/blockers.csv"


def test_parse_years_supports_ranges_and_lists() -> None:
    assert parse_years(["2024,2025", "2026"]) == [2024, 2025, 2026]
    assert parse_years(["2024-2026"]) == [2024, 2025, 2026]

