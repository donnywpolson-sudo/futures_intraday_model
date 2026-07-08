# Pipeline Evidence-Chain Audit

Date: 2026-07-06

Audit target: current `futures_intraday_model` pipeline order and current Tier 1 evidence chain.

Audit mode: read-only evidence review plus this Markdown report. No provider download, data build, WFA rerun, prediction generation, cleanup, staging, commit, push, paper, or live command was run.

## Verdict

Pipeline order verdict: **Pass with caveats**. The declared public order in `PROJECT_OUTLINE.md` is coherent: Phase 1A/1B source and raw evidence, Phase 2 causal base, Phase 3 labels, Phase 4 features, Phase 5 WFA splits, Phase 6 OOS predictions, Phase 7 prediction artifact audit, Phase 8 evaluation/model-selection, Phase 9 bounded research diagnostics, Phase 10 freeze, and Phase 11 locked holdout guard. `scripts.phase7_wfa` is correctly demoted to legacy/internal Phase 6 support, not a public downstream phase.

Current evidence-chain verdict: **Fail for alpha/promotion, usable for diagnostic research only**. The current Tier 1 chain has ordered evidence through Phase 7 and structurally complete Phase 8 diagnostics, but Phase 8 blocks promotion. Current costed OOS is negative, the baseline gate fails, capacity/liquidity evidence is missing, and statistical-validity evidence fails.

Proceed status: **yes with problems for research diagnostics only; no for promotion, freeze, holdout acceptance, paper, or live trading**.

Scores:

| Area | Score | Reason |
| --- | ---: | --- |
| Pipeline order quality | 86 | Phase order and public/internal phase boundaries are clear. |
| Current Tier 1 evidence-chain completeness | 64 | Phase 5/6/7 are evidenced, but broad Phase 2 remains WARN and Phase 8 fails. |
| Current alpha/promotion readiness | 18 | Phase 8 has 30 promotion blockers and `model_promotion_allowed=false`. |
| Paper/live readiness | 0 | Explicitly out of scope; execution, reconciliation, risk, broker, compliance, and ops gates are not implemented as approval evidence. |

## Evidence Reviewed

Primary repo evidence:

- `PROJECT_OUTLINE.md`: public phase order, gates, baseline taxonomy, statistical-validity gate, Phase 10/11 freeze/holdout blockers, production deferral.
- `AUDIT.md`: adversarial audit rubric and hard-fail conditions.
- `configs/alpha_tiered.yaml`: profile ladder, research/holdout/forward partitioning, readiness exceptions.
- `configs/costs.yaml`: tick value, point value, commission, fee, and slippage assumptions.
- `reports/data_audit/current_state/phase1ab_33markets_2010_2026_post_status_placement_refresh_20260706_rerun1/phase1ab_post_status_placement_refresh_summary.md`
- `reports/data_audit/current_state/phase2_readiness_post_historical_6m_tn_exclusions_20260706/active_root_raw_to_causal_readiness_post_historical_6m_tn_exclusions.md`
- `reports/data_audit/current_state/tier1_core_phase34_active_placement_20260706/active_placement_report.json`
- `reports/data_audit/current_state/tier1_core_phase4_self_reference_cleanup_active_placement_20260706/active_placement_report.md`
- `reports/wfa/tier1_core_phase5_split_plan_20260706/split_plan_acceptance_report.md`
- `reports/wfa/tier1_core_phase6_wfa_runner_preflight_20260706/wfa_runner_preflight_report.md`
- `reports/wfa/tier1_core_phase6_full_predictions_20260706/tier1_core_phase6_full_predictions_20260706_predictions_manifest.json`
- `reports/prediction_audit/tier1_core_phase6_full_predictions_20260706/prediction_audit_summary.json`
- `reports/phase8/tier1_core_phase6_full_predictions_20260706/alpha_promotion_decision.json`
- `reports/failure_analysis/tier1_core_phase6_full_predictions_20260706/failure_analysis_summary.json`
- `reports/statistical_validity/tier1_core_phase6_full_predictions_20260706/statistical_validity_summary.json`

External criteria anchors:

