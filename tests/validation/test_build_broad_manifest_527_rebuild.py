from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from scripts.validation import build_broad_manifest_527_rebuild as runner


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _include(path: Path, rows: list[dict[str, object]], token: str | None = None) -> None:
    _write_json(
        path,
        {
            "summary": {
                "approval_token": token or runner.APPROVAL_TOKEN,
                "approved_ready_row_count": runner.EXPECTED_MARKET_YEAR_COUNT,
                "build_approved": True,
                "broader_modeling_approved": False,
                "config_promotion_approved": False,
                "research_use_allowed": False,
            },
            "market_years": rows,
        },
    )


def _readiness(path: Path, *, status: str = "PASS", count: int | None = None) -> None:
    observed = runner.EXPECTED_MARKET_YEAR_COUNT if count is None else count
    _write_json(
        path,
        {
            "status": status,
            "selected_market_year_count": observed,
            "checked_market_year_count": observed,
            "pending_market_year_count": 0,
            "blocker_count": 0,
            "failure_count": 0,
        },
    )


def _args(
    tmp_path: Path,
    *,
    include_rows: list[dict[str, object]] | None = None,
    token: str | None = None,
    chunk_size: int = 1,
    checkpoint: str | None = None,
) -> list[str]:
    include = tmp_path / "include.json"
    readiness = tmp_path / "readiness.json"
    _include(include, include_rows or [{"market": "ES", "year": 2024}])
    _readiness(readiness)
    return [
        "--raw-root",
        str(tmp_path / "data" / "raw"),
        "--output-root",
        str(tmp_path / "data" / "causal_base_candidates" / "broad_manifest_527_rebuild_v1"),
        "--reports-root",
        str(tmp_path / "reports" / "data_audit" / "causal_base_rebuild" / "broad_manifest_527_rebuild_v1"),
        "--profile-config",
        str(tmp_path / "configs" / "alpha_tiered.yaml"),
        "--session-config",
        str(tmp_path / "configs" / "market_sessions.yaml"),
        "--raw-alignment-report",
        str(tmp_path / "raw_alignment.json"),
        "--market-year-include-list",
        str(include),
        "--readiness-report",
        str(readiness),
        "--checkpoint-jsonl",
        checkpoint
        or str(
            tmp_path
            / "reports"
            / "data_audit"
            / "causal_base_rebuild"
            / "broad_manifest_527_rebuild_v1"
            / "build_progress.jsonl"
        ),
        "--chunk-size",
        str(chunk_size),
        "--broad-build-approval-token",
        token or runner.APPROVAL_TOKEN,
    ]


def test_rejects_wrong_token(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "EXPECTED_MARKET_YEAR_COUNT", 1)

    assert runner.main(_args(tmp_path, token="WRONG")) == 1

    assert "incorrect broad build approval token" in capsys.readouterr().out


def test_rejects_non_460_readiness(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "EXPECTED_MARKET_YEAR_COUNT", 1)
    args = _args(tmp_path)
    readiness_path = Path(args[args.index("--readiness-report") + 1])
    _readiness(readiness_path, count=0)

    assert runner.main(args) == 1

    assert "readiness selected_market_year_count mismatch" in capsys.readouterr().out


def test_rejects_forbidden_rows(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "EXPECTED_MARKET_YEAR_COUNT", 1)

    assert runner.main(_args(tmp_path, include_rows=[{"market": "6M", "year": 2012}])) == 1

    assert "forbidden market-years" in capsys.readouterr().out


def test_rejects_existing_roots(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "EXPECTED_MARKET_YEAR_COUNT", 1)
    args = _args(tmp_path)
    output_root = Path(args[args.index("--output-root") + 1])
    output_root.mkdir(parents=True)

    assert runner.main(args) == 1

    assert "output root already exists" in capsys.readouterr().out


