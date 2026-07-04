from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _windows(start: str, end: str, count: int) -> list[tuple[str, str]]:
    cursor = _dt(start)
    final = _dt(end)
    result: list[tuple[str, str]] = []
    for index in range(count):
        next_cursor = final if index == count - 1 else cursor + timedelta(days=7)
        result.append((_iso(cursor), _iso(next_cursor)))
        cursor = next_cursor
    return result


def _clean_report(
    *,
    market: str,
    year: int,
    window: dict[str, str],
    causal_root: str,
    status: str = "PASS",
    failed_minutes: int = 0,
    unverified_minutes: int = 0,
) -> dict[str, object]:
    row_status = "PASS" if status == "PASS" and failed_minutes == 0 and unverified_minutes == 0 else "FAIL"
    return {
        "generated_at_utc": "2026-07-02T00:00:00Z",
        "status": status,
        "failures": [] if status == "PASS" else ["local trade evidence failed"],
        "method": "local trades DBN cross-check of OHLCV synthetic missing minutes",
        "caveat": "This is not direct trades proof outside the access window.",
        "window": window,
        "local_trades_schema_access": ledger.EXPECTED_ACCESS_WINDOW,
        "dbn_root": ledger.EXPECTED_DBN_ROOT,
        "raw_root": ledger.EXPECTED_RAW_ROOT,
        "causal_root": causal_root,
        "summary": {
            "synthetic_gap_count": 1,
            "missing_minute_count": 1,
            "verified_empty_minutes": 1,
            "timestamp_basis_mismatch_minutes": 0,
            "failed_minutes": failed_minutes,
            "unverified_minutes": unverified_minutes,
            "status_counts": {row_status: 1},
        },
        "market_years": [
            {
                "market": market,
                "year": year,
                "status": row_status,
                "failures": [] if row_status == "PASS" else ["bad row"],
                "classification_counts": {"verified_no_trade_rows_inside_ohlcv_gap": 1},
                "summary": {
                    "failed_minutes": failed_minutes,
                    "unverified_minutes": unverified_minutes,
                },
            }
        ],
    }


def _write_tier1_report(path: Path) -> None:
    market_years: list[dict[str, object]] = []
    for market in ["ES", "CL"]:
        for year in [2025, 2026]:
            market_years.append(
                {
                    "market": market,
                    "year": year,
                    "status": "PASS",
                    "failures": [],
                    "classification_counts": {"verified_no_trade_rows_inside_ohlcv_gap": 1},
                    "summary": {"failed_minutes": 0, "unverified_minutes": 0},
                }
            )
    payload = _clean_report(
        market="ES",
        year=2025,
        window=ledger.EXPECTED_ACCESS_WINDOW,
        causal_root=ledger.TIER1_CAUSAL_ROOT,
    )
    payload["summary"] = {
        "synthetic_gap_count": 4,
        "missing_minute_count": 4,
        "verified_empty_minutes": 4,
        "timestamp_basis_mismatch_minutes": 0,
        "failed_minutes": 0,
        "unverified_minutes": 0,
        "status_counts": {"PASS": 4},
    }
    payload["market_years"] = market_years
    _write_json(path, payload)


def _write_candidate_shard(path: Path, *, market: str, year: int, start: str, end: str) -> None:
    _write_json(
        path,
        _clean_report(
            market=market,
            year=year,
            window={"start": start, "end": end},
            causal_root=ledger.CANDIDATE_CAUSAL_ROOT,
        ),
    )


def _write_candidate_set(shards_root: Path, spec: dict[str, object]) -> None:
    market = str(spec["market"])
    year = int(spec["year"])
    count = int(spec["expected_count"])
    year_window = ledger._year_window(year)
    if "relative_file" in spec:
        start, end = year_window["start"], year_window["end"]
        _write_candidate_shard(shards_root / str(spec["relative_file"]), market=market, year=year, start=start, end=end)
        return
    for index, (start, end) in enumerate(_windows(year_window["start"], year_window["end"], count), start=1):
        stem = f"{market}_{year}_w{index:02d}_{start[:10].replace('-', '')}_{end[:10].replace('-', '')}.json"
        _write_candidate_shard(shards_root / str(spec["relative_dir"]) / stem, market=market, year=year, start=start, end=end)


def _write_superseded(shards_root: Path) -> None:
    for relative_path in ledger.SUPERSEDED_REPORTS:
        path = shards_root / relative_path
        market = path.stem.split("_")[0]
        year = int(path.stem.split("_")[1])
        payload = _clean_report(
            market=market,
            year=year,
            window=ledger._year_window(year),
            causal_root=ledger.CANDIDATE_CAUSAL_ROOT,
            status="FAIL",
            unverified_minutes=1,
        )
        payload["failures"] = ["--max-runtime-seconds limit exceeded"]
        _write_json(path, payload)