- Carr and Lopez de Prado, "Determining Optimal Trading Rules without Backtesting": https://arxiv.org/abs/1408.1159
- Interactive Brokers futures commissions: https://www.interactivebrokers.com/en/pricing/commissions-futures.php
- Interactive Brokers CME fee recovery: https://www.interactivebrokers.com/en/accounts/fees/CME.php
- CME clearing and trading fees: https://www.cmegroup.com/company/clearing-fees.html
- CME E-mini S&P 500 contract specs: https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.contractSpecs.html

## Missing Or Misordered Steps

| Severity | Finding | Evidence | Required fix |
| --- | --- | --- | --- |
| Severe | No promotion path is currently allowed. | `alpha_promotion_decision.json`: `promoted=false`, `research_alpha_ready=false`, `model_promotion_allowed=false`, 30 blockers. | Stop promotion/freeze/holdout/paper/live. Use Phase 8 failure as diagnostic input only. |
| Severe | Statistical-validity gate is failing. | `statistical_validity_summary.json`: `status=FAIL`; missing/failing PBO, Deflated Sharpe, Probabilistic Sharpe, multiple-testing adjustment, and regime breakdowns. | Build a predeclared trial log and run anti-overfit/stat-validity evidence before any model-trust claim. |
| Severe | Baseline discipline is incomplete. | `failure_analysis_summary.json`: baseline gate `FAIL`; missing required `simple_carry`; no-trade baseline beats the candidate because candidate net PnL is negative. | Add required simple futures-native baselines under identical split, cost, policy, and risk assumptions. |
| Severe | Costed economics fail. | `alpha_promotion_decision.json`: gross -19871.875, costs 36123.34, net -55995.215, net Sharpe-like -4.5339, all markets nonpositive net. | Treat this exact model line as rejected unless a separately predeclared new hypothesis is built. Do not rescue-tune. |
| Medium | Capacity/liquidity evidence is missing. | `failure_analysis_summary.json`: capacity/liquidity status `MISSING_EVIDENCE`. | Add liquidity, capacity, market impact, and executable-size evidence before any trading conclusion. |
| Medium | Broad active causal coverage remains WARN. | `active_root_raw_to_causal_readiness_post_historical_6m_tn_exclusions.md`: active-scope raw 526, active causal 518, unapproved raw-without-causal rows are 2025/2026 `6E`, `CL`, `ES`, `ZN`. | Finish separately bounded holdout/forward causal policy and active replacement only if approved. |
| Medium | Local-trade/OHLCV gap proof remains incomplete for local-trade evidence groups. | Current causal readiness report lists `local_trade_2025_2026_v1` with local-trade gate `NOT_RUN`; broad historical group also `NOT_RUN`. | Do not use local-trade proof claims beyond their documented scope until the bounded proof scan or accepted policy disposition exists. |
| Medium | Holdout/forward causal files are staged or blocked, not active. | `staged_phase2_holdout_forward_summary.md`: 2025 staged PASS but no active replacement; 2026 blocked on degraded-row readiness at that run. | Do not run holdout/forward labels, features, WFA, or final-holdout acceptance from those staged artifacts. |
| Low | One current-state refresh is stale after later placements. | `tier1_core_active_chain_refresh_20260706.json` says active labels/features absent, but current file checks show 8 labels, 8 feature parquets, and one prediction parquet now exist. | Prefer later active-placement reports and direct file checks; refresh that current-state summary if it will remain in use. |

No step appears wrongly ordered in the current public run. The main issue is not order; it is that downstream trust gates correctly fail.

## Phase Evidence Table

