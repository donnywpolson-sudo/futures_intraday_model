# New Hypothesis Intake: volume_pace_breakout_continuation_30m_v1

Status: `HISTORICAL_INTAKE_SUPERSEDED_BY_REJECTED_DISPOSITION`

This is a historical proposed intake document. The intake itself did not register a hypothesis, mutate the trial ledger, implement target construction, run source tests, run discovery, run WFA/modeling, refresh Phase 8, promote artifacts, paper trade, or live trade. Later separate approvals implemented source/tests, registered and configured the candidate, ran one bounded discovery smoke, and rejected the candidate. The current registry and trial ledger are authoritative for disposition.

## Current Disposition Reconciliation

- As of the 2026-07-08 disposition update, `volume_pace_breakout_continuation_30m_v1` is present in the target registry as `REJECTED`, `wfa_allowed=false`, with `next_allowed_actions=[]`.
- The registry attaches `reports/pipeline_audit/volume_pace_source_packet_20260708_volume_pace_breakout_continuation_30m_v1_discovery_smoke.{md,json}` as source reports.
- The trial ledger records the original `register_candidate` row plus one rejected `phase9_discovery_smoke` row: `volume_pace_breakout_continuation_30m_v1_discovery_smoke_rejected_20260708t204156z`.
- The authoritative discovery decision is `STOP_CLASS_COLLAPSE`, with long/short/flat counts `98/106/1100`, duplicate overlap `0.8186274509803921` versus cap `0.8`, discovery top total net `729.0`, and `2 of 4` discovery folds positive.
- This document is retained only as historical intake evidence. It no longer approves a next phase for this hypothesis, and it does not approve rerun, tuning, WFA/modeling, Phase 8, provider, promotion, artifact freeze, paper, or live work.

## Reconciled Evidence

Primary repo evidence reviewed:

- `CODEX_HANDOFF.md`
- `PROJECT_OUTLINE.md`
- `docs/post_stop_research_direction_20260708.md`
- `manifests/target_hypotheses/registry.json`
- `manifests/target_hypotheses/trial_statuses.jsonl`
- `reports/phase8/tier1_core_phase6_full_predictions_20260706/alpha_promotion_decision.json`
- `reports/failure_analysis/tier1_core_phase6_full_predictions_20260706/failure_analysis_summary.json`
- `reports/statistical_validity/tier1_core_phase6_full_predictions_20260706/statistical_validity_summary.json`
- `reports/model_trust_audit/codex_model_trust_audit_20260707T000000Z/model_trust_audit.{json,md}`
- `reports/candidate_rescue_feasibility/opening_range_acceptance_continuation_30m_v1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/rescue_feasibility.json`
- `reports/wfa/tier1_core_phase6_wfa_runner_preflight_20260706/tier1_core_active_feature_set.json`
- `reports/data_audit/current_state/tier1_core_phase4_self_reference_cleanup_active_placement_20260706/active_feature_manifest.json`

Draft context reviewed, not primary evidence:

- `reports/pipeline_audit/strategy_candidate_ideation/010_volume_pace_breakout_continuation_30m_v1.{json,md}`

## Original Verified Facts At Intake Time

- At intake review time, the registry had exactly one non-rejected hypothesis: `opening_range_acceptance_continuation_30m_v1`, which was `FROZEN` with `wfa_allowed=true` and `next_allowed_actions=["PREPARE_BOUNDED_NEXT_PHASE_PLAN"]`.
- At intake review time, all other then-listed target hypotheses were `REJECTED`, `wfa_allowed=false`, and had no next allowed actions.
- At intake review time, `volume_pace_breakout_continuation_30m_v1` did not appear in the target registry or trial ledger.
- The ideation packet for `volume_pace_breakout_continuation_30m_v1` is explicitly `draft_only`, `not_runnable`, and `not_model_trust_evidence`.
- The active Tier 1 feature evidence includes volume-related fields such as `feature_volume_z_20`, `feature_volume_z_60`, `feature_volume_surge_with_range`, `feature_volume_surge_without_progress`, `feature_range_per_volume`, `feature_volume_climax_flag`, `feature_bars_since_volume_climax`, and `feature_volume_per_tick_progress_30`.
- Existing Tier 1 model evidence is stopped: `promoted=false`, `research_alpha_ready=false`, and `model_promotion_allowed=false`.
- Existing Tier 1 economics are negative: gross dollars `-19871.875000000156`, net dollars `-55995.21500000016`, and average net dollars per trade `-41.57031551596151`.
- The statistical-validity report for Tier 1 is `FAIL`, with failures for PBO, Deflated Sharpe, Probabilistic Sharpe, multiple-testing adjustment, and regime breakdowns.
- ORAC v1 rescue diagnostics report `V1_NOT_RESCUED_V2_HYPOTHESIS_REQUIRED`, `v1_rescue_allowed=false`, `tuning_or_selection_allowed=false`, `promotion_allowed=false`, and `live_execution_ready=false`.

## Assumptions And Inferences

- The proposed candidate is materially different enough for intake review because it requires an independent causal volume-pace condition before labeling a breakout continuation event.
- This is not evidence that the candidate has alpha. It is only a reason to consider a doc-only intake decision.
- Existing volume-related feature evidence proves that volume-derived fields exist in current feature artifacts, but it does not prove the proposed event definition is valid, leak-free, tradable, or profitable.
- The draft ideation packet can describe the candidate shape, but it cannot justify registry mutation, source implementation, discovery, WFA, Phase 8, promotion, paper, or live work.

## Proposed Candidate

