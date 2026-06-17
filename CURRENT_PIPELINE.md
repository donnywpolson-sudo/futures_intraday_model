# Current Pipeline

This repo has a reproducible intraday futures research pipeline. It is not a
production trading system, and the current Tier 1 baseline is locked negative
evidence.

## Current Status

- Tier 1 alias resolution is `tier_1 -> tier_1_research`.
- Current Tier 1 research scope is `ES`, `CL`, `ZN`, and `6E` for 2023-2024.
- Phase 2, Phase 3, Phase 4, Phase 5, Phase 7, and Phase 8 now have
  artifact/scope/provenance guards for the confirmed stale/partial artifact
  failure modes.
- Shared report manifests now distinguish full-scope evidence from partial
  Tier 1 evidence with `partial_scope`, `authoritative`,
  `expected_input_count`, selected/actual input counts, and missing/extra
  market-years where computable.
- Phase 7 fails closed on split-plan profile, resolved profile, markets, years,
  and required provenance/hash mismatches.
- Phase 8 fails closed when the prediction manifest does not match the actual
  prediction parquet path, hash, row count, profile/scope, artifact readiness,
  stale flag, or split-plan provenance.

## Locked Tier 1 Baseline Evidence

Locked run:

- Run: `tier1_locked_baseline_20260616`
- Prediction file:
  `data/predictions/tier1_locked_baseline_20260616/oos_predictions.parquet`
- Prediction manifest:
  `reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json`
- Metrics:
  `reports/metrics/tier1_locked_baseline_20260616_metrics.json`
- Promotion decision:
  `reports/phase8/alpha_promotion_decision.json`

Structural pipeline evidence:

- Phase 2 causal data: `WARN`, full Tier 1 scope, `authoritative=true`,
  `partial_scope=false`, failures `0`, warnings `4`.
- Phase 2 warnings are synthetic-gap warnings for `ZN 2023`, `ZN 2024`,
  `6E 2023`, and `6E 2024`. These were explicitly accepted for this locked
  evidence after local provenance checks; they are not a model edge.
- Phase 3 labels: `PASS`, full Tier 1 scope, `authoritative=true`,
  failures `0`, warnings `0`.
- Phase 4 baseline features: `WARN`, full Tier 1 scope, `authoritative=true`,
  failures `0`, warnings from self-reference unavailable features.
- Phase 5 WFA split plan: `PASS`, folds `48`, markets `4`, failures `0`.
- Phase 7 WFA was run as 8 fold shards and combined:
  predictions `4,616,712`, folds `48`, failures `0`,
  `artifact_evidence_ready=true`.
- Phase 8 structural evaluation passed with failures `0`, but promotion failed.

Costed OOS policy result:

- Policy rows: `1,154,178`
- Trades: `780`
- Gross dollars: `-20,287.50`
- Costs: `22,357.88`
- Net dollars: `-42,645.38`
- Net Sharpe-like: `-5.1086`
- Cost drag to absolute gross: `1.1021`
- `research_alpha_ready=false`
- `model_promotion_allowed=false`
- `promoted=false`

Market result:

- `6E`: `281,895` rows, `0` trades, net `0`.
- `CL`: `300,436` rows, `137` trades, net `-8,489.38`.
- `ES`: `342,821` rows, `643` trades, net `-34,156.00`.
- `ZN`: `229,026` rows, `0` trades, net `0`.

## Diagnostic Decisions

- 6E and ZN zero-trade behavior is explained by current policy gates and label
  base rates, not by artifact/provenance failure.
- Fade is not the blocking gate for 6E/ZN. Direction edge, flat probability,
  and trend-danger probability block all rows under the current policy.
- Label/feature alignment passed:
  - policy rows matched feature rows: `1,154,178 / 1,154,178`
  - return target match rate: `1.0`
  - direction target match rate: `1.0`
  - decision: `targets_align_return_scale_not_flagged_review_policy_signal_quality`
