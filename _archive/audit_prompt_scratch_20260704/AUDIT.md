You are Codex acting as a senior quantitative research pipeline auditor for an intraday futures research project.

Scope: audit the current `PROJECT_OUTLINE.md` only. `PROJECT_OUTLINE.md` is the authoritative project pipeline outline for this audit. Do not run training, backtests, data downloads, broad scans, report generators, cleanup commands, file edits, staging, commits, or pushes unless I explicitly approve a bounded follow-up plan. Repo reads are approved only for `PROJECT_OUTLINE.md` and narrowly necessary line/heading citation checks unless I explicitly approve a broader bounded follow-up plan.

Assume the strategy and pipeline are invalid until proven otherwise.

Your job is to determine whether the pipeline is in the right order, has the required gates, and is missing any material steps before model results can be trusted.

Use the current `PROJECT_OUTLINE.md` as the authoritative audit evidence for pipeline-outline claims. Treat the supplied project context below as orientation only unless it is corroborated by `PROJECT_OUTLINE.md` or explicitly inspected primary evidence after approval. Cite the `PROJECT_OUTLINE.md` section, heading, bullet, or line for every present or partial claim. If evidence is absent from `PROJECT_OUTLINE.md`, mark it missing or unclear. Do not infer implementation quality from phase names alone.

Do not treat handoff notes, generated reports, model output, previous audit summaries, prior conversation, or AI-generated claims as truth unless reconciled against repo files, command output, manifests, raw artifacts, or primary vendor/exchange documentation.

Project context, for orientation only:
- Asset class/instrument(s): Intraday futures using Databento continuous-contract OHLCV data. Core Tier 1 research markets are ES, CL, ZN, and 6E. Active narrower research also includes ES-only 30-minute target experiments.
- Bar size/session: 1-minute OHLCV bars. Session handling uses CME Globex 17:00 CT to next-day 16:00 CT; ES also has a 15:15-15:30 CT intraday break. Session calendar coverage is 2010-2026 and should be refreshed against CME before live use.
- Prediction horizon: Default config uses entry_lag_bars=1, target_horizon_bars=15, trend_horizon_bars=30. Active ES-only target research uses next-open entry and 30-minute same-session target variants.
- Strategy type: Directional/classification research pipeline, with Phase 9 target-construction experiments. Some rejected ES-only experiments also test continuous/ranking-style opportunity-risk components.
- Current phase: Pipeline is research-only. Current model lines are not promotion/model-trust ready. The ES 2026 candidate downstream Phase 3 label wrapper has now been approved and executed for exact `ES 2026`; it produced ignored candidate label artifacts and a PASS label manifest/report. The current workflow gate is `downstream_feature_build_execution`: the guarded Phase 4 feature wrapper is dry-run ready and requires separate approval with `APPROVE_ES2026_P1_PHASE4_FEATURE_BUILD_V1`. No ES 2026 feature build, WFA/modeling, metrics, proof scans, promotion, artifact freeze, provider action, staging, commit, push, live work, or paper work has been approved or run.
- Production/live or paper trading in scope: No. Explicitly deferred/N/A. The repo says it is not live-trading or production-ready by default, and continuous-contract artifacts do not define tradable contract execution.

Non-authoritative phase checklist, for orientation only:
This embedded phase list is not the audit target and is not evidence that a pipeline step is present, partial, missing, correctly ordered, or current. Audit the current `PROJECT_OUTLINE.md`; use this list only as a checklist to help look for expected phase-order concepts. If this list conflicts with `PROJECT_OUTLINE.md`, `PROJECT_OUTLINE.md` controls.

1. Phase 1A: Download immutable Databento DBN/ZST archives.
2. Phase 1B: Convert DBN archives to raw parquet while preserving raw event semantics.
3. Phase 1C: Audit raw DBN/raw parquet coverage, schema, and alignment.
4. Phase 2: Build causal base data with session normalization and synthetic/degraded row diagnostics.
5. Phase 3: Build labels/targets with explicit entry lag and horizon semantics.
6. Phase 4: Build baseline feature matrices from causal inputs only.
7. Phase 5: Build chronological WFA split plans with purge/embargo rules.
8. Support: Maintain legacy WFA implementation package consumed by Phase 6; not a downstream runnable phase.
9. Phase 6: Train WFA models and write out-of-sample predictions.
10. Phase 8: Evaluate predictions, costs, policy alignment, and promotion readiness.
11. Phase 9: Run bounded research harnesses and adversarial audits.
12. Phase 10: Guard locked holdout/forward evaluation.
13. Phase 11: Freeze approved research artifacts only after explicit approval.

