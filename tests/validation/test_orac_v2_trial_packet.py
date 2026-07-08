from __future__ import annotations

import json
from pathlib import Path

from scripts.phase9_research.es_30m_target_smoke_harness import TARGET_SPECS


HYPOTHESIS_ID = "opening_range_acceptance_continuation_event_capture_30m_v2"
VWAP_RECLAIM_ID = "vwap_reclaim_continuation_15m_v1"
OPENING_DRIVE_ID = "opening_drive_failed_followthrough_15m_v1"
VOLUME_PACE_ID = "volume_pace_breakout_continuation_30m_v1"
REGISTRY = Path("manifests/target_hypotheses/registry.json")
TRIAL_STATUSES = Path("manifests/target_hypotheses/trial_statuses.jsonl")
PACKET = Path("docs/opening_range_acceptance_continuation_event_capture_30m_v2_trial_packet.md")
VWAP_PACKET = Path("docs/vwap_reclaim_continuation_15m_v1_trial_packet.md")
OPENING_DRIVE_PACKET = Path(
    "docs/opening_drive_failed_followthrough_15m_v1_primary_evidence_predecl_packet_20260707.md"
)
OPENING_DRIVE_CONFIG = Path(
    "configs/alpha_discovery_generated/opening_drive_failed_followthrough_source_packet_20260707/"
    "alpha_discovery_runner.opening_drive_failed_followthrough_15m_v1.json"
)
DISCOVERY_MD = (
    "reports/pipeline_audit/"
    "orac_v2_source_packet_20260707_"
    "opening_range_acceptance_continuation_event_capture_30m_v2_discovery_smoke.md"
)
DISCOVERY_JSON = (
    "reports/pipeline_audit/"
    "orac_v2_source_packet_20260707_"
    "opening_range_acceptance_continuation_event_capture_30m_v2_discovery_smoke.json"
)
VWAP_DISCOVERY_MD = (
    "reports/pipeline_audit/"
    "vwap_reclaim_source_packet_20260707_"
    "vwap_reclaim_continuation_15m_v1_discovery_smoke.md"
)
VWAP_DISCOVERY_JSON = (
    "reports/pipeline_audit/"
    "vwap_reclaim_source_packet_20260707_"
    "vwap_reclaim_continuation_15m_v1_discovery_smoke.json"
)
OPENING_DRIVE_DISCOVERY_MD = (
    "reports/pipeline_audit/"
    "opening_drive_failed_followthrough_source_packet_20260707_"
    "opening_drive_failed_followthrough_15m_v1_discovery_smoke.md"
)
OPENING_DRIVE_DISCOVERY_JSON = (
    "reports/pipeline_audit/"
    "opening_drive_failed_followthrough_source_packet_20260707_"
    "opening_drive_failed_followthrough_15m_v1_discovery_smoke.json"
)
VOLUME_PACE_DISCOVERY_MD = (
    "reports/pipeline_audit/"
    "volume_pace_source_packet_20260708_"
    "volume_pace_breakout_continuation_30m_v1_discovery_smoke.md"
)
VOLUME_PACE_DISCOVERY_JSON = (
    "reports/pipeline_audit/"
    "volume_pace_source_packet_20260708_"
    "volume_pace_breakout_continuation_30m_v1_discovery_smoke.json"
)


def _registry_entry(hypothesis_id: str = HYPOTHESIS_ID) -> dict[str, object]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    matches = [
        row
        for row in payload["hypotheses"]
        if row.get("target_hypothesis_id") == hypothesis_id
    ]
    assert len(matches) == 1
    return matches[0]


def _trial_events(hypothesis_id: str = HYPOTHESIS_ID) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in TRIAL_STATUSES.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("hypothesis_id") == hypothesis_id
    ]


def test_orac_v2_registry_is_rejected_after_discovery_stop() -> None:
    entry = _registry_entry()

    assert entry["status"] == "REJECTED"
    assert entry["wfa_allowed"] is False
    assert entry["target_family"] == "es_opening_range_acceptance_continuation_event_capture_30m"
    assert entry["scope"] == {
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "markets": ["ES"],
        "years": [2023, 2024],
    }
    assert entry["source_reports"] == [DISCOVERY_MD, DISCOVERY_JSON]
    assert entry["next_allowed_actions"] == []
    assert "STOP_CLASS_COLLAPSE" in entry["status_reason"]
    assert "237/225/0" in entry["status_reason"]
    assert "-52.0" in entry["status_reason"]
    assert "Do not rerun discovery" in entry["status_reason"]


