# Adversarial Current Project Evidence-Gate Quant Audit

Date: 2026-07-09

Audit target: current `futures_intraday_model` evidence state, centered on `tier1_core_phase6_full_predictions_20260706` and current target-hypothesis status. This is an evidence-gate audit, not a live strategy approval review.

Audit mode: report-only local primary-evidence review. No provider download, data build, target discovery, source test, WFA/modeling, Phase 8 refresh, generated-report command, registry/ledger mutation, promotion, artifact freeze, final-holdout action, paper/live command, staging, commit, or push was run.

## Verdict

Verdict: **Fail / Blocked for trading and alpha acceptance**.

The current project state does not contain an accepted profit profile, accepted win rate, or capital-ready strategy. The current Tier 1 line is closed for alpha evidence, future modeling is not allowed from this line, and promotion/paper/live readiness is not established.

Proceed status: **no** for model promotion, artifact freeze, final holdout acceptance, paper trading, live trading, or treating any current stopped/frozen/rejected branch as tradable alpha. Proceed status is **yes only for a separately predeclared evidence program** that starts from explicit baseline/null/statistical/execution scope.

Overall adversarial score: **22/100**.

Reason for the lower score versus the 2026-07-07 audit: the later July 9 closeout now classifies the current line as terminal for alpha evidence, with modeling pause required and promotion disallowed.

## Evidence Boundary

Verified local facts:

- `reports/model_trust_audit/alpha_evidence_completion_closeout_20260709T035929Z/alpha_evidence_completion_closeout.json` reports `verdict=CLOSE_CURRENT_LINE_NO_ALPHA_EVIDENCE`, `modeling_pause_required=true`, `future_modeling_allowed=false`, `future_evidence_work_allowed=true`, and `promotion_allowed=false`.
- The same closeout reports bucket status counts `PASS=6`, `FAIL=6`, `MISSING_EVIDENCE=11`, with closeout classifications `terminal_fail=5`, `missing_required_evidence=11`, `diagnostic_pass_only=6`, and `not_actionable_for_current_line=1`.
- `reports/model_trust_audit/alpha_evidence_gap_matrix_20260709T034313Z/alpha_evidence_gap_matrix.json` reports `verdict=PAUSE_MODELING_BASELINE_NULL_EXECUTION_EVIDENCE_INCOMPLETE` and `alpha_evidence_ready=false`.
- `reports/phase8/tier1_core_phase6_full_predictions_20260706/alpha_promotion_decision.json` reports `promoted=false`, `research_alpha_ready=false`, and `model_promotion_allowed=false`.
- The Phase 8 costed OOS block reports gross return `-19871.875`, costs `36123.34`, net return `-55995.215`, trade count `1347`, average net per trade `-41.5703`, net Sharpe-like `-4.5339`, max drawdown `-56962.245`, profit factor `0.6699`, and cost drag to absolute gross `1.8178`.
- `reports/failure_analysis/tier1_core_phase6_full_predictions_20260706/failure_analysis_summary.json` reports baseline comparison `FAIL`, candidate does not beat no-trade, `simple_carry` is missing, and capacity/liquidity status is `MISSING_EVIDENCE`.
- `reports/statistical_validity/tier1_core_phase6_full_predictions_20260706/statistical_validity_summary.json` reports statistical validity `FAIL`; PBO, Deflated Sharpe, and multiple-testing adjustment fail as missing trial-log evidence; Probabilistic Sharpe and regime breakdowns fail.
- `configs/costs.yaml` contains repo-configured costs and ES tick metadata, including ES tick size `0.25`, tick value `$12.50`, point value `$50.00`, round-turn cost `2.36` ticks / `$29.50`, fixed one-tick-per-side slippage, and `live_fill_model_available=false`.
- `live_ops` is intentionally broker-agnostic and disabled/paper-only by default. `LiveBroker.place_order` raises `NotImplementedError`; risk and data gates block live broker mode.
- `manifests/target_hypotheses/registry.json` currently records `opening_range_acceptance_continuation_30m_v1` as `FROZEN` / `wfa_allowed=true`, and current recent rejected candidates including `first_hour_midday_pullback_continuation_30m_v1` as `REJECTED` / `wfa_allowed=false`.

Inferences:

- Because the current line loses before and after costs, a new execution wrapper, kill switch, or risk overlay cannot make the existing evidence capital-ready.
- Because capacity, liquidity windows, spread/slippage validation, delay stress, and partial-fill/reject evidence are missing, any live/paper profitability claim would be unsupported even if model metrics were positive.

Assumptions:

