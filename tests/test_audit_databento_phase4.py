from __future__ import annotations

from pathlib import Path

from scripts.audit_databento_phase4 import active_pipeline_rows, parse_paths_config


def test_predictions_root_null_is_not_configured(tmp_path: Path) -> None:
    config = tmp_path / "alpha_tiered.yaml"
    config.write_text(
        "\n".join(
            [
                "paths:",
                "  raw_root: data/raw",
                "  predictions_root: null",
                "",
            ]
        ),
        encoding="utf-8",
    )

    config_paths = parse_paths_config(config)
    rows = active_pipeline_rows([], config_paths, set())
    prediction_row = next(row for row in rows if row["name"] == "predictions_root")

    assert config_paths["predictions_root"] == ""
    assert prediction_row["path"] == ""
    assert prediction_row["status"] == "not_configured"
    assert prediction_row["issue"] == "predictions_root not configured; explicit root required"


def test_predictions_root_accepts_report_scoped_root(tmp_path: Path) -> None:
    config = tmp_path / "alpha_tiered.yaml"
    report_root = "reports/wfa_research/tier1_rebuild_v1/predictions"
    config.write_text(
        "\n".join(
            [
                "paths:",
                f"  predictions_root: {report_root}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    config_paths = parse_paths_config(config)
    rows = active_pipeline_rows([], config_paths, set())
    prediction_row = next(row for row in rows if row["name"] == "predictions_root")

    assert config_paths["predictions_root"] == report_root
    assert prediction_row["path"] == report_root
    assert prediction_row["status"] == "ok"
    assert prediction_row["issue"] == ""
