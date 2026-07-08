# Post-Stop Research Direction Packet 20260708

Status: `HISTORICAL_CLOSEOUT_SUPERSEDED_BY_VOLUME_PACE_REJECTED_DISPOSITION`

This packet closed the alpha execution queue after the Tier 1 weak-alpha stop and the then-rejected discovery branches. It is historical planning evidence only. Later separate approvals used this direction to create, implement, register, configure, run, and reject `volume_pace_breakout_continuation_30m_v1`. This packet does not approve data builds, discovery runs, WFA/modeling, Phase 8 refreshes, promotion, artifact freeze, paper trading, or live trading.

## Current Disposition Reconciliation

- As of the 2026-07-08 disposition update, `volume_pace_breakout_continuation_30m_v1` is present in the target registry as `REJECTED`, `wfa_allowed=false`, with `next_allowed_actions=[]`.
- The registry attaches `reports/pipeline_audit/volume_pace_source_packet_20260708_volume_pace_breakout_continuation_30m_v1_discovery_smoke.{md,json}` as source reports.
- The trial ledger records the original `register_candidate` row plus one rejected `phase9_discovery_smoke` row: `volume_pace_breakout_continuation_30m_v1_discovery_smoke_rejected_20260708t204156z`.
- The authoritative discovery decision is `STOP_CLASS_COLLAPSE`, with long/short/flat counts `98/106/1100`, duplicate overlap `0.8186274509803921` versus cap `0.8`, discovery top total net `729.0`, and `2 of 4` discovery folds positive.
- Do not continue volume pace through rerun, tuning, WFA/modeling, Phase 8, provider, promotion, artifact freeze, paper, or live work.

## Sources Reconciled

- `CODEX_HANDOFF.md`
- `PROJECT_OUTLINE.md`
- `manifests/target_hypotheses/registry.json`
- `manifests/target_hypotheses/trial_statuses.jsonl`
- `reports/phase8/tier1_core_phase6_full_predictions_20260706/alpha_promotion_decision.json`
- `reports/failure_analysis/tier1_core_phase6_full_predictions_20260706/failure_analysis_summary.json`
- `reports/statistical_validity/tier1_core_phase6_full_predictions_20260706/statistical_validity_summary.json`
- `reports/model_trust_audit/codex_model_trust_audit_20260707T000000Z/model_trust_audit.{json,md}`
- `reports/candidate_rescue_feasibility/opening_range_acceptance_continuation_30m_v1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/rescue_feasibility.json`
- Existing discovery-smoke reports referenced by the target registry for rejected branches.

## Verified Facts

- `PROJECT_OUTLINE.md` remains the runnable workflow authority and does not authorize broad data builds, WFA/model runs, provider downloads, cleanup, artifact promotion, paper trading, or live trading by itself.
- `PROJECT_OUTLINE.md` says stopped branches must not be reused as new hypotheses, promotion readiness must fail closed when baseline/statistical/portfolio evidence is missing or failing, and paper/live readiness claims remain deferred.
- `CODEX_HANDOFF.md` records `STOP_TIER1_WEAK_ALPHA` for `tier1_core_phase6_full_predictions_20260706`.
- The Tier 1 Phase 8 promotion decision has `promoted=false`, `research_alpha_ready=false`, and `model_promotion_allowed=false`.
- Tier 1 economics are negative before and after costs: gross dollars `-19871.875000000156`, net dollars `-55995.21500000016`, and average net dollars per trade `-41.57031551596151`.
- Tier 1 does not beat the no-trade baseline and still lacks required comparable baseline, capacity/liquidity, market-impact, regime, and statistical-validity evidence.
- The statistical-validity report is `FAIL`, with failures for PBO, Deflated Sharpe, Probabilistic Sharpe, multiple-testing adjustment, and regime breakdowns.
- The model-trust audit permits `research_only` use and does not support promotion, artifact freeze, paper trading, or live trading.
- The target registry has exactly one non-rejected hypothesis: `opening_range_acceptance_continuation_30m_v1`, status `FROZEN`, `wfa_allowed=true`, `next_allowed_actions=["PREPARE_BOUNDED_NEXT_PHASE_PLAN"]`.
- All other listed target hypotheses in the registry are `REJECTED` with `wfa_allowed=false` and no next allowed actions.
- `volume_pace_breakout_continuation_30m_v1` is now one of the rejected target hypotheses after a separately approved source/test, registration, config, discovery-smoke, and disposition sequence.
- The trial ledger records `opening_range_acceptance_continuation_30m_v1` as frozen after discovery, confirmation, and locked target-construction smokes, but that evidence is target-smoke readiness only.
- ORAC v1 rescue feasibility reports `decision=V1_NOT_RESCUED_V2_HYPOTHESIS_REQUIRED`, `v1_rescue_allowed=false`, `tuning_or_selection_allowed=false`, `promotion_allowed=false`, and `live_execution_ready=false`.
- ORAC v1 first-touch diagnostics did not rescue the executable policy; stop-first positive grids were `0/36`.

