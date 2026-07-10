from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import build_execution_realism_primary_evidence_intake as intake


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _prediction_inputs(tmp_path: Path) -> tuple[Path, Path]:
    prediction_path = _write_text(tmp_path / "data" / "predictions.parquet", "fixture-predictions")
    manifest_path = _write_json(
        tmp_path / "reports" / "prediction_manifest.json",
        {"run": "baseline", "prediction_path": prediction_path.as_posix()},
    )
    return prediction_path, manifest_path


def _source_manifest(
    tmp_path: Path,
    *,
    status: str = "PASS",
    rationale: str | None = "reviewed primary execution evidence",
) -> Path:
    rows = []
    for category in intake.REQUIRED_CATEGORIES:
        source_path = _write_text(
            tmp_path / "external_primary" / f"{category}.json",
            f"{category} source evidence",
        )
        row: dict[str, object] = {
            "path": source_path.as_posix(),
            "category": category,
            "description": f"{category} source",
            "review_status": status,
        }
        if rationale is not None:
            row["review_rationale"] = rationale
        rows.append(row)
    return _write_json(tmp_path / "source_manifest.json", {"sources": rows})


def test_intake_writes_phase8_compatible_summary_with_reviewed_source_hashes(
    tmp_path: Path,
) -> None:
    prediction_path, manifest_path = _prediction_inputs(tmp_path)
    source_manifest = _source_manifest(tmp_path, status="PASS")
    output_root = tmp_path / "reports" / "execution_realism"

    payloads = intake.build_payloads(
        run="baseline",
        prediction_path=prediction_path,
        predictions_manifest=manifest_path,
        source_manifest_path=source_manifest,
        output_root=output_root,
        max_source_files=16,
        max_total_bytes=1024 * 1024,
    )
    outputs = intake.write_outputs(output_root=output_root, payloads=payloads, overwrite=False)

    summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
    inventory = json.loads(outputs["source_inventory"].read_text(encoding="utf-8"))
    gate = summary["execution_realism_gate"]
    assert gate["status"] == "PASS"
    assert gate["execution_realism_ready"] is True
    assert set(gate["check_results"]) == set(intake.REQUIRED_CATEGORIES)
    assert summary["prediction_path"].endswith("predictions.parquet")
    assert summary["input_file_hashes"][summary["prediction_path"]] == intake._file_sha256(
        prediction_path
    )
    for category, check in gate["check_results"].items():
        assert check["status"] == "PASS"
        assert check["evidence_paths"]
        assert check["source_hashes"]
        assert category in check["evidence_paths"][0]
    assert inventory["source_file_count"] == 4
    assert inventory["budget_failure"] is None
    assert outputs["readme"].exists()

    with pytest.raises(FileExistsError):
        intake.write_outputs(output_root=output_root, payloads=payloads, overwrite=False)


def test_unreviewed_source_rows_remain_missing_evidence(tmp_path: Path) -> None:
    prediction_path, manifest_path = _prediction_inputs(tmp_path)
    source_path = _write_text(tmp_path / "external_primary" / "delay.json", "delay evidence")
    source_manifest = _write_json(
        tmp_path / "source_manifest.json",
        {
            "sources": [
                {
                    "path": source_path.as_posix(),
                    "category": "delay_stress",
                    "description": "delay source",
                }
            ]
        },
    )

    payloads = intake.build_payloads(
        run="baseline",
        prediction_path=prediction_path,
        predictions_manifest=manifest_path,
        source_manifest_path=source_manifest,
        output_root=tmp_path / "reports",
        max_source_files=16,
        max_total_bytes=1024 * 1024,
    )

    check = payloads["summary"]["execution_realism_gate"]["check_results"]["delay_stress"]
    assert check["status"] == "MISSING_EVIDENCE"
    assert "review_status PASS or FAIL missing" in check["reason"]
    assert check["source_hashes"] == {}
    assert payloads["inventory"]["rows"][0]["sha256"] == intake._file_sha256(source_path)


def test_reviewed_pass_without_rationale_remains_missing_evidence(tmp_path: Path) -> None:
    prediction_path, manifest_path = _prediction_inputs(tmp_path)
    source_manifest = _source_manifest(tmp_path, status="PASS", rationale=None)

    payloads = intake.build_payloads(
        run="baseline",
        prediction_path=prediction_path,
        predictions_manifest=manifest_path,
        source_manifest_path=source_manifest,
        output_root=tmp_path / "reports",
        max_source_files=16,
        max_total_bytes=1024 * 1024,
    )

    gate = payloads["summary"]["execution_realism_gate"]
    assert gate["status"] == "FAIL"
    for check in gate["check_results"].values():
        assert check["status"] == "MISSING_EVIDENCE"
        assert "review rationale missing" in check["reason"]


def test_missing_source_file_remains_missing_evidence(tmp_path: Path) -> None:
    prediction_path, manifest_path = _prediction_inputs(tmp_path)
    source_manifest = _write_json(
        tmp_path / "source_manifest.json",
        {
            "sources": [
                {
                    "path": (tmp_path / "missing.json").as_posix(),
                    "category": "delay_stress",
                    "description": "delay source",
                    "review_status": "PASS",
                    "review_rationale": "reviewed but file is absent",
                }
            ]
        },
    )

    payloads = intake.build_payloads(
        run="baseline",
        prediction_path=prediction_path,
        predictions_manifest=manifest_path,
        source_manifest_path=source_manifest,
        output_root=tmp_path / "reports",
        max_source_files=16,
        max_total_bytes=1024 * 1024,
    )

    check = payloads["summary"]["execution_realism_gate"]["check_results"]["delay_stress"]
    assert check["status"] == "MISSING_EVIDENCE"
    assert "source file missing" in check["reason"]


def test_source_budget_limit_prevents_favorable_status(tmp_path: Path) -> None:
    prediction_path, manifest_path = _prediction_inputs(tmp_path)
    source_manifest = _source_manifest(tmp_path, status="PASS")

    payloads = intake.build_payloads(
        run="baseline",
        prediction_path=prediction_path,
        predictions_manifest=manifest_path,
        source_manifest_path=source_manifest,
        output_root=tmp_path / "reports",
        max_source_files=16,
        max_total_bytes=1,
    )

    inventory = payloads["inventory"]
    gate = payloads["summary"]["execution_realism_gate"]
    assert inventory["budget_failure"]
    assert gate["status"] == "FAIL"
    for check in gate["check_results"].values():
        assert check["status"] == "MISSING_EVIDENCE"
        assert "exceeds max_total_bytes" in check["reason"]


def test_main_writes_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    prediction_path, manifest_path = _prediction_inputs(tmp_path)
    source_manifest = _source_manifest(tmp_path, status="FAIL", rationale="reviewed failure")
    output_root = tmp_path / "reports" / "execution_realism"

    result = intake.main(
        [
            "--run",
            "baseline",
            "--prediction-path",
            prediction_path.as_posix(),
            "--predictions-manifest",
            manifest_path.as_posix(),
            "--source-manifest",
            source_manifest.as_posix(),
            "--output-root",
            output_root.as_posix(),
            "--max-source-files",
            "16",
            "--max-total-bytes",
            str(1024 * 1024),
        ]
    )

    assert result == 0
    assert (output_root / intake.SUMMARY_NAME).exists()
    assert "FAIL execution realism evidence intake" in capsys.readouterr().out