- Cost and fee values are treated as local repo-configured assumptions only. This audit did not browse official IBKR/CME pages or verify current fee schedules.
- Ignored generated artifacts may be stale unless cited by current tracked docs, handoff, or directly inspected report paths above.

## Gate Score Table

| Gate | Area | Score | Confidence | Main weakness | Required fix |
|---|---|---:|---|---|---|
| A | Intended use and thesis | 35 | High | Current line is closed; no accepted current thesis remains | Start only with a new predeclared evidence program |
| B | Futures contract and universe integrity | 40 | Med | Config metadata exists, but executable contract/roll/margin proof is incomplete | Add official contract, roll, margin, and tradable contract mapping evidence |
| C | Data provenance and point-in-time integrity | 55 | Med | Research chain has substantial evidence but broad active scope has caveats | Keep current-scope evidence explicit; do not generalize to holdout/forward |
| D | Label and target construction | 45 | Med | Target smoke and labels are not tradability proof | Reverify target/entry/exit timing under exact new hypothesis |
| E | Feature engineering | 50 | Med | Prior cleanup helps, but no new fold-level leakage rerun was done here | Add timing-shift and train-only transform checks before modeling |
| F | Baseline discipline | 10 | High | No-trade and random-entry/null fail; carry baseline missing | Require all baseline/null buckets before modeling |
| G | WFA and validation | 55 | High | WFA structure exists but cannot rescue failed economics | Keep splits locked; do not tune from failed OOS |
| H | Overfit and false discovery | 5 | High | Trial-log-dependent tests missing or failing | Require append-only trial ledger and PBO/DSR/multiple-testing evidence |
| I | Costs, execution, and capacity | 5 | High | Net economics fail; cost stress fails; capacity/liquidity/fills missing | Require executable cost/fill/capacity evidence before any trading claim |
| J | Risk and portfolio construction | 10 | Med | Drawdown exists, but approved capital/margin/exposure/kill evidence is absent | Build portfolio/risk gate on locked OOS rows before promotion |
| K | Robustness and adversarial tests | 10 | Med | Label shuffle, timing shift, delay, spread, partial-fill tests missing | Run adversarial null/timing/cost/regime tests under a new approved scope |
| L | Governance and monitoring | 25 | Med | Repo gates are good; live monitoring evidence is absent | Add owner, monitoring, drift, incident, and stop-condition evidence |
| M | Production order system | 10 | High | `live_ops` is scaffold only; no real broker state machine | Prove broker/order/fill idempotency, restart, and reconciliation |
| N | Exchange/compliance | 5 | Low | No self-match/message-rate/exchange-rule evidence | Add compliance design and order audit trail |
| O | Accounting and PnL | 10 | Med | PnL comes from reports, not fills/statements/settlement | Reconcile signals to fills, fees, settlement, and broker-style statements |
| P | Stress and disaster | 5 | Low | No halt/outage/margin-jump/liquidation evidence | Add chaos, halt, outage, liquidation, and incident runbook tests |
| Q | Security/change control | 35 | Med | Defaults are safe, but no dedicated secrets/dependency/deploy audit | Run separate secrets/dependency/change-control audit |
| R | Crowding/market response | 5 | Low | No footprint, impact, or adversarial liquidity-provider analysis | Add scale, footprint, and depth/impact stress evidence |
| S | Research-process integrity | 25 | High | Good pause discipline, but current line lacks complete trial evidence | Close the line; require predeclared trial log for any new line |

## Highest-Risk Findings And Patches

### 1. Severe: Current line loses money before and after costs

Evidence: Phase 8 reports gross `-19871.875`, costs `36123.34`, net `-55995.215`, profit factor `0.6699`, and cost drag `1.8178`. This is not a hidden execution issue; the gross signal is already negative.

Capital loss / exploit: Any paper/live deployment would intentionally route a negative-expectancy policy. Cost, slippage, and stress only increase the loss.

Corrective rule:

```python
def require_promotable_phase8(decision: dict) -> None:
    if decision.get("promoted") is not True:
        raise RuntimeError("BLOCK: Phase 8 did not promote this model line")
    if decision.get("research_alpha_ready") is not True:
        raise RuntimeError("BLOCK: research alpha readiness is false")
    if decision.get("model_promotion_allowed") is not True:
        raise RuntimeError("BLOCK: model promotion is not allowed")
    costed = decision.get("costed_oos", {})
    if float(costed.get("gross_return_dollars", 0.0)) <= 0.0:
        raise RuntimeError("BLOCK: gross edge is nonpositive")
    if float(costed.get("net_return_dollars", 0.0)) <= 0.0:
        raise RuntimeError("BLOCK: net edge is nonpositive")
```