## Decision

The current alpha queue is closed for execution.

Do not continue Tier 1, ORAC v1 rescue, ORAC v2, VWAP reclaim, opening-drive failed-followthrough, session-compression breakout, late-session range-resolution, or any other rejected branch through discovery reruns, threshold changes, WFA/modeling, Phase 8, promotion, artifact freeze, paper trading, or live trading.

At the time of this packet, the next safest research direction was `NEW_HYPOTHESIS_INTAKE_ONLY`: a doc-only intake gate for a materially new, predeclared hypothesis. That direction produced the volume-pace intake path, which has since completed through one bounded discovery smoke and ended as `REJECTED`. This packet is no longer active authority for a volume-pace next phase.

## New-Hypothesis Intake Criteria

A future intake packet must include:

- Hypothesis ID, target family, market/year scope, entry event, exit horizon, cost assumptions, and primary/secondary metrics.
- Explicit material-difference proof against Tier 1, ORAC v1/v2, VWAP reclaim/reversion, opening-drive failed-followthrough, session-compression breakout, late-session range-resolution, and other registry-rejected branches.
- Predeclared forbidden actions: no retuning after seeing results, no stopped-branch relabeling, no holdout/forward selection, no cost-config mutation, no provider download, no WFA/modeling, no Phase 8, no promotion, no artifact freeze, no paper/live work without later bounded approval.
- Required controls: no-trade, random-entry matched by session/count/direction, simple trend, simple mean-reversion, intraday seasonality, and carry or term-structure where data supports it.
- Stop criteria: class collapse, duplicate-target overlap above cap, nonpositive net under base or 2x costs, fewer than half folds positive, missing comparable baselines, missing full trial log, PBO/Deflated Sharpe/Probabilistic Sharpe failure, missing regime evidence, or any evidence conflict against the registry/trial ledger.
- Evidence boundaries: ideation cards are draft context only; registry, trial ledger, project outline, command output, and report JSON/MD are primary repo evidence.

## Later Approval Packet

If the user later approves intake work, the first follow-up should still be doc-only.

Exact allowed scope:

- Read `CODEX_HANDOFF.md`, `PROJECT_OUTLINE.md`, `manifests/target_hypotheses/registry.json`, `manifests/target_hypotheses/trial_statuses.jsonl`, and relevant existing report summaries only.
- Write one proposed intake document under `docs/` and, if needed, update `CODEX_HANDOFF.md`.

Forbidden actions:

- Do not mutate `data/**`, `reports/**`, model artifacts, predictions, configs, registry, or trial ledger.
- Do not run data/model/discovery/provider commands.
- Do not tune or rerun stopped candidates.
- Do not stage, commit, push, promote, freeze, paper trade, or live trade without separate explicit approval.

Timeout and stop budget:

- Maximum 45 minutes.
- Stop after the first unreconciled contradiction between registry, trial ledger, and report summaries.

Stop condition:

- Produce exactly one doc-only proposed intake path, or state `NO_IMPLEMENTABLE_NEW_HYPOTHESIS_INTAKE` if the evidence does not support a materially distinct hypothesis.

Validation:

- `python -m scripts.validation.check_coordination_docs`
- `git diff --check`
- `git status --short`
