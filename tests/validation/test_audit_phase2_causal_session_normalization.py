from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.phase2_causal_base.build_causal_base_data import process_file
from scripts.validation.audit_phase2_causal_session_normalization import build_report


def _write_session_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "session_templates:",
                "  cme_globex_17_16_ct:",
                "    timezone: America/Chicago",
                '    regular_open: "17:00"',
                '    regular_close: "16:00"',
                "    holidays:",
                '      - "2024-01-01"',
                "    closed_dates: []",
                "    early_closes:",
                '      "2024-01-15": "12:00"',
                "markets:",
                "  default:",
                "    session_template: cme_globex_17_16_ct",
                "  ES:",
                "    session_template: cme_globex_17_16_ct",
            ]
        ),
        encoding="utf-8",
    )


def _write_raw(path: Path, *, gap: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    offsets = [0, 2] if gap else [0, 1, 2]
    rows = []
    for offset in offsets:
        rows.append(
            {
                "rtype": 33,
                "publisher_id": 1,
                "instrument_id": 100,
                "symbol": "ESH4",
                "ts_event": pd.Timestamp("2024-01-02T15:00:00Z")
                + pd.Timedelta(minutes=offset),
                "open": 100.0 + offset,
                "high": 101.0 + offset,
                "low": 99.0 + offset,
                "close": 100.5 + offset,
                "volume": 10 + offset,
                "data_quality_status": "available",
                "data_quality_degraded": False,
            }
        )
    pd.DataFrame(rows).to_parquet(path, index=False)


def _build_fixture(tmp_path: Path, *, gap: bool = False) -> tuple[Path, Path, Path]:
    raw_root = tmp_path / "data" / "raw"
    causal_root = tmp_path / "data" / "causally_gated_normalized"
    session_config = tmp_path / "configs" / "market_sessions.yaml"
    raw_path = raw_root / "ES" / "2024.parquet"
    causal_path = causal_root / "ES" / "2024.parquet"
    _write_session_config(session_config)
    _write_raw(raw_path, gap=gap)
    result = process_file(
        raw_path,
        causal_path,
        profile="tier_1",
        session_config_path=session_config,
    )
    assert result.failures == []
    return raw_root, causal_root, session_config


def test_phase2_causal_session_audit_passes_clean_output(tmp_path: Path) -> None:
    raw_root, causal_root, session_config = _build_fixture(tmp_path)

    report = build_report(
        causal_root=causal_root,
        raw_root=raw_root,
        session_config=session_config,
        repo_root=tmp_path,
    )

    assert report["status"] == "PASS"
    assert report["failure_count"] == 0


def test_phase2_causal_session_audit_rejects_synthetic_ohlcv_values(
    tmp_path: Path,
) -> None:
    raw_root, causal_root, session_config = _build_fixture(tmp_path, gap=True)
    causal_path = causal_root / "ES" / "2024.parquet"
    frame = pd.read_parquet(causal_path)
    synthetic_idx = frame.index[frame["is_synthetic"]][0]
    frame.loc[synthetic_idx, "open"] = 100.5
    frame.to_parquet(causal_path, index=False)

    report = build_report(
        causal_root=causal_root,
        raw_root=raw_root,
        session_config=session_config,
        repo_root=tmp_path,
    )

    failures = report["files"][0]["failures"]
    assert report["status"] == "FAIL"
    assert any("synthetic rows carry open values" in failure for failure in failures)


def test_phase2_causal_session_audit_rejects_session_drift(tmp_path: Path) -> None:
    raw_root, causal_root, session_config = _build_fixture(tmp_path)
    causal_path = causal_root / "ES" / "2024.parquet"
    frame = pd.read_parquet(causal_path)
    frame.loc[0, "inside_session"] = False
    frame.to_parquet(causal_path, index=False)

    report = build_report(
        causal_root=causal_root,
        raw_root=raw_root,
        session_config=session_config,
        repo_root=tmp_path,
    )

    failures = report["files"][0]["failures"]
    assert report["status"] == "FAIL"
    assert any("session metadata drift inside_session" in failure for failure in failures)


def test_phase2_causal_session_audit_rejects_stale_lineage_hash(
    tmp_path: Path,
) -> None:
    raw_root, causal_root, session_config = _build_fixture(tmp_path)
    causal_path = causal_root / "ES" / "2024.parquet"
    frame = pd.read_parquet(causal_path)
    frame.loc[frame["raw_row_present"], "source_file_hash"] = "bad"
    frame.to_parquet(causal_path, index=False)

    report = build_report(
        causal_root=causal_root,
        raw_root=raw_root,
        session_config=session_config,
        repo_root=tmp_path,
    )

    failures = report["files"][0]["failures"]
    assert report["status"] == "FAIL"
    assert any("source_file_hash does not match" in failure for failure in failures)


def test_phase2_causal_session_audit_rejects_target_columns_and_overlap(
    tmp_path: Path,
) -> None:
    raw_root, causal_root, session_config = _build_fixture(tmp_path)
    causal_path = causal_root / "ES" / "2024.parquet"
    frame = pd.read_parquet(causal_path)
    frame["target_valid"] = False
    frame.loc[0, "target_valid"] = True
    frame.loc[1, "phase2_ready"] = False
    frame.loc[1, "phase2_not_ready_reason"] = "synthetic"
    frame.to_parquet(causal_path, index=False)

    report = build_report(
        causal_root=causal_root,
        raw_root=raw_root,
        session_config=session_config,
        repo_root=tmp_path,
    )

    failures = report["files"][0]["failures"]
    assert report["status"] == "FAIL"
    assert any("forbidden leakage columns present" in failure for failure in failures)
    assert any("target_valid crosses phase2_not_ready path" in failure for failure in failures)