- Target-construction feasibility did not justify a target semantics change.
  The current fixed 15m deadzone direction oracle is positive in hindsight, but
  the pathwise first-hit barrier candidate is net negative.
- Policy signal alignment decision:
  `direction_edge_calibration_issue_not_policy_logic_bug`.
- Direction-edge calibration decision:
  `direction_probabilities_not_tradeable_without_new_edge_model`.
- Event-level edge feasibility decision:
  `does_not_support_new_edge_model_research`.
- Event-level base-signal candidate result:
  `11,398` non-overlapping events, gross `23,558.13`, costs `281,986.73`,
  net `-258,428.60`, direction accuracy `0.2987`, positive folds `0 / 48`.
- Signal trade-quality diagnostics found small positive threshold pockets, but
  they are not accepted:
  - best net case had only `31` trades
  - the only `>=100` trade positive case required dropping the flat gate, which
    is a policy semantics change
  - that case had only `106` trades, traded in `11` folds, positive in `6`, and
    was concentrated in ES while CL remained materially negative

## Current Decision

Decision: `TIER1_LOCKED_BASELINE_NO_GO`.

Do not:

- promote this model or policy
- tune thresholds against this locked run
- rerun near-neighbor policy variants to rescue this baseline
- run full-market/full-fold WFA again for this same baseline line
- treat the small positive threshold pockets as alpha
- start a new edge-model experiment from the saved base-signal candidate set

The current evidence says the Tier 1 baseline has weak or negative gross edge
after realistic costs and non-overlapping event handling. Cost accounting is
not the only problem.

## Phase 9 Cost-Clearability Feasibility

The Tier 1 cost-clearability feasibility harness is also stopped as currently
registered.

- Harness report:
  `reports/pipeline_audit/tier1_cost_clearability_event_harness_20260617T002348Z.md`
- JSON report:
  `reports/pipeline_audit/tier1_cost_clearability_event_harness_20260617T002348Z.json`
- Decision: `STOP_BRANCH_PERMANENTLY`
- Scope: `tier_1 -> tier_1_research`, `ES`, `CL`, `ZN`, `6E`, 2023-2024
- Events: `154,728`
  - `ES`: `43,712`
  - `CL`: `40,352`
  - `6E`: `38,318`
  - `ZN`: `32,346`
- Passed gates:
  - schema/provenance and all markets have events
  - minimum events per market
  - model beats random-label, shuffled-feature, market/year/session baseline,
    and inverse-score controls in discovery and confirmation
  - positive fold requirement: `12 / 12` positive folds for every market
  - top-5% cost drag below 50%: `0.1460`
  - non-ES markets participate materially
- Failed gate:
  - positive oracle net concentration limit. ES contributed `57.66%` of
    positive oracle net, above the pre-registered `35%` cap.

This harness output is oracle/feasibility evidence only. It is not executable
PnL or strategy PnL. Do not proceed from it to a direction model or full Tier 1
WFA. Any next harness must be materially different and must address
cross-market concentration before direction modeling.

## Phase 9 Market-Balanced Cost-Clearability Feasibility

The market-balanced Tier 1 cost-clearability follow-up is also stopped.

- Harness report:
  `reports/pipeline_audit/tier1_market_balanced_cost_clearability_harness_20260617T012137Z.md`
- JSON report:
  `reports/pipeline_audit/tier1_market_balanced_cost_clearability_harness_20260617T012137Z.json`
- Smoke report:
  `reports/pipeline_audit/tier1_market_balanced_cost_clearability_smoke_20260617T011545Z.md`
- Decision: `STOP_BRANCH_PERMANENTLY`
- Scope: `tier_1 -> tier_1_research`, `ES`, `CL`, `ZN`, `6E`, 2023-2024
- Events: `154,728`
  - `ES`: `43,712`
  - `CL`: `40,352`
  - `6E`: `38,318`
  - `ZN`: `32,346`
