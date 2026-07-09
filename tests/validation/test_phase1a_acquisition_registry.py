from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import phase1a_acquisition_registry as registry


def _write_plan(path: Path, *, output_path: str, plan_hash: str = "hash-test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "mode": "download-dbn",
                "schema": "ohlcv-1m",
                "schemas": ["ohlcv-1m"],
                "generated_at": "2026-07-09T00:00:00+00:00",
                "approval_id": None,
                "plan_hash": plan_hash,
                "reports_root": "reports/raw_ingest",
                "tasks": [
                    {
                        "dataset": "GLBX.MDP3",
                        "product": "ES",
                        "year": 2024,
                        "start": "2024-01-01",
                        "end": "2025-01-01",
                        "symbol": "ES.v.0",
                        "output_path": output_path,
                        "schema": "ohlcv-1m",
                        "stype_in": "continuous",
                        "stype_out": "instrument_id",
                        "chunk": "year",
                        "raw_format": "dbn-zstd",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_legacy_plan_row_is_partial_reproducibility_not_invalid(
    tmp_path: Path,
) -> None:
    output_path = "data/dbn/ohlcv_1m/ES/2024/2024-01-01_2025-01-01.dbn.zst"
    plan_path = tmp_path / "reports" / "raw_ingest" / "databento_download_plan.json"
    _write_plan(plan_path, output_path=output_path)

    rows = registry.rows_from_plan_path(plan_path, repo_root=tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["dataset"] == "GLBX.MDP3"
    assert row["schema"] == "ohlcv-1m"
    assert row["symbol"] == "ES.v.0"
    assert row["approval_id"] == registry.LEGACY_APPROVAL_ID
    assert row["plan_hash"] == "hash-test"
    assert json.loads(row["request_text"]) == {
        "compression": "zstd",
        "dataset": "GLBX.MDP3",
        "delivery": "download",
        "encoding": "dbn",
        "schema": "ohlcv-1m",
        "split_duration": "year",
        "start": "2024-01-01",
        "stype_in": "continuous",
        "stype_out": "instrument_id",
        "symbols": "ES.v.0",
        "end": "2025-01-01",
    }
    assert row["download_started_at"] is None
    assert row["download_completed_at"] is None
    assert row["provenance_status"] == "post_transfer_hash_only"
    assert row["reproducibility_status"] == "partially_reproducible"
    assert row["validity_status"] == "request_definition_only_current_artifact_not_verified"
    assert registry.validate_registry_row(row) == []


def test_sidecar_original_delivery_fields_upgrade_registry_status(tmp_path: Path) -> None:
    output_path = "data/dbn/ohlcv_1m/ES/2024/2024-01-01_2025-01-01.dbn.zst"
    plan_path = tmp_path / "reports" / "raw_ingest" / "databento_download_plan.json"
    _write_plan(plan_path, output_path=output_path)
    sidecar = tmp_path / output_path
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_bytes(b"placeholder")
    sidecar.with_name(sidecar.name + ".manifest.json").write_text(
        json.dumps(
            {
                "file_sha256": "current-hash",
                "dataset_version": "dataset-v1",
                "schema_version": "schema-v1",
                "request_text": "{\"dataset\":\"GLBX.MDP3\",\"symbols\":\"ES.v.0\"}",
                "original_filename": "databento-original.dbn.zst",
                "original_file_sha256": "original-hash",
                "download_started_at": "2026-07-09T00:00:01+00:00",
                "download_completed_at": "2026-07-09T00:00:02+00:00",
                "transfer_history": [{"action": "filesystem_move_to_final_path"}],
            }
        ),
        encoding="utf-8",
    )

    row = registry.rows_from_plan_path(plan_path, repo_root=tmp_path)[0]

    assert row["provenance_status"] == "original_delivery_hash_recorded"
    assert row["reproducibility_status"] == "reproducible_with_recorded_original_hash"
    assert row["current_file_sha256"] == "current-hash"
    assert row["request_text"] == "{\"dataset\":\"GLBX.MDP3\",\"symbols\":\"ES.v.0\"}"
    assert row["original_file_sha256"] == "original-hash"
    assert row["download_started_at"] == "2026-07-09T00:00:01+00:00"
    assert row["download_completed_at"] == "2026-07-09T00:00:02+00:00"
    assert row["validity_status"] == "valid_current_artifact_if_current_hash_matches"
    assert registry.validate_registry_row(row) == []


def test_build_registry_dedupes_and_writes_jsonl(tmp_path: Path) -> None:
    output_path = "data/dbn/ohlcv_1m/ES/2024/2024-01-01_2025-01-01.dbn.zst"
    _write_plan(
        tmp_path / "reports" / "one" / "databento_download_plan.json",
        output_path=output_path,
    )
    _write_plan(
        tmp_path / "reports" / "two" / "databento_download_plan.json",
        output_path=output_path,
    )

    rows = registry.build_registry([tmp_path / "reports"], repo_root=tmp_path)
    out = tmp_path / "manifests" / "phase1a_acquisition_registry.jsonl"
    registry.write_jsonl(out, rows)
    read_back = registry.read_jsonl(out)

    assert len(rows) == 1
    assert read_back == rows
    assert registry.validation_failures(read_back) == []