| Phase | Current order | Current evidence | Result |
| --- | --- | --- | --- |
| 1A | Before raw conversion | Phase 1A archive coverage PASS, 0 missing archives/manifests, 0 invalid manifests. | Pass for inspected broad current-state evidence. |
| 1B | Before Phase 2 | Phase 1B 33/33 market batches PASS, 527/527 expected/raw, 0 source-hash mismatches. | Pass for inspected broad current-state evidence. |
| 2 | Before labels | Broad active readiness is WARN: active-scope raw 526, active causal 518, 8 unapproved raw-without-causal rows. Tier 1 2023/2024 causal chain is present. | Pass for current Tier 1 research scope; warn for broad/holdout/forward scope. |
| 3 | Before features | Active Tier 1 label files exist for `ES`, `CL`, `ZN`, `6E` years 2023/2024. Active placement report status is PASS. | Pass for Tier 1 research scope. |
| 4 | Before WFA splits | Active Tier 1 feature files exist for the same 8 market-years. Self-reference cleanup placement PASS, 114 active features, 0 removed self-reference features present. | Pass for Tier 1 research scope. |
| 5 | Before WFA training/predictions | Split acceptance PASS: chronology, fold counts, purge/embargo, feature-manifest binding, and data-audit universe binding all PASS. | Pass. |
| 6 | Before prediction audit/evaluation | Prediction manifest records 48 folds, 9,172,416 predictions, 0 duplicate predictions, prediction artifact written, artifact evidence ready. | Pass structurally. |
| 7 | Before Phase 8 promotion readiness | Prediction audit summary PASS, `phase7_prediction_audit_ready=true`, 9,172,416 predictions, failure count 0. | Pass structurally. |
| 8 | Before freeze/holdout/promotion | Phase 8 has failure count 0/warnings 0 structurally, but promotion gate FAIL with 30 blockers; costed OOS is negative; statistical-validity gate FAIL. | Fail for alpha/promotion. |
| 9 | After failed diagnostics or for bounded research | Diagnostic/ideation tooling exists and current strategy packets are proposal-only. | Allowed only as bounded research planning. |
| 10 | After approved Phase 8 promotion only | No current promoted Phase 8 decision exists. | Blocked. |
| 11 | After Phase 10 freeze only | No frozen approved artifact chain exists. | Blocked. |

## Highest-Yield Fixes

1. Stop treating the current Tier 1 model line as a candidate for rescue. It failed after realistic costs, failed baseline requirements, and failed statistical-validity gates.
2. Before any new model run, choose exactly one predeclared hypothesis and write its target, features, market/year scope, baselines, costs, acceptance criteria, kill criteria, and trial-log policy.
3. Add the missing simple futures-native baseline set under the same Phase 5 split plan and Phase 8 cost/policy path: no-trade, random-entry/null, simple trend/time-series momentum, simple carry/term-structure where data permits, simple intraday seasonality, and simple mean-reversion/liquidity-window rules.
4. Build anti-overfit evidence before promotion: full trial log, PBO or equivalent, Deflated Sharpe, Probabilistic Sharpe, multiple-testing adjustment, parameter stability, and regime breakdowns.
5. Add capacity/liquidity and execution-realism evidence before any trading conclusion: bid/ask or conservative spread evidence, market impact, fill delay, rejected/partial fills, order throttles, contract-specific liquidity windows, and max size.
6. Finish broad data-scope decisions separately: active replacement policy for staged 2025 holdout causal files, 2026 degraded-session policy and rebuild if approved, and local-trade/OHLCV proof disposition.
7. Keep paper/live gates out of this research pipeline until there is a separate execution system audit covering broker state, order IDs, reconciliations, account/cash/margin, kill switch, monitoring, incident recovery, compliance, and secrets.

## Hard Blocks

- Do not run Phase 10 freeze: Phase 8 is not promoted and promotion is not allowed.
- Do not run Phase 11 final holdout guard for acceptance: no frozen approved artifact chain exists.
- Do not paper trade or live trade: production/order-system, reconciliation, risk, margin, monitoring, and compliance gates are absent.
- Do not tune thresholds or features from the failed Phase 8 result.
- Do not use 2025/2026 staged causal outputs as active holdout/forward evidence until active replacement and downstream gates are separately approved.

## What Could Still Be Wrong

- The audit did not re-run raw-to-report reproduction, so reproducibility is evidenced by manifests/reports, not freshly rebuilt in this audit.
- Cost inputs in `configs/costs.yaml` link to current vendor pages, but this audit did not reconcile every market fee line against a fresh official contract-by-contract fee table.
- Tick values and contract metadata are configured locally, but only selected external source pages were opened during this audit.
- Feature-leakage controls are evidenced by existing audits and naming checks, not by an independent full reimplementation.
- Current ignored/generated reports may be stale if later local artifact edits occurred outside recorded gates; direct existence checks were used only for the active Tier 1 labels/features/prediction parquet.

## Final Answer

The pipeline's phase order is broadly correct. The missing work is not a new phase between existing phases; it is stronger gate evidence before trusting or advancing results. Current Tier 1 evidence can support diagnostic research review only. It cannot support alpha promotion, artifact freeze, final-holdout acceptance, paper trading, or live trading.
