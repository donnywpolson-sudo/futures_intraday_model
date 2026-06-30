from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.validation import validate_broad_causal_raw_source_readiness as readiness


def _write_source(path: Path, payload: bytes = b"source") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return readiness.sha256_file(path)


def _write_raw(
    path: Path,
    *,
    market: str = "ES",
    year: int = 2024,
    source_file: str,
    source_sha256: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            {
                "ts_event": pd.Timestamp(f"{year}-01-02T15:00:00Z"),
                "market": market,
                "year": year,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10,
                "source_file": source_file,
                "source_sha256": source_sha256,
            }
        ]
    )
    frame.to_parquet(path, index=False)


def _prebuild_plan(rows: list[dict[str, object]]) -> dict[str, object]:
    counts = {
        "action_required": sum(1 for row in rows if row["prebuild_status"] == "action_required"),
        "deferred_policy_review": sum(
            1 for row in rows if row["prebuild_status"] == "deferred_policy_review"
        ),
        "ready_for_build": 0,
        "excluded_from_phase2": sum(
            1 for row in rows if row["prebuild_status"] == "excluded_from_phase2"
        ),
    }
    return {
        "summary": {
            "stage": "broad_causal_rebuild_prebuild_plan",
            "future_root": readiness.FUTURE_ROOT,
            "expected_rows": len(rows),
            "status_counts": counts,
            "research_use_allowed": False,
            "broader_modeling_approved": False,
            "config_promotion_approved": False,
            "legacy_restore_approved": False,
        },
        "rows": rows,
    }


def _row(
    market: str,
    year: int,
    status: str = "action_required",
) -> dict[str, object]:
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


def _write_plan(path: Path, plan: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan), encoding="utf-8")


def test_build_report_marks_ready_and_deferred_without_reading_deferred(tmp_path: Path) -> None:
    source_path = tmp_path / "data" / "dbn" / "ohlcv_1m" / "ES" / "2024" / "source.dbn.zst"
    source_hash = _write_source(source_path)
    _write_raw(
        tmp_path / "data" / "raw" / "ES" / "2024.parquet",
        source_file=source_path.relative_to(tmp_path).as_posix(),
        source_sha256=source_hash,
    )
    plan_path = tmp_path / "prebuild.json"
    _write_plan(plan_path, _prebuild_plan([_row("ES", 2024), _row("ES", 2025, "deferred_policy_review")]))

    report = readiness.build_report(
        repo_root=tmp_path,
        prebuild_plan_path=plan_path,
        generated_at_utc="2026-06-29T00:00:00Z",
        expected_rows=2,
        expected_action_required=1,
        expected_deferred_policy_review=1,
    )
    rows = {row["pair"]: row for row in report["rows"]}

    assert report["summary"]["status"] == "READY_FOR_SEPARATE_BUILD_APPROVAL"
    assert rows["ES:2024"]["readiness_status"] == readiness.READY_STATUS
    assert rows["ES:2024"]["source_reference_count"] == 1
    assert rows["ES:2025"]["readiness_status"] == readiness.DEFERRED_STATUS
    assert rows["ES:2025"]["raw_read_performed"] is False
    assert report["summary"]["broader_modeling_approved"] is False
    assert report["summary"]["build_approved"] is False


def test_missing_raw_parquet_fails_closed(tmp_path: Path) -> None:
    plan_path = tmp_path / "prebuild.json"
    _write_plan(plan_path, _prebuild_plan([_row("ES", 2024)]))

    report = readiness.build_report(
        repo_root=tmp_path,
        prebuild_plan_path=plan_path,
        expected_rows=1,
        expected_action_required=1,
        expected_deferred_policy_review=0,
    )

    assert report["summary"]["status"] == "ACTION_REQUIRED"
    assert report["rows"][0]["readiness_status"] == readiness.MISSING_RAW_STATUS


def test_source_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    source_path = tmp_path / "data" / "dbn" / "ohlcv_1m" / "ES" / "2024" / "source.dbn.zst"
    _write_source(source_path, b"actual")
    _write_raw(
        tmp_path / "data" / "raw" / "ES" / "2024.parquet",
        source_file=source_path.relative_to(tmp_path).as_posix(),
        source_sha256="0" * 64,
    )
    plan_path = tmp_path / "prebuild.json"
    _write_plan(plan_path, _prebuild_plan([_row("ES", 2024)]))

    report = readiness.build_report(
        repo_root=tmp_path,
        prebuild_plan_path=plan_path,
        expected_rows=1,
        expected_action_required=1,
        expected_deferred_policy_review=0,
    )

    assert report["rows"][0]["readiness_status"] == readiness.SOURCE_REFERENCE_STATUS
    assert "source hash mismatch" in report["rows"][0]["blockers"][0]


def test_invalid_prebuild_plan_fails_closed(tmp_path: Path) -> None:
    plan = _prebuild_plan([_row("ES", 2024)])
    plan["summary"]["broader_modeling_approved"] = True  # type: ignore[index]
    plan_path = tmp_path / "prebuild.json"
    _write_plan(plan_path, plan)

    with pytest.raises(ValueError, match="prebuild plan invariant failure"):
        readiness.build_report(
            repo_root=tmp_path,
            prebuild_plan_path=plan_path,
            expected_rows=1,
            expected_action_required=1,
            expected_deferred_policy_review=0,
        )


def test_write_report_outputs_json_and_markdown_with_non_approval(tmp_path: Path) -> None:
    plan_path = tmp_path / "prebuild.json"
    _write_plan(plan_path, _prebuild_plan([_row("ES", 2024, "deferred_policy_review")]))
    report = readiness.build_report(
        repo_root=tmp_path,
        prebuild_plan_path=plan_path,
        expected_rows=1,
        expected_action_required=0,
        expected_deferred_policy_review=1,
    )
    json_out = tmp_path / "out" / "readiness.json"
    md_out = tmp_path / "out" / "readiness.md"

    readiness.write_report(report, json_out=json_out, markdown_out=md_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = md_out.read_text(encoding="utf-8")
    assert payload["summary"]["stage"] == "broad_causal_raw_source_readiness"
    assert payload["summary"]["config_promotion_approved"] is False
    assert "does not approve broader modeling" in markdown
    assert "config promotion" in markdown