def _fixture(tmp_path: Path) -> dict[str, Path]:
    tier1_report = tmp_path / "reports" / "pipeline_audit" / "tier1.json"
    shards_root = tmp_path / "reports" / "pipeline_audit" / "local_trade_shards_20250618_20260613"
    phase2_manifest = tmp_path / "reports" / "data_audit" / "phase2_460" / "causal_base_manifest.json"
    _write_tier1_report(tier1_report)
    for spec in ledger.EXPECTED_SHARD_SETS:
        _write_candidate_set(shards_root, spec)
    _write_superseded(shards_root)
    _write_json(
        phase2_manifest,
        {
            "status": "PASS",
            "outputs": [{"market": market, "year": 2020} for market in ["ES", "CL", "NG", "RB", "HO", "ZN"]],
        },
    )
    return {
        "repo_root": tmp_path,
        "tier1_report": tier1_report,
        "shards_root": shards_root,
        "phase2_manifest": phase2_manifest,
    }


def _build(paths: dict[str, Path]) -> dict[str, object]:
    return ledger.build_report(
        repo_root=paths["repo_root"],
        tier1_report_path=paths["tier1_report"],
        accepted_shards_root=paths["shards_root"],
        phase2_manifest_path=paths["phase2_manifest"],
        generated_at_utc="2026-07-02T00:00:00Z",
    )


def test_builds_review_ready_ledger_from_tier1_plus_133_shards(tmp_path: Path) -> None:
    report = _build(_fixture(tmp_path))

    assert report["summary"]["status"] == ledger.STATUS_READY
    assert report["summary"]["decision"] == ledger.DECISION_REVIEW_ONLY
    assert report["summary"]["accepted_report_count"] == 134
    assert report["summary"]["accepted_shard_report_count"] == 133
    assert report["summary"]["tier1_report_count"] == 1
    assert report["summary"]["excluded_report_count"] == 3
    assert report["summary"]["proof_status_promoted"] is False
    assert report["summary"]["generated_artifacts_staged"] is False
    assert report["summary"]["candidate_root_promoted_to_canonical"] is False
    assert "ZN" in report["coverage"]["uncovered_canonical_markets"]


def test_write_report_records_non_approval_flags_and_superseded_files(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    report = _build(paths)
    json_out = tmp_path / "reports" / "pipeline_audit" / "ledger.json"
    markdown_out = tmp_path / "reports" / "pipeline_audit" / "ledger.md"

    ledger.write_report(report, repo_root=tmp_path, json_out=json_out, markdown_out=markdown_out)

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    markdown = markdown_out.read_text(encoding="utf-8")
    assert payload["summary"]["canonical_promotion_approved"] is False
    assert payload["summary"]["data_mutation_performed"] is False
    assert payload["summary"]["reports_generated_only"] is True
    assert "review-only" in markdown
    assert "remaining_v1/RB_2025.json" in markdown
    assert "`proof_status_promoted`: `false`" in markdown


def test_missing_expected_shard_fails_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    next((paths["shards_root"] / "HO_2026_split_v1").glob("HO_2026_w24*.json")).unlink()

    report = _build(paths)

    assert report["summary"]["status"] == ledger.STATUS_NO_GO
    assert any(check["name"] == "accepted_shard_file_count" for check in report["checks"] if check["status"] == "FAIL")


def test_non_pass_or_unverified_shard_fails_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    bad_path = next((paths["shards_root"] / "RB_2026_split_v1").glob("RB_2026_w01*.json"))
    payload = json.loads(bad_path.read_text(encoding="utf-8"))
    payload["status"] = "FAIL"
    payload["failures"] = ["bad shard"]
    payload["summary"]["unverified_minutes"] = 1
    payload["market_years"][0]["status"] = "FAIL"
    payload["market_years"][0]["summary"]["unverified_minutes"] = 1
    _write_json(bad_path, payload)

    report = _build(paths)

    assert report["summary"]["status"] == ledger.STATUS_NO_GO
    assert any(check["name"] == "accepted_shard_reports_clean" for check in report["checks"] if check["status"] == "FAIL")


def test_overlapping_candidate_windows_fail_closed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    bad_path = next((paths["shards_root"] / "NG_2025_split_v1").glob("NG_2025_w02*.json"))
    payload = json.loads(bad_path.read_text(encoding="utf-8"))
    payload["window"]["start"] = ledger.EXPECTED_ACCESS_WINDOW["start"]
    _write_json(bad_path, payload)

    report = _build(paths)

    assert report["summary"]["status"] == ledger.STATUS_NO_GO
    assert any(check["name"] == "accepted_shard_windows_contiguous" for check in report["checks"] if check["status"] == "FAIL")


def test_candidate_root_is_classified_as_review_evidence_not_canonical(tmp_path: Path) -> None:
    report = _build(_fixture(tmp_path))

    candidate_reports = [
        row for row in report["input_reports"] if row["role"] == "candidate_recovery_shard"
    ]
    assert candidate_reports
    assert {row["root_classification"] for row in candidate_reports} == {"candidate_derived_review_evidence"}
    assert {row["causal_root"] for row in candidate_reports} == {ledger.CANDIDATE_CAUSAL_ROOT}
    assert ledger.TIER1_CAUSAL_ROOT not in {row["causal_root"] for row in candidate_reports}
