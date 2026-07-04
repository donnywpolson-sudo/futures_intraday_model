#!/usr/bin/env python3
"""Build a read-only proof-status promotion proposal from the accepted evidence ledger."""

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


STAGE = "local_trade_proof_status_promotion_proposal"
STATUS_READY = "REVIEW_READY_PROOF_STATUS_PROMOTION_PROPOSAL"
STATUS_NO_GO = "NO_GO_PROOF_STATUS_PROMOTION_PROPOSAL"
DECISION_REVIEW_ONLY = "review_only_no_proof_status_promotion"
PROPOSED_STATUS = "PROPOSED_LOCAL_TRADE_PROOF_STATUS_REVIEW_READY"

DEFAULT_LEDGER = ledger_gate.DEFAULT_JSON_OUT
DEFAULT_JSON_OUT = (
    REPO_ROOT
    / "reports/pipeline_audit/local_trade_proof_status_promotion_proposal_20250618_20260613.json"
)
DEFAULT_MARKDOWN_OUT = DEFAULT_JSON_OUT.with_suffix(".md")

FALSE_APPROVAL_FLAGS = (
    "proof_status_promoted",
    "canonical_promotion_approved",
    "generated_artifacts_staged",
    "data_mutation_performed",
    "modeling_approved",
    "wfa_approved",
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


def _input_reports_by_path(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = ledger.get("input_reports")
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("path")): row
        for row in rows
        if isinstance(row, dict) and row.get("path")
    }


