# Source/Test Conversion Plan: volume_pace_breakout_continuation_30m_v1

Status: `HISTORICAL_SOURCE_TEST_PLAN_SUPERSEDED_BY_REJECTED_DISPOSITION`

This document is the historical bounded source/test conversion plan for `volume_pace_breakout_continuation_30m_v1`. The plan approved only the bounded source/test implementation phase described below at the time it was written. Later separate approvals registered and configured the candidate, ran one bounded discovery smoke, and rejected the candidate. The current registry and trial ledger are authoritative for disposition.

## Current Disposition Reconciliation

- As of the 2026-07-08 disposition update, `volume_pace_breakout_continuation_30m_v1` is present in the target registry as `REJECTED`, `wfa_allowed=false`, with `next_allowed_actions=[]`.
- The registry attaches `reports/pipeline_audit/volume_pace_source_packet_20260708_volume_pace_breakout_continuation_30m_v1_discovery_smoke.{md,json}` as source reports.
- The trial ledger records the original `register_candidate` row plus one rejected `phase9_discovery_smoke` row: `volume_pace_breakout_continuation_30m_v1_discovery_smoke_rejected_20260708t204156z`.
- The authoritative discovery decision is `STOP_CLASS_COLLAPSE`, with long/short/flat counts `98/106/1100`, duplicate overlap `0.8186274509803921` versus cap `0.8`, discovery top total net `729.0`, and `2 of 4` discovery folds positive.
- This document is retained only as historical implementation-planning evidence. It does not approve rerun, tuning, WFA/modeling, Phase 8, provider, promotion, artifact freeze, paper, live, staging, commit, or push work.

## Reconciled Evidence

Verified from primary repo evidence:

- `CODEX_HANDOFF.md`
- `PROJECT_OUTLINE.md`
- `docs/post_stop_research_direction_20260708.md`
- `docs/new_hypothesis_intake_volume_pace_breakout_20260708.md`
- `manifests/target_hypotheses/registry.json`
- `manifests/target_hypotheses/trial_statuses.jsonl`
- `reports/phase8/tier1_core_phase6_full_predictions_20260706/alpha_promotion_decision.json`
- `reports/failure_analysis/tier1_core_phase6_full_predictions_20260706/failure_analysis_summary.json`
- `reports/statistical_validity/tier1_core_phase6_full_predictions_20260706/statistical_validity_summary.json`
- `reports/model_trust_audit/codex_model_trust_audit_20260707T000000Z/model_trust_audit.{json,md}`
- `reports/candidate_rescue_feasibility/opening_range_acceptance_continuation_30m_v1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/rescue_feasibility.json`
- `scripts/phase9_research/es_30m_target_smoke_harness.py`
- `tests/phase9_research/test_es_30m_target_smoke_harness.py`

Draft context only:

- `reports/pipeline_audit/strategy_candidate_ideation/010_volume_pace_breakout_continuation_30m_v1.{json,md}`

## Original Verified Facts At Plan Time

- At source/test planning time, `volume_pace_breakout_continuation_30m_v1` was not present in the target registry or trial ledger.
- The intake decision is `APPROVED_FOR_BOUNDED_SOURCE_TEST_CONVERSION_PLAN_ONLY`.
- The current alpha queue is closed for execution.
- The ideation dossier is draft-only, not runnable, not registered, and not model-trust evidence.
- `PROJECT_OUTLINE.md` says selected ideation JSON becomes wizard-consumable only after a later explicit conversion/implementation phase implements target construction, adds source tests, appends real registry/status rows after approval, and stops at `WIZARD_PREFLIGHT_COMPLETE` unless separate discovery approval exists.
- The current Tier 1 candidate is stopped: `promoted=false`, `research_alpha_ready=false`, `model_promotion_allowed=false`, gross PnL is negative, net PnL is negative, and the candidate does not beat no-trade.
- Statistical-validity evidence is failing or incomplete for PBO, Deflated Sharpe, multiple-testing, and regime breakdowns.
- The model-trust audit is `research_only`; it does not approve provider downloads, WFA/modeling, prediction generation, promotion, paper, live, staging, commit, or push.
- ORAC v1 rescue feasibility says `V1_NOT_RESCUED_V2_HYPOTHESIS_REQUIRED`, with no v1 rescue, tuning, promotion, or live execution approval.

