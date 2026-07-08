# Adversarial Futures Quant Trading System Audit

Date: 2026-07-07

Audit target: current `futures_intraday_model` Tier 1 core research line and the surrounding research-to-trading system evidence.

Audit mode: local primary-evidence review using `AUDIT.md`, plus one bounded report-only model-trust audit. No provider download, raw/causal/label/feature rebuild, WFA rerun, prediction generation, tuning, cleanup, staging, commit, push, paper trading, or live trading was run.

Generated audit input:

- `reports/model_trust_audit/codex_model_trust_audit_20260707T000000Z/model_trust_audit.json`
- `reports/model_trust_audit/codex_model_trust_audit_20260707T000000Z/model_trust_audit.md`

## 1. Verdict

Verdict: **Fail**.

The current Tier 1 core chain is usable as diagnostic research evidence only. It does not support alpha acceptance, artifact freeze, final-holdout acceptance, paper trading, or live trading.

Proceed status: **no** for the audited system or current model line. Bounded research can continue only as a new or explicitly predeclared diagnostic effort, not as promotion or rescue-tuning of this result.

## 2. Overall Score

Overall score: **34/100**.

Research validity score: **42/100** for gates A-K and S.

Trading-system readiness score: **34/100** for gates A-S.

Caps applied:

- Hard fail: current model does not beat the no-trade baseline after costs.
- Hard fail: no complete current-scope trial log for anti-overfit controls.
- Cap: this audit did not re-run the raw-to-report path.
- Cap: realistic execution, capacity, margin, and broker/fill evidence are missing for any trading conclusion.
- Cap: live/paper safety gates are not acceptance evidence for this model line.

## 3. Gate Score Table

