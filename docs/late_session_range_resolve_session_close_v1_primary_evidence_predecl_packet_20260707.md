# Late Session Range Resolve Session Close Primary-Evidence Predeclaration Packet

Hypothesis ID: `late_session_range_resolve_session_close_v1`

Status: `EVIDENCE_PACKET_READY_NO_IMPLEMENTATION`

Evidence date: 2026-07-07

Scope: ES only, 2023/2024 research folds only.

Allowed use: predeclaration evidence review only. This packet does not approve target implementation, registry or trial-ledger mutation, alpha-discovery config generation, source-test execution, discovery-run, WFA/modeling, Phase 8, provider downloads, cost-config mutation, tuning, promotion, artifact freeze, paper trading, or live trading.

## Verified Primary Evidence

- `session_compression_breakout_30m_v1` is stopped. Registry status is `REJECTED`, `wfa_allowed=false`, `source_reports` point to the generated session-compression discovery smoke MD/JSON, and `next_allowed_actions=[]`.
- The authoritative session-compression discovery JSON reports `decision=STOP_CLASS_COLLAPSE`, `candidate_passed=false`, `candidate_stopped=true`, `failure_count=0`, `top_total_net_dollars=-1540.5`, and `positive_top_net_fold_count=3`.
- Session-compression stopped on class-balance and net-economics evidence: long/short/flat counts were `514/505/5985`, duplicate overlap with the current 15-minute deadzone target was `0.7723258096172718 <= 0.8`, and `target_smoke_is_tradability_proof=false`.
- `opening_drive_failed_followthrough_15m_v1` is stopped. Registry status is `REJECTED`, `wfa_allowed=false`, `source_reports` point to the generated opening-drive failed-followthrough discovery smoke MD/JSON, and `next_allowed_actions=[]`.
- Opening-drive failed-followthrough stopped with `STOP_CLASS_COLLAPSE`, long/short/flat counts `445/283/4574`, duplicate overlap `1.0` versus cap `0.8`, top net `2519.0`, and `target_smoke_is_tradability_proof=false`.
- `vwap_reclaim_continuation_15m_v1` is stopped. Registry status is `REJECTED`, `wfa_allowed=false`, `source_reports` point to the generated VWAP reclaim discovery smoke MD/JSON, and `next_allowed_actions=[]`.
- VWAP reclaim stopped with `STOP_CLASS_COLLAPSE`, long/short/flat counts `429/528/5806`, duplicate overlap `1.0` versus cap `0.8`, top net `1775.5`, and `target_smoke_is_tradability_proof=false`.
- `opening_range_acceptance_continuation_event_capture_30m_v2` is stopped. Registry status is `REJECTED`, `wfa_allowed=false`, `source_reports` point to the generated ORAC v2 discovery smoke MD/JSON, and `next_allowed_actions=[]`.
- ORAC v2 stopped with `STOP_CLASS_COLLAPSE`, long/short/flat counts `237/225/0`, top net `-52.0`, and only target-construction smoke evidence.
- `docs/pipeline_evidence_chain_audit_20260706.md` records the current Tier 1 chain as diagnostic research only, not alpha/promotion-ready.
- `docs/adversarial_futures_quant_system_audit_20260707.md` gives an audit verdict of `Fail` and records severe blockers including costed OOS failure, baseline failure, statistical-validity failure, missing complete trial log, missing capacity/liquidity/market-impact evidence, and no paper/live readiness.
- `configs/costs.yaml` currently sets ES `round_turn_cost_dollars=29.50` and `round_turn_cost_ticks=2.36`. `docs/orac_v2_es_round_turn_cost_evidence_20260707.md` supports those ES dollar components as supplemental dated evidence while noting the unchanged config effective-date caveat.
- `configs/market_sessions.yaml` maps ES to `cme_globex_17_16_ct`, timezone `America/Chicago`, regular open `17:00`, and regular close `16:00`.
- `PROJECT_OUTLINE.md` states strategy ideation outputs under `reports/pipeline_audit/strategy_candidate_ideation/` are draft-only, conversion-required, not wizard-runnable, and `not_model_trust_evidence`.

## Draft Context, Not Proof

The draft dossier `reports/pipeline_audit/strategy_candidate_ideation/010_late_session_range_resolve_session_close_v1.json` is useful only as naming and implementation-context handoff. It is explicitly `draft_only=true`, `conversion_required=true`, `current_wizard_compatible=false`, and `evidence_status=not_model_trust_evidence`.

This packet does not rely on that draft as performance proof. It uses the draft only to name a materially new candidate family for later implementation planning.

