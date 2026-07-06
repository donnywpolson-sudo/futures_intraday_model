#!/usr/bin/env python3
"""Generate proposal-only alpha candidates or preflight config artifacts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from scripts.validation import run_alpha_discovery as single_runner


HARD_MAX_CANDIDATES = 100
DEFAULT_IDEATION_MAX_CANDIDATES = 10
IDEATION_REPORT_ROOT = Path("reports/pipeline_audit/strategy_candidate_ideation")
IDEATION_LAUNCHER_NAME = "RUN_STRATEGY_CANDIDATE_IDEATION.bat"
IDEATION_GENERATOR_ID = "strategy_candidate_ideation_v2"
IMPLEMENTATION_SELECTION_GENERATOR_ID = "strategy_candidate_ideation_selection_v1"
IMPLEMENTATION_SELECTION_FILENAME = "implementation_selection.json"
MARKDOWN_GENERATOR_MARKER = f"<!-- generated_by: {IDEATION_GENERATOR_ID} -->"
CANDIDATE_PACKET_FILENAME_RE = r"^[0-9]{3}_[a-z0-9_]+_v[0-9]+\.(md|json)$"
RISK_FLAG_VALUES = {"low", "medium", "high", "not_applicable", "not_run"}
WIZARD_READINESS_VALUES = {
    "not_runnable",
    "ready_for_implementation",
    "registered_not_configured",
    "preflight_ready",
}
IDEATION_STAMP = (
    "PROPOSAL ONLY - NOT REGISTERED - NOT MODEL-TRUST EVIDENCE - "
    "DO NOT RETUNE FROM THIS IDEATION"
)
CANONICAL_REGISTRY = Path("manifests/target_hypotheses/registry.json")
CANONICAL_TRIAL_STATUSES = Path("manifests/target_hypotheses/trial_statuses.jsonl")
ID_PLACEHOLDER = "replace_with_registered_candidate_id"
RUN_PLACEHOLDER = "replace_with_bounded_run_name"
SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
IDEATION_LIBRARY: tuple[dict[str, Any], ...] = (
    {
        "target_hypothesis_id": "opening_drive_followthrough_5m_v1",
        "target_family": "es_opening_drive_followthrough_5m",
        "horizon_label": "5m",
        "target_horizon": {"kind": "fixed_bars", "bar_size": "1m", "bars": 5},
        "exit_rule": {"kind": "fixed_horizon_close"},
        "description": (
            "Proposal-only ES 5-minute target idea conditioned on a strong causal opening drive "
            "and follow-through in the opening-drive direction."
        ),
        "novelty_rationale": (
            "Tests a short-horizon opening-drive continuation idea instead of reusing frozen "
            "opening-range acceptance or any existing 30-minute target shape."
        ),
        "setup_type": "opening_drive_followthrough",
        "required_inputs": [
            "ES 1-minute OHLCV with regular-session segment IDs",
            "pre-registered opening-drive window and direction state",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": ["opening_range_acceptance_continuation_30m_v1"],
        "blocked_reuse_notes": [
            "Do not reuse frozen opening-range acceptance as evidence for this shorter-horizon idea.",
            "Define opening-drive magnitude and event timing before any conversion or smoke output.",
        ],
        "review_metrics": {
            "implementation_complexity": "medium",
            "leakage_risk": "medium",
            "duplicate_target_risk": "medium",
            "event_density_risk": "medium",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "existing_session_ohlcv_plus_new_opening_drive_state",
        },
        "pre_registration": {
            "research_question": (
                "Does a strong causal ES opening drive produce cost-clearing 5-minute continuation?"
            ),
            "entry_condition": (
                "Candidate rows require a completed pre-registered opening-drive state using only "
                "same-session bars available at the event timestamp."
            ),
            "target_definition": (
                "Use next-open entry, same-session 5-bar path, configured ES costs, non-overlapping "
                "events, and continuation direction from the opening-drive side."
            ),
        },
    },
    {
        "target_hypothesis_id": "opening_drive_failed_followthrough_15m_v1",
        "target_family": "es_opening_drive_failed_followthrough_15m",
        "horizon_label": "15m",
        "target_horizon": {"kind": "fixed_bars", "bar_size": "1m", "bars": 15},
        "exit_rule": {"kind": "fixed_horizon_close"},
        "description": (
            "Proposal-only ES 15-minute target idea conditioned on a strong early opening drive, "
            "a failed follow-through attempt, and reversal away from the failed drive side."
        ),
        "novelty_rationale": (
            "Targets failed opening-drive reversal at a shorter horizon, not continuation after "
            "opening-range acceptance or retest."
        ),
        "setup_type": "opening_drive_failed_followthrough",
        "required_inputs": [
            "ES 1-minute OHLCV with regular-session segment IDs",
            "pre-registered opening-drive window and direction state",
            "causal failed follow-through or lower-high/higher-low state",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": ["opening_range_acceptance_continuation_30m_v1"],
        "blocked_reuse_notes": [
            "Do not reuse frozen opening-range acceptance as reversal evidence.",
            "Define failed-follow-through criteria before any conversion or smoke output.",
        ],
        "review_metrics": {
            "implementation_complexity": "medium",
            "leakage_risk": "medium",
            "duplicate_target_risk": "medium",
            "event_density_risk": "medium",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "existing_session_ohlcv_plus_new_opening_drive_state",
        },
        "pre_registration": {
            "research_question": (
                "After a strong ES opening drive fails to follow through, does the failure identify "
                "cost-clearing 15-minute reversal?"
            ),
            "entry_condition": (
                "Candidate rows require a completed opening-drive state and a later failed continuation "
                "attempt in the drive direction using only same-session causal bars."
            ),
            "target_definition": (
                "Use next-open entry, same-session 15-bar path, configured ES costs, non-overlapping "
                "events, and reversal direction opposite the failed opening-drive side."
            ),
        },
    },
    {
        "target_hypothesis_id": "vwap_reclaim_continuation_15m_v1",
        "target_family": "es_vwap_reclaim_continuation_15m",
        "horizon_label": "15m",
        "target_horizon": {"kind": "fixed_bars", "bar_size": "1m", "bars": 15},
        "exit_rule": {"kind": "fixed_horizon_close"},
        "description": (
            "Proposal-only ES 15-minute target idea conditioned on a causal excursion away from "
            "session VWAP, a reclaim through VWAP, and continuation in the reclaim direction."
        ),
        "novelty_rationale": (
            "Different from the stopped VWAP-reversion branch because it requires reclaim first and "
            "tests continuation after reclaim rather than direct mean reversion from stretch."
        ),
        "setup_type": "vwap_reclaim_continuation",
        "required_inputs": [
            "ES 1-minute OHLCV with session segment IDs and volume",
            "causal same-session VWAP state",
            "pre-registered VWAP excursion and reclaim thresholds",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": ["vwap_reversion_30m_v1"],
        "blocked_reuse_notes": [
            "Do not repackage the rejected VWAP-reversion result as fresh evidence.",
            "Register only if excursion, reclaim, and direction rules are source-tested separately.",
        ],
        "review_metrics": {
            "implementation_complexity": "medium",
            "leakage_risk": "medium",
            "duplicate_target_risk": "medium",
            "event_density_risk": "medium",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "existing_session_ohlcv_plus_new_causal_vwap_reclaim_state",
        },
        "pre_registration": {
            "research_question": (
                "After ES moves away from session VWAP and causally reclaims it, does the reclaim identify "
                "cost-clearing 15-minute continuation?"
            ),
            "entry_condition": (
                "Candidate rows require a completed causal VWAP excursion followed by a reclaim through "
                "VWAP using only bars available at the event timestamp."
            ),
            "target_definition": (
                "Use next-open entry, same-session 15-bar path, configured ES costs, non-overlapping "
                "events, and continuation direction from the VWAP reclaim side."
            ),
        },
    },
    {
        "target_hypothesis_id": "session_compression_breakout_30m_v1",
        "target_family": "es_session_compression_breakout_30m",
        "horizon_label": "30m",
        "target_horizon": {"kind": "fixed_bars", "bar_size": "1m", "bars": 30},
        "exit_rule": {"kind": "fixed_horizon_close"},
        "description": (
            "Proposal-only ES 30-minute target idea conditioned on a causal low-range compression "
            "state followed by a break from the compression box."
        ),
        "novelty_rationale": (
            "Tests compression-to-expansion structure rather than failed extremes, VWAP stretch, "
            "opening-range acceptance, or generic opportunity/risk ranking."
        ),
        "setup_type": "session_compression_breakout",
        "required_inputs": [
            "ES 1-minute OHLCV with session segment IDs",
            "causal rolling compression-window high/low/range state",
            "post-compression break direction",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": [
            "triple_barrier_30m_v1",
            "opening_range_acceptance_continuation_30m_v1",
        ],
        "blocked_reuse_notes": [
            "Do not reuse generic barrier or opening-range branches as fresh compression evidence.",
            "Define compression window and threshold before any conversion or smoke output.",
        ],
        "review_metrics": {
            "implementation_complexity": "medium",
            "leakage_risk": "medium",
            "duplicate_target_risk": "medium",
            "event_density_risk": "medium",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "existing_session_ohlcv_plus_new_causal_compression_state",
        },
        "pre_registration": {
            "research_question": (
                "After an intraday ES compression regime, does a causal break from the compression range "
                "produce cost-clearing 30-minute continuation?"
            ),
            "entry_condition": (
                "Candidate rows require a pre-registered rolling compression window and a break outside "
                "that completed window using only information available at the event timestamp."
            ),
            "target_definition": (
                "Use next-open entry, same-session 30-bar path, configured ES costs, non-overlapping "
                "events, and continuation direction from the compression break side."
            ),
        },
    },
    {
        "target_hypothesis_id": "inside_session_range_breakout_60m_v1",
        "target_family": "es_inside_session_range_breakout_60m",
        "horizon_label": "60m",
        "target_horizon": {"kind": "fixed_bars", "bar_size": "1m", "bars": 60},
        "exit_rule": {"kind": "fixed_horizon_close"},
        "description": (
            "Proposal-only ES 60-minute target idea conditioned on the current regular session trading "
            "inside the prior regular-session range before breaking that prior range."
        ),
        "novelty_rationale": (
            "Different from prior-extreme failure because it tests continuation from a prior-session range "
            "break after inside-range behavior, not rejection back inside a breached extreme."
        ),
        "setup_type": "inside_session_range_breakout",
        "required_inputs": [
            "ES 1-minute OHLCV with regular-session identifiers",
            "prior regular-session high/low available before the current session",
            "causal current-session inside-range state",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": [
            "prior_extreme_failure_30m_v1",
            "opening_range_acceptance_continuation_30m_v1",
        ],
        "blocked_reuse_notes": [
            "Do not reuse rejected prior-extreme-failure evidence as breakout evidence.",
            "Do not proceed unless prior-session range availability and inside-range state are source-tested.",
        ],
        "review_metrics": {
            "implementation_complexity": "medium",
            "leakage_risk": "medium",
            "duplicate_target_risk": "medium",
            "event_density_risk": "medium",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "existing_session_ohlcv_plus_prior_regular_session_range_state",
        },
        "pre_registration": {
            "research_question": (
                "When ES trades inside the prior regular-session range before breaking it, does the break "
                "produce cost-clearing 60-minute continuation?"
            ),
            "entry_condition": (
                "Candidate rows require a pre-registered current-session inside-range state followed by a "
                "break outside the prior regular-session high or low."
            ),
            "target_definition": (
                "Use next-open entry, same-session 60-bar path, configured ES costs, non-overlapping "
                "events, and continuation direction from the prior-range break side."
            ),
        },
    },
    {
        "target_hypothesis_id": "gap_fill_failure_continuation_60m_v1",
        "target_family": "es_gap_fill_failure_continuation_60m",
        "horizon_label": "60m",
        "target_horizon": {"kind": "fixed_bars", "bar_size": "1m", "bars": 60},
        "exit_rule": {"kind": "fixed_horizon_close"},
        "description": (
            "Proposal-only ES 60-minute target idea conditioned on a meaningful overnight gap, a "
            "regular-session attempt to fill toward the prior close, and failure before full fill."
        ),
        "novelty_rationale": (
            "Narrower than a generic overnight-inventory idea because it requires an observed failed "
            "gap-fill attempt before labeling continuation."
        ),
        "setup_type": "gap_fill_failure_continuation",
        "required_inputs": [
            "ES 1-minute OHLCV with regular and overnight session context",
            "prior regular-session close available before the event row",
            "causal gap-fill progress and failure state",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": ["prior_extreme_failure_30m_v1"],
        "blocked_reuse_notes": [
            "Do not retune gap or failure tolerances after seeing discovery output.",
            "Do not treat generic overnight gap behavior as evidence for this failed-fill branch.",
        ],
        "review_metrics": {
            "implementation_complexity": "high",
            "leakage_risk": "high",
            "duplicate_target_risk": "medium",
            "event_density_risk": "medium",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "requires_verified_overnight_session_and_prior_close_context",
        },
        "pre_registration": {
            "research_question": (
                "When ES gaps away from the prior regular-session close and fails a causal gap-fill attempt, "
                "does that failure identify 60-minute continuation in the gap direction?"
            ),
            "entry_condition": (
                "Candidate rows occur after a pre-registered overnight gap and after price moves toward, "
                "but fails to complete, the prior-close fill within a causal tolerance band."
            ),
            "target_definition": (
                "Use next-open entry, same-session 60-bar path, configured ES costs, non-overlapping "
                "events, and continuation direction from the original gap side."
            ),
        },
    },
    {
        "target_hypothesis_id": "midday_liquidity_reversal_15m_v1",
        "target_family": "es_midday_liquidity_reversal_15m",
        "horizon_label": "15m",
        "target_horizon": {"kind": "fixed_bars", "bar_size": "1m", "bars": 15},
        "exit_rule": {"kind": "fixed_horizon_close"},
        "description": (
            "Proposal-only ES 15-minute target idea conditioned on a midday stop-run style extension "
            "beyond a recent local range followed by failure back inside that range."
        ),
        "novelty_rationale": (
            "Materially narrows the broader prior-extreme-failure idea to same-session midday local-range "
            "liquidity events."
        ),
        "setup_type": "midday_local_range_liquidity_reversal",
        "required_inputs": [
            "ES 1-minute OHLCV with session segment IDs",
            "pre-registered midday time window",
            "causal same-session local range high/low",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": ["prior_extreme_failure_30m_v1"],
        "blocked_reuse_notes": [
            "Do not repackage the rejected prior-session extreme failure branch.",
            "Only proceed if same-session local-range sweep logic is separately implemented.",
        ],
        "review_metrics": {
            "implementation_complexity": "medium",
            "leakage_risk": "medium",
            "duplicate_target_risk": "medium",
            "event_density_risk": "high",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "existing_session_ohlcv_plus_new_local_range_state",
        },
        "pre_registration": {
            "research_question": (
                "Do midday ES local-range liquidity sweeps that fail back inside the range identify "
                "cost-clearing 15-minute reversals?"
            ),
            "entry_condition": (
                "Candidate rows occur during a pre-registered midday window after a sweep beyond a completed "
                "same-session local range and close/reentry back inside that range."
            ),
            "target_definition": (
                "Use next-open entry, same-session 15-bar path, configured ES costs, non-overlapping "
                "events, and reversal direction opposite the failed sweep."
            ),
        },
    },
    {
        "target_hypothesis_id": "trend_day_pullback_continuation_60m_v1",
        "target_family": "es_trend_day_pullback_continuation_60m",
        "horizon_label": "60m",
        "target_horizon": {"kind": "fixed_bars", "bar_size": "1m", "bars": 60},
        "exit_rule": {"kind": "fixed_horizon_close"},
        "description": (
            "Proposal-only ES 60-minute target idea conditioned on an established same-session trend "
            "state and a causal pullback that does not break the trend structure."
        ),
        "novelty_rationale": (
            "Tests trend-state pullback continuation at a longer intraday horizon rather than opening-range "
            "acceptance, terminal direction, barrier, VWAP stretch, or component-rank opportunity/risk labels."
        ),
        "setup_type": "trend_day_pullback_continuation",
        "required_inputs": [
            "ES 1-minute OHLCV with session segment IDs",
            "pre-registered causal trend-state filter",
            "causal pullback depth and invalidation state",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": [
            "vol_scaled_terminal_30m_v1",
            "opportunity_risk_component_rank_30m_v1",
        ],
        "blocked_reuse_notes": [
            "Do not reuse rejected terminal-direction or component-rank results as evidence.",
            "Pre-register trend and pullback thresholds before any conversion or smoke output.",
        ],
        "review_metrics": {
            "implementation_complexity": "high",
            "leakage_risk": "medium",
            "duplicate_target_risk": "medium",
            "event_density_risk": "medium",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "existing_session_ohlcv_plus_new_trend_pullback_state",
        },
        "pre_registration": {
            "research_question": (
                "Once ES establishes a same-session trend state, do shallow causal pullbacks produce "
                "learnable 60-minute continuation after realistic costs?"
            ),
            "entry_condition": (
                "Candidate rows require a pre-registered trend-state filter and a pullback depth that remains "
                "inside the allowed trend structure using only causal bars."
            ),
            "target_definition": (
                "Use next-open entry, same-session 60-bar path, configured ES costs, non-overlapping "
                "events, and continuation direction from the trend-state side."
            ),
        },
    },
    {
        "target_hypothesis_id": "opening_range_retest_first_touch_v1",
        "target_family": "es_opening_range_retest_first_touch",
        "horizon_label": "first_touch_45m",
        "target_horizon": {"kind": "event_or_timeout", "bar_size": "1m", "timeout_bars": 45},
        "exit_rule": {"kind": "first_touch_take_profit_or_stop_loss_else_timeout"},
        "description": (
            "Proposal-only ES first-touch target idea conditioned on a completed opening-range break, "
            "a later retest of the broken boundary, and first-touch continuation before a timeout."
        ),
        "novelty_rationale": (
            "Different from frozen opening-range acceptance because it requires retest and first-touch "
            "path behavior rather than fixed-horizon acceptance continuation."
        ),
        "setup_type": "opening_range_retest_first_touch",
        "required_inputs": [
            "ES 1-minute OHLCV with session segment IDs",
            "completed first 30 session bars' opening-range high/low",
            "same-session post-break retest state",
            "pre-registered take-profit, stop-loss, and timeout rules",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": [
            "opening_range_acceptance_continuation_30m_v1",
            "triple_barrier_30m_v1",
        ],
        "blocked_reuse_notes": [
            "Do not reuse frozen opening-range acceptance as fresh first-touch evidence.",
            "Do not tune take-profit, stop-loss, or timeout after inspecting smoke output.",
        ],
        "review_metrics": {
            "implementation_complexity": "high",
            "leakage_risk": "medium",
            "duplicate_target_risk": "medium",
            "event_density_risk": "medium",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "existing_session_ohlcv_plus_new_causal_retest_and_first_touch_state",
        },
        "pre_registration": {
            "research_question": (
                "After ES breaks and retests the completed opening range, does a first-touch rule identify "
                "cost-clearing continuation before a 45-bar timeout?"
            ),
            "entry_condition": (
                "Candidate rows occur after opening range completion, after an earlier same-session range "
                "break, when price causally retests the broken boundary without invalidating the break."
            ),
            "target_definition": (
                "Use next-open entry, same-session first-touch take-profit or stop-loss path with a 45-bar "
                "timeout, configured ES costs, non-overlapping events, and continuation direction from the "
                "prior break side."
            ),
        },
    },
    {
        "target_hypothesis_id": "late_session_range_resolve_session_close_v1",
        "target_family": "es_late_session_range_resolve_session_close",
        "horizon_label": "session_close",
        "target_horizon": {"kind": "session_close", "bar_size": "1m"},
        "exit_rule": {"kind": "session_close"},
        "description": (
            "Proposal-only ES session-close target idea conditioned on a late-session range state and "
            "directional resolution into the regular-session close."
        ),
        "novelty_rationale": (
            "Tests session-close resolution rather than any fixed 30-minute, barrier, VWAP, prior-extreme, "
            "or opening-range target shape."
        ),
        "setup_type": "late_session_range_resolution",
        "required_inputs": [
            "ES 1-minute OHLCV with regular-session identifiers",
            "pre-registered late-session time window",
            "causal late-session range high/low state",
            "regular-session close boundary available from session configuration",
            "configured ES costs and existing path-validity flags",
        ],
        "similar_prior_candidates": [
            "vol_scaled_terminal_30m_v1",
            "opening_range_acceptance_continuation_30m_v1",
        ],
        "blocked_reuse_notes": [
            "Do not reuse fixed-horizon terminal-direction evidence as session-close evidence.",
            "Define late-session window and range state before any conversion or smoke output.",
        ],
        "review_metrics": {
            "implementation_complexity": "high",
            "leakage_risk": "high",
            "duplicate_target_risk": "low",
            "event_density_risk": "medium",
            "cost_sensitivity_risk": "high",
            "data_dependency_status": "requires_verified_regular_session_close_context",
        },
        "pre_registration": {
            "research_question": (
                "Does a causal ES late-session range state identify directional resolution into the "
                "regular-session close after realistic costs?"
            ),
            "entry_condition": (
                "Candidate rows occur during a pre-registered late-session window after a completed "
                "same-session local range and causal break or rejection state."
            ),
            "target_definition": (
                "Use next-open entry, same-session path into the regular-session close, configured ES costs, "
                "non-overlapping events, and direction from the late-session range resolution side."
            ),
        },
    },
)


class GeneratorError(RuntimeError):
    """Raised when candidate generation must fail closed."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _as_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GeneratorError(f"missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GeneratorError(f"invalid {label} JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise GeneratorError(f"{label} must be a JSON object")
    return payload


def _registered_hypothesis_ids(root: Path) -> tuple[set[str], str]:
    registry_path = root / CANONICAL_REGISTRY
    if not registry_path.exists():
        return set(), "missing"
    registry = _read_json(registry_path, label="canonical target registry")
    rows = registry.get("hypotheses")
    if not isinstance(rows, list):
        raise GeneratorError("canonical target registry hypotheses must be a list")
    ids = {
        str(item["target_hypothesis_id"])
        for item in rows
        if isinstance(item, dict) and isinstance(item.get("target_hypothesis_id"), str)
    }
    return ids, "read"


def default_ideation_launcher_path(root: Path) -> Path:
    return root / IDEATION_LAUNCHER_NAME


def ideation_launcher_self_check(*, root: Path, launcher_path: Path) -> dict[str, Any]:
    expected_path = default_ideation_launcher_path(root).resolve()
    resolved_launcher_path = launcher_path.resolve()
    if resolved_launcher_path != expected_path:
        raise GeneratorError(
            "ideation launcher self-check failed: only the repo-local ideation launcher is supported. "
            f"launcher_path={resolved_launcher_path}; expected_launcher_path={expected_path}"
        )
    try:
        text = launcher_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GeneratorError(f"missing ideation launcher file: {launcher_path}") from exc
    required_markers = (
        "scripts.validation.generate_alpha_discovery_candidates",
        "--write-review-packet",
        "--select-implementation",
        "--max-ideas 10",
        "--self-check",
    )
    missing_markers = [marker for marker in required_markers if marker not in text]
    if missing_markers:
        raise GeneratorError(f"ideation launcher is missing required route markers: {missing_markers}")
    return {
        "status": "IDEATION_LAUNCHER_SELF_CHECK_PASS",
        "launcher_path": str(expected_path),
        "template_path": str(expected_path),
        "default_route": (
            "scripts.validation.generate_alpha_discovery_candidates "
            "--write-review-packet --select-implementation"
        ),
        "static_check_only": True,
    }


def _standard_controls() -> list[str]:
    return [
        "compare duplicate overlap with current 15m deadzone target",
        "require class-balance and event-count gates",
        "require fold-stability gates on ES_research_0001 through ES_research_0004",
        "do not tune thresholds, features, costs, folds, markets, or years after seeing discovery output",
    ]


def _standard_stop_rules() -> list[str]:
    return [
        "STOP_INPUT_FAILURE on stale/missing registry, split, feature, cost, or matrix evidence",
        "STOP_CLASS_COLLAPSE if long, short, or flat events fail minimum count or rate gates",
        "STOP_DUPLICATE_TARGET if overlap with the current 15m deadzone target exceeds the registered cap",
        "STOP_UNSTABLE_FOLDS if fewer than half of discovery folds have positive top net",
        "STOP_DISCOVERY_NEGATIVE_NET if discovery top net is nonpositive",
    ]


def _standard_forbidden_actions() -> list[str]:
    return [
        "no WFA/modeling, Phase 8, promotion, paper, or live execution without separate bounded approval",
        "no holdout or forward rows for selection",
        "no threshold, feature, cost, fold, market, or year retuning after discovery output",
        "no reuse as a new hypothesis if stopped",
    ]


def _risk_flags(proposal: dict[str, Any]) -> dict[str, str]:
    return {
        key: value
        for key, value in proposal["review_metrics"].items()
        if key.endswith("_risk") or key == "implementation_complexity"
    }


def _validate_risk_flags(flags: dict[str, str]) -> None:
    invalid = {key: value for key, value in flags.items() if value not in RISK_FLAG_VALUES}
    if invalid:
        raise GeneratorError(f"invalid ideation risk flag values: {invalid}")


def _actual_model_backtest_metrics() -> dict[str, str]:
    return {
        "wfa_metrics": "not_run",
        "phase8_metrics": "not_run",
        "backtest_metrics": "not_run",
        "live_or_paper_metrics": "not_run",
        "promotion_metrics": "not_run",
    }


def _proposal_slug(proposal: dict[str, Any]) -> str:
    candidate_id = str(proposal["target_hypothesis_id"])
    return re.sub(r"_v[0-9]+$", "", candidate_id)


def _proposed_apply_function(proposal: dict[str, Any]) -> str:
    return f"apply_{_proposal_slug(proposal)}_target"


def _proposed_target_columns(proposal: dict[str, Any]) -> list[str]:
    slug = _proposal_slug(proposal)
    return [
        f"target_valid_{slug}",
        f"target_direction_{slug}",
        f"target_gross_dollars_{slug}",
        f"target_cost_dollars_{slug}",
        f"target_net_dollars_{slug}",
        f"target_nonflat_{slug}",
        f"target_entry_ts_{slug}",
        f"target_exit_ts_{slug}",
        f"target_threshold_ticks_{slug}",
    ]


def _proposed_implementation_contract(proposal: dict[str, Any]) -> dict[str, Any]:
    slug = _proposal_slug(proposal)
    return {
        "draft_only": True,
        "applied": False,
        "conversion_required": True,
        "compatible_runnable_harness": None,
        "current_wizard_compatible": False,
        "hypothesis_id": proposal["target_hypothesis_id"],
        "target_family": proposal["target_family"],
        "horizon_label": proposal["horizon_label"],
        "target_horizon": copy.deepcopy(proposal["target_horizon"]),
        "exit_rule": copy.deepcopy(proposal["exit_rule"]),
        "slug": slug,
        "description": proposal["description"],
        "proposed_apply_function": _proposed_apply_function(proposal),
        "proposed_target_columns": _proposed_target_columns(proposal),
        "evaluation_mode": "directional_net",
        "auxiliary_columns": [],
        "component_model_columns": [],
        "rank_score_column": None,
        "threshold_description": (
            "Draft only; implement with configured ES costs and pre-registered causal thresholds before use."
        ),
    }


def _target_construction_contract(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "draft_only": True,
        "applied": False,
        "conversion_required": True,
        "compatible_runnable_harness": None,
        "current_wizard_compatible": False,
        "horizon_label": proposal["horizon_label"],
        "target_horizon": copy.deepcopy(proposal["target_horizon"]),
        "exit_rule": copy.deepcopy(proposal["exit_rule"]),
        "entry_condition": proposal["pre_registration"]["entry_condition"],
        "target_definition": proposal["pre_registration"]["target_definition"],
        "required_inputs": copy.deepcopy(proposal["required_inputs"]),
        "causal_validity_constraints": [
            "use only event-time and prior-bar/session state for entry conditions",
            "do not use future bars to decide whether a row is a candidate event",
            "preserve existing causal_valid, feature_input_valid, feature_row_valid, training_row_valid, and target_valid gates",
        ],
        "path_validity_rules": [
            "same session segment for event, next-open entry, and proposed target path or exit rule",
            "exclude synthetic, invalid, boundary-session, and roll-window rows",
            "use non-overlapping event selection before fold scoring",
        ],
        "cost_handling": [
            "use configs/costs.yaml",
            "include round-turn cost ticks and min_profit_ticks in threshold decisions",
            "do not retune costs after discovery output",
        ],
        "same_session_behavior": "required for entry, path, and exit rule unless a future conversion explicitly proves otherwise",
        "expected_output_columns": _proposed_target_columns(proposal),
        "known_leakage_risks": [
            "event filters must not depend on future high/low/close beyond the prediction timestamp",
            "thresholds and windows must be pre-registered before discovery output is inspected",
        ],
    }


def _source_test_plan(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "draft_only": True,
        "applied": False,
        "conversion_required": True,
        "compatible_runnable_harness": None,
        "current_wizard_compatible": False,
        "pytest_targets": [],
        "test_location_status": "requires_selected_compatible_harness",
        "required_scenarios": [
            f"{proposal['target_hypothesis_id']} creates expected long, short, and flat/invalid examples",
            "entry condition uses only causal information available at the event timestamp",
            "proposed horizon or exit-rule path-validity filters reject insufficient or cross-session paths",
            "cost-aware thresholds affect nonflat labels as expected",
            "target columns are present, typed consistently, and contain no future-derived entry filter leakage",
        ],
    }


def _post_registration_config_spec_draft(proposal: dict[str, Any]) -> dict[str, Any]:
    candidate_id = proposal["target_hypothesis_id"]
    return {
        "draft_only": True,
        "applied": False,
        "conversion_required": True,
        "compatible_runnable_harness": None,
        "current_wizard_compatible": False,
        "runnable": False,
        "reason_not_runnable": (
            "No compatible runnable harness has been selected yet; target construction, source tests, "
            "and registry/status rows must exist before config generation."
        ),
        "schema_version": 1,
        "batch_id": "replace_with_reviewed_batch_id",
        "template_config": "configs/alpha_discovery_runner.example.json",
        "output_config_dir": "configs/alpha_discovery_generated/replace_with_reviewed_batch_id",
        "output_queue": (
            "configs/alpha_discovery_generated/alpha_discovery_queue.replace_with_reviewed_batch_id.json"
        ),
        "max_candidates": 1,
        "candidates": [
            {
                "id": candidate_id,
                "run": f"replace_with_reviewed_batch_id_{candidate_id}",
            }
        ],
    }


def _bounded_run_plan(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "draft_only": True,
        "applied": False,
        "conversion_required": True,
        "compatible_runnable_harness": None,
        "current_wizard_compatible": False,
        "allowed_terminal_wizard_status_after_conversion": "WIZARD_PREFLIGHT_COMPLETE",
        "steps": [
            "Choose or build a compatible Phase 9 harness for this idea's target horizon and exit rule.",
            "Implement only this selected target construction in the compatible harness.",
            "Add focused source tests for that harness and run only those source tests.",
            "Append real registry/status rows only after explicit approval.",
            "Generate candidate config/queue artifacts only after the selected candidate passes the canonical gate.",
            "Run wizard preflight/generation and stop at WIZARD_PREFLIGHT_COMPLETE.",
        ],
        "must_stop_before": [
            "optional discovery prompt",
            "discovery-run",
            "confirmation smoke",
            "locked smoke",
            "WFA/modeling",
            "Phase 8",
            "promotion",
            "paper/live execution",
        ],
        "blocked_actions": [
            "WFA",
            "Phase 8",
            "discovery-run without separate bounded approval",
            "promotion",
            "staging",
            "commit",
            "push",
            "paper/live execution",
            "registry/status mutation without explicit approval",
            "config generation before conversion to a compatible runnable harness",
        ],
    }


def _selected_candidate_next_prompt(proposal: dict[str, Any]) -> str:
    candidate_id = proposal["target_hypothesis_id"]
    return (
        f"Implement only this selected candidate from its draft JSON: {candidate_id}.\n\n"
        "Use the JSON dossier as a draft-only implementation handoff. Convert this selected idea to a runnable "
        "Phase 9 candidate by choosing or building a compatible harness for its target horizon and exit rule, "
        "implementing target construction, and adding focused source tests. Stop before any discovery-run. Do not run or "
        "perform any of the following without separate explicit approval: WFA, Phase 8, discovery-run, promotion, "
        "staging, commit, push, paper/live execution, or registry/status mutation. The only allowed wizard terminal "
        "status after conversion is WIZARD_PREFLIGHT_COMPLETE."
    )


def _registry_patch_draft(proposal: dict[str, Any]) -> dict[str, Any]:
    pre_registration = copy.deepcopy(proposal["pre_registration"])
    pre_registration["horizon_label"] = proposal["horizon_label"]
    pre_registration["target_horizon"] = copy.deepcopy(proposal["target_horizon"])
    pre_registration["exit_rule"] = copy.deepcopy(proposal["exit_rule"])
    pre_registration["controls"] = _standard_controls()
    pre_registration["discovery_success_rule"] = (
        "Discovery can advance only if the registered bounded smoke reports DISCOVERY_PASS with "
        "positive stage net, at least half of discovery folds positive, nonconstant predictions, "
        "sufficient event/class balance, and duplicate overlap at or below the registered cap."
    )
    pre_registration["stop_rules"] = _standard_stop_rules()
    pre_registration["forbidden_actions"] = _standard_forbidden_actions()
    pre_registration["implementation_status"] = (
        "Proposal only; not registered, no compatible runnable harness selected, and not runnable by the wizard."
    )
    return {
        "target_hypothesis_id": proposal["target_hypothesis_id"],
        "status": "CANDIDATE",
        "wfa_allowed": False,
        "target_family": proposal["target_family"],
        "horizon_label": proposal["horizon_label"],
        "target_horizon": copy.deepcopy(proposal["target_horizon"]),
        "exit_rule": copy.deepcopy(proposal["exit_rule"]),
        "conversion_required": True,
        "compatible_runnable_harness": None,
        "current_wizard_compatible": False,
        "scope": {
            "profile": "tier_1",
            "resolved_profile": "tier_1_research",
            "markets": ["ES"],
            "years": [2023, 2024],
        },
        "description": proposal["description"],
        "status_reason": "Draft proposal only; not registered until explicitly approved and written to manifests.",
        "pre_registration": pre_registration,
        "source_reports": [],
        "next_allowed_actions": ["CONVERT_TO_RUNNABLE_HARNESS_AND_SOURCE_TESTS"],
    }


def _trial_status_patch_draft(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "hypothesis_id": proposal["target_hypothesis_id"],
        "trial_id": f"{proposal['target_hypothesis_id']}_candidate",
        "stage": "register_candidate",
        "status": "CANDIDATE",
        "evidence": [],
        "notes": (
            "Draft proposal only. Do not run WFA, Phase 8, promotion, paper, live execution, or discovery "
            "until this candidate is explicitly registered and implemented with bounded source tests."
        ),
    }


def ideate_strategy_candidates(*, root: Path, max_ideas: int = DEFAULT_IDEATION_MAX_CANDIDATES) -> dict[str, Any]:
    if max_ideas <= 0:
        raise GeneratorError("max_ideas must be a positive integer")
    if max_ideas > HARD_MAX_CANDIDATES:
        raise GeneratorError(f"max_ideas {max_ideas} exceeds hard cap {HARD_MAX_CANDIDATES}")
    existing_ids, registry_status = _registered_hypothesis_ids(root)
    selected: list[dict[str, Any]] = []
    for proposal in IDEATION_LIBRARY:
        if proposal["target_hypothesis_id"] in existing_ids:
            continue
        candidate_index = len(selected) + 1
        _candidate_packet_filename(candidate_index, proposal, "md")
        _candidate_packet_filename(candidate_index, proposal, "json")
        risk_flags = _risk_flags(proposal)
        _validate_risk_flags(risk_flags)
        registry_patch_draft = _registry_patch_draft(proposal)
        selected.append(
            {
                "target_hypothesis_id": proposal["target_hypothesis_id"],
                "schema_version": 2,
                "generated_by": IDEATION_GENERATOR_ID,
                "draft_only": True,
                "applied": False,
                "conversion_required": True,
                "compatible_runnable_harness": None,
                "current_wizard_compatible": False,
                "horizon_label": proposal["horizon_label"],
                "target_horizon": copy.deepcopy(proposal["target_horizon"]),
                "exit_rule": copy.deepcopy(proposal["exit_rule"]),
                "evidence_status": "not_model_trust_evidence",
                "actual_model_backtest_metrics": _actual_model_backtest_metrics(),
                "requires_explicit_approval_before_registry_status_mutation": True,
                "review_card": {
                    "target_hypothesis_id": proposal["target_hypothesis_id"],
                    "target_family": proposal["target_family"],
                    "setup_type": proposal["setup_type"],
                    "horizon_label": proposal["horizon_label"],
                    "target_horizon": copy.deepcopy(proposal["target_horizon"]),
                    "exit_rule": copy.deepcopy(proposal["exit_rule"]),
                    "conversion_required": True,
                    "compatible_runnable_harness": None,
                    "current_wizard_compatible": False,
                    "strategy_summary": proposal["description"],
                    "plain_english_strategy": proposal["description"],
                    "novelty_rationale": proposal["novelty_rationale"],
                    "risk_flags": risk_flags,
                    "data_dependency_status": proposal["review_metrics"]["data_dependency_status"],
                    "wizard_readiness_status": "not_runnable",
                    "evidence_status": "not_model_trust_evidence",
                    "review_decision_required": "Approve, edit, or reject before implementation or registration.",
                    "matching_json_path": None,
                },
                "proposed_implementation_contract": _proposed_implementation_contract(proposal),
                "target_construction_contract": _target_construction_contract(proposal),
                "source_test_plan": _source_test_plan(proposal),
                "registry_patch_draft": registry_patch_draft,
                "trial_status_patch_draft": _trial_status_patch_draft(proposal),
                "post_registration_config_spec_draft": _post_registration_config_spec_draft(proposal),
                "bounded_run_plan": _bounded_run_plan(proposal),
                "selected_candidate_next_prompt": _selected_candidate_next_prompt(proposal),
            }
        )
        if len(selected) >= max_ideas:
            break
    return {
        "schema_version": 2,
        "generated_by": IDEATION_GENERATOR_ID,
        "status": "STRATEGY_CANDIDATE_IDEATION_READY",
        "stamp": IDEATION_STAMP,
        "proposal_only": True,
        "generated_runnable_configs": False,
        "candidate_count": len(selected),
        "max_ideas": max_ideas,
        "registry_status": registry_status,
        "excluded_existing_candidate_count": len(existing_ids),
        "candidates": selected,
        "safety": {
            "registry_status_mutated": False,
            "target_specs_mutated": False,
            "wizard_run": False,
            "review_packet_written": False,
            "reports_written": False,
            "configs_written": False,
            "data_written": False,
            "logs_written": False,
            "models_written": False,
            "wfa_run": False,
            "phase8_run": False,
            "promotion_or_deployment_evidence": False,
            "staging_commits_pushes": False,
        },
    }


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _assert_under_reports(root: Path, path: Path, *, field: str) -> None:
    _assert_under(root, path, root / "reports", field=field)


def _markdown_list(items: list[str]) -> list[str]:
    if not items:
        return ["- None."]
    return [f"- {item}" for item in items]


def _candidate_file_stem(index: int, candidate: dict[str, Any]) -> str:
    return f"{index:03d}_{candidate['target_hypothesis_id']}"


def _candidate_packet_filename(index: int, candidate: dict[str, Any], suffix: str) -> str:
    name = f"{_candidate_file_stem(index, candidate)}.{suffix}"
    if not re.fullmatch(CANDIDATE_PACKET_FILENAME_RE, name):
        raise GeneratorError(
            f"candidate packet filename must match {CANDIDATE_PACKET_FILENAME_RE!r}; got {name!r}"
        )
    return name


def _marked_v2_file(path: Path) -> bool:
    if path.suffix.lower() == ".md":
        try:
            return MARKDOWN_GENERATOR_MARKER in path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return False
        return isinstance(payload, dict) and payload.get("generated_by") == IDEATION_GENERATOR_ID
    return False


def _archive_dir(review_root: Path, timestamp: str) -> Path:
    archive_root = review_root / "_archive"
    candidate = archive_root / timestamp
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        suffixed = archive_root / f"{timestamp}_{index:03d}"
        if not suffixed.exists():
            return suffixed
    raise GeneratorError(f"could not allocate archive directory under {_relative(review_root, archive_root)}")


def _archive_unmarked_candidate_files(*, root: Path, review_root: Path, timestamp: str) -> dict[str, Any]:
    if not review_root.exists():
        return {"archive_dir": None, "moved_files": []}
    candidates = [
        path
        for path in review_root.iterdir()
        if path.is_file()
        and re.fullmatch(CANDIDATE_PACKET_FILENAME_RE, path.name)
        and not _marked_v2_file(path)
    ]
    if not candidates:
        return {"archive_dir": None, "moved_files": []}
    archive_dir = _archive_dir(review_root, timestamp)
    archive_dir.mkdir(parents=True, exist_ok=False)
    moved: list[dict[str, str]] = []
    for path in sorted(candidates, key=lambda item: item.name):
        destination = archive_dir / path.name
        shutil.move(str(path), str(destination))
        moved.append(
            {
                "from": _relative(root, path),
                "to": _relative(root, destination),
            }
        )
    return {
        "archive_dir": _relative(root, archive_dir),
        "moved_files": moved,
    }


def _markdown_candidate_packet(
    *,
    payload: dict[str, Any],
    candidate: dict[str, Any],
    index: int,
    json_path: str,
) -> str:
    review_card = candidate["review_card"]
    risk_flags = review_card["risk_flags"]
    lines = [
        MARKDOWN_GENERATOR_MARKER,
        f"# {index:03d} {candidate['target_hypothesis_id']}",
        "",
        f"- matching_json_path: {json_path}",
        f"- target_family: {review_card['target_family']}",
        f"- setup_type: {review_card['setup_type']}",
        f"- horizon_label: {review_card['horizon_label']}",
        f"- conversion_required: {str(review_card['conversion_required']).lower()}",
        f"- current_wizard_compatible: {str(review_card['current_wizard_compatible']).lower()}",
        f"- wizard_readiness_status: {review_card['wizard_readiness_status']}",
        f"- evidence_status: {review_card['evidence_status']}",
        "",
        "## Plain English Strategy",
        "",
        review_card["plain_english_strategy"],
        "",
        "## Risk Flags",
        "",
        f"- implementation_complexity: {risk_flags['implementation_complexity']}",
        f"- leakage_risk: {risk_flags['leakage_risk']}",
        f"- duplicate_target_risk: {risk_flags['duplicate_target_risk']}",
        f"- event_density_risk: {risk_flags['event_density_risk']}",
        f"- cost_sensitivity_risk: {risk_flags['cost_sensitivity_risk']}",
        f"- data_dependency_status: {review_card['data_dependency_status']}",
        "",
        "## Decision",
        "",
        "- Approve, edit, or reject this candidate before any conversion, implementation, or registration work.",
        "- This is not implemented, not registered, not compatible with the current wizard, and not model-trust evidence.",
        "- Use the matching JSON only as a draft handoff after selecting this candidate.",
        "",
        "## Boundary",
        "",
        "- Do not mutate registry/status, convert to a runnable harness, run the wizard, run WFA, run Phase 8, promote, stage, commit, push, paper trade, or live trade from this Markdown review card.",
    ]
    return "\n".join(lines)


def write_review_packet(
    *,
    root: Path,
    max_ideas: int = DEFAULT_IDEATION_MAX_CANDIDATES,
    review_root: Path | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    review_root = review_root or (root / IDEATION_REPORT_ROOT)
    if not review_root.is_absolute():
        review_root = root / review_root
    _assert_under_reports(root, review_root, field="review_root")
    if timestamp is not None:
        _require_safe_token(timestamp, field="review packet timestamp")
    payload = ideate_strategy_candidates(root=root, max_ideas=max_ideas)
    packet_timestamp = timestamp or _timestamp()
    packet_safety = {
        **payload["safety"],
        "review_packet_written": True,
        "reports_written": True,
    }
    payload = {
        **payload,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "safety": packet_safety,
        "review_packet": {
            "output_dir": _relative(root, review_root),
            "layout": "direct_numbered_candidate_files",
            "timestamp": packet_timestamp,
            "candidate_files": [],
            "archive": {"archive_dir": None, "moved_files": []},
        },
    }
    archive = _archive_unmarked_candidate_files(root=root, review_root=review_root, timestamp=packet_timestamp)
    payload["review_packet"]["archive"] = archive
    review_root.mkdir(parents=True, exist_ok=True)
    candidate_files: list[dict[str, Any]] = []
    for index, candidate in enumerate(payload["candidates"], start=1):
        json_name = _candidate_packet_filename(index, candidate, "json")
        markdown_name = _candidate_packet_filename(index, candidate, "md")
        json_path = review_root / json_name
        markdown_path = review_root / markdown_name
        relative_json_path = _relative(root, json_path)
        review_card = copy.deepcopy(candidate["review_card"])
        if review_card["wizard_readiness_status"] not in WIZARD_READINESS_VALUES:
            raise GeneratorError(f"invalid wizard readiness status: {review_card['wizard_readiness_status']}")
        review_card["matching_json_path"] = relative_json_path
        candidate_payload = {
            "schema_version": 2,
            "generated_by": IDEATION_GENERATOR_ID,
            "status": payload["status"],
            "stamp": payload["stamp"],
            "created_at_utc": payload["created_at_utc"],
            "draft_only": True,
            "applied": False,
            "conversion_required": candidate["conversion_required"],
            "compatible_runnable_harness": candidate["compatible_runnable_harness"],
            "current_wizard_compatible": candidate["current_wizard_compatible"],
            "horizon_label": candidate["horizon_label"],
            "target_horizon": candidate["target_horizon"],
            "exit_rule": candidate["exit_rule"],
            "evidence_status": "not_model_trust_evidence",
            "actual_model_backtest_metrics": candidate["actual_model_backtest_metrics"],
            "requires_explicit_approval_before_registry_status_mutation": True,
            "candidate_index": index,
            "candidate_count": payload["candidate_count"],
            "target_hypothesis_id": candidate["target_hypothesis_id"],
            "review_card": review_card,
            "proposed_implementation_contract": candidate["proposed_implementation_contract"],
            "target_construction_contract": candidate["target_construction_contract"],
            "source_test_plan": candidate["source_test_plan"],
            "registry_patch_draft": candidate["registry_patch_draft"],
            "trial_status_patch_draft": candidate["trial_status_patch_draft"],
            "post_registration_config_spec_draft": candidate["post_registration_config_spec_draft"],
            "bounded_run_plan": candidate["bounded_run_plan"],
            "selected_candidate_next_prompt": candidate["selected_candidate_next_prompt"],
            "safety": packet_safety,
        }
        _write_json(json_path, candidate_payload)
        markdown_path.write_text(
            _markdown_candidate_packet(
                payload=payload,
                candidate={**candidate, "review_card": review_card},
                index=index,
                json_path=relative_json_path,
            )
            + "\n",
            encoding="utf-8",
        )
        candidate_files.append(
            {
                "index": index,
                "target_hypothesis_id": candidate["target_hypothesis_id"],
                "markdown_path": _relative(root, markdown_path),
                "json_path": _relative(root, json_path),
            }
        )
    payload["review_packet"]["candidate_files"] = candidate_files
    return {
        "status": "STRATEGY_CANDIDATE_REVIEW_PACKET_WRITTEN",
        "stamp": payload["stamp"],
        "proposal_only": True,
        "candidate_count": payload["candidate_count"],
        "output_dir": _relative(root, review_root),
        "packet_timestamp": packet_timestamp,
        "candidate_files": candidate_files,
        "archive": archive,
        "safety": packet_safety,
    }


def _parse_implementation_selection(raw_selection: str, *, candidate_count: int) -> list[int] | None:
    selection = raw_selection.strip()
    if not selection or selection.lower() in {"skip", "cancel"}:
        return None
    if selection.lower() == "all":
        return list(range(1, candidate_count + 1))

    tokens = [token for token in re.split(r"[\s,]+", selection) if token]
    if any(token.lower() in {"all", "skip", "cancel"} for token in tokens):
        raise GeneratorError("selection must be all, skip/cancel, or candidate numbers only")
    selected: list[int] = []
    seen: set[int] = set()
    for token in tokens:
        if not token.isdigit():
            raise GeneratorError(f"invalid candidate selection token: {token!r}")
        value = int(token)
        if value < 1 or value > candidate_count:
            raise GeneratorError(f"candidate selection {value} is out of range 1..{candidate_count}")
        if value not in seen:
            selected.append(value)
            seen.add(value)
    if not selected:
        return None
    return selected


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _implementation_selection_path(root: Path, payload: dict[str, Any]) -> Path:
    output_dir = payload.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir:
        raise GeneratorError("review packet output_dir is required before implementation selection")
    return _as_path(root, output_dir) / IMPLEMENTATION_SELECTION_FILENAME


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _write_implementation_selection(
    *,
    root: Path,
    review_packet: dict[str, Any],
    raw_selection: str,
    selected_indices: list[int],
) -> dict[str, Any]:
    candidate_files = review_packet.get("candidate_files")
    if not isinstance(candidate_files, list):
        raise GeneratorError("review packet candidate_files must be a list before implementation selection")
    by_index = {
        item.get("index"): item
        for item in candidate_files
        if isinstance(item, dict) and isinstance(item.get("index"), int)
    }
    selected_candidates: list[dict[str, Any]] = []
    for index in selected_indices:
        item = by_index.get(index)
        if not isinstance(item, dict):
            raise GeneratorError(f"candidate selection {index} is missing from review packet")
        json_path_text = item.get("json_path")
        markdown_path_text = item.get("markdown_path")
        candidate_id = item.get("target_hypothesis_id")
        if not all(isinstance(value, str) and value for value in (json_path_text, markdown_path_text, candidate_id)):
            raise GeneratorError(f"candidate selection {index} has incomplete review packet paths")
        json_path = _as_path(root, json_path_text)
        selected_candidates.append(
            {
                "index": index,
                "target_hypothesis_id": candidate_id,
                "markdown_path": markdown_path_text,
                "json_path": json_path_text,
                "json_sha256": _sha256_file(json_path),
            }
        )

    selection_path = _implementation_selection_path(root, review_packet)
    _assert_under_reports(root, selection_path, field="implementation_selection")
    selection_payload = {
        "schema_version": 1,
        "status": "IMPLEMENTATION_SELECTION_READY",
        "generated_by": IMPLEMENTATION_SELECTION_GENERATOR_ID,
        "selection_source": "review_packet_candidate_files",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_review_dir": review_packet["output_dir"],
        "source_packet_timestamp": review_packet.get("packet_timestamp"),
        "raw_selection": raw_selection,
        "selected_candidate_count": len(selected_candidates),
        "selected_candidates": selected_candidates,
        "blocked_actions": [
            "not registry/status approval",
            "not implementation approval",
            "not discovery approval",
            "no WFA",
            "no Phase 8",
            "no promotion",
            "no staging",
            "no commit",
            "no push",
            "no paper/live execution",
        ],
        "next_step": (
            "Codex implementation must verify every selected JSON file still matches json_sha256 "
            "before converting to a runnable harness, changing code, tests, or registry/status."
        ),
    }
    _write_json_atomic(selection_path, selection_payload)
    return {
        "status": "READY",
        "selection_path": _relative(root, selection_path),
        "selected_candidate_count": len(selected_candidates),
        "selected_candidate_ids": [item["target_hypothesis_id"] for item in selected_candidates],
    }


def select_implementation_candidates(
    *,
    root: Path,
    review_packet: dict[str, Any],
    raw_selection: str,
) -> tuple[dict[str, Any], int]:
    candidate_count = int(review_packet.get("candidate_count") or 0)
    try:
        selected_indices = _parse_implementation_selection(raw_selection, candidate_count=candidate_count)
    except GeneratorError as exc:
        return {
            "status": "FAILED",
            "raw_selection": raw_selection,
            "failure": str(exc),
        }, 1
    if selected_indices is None:
        return {
            "status": "SKIPPED",
            "raw_selection": raw_selection,
            "selection_path": _relative(root, _implementation_selection_path(root, review_packet)),
            "selected_candidate_count": 0,
        }, 0
    return _write_implementation_selection(
        root=root,
        review_packet=review_packet,
        raw_selection=raw_selection,
        selected_indices=selected_indices,
    ), 0


def _display_path(root: Path, path_text: str | None) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.is_absolute():
        path = root / path
    return str(path)


def _print_review_packet_console_summary(root: Path, payload: dict[str, Any]) -> None:
    print("", file=sys.stderr)
    print(f"Review directory: {_display_path(root, payload.get('output_dir'))}", file=sys.stderr)
    print("Written candidate files:", file=sys.stderr)
    for candidate_file in payload.get("candidate_files", []):
        print(f"  Markdown: {_display_path(root, candidate_file.get('markdown_path'))}", file=sys.stderr)
        print(f"  JSON: {_display_path(root, candidate_file.get('json_path'))}", file=sys.stderr)
    archive = payload.get("archive")
    if isinstance(archive, dict) and archive.get("archive_dir"):
        print(f"Archive directory: {_display_path(root, archive.get('archive_dir'))}", file=sys.stderr)
        print("Archived candidate files:", file=sys.stderr)
        for moved_file in archive.get("moved_files", []):
            print(
                "  "
                f"{_display_path(root, moved_file.get('from'))} -> "
                f"{_display_path(root, moved_file.get('to'))}",
                file=sys.stderr,
            )


def _print_implementation_selection_prompt() -> str:
    print("", file=sys.stderr)
    print("Type candidate numbers to prepare for implementation, or skip:", file=sys.stderr)
    return sys.stdin.readline()


def _print_implementation_selection_summary(root: Path, payload: dict[str, Any]) -> None:
    selection = payload.get("implementation_selection")
    if not isinstance(selection, dict):
        return
    print("", file=sys.stderr)
    if selection.get("status") == "READY":
        print(f"Implementation selection: {_display_path(root, selection.get('selection_path'))}", file=sys.stderr)
        print("Selected candidates:", file=sys.stderr)
        for candidate_id in selection.get("selected_candidate_ids", []):
            print(f"  {candidate_id}", file=sys.stderr)
    elif selection.get("status") == "SKIPPED":
        print("Implementation selection skipped.", file=sys.stderr)
    elif selection.get("status") == "FAILED":
        print(f"Implementation selection failed: {selection.get('failure')}", file=sys.stderr)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _require_string(payload: dict[str, Any], key: str, *, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GeneratorError(f"{label} field {key!r} is required")
    return value.strip()


def _require_safe_token(value: str, *, field: str) -> None:
    if not SAFE_TOKEN_RE.fullmatch(value):
        raise GeneratorError(
            f"{field} must match {SAFE_TOKEN_RE.pattern!r}; got {value!r}"
        )


def _assert_under(root: Path, path: Path, base: Path, *, field: str) -> None:
    resolved = path.resolve()
    resolved_base = base.resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError as exc:
        rel_base = _relative(root, resolved_base)
        raise GeneratorError(f"{field} must be under {rel_base}: {_relative(root, path)}") from exc


def _assert_under_root(root: Path, path: Path, *, field: str) -> None:
    _assert_under(root, path, root, field=field)


def _assert_under_configs(root: Path, path: Path, *, field: str) -> None:
    _assert_under(root, path, root / "configs", field=field)


def _is_canonical_path(root: Path, value: str, canonical_path: Path) -> bool:
    return _as_path(root, value).resolve() == (root / canonical_path).resolve()


def _require_canonical_path(root: Path, value: Any, *, field: str, canonical_path: Path) -> None:
    if not isinstance(value, str) or not value.strip():
        raise GeneratorError(f"{field} must be a non-empty canonical path")
    if not _is_canonical_path(root, value.strip(), canonical_path):
        raise GeneratorError(
            f"{field} must be {_relative(root, root / canonical_path)}; got {value!r}"
        )


def _require_canonical_config_paths(config: dict[str, Any], *, root: Path, candidate_id: str) -> None:
    if "target_registry" in config:
        _require_canonical_path(
            root,
            config["target_registry"],
            field=f"{candidate_id} target_registry",
            canonical_path=CANONICAL_REGISTRY,
        )
    if "target_trial_statuses" in config:
        _require_canonical_path(
            root,
            config["target_trial_statuses"],
            field=f"{candidate_id} target_trial_statuses",
            canonical_path=CANONICAL_TRIAL_STATUSES,
        )

    command = config.get("discovery_command")
    if not isinstance(command, list):
        return
    for flag, canonical_path in (
        ("--target-registry", CANONICAL_REGISTRY),
        ("--target-trial-statuses", CANONICAL_TRIAL_STATUSES),
    ):
        for index, part in enumerate(command):
            if part != flag:
                continue
            if index + 1 >= len(command):
                raise GeneratorError(f"{candidate_id} discovery_command {flag} is missing a value")
            _require_canonical_path(
                root,
                command[index + 1],
                field=f"{candidate_id} discovery_command {flag}",
                canonical_path=canonical_path,
            )


def _replace_placeholders(value: Any, *, candidate_id: str, run: str) -> Any:
    if isinstance(value, str):
        return value.replace(ID_PLACEHOLDER, candidate_id).replace(RUN_PLACEHOLDER, run)
    if isinstance(value, list):
        return [
            _replace_placeholders(item, candidate_id=candidate_id, run=run)
            for item in value
        ]
    if isinstance(value, dict):
        return {
            _replace_placeholders(key, candidate_id=candidate_id, run=run): _replace_placeholders(
                item,
                candidate_id=candidate_id,
                run=run,
            )
            for key, item in value.items()
        }
    return value


def _normalize_candidates(payload: dict[str, Any]) -> tuple[int, list[dict[str, str]]]:
    max_candidates = payload.get("max_candidates")
    if not isinstance(max_candidates, int) or max_candidates <= 0:
        raise GeneratorError("spec field 'max_candidates' must be a positive integer")
    if max_candidates > HARD_MAX_CANDIDATES:
        raise GeneratorError(
            f"spec max_candidates {max_candidates} exceeds hard cap {HARD_MAX_CANDIDATES}"
        )

    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise GeneratorError("spec candidates must contain at least one entry")
    if len(raw_candidates) > max_candidates:
        raise GeneratorError(
            f"spec has {len(raw_candidates)} candidates but max_candidates is {max_candidates}"
        )
    if len(raw_candidates) > HARD_MAX_CANDIDATES:
        raise GeneratorError(
            f"spec has {len(raw_candidates)} candidates but hard cap is {HARD_MAX_CANDIDATES}"
        )

    candidates: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw_candidates, start=1):
        if not isinstance(entry, dict):
            raise GeneratorError(f"candidate entry {index} must be a JSON object")
        candidate_id = _require_string(entry, "id", label=f"candidate entry {index}")
        run = _require_string(entry, "run", label=f"candidate {candidate_id}")
        _require_safe_token(candidate_id, field=f"candidate {candidate_id} id")
        _require_safe_token(run, field=f"candidate {candidate_id} run")
        if candidate_id in seen_ids:
            raise GeneratorError(f"duplicate candidate id: {candidate_id}")
        seen_ids.add(candidate_id)
        candidates.append({"id": candidate_id, "run": run})
    return max_candidates, candidates


def _registry_entry(registry: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    rows = registry.get("hypotheses")
    if not isinstance(rows, list):
        raise GeneratorError("canonical target registry hypotheses must be a list")
    matches = [
        item
        for item in rows
        if isinstance(item, dict) and item.get("target_hypothesis_id") == candidate_id
    ]
    if len(matches) != 1:
        raise GeneratorError(
            f"expected exactly one canonical registry entry for {candidate_id!r}; found {len(matches)}"
        )
    return matches[0]


def _trial_status_entries(path: Path, candidate_id: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise GeneratorError(f"missing canonical trial-status ledger: {path}")
    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GeneratorError(
                f"invalid canonical trial-status JSONL line {line_number}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise GeneratorError(f"canonical trial-status line {line_number} is not an object")
        if payload.get("hypothesis_id") == candidate_id:
            entries.append(payload)
    return entries


def _target_specs() -> dict[str, Any]:
    from scripts.phase9_research.es_30m_target_smoke_harness import TARGET_SPECS

    return TARGET_SPECS


def _validate_canonical_candidate(candidate_id: str, *, root: Path) -> None:
    target_specs = _target_specs()
    if candidate_id not in target_specs:
        raise GeneratorError(
            f"{candidate_id!r} is not supported by the ES 30m target smoke harness"
        )

    registry = _read_json(root / CANONICAL_REGISTRY, label="canonical target registry")
    entry = _registry_entry(registry, candidate_id)
    target_spec = target_specs[candidate_id]
    failures: list[str] = []

    if entry.get("status") != "CANDIDATE":
        failures.append("registry status must be CANDIDATE")
    if entry.get("wfa_allowed") is not False:
        failures.append("registry wfa_allowed must be false")
    if entry.get("source_reports") != []:
        failures.append("registry source_reports must be empty before discovery")
    if entry.get("target_family") != target_spec.target_family:
        failures.append(f"registry target_family must be {target_spec.target_family}")

    scope = entry.get("scope")
    if not isinstance(scope, dict):
        failures.append("registry scope must be an object")
    else:
        if scope.get("profile") != "tier_1":
            failures.append("registry scope.profile must be tier_1")
        if scope.get("markets") != ["ES"]:
            failures.append("registry scope.markets must be ['ES']")
        if scope.get("years") != [2023, 2024]:
            failures.append("registry scope.years must be [2023, 2024]")

    trial_entries = _trial_status_entries(root / CANONICAL_TRIAL_STATUSES, candidate_id)
    if not trial_entries:
        failures.append("candidate is missing from canonical trial-status ledger")
    else:
        latest = trial_entries[-1]
        if latest.get("status") != "CANDIDATE":
            failures.append("latest trial status must be CANDIDATE")
        if latest.get("stage") != "register_candidate":
            failures.append("latest trial stage must be register_candidate")
        if latest.get("evidence") != []:
            failures.append("latest trial evidence must be empty before discovery")

    if failures:
        raise GeneratorError(
            f"{candidate_id} is not canonical Phase 9 target-discovery ready: "
            + "; ".join(failures)
        )


def _generated_config(
    template: dict[str, Any],
    *,
    root: Path,
    candidate_id: str,
    run: str,
) -> dict[str, Any]:
    config = copy.deepcopy(template)
    config.pop("template", None)
    config = _replace_placeholders(config, candidate_id=candidate_id, run=run)
    if not isinstance(config, dict):
        raise GeneratorError(f"generated config for {candidate_id} is not a JSON object")
    config["runner_mode"] = "preflight"
    if config.get("hypothesis_id") != candidate_id:
        raise GeneratorError(f"generated config hypothesis_id must be {candidate_id}")
    _require_canonical_config_paths(config, root=root, candidate_id=candidate_id)
    single_runner.validate_runner_config(config, mode="preflight")
    single_runner.validate_runner_config(config, mode="discovery-packet")
    return config


def generate_from_spec(*, spec_path: Path, root: Path) -> dict[str, Any]:
    spec = _read_json(spec_path, label="candidate generation spec")
    if spec.get("schema_version") != 1:
        raise GeneratorError("spec schema_version must be 1")

    batch_id = _require_string(spec, "batch_id", label="spec")
    _require_safe_token(batch_id, field="batch_id")
    template_path = _as_path(root, _require_string(spec, "template_config", label="spec"))
    output_config_dir = _as_path(root, _require_string(spec, "output_config_dir", label="spec"))
    output_queue = _as_path(root, _require_string(spec, "output_queue", label="spec"))
    _assert_under_root(root, template_path, field="template_config")
    _assert_under_configs(root, output_config_dir, field="output_config_dir")
    _assert_under_configs(root, output_queue, field="output_queue")

    max_candidates, candidates = _normalize_candidates(spec)
    template = _read_json(template_path, label="template config")
    for candidate in candidates:
        _validate_canonical_candidate(candidate["id"], root=root)

    generated_configs: list[tuple[Path, dict[str, Any]]] = []
    queue_entries: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate["id"]
        config_path = output_config_dir / f"alpha_discovery_runner.{candidate_id}.json"
        _assert_under_configs(root, config_path, field=f"candidate {candidate_id} config")
        config = _generated_config(
            template,
            root=root,
            candidate_id=candidate_id,
            run=candidate["run"],
        )
        generated_configs.append((config_path, config))
        queue_entries.append(
            {
                "id": candidate_id,
                "config": _relative(root, config_path),
                "approved": False,
            }
        )

    queue = {
        "schema_version": 1,
        "runner_mode": "preflight",
        "max_candidates": max_candidates,
        "stop_on_infrastructure_failure": True,
        "log_root": "logs/alpha_discovery_queue",
        "candidates": queue_entries,
    }

    outputs = [path for path, _ in generated_configs] + [output_queue]
    existing = [_relative(root, path) for path in outputs if path.exists()]
    if existing:
        raise GeneratorError(f"output file already exists; refusing overwrite: {existing}")

    for path, config in generated_configs:
        _write_json(path, config)
    _write_json(output_queue, queue)

    return {
        "status": "GENERATOR_COMPLETED",
        "generated": True,
        "batch_id": batch_id,
        "candidate_count": len(candidates),
        "max_candidates": max_candidates,
        "mode": "preflight",
        "config_paths": [_relative(root, path) for path, _ in generated_configs],
        "queue_path": _relative(root, output_queue),
        "writes_restricted_to_configs": True,
        "registry_status_mutated": False,
        "reports_data_models_or_logs_written": False,
        "canonical_candidate_gate": "passed",
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generate-candidates",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--spec",
        help=(
            "candidate generation spec JSON; when omitted, print proposal-only strategy "
            "candidate ideation instead of writing config artifacts"
        ),
    )
    parser.add_argument(
        "--max-ideas",
        type=int,
        default=DEFAULT_IDEATION_MAX_CANDIDATES,
        help="maximum proposal-only ideation candidates to print when --spec is omitted",
    )
    parser.add_argument(
        "--write-review-packet",
        action="store_true",
        help="write a timestamped Markdown and JSON ideation review packet under reports/",
    )
    parser.add_argument(
        "--select-implementation",
        action="store_true",
        help="after writing a review packet, prompt for candidate numbers and write a shortlist under the review root",
    )
    parser.add_argument(
        "--review-root",
        default=IDEATION_REPORT_ROOT.as_posix(),
        help="review-packet root under reports/",
    )
    parser.add_argument(
        "--timestamp",
        help="optional safe timestamp slug for deterministic review-packet output",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="run static ideation launcher self-check and exit",
    )
    parser.add_argument("--launcher-path", help="path to the ideation launcher that invoked this script")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = repo_root()
    exit_code = 0
    try:
        if args.self_check:
            if args.select_implementation:
                raise GeneratorError("--select-implementation cannot be combined with --self-check")
            launcher_path = Path(args.launcher_path) if args.launcher_path else default_ideation_launcher_path(root)
            payload = ideation_launcher_self_check(root=root, launcher_path=launcher_path)
        elif args.spec and (args.write_review_packet or args.select_implementation):
            raise GeneratorError("--spec cannot be combined with --write-review-packet or --select-implementation")
        elif args.select_implementation and not args.write_review_packet:
            raise GeneratorError("--select-implementation requires --write-review-packet")
        elif args.spec:
            spec_path = _as_path(root, args.spec)
            payload = generate_from_spec(spec_path=spec_path, root=root)
        elif args.write_review_packet:
            payload = write_review_packet(
                root=root,
                max_ideas=args.max_ideas,
                review_root=_as_path(root, args.review_root),
                timestamp=args.timestamp,
            )
            if args.select_implementation:
                raw_selection = _print_implementation_selection_prompt()
                selection_payload, exit_code = select_implementation_candidates(
                    root=root,
                    review_packet=payload,
                    raw_selection=raw_selection,
                )
                payload["implementation_selection"] = selection_payload
        else:
            payload = ideate_strategy_candidates(root=root, max_ideas=args.max_ideas)
        print(json.dumps(payload, indent=2, sort_keys=True))
        if payload.get("status") == "STRATEGY_CANDIDATE_REVIEW_PACKET_WRITTEN":
            _print_review_packet_console_summary(root, payload)
            _print_implementation_selection_summary(root, payload)
        return exit_code
    except GeneratorError as exc:
        print(json.dumps({"status": "FAIL", "failure": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    except single_runner.RunnerError as exc:
        print(json.dumps({"status": "FAIL", "failure": str(exc)}, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fail-closed path.
        payload = {"status": "FAIL", "failure": f"unexpected error: {type(exc).__name__}: {exc}"}
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