| Gate | Area | Score 0-100 | Confidence | Evidence inspected | Main weakness | Required fix |
|---|---|---:|---|---|---|---|
| A | Intended use and thesis | 45 | Med | `PROJECT_OUTLINE.md`, `configs/alpha_tiered.yaml`, Phase 5/6/8 reports | Scope is known, but no current predeclared economic thesis/trial packet for this line | Write one hypothesis with acceptance and kill criteria before any new run |
| B | Futures contract and universe integrity | 45 | Med | `configs/costs.yaml`, `configs/market_sessions.yaml`, data-audit reports | Tick/point/session config exists, but expiry, first notice, margin, roll liquidity, and executable contract mapping are not fully proven | Add contract-spec and roll/execution evidence by market |
| C | Data provenance and point-in-time integrity | 62 | Med | Phase 1A/1B/2 current-state reports, causal readiness report | Broad active causal readiness is still `WARN`; local-trade/OHLCV gap gate remains incomplete | Finish active-scope causal policy and proof gates before broad claims |
| D | Label and target construction | 55 | Med | Label/feature placement reports, Phase 8 policy rows | Label chain exists for Tier 1, but this audit did not independently rebuild target timing | Re-run or independently verify label timing and target exclusions for the exact scope |
| E | Feature engineering | 62 | Med | Phase 4 self-reference cleanup placement report | 114 active features are verified for Tier 1, but train-only transforms and leakage safety are not independently reimplemented here | Add fold-level feature rebuild/leakage checks for model-trust claims |
| F | Strategy baseline discipline | 35 | High | `failure_analysis_summary.json`, `alpha_promotion_decision.json` | Candidate fails no-trade; `simple_carry` baseline missing | Complete futures-native baseline suite under the same split/cost/policy |
| G | Splits, WFA, and cross-validation | 75 | High | Phase 5 split acceptance, Phase 6 WFA report and manifest | Chronological WFA evidence is strong, but does not rescue failed economics or missing trial log | Keep split plan locked and do not tune from the failed OOS result |
| H | Overfitting and false discovery | 20 | High | `statistical_validity_summary.json` | PBO, Deflated Sharpe, multiple-testing, and regime evidence fail or are missing | Build full trial ledger and anti-overfit evidence before model-trust claims |
| I | Costs, execution, and capacity | 25 | High | Phase 8 metrics, failure analysis, `configs/costs.yaml` | Costs are modeled, but net economics fail and capacity/liquidity/real fills are missing | Add executable spread, slippage, liquidity, capacity, latency, and fill evidence |
| J | Risk and portfolio construction | 20 | Med | Phase 8 metrics, Project Outline risk gates | Drawdown/tail metrics exist, but capital base, margin, exposure, and risk controls are not approved | Add portfolio/risk report tied to locked OOS rows and contract sizing |
| K | Robustness and adversarial tests | 25 | Med | Phase 8 cost stress, failure analysis, statistical-validity report | Cost stress fails; label-randomization, timing-shift, and perturbation tests are incomplete | Run adversarial timing, null, cost, regime, and feature-removal tests |
| L | Governance and monitoring | 25 | Med | `PROJECT_OUTLINE.md`, `AGENTS.md`, handoff policy | Research governance exists, but no live monitoring or promotion governance evidence | Add model inventory, monitoring, owner, review, and stop-condition records |
| M | Production order-system and state-machine | 15 | Med | `live_ops/*` source scan | Paper-only scaffold exists, but no integrated broker state, restart, or real order lifecycle proof | Prove idempotent broker/order/fill state with restart/reconcile tests before paper/live |
| N | Market abuse, exchange-rule, and compliance | 10 | Low | `AUDIT.md`, `live_ops` source scan | No self-match, spoofing/layering, message-rate, or exchange-rule compliance evidence | Add compliance design and audit trail from signal to order to fill |
| O | Accounting, cash, settlement, and PnL | 20 | Med | Phase 8 metrics and cost reports | PnL is from saved predictions and cost assumptions, not fills and settlement/account statements | Reconcile PnL to fills, fees, settlement, margin variation, and broker-style statements |
| P | Stress, chaos, and disaster tests | 15 | Low | Phase 8 cost stress, `live_ops` source scan | No halt, outage, bad tick, margin jump, crash/restart, or liquidation stress evidence | Add chaos/stress tests and incident runbook |
| Q | Security and change-control | 40 | Med | `live_ops/schemas.py`, source scan excluding generated data/reports | Defaults block live broker, but no full secrets scan, dependency review, or deploy control proof | Run dedicated secrets/dependency/change-control audit |
| R | Crowding and adversarial market response | 10 | Low | Phase 8/failure-analysis evidence | No crowding, footprint, impact, or adversarial liquidity-provider analysis | Add market-response and scale/footprint stress evidence |
| S | Research-process integrity | 35 | High | Project docs, manifests, statistical-validity report | Good bounded-report discipline, but no complete tested-variant/trial ledger for this result | Require append-only trial log before any new model-trust run |

## 4. Highest-Risk Findings

1. **Severe: current model line fails costed OOS.** `alpha_promotion_decision.json` reports `promoted=false`, `research_alpha_ready=false`, `model_promotion_allowed=false`, 30 promotion blockers, gross PnL `-19871.875`, costs `36123.34`, net PnL `-55995.215`, average net per trade `-41.5703`, net Sharpe-like `-4.5339`, and profit factor `0.6699`.
2. **Severe: baseline discipline fails.** `failure_analysis_summary.json` reports baseline gate `FAIL`: the candidate does not beat no-trade and `simple_carry` is missing.
3. **Severe: overfit controls fail.** `statistical_validity_summary.json` reports `FAIL`, with missing/failing PBO, Deflated Sharpe, Probabilistic Sharpe, multiple-testing adjustment, and regime breakdowns.
4. **Severe: no trading-system readiness.** Phase 8 explicitly says live execution is not ready and partial fills, order rejection, latency, capacity, and contract-specific execution mapping remain outside the report.
5. **Medium: broad data scope is not fully accepted.** Phase 2 current active readiness is `WARN`: active raw 530, active-scope raw 526, active causal 518, stale raw-input hashes 0, severe blockers 0, medium blockers 2.
6. **Medium: paper/live scaffold is not acceptance evidence.** `live_ops` defaults to broker-agnostic, disabled, paper-only behavior and blocks live broker mode, but it is not integrated evidence for the failed Tier 1 model line.