### 2. Severe: Baseline/null failure means the model does not beat doing nothing

Evidence: failure analysis reports baseline comparison `FAIL`, candidate does not beat no-trade, random-entry median fails in the July 9 matrix, and `simple_carry` evidence is missing.

Capital loss / exploit: A complex model can create turnover and cost drag while a flat book preserves capital. Repeated rescue attempts can convert random noise into a chosen narrative.

Corrective risk rule:

```yaml
baseline_gate:
  required_before_modeling: true
  required_status:
    no_trade: PASS_AND_CANDIDATE_BEATS
    random_entry_null: PASS_AND_CANDIDATE_BEATS_MEDIAN
    simple_trend: PRESENT_COMPARABLE
    simple_mean_reversion: PRESENT_COMPARABLE
    simple_carry_term_structure: PRESENT_OR_NOT_APPLICABLE_WITH_REASON
  if_any_missing_or_failed: STOP_MODEL_LINE
```

### 3. Severe: Overfitting controls are missing or failing

Evidence: statistical-validity summary reports `FAIL`; PBO, Deflated Sharpe, and multiple-testing adjustment require missing trial/search-path evidence, while Probabilistic Sharpe and regime breakdowns fail.

Capital loss / exploit: Without a full trial ledger, a user or agent can repeatedly test variants, retain only favorable runs, and unknowingly trade a false discovery.

Corrective rule:

```python
def require_trial_log_for_model_trust(matrix: dict) -> None:
    required = {
        "statistical_pbo",
        "statistical_deflated_sharpe",
        "statistical_multiple_testing",
    }
    buckets = {row["bucket_id"]: row["status"] for row in matrix.get("buckets", [])}
    missing = sorted(bucket for bucket in required if buckets.get(bucket) != "PASS")
    if missing:
        raise RuntimeError(f"BLOCK: missing anti-overfit evidence: {missing}")
```

### 4. Severe: Execution/capacity evidence is absent where the strategy would be most fragile

Evidence: July 9 matrix marks delay stress, capacity, liquidity window, spread/slippage, and partial-fill/reject evidence as `MISSING_EVIDENCE`; failure analysis reports capacity/liquidity `MISSING_EVIDENCE`. Local costs use fixed slippage assumptions and explicitly say no live fill model is available.

Edge cases that can cause loss:

- Opening gaps and fast first-hour bars: signal price exists in OHLCV but live fills could occur several ticks away or not at all.
- Volatility spikes: fixed one-tick-per-side slippage is too weak when spreads and queue position degrade.
- Liquidity crunches: top-of-book depth disappears and marketable orders sweep levels.
- Contract roll/expiry windows: wrong contract mapping or thin liquidity can turn a valid research symbol into an unfillable order.
- Halt/limit events: exits may be impossible while the report assumes deterministic policy rows.

Corrective execution rule:

```yaml
execution_gate:
  require_before_paper_or_live:
    - bid_ask_or_depth_source
    - delay_stress_pass
    - spread_slippage_stress_pass
    - partial_fill_reject_model_pass
    - capacity_limit_by_contract_and_session
    - contract_roll_execution_mapping
  max_order_size: min(research_limit, capacity_limit_contracts)
  if_liquidity_window_unknown: BLOCK_NEW_ORDERS
  if_current_spread_ticks_gt_limit: BLOCK_NEW_ORDERS
```

### 5. Severe: Live risk-management code is scaffold, not acceptance evidence

Evidence: `live_ops/schemas.py` defaults to disabled trading, no paper trading, no live broker, max one contract, and `live_fill_model_available` is false in costs. `live_ops/broker.py` implements a deterministic `PaperBroker`; `LiveBroker.place_order` raises `NotImplementedError`. `live_ops/risk.py` blocks live broker mode.

Capital loss / exploit: The scaffold can block unsafe use, but it does not prove real broker order IDs, cancel/replace handling, partial fills, rejects, margin changes, market data replay, restart recovery, or statement-level PnL.

Corrective promotion rule:

```yaml
paper_live_gate:
  live_ops_scaffold_counts_as: BLOCKING_CONTROL_ONLY
  not_allowed_as:
    - fill_quality_evidence
    - broker_reconciliation_evidence
    - margin_evidence
    - production_order_state_machine
  required_passes:
    - broker_sandbox_order_lifecycle
    - restart_idempotency
    - partial_fill_cancel_reject_reconciliation
    - account_margin_and_cash_reconciliation
    - kill_switch_manual_override_drill
```

