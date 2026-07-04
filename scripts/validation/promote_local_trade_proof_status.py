#!/usr/bin/env python3
"""Promote reviewed local-trade proof status without staging generated artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import build_local_trade_proof_status_promotion_proposal as proposal_gate


STAGE = "local_trade_proof_status_promotion"
STATUS_PROMOTED = "PROMOTED_LOCAL_TRADE_PROOF_STATUS_REVIEW_READY"
STATUS_NO_GO = "NO_GO_LOCAL_TRADE_PROOF_STATUS_PROMOTION"
DECISION_APPROVED = "human_approved_separate_proof_status_promotion"
DECISION_BLOCKED = "proof_status_promotion_blocked"
PROMOTED_PROOF_STATUS = "LOCAL_TRADE_PROOF_STATUS_REVIEW_READY"
NOT_PROMOTED_PROOF_STATUS = "LOCAL_TRADE_PROOF_STATUS_NOT_PROMOTED"

DEFAULT_PROPOSAL = proposal_gate.DEFAULT_JSON_OUT

FALSE_APPROVAL_FLAGS = (
    "canonical_promotion_approved",
    "data_mutation_performed",
    "generated_artifacts_staged",
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "live_or_paper_execution_approved",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def resolve_path(repo_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def rel(path: Path, repo_root: Path) -> str:
    return ledger_gate.rel(path, repo_root)


def _check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
    )


def _git_staged_generated_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "data", "reports"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff --cached failed")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


def _proposal_rows(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    rows = proposal.get("proposal_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _pair(row: dict[str, Any]) -> str:
    return f"{row.get('market')}:{row.get('year')}"


def _source_status_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        source_reports = row.get("source_reports")
        if not isinstance(source_reports, list) or not source_reports:
            failures.append({"market_year": _pair(row), "reason": "source_reports_missing"})
            continue
        for source in source_reports:
            if not isinstance(source, dict):
                failures.append({"market_year": _pair(row), "reason": "source_report_not_object"})
                continue
            if source.get("status") != "PASS":
                failures.append(
                    {
                        "market_year": _pair(row),
                        "path": source.get("path"),
                        "status": source.get("status"),
                    }
                )
    return failures


def _candidate_classification_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        classifications = row.get("source_classifications")
        causal_roots = row.get("causal_roots")
        if not isinstance(classifications, list) or len(classifications) != 1:
            continue
        if not isinstance(causal_roots, list):
            continue
        if ledger_gate.CANDIDATE_CAUSAL_ROOT in causal_roots and classifications[0] != "candidate_derived_review_evidence":
            failures.append(
                {
                    "market_year": _pair(row),
                    "source_classifications": classifications,
                    "causal_roots": causal_roots,
                }
            )
    return failures


def _mixed_classification_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        classifications = row.get("source_classifications")
        if not isinstance(classifications, list) or len(classifications) != 1:
            failures.append(
                {
                    "market_year": _pair(row),
                    "source_classifications": classifications,
                }
            )
    return failures


def _proposed_status_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "market_year": _pair(row),
            "proposed_proof_status": row.get("proposed_proof_status"),
            "proof_status_promoted": row.get("proof_status_promoted"),
        }
        for row in rows
        if row.get("proposed_proof_status") != proposal_gate.PROPOSED_STATUS
        or row.get("proof_status_promoted") is not False
    ]


def _duplicate_pairs(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        pair = _pair(row)
        if pair in seen:
            duplicates.add(pair)
        seen.add(pair)
    return sorted(duplicates)


def _single_classification(row: dict[str, Any]) -> Any:
    classifications = row.get("source_classifications")
    if isinstance(classifications, list) and classifications:
        return classifications[0]
    return None


def _promotion_rows(rows: list[dict[str, Any]], *, promoted: bool) -> list[dict[str, Any]]:
    proof_status = PROMOTED_PROOF_STATUS if promoted else NOT_PROMOTED_PROOF_STATUS
    return [
        {
            "market": row.get("market"),
            "year": row.get("year"),
            "proof_status": proof_status,
            "proof_status_promoted": promoted,
            "source_classification": _single_classification(row),
            "source_reports": row.get("source_reports", []),
            "evidence_windows": row.get("evidence_windows", []),
            "causal_roots": row.get("causal_roots", []),
            "canonical_promotion_approved": False,
            "modeling_approved": False,
            "wfa_approved": False,
        }
        for row in rows
    ]


def build_report(
    *,
    repo_root: Path,
    proposal_path: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    proposal = read_json(proposal_path)
    summary = proposal.get("summary") if isinstance(proposal.get("summary"), dict) else {}
    proposal_checks = proposal.get("checks") if isinstance(proposal.get("checks"), list) else []
    proposal_rows = _proposal_rows(proposal)
    staged_paths = sorted(staged_generated_paths) if staged_generated_paths is not None else _git_staged_generated_paths(repo_root)

    failed_proposal_checks = [
        check for check in proposal_checks if isinstance(check, dict) and check.get("status") != "PASS"
    ]
    row_pairs = {_pair(row) for row in proposal_rows}
    duplicate_pairs = _duplicate_pairs(proposal_rows)
    source_failures = _source_status_failures(proposal_rows)
    candidate_failures = _candidate_classification_failures(proposal_rows)
    mixed_classifications = _mixed_classification_failures(proposal_rows)
    proposed_status_failures = _proposed_status_failures(proposal_rows)
    proposal_staged_paths = proposal.get("staged_generated_paths")
    proposal_staged_count = summary.get("staged_generated_path_count")

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="proposal_review_ready",
        passed=summary.get("status") == proposal_gate.STATUS_READY,
        observed=summary.get("status"),
        expected=proposal_gate.STATUS_READY,
        detail="Proof-status promotion requires a review-ready proposal.",
    )
    _check(
        checks,
        name="proposal_checks_pass",
        passed=not failed_proposal_checks,
        observed=failed_proposal_checks,
        expected=[],
        detail="All proposal checks must pass before proof-status promotion.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged during proof-status promotion.",
    )
    _check(
        checks,
        name="proposal_staged_generated_artifacts_absent",
        passed=proposal_staged_count == 0 and proposal_staged_paths == [],
        observed={"count": proposal_staged_count, "paths": proposal_staged_paths},
        expected={"count": 0, "paths": []},
        detail="The reviewed proposal must also have been built with zero staged generated artifacts.",
    )
    _check(
        checks,
        name="proposal_rows_present_and_counted",
        passed=bool(proposal_rows) and len(proposal_rows) == summary.get("proposal_row_count"),
        observed={"rows": len(proposal_rows), "summary_count": summary.get("proposal_row_count")},
        expected="nonzero rows matching summary.proposal_row_count",
        detail="Promotion rows must exactly match the reviewed proposal row count.",
    )
    _check(
        checks,
        name="proposal_rows_unique",
        passed=not duplicate_pairs and len(row_pairs) == len(proposal_rows),
        observed=duplicate_pairs,
        expected=[],
        detail="Each promoted market-year may appear only once.",
    )
    _check(
        checks,
        name="proposal_rows_are_unpromoted_review_status",
        passed=not proposed_status_failures,
        observed=proposed_status_failures,
        expected=proposal_gate.PROPOSED_STATUS,
        detail="Input rows must still be proposal-only rows, not pre-promoted rows.",
    )
    _check(
        checks,
        name="source_reports_pass",
        passed=not source_failures,
        observed=source_failures,
        expected=[],
        detail="Every source report behind a promoted proof-status row must be PASS.",
    )
    _check(
        checks,
        name="candidate_rows_remain_review_evidence",
        passed=not candidate_failures,
        observed=candidate_failures,
        expected=[],
        detail="Candidate-root rows may be promoted only as proof status, not as canonical evidence.",
    )
    _check(
        checks,
        name="proposal_rows_not_mixed_classification",
        passed=not mixed_classifications,
        observed=mixed_classifications,
        expected=[],
        detail="Each promoted market-year must have exactly one evidence classification.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    promoted = not failures
    promoted_rows = _promotion_rows(proposal_rows, promoted=promoted)
    promoted_markets = sorted({str(row["market"]) for row in promoted_rows if row.get("market")})
    candidate_count = sum(
        1
        for row in promoted_rows
        if row.get("source_classification") == "candidate_derived_review_evidence"
    )
    tier1_count = sum(
        1
        for row in promoted_rows
        if row.get("source_classification") == "repaired_tier1_convention_evidence"
    )
    status = STATUS_PROMOTED if promoted else STATUS_NO_GO
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_APPROVED if promoted else DECISION_BLOCKED,
            "input_proposal": rel(proposal_path, repo_root),
            "input_proposal_sha256": ledger_gate.sha256_file(proposal_path) if proposal_path.exists() else None,
            "input_proposal_status": summary.get("status"),
            "promoted_proof_status": PROMOTED_PROOF_STATUS if promoted else NOT_PROMOTED_PROOF_STATUS,
            "proof_status_promoted": promoted,
            "promoted_market_year_count": len(promoted_rows) if promoted else 0,
            "promoted_market_count": len(promoted_markets) if promoted else 0,
            "candidate_derived_market_year_count": candidate_count if promoted else 0,
            "repaired_tier1_market_year_count": tier1_count if promoted else 0,
            "uncovered_canonical_market_count": summary.get("uncovered_canonical_market_count"),
            "unselected_report_count": summary.get("unselected_report_count"),
            "excluded_report_count": summary.get("excluded_report_count"),
            "staged_generated_path_count": len(staged_paths),
            "canonical_promotion_approved": False,
            "data_mutation_performed": False,
            "generated_artifacts_staged": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "live_or_paper_execution_approved": False,
            "failure_count": len(failures),
        },
        "checks": checks,
        "proof_status_rows": promoted_rows,
        "uncovered_canonical_markets": proposal.get("uncovered_canonical_markets", []),
        "unselected_reports": proposal.get("unselected_reports", []),
        "excluded_reports": proposal.get("excluded_reports", []),
        "staged_generated_paths": staged_paths,
        "non_approval": {
            "scope": "proof-status promotion only",
            "canonical_promotion_approved": False,
            "data_mutation_performed": False,
            "generated_artifacts_staged": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "live_or_paper_execution_approved": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Local Trade Proof-Status Promotion",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: proof-status promotion only; no generated artifacts, canonical data, modeling, WFA, metrics, predictions, or live/paper execution are approved.",
        f"- Status: `{summary['status']}`.",
        f"- Decision: `{summary['decision']}`.",
        f"- Input proposal: `{summary['input_proposal']}`.",
        f"- Promoted proof status: `{summary['promoted_proof_status']}`.",
        f"- Promoted market-years: {summary['promoted_market_year_count']}.",
        f"- Promoted markets: {summary['promoted_market_count']}.",
        f"- Uncovered canonical markets: {summary['uncovered_canonical_market_count']}.",
        "",
        "## Non-Approval Flags",
        "",
    ]
    for flag in FALSE_APPROVAL_FLAGS:
        lines.append(f"- `{flag}`: `{str(summary[flag]).lower()}`.")

    lines.extend(["", "## Proof-Status Rows", "", "| market-year | proof status | source classification |", "| --- | --- | --- |"])
    for row in report["proof_status_rows"]:
        lines.append(
            f"| `{row['market']}:{row['year']}` | `{row['proof_status']}` | `{row['source_classification']}` |"
        )

    failed_checks = [check for check in report["checks"] if check["status"] == "FAIL"]
    if failed_checks:
        lines.extend(["", "## Failed Checks", ""])
        for check in failed_checks:
            lines.append(f"- `{check['name']}` observed `{check['observed']}` expected `{check['expected']}`.")
    lines.append("")
    return "\n".join(lines)


def _ensure_reports_output(repo_root: Path, output_path: Path) -> None:
    try:
        output_path.resolve().relative_to((repo_root / "reports").resolve())
    except ValueError as exc:
        raise ValueError(f"output path must be under reports/: {rel(output_path, repo_root)}") from exc


def write_report(report: dict[str, Any], *, repo_root: Path, json_out: Path, markdown_out: Path) -> None:
    _ensure_reports_output(repo_root, json_out)
    _ensure_reports_output(repo_root, markdown_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--proposal", default=str(DEFAULT_PROPOSAL))
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    proposal_path = resolve_path(repo_root, args.proposal)
    try:
        report = build_report(repo_root=repo_root, proposal_path=proposal_path)
        if bool(args.json_out) != bool(args.markdown_out):
            raise ValueError("--json-out and --markdown-out must be supplied together")
        if args.json_out and args.markdown_out:
            write_report(
                report,
                repo_root=repo_root,
                json_out=resolve_path(repo_root, args.json_out),
                markdown_out=resolve_path(repo_root, args.markdown_out),
            )
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"promoted_market_years={summary['promoted_market_year_count']} "
        f"uncovered_canonical_markets={summary['uncovered_canonical_market_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 0 if summary["status"] == STATUS_PROMOTED else 1


if __name__ == "__main__":
    raise SystemExit(main())