- Passed gates:
  - minimum events and top-5 rows by market
  - positive fold requirement by market
  - fold/hour concentration limit
- Failed gates:
  - each market beats all controls by stage
  - market quality requirements
  - market contribution balance
- Main failures:
  - market-local model did not beat `pooled_score_transfer` in ES, CL, and
    ZN where listed
  - ZN top-5 cost drag was `0.5418`, above the registered `0.50` cap
  - market contribution balance failed: ES `58.32%`, CL `27.48%`, 6E
    `10.25%`, ZN `3.95%`

Both pooled and market-balanced cost-clearability versions failed
pre-registered robustness gates. The cost-clearability research branch is
stopped. Do not proceed from it to direction modeling, policy work, or full
Tier 1 WFA. Next valid work must be a materially different target/feature
hypothesis, not a rescue variant of cost-clearability.

## Data Audit Status

The old data-audit action list is complete for the current Tier 1 decision. It
is now historical context, not the active next-step file.

Current Tier 1 data-audit interpretation:

- Usable market-years for the current Tier 1 evidence:
  `ES 2023`, `ES 2024`, `CL 2023`, `CL 2024`, `ZN 2023`, `ZN 2024`,
  `6E 2023`, `6E 2024`.
- Diagnostic-only: none under the current audited-universe policy.
- Quarantined: none under the current audited-universe policy.
- DBN-to-raw-parquet parity found no dropped rows and no OHLCV/timestamp
  mismatches for the previously blocked Tier 1 market-years.
- Acceptance relies on Databento's documented OHLCV no-trade convention plus
  local DBN/parquet provenance.
- Independent historical L1/trades proof is still unavailable under the
  current subscription.
- No Phase 2/session/fill semantic change is justified by the current data
  audit.

## Next Valid Work

The current baseline line is stopped.

The cost-clearability branch is also stopped as currently registered, including
the market-balanced follow-up.

Next valid work must be a separate research direction with a new hypothesis and
pre-registered stop rules. Do not run more cost-clearability rescue variants.
Acceptable directions are:

- new target-construction research
- new feature-generation research
- a genuinely new ES-only custom hypothesis on unused folds from
  `reports/wfa_phase9_es_tier2_refresh/split_plan.json`

Do not reuse the failed built-in ES feature-family sweep or the stopped Phase 9
hypotheses as "new" work:

- `time_buckets`
- `post_shock_volume_confirmed_continuation`
- `compression_breakout_participation_filter`
- `es_late_session_close_long_bias_context`
- `tier2_es_auction_acceptance_reversal_context`
- `tier2_es_prior_session_cross_market_context`
- the 15 registered ES feature families in
  `reports/pipeline_audit/tier1_es_harness_family_sweep.md`

## Phases

- Phase 1A: download Databento DBN archives.
- Phase 1B: convert DBN archives into raw yearly parquet files.
- Phase 2: clean and normalize bars into causal session-aware data.
- Phase 3: create future-looking labels and cost-aware targets.
- Phase 4: build model features while excluding target and leakage columns.
- Phase 5: build walk-forward train/test splits with purge and embargo.
- Phase 6: no separate implemented phase in this repo.
- Phase 7: train baseline models and save out-of-sample predictions.
- Phase 8: score predictions with deterministic research policy, costs,
  promotion gates, and artifact/provenance guards.

## Useful Checks

```powershell
python -m scripts.validation.check_tier_2_coverage --profile tier_1 --stage all
python -m pytest tests\phase7_wfa\test_run_wfa.py tests\phase8_model_selection\test_evaluate_predictions.py -q
python -m scripts.phase8_model_selection.evaluate_predictions --predictions data/predictions/tier1_locked_baseline_20260616/oos_predictions.parquet --predictions-manifest reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json --run tier1_locked_baseline_20260616 --require-promotion-ready
```

The last command is expected to fail promotion because the locked model is not
promotion-ready. A structural pass with `alpha_ready=False` is the expected
state for this evidence.