### 6. Medium: Risk metrics exist, but approved capital risk does not

Evidence: Phase 8 reports max drawdown and tail loss, but project gates require capital base, margin, exposure, capacity, stale-data handling, kill switches, and risk-limit evidence before portfolio/risk claims.

Capital loss / exploit: A one-contract research drawdown can scale into an account-level liquidation if margin, correlation, gap loss, or contract multiplier assumptions are wrong.

Corrective risk rule:

```yaml
portfolio_risk_gate:
  require:
    capital_base_dollars: explicit
    contract_margin_by_symbol: official_or_broker_source
    max_position_contracts: explicit
    daily_loss_limit: explicit
    max_drawdown_stop: explicit
    stale_data_action: block_or_flatten
    kill_switch_drill: tested
  if_any_missing: BLOCK_PROMOTION_AND_PAPER_LIVE
```

## Edge-Case Stress Matrix

| Scenario | Current evidence result | Loss mode | Required mitigation |
|---|---|---|---|
| Market opens with gap through intended entry | Not proven | Fill far from modeled next-open/close price | Delay and slippage stress with worst acceptable fill rule |
| Spread widens 5x | Missing evidence | Fixed slippage underestimates cost | Spread/depth gate and cost-stress pass |
| Partial fill then reversal | Missing evidence | Model assumes full deterministic position while broker holds partial | Partial-fill state machine and reconcile-before-next-order |
| Reject/cancel failure | Missing evidence | Strategy thinks flat or filled when broker state differs | Broker open-order reconciliation and cancel-reject handling |
| Feed stale or duplicate bars | Scaffold blocks some cases | Live evidence absent; replay/backfill not proven | Tested market-data replay and reconnect backfill gate |
| Contract rolls or active contract changes | Config/report evidence only | Orders route to wrong/thin contract | Contract-specific execution mapping and roll calendar gate |
| Limit halt or exchange outage | Missing evidence | Exit assumed in report, impossible live | Halt/outage runbook and fail-safe liquidation policy |
| Margin requirement jumps | Missing evidence | Forced liquidation or inability to hold | Broker margin stress and max notional rule |
| Same-bar high/low ambiguity | Partly recognized in ORAC policy tooling | Backtest may choose favorable path ordering | Stop-first or ambiguous-block policy for path labels |
| Repeated candidate discovery after failure | Current closeout blocks line | False-discovery narrative from retries | Append-only trial log and predeclared single-run approvals |

## Overfitting / Data-Snooping Flags

- Severe: no complete current-scope trial log supports PBO, Deflated Sharpe, or multiple-testing acceptance.
- Severe: current candidate families include multiple rejected/stopped discovery branches; those reports are diagnostic context, not a menu for post-hoc rescue.
- Severe: ORAC v1 remains frozen target-smoke evidence, not executable-policy proof.
- Medium: registry/trial status should be treated as current local evidence, but any generated report not named by registry, handoff, or direct inspection should be treated as stale until verified.
- Medium: isolated fold/market wins are explicitly not acceptance evidence when total net, no-trade baseline, and statistical-validity gates fail.

## Execution Loop Audit

Costs are present in the research report, but the execution loop is not proven:

- Research costs include configured commissions, fee recovery, fixed slippage, tick size, tick value, and contract multiplier assumptions.
- The current model loses net after those costs; stressed costs make the result worse.
- There is no accepted live fill model, no paper/live fill comparison, and no capacity/depth evidence.
- `PaperBroker` fills at bar close plus optional fixed slippage; this is useful for scaffold smoke tests but not a futures execution model.
- `LiveBroker` is intentionally disabled, so no real broker order lifecycle has been validated.

Required before any execution claim:

```yaml
execution_acceptance:
  minimum_evidence:
    - hand_verified_signal_to_order_to_fill_to_pnl_sample
    - broker_or_exchange_timestamped_fill_log
    - commission_fee_slippage_reconciliation
    - partial_fill_reject_cancel_replace_tests
    - restart_reconciliation_test
    - capacity_limit_by_contract_session
  if_missing: EXECUTION_CLAIM_BLOCKED
```

## Final Finding

The safest interpretation is simple: the current project has useful research-process guardrails, but no accepted tradable alpha. The current Tier 1 line is closed. Recent target-discovery branches are rejected or frozen research evidence. Live/paper code is fail-closed scaffolding, not trading-system proof.

Exact next recommended step: keep modeling paused and do not rescue the current Tier 1 line. Any future modeling must start only as a separate predeclared evidence program with explicit baseline/null/statistical/execution scope and a separate bounded approval plan.
