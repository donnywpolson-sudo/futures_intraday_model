#!/usr/bin/env python3
"""Build a local-trade model-eligible scope from promoted proof-status rows."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation import build_local_trade_accepted_evidence_ledger as ledger_gate
from scripts.validation import promote_local_trade_proof_status as promotion_gate


STAGE = "local_trade_model_eligible_scope"
STATUS_READY = "REVIEW_READY_LOCAL_TRADE_MODEL_ELIGIBLE_SCOPE"
STATUS_NO_GO = "NO_GO_LOCAL_TRADE_MODEL_ELIGIBLE_SCOPE"
DECISION_SCOPE_ONLY = "model_eligible_scope_defined_no_modeling_execution"
DECISION_BLOCKED = "model_eligible_scope_blocked"
ELIGIBLE_SCOPE_STATUS = "MODEL_ELIGIBLE_SCOPE_REVIEW_READY"
BLOCKED_SCOPE_STATUS = "MODEL_SCOPE_BLOCKED_UNCOVERED_CANONICAL_MARKET"

DEFAULT_PROPOSAL = promotion_gate.DEFAULT_PROPOSAL

FALSE_APPROVAL_FLAGS = (
    "label_build_approved",
    "feature_matrix_build_approved",
    "modeling_approved",
    "wfa_approved",
    "metrics_approved",
    "predictions_approved",
    "canonical_promotion_approved",
    "data_mutation_performed",
    "generated_artifacts_staged",
    "live_or_paper_execution_approved",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _proof_status_rows(promotion_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = promotion_report.get("proof_status_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _market_year_pair(row: dict[str, Any]) -> str:
    return f"{row.get('market')}:{row.get('year')}"


def _bad_proof_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bad: list[dict[str, Any]] = []
    for row in rows:
        if row.get("proof_status") != promotion_gate.PROMOTED_PROOF_STATUS or row.get("proof_status_promoted") is not True:
            bad.append(
                {
                    "market_year": _market_year_pair(row),
                    "proof_status": row.get("proof_status"),
                    "proof_status_promoted": row.get("proof_status_promoted"),
                }
            )
        if not row.get("source_classification"):
            bad.append(
                {
                    "market_year": _market_year_pair(row),
                    "source_classification": row.get("source_classification"),
                }
            )
    return bad


def _duplicate_pairs(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        pair = _market_year_pair(row)
        if pair in seen:
            duplicates.add(pair)
        seen.add(pair)
    return sorted(duplicates)


def _eligible_market_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_market: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        market = row.get("market")
        if isinstance(market, str):
            by_market.setdefault(market, []).append(row)

    eligible: list[dict[str, Any]] = []
    for market, market_rows in sorted(by_market.items()):
        years = sorted(
            int(row["year"])
            for row in market_rows
            if isinstance(row.get("year"), int)
        )
        classifications = sorted({str(row.get("source_classification")) for row in market_rows})
        causal_roots = sorted(
            {
                str(root)
                for row in market_rows
                for root in (row.get("causal_roots") if isinstance(row.get("causal_roots"), list) else [])
            }
        )
        source_reports = sorted(
            {
                str(source.get("path"))
                for row in market_rows
                for source in (row.get("source_reports") if isinstance(row.get("source_reports"), list) else [])
                if isinstance(source, dict) and source.get("path")
            }
        )
        eligible.append(
            {
                "market": market,
                "scope_status": ELIGIBLE_SCOPE_STATUS,
                "proof_status": promotion_gate.PROMOTED_PROOF_STATUS,
                "proof_status_years": years,
                "source_classifications": classifications,
                "causal_roots": causal_roots,
                "source_reports": source_reports,
                "baseline_planning_allowed": True,
                "label_build_approved": False,
                "feature_matrix_build_approved": False,
                "modeling_approved": False,
                "wfa_approved": False,
            }
        )
    return eligible


def _blocked_market_rows(markets: Iterable[Any]) -> list[dict[str, Any]]:
    return [
        {
            "market": str(market),
            "scope_status": BLOCKED_SCOPE_STATUS,
            "reason": "canonical market is not covered by promoted local-trade proof status",
            "baseline_planning_allowed": False,
            "label_build_approved": False,
            "feature_matrix_build_approved": False,
            "modeling_approved": False,
            "wfa_approved": False,
        }
        for market in sorted(str(item) for item in markets)
    ]


def build_report(
    *,
    repo_root: Path,
    proposal_path: Path,
    generated_at_utc: str | None = None,
    staged_generated_paths: list[str] | None = None,
) -> dict[str, Any]:
    promotion_report = promotion_gate.build_report(
        repo_root=repo_root,
        proposal_path=proposal_path,
        staged_generated_paths=staged_generated_paths,
    )
    promotion_summary = promotion_report["summary"]
    proof_rows = _proof_status_rows(promotion_report)
    bad_rows = _bad_proof_rows(proof_rows)
    duplicate_pairs = _duplicate_pairs(proof_rows)
    eligible_markets = _eligible_market_rows(proof_rows) if not bad_rows and not duplicate_pairs else []
    blocked_markets = _blocked_market_rows(promotion_report.get("uncovered_canonical_markets", []))
    staged_paths = promotion_report.get("staged_generated_paths", [])

    checks: list[dict[str, Any]] = []
    _check(
        checks,
        name="proof_status_promotion_ready",
        passed=promotion_summary.get("status") == promotion_gate.STATUS_PROMOTED,
        observed=promotion_summary.get("status"),
        expected=promotion_gate.STATUS_PROMOTED,
        detail="Model-eligible scope can only be built from promoted proof-status rows.",
    )
    _check(
        checks,
        name="current_staged_generated_artifacts_absent",
        passed=not staged_paths,
        observed=staged_paths,
        expected=[],
        detail="Generated data/** and reports/** artifacts must not be staged while defining model-eligible scope.",
    )
    _check(
        checks,
        name="proof_status_rows_present_and_counted",
        passed=bool(proof_rows) and len(proof_rows) == promotion_summary.get("promoted_market_year_count"),
        observed={"rows": len(proof_rows), "summary_count": promotion_summary.get("promoted_market_year_count")},
        expected="nonzero rows matching promoted_market_year_count",
        detail="Eligible scope rows must match the promoted proof-status row count.",
    )
    _check(
        checks,
        name="proof_status_rows_promoted",
        passed=not bad_rows,
        observed=bad_rows,
        expected=[],
        detail="Every input row must carry promoted local-trade proof status and a source classification.",
    )
    _check(
        checks,
        name="proof_status_rows_unique",
        passed=not duplicate_pairs,
        observed=duplicate_pairs,
        expected=[],
        detail="Each proof-status market-year may appear only once.",
    )
    _check(
        checks,
        name="blocked_canonical_markets_preserved",
        passed=len(blocked_markets) == promotion_summary.get("uncovered_canonical_market_count"),
        observed={"rows": len(blocked_markets), "summary_count": promotion_summary.get("uncovered_canonical_market_count")},
        expected="blocked rows match uncovered canonical market count",
        detail="The scope gate must preserve uncovered canonical markets as blocked, not silently include them.",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    ready = not failures
    status = STATUS_READY if ready else STATUS_NO_GO
    return {
        "summary": {
            "stage": STAGE,
            "generated_at_utc": generated_at_utc or utc_now(),
            "status": status,
            "decision": DECISION_SCOPE_ONLY if ready else DECISION_BLOCKED,
            "input_proposal": rel(proposal_path, repo_root),
            "input_proof_status_promotion_status": promotion_summary.get("status"),
            "model_scope_defined": ready,
            "eligible_market_count": len(eligible_markets) if ready else 0,
            "eligible_proof_status_market_year_count": len(proof_rows) if ready else 0,
            "blocked_canonical_market_count": len(blocked_markets),
            "staged_generated_path_count": len(staged_paths),
            "baseline_planning_allowed": ready,
            "label_build_approved": False,
            "feature_matrix_build_approved": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "canonical_promotion_approved": False,
            "data_mutation_performed": False,
            "generated_artifacts_staged": False,
            "live_or_paper_execution_approved": False,
            "failure_count": len(failures),
        },
        "checks": checks,
        "model_eligible_markets": eligible_markets,
        "blocked_canonical_markets": blocked_markets,
        "proof_status_market_years": proof_rows,
        "non_approval": {
            "scope": "model-eligible scope definition only",
            "label_build_approved": False,
            "feature_matrix_build_approved": False,
            "modeling_approved": False,
            "wfa_approved": False,
            "metrics_approved": False,
            "predictions_approved": False,
            "canonical_promotion_approved": False,
            "data_mutation_performed": False,
            "generated_artifacts_staged": False,
            "live_or_paper_execution_approved": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Local Trade Model-Eligible Scope",
        "",
        f"- Generated at UTC: {summary['generated_at_utc']}",
        "- Scope: model-eligible scope definition only; this does not build labels, features, models, WFA splits, metrics, predictions, or live/paper execution artifacts.",
        f"- Status: `{summary['status']}`.",
        f"- Decision: `{summary['decision']}`.",
        f"- Input proposal: `{summary['input_proposal']}`.",
        f"- Eligible markets: {summary['eligible_market_count']}.",
        f"- Eligible proof-status market-years: {summary['eligible_proof_status_market_year_count']}.",
        f"- Blocked canonical markets: {summary['blocked_canonical_market_count']}.",
        "",
        "## Non-Approval Flags",
        "",
    ]
    for flag in FALSE_APPROVAL_FLAGS:
        lines.append(f"- `{flag}`: `{str(summary[flag]).lower()}`.")

    lines.extend(["", "## Model-Eligible Markets", "", "| market | proof-status years | source classifications |", "| --- | --- | --- |"])
    if report["model_eligible_markets"]:
        for row in report["model_eligible_markets"]:
            years = ", ".join(str(year) for year in row["proof_status_years"])
            classifications = ", ".join(str(item) for item in row["source_classifications"])
            lines.append(f"| `{row['market']}` | `{years}` | `{classifications}` |")
    else:
        lines.append("| None | None | None |")

    lines.extend(["", "## Blocked Canonical Markets", ""])
    blocked = [row["market"] for row in report["blocked_canonical_markets"]]
    lines.append(f"- `{', '.join(blocked)}`" if blocked else "- None.")

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
        f"eligible_markets={summary['eligible_market_count']} "
        f"eligible_proof_status_market_years={summary['eligible_proof_status_market_year_count']} "
        f"blocked_canonical_markets={summary['blocked_canonical_market_count']} "
        f"staged_generated_paths={summary['staged_generated_path_count']} "
        f"failure_count={summary['failure_count']}"
    )
    return 0 if summary["status"] == STATUS_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