## 5. Evidence Table

| Claim | Inspected evidence | Result | Missing proof |
|---|---|---|---|
| Current model is promotable | `reports/phase8/.../alpha_promotion_decision.json` | False: promotion gate fails with 30 blockers | None needed; this is a hard fail |
| Costed economics are positive | Phase 8 costed OOS metrics | False: gross, net, and risk-adjusted metrics are negative | None needed; this is a hard fail |
| Candidate beats simple controls | `failure_analysis_summary.json` | False: no-trade beats candidate; `simple_carry` missing | Full futures-native baseline suite |
| WFA artifacts exist | Phase 6 WFA report and predictions manifest | Verified structurally: 48 folds, 9,172,416 predictions, 0 duplicates | Raw-to-report rerun and anti-overfit proof |
| Prediction audit passed | Phase 7 prediction audit summary | Verified: `PASS`, prediction audit ready | Trading policy validity and execution proof |
| Active Tier 1 features are placed | Phase 4 cleanup active placement report | Verified: 8 parquets, 4 sidecars, 114 active features, removed self-reference features absent | Independent fold-level leakage rebuild |
| Broad active causal scope is complete | Phase 2 readiness report | Not complete: `WARN` with medium blockers | Resolve active raw without causal policy and local-trade gap proof |
| Execution is tradable | Phase 8 caveats, `live_ops` source scan | Not established | Contract-specific order mapping, fills, latency, capacity, broker reconciliation |
| Paper/live safety is ready | `live_ops` source scan | Not established for this model line | Integrated paper/live tests, account state, risk limits, compliance, incident recovery |

## 6. Leakage Audit

Data lineage: Tier 1 research evidence has a structured causal chain, but broad active data readiness remains `WARN`. This audit did not rerun raw-to-report reproduction.

Labels: Label evidence exists for the Tier 1 scope, but this audit did not independently recompute prediction, entry, and exit timestamps. Label-timing safety remains report-backed, not independently proven here.

Features: Active Tier 1 feature placement passed after self-reference cleanup, with 114 active features and zero removed self-reference features present. This is positive evidence, but not a full independent train-only transform audit.

Splits and validation: Phase 5 split acceptance and Phase 6 WFA artifacts are strong structural evidence: 48 folds, 9,172,416 predictions, 0 duplicate predictions, and no final holdout touched. This does not offset failed economics or missing false-discovery controls.

Reports and execution: Phase 8 uses saved OOS predictions and a max-one-contract, non-overlapping target-window policy. It is not evidence of live fills or executable contract handling.

Leakage conclusion: no specific new leakage defect was proven in this audit, but leakage cannot be ruled out strongly enough for model-trust or trading claims without an exact-scope raw-to-report rerun and adversarial timing tests.

## 7. Overfitting / False-Discovery Audit

The current line fails anti-overfit review. `statistical_validity_summary.json` reports:

- PBO: `FAIL_MISSING_TRIAL_LOG`
- Deflated Sharpe: `FAIL_MISSING_TRIAL_LOG`
- Probabilistic Sharpe: `FAIL`
- Bootstrap confidence intervals: `PASS`
- Multiple-testing adjustment: `FAIL_MISSING_TRIAL_LOG`
- Parameter stability: `PASS`
- Regime breakdowns: `FAIL`

The missing trial ledger is severe because it prevents knowing how many variants, parameters, markets, windows, features, and cost assumptions were tried before this result.

## 8. Execution, Cost, Capacity, Margin, And Risk Audit