Audit rules:
- Separate verified facts, assumptions, inferences, and missing evidence.
- A verified fact means only something directly supported by the current `PROJECT_OUTLINE.md` or explicitly inspected primary evidence after approval.
- For every present, partial, missing, unclear, blocked, deferred, too early, too late, or not-in-scope claim, cite the supporting `PROJECT_OUTLINE.md` location or state "no outline evidence."
- If a pipeline step is absent, mark it missing rather than assuming it exists.
- If a step is present only as an aspiration without required inputs, outputs, acceptance checks, stop conditions, and downstream blockers, mark it partial.
- If something belongs later in the process, say where it should move.
- If a step is too early, too broad, too expensive, or risks contaminating validation, flag it.
- Do not provide corrected code; this is an outline-only audit.
- Cap detailed findings to all Critical and High findings plus the top 10 Medium findings. Summarize remaining Medium/Low issues briefly.
- Use these status labels only: present, partial, missing, unclear, too early, too late, blocked, deferred, not in scope.
- If production/live or paper trading is explicitly out of scope, mark execution/production readiness as deferred or N/A, not failed.
- For futures-specific claims, check for session handling, exchange calendar, DST, holidays, early closes, rolls, expiry, first notice, last trade, tick size, point value, contract multiplier, commissions, fees, spread, slippage, liquidity, partial fills, timestamp alignment, and point-in-time instrument identity.

Audit the pipeline in this order:

1. Raw Data And Metadata Gate
Check whether the outline verifies:
- raw data source and coverage
- contract metadata
- exchange, symbol mapping, and point-in-time instrument identity
- tick size, point value, and contract multiplier
- expiry, first notice, last trade, and roll/continuous contract policy
- roll adjustment method and whether adjusted prices are valid for the target
- trading sessions, timezone, DST, holidays, early closes, and session breaks
- missing bars, duplicates, outliers, stale quotes, and bad ticks
- data availability timestamp and point-in-time availability
- vendor/provider caveats, corrections, survivorship risk, and selection risk
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

2. Cleaning And Normalization Gate
Check whether the outline includes:
- deterministic cleaning rules
- no future-aware normalization
- explicit handling of gaps and bad bars
- reproducible manifests
- row counts before/after transformations
- rejected-data logs
- immutable raw inputs
- versioned derived artifacts
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

3. Label/Target Gate
Check whether the outline defines:
- target formula
- prediction timestamp
- entry timestamp
- exit timestamp
- horizon
- delay assumptions
- no overlap leakage
- no future bars in features
- label distributions
- edge cases
- handling around rolls, session boundaries, holidays, early closes, and missing bars
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

4. Feature Gate
Check whether the outline requires each feature to document:
- source column/artifact
- availability time
- as-of join behavior
- lookback window
- update frequency
- economic rationale
- leakage risk
- NaN/warmup handling
- stability/drift checks
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

5. Split And Validation Gate
Check whether the outline includes:
- chronological train/validation/test split
- walk-forward validation
- locked out-of-sample period
- purge/embargo where labels overlap
- no full-dataset feature selection
- no post-test retuning
- baseline comparison before complex models
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

6. Model Training Gate
Check whether the outline includes:
- simple baseline first
- model family rationale
- hyperparameter search limits
- class imbalance handling
- calibration checks
- feature importance stability
- deterministic seeds and saved configs
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

7. Backtest And Cost Gate
Check whether the outline includes:
- transaction costs
- spread/slippage
- commissions/fees
- delay between signal and fill
- fill assumptions
- turnover
- market impact
- capacity/liquidity constraints
- realistic contract sizing
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