- Hypothesis ID: `volume_pace_breakout_continuation_30m_v1`
- Target family: `es_volume_pace_breakout_continuation_30m`
- Market/year scope: ES only, Tier 1 research scope, 2023-2024 only.
- Entry event: candidate rows require a completed causal intraday range, a break outside that range, and elevated causal volume pace versus a predeclared session-minute baseline available at the event timestamp.
- Entry timing: next-open entry after the qualifying event.
- Exit horizon: same-session 30-minute fixed horizon.
- Direction: continuation in the volume-confirmed breakout direction.
- Costs: existing configured ES costs from `configs/costs.yaml`; no cost-config mutation in this intake.
- Required threshold discipline: all range, volume-pace, event-density, duplicate-overlap, and cost-clearance thresholds must be predeclared before any source test or discovery output is inspected.

## Material Difference From Stopped Branches

- Not Tier 1 directional baseline: this is a sparse event target, not a broad baseline directional policy over all active feature rows.
- Not ORAC v1/v2: it is not keyed to first opening-range acceptance, opening-range high/low acceptance, ORAC hour buckets, or ORAC v1 path-capture diagnostics.
- Not VWAP reclaim/reversion: it does not use VWAP distance, VWAP stretch, or VWAP reclaim as the event condition.
- Not opening-drive failed-followthrough: it does not depend on a completed opening drive or failed continuation attempt.
- Not session-compression breakout: it does not use compression-box percentile logic as the primary filter; volume pace is a required independent event qualifier.
- Not late-session range-resolution: it is not restricted to late-session range resolution or session-close behavior.
- Not a stopped-branch relabel: if implemented later, it must use a new target family and must explicitly compare duplicate overlap with prior accepted/stopped targets before any pass decision.

## Required Intake Controls

- No-trade baseline.
- Random-entry baseline matched by session, count, and direction.
- Simple trend baseline.
- Simple mean-reversion baseline.
- Intraday seasonality baseline.
- Carry or term-structure baseline where existing data supports it.
- Duplicate-overlap review against current 15-minute deadzone target and all stopped ES target families.
- Full trial ledger entry before any locked OOS or promotion-facing claim.
- Statistical-validity plan covering PBO, Deflated Sharpe, Probabilistic Sharpe, multiple-testing adjustment, parameter stability, and regime breakdowns.

## Stop Criteria

Stop the candidate before any next phase if any of these occur:

- Registry or trial ledger evidence conflicts with this intake.
- The candidate cannot be proven materially different from stopped branches.
- The volume-pace baseline would require holdout/forward rows or post-event data.
- Source design cannot guarantee event-time-only information for entry conditions.
- Required volume fields are unavailable, stale, or not validated for the exact scope.
- Duplicate target overlap exceeds the predeclared cap.
- Event counts or class balance collapse.
- Base-cost or 2x-cost economics are nonpositive.
- Fewer than half of scoped folds are positive.
- Comparable baselines are missing or beat the candidate.
- Full trial-log evidence is missing.
- Statistical-validity, regime, capacity/liquidity, or market-impact evidence is missing for any model-trust or promotion-facing claim.

## Forbidden Actions

- Do not mutate `data/**`, `reports/**`, configs, registry, or trial ledger from this intake.
- Do not implement target construction, edit `TARGET_SPECS`, run source tests, run the wizard, run discovery, run WFA/modeling, run Phase 8, promote, freeze artifacts, paper trade, or live trade from this intake.
- Do not tune thresholds, features, costs, folds, markets, or years after seeing any source-test or discovery output.
- Do not reuse stopped branches under a new name.
- Do not use holdout or forward rows for selection.
- Do not stage, commit, or push without separate explicit approval.

## Historical Later Approval Packet

If the user explicitly approves this intake, the next phase should be a bounded source/test conversion plan, not execution by default.

Allowed objective for that later phase:

- Produce one implementation plan for `volume_pace_breakout_continuation_30m_v1` that specifies exact target construction, source tests, registry/trial-ledger changes that would be needed later, expected files, stop conditions, and validation.

Maximum scope for that later plan:

- ES only.
- Years 2023-2024.
- Existing local data/features only.
- No provider calls.
- No generated data/model/report artifacts beyond the proposed plan document unless separately approved.

Forbidden in that later planning phase:

- No registry/trial-ledger mutation.
- No target implementation.
- No source-test execution.
- No discovery run.
- No WFA/modeling.
- No Phase 8.
- No promotion, artifact freeze, paper, or live work.

Timeout and stop budget:

- 45 minutes.
- Stop after the first unreconciled contradiction against `CODEX_HANDOFF.md`, `PROJECT_OUTLINE.md`, registry, trial ledger, or existing report summaries.

Validation if later docs are edited:

- `python -m scripts.validation.check_coordination_docs`
- `git diff --check`
- `git status --short`

## Historical Decision

`APPROVED_FOR_BOUNDED_SOURCE_TEST_CONVERSION_PLAN_ONLY`

Reviewed decision: approve this intake only as the next plan-only gate. Primary repo evidence supports treating `volume_pace_breakout_continuation_30m_v1` as materially distinct enough to plan source/test conversion, but the leakage, event-density, duplicate-overlap, and cost-sensitivity risks remain unresolved.

This approval permits only the later bounded source/test conversion plan described above. It is not approved for implementation, registry or trial-ledger mutation, source-test execution, wizard use, discovery, WFA/modeling, Phase 8, promotion, paper trading, or live trading.

## Current Decision

`SUPERSEDED_BY_REJECTED_DISPOSITION`

After separate bounded approvals, the candidate was implemented, registered, configured, run once through discovery smoke, and rejected. Do not use this intake as authority for additional execution or tuning.
