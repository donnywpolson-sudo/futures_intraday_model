# Opening Drive Failed Followthrough 15m Primary-Evidence Predeclaration Packet

Hypothesis ID: `opening_drive_failed_followthrough_15m_v1`

Status: `EVIDENCE_PACKET_READY_NO_IMPLEMENTATION`

Evidence date: 2026-07-07

Scope: ES only, 2023/2024 research folds only.

Allowed use: predeclaration evidence review only. This packet does not approve target implementation, registry or trial-ledger mutation, alpha-discovery config generation, source-test execution, discovery-run, WFA/modeling, Phase 8, provider downloads, cost-config mutation, tuning, promotion, artifact freeze, paper trading, or live trading.

## Verified Primary Evidence

- `vwap_reclaim_continuation_15m_v1` is stopped. Registry status is `REJECTED`, `wfa_allowed=false`, `source_reports` point to the generated VWAP discovery smoke MD/JSON, and `next_allowed_actions=[]`.
- The authoritative VWAP discovery JSON reports `decision=STOP_CLASS_COLLAPSE`, `failure_count=0`, `top_total_net_dollars=1775.5`, and `positive_top_net_fold_count=2`.
- VWAP failed class-balance and duplicate-target gates: long/short/flat counts were `429/528/5806`, long and short counts were below the `1000` minimum, and overlap with the current 15-minute deadzone target was `1.0` versus cap `0.8`.
- `opening_range_acceptance_continuation_event_capture_30m_v2` is stopped. Registry status is `REJECTED`, `wfa_allowed=false`, `source_reports` point to the generated ORAC v2 discovery smoke MD/JSON, and `next_allowed_actions=[]`.
- The authoritative ORAC v2 discovery JSON reports `decision=STOP_CLASS_COLLAPSE`, `top_total_net_dollars=-52.0`, and `positive_top_net_fold_count=2`. Long/short/flat event counts were `237/225/0`.
- `docs/pipeline_evidence_chain_audit_20260706.md` records the current Tier 1 chain as diagnostic research only, not alpha/promotion-ready.
- `docs/adversarial_futures_quant_system_audit_20260707.md` gives an audit verdict of `Fail` and records severe blockers including costed OOS failure, baseline failure, statistical-validity failure, missing complete trial log, missing capacity/liquidity/market-impact evidence, and no paper/live readiness.
- `PROJECT_OUTLINE.md` states strategy ideation outputs under `reports/pipeline_audit/strategy_candidate_ideation/` are draft-only, conversion-required, not wizard-runnable, and `not_model_trust_evidence`.

## Draft Context, Not Proof

The draft dossier `reports/pipeline_audit/strategy_candidate_ideation/002_opening_drive_failed_followthrough_15m_v1.json` is useful only as a naming and implementation-context handoff. It is explicitly `draft_only=true`, `conversion_required=true`, `current_wizard_compatible=false`, and `evidence_status=not_model_trust_evidence`.

This packet does not rely on that draft as performance proof. It only uses the draft to name a materially new candidate family for later implementation planning.

## Predeclared Hypothesis

Research question: after a strong causal ES opening drive fails to follow through, does reversal away from the failed drive side identify cost-clearing 15-minute movement?

Candidate rules for any later implementation plan:

- Market and years: ES only, 2023/2024 research folds only.
- Entry condition: a completed same-session opening-drive state followed by a later failed continuation attempt in the drive direction, using only bars available at the event timestamp.
- Direction: reversal direction opposite the failed opening-drive continuation side.
- Entry timing: next bar open after the failed-followthrough event.
- Exit: fixed 15-minute same-session exit.
- Costs: use unchanged `configs/costs.yaml`; do not mutate costs from this packet.
- Validity: preserve existing causal, session, synthetic/boundary/roll, feature-validity, and target-validity gates.
- Event policy: use non-overlapping events before fold scoring.
- Thresholds and windows: predeclare before any discovery output is generated; do not tune after seeing source-test, preflight, packet, or discovery output.

## Material Difference From Stopped Branches

This candidate is materially different from the stopped VWAP reclaim branch because it does not use VWAP distance, VWAP excursion, or VWAP reclaim logic. It is also materially different from stopped ORAC v2 because it does not use opening-range highs/lows, first post-opening-range acceptance, or opening-range acceptance event capture.

This candidate must not reuse rejected VWAP reclaim or ORAC v2 code paths as a renamed hypothesis. Any later implementation must encode opening-drive failed-followthrough state as its own causal event definition.

## Required Gates For Any Later Implementation

A later implementation plan must stop before discovery unless separately approved and must require:

- focused source tests for long, short, flat/invalid, same-session, non-overlap, and cost-threshold behavior;
- preflight and discovery-packet only before any discovery-run approval;
- registry status `CANDIDATE`, `wfa_allowed=false`, empty `source_reports`, and no WFA/Phase 8 permission at registration time;
- trial ledger event with empty evidence at registration time;
- duplicate-overlap check against the current 15-minute deadzone target;
- class-balance and event-count gates;
- stable-fold and positive-stage-net gates;
- JSON-first review if any future discovery smoke is separately approved.

## Stop Conditions

Stop without implementation if:

- a later review cannot specify opening-drive and failed-followthrough event rules causally;
- the candidate would depend on VWAP reclaim, ORAC/opening-range acceptance, or first-touch path-capture logic;
- any required source test would need holdout or forward rows;
- cost, threshold, feature, fold, market, or year tuning is proposed before implementation;
- any step tries to run discovery, WFA/modeling, Phase 8, provider downloads, cost mutation, promotion, artifact freeze, paper/live, commit, or push from this packet.

## Next Allowed Step

Plan only a bounded source/test registration phase for `opening_drive_failed_followthrough_15m_v1`. That future plan may propose source-file changes, target construction rules, focused tests, registry/ledger registration, and an alpha-discovery preflight/discovery-packet config, but it must stop before any discovery-run.