def test_orac_v2_registry_locks_core_research_rules() -> None:
    pre_registration = _registry_entry()["pre_registration"]

    assert pre_registration["market"] == "ES only"
    assert "first qualifying acceptance event" in pre_registration["entry_timing"]
    assert "Fixed 30-minute timeout exit" in pre_registration["exit_horizon"]
    assert any(
        "post-hoc UTC hour filters" in item
        for item in pre_registration["features_forbidden"]
    )
    assert "no discovery, WFA, Phase 8, promotion, artifact freeze, paper, or live execution without separate bounded approval" in pre_registration["forbidden_actions"]
    assert "no-trade" in pre_registration["required_baselines"]
    assert "random-entry matched by session, count, and direction" in pre_registration["required_baselines"]
    assert "PBO below 0.20" in pre_registration["statistical_validity_requirements"]
    assert "actual contract mapping" in pre_registration["execution_realism_gate"]


def test_orac_v2_trial_ledger_records_rejected_discovery() -> None:
    events = _trial_events()

    assert len(events) == 2
    candidate, rejected = events
    assert candidate["trial_id"] == f"{HYPOTHESIS_ID}_candidate"
    assert candidate["stage"] == "register_candidate"
    assert candidate["status"] == "CANDIDATE"
    assert candidate["evidence"] == []
    assert "target-construction source implemented" in candidate["notes"]

    assert rejected["trial_id"] == f"{HYPOTHESIS_ID}_discovery_smoke_rejected_20260707t153854z"
    assert rejected["stage"] == "phase9_discovery_smoke"
    assert rejected["status"] == "REJECTED"
    assert rejected["evidence"] == [DISCOVERY_MD, DISCOVERY_JSON]
    assert "STOP_CLASS_COLLAPSE" in rejected["notes"]
    assert "237/225/0" in rejected["notes"]
    assert "-52.0" in rejected["notes"]
    assert "Do not rerun discovery" in rejected["notes"]


def test_orac_v2_packet_contains_required_audit_gates() -> None:
    text = PACKET.read_text(encoding="utf-8")

    for required in (
        "Market: ES only.",
        "Entry timing: enter at the next bar open",
        "fixed 30-minute timeout exit is the pass/fail economic policy",
        "No post-hoc UTC hour filters",
        "IBKR futures commission page",
        "CME clearing and trading fee page",
        "Random-entry matched by session, count, and direction",
        "PBO must be below `0.20`",
        "Probabilistic Sharpe probability must be at least `0.95`",
        "Deflated Sharpe probability must be at least `0.95`",
        "Actual contract mapping",
        "Do not run discovery, WFA, Phase 8, promotion",
    ):
        assert required in text


def test_orac_v2_target_source_is_registered_but_not_advanced() -> None:
    spec = TARGET_SPECS[HYPOTHESIS_ID]
    entry = _registry_entry()

    assert spec.target_family == entry["target_family"]
    assert entry["status"] == "REJECTED"
    assert entry["wfa_allowed"] is False
    assert entry["source_reports"] == [DISCOVERY_MD, DISCOVERY_JSON]


def test_vwap_reclaim_registry_is_rejected_after_discovery_stop() -> None:
    entry = _registry_entry(VWAP_RECLAIM_ID)

    assert entry["status"] == "REJECTED"
    assert entry["wfa_allowed"] is False
    assert entry["target_family"] == "es_vwap_reclaim_continuation_15m"
    assert entry["scope"] == {
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "markets": ["ES"],
        "years": [2023, 2024],
    }
    assert entry["source_reports"] == [VWAP_DISCOVERY_MD, VWAP_DISCOVERY_JSON]
    assert entry["next_allowed_actions"] == []
    assert "STOP_CLASS_COLLAPSE" in entry["status_reason"]
    assert "429/528/5806" in entry["status_reason"]
    assert "1.0 versus cap 0.8" in entry["status_reason"]
    assert "1775.5" in entry["status_reason"]
    assert "2 of 4" in entry["status_reason"]
    assert "Do not rerun discovery" in entry["status_reason"]