def _coverage_rows(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = ledger.get("coverage")
    rows = coverage.get("rows") if isinstance(coverage, dict) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _dedupe_dicts(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        key = json.dumps(row, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _candidate_classification_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        role = row.get("report_role")
        causal_root = row.get("causal_root")
        classification = row.get("root_classification")
        if role == "candidate_recovery_shard" or causal_root == ledger_gate.CANDIDATE_CAUSAL_ROOT:
            if classification != "candidate_derived_review_evidence":
                failures.append(
                    {
                        "market": row.get("market"),
                        "year": row.get("year"),
                        "report_path": row.get("report_path"),
                        "report_role": role,
                        "causal_root": causal_root,
                        "root_classification": classification,
                    }
                )
    return failures


def _build_proposal_rows(
    *,
    coverage_rows: list[dict[str, Any]],
    reports_by_path: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    by_pair: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in coverage_rows:
        market = row.get("market")
        year = row.get("year")
        if not isinstance(market, str):
            continue
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            continue
        by_pair.setdefault((market, year_int), []).append(row)

    proposal_rows: list[dict[str, Any]] = []
    for (market, year), rows in sorted(by_pair.items()):
        classifications = sorted({str(row.get("root_classification")) for row in rows})
        roles = sorted({str(row.get("report_role")) for row in rows})
        causal_roots = sorted({str(row.get("causal_root")) for row in rows})
        report_paths = sorted({str(row.get("report_path")) for row in rows})
        source_reports = []
        for path in report_paths:
            source = reports_by_path.get(path, {})
            source_reports.append(
                {
                    "path": path,
                    "sha256": source.get("sha256"),
                    "role": source.get("role"),
                    "root_classification": source.get("root_classification"),
                    "status": source.get("status"),
                }
            )
        evidence_windows = _dedupe_dicts(
            [
                {
                    "report_path": str(row.get("report_path")),
                    "window": row.get("window"),
                }
                for row in rows
            ]
        )
        proposal_rows.append(
            {
                "market": market,
                "year": year,
                "proposed_proof_status": PROPOSED_STATUS,
                "proposal_only": True,
                "proof_status_promoted": False,
                "source_report_roles": roles,
                "source_classifications": classifications,
                "causal_roots": causal_roots,
                "source_reports": source_reports,
                "evidence_windows": evidence_windows,
            }
        )
    return proposal_rows


def _mixed_classification_rows(proposal_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "market": row["market"],
            "year": row["year"],
            "source_classifications": row["source_classifications"],
            "causal_roots": row["causal_roots"],
        }
        for row in proposal_rows
        if len(row["source_classifications"]) != 1
    ]


def build_report(
    *,
    repo_root: Path,
    ledger_path: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    ledger = read_json(ledger_path)
    summary = ledger.get("summary") if isinstance(ledger.get("summary"), dict) else {}
    ledger_checks = ledger.get("checks") if isinstance(ledger.get("checks"), list) else []
    coverage_rows = _coverage_rows(ledger)
    reports_by_path = _input_reports_by_path(ledger)
    staged_paths = sorted(staged_generated_paths) if staged_generated_paths is not None else _git_staged_generated_paths(repo_root)
    proposal_rows = _build_proposal_rows(coverage_rows=coverage_rows, reports_by_path=reports_by_path)

    ledger_failed_checks = [
        check for check in ledger_checks if isinstance(check, dict) and check.get("status") != "PASS"
    ]
    candidate_failures = _candidate_classification_failures(coverage_rows)
    mixed_classifications = _mixed_classification_rows(proposal_rows)

    coverage_pairs = {
        f"{row.get('market')}:{row.get('year')}"
        for row in coverage_rows
        if row.get("market") is not None and row.get("year") is not None
    }
    proposal_pairs = {f"{row['market']}:{row['year']}" for row in proposal_rows}

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="input_ledger_review_ready",
        passed=summary.get("status") == ledger_gate.STATUS_READY,
        observed=summary.get("status"),
        expected=ledger_gate.STATUS_READY,
        detail="The proposal can only be built from a review-ready accepted-evidence ledger.",
    )
    _check(
        checks,
        name="input_ledger_checks_pass",
        passed=not ledger_failed_checks,
        observed=ledger_failed_checks,
        expected=[],
        detail="All accepted-evidence ledger checks must be PASS.",
    )
    _check(
        checks,
        name="staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged for a read-only proposal.",
    )
    _check(
        checks,
        name="proposal_rows_from_accepted_coverage",
        passed=bool(proposal_rows) and proposal_pairs == coverage_pairs,
        observed={"proposal_pairs": sorted(proposal_pairs), "coverage_pairs": sorted(coverage_pairs)},
        expected="proposal rows collapse exactly the accepted ledger coverage market-years",
        detail="Proposal rows must come only from accepted ledger coverage rows.",
    )
    _check(
        checks,
        name="candidate_rows_preserve_review_classification",
        passed=not candidate_failures,
        observed=candidate_failures,
        expected=[],
        detail="Candidate recovery shard rows must remain candidate_derived_review_evidence.",
    )
    _check(
        checks,
        name="proposal_rows_not_mixed_classification",
        passed=not mixed_classifications,
        observed=mixed_classifications,
        expected=[],
        detail="Each proposed market-year must have one evidence classification and must not mix candidate and repaired evidence.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    status = STATUS_READY if not failures else STATUS_NO_GO
    coverage = ledger.get("coverage") if isinstance(ledger.get("coverage"), dict) else {}
    report = {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_REVIEW_ONLY,
            "input_ledger": rel(ledger_path, repo_root),
            "input_ledger_sha256": ledger_gate.sha256_file(ledger_path) if ledger_path.exists() else None,
            "input_ledger_status": summary.get("status"),
            "proposal_row_count": len(proposal_rows),
            "accepted_market_year_count": summary.get("accepted_market_year_count"),
            "uncovered_canonical_market_count": summary.get("uncovered_canonical_market_count"),
            "unselected_report_count": summary.get("unselected_report_count"),
            "excluded_report_count": summary.get("excluded_report_count"),
            "staged_generated_path_count": len(staged_paths),
            "review_only_no_promotion": True,
            "proof_status_promoted": False,
            "canonical_promotion_approved": False,
            "generated_artifacts_staged": False,
            "data_mutation_performed": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "failure_count": len(failures),
        },
        "checks": checks,
        "proposal_rows": proposal_rows,
        "uncovered_canonical_markets": coverage.get("uncovered_canonical_markets", []),
        "unselected_reports": ledger.get("unselected_reports", []),
        "excluded_reports": ledger.get("excluded_reports", []),
        "staged_generated_paths": staged_paths,
        "non_approval": {
            "scope": "generated proof-status promotion proposal only",
            "proof_status_promoted": False,
            "canonical_promotion_approved": False,
            "generated_artifacts_staged": False,
            "data_mutation_performed": False,
            "modeling_approved": False,
            "wfa_approved": False,
        },
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Local Trade Proof-Status Promotion Proposal",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: read-only generated proposal; no proof-status promotion is performed.",
        f"- Status: `{summary['status']}`.",
        f"- Decision: `{summary['decision']}`.",
        f"- Input ledger: `{summary['input_ledger']}`.",
        f"- Proposal rows: {summary['proposal_row_count']}.",
        f"- Uncovered canonical markets: {summary['uncovered_canonical_market_count']}.",
        f"- Unselected reports: {summary['unselected_report_count']}.",
        "",
        "## Non-Approval Flags",
        "",
        "- This report does not stage generated artifacts, write proof status, mutate canonical data/configs, approve modeling, or approve WFA.",
    ]
    for flag in FALSE_APPROVAL_FLAGS:
        lines.append(f"- `{flag}`: `{str(summary[flag]).lower()}`.")

    lines.extend(
        [
            "",
            "## Proposal Rows",
            "",
            "| market-year | proposed status | source classification | source reports |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in report["proposal_rows"]:
        source_reports = ", ".join(str(item["path"]) for item in row["source_reports"])
        lines.append(
            f"| `{row['market']}:{row['year']}` | `{row['proposed_proof_status']}` | "
            f"`{', '.join(row['source_classifications'])}` | {source_reports} |"
        )

    lines.extend(["", "## Uncovered Canonical Markets", ""])
    uncovered = report.get("uncovered_canonical_markets") or []
    lines.append(f"- `{', '.join(str(item) for item in uncovered)}`" if uncovered else "- None.")

    lines.extend(["", "## Unselected Reports", ""])
    unselected = report.get("unselected_reports") or []
    if unselected:
        lines.extend(f"- `{path}`" for path in unselected)
    else:
        lines.append("- None.")

    lines.extend(["", "## Excluded Superseded Reports", ""])
    excluded = report.get("excluded_reports") or []
    if excluded:
        for row in excluded:
            failures = "; ".join(str(item) for item in row.get("failures", []))
            lines.append(f"- `{row.get('path')}` status `{row.get('status')}`: {failures}")
    else:
        lines.append("- None.")

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
    parser.add_argument("--accepted-evidence-ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root).resolve()
    ledger_path = resolve_path(repo_root, args.accepted_evidence_ledger)
    json_out = resolve_path(repo_root, args.json_out)
    markdown_out = resolve_path(repo_root, args.markdown_out)
    try:
        report = build_report(repo_root=repo_root, ledger_path=ledger_path)
        write_report(report, repo_root=repo_root, json_out=json_out, markdown_out=markdown_out)
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL {STAGE}: {exc}")
        return 1
    summary = report["summary"]
    print(
        f"{STAGE} "
        f"status={summary['status']} "
        f"proposal_rows={summary['proposal_row_count']} "
        f"uncovered_canonical_markets={summary['uncovered_canonical_market_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"json={rel(json_out, repo_root)}"
    )
    return 0 if summary["status"] == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