## Decision

Approve one source/test-only implementation phase.

The candidate is materially distinct enough to plan because it requires a causal volume-pace qualifier before a breakout-continuation label. That is an inference, not alpha evidence. The main unresolved risks are leakage from volume-baseline construction, event-density collapse, duplicate-target overlap, and cost sensitivity.

This approval covers only:

- source/test edits in the two allowed files;
- synthetic unit-test construction;
- the narrow validation command listed below.

## Later Implementation Scope

Allowed files for the later implementation phase only after explicit approval:

- `scripts/phase9_research/es_30m_target_smoke_harness.py`
- `tests/phase9_research/test_es_30m_target_smoke_harness.py`

Forbidden files in that phase unless separately approved:

- `data/**`
- `reports/**`
- `configs/**`
- `manifests/target_hypotheses/registry.json`
- `manifests/target_hypotheses/trial_statuses.jsonl`
- WFA, Phase 8, prediction, model, provider, paper, live, staging, commit, or push surfaces

Expected generated artifacts in that phase:

- None. Use `pytest -p no:cacheprovider` so pytest does not intentionally create cache artifacts.

## Target Construction Contract

Add one `TargetSpec` entry:

- Hypothesis ID: `volume_pace_breakout_continuation_30m_v1`
- Target family: `es_volume_pace_breakout_continuation_30m`
- Slug: `volume_pace_breakout_continuation_30m`
- Apply function: `apply_volume_pace_breakout_continuation_30m_target`
- Evaluation mode: `directional_net`
- Horizon: fixed 30-minute timeout with next-open entry and same-session exit path
- Costs: existing ES cost config only; no cost-config mutation

Predeclared constants:

- `VOLUME_PACE_RANGE_BARS = 60`
- `VOLUME_PACE_MIN_BASELINE_SESSIONS = 20`
- `VOLUME_PACE_BREAKOUT_BUFFER_TICKS = 1.0`
- `VOLUME_PACE_RATIO_MIN = 1.5`

Event-time inputs:

- Use only rows passing the existing `_row_valid_mask`.
- Use the same `session_segment_id` path discipline as existing targets.
- Prior range is the previous 60 valid same-session bars, excluding the current event bar.
- Long event: current close is at least one tick above the prior 60-bar range high.
- Short event: current close is at least one tick below the prior 60-bar range low.
- Volume pace is cumulative same-session volume through the current event bar divided by completed same-session bar count through the current event bar.
- Volume baseline is a same-session-bar-index rolling median of prior-session volume pace, shifted so the current session and all future sessions are excluded.
- Event qualifies only when the volume-pace ratio is at least `1.5`, baseline is positive, and at least 20 prior sessions are available for the same session-bar index.

Label math:

- Entry price is `open.shift(-1)`.
- Exit price is `open.shift(-31)`.
- Entry and exit must remain in the same session and pass `_path_valid_mask`.
- Event direction is fixed by the current-bar breakout side and must not depend on future path.
- `signed_exit_ticks = event_direction * ((exit_price - entry_price) / tick_size)`.
- Threshold uses existing `_threshold_ticks(..., horizon_bars=30)`.
- Direction is event direction only when `signed_exit_ticks > threshold_ticks`; otherwise direction is flat.
- Gross dollars are `signed_exit_ticks * tick_value` for valid events.
- Net dollars are gross dollars minus configured round-turn cost dollars for valid events.

Auxiliary columns to add:

- `target_range_high_volume_pace_breakout_continuation_30m`
- `target_range_low_volume_pace_breakout_continuation_30m`
- `target_range_ticks_volume_pace_breakout_continuation_30m`
- `target_volume_pace_volume_pace_breakout_continuation_30m`
- `target_volume_pace_baseline_volume_pace_breakout_continuation_30m`
- `target_volume_pace_ratio_volume_pace_breakout_continuation_30m`
- `target_event_direction_volume_pace_breakout_continuation_30m`
- `target_breakout_ticks_volume_pace_breakout_continuation_30m`
- `target_timeout_exit_ticks_volume_pace_breakout_continuation_30m`