def test_vwap_reclaim_registry_predeclares_materially_new_rules() -> None:
    entry = _registry_entry(VWAP_RECLAIM_ID)
    pre_registration = entry["pre_registration"]

    assert "causal VWAP excursion" in pre_registration["entry_condition"]
    assert "15-minute same-session fixed-horizon exit" in pre_registration["target_definition"]
    assert "round-turn cost ticks plus min_profit_ticks" in pre_registration["target_definition"]
    assert "vwap_reversion_30m_v1" in pre_registration["material_difference_from_stopped_branches"]
    assert "opening_range_acceptance_continuation_event_capture_30m_v2" in pre_registration[
        "material_difference_from_stopped_branches"
    ]
    assert "no discovery-run without separate bounded approval" in pre_registration["forbidden_actions"]
    assert any("STOP_CLASS_COLLAPSE" in item for item in pre_registration["stop_rules"])


def test_vwap_reclaim_trial_ledger_records_rejected_discovery() -> None:
    events = _trial_events(VWAP_RECLAIM_ID)

    assert len(events) == 2
    candidate, rejected = events
    assert candidate["trial_id"] == f"{VWAP_RECLAIM_ID}_candidate"
    assert candidate["stage"] == "register_candidate"
    assert candidate["status"] == "CANDIDATE"
    assert candidate["evidence"] == []
    assert "source/tests-only implementation" in candidate["notes"].lower()
    assert "No discovery-run" in candidate["notes"]

    assert rejected["trial_id"] == f"{VWAP_RECLAIM_ID}_discovery_smoke_rejected_20260707t171048z"
    assert rejected["stage"] == "phase9_discovery_smoke"
    assert rejected["status"] == "REJECTED"
    assert rejected["evidence"] == [VWAP_DISCOVERY_MD, VWAP_DISCOVERY_JSON]
    assert "STOP_CLASS_COLLAPSE" in rejected["notes"]
    assert "429/528/5806" in rejected["notes"]
    assert "1.0 versus cap 0.8" in rejected["notes"]
    assert "1775.5" in rejected["notes"]
    assert "2 of 4" in rejected["notes"]
    assert "target_smoke_is_tradability_proof=false" in rejected["notes"]
    assert "Do not rerun discovery" in rejected["notes"]


def test_vwap_reclaim_trial_packet_contains_required_audit_gates() -> None:
    text = VWAP_PACKET.read_text(encoding="utf-8")

    for required in (
        "Hypothesis ID: `vwap_reclaim_continuation_15m_v1`",
        "Market: ES only.",
        "15-minute same-session fixed-horizon exit",
        "causal session VWAP",
        "Round-turn cost ticks plus `min_profit_ticks`",
        "ORAC v2 is stopped by `STOP_CLASS_COLLAPSE`",
        "No-trade.",
        "Random-entry matched by session, count, and direction.",
        "PBO must be below `0.20`",
        "Do not run discovery, WFA, Phase 8, promotion",
    ):
        assert required in text


def test_vwap_reclaim_target_source_is_registered_but_not_advanced() -> None:
    spec = TARGET_SPECS[VWAP_RECLAIM_ID]
    entry = _registry_entry(VWAP_RECLAIM_ID)

    assert spec.target_family == entry["target_family"]
    assert spec.horizon_bars == 15
    assert entry["status"] == "REJECTED"
    assert entry["wfa_allowed"] is False
    assert entry["source_reports"] == [VWAP_DISCOVERY_MD, VWAP_DISCOVERY_JSON]


def test_opening_drive_failed_followthrough_registry_is_rejected_after_discovery_stop() -> None:
    entry = _registry_entry(OPENING_DRIVE_ID)

    assert entry["status"] == "REJECTED"
    assert entry["wfa_allowed"] is False
    assert entry["target_family"] == "es_opening_drive_failed_followthrough_15m"
    assert entry["scope"] == {
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "markets": ["ES"],
        "years": [2023, 2024],
    }
    assert entry["source_reports"] == [OPENING_DRIVE_DISCOVERY_MD, OPENING_DRIVE_DISCOVERY_JSON]
    assert entry["next_allowed_actions"] == []
    assert "STOP_CLASS_COLLAPSE" in entry["status_reason"]
    assert "445/283/4574" in entry["status_reason"]
    assert "1.0 versus cap 0.8" in entry["status_reason"]
    assert "2519.0" in entry["status_reason"]
    assert "3 of 4" in entry["status_reason"]
    assert "Do not rerun discovery" in entry["status_reason"]