def test_resume_existing_partial_rejects_unapproved_existing_output(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(runner, "EXPECTED_MARKET_YEAR_COUNT", 1)
    args = _args(tmp_path)
    output_root = Path(args[args.index("--output-root") + 1])
    bad_output = output_root / "ES" / "2025.parquet"
    bad_output.parent.mkdir(parents=True)
    bad_output.write_text("bad", encoding="utf-8")

    assert runner.main([*args, "--resume-existing-partial"]) == 1

    assert "outside approved scope" in capsys.readouterr().out


def test_rejects_checkpoint_under_data(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "EXPECTED_MARKET_YEAR_COUNT", 1)

    assert runner.main(_args(tmp_path, checkpoint="data/progress.jsonl")) == 1

    assert "checkpoint path must not be under data" in capsys.readouterr().out


def test_rejects_chunk_size_over_25(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(runner, "EXPECTED_MARKET_YEAR_COUNT", 1)

    assert runner.main(_args(tmp_path, chunk_size=runner.MAX_CHUNK_SIZE + 1)) == 1

    assert "--chunk-size must be <=" in capsys.readouterr().out


def test_build_accumulates_results_and_writes_one_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    rows = [
        {"market": "ES", "year": 2020},
        {"market": "CL", "year": 2020},
        {"market": "ZN", "year": 2021},
    ]
    monkeypatch.setattr(runner, "EXPECTED_MARKET_YEAR_COUNT", len(rows))
    args = _args(tmp_path, include_rows=rows, chunk_size=2)
    output_root = Path(args[args.index("--output-root") + 1])
    reports_root = Path(args[args.index("--reports-root") + 1])
    checkpoint = Path(args[args.index("--checkpoint-jsonl") + 1])

    def fake_select_build_inputs(**_: object) -> runner.BuildInputs:
        return runner.BuildInputs(
            config=SimpleNamespace(max_synthetic_gap_minutes=120),
            inputs=[
                (
                    str(row["market"]),
                    int(row["year"]),
                    tmp_path / "data" / "raw" / str(row["market"]) / f"{row['year']}.parquet",
                )
                for row in rows
            ],
            selection_metadata={"selection_mode": "exact_market_year_include_list"},
        )

    def fake_single_subprocess(
        *,
        input_path: Path,
        output_path: Path,
        result_json: Path,
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("fake parquet", encoding="utf-8")
        payload = {
            "profile": "all_raw",
            "market": output_path.parent.name,
            "year": int(output_path.stem),
            "input_path": input_path.as_posix(),
            "output_path": output_path.as_posix(),
            "raw_rows": 10,
            "output_rows": 10,
            "synthetic_rows": 0,
            "warnings": [],
            "failures": [],
        }
        result_json.parent.mkdir(parents=True, exist_ok=True)
        result_json.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                f"PASS {output_path.parent.name} {output_path.stem}: "
                "raw=10 out=10 synthetic=0 warnings=0 failures=0\n"
            ),
            stderr="",
        )

    def fake_write_reports(results: object, reports_root_arg: Path, *_: object, **__: object) -> None:
        result_list = list(results)
        reports_root_arg.mkdir(parents=True, exist_ok=True)
        manifest = {
            "status": "PASS",
            "outputs": [
                {
                    "market": result.market,
                    "year": result.year,
                    "output_path": result.output_path,
                }
                for result in result_list
            ],
        }
        validation = {"status": "PASS", "summary": {"file_count": len(result_list)}}
        (reports_root_arg / "causal_base_manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        (reports_root_arg / "causal_base_validation.json").write_text(
            json.dumps(validation),
            encoding="utf-8",
        )
        (reports_root_arg / "causal_base_validation.csv").write_text(
            "market,year\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(runner, "select_build_inputs", fake_select_build_inputs)
    monkeypatch.setattr(runner, "_run_single_subprocess", fake_single_subprocess)
    monkeypatch.setattr(runner.phase2, "write_reports", fake_write_reports)

    assert runner.main(args) == 0

    records = [
        json.loads(line)
        for line in checkpoint.read_text(encoding="utf-8").splitlines()
    ]
    manifest = json.loads((reports_root / "causal_base_manifest.json").read_text())
    assert len(list(output_root.rglob("*.parquet"))) == len(rows)
    assert [record["stage"] for record in records].count(
        "broad_manifest_527_build_chunk_start"
    ) == 2
    assert records[-1]["stage"] == "broad_manifest_527_build_summary"
    assert records[-1]["status"] == "PASS"
    assert len(manifest["outputs"]) == len(rows)
