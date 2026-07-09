#!/usr/bin/env python3
"""Build a terminal report-only alpha evidence completion closeout."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_MATRIX_PATH = (
    Path("reports")
    / "model_trust_audit"
    / "alpha_evidence_gap_matrix_20260709T034313Z"
    / "alpha_evidence_gap_matrix.json"
)
DEFAULT_RUN_ID = "tier1_core_phase6_full_predictions_20260706"

CLOSEOUT_VERDICT = "CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE"
SOURCE_MATRIX_VERDICT = "PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE"

PASS = "PASS"
FAIL = "FAIL"
MISSING = "MISSING_EVIDENCE"

TERMINAL_FAIL_BUCKETS = {
    "baseline_no_trade",
    "baseline_random_entry_null",
    "statistical_probabilistic_sharpe",
    "stability_fold_market_year_session",
    "execution_cost_stress",
}

MISSING_REQUIRED_BUCKETS = {
    "baseline_simple_carry_term_structure",
    "null_label_shuffle",
    "null_timing_shift",
    "statistical_pbo",
    "statistical_deflated_sharpe",
    "statistical_multiple_testing",
    "execution_delay_stress",
    "execution_capacity",
    "execution_liquidity_window",
    "execution_spread_slippage",
    "execution_partial_fills_rejects",
}

DIAGNOSTIC_PASS_BUCKETS = {
    "baseline_cost_only",
    "baseline_simple_trend",
    "baseline_simple_mean_reversion",
    "statistical_bootstrap_ci",
    "stability_parameter",
    "execution_turnover",
}

EXPECTED_OUTPUT_FILES = {
    "alpha_evidence_completion_closeout.json",
    "alpha_evidence_completion_closeout.md",
    "bucket_disposition.csv",
}


class CloseoutError(RuntimeError):
    """Fail-closed closeout construction error."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(value: str) -> str:
    return value.replace("+00:00", "Z").replace("-", "").replace(":", "").replace(".", "_")