def test_opening_drive_failed_followthrough_registry_predeclares_materially_new_rules() -> None:
    entry = _registry_entry(OPENING_DRIVE_ID)
    pre_registration = entry["pre_registration"]

    assert "first 15 session bars" in pre_registration["entry_condition"]
    assert "current-bar failure" in pre_registration["entry_condition"]
    assert "failed long-drive continuation maps to short" in pre_registration["direction"]
    assert "15-minute same-session fixed-horizon exit" in pre_registration["target_definition"]
    assert "round-turn cost ticks + min_profit_ticks" in pre_registration["threshold_rule"]
    assert "not VWAP reclaim" in pre_registration["material_difference_from_stopped_branches"]
    assert "not ORAC v2" in pre_registration["material_difference_from_stopped_branches"]
    assert "no discovery-run without separate bounded approval" in pre_registration["forbidden_actions"]
    assert any("STOP_CLASS_COLLAPSE" in item for item in pre_registration["stop_rules"])


def test_opening_drive_failed_followthrough_trial_ledger_records_rejected_discovery() -> None:
    events = _trial_events(OPENING_DRIVE_ID)

    assert len(events) == 2
    candidate, rejected = events
    assert candidate["trial_id"] == f"{OPENING_DRIVE_ID}_candidate"
    assert candidate["stage"] == "register_candidate"
    assert candidate["status"] == "CANDIDATE"
    assert candidate["evidence"] == []
    assert "source/tests-only" in candidate["notes"].lower()
    assert "No discovery-run" in candidate["notes"]

    assert rejected["trial_id"] == f"{OPENING_DRIVE_ID}_discovery_smoke_rejected_20260707t185416z"
    assert rejected["stage"] == "phase9_discovery_smoke"
    assert rejected["status"] == "REJECTED"
    assert rejected["evidence"] == [OPENING_DRIVE_DISCOVERY_MD, OPENING_DRIVE_DISCOVERY_JSON]
    assert "STOP_CLASS_COLLAPSE" in rejected["notes"]
    assert "445/283/4574" in rejected["notes"]
    assert "1.0 versus cap 0.8" in rejected["notes"]
    assert "2519.0" in rejected["notes"]
    assert "3 of 4" in rejected["notes"]
    assert "target_smoke_is_tradability_proof=false" in rejected["notes"]
    assert "Do not rerun discovery" in rejected["notes"]


def test_opening_drive_failed_followthrough_packet_contains_required_audit_gates() -> None:
    text = OPENING_DRIVE_PACKET.read_text(encoding="utf-8")

    for required in (
        "Hypothesis ID: `opening_drive_failed_followthrough_15m_v1`",
        "Scope: ES only, 2023/2024 research folds only.",
        "completed same-session opening-drive state",
        "failed continuation attempt in the drive direction",
        "fixed 15-minute same-session exit",
        "must not reuse rejected VWAP reclaim or ORAC v2 code paths",
        "preflight and discovery-packet only before any discovery-run approval",
        "any step tries to run discovery, WFA/modeling, Phase 8",
        "Plan only a bounded source/test registration phase",
    ):
        assert required in text


def test_opening_drive_failed_followthrough_target_source_and_config_are_registered_but_not_advanced() -> None:
    spec = TARGET_SPECS[OPENING_DRIVE_ID]
    entry = _registry_entry(OPENING_DRIVE_ID)
    config = json.loads(OPENING_DRIVE_CONFIG.read_text(encoding="utf-8"))

    assert spec.target_family == entry["target_family"]
    assert spec.horizon_bars == 15
    assert entry["status"] == "REJECTED"
    assert entry["wfa_allowed"] is False
    assert entry["source_reports"] == [OPENING_DRIVE_DISCOVERY_MD, OPENING_DRIVE_DISCOVERY_JSON]
    assert config["runner_mode"] == "preflight"
    assert config["hypothesis_id"] == OPENING_DRIVE_ID
    assert config["target_policy_contract"]["payoff_basis"] == "fixed_horizon_exit"
    assert config["target_policy_contract"]["horizon_bars"] == 15
    assert config["discovery_command"][config["discovery_command"].index("--hypothesis-id") + 1] == OPENING_DRIVE_ID
    assert config["expected_outputs"] == [OPENING_DRIVE_DISCOVERY_JSON, OPENING_DRIVE_DISCOVERY_MD]
    assert "discovery-run" in config["forbidden_actions"]
    assert "WFA/modeling" in config["forbidden_actions"]