## Source Tests To Add

Add focused tests in `tests/phase9_research/test_es_30m_target_smoke_harness.py`:

- `test_volume_pace_breakout_continuation_30m_target_spec_is_distinct`
- `test_volume_pace_breakout_continuation_30m_label_math`
- `test_volume_pace_breakout_event_side_does_not_use_future_path`
- `test_volume_pace_breakout_rejects_cross_session_30m_horizon`
- `test_volume_pace_breakout_requires_prior_session_volume_baseline`
- `test_volume_pace_breakout_rejects_low_volume_pace`
- `test_volume_pace_breakout_distribution_has_long_short_and_flat`

The tests must use synthetic frames only. They must cover:

- expected long, short, and flat examples;
- missing or insufficient prior-session volume baseline;
- low current volume pace despite price breakout;
- same-session path enforcement;
- future-path mutation not changing event side or validity;
- target columns and auxiliary columns present and typed consistently;
- non-overlap and duplicate-overlap helper compatibility.

## Historical Registry And Trial Ledger Needs

The source/test implementation phase did not approve registry or trial-ledger mutation. Those mutations were later handled under separate bounded approvals and are now superseded by the rejected discovery-smoke disposition.

At the time of this plan, a later registration phase was expected to need:

- one real registry entry with `target_hypothesis_id="volume_pace_breakout_continuation_30m_v1"`;
- `status="CANDIDATE"`;
- `target_family="es_volume_pace_breakout_continuation_30m"`;
- `wfa_allowed=false`;
- source reports empty until a real source-test or discovery-packet report exists;
- next allowed actions limited to source-tests/preflight/discovery-packet, not discovery-run;
- one trial-status row at `stage="register_candidate"`, `status="CANDIDATE"`, and no model-trust claim.

## Historical Bounded Implementation Approval Packet

The approved bounded implementation phase is:

- Objective: implement only `volume_pace_breakout_continuation_30m_v1` target construction and source tests.
- Maximum scope: source/test code only; ES-only semantics; existing local code and synthetic unit-test data only.
- Timeout/stop budget: 30 minutes for edits and 120 seconds per validation command.
- Allowed command family after edits: `python -m pytest -q -p no:cacheprovider tests\phase9_research\test_es_30m_target_smoke_harness.py -k volume_pace_breakout`.
- Optional if imports or shared helpers change: `python -m pytest -q -p no:cacheprovider tests\phase9_research\test_es_30m_target_smoke_harness.py`.
- Required after doc or handoff edits: `python -m scripts.validation.check_coordination_docs`, `git diff --check`, and `git status --short`.

Forbidden command patterns:

- `RUN_ALPHA_DISCOVERY.bat`
- `RUN_STRATEGY_CANDIDATE_IDEATION.bat`
- `python -m scripts.validation.run_alpha_discovery`
- `python -m scripts.validation.run_alpha_discovery_wizard`
- `python -m scripts.validation.run_alpha_discovery_queue`
- `python -m scripts.validation.generate_alpha_discovery_candidates`
- `python -m scripts.phase9_research.es_30m_target_smoke_harness`
- any command using `--mode discovery-run`, `--approve-discovery-run`, or `RUN_PHASE9_DISCOVERY_ONCE`
- any provider, data build, report generator, WFA/modeling, Phase 8, promotion, paper, live, staging, commit, or push command

Stop immediately if:

- registry or trial ledger state has changed and conflicts with this plan;
- implementation would require `data/**`, `reports/**`, `configs/**`, registry, or trial-ledger mutation;
- event side depends on future path;
- volume baseline requires current/future sessions, holdout/forward rows, or post-event data;
- synthetic source tests cannot produce long, short, and flat cases without post-hoc threshold tuning;
- target construction duplicates a stopped branch without an independent volume-pace qualifier;
- any validation creates tracked or staged generated artifacts.

## Historical Non-Approval

At the time of this plan, this approval did not approve registry/trial-ledger mutation, wizard preflight, discovery-packet generation, discovery-run, WFA/modeling, Phase 8, promotion, artifact freeze, paper trading, live trading, staging, commit, or push. Later separate approvals covered registration, config, and exactly one discovery smoke; the final candidate disposition is now `REJECTED`.
