#!/usr/bin/env python3
"""Build report-only Phase 7 prediction artifact audit evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from scripts.phase6_wfa.prediction_diagnostics import (
    build_prediction_diagnostics,
)
from scripts.phase8_model_selection.evaluate_predictions import (
    _file_sha256,
    _relative_path,
    _write_json,
)


DEFAULT_OUTPUT_ROOT = Path("reports") / "prediction_audit"
DEFAULT_RUN = "baseline"
PHASE7_READY_STATUS = "PASS"
PHASE7_FAIL_STATUS = "FAIL"


def build_prediction_audit(
    *,
    predictions_path: Path,
    predictions_manifest: Path,
    output_root: Path,
    run: str,
) -> dict[str, Any]:
    legacy = build_prediction_diagnostics(
        predictions_path=predictions_path,
        predictions_manifest=predictions_manifest,
        output_root=output_root,
        run=run,
    )
    ready = bool(legacy.get("prediction_diagnostics_ready"))
    summary_path = output_root / "prediction_audit_summary.json"
    readme_path = output_root / "prediction_audit.md"
    outputs = dict(legacy.get("outputs", {}))
    outputs["legacy_prediction_diagnostics_summary"] = outputs.get("summary")
    outputs["summary"] = _relative_path(summary_path)
    outputs["readme"] = _relative_path(readme_path)

    payload = {
        **legacy,
        "script_path": _relative_path(Path(__file__)),
        "script_hash": _file_sha256(Path(__file__)),
        "diagnostic_type": "phase7_prediction_audit",
        "status": PHASE7_READY_STATUS if ready else PHASE7_FAIL_STATUS,
        "phase7_prediction_audit_ready": ready,
        "phase7_public_gate": True,
        "legacy_diagnostic_type": legacy.get("diagnostic_type"),
        "legacy_status": legacy.get("status"),
        "outputs": outputs,
        "model_promotion_allowed": False,
        "research_only": True,
    }
    _write_json(summary_path, payload)
    readme_path.write_text(
        "\n".join(
            [
                "# Phase 7 Prediction Audit",
                "",
                f"Run: `{run}`",
                "",
                "This report audits saved Phase 6 OOS predictions before Phase 8 trading evaluation.",
                "It does not train, tune, select, promote, or trade a model.",
                "",
                f"Status: `{payload['status']}`",
                f"Ready: `{payload['phase7_prediction_audit_ready']}`",
                "Failure labels: "
                f"`{', '.join(payload['failure_labels']) if payload['failure_labels'] else 'none'}`",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--predictions-manifest", required=True)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT.as_posix())
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = build_prediction_audit(
        predictions_path=Path(args.predictions),
        predictions_manifest=Path(args.predictions_manifest),
        output_root=Path(args.output_root),
        run=args.run,
    )
    print(
        result["status"],
        "phase7 prediction audit:",
        f"predictions={result['prediction_count']}",
        f"targets={result['target_count']}",
        f"failures={result['failure_count']}",
        f"summary={result['outputs']['summary']}",
    )
    return 1 if result["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