def _resolve(repo_root: Path, path: Path | str | None) -> Path | None:
    if path is None:
        return None
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _relative(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CloseoutError(f"required matrix input missing: {path.as_posix()}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CloseoutError(f"could not read matrix input: {exc}") from exc
    if not isinstance(payload, dict):
        raise CloseoutError("matrix JSON root must be an object")
    return payload


def _file_sha256(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _validate_matrix(matrix: Mapping[str, Any]) -> list[dict[str, Any]]:
    if matrix.get("run_id") != DEFAULT_RUN_ID:
        raise CloseoutError(f"matrix run_id must be {DEFAULT_RUN_ID}")
    if matrix.get("verdict") != SOURCE_MATRIX_VERDICT:
        raise CloseoutError(f"matrix verdict must be {SOURCE_MATRIX_VERDICT}")
    if matrix.get("alpha_evidence_ready") is not False:
        raise CloseoutError("matrix alpha_evidence_ready must be false")
    buckets = matrix.get("buckets")
    if not isinstance(buckets, list):
        raise CloseoutError("matrix buckets must be a list")
    rows = [dict(row) for row in buckets if isinstance(row, Mapping)]
    if len(rows) != 23:
        raise CloseoutError(f"matrix must contain exactly 23 buckets, got {len(rows)}")
    if len({str(row.get("bucket_id")) for row in rows}) != len(rows):
        raise CloseoutError("matrix bucket_id values must be unique")
    return rows


def _classify_bucket(row: Mapping[str, Any], *, terminal_fail_present: bool) -> tuple[str, bool]:
    bucket_id = str(row.get("bucket_id"))
    status = str(row.get("status"))
    if bucket_id in TERMINAL_FAIL_BUCKETS and status == FAIL:
        return "terminal_fail", True
    if bucket_id in MISSING_REQUIRED_BUCKETS and status == MISSING:
        return "missing_required_evidence", True
    if bucket_id in DIAGNOSTIC_PASS_BUCKETS and status == PASS:
        return "diagnostic_pass_only", terminal_fail_present
    return "not_actionable_for_current_line", terminal_fail_present


def _bucket_disposition_rows(buckets: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    terminal_fail_present = any(
        str(row.get("bucket_id")) in TERMINAL_FAIL_BUCKETS and str(row.get("status")) == FAIL
        for row in buckets
    )
    rows: list[dict[str, Any]] = []
    for row in buckets:
        classification, blocked_by_terminal = _classify_bucket(
            row,
            terminal_fail_present=terminal_fail_present,
        )
        rows.append(
            {
                "bucket_id": str(row.get("bucket_id")),
                "category": str(row.get("category")),
                "name": str(row.get("name")),
                "source_status": str(row.get("status")),
                "closeout_classification": classification,
                "blocks_current_line": classification in {
                    "terminal_fail",
                    "missing_required_evidence",
                    "not_actionable_for_current_line",
                }
                and str(row.get("status")) != PASS,
                "blocked_by_terminal_fail": blocked_by_terminal,
                "reason": str(row.get("reason")),
            }
        )
    return rows


def _assert_output_paths(report_root: Path) -> dict[str, Path]:
    paths = {
        "json": report_root / "alpha_evidence_completion_closeout.json",
        "markdown": report_root / "alpha_evidence_completion_closeout.md",
        "bucket_disposition": report_root / "bucket_disposition.csv",
    }
    root = report_root.resolve()
    for path in paths.values():
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise CloseoutError(f"output path outside report root: {path}") from exc
    if {path.name for path in paths.values()} != EXPECTED_OUTPUT_FILES:
        raise CloseoutError("unexpected output file set")
    return paths


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "bucket_id",
        "category",
        "name",
        "source_status",
        "closeout_classification",
        "blocks_current_line",
        "blocked_by_terminal_fail",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Alpha Evidence Completion Closeout",
        "",
        f"- run: `{payload['run_id']}`",
        f"- verdict: `{payload['verdict']}`",
        f"- modeling_pause_required: `{payload['modeling_pause_required']}`",
        f"- future_modeling_allowed: `{payload['future_modeling_allowed']}`",
        f"- promotion_allowed: `{payload['promotion_allowed']}`",
        "",
        "## Disposition",
        "",
        "| bucket | source status | closeout classification | reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["bucket_dispositions"]:
        reason = str(row["reason"]).replace("|", "/")
        lines.append(
            f"| {row['bucket_id']} | {row['source_status']} | "
            f"{row['closeout_classification']} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## Non Approval",
            "",
            "- This closeout does not approve target discovery, source tests, WFA/modeling, Phase 8 refreshes, promotion, artifact freeze, final holdout, paper/live, provider/download commands, cleanup, staging, commit, push, or rescue tuning.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_alpha_evidence_completion_closeout(
    *,
    repo_root: Path,
    matrix_path: Path = DEFAULT_MATRIX_PATH,
    report_root: Path | None = None,
    generated_at_utc: str | None = None,
    write_reports: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    generated_at_utc = generated_at_utc or _utc_now()
    resolved_matrix = _resolve(repo_root, matrix_path)
    assert resolved_matrix is not None
    matrix = _read_json(resolved_matrix)
    buckets = _validate_matrix(matrix)
    source_counts = Counter(str(row.get("status")) for row in buckets)
    if dict(source_counts) != dict(matrix.get("bucket_status_counts", {})):
        raise CloseoutError("matrix bucket_status_counts do not match bucket rows")

    dispositions = _bucket_disposition_rows(buckets)
    classification_counts = Counter(row["closeout_classification"] for row in dispositions)
    terminal_fail_count = classification_counts.get("terminal_fail", 0)
    missing_required_count = classification_counts.get("missing_required_evidence", 0)
    if terminal_fail_count == 0:
        raise CloseoutError("closeout requires at least one terminal fail")

    report_root = _resolve(
        repo_root,
        report_root
        or Path("reports")
        / "model_trust_audit"
        / f"alpha_evidence_completion_closeout_{_timestamp_slug(generated_at_utc)}",
    )
    assert report_root is not None
    output_paths = _assert_output_paths(report_root)

    payload: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "git_commit": _git_commit(repo_root),
        "script_path": _relative(repo_root, Path(__file__).resolve()),
        "diagnostic_type": "alpha_evidence_completion_closeout",
        "diagnostic_only": True,
        "run_id": DEFAULT_RUN_ID,
        "status": "PASS_REPORT_WRITTEN" if write_reports else "PASS_REPORT_BUILT",
        "verdict": CLOSEOUT_VERDICT,
        "modeling_pause_required": True,
        "future_modeling_allowed": False,
        "future_evidence_work_allowed": True,
        "promotion_allowed": False,
        "source_matrix": {
            "path": _relative(repo_root, resolved_matrix),
            "sha256": _file_sha256(resolved_matrix),
            "verdict": matrix.get("verdict"),
            "alpha_evidence_ready": matrix.get("alpha_evidence_ready"),
            "bucket_status_counts": dict(source_counts),
        },
        "bucket_count": len(dispositions),
        "bucket_status_counts": dict(source_counts),
        "closeout_classification_counts": dict(classification_counts),
        "terminal_fail_count": terminal_fail_count,
        "missing_required_evidence_count": missing_required_count,
        "bucket_dispositions": dispositions,
        "blockers": [
            f"{row['bucket_id']}: {row['closeout_classification']} - {row['reason']}"
            for row in dispositions
            if row["blocks_current_line"]
        ],
        "non_approval": {
            "target_discovery": False,
            "source_tests": False,
            "wfa_modeling": False,
            "phase8_refresh": False,
            "promotion": False,
            "artifact_freeze": False,
            "final_holdout": False,
            "paper": False,
            "live": False,
            "provider_downloads": False,
            "cleanup": False,
            "staging_commit_push": False,
            "rescue_tuning": False,
        },
        "recommended_next_action": (
            "Do not continue this model line. Any future modeling must start as a "
            "separate predeclared evidence program."
        ),
        "outputs": {},
    }
    if write_reports:
        if report_root.exists():
            raise CloseoutError(f"report root already exists: {_relative(repo_root, report_root)}")
        report_root.mkdir(parents=True)
        _write_csv(output_paths["bucket_disposition"], dispositions)
        payload["outputs"] = {
            key: _relative(repo_root, path)
            for key, path in output_paths.items()
        }
        _write_json(output_paths["json"], payload)
        output_paths["markdown"].write_text(_markdown(payload), encoding="utf-8")
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--matrix", default=DEFAULT_MATRIX_PATH.as_posix())
    parser.add_argument("--report-root", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        result = build_alpha_evidence_completion_closeout(
            repo_root=Path(args.repo_root),
            matrix_path=Path(args.matrix),
            report_root=Path(args.report_root) if args.report_root else None,
            write_reports=True,
        )
    except CloseoutError as exc:
        print(f"FAIL alpha evidence completion closeout: {exc}")
        return 1
    print(
        f"{result['verdict']} alpha evidence completion closeout: "
        f"buckets={result['bucket_count']} "
        f"terminal_fails={result['terminal_fail_count']} "
        f"missing_required={result['missing_required_evidence_count']} "
        f"report={result['outputs'].get('json')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