Costs are not omitted: `configs/costs.yaml` contains tick size, tick value, point value, commission, exchange-fee recovery, regulatory fee, and fixed slippage assumptions. Phase 8 applies costs and stress tests.

The result still fails:

- Net PnL: `-55995.215`
- Costs: `36123.34`
- Cost drag to absolute gross: `1.8178`
- 2x cost stress: fails
- Capacity/liquidity/market-impact: missing
- Partial fills, rejects, latency, and queue position: outside Phase 8
- Margin and contract-count conversion for promotion: not approved

Risk evidence is incomplete. The report has drawdown and tail metrics, but not approved capital, margin, position limits, exposure, liquidation, capacity, or kill-switch evidence for this model line.

## 9. Production, Compliance, Security, And Operations Audit

`live_ops` contains useful paper-only guard scaffolding. Source scan evidence shows broker-agnostic defaults, disabled live broker mode, kill-switch and duplicate-order controls, max-order controls, and reconciliation concepts.

That does not make the system production ready. Missing evidence includes:

- integrated broker/exchange state as source of truth;
- restart recovery without duplicate orders;
- live or paper fill reconciliation for this model line;
- account cash, margin, settlement, and broker statement matching;
- self-match prevention, message-rate, exchange-rule, and compliance review;
- production credential handling and deployment controls;
- incident runbook, alerting, and human override evidence tied to this strategy.

## 10. Required Adversarial Tests

Before any model-trust or promotion claim:

1. Re-run exact-scope raw-to-report reproduction with pinned code/config/data hashes.
2. Run one-bar feature/label shift tests to expose timing leaks.
3. Randomize labels; performance must collapse.
4. Complete no-trade, random-entry/null, simple trend, simple carry, intraday seasonality, and mean-reversion baselines under identical WFA/cost/policy rules.
5. Run feature-removal and suspicious-column removal tests.
6. Run regime, market, year, session, cost, delay, roll-date, and parameter perturbation tests.
7. Build full trial log and compute PBO or equivalent, Deflated Sharpe, Probabilistic Sharpe, multiple-testing adjustment, parameter stability, and regime breakdowns.
8. Add liquidity, capacity, spread/depth, market-impact, partial-fill, reject, latency, and executable-size evidence.
9. Reconcile a hand-verified sample from signals to orders to fills to PnL before any paper/live claim.
10. Run broker disconnect, crash/restart, duplicate order, stale data, kill-switch, and reconciliation tests tied to the actual strategy.

## 11. Hard Fail Conditions

Hard fails present:

- Current model cannot beat no-trade after realistic costs.
- No complete trial log after enough variants/reports exist to require one.
- Statistical validity fails.
- Execution assumptions are insufficient for any trading conclusion.
- Capacity/liquidity evidence is missing.
- No broker/exchange reconciliation for this strategy.
- No audit trail from live signal to order to fill to settlement PnL.
- No production-ready paper/live safety gate.

Hard fails not proven in this audit:

- No new direct future-information feature leak was identified.
- No secrets or broker credentials were identified by targeted source scan, but a full secrets scan was not run.

## 12. What Could Still Be Wrong

- Existing reports may be stale relative to ignored local artifacts if files were manually changed outside recorded gates.
- Cost assumptions may be stale relative to current broker/exchange fee schedules; no live web verification was run in this audit.
- Contract metadata and roll handling were inspected through local configs/reports, not independently reconciled to every official contract spec.
- The active prediction parquet was not re-read row by row in this audit.
- `live_ops` source controls may pass unit/smoke tests, but no production broker integration evidence was inspected.

## 13. Proceed Status

Proceed status: **no** for promotion, artifact freeze, final-holdout acceptance, paper trading, live trading, or treating the current Tier 1 line as alpha.

Exact next recommended step: write one predeclared replacement hypothesis/trial packet before any new model run, including target, features, market/year scope, baselines, costs, acceptance criteria, kill criteria, trial-log policy, and forbidden rescue-tuning of the failed Tier 1 result.