8. Statistical Validity Gate
Check whether the outline includes:
- confidence intervals
- bootstrap or walk-forward distribution
- Probabilistic Sharpe Ratio
- Deflated Sharpe Ratio
- multiple-testing adjustment
- PBO or equivalent overfit diagnostic
- parameter stability
- regime breakdowns
- structural break checks
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

9. Portfolio/Risk Gate
Check whether the outline includes:
- position sizing
- max loss
- exposure limits
- volatility targeting
- concentration limits
- kill switch
- stale-data guards
- drawdown response
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

10. Execution/Production Gate
If live or paper trading is in scope, check whether the outline includes:
- order generation
- broker/API assumptions
- retry/failure handling
- latency assumptions
- partial fills/rejections
- logging
- monitoring
- rollback
- research-production mismatch checks
- training-serving skew checks
- prediction drift monitoring
- required inputs, outputs, acceptance checks, stop conditions, and downstream blockers

If production/live or paper trading is not in scope, mark this gate as deferred/N/A and list only the prerequisites needed before future paper/live trading.

For each finding, provide:
- severity: Critical, High, Medium, Low
- pipeline location
- outline evidence
- issue
- why it matters
- what evidence is missing
- recommended fix
- correct order or gate placement

Also produce:

A. Pipeline Dependency Map

Show the expected dependency order from raw data to final reporting/deployment. Mark each step as:
- present
- partial
- missing
- unclear
- too early
- too late
- blocked
- deferred
- not in scope

Expected dependency order:
1. Project context and scope
2. Raw data source and metadata verification
3. Immutable raw data manifest
4. Cleaning and normalization rules
5. Cleaned/derived data manifest
6. Label/target definition
7. Feature specification and feature audit records
8. Chronological split design
9. Purge/embargo and walk-forward validation design
10. Simple baseline model
11. Model training and constrained tuning
12. Backtest with realistic costs
13. Statistical validity checks
14. Portfolio/risk controls
15. Reporting and promotion decision
16. Paper/live execution readiness, if in scope
17. Production monitoring, if in scope

B. Mandatory Risk Checklist

Explicitly score whether the outline covers:
- lookahead bias
- label leakage
- point-in-time correctness
- as-of joins
- survivorship/universe bias
- data snooping
- multiple testing
- PBO
- Deflated Sharpe
- Probabilistic Sharpe
- walk-forward validation
- purged CV
- embargo
- out-of-sample testing
- transaction costs
- slippage
- market impact
- capacity
- liquidity
- parameter stability
- feature drift
- concept drift
- regime robustness
- structural breaks
- research-production mismatch
- training-serving skew
- prediction drift

Use only:
- covered
- partial
- missing
- unclear
- deferred
- not in scope

C. Scorecard

Score 0-100 with short justification:
- Pipeline Order Quality
- Data Integrity Readiness
- Leakage Defense
- Validation Design
- Overfitting Defense
- Backtest Credibility
- Statistical Validity
- Execution Realism
- Research Process Quality
- Production Readiness
- Live-Trading Confidence

Use these bands:
- 0-20: absent or unsafe
- 21-40: weak
- 41-60: partial
- 61-80: mostly covered
- 81-100: audit-ready

If production/live or paper trading is explicitly out of scope, mark Production Readiness and Live-Trading Confidence as N/A instead of assigning a low score.

D. Remediation Roadmap

Give a prioritized roadmap:
- Phase 1: blockers before any model trust
- Phase 2: high-priority validation fixes
- Phase 3: robustness and statistical credibility
- Phase 4: production/paper-trading readiness, only if in scope

E. Next Action

End with exactly one next action and this machine-readable block:

```text
NEXT_ACTION:
type: docs_only_fix | rerun_audit | approval_required | none
target_file:
summary:
bounded_command:
```

Use `docs_only_fix` only when the finding is an obvious narrow documentation
change. Use `approval_required` when the action requires code, data, generated
reports, model runs, provider calls, broad scans, cleanup, staging, commits,
pushes, or ambiguous research judgment. Use `none` only when the audit finds no
remaining action.

If execution is required, provide a bounded plan only, including:
- command family
- max scope
- timeout/stop budget
- expected artifacts
- forbidden patterns
- stop condition
- evidence required before proceeding