def test_volume_pace_breakout_registry_is_rejected_after_discovery_stop() -> None:
    entry = _registry_entry(VOLUME_PACE_ID)

    assert entry["status"] == "REJECTED"
    assert entry["wfa_allowed"] is False
    assert entry["target_family"] == "es_volume_pace_breakout_continuation_30m"
    assert entry["scope"] == {
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "markets": ["ES"],
        "years": [2023, 2024],
    }
    assert entry["source_reports"] == [VOLUME_PACE_DISCOVERY_MD, VOLUME_PACE_DISCOVERY_JSON]
    assert entry["next_allowed_actions"] == []
    assert "STOP_CLASS_COLLAPSE" in entry["status_reason"]
    assert "98/106/1100" in entry["status_reason"]
    assert "0.8186274509803921" in entry["status_reason"]
    assert "729.0" in entry["status_reason"]
    assert "2 of 4" in entry["status_reason"]
    assert "Do not rerun discovery" in entry["status_reason"]


def test_volume_pace_breakout_registry_predeclares_rules() -> None:
    entry = _registry_entry(VOLUME_PACE_ID)
    pre_registration = entry["pre_registration"]

    assert "prior 60 valid same-session bar range" in pre_registration["entry_condition"]
    assert "at least one ES tick outside that range" in pre_registration["entry_condition"]
    assert "volume pace ratio >= 1.5" in pre_registration["volume_pace_rule"]
    assert "positive baseline" in pre_registration["volume_pace_rule"]
    assert "at least 20 prior sessions" in pre_registration["volume_pace_rule"]
    assert "next-open entry" in pre_registration["target_definition"]
    assert "fixed same-session 30-minute" in pre_registration["target_definition"]
    assert "configured ES costs" in pre_registration["target_definition"]
    assert "not session-compression" in pre_registration["material_difference_from_stopped_branches"]
    assert "not ORAC" in pre_registration["material_difference_from_stopped_branches"]
    assert "no discovery-run without separate bounded approval" in pre_registration["forbidden_actions"]
    assert any("STOP_CLASS_COLLAPSE" in item for item in pre_registration["stop_rules"])
    assert "STOP_CLASS_COLLAPSE" in pre_registration["implementation_status"]


def test_volume_pace_breakout_trial_ledger_records_rejected_discovery() -> None:
    events = _trial_events(VOLUME_PACE_ID)

    assert len(events) == 2
    candidate = events[0]
    assert candidate["trial_id"] == f"{VOLUME_PACE_ID}_candidate"
    assert candidate["stage"] == "register_candidate"
    assert candidate["status"] == "CANDIDATE"
    assert candidate["evidence"] == []
    assert "source/tests-only implementation approved" in candidate["notes"].lower()
    assert "No discovery-run" in candidate["notes"]
    assert "WFA/modeling" in candidate["notes"]

    rejected = events[1]
    assert rejected["trial_id"] == f"{VOLUME_PACE_ID}_discovery_smoke_rejected_20260708t204156z"
    assert rejected["stage"] == "phase9_discovery_smoke"
    assert rejected["status"] == "REJECTED"
    assert rejected["evidence"] == [VOLUME_PACE_DISCOVERY_MD, VOLUME_PACE_DISCOVERY_JSON]
    assert "STOP_CLASS_COLLAPSE" in rejected["notes"]
    assert "98/106/1100" in rejected["notes"]
    assert "0.8186274509803921" in rejected["notes"]
    assert "729.0" in rejected["notes"]
    assert "2 of 4" in rejected["notes"]
    assert "target_smoke_is_tradability_proof=false" in rejected["notes"]
    assert "Do not rerun discovery" in rejected["notes"]


def test_volume_pace_breakout_target_source_is_registered_but_not_advanced() -> None:
    spec = TARGET_SPECS[VOLUME_PACE_ID]
    entry = _registry_entry(VOLUME_PACE_ID)

    assert spec.target_family == entry["target_family"]
    assert spec.horizon_bars == 30
    assert entry["status"] == "REJECTED"
    assert entry["wfa_allowed"] is False
    assert entry["source_reports"] == [VOLUME_PACE_DISCOVERY_MD, VOLUME_PACE_DISCOVERY_JSON]
    assert entry["next_allowed_actions"] == []