## Predeclared Hypothesis

Research question: after ES forms a causal late-session range before the configured regular session close, does a directional break from that completed range identify cost-clearing continuation into the session close?

Candidate rules for any later implementation plan:

- Market and years: ES only, 2023/2024 research folds only.
- Session basis: use existing ES `cme_globex_17_16_ct` session metadata from `configs/market_sessions.yaml`; do not create a separate session calendar from this packet.
- Late-session range: use completed same-session bars from `14:00` through `15:00` America/Chicago on normal sessions, requiring the full range to exist before any event can fire. Early-close sessions must be invalid unless a later source-test plan predeclares an early-close-specific rule before implementation.
- Entry condition: after `15:00` and before configured regular close, a long event requires a close above the completed late-session range high by at least one ES tick; a short event requires a close below the completed late-session range low by at least one ES tick.
- Direction: continuation in the direction of the range break.
- Entry timing: next bar open after the qualifying break event.
- Exit: configured same-session regular close.
- Target threshold: terminal close movement in the event direction must exceed `max(round_turn_cost_ticks + min_profit_ticks, prior 60-bar 1m close-diff std scaled to remaining minutes until close)`.
- Costs: use unchanged `configs/costs.yaml`; do not mutate costs from this packet.
- Feature policy: any later implementation may use only pre-event OHLC/session state, completed late-session range state, and existing leak-checked feature columns available at the event timestamp. It must not use target, label, future, entry, exit, or post-event session-close columns as model features.
- Validity: preserve existing causal, session, synthetic/boundary/roll, feature-validity, and target-validity gates.
- Event policy: use non-overlapping events before fold scoring.
- Thresholds and windows: predeclare before any source-test, preflight, discovery-packet, or discovery output is generated; do not tune after seeing source-test, preflight, packet, or discovery output.

## Material Difference From Stopped Branches

This candidate is materially different from stopped session-compression because it does not use a rolling compression box, compression percentile, compression breakout threshold, or fixed 30-minute timeout exit.

It is materially different from stopped opening-drive failed-followthrough because it does not use opening-drive state, failed continuation attempts, or reversal away from the opening-drive side.

It is materially different from stopped VWAP reclaim because it does not use VWAP distance, VWAP excursion, or reclaim-through-VWAP logic.

It is materially different from stopped ORAC v2 because it does not use opening-range highs/lows, first post-opening-range acceptance, or opening-range event capture.

It tests late-session range resolution into the configured session close, not failed extremes, VWAP stretch/reclaim, opening-range acceptance, first-touch path capture, compression-to-expansion, or a renamed stopped target.

## Required Gates For Any Later Implementation

A later implementation plan must stop before discovery unless separately approved and must require:

- focused source tests for long, short, flat/invalid, causal range formation, same-session close exit, insufficient range or missing close rejection, early-close rejection, non-overlap, and cost-threshold behavior;
- preflight and discovery-packet only before any discovery-run approval;
- registry status `CANDIDATE`, `wfa_allowed=false`, empty `source_reports`, and no WFA/Phase 8 permission at registration time;
- trial ledger event with empty evidence at registration time;
- duplicate-overlap check against the current 15-minute deadzone target and the stopped session-compression target;
- class-balance and event-count gates;
- stable-fold and positive-stage-net gates;
- JSON-first review if any future discovery smoke is separately approved;
- trial-log policy that records this packet, implementation timestamp, data hashes, cost config hash, model or target construction parameters, and all tested variants before any model-trust claim.

## Stop Conditions

Stop without implementation if:

- a later review cannot specify late-session range formation, break timing, and session-close exit rules causally;
- the candidate would depend on session-compression, opening-drive failed-followthrough, VWAP reclaim, ORAC/opening-range acceptance, or first-touch path-capture logic;
- regular session close context is missing, ambiguous, early-close dependent, or inconsistent with `configs/market_sessions.yaml`;
- any required source test would need holdout or forward rows;
- cost, threshold, feature, fold, market, year, session-window, or close-rule tuning is proposed before implementation;
- any step tries to rerun stopped target discovery, run discovery, WFA/modeling, Phase 8, provider downloads, cost mutation, promotion, artifact freeze, paper/live, commit, or push from this packet.

## Next Allowed Step

Plan only a bounded source/test registration phase for `late_session_range_resolve_session_close_v1`. That future plan may propose source-file changes, target construction rules, focused tests, registry/ledger registration, and an alpha-discovery preflight/discovery-packet config, but it must stop before any discovery-run.
