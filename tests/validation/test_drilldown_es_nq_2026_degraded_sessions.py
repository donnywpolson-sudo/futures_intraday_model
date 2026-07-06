from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from scripts.validation import drilldown_es_nq_2026_degraded_sessions as drilldown


def _write_raw(path: Path, *, market: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "ts_event": pd.to_datetime(
                [
                    "2026-01-05T23:00:00Z",
                    "2026-01-05T23:01:00Z",
                    "2026-01-06T23:00:00Z",
                    "2026-01-06T23:01:00Z",
                    "2026-01-07T17:00:00Z",
                ],
                utc=True,
            ),
            "market": [market] * 5,
            "open": [1.0, 1.1, 1.2, 1.3, 1.4],
            "high": [1.0, 1.1, 1.2, 1.3, 1.4],
            "low": [1.0, 1.1, 1.2, 1.3, 1.4],
            "close": [1.0, 1.1, 1.2, 1.3, 1.4],
            "volume": [1, 1, 1, 1, 1],
            "data_quality_degraded": [True, True, True, True, False],
            "data_quality_status": [
                "degraded",
                "degraded",
                "degraded",
                "degraded",
                "available",
            ],
        }
    )
    frame.to_parquet(path, index=False)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(tmp_path: Path) -> argparse.Namespace:
    raw_root = tmp_path / "raw"
    causal_root = tmp_path / "causal"
    for market in ("ES", "NQ"):
        _write_raw(raw_root / market / "2026.parquet", market=market)
    causal_frame = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2026-01-05T23:00:00Z"], utc=True),
            "data_quality_degraded": [True],
            "data_quality_status": ["degraded"],
            "is_synthetic": [False],
            "session_date": ["2026-01-06"],
        }
    )
    causal_path = causal_root / "NQ" / "2026.parquet"
    causal_path.parent.mkdir(parents=True, exist_ok=True)
    causal_frame.to_parquet(causal_path, index=False)

    es_readiness = tmp_path / "reports" / "es_readiness.json"
    phase_chain = tmp_path / "reports" / "phase_chain.json"
    _write_json(
        es_readiness,
        {
            "status": "FAIL",
            "failure_count": 1,
            "blocker_count": 1,
            "failures": ["accepted_readiness_exception is stale"],
            "blockers": [{"market": "ES", "year": 2026, "degraded_rows_pct": 1.7}],
        },
    )
    _write_json(
        phase_chain,
        {
            "status": "PASS_DIAGNOSTIC_NO_MUTATION",
            "conclusion": {"likely_root_cause": "policy/exception mismatch"},
        },
    )
    return argparse.Namespace(
        year=2026,
        raw_root=str(raw_root),
        causal_root=str(causal_root),
        session_config="configs/market_sessions.yaml",
        es_readiness_summary=str(es_readiness),
        phase_chain_diagnostic=str(phase_chain),
        json_out=str(tmp_path / "report.json"),
        md_out=str(tmp_path / "report.md"),
    )


def test_build_report_compares_es_nq_degraded_session_dates(tmp_path: Path) -> None:
    report = drilldown.build_report(_args(tmp_path))

    assert report["status"] == "PASS_DIAGNOSTIC_NO_MUTATION"
    assert report["policy"] == "REPORT_ONLY_NO_DATA_MUTATION"
    assert report["raw_degraded_session_summaries"]["ES"]["degraded_session_count"] == 2
    assert report["raw_degraded_session_summaries"]["NQ"]["degraded_session_count"] == 2
    assert report["comparison"]["cluster_call"] == "MATCHED_DEGRADED_SESSION_DATES"
    assert (
        report["comparison"]["exception_review_call"]
        == "SCOPED_EXCEPTION_REVIEW_SUPPORTED_NOT_APPROVED"
    )
    assert report["authorization"]["phase2_2026_rebuild_approved"] is False
    assert report["authorization"]["labels_features_wfa_predictions_approved"] is False


def test_writers_emit_json_and_markdown(tmp_path: Path) -> None:
    args = _args(tmp_path)
    report = drilldown.build_report(args)

    drilldown.write_json_report(report, Path(args.json_out))
    drilldown.write_markdown_report(report, Path(args.md_out))

    written = json.loads(Path(args.json_out).read_text(encoding="utf-8"))
    markdown = Path(args.md_out).read_text(encoding="utf-8")
    assert written["stage"] == "es_nq_2026_degraded_session_drilldown"
    assert "MATCHED_DEGRADED_SESSION_DATES" in markdown
    assert "Phase 2 2026 rebuild approved: `false`" in markdown
