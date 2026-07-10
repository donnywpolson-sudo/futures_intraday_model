# Master Audit

Source: Google Doc `master audit`

Source URL: https://docs.google.com/document/d/1M5levKjQXYXxbsj4os4iAxei4ziW0R4Ly28u3kpGsjY/edit?usp=drivesdk

Copied into this repository on 2026-07-09 from Google Docs revision
`ALtnJHxoRladhBxJHAOgPiCDRotrONI98yI4LHvVKyeBMuG_hGAwL6kkw2-hCDWaC-wUqGG63OP_zNwnLKATig9EUq3u7geB2SR41CNIvsM`.

This file is a local convenience copy of the audit prompt library. It is not a
repo source of truth. When applying it inside this repository, reconcile it
against `AGENTS.md`, `PROJECT_OUTLINE.md`, `CODEX_HANDOFF.md`, current files,
command output, and generated report evidence. Do not treat this file as
authorization to run broad, mutating, provider, data/model, promotion, freeze,
paper, or live-trading actions.

## How To Use This File

- Default mode is plan-only.
- Use this file as checklist material for audit scope and review prompts, not as
  proof that any claim is true.
- Do not run commands unless the current prompt or handoff approves a bounded
  plan with exact scope, command family, timeout, artifacts, forbidden actions,
  stop condition, and pass/fail criteria.
- Treat the Google Doc source and this Markdown copy as audit prompts only. Repo
  files, command output, accepted reports, manifests, hashes, and primary source
  documentation are the evidence surfaces.
- If this file conflicts with `AGENTS.md`, `PROJECT_OUTLINE.md`,
  `CODEX_HANDOFF.md`, current repo evidence, or command output, follow the
  higher-authority repo evidence and record the conflict.
- Do not use certification, live, paper, promotion, freeze, or production
  language unless that scope is explicitly approved and supported by primary
  evidence.
- For this repository, paper, live, broker, production, artifact-freeze, and
  promotion-readiness checks default to `N/A - not approved / not in scope`
  unless `AGENTS.md`, `PROJECT_OUTLINE.md`, the current prompt, and primary
  evidence all explicitly approve that scope.

## Audit Run Status

This file is a prompt library and checklist. It is not evidence that an audit
was executed.

Before using any tab below, record a run-status table:

| Audit area | Status | Accepted evidence | Scope | Notes |
| --- | --- | --- | --- | --- |
| Overview | `NOT_RUN` / `RUN` / `N/A` | paths and hashes | markets, years, profile, run id | conflicts or caveats |
| Phase 1A-11 | `NOT_RUN` / `RUN` / `N/A` | paths and hashes | exact bounded phase scope | stale/missing evidence |
| Research Factory | `NOT_RUN` / `RUN` / `N/A` | paths and hashes | capability review only | no execution permission |
| Research Readiness | `NOT_RUN` / `RUN` / `N/A` | paths and hashes | research-only unless approved | no paper/live by default |

Default for this imported Markdown copy: all audit tabs are `NOT_RUN`. A future
completed audit must change status using primary repo evidence, not summaries or
this prompt text.

## Repo-Specific Phase And Evidence Crosswalk

When this file is applied inside `futures_intraday_model`, use this repo-specific
phase map instead of generic phase assumptions:

| Audit prompt | Repo phase or gate | Current implementation authority | Evidence surface to inspect first | Default execution posture |
| --- | --- | --- | --- | --- |
| Phase 1A | DBN request planning, provider acquisition, DBN validation | `scripts.phase1A_download.download_databento_raw` | `PROJECT_OUTLINE.md`, `configs/alpha_tiered.yaml`, `manifests/phase1a_acquisition_registry.jsonl`, `data/dbn/**` manifests, Phase 1A reports | Plan-only unless bounded provider/download approval exists |
| Phase 1B | DBN-to-raw conversion plus immediate raw/DBN validation | `scripts.phase1B_convert.convert_databento_raw`; internal validator `scripts.phase1C_validate.audit_raw_dbn_alignment` | `data/raw/**`, `reports/raw_ingest/**`, raw/DBN alignment reports | Plan-only unless exact market/year conversion or report-only validation is approved |
| Phase 2 | Causal/session-normalized base data and readiness | `scripts.phase2_causal_base.build_causal_base_data`; `scripts.validation.audit_phase2_causal_session_normalization` | `data/causally_gated_normalized/**`, `reports/causal_base/**`, current-state readiness reports | Plan-only unless exact rebuild or report-only audit is approved |
| Phase 3 | Label and target construction | `scripts.phase3_labels.build_labels` | `data/labeled/**`, label manifests, target timing reports | Plan-only unless exact label scope is approved |
| Phase 4 | Baseline feature matrix and leakage controls | `scripts.phase4_features.build_baseline_features`; feature leakage guards | `data/feature_matrices/**`, feature manifests, final feature-matrix leakage reports | Plan-only unless exact feature scope or report-only audit is approved |
| Phase 5 | WFA split planning | `scripts.phase5_wfa.build_wfa_splits` | `reports/wfa/**/split_plan.json`, split acceptance reports, feature manifests | Plan-only unless exact split-build/report-only scope is approved |
| Phase 6 | WFA training and OOS prediction generation | `scripts.phase6_wfa.run_wfa`; `scripts.phase6_wfa.combine_wfa_predictions` | WFA reports, prediction manifests, `data/predictions/**` only when approved | Blocked unless bounded WFA/modeling approval exists |
| Phase 7 | Public prediction artifact audit | `scripts.phase7_prediction_audit.audit_predictions` | `reports/prediction_audit/**`, Phase 6 prediction manifests | Report-only by default; do not use `scripts.phase7_wfa` as a standalone phase |
| Internal WFA engine | Legacy engine consumed by Phase 6 | `scripts.phase7_wfa.*` | Phase 6 tests and manifests | Internal only; validate as Phase 6 work |
| Phase 8 | Prediction evaluation, cost/backtest, promotion gate | `scripts.phase8_model_selection.*` | `reports/phase8/**`, baseline/null/statistical/execution-realism evidence | Report-only unless exact evaluation is approved; promotion defaults blocked |
| Phase 9 | Bounded research harnesses and statistical-validity diagnostics | `scripts.phase9_research.*`; validation utilities | target registries, trial ledgers, `reports/pipeline_audit/**`, model-trust reports | Feasibility evidence only until Phase 8 consumes it |
| Phase 10 | Artifact freeze after approved research result | `scripts.artifact_freeze.freeze_research_artifacts` | freeze manifests and explicit approval evidence | `N/A` / blocked unless explicit freeze approval exists |
| Phase 11 | Final holdout/forward guard using frozen artifacts | `scripts.final_holdout.guard_final_holdout` | holdout guard reports and frozen-artifact lineage | `N/A` / blocked unless explicit holdout approval exists |
| Production / paper / live | Future non-authorizing gate | `PROJECT_OUTLINE.md` Production Deferral Gate | runbook, validation suite, evidence manifest, broker/fill/risk/monitoring proof | `N/A - not approved / not in scope` |

## Evidence Inventory Gate

Before writing audit findings:

1. Record the current repo path and current `git status --short`.
2. Record branch, commit, remote URL, untracked/modified/deleted files relevant
   to the audit, and whether the target evidence is tracked, ignored, generated,
   or external.
3. Identify the accepted source files, generated reports, manifests, hashes,
   timestamps, revisions, command outputs, export revisions, and export or file
   checksums used as evidence.
4. For generated reports, record JSON/Markdown path pairs when present, report
   root, run id, profile, market/year scope, row counts, hash fields, and whether
   the report was regenerated in the current run or inspected as existing
   evidence.
5. Label every evidence item as `current`, `stale`, `unknown`, `missing`, or
   `unreadable`.
6. Record the relevant scope for each evidence item, such as market, year,
   phase, profile, model run, report root, or artifact path.
7. Record the accepted source of truth for each claim: repo file, command output,
   raw data artifact, generated report, manifest, hash, or primary external
   documentation.
8. Treat missing, stale, unreadable, out-of-scope, summary-only, or handoff-only
   evidence as not verified.
9. For every material finding, use the Standard Finding Format below and
   separate verified facts from inferences and assumptions.

## Tabs

- [01 - Quant Research Platform Audit Standard v1.0](#01---quant-research-platform-audit-standard-v10)
- [02 - Overview Audit Prompt](#02---overview-audit-prompt)
- [03 - Phase Audit Prompts 1A-11](#03---phase-audit-prompts-1a-11)
- [04 - Self-Running Research Factory](#04---self-running-research-factory)
- [05 - Pipeline Research-Readiness Review Prompt](#05---pipeline-research-readiness-review-prompt)

## 01 - Quant Research Platform Audit Standard v1.0

### Purpose

This document defines all cross-cutting audit requirements applicable to every
phase of the research platform.

All audits inherit and apply this standard.

### Objectives

The audit framework must identify:

- Data leakage
- Look-ahead bias
- Timestamp misalignment
- Split contamination
- Transformation contamination
- Survivorship bias
- Selection bias
- Overfitting
- P-hacking
- Reproducibility failures
- Governance failures
- Automation gaps

### Severity Definitions

#### Critical

Can invalidate results.

Examples:

- Future information
- Leakage
- Holdout contamination
- Timestamp violations
- Split contamination

Severity action: block model-trust, WFA/model conclusions, promotion, freeze,
holdout, paper, and live claims until remediated and retested with primary
evidence.

#### High

Can materially distort results.

Examples:

- Missing-data errors
- Execution-assumption errors
- Contract-roll errors
- Cost-model errors

Severity action: block promotion, freeze, holdout, paper, and live claims; block
model-trust claims when the issue touches the active evidence scope. Remediate
before relying on affected metrics.

#### Medium

Can reduce confidence.

Severity action: allow only scoped diagnostic research if the affected claim is
clearly caveated. Require a remediation plan and targeted retest before any
broader research-readiness or model-trust claim.

#### Low

Documentation, process, reporting, or cosmetic issues.

Severity action: does not block narrow diagnostic research by itself, but must
be fixed before using the audit as durable coordination or external evidence.

### Lineage Audit

Verify complete lineage exists from:

1. Prediction
2. Model
3. Feature Set
4. Label Set
5. Dataset
6. Raw Source Files

### Dependency Graph Audit

Construct dependency graph covering:

1. Datasets
2. Labels
3. Features
4. Transforms
5. Predictions

Verify contamination cannot propagate through indirect dependencies.

### Configuration Drift Audit

Verify versioning and reproducibility of:

1. yaml
2. json
3. toml
4. environment variables
5. configuration files

### Live Reproducibility Audit

Determine whether identical outputs can be generated:

1. Historical
2. Simulation
3. Forward Test
4. Production

### Deployment Parity Audit

Compare:

1. Research
2. Evaluation
3. Forward Test
4. Production

### Research Budget Enforcement Audit

Track:

1. Hypotheses Tested
2. Models Tested
3. Feature Searches
4. Parameter Searches

### Candidate Uniqueness Audit

Identify:

1. Duplicate Candidates
2. Equivalent Candidates
3. Redundant Experiments
4. Repeated Feature Sets

### Failure Recovery Audit

Verify:

1. Failure Detection
2. Retry Logic
3. Resume Logic
4. Artifact Recovery

### Resource Governance Audit

Review:

1. CPU
2. GPU
3. RAM
4. Storage
5. Concurrency Limits

### Standard Audit Output

Every audit must output:

1. Finding
2. Severity
3. Verified fact
4. Inference
5. Assumption
6. Evidence path
7. What could be wrong/stale
8. Impact
9. Remediation
10. Retest required

### Bounded Execution Template

Complete this template before running any audit command:

- Audit objective:
- Command family:
- Scope limit:
- Timeout or stop budget:
- Expected artifacts:
- Forbidden actions:
- Stop condition:
- Pass/fail criteria:

If any field is missing, do not execute. Produce a plan instead.

### Acceptance Criteria Standard

Vague checks such as "verify integrity," "verify reproducibility," or "review
fidelity" must be converted into concrete acceptance criteria before execution.
At minimum, criteria should name the rows, columns, timestamps, manifests,
hashes, lineage files, boundaries, schemas, or report fields that would prove
the claim.

## 02 - Overview Audit Prompt

### Purpose

Evaluate the entire research platform architecture.

Apply Quant Research Platform Audit Standard v1.0.

Review:

- Architecture
- Workflows
- Repositories
- Data Flow
- Governance
- Orchestration

Assess:

- Phase 1A
- Phase 1B
- Phase 2
- Phase 3
- Phase 4
- Phase 5
- Phase 6
- Phase 7
- Phase 8
- Phase 9
- Phase 10
- Phase 11

Determine:

1. Missing phases
2. Missing controls
3. Missing governance
4. Missing automation
5. Missing reproducibility controls
6. Missing statistical-validity controls

Construct:

- Research Lifecycle Diagram
- Data Lifecycle Diagram
- Artifact Lineage Diagram

Identify:

- Largest Risks
- Blind Spots
- Automation Opportunities

Output:

A. Executive Summary

B. Architecture Review

C. Missing Controls

D. Risk Assessment

E. Automation Assessment

F. Governance Assessment

G. Recommended Improvements

H. Readiness Score

## 03 - Phase Audit Prompts 1A-11

### Phase 1A Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Market Selection
- Contract Selection
- Date Range Selection
- Databento Requests
- Continuous Futures Methodology
- Roll Methodology
- Roll Triggers
- Roll Date Determination
- Back-Adjustment Methodology
- Exchange Calendar Assumptions

Identify:

- Future Information Usage
- Survivorship Bias
- Universe Selection Bias

Acceptance criteria must cover request-plan scope, provider request evidence,
contract/roll selection rules, date ranges, exchange-calendar assumptions,
continuous-contract methodology, back-adjustment policy, source-file hashes,
manifest timestamps, and any missing/stale provider evidence.

Output findings using the Standard Finding Format.

### Phase 1B Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- DBN Ingestion
- Parquet Generation
- Hashing
- Row Reconciliation
- Duplicate Detection
- Gap Detection
- Schema Drift
- Minute Bar Reconstruction
- Session Reconstruction
- Canonical Market Reconstruction

Acceptance criteria must cover source DBN manifests, decoded/source row counts,
raw parquet row counts, duplicate keys, missing/output-only rows, schema drift,
timestamp timezone semantics, source-file hashes, definition/status/statistics
sidecar lineage, and raw-output hash evidence.

Output findings using the Standard Finding Format.

### Phase 2 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Feature Readiness
- Session Normalization
- Missing-Data Handling
- Indicator Warmup Rules
- Causal Dataset Construction

Verify:

```text
source_timestamp <= prediction_timestamp
```

for all features.

Acceptance criteria must cover causal input roots, session normalization rules,
missing-data markers, indicator warmup rows, `bar_available_ts`, invalid-row
handling, row counts, output manifests, and any source timestamp greater than
the prediction timestamp.

Output findings using the Standard Finding Format.

### Phase 3 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Label Timing
- Label Horizons
- Invalid Row Rules
- Cost Assumptions
- Execution Assumptions
- Label Realizability
- Label Stability

Verify:

```text
signal_timestamp < execution_timestamp < label_start < label_end
```

Acceptance criteria must cover entry-lag semantics, horizon timestamps,
same-session rules, invalid-row rules, cost assumptions, label row counts,
target columns, label manifest lineage, and any feature/label timestamp
boundary violation.

Output findings using the Standard Finding Format.

### Phase 4 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Feature Matrix
- Feature Lineage
- Feature Redundancy
- Feature Stability
- Target Leakage

Assess:

- Multicollinearity
- Regime Sensitivity
- Feature Drift

Acceptance criteria must cover feature-matrix row counts, feature names,
forbidden target/label columns, negative shifts, full-sample transforms,
normalization scope, join keys, feature lineage, feature manifest hashes, and
timestamp availability for every audited feature.

Output findings using the Standard Finding Format.

### Phase 5 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Walk-Forward Splits
- Purge Periods
- Embargo Periods
- Transformation Leakage
- Fold Independence

Acceptance criteria must cover train/validation/test window presence, chronological
ordering, target-horizon overlap, purge length, embargo length, later-fold reuse
of prior OOS windows, transform fit scope, parameter/calibration reuse, split
manifest paths, and fold count consistency.

Output findings using the Standard Finding Format.

### Phase 6 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Model Training
- Feature Selection
- Hyperparameter Tuning
- Calibration
- Model Complexity
- Seed Stability

Assess:

- Overfitting Risk
- Stability Risk
- Reproducibility

Acceptance criteria must cover model config identity, feature-selection scope,
hyperparameter search boundaries, calibration fit windows, random seeds,
train-only transform fitting, prediction-write controls, model artifact
manifests, and repeatability evidence.

Output findings using the Standard Finding Format.

### Phase 7 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Prediction Artifacts
- Prediction Timing
- Prediction Lineage
- Horizon Consistency
- Prediction Distribution Stability

Acceptance criteria must cover prediction row counts, horizon alignment,
duplicate keys, timestamp order, lineage manifest, prediction artifact hash,
train/test boundary, missing predictions, output schema, and distribution
stability by fold/market/year.

Output findings using the Standard Finding Format.

### Phase 8 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Performance Evaluation
- Capacity
- Execution Realism
- Tail Risk
- PnL Decomposition

Stress Test:

- Costs
- Spreads
- Slippage
- Volatility

Acceptance criteria must cover cost configuration, spread/slippage assumptions,
policy alignment, capacity assumptions, PnL decomposition, tail-risk metrics,
execution-realism primary evidence, baseline/null comparisons, and report-field
lineage back to prediction artifacts.

Output findings using the Standard Finding Format.

### Phase 9 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Research Process
- Multiple Testing
- Experiment History
- Candidate Uniqueness
- Research Budget Accounting

Require:

- Deflated Sharpe
- White Reality Check
- SPA Tests
- FDR Controls

Applicability status is mandatory for each named statistical test and any
substitute test:

- `PASS`: applicable, executed on the scoped evidence, and passed with evidence
  path, parameters, sample scope, and result fields recorded.
- `FAIL`: applicable and failed, or applicable but missing required evidence.
- `NOT_APPLICABLE_WITH_REASON`: not applicable to the actual metric, sample
  shape, hypothesis family, or evidence set; record the reason and substitute
  evidence required before model-trust, promotion, freeze, or holdout claims.
- `MISSING_EVIDENCE`: applicability cannot be determined from current primary
  evidence; treat as `FAIL` for model-trust, promotion, freeze, and holdout
  claims.

Acceptance criteria must cover the predeclared hypothesis family, tested
candidates, rejected candidates, feature/search budget, parameter-search budget,
negative trials, model-selection path, statistical-validity report inputs, and
whether named statistical tests are applicable to the actual evidence set.

Output findings using the Standard Finding Format.

### Phase 10 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Freeze Process
- Immutable Artifacts
- Environment Freezing
- Configuration Freezing

Acceptance criteria must cover explicit freeze approval, immutable artifact list,
artifact hashes, environment metadata, configuration hashes, dependency versions,
rebuild command evidence, and whether a separate reproduction run matched the
frozen outputs.

Output findings using the Standard Finding Format.

### Phase 11 Audit

Apply Quant Research Platform Audit Standard v1.0.

Before executing this phase audit, complete the Bounded Execution Template for
this phase.

Audit:

- Holdout Integrity
- Holdout Degradation
- Forward Testing
- Lineage Verification

Determine whether holdout remains valid.

Acceptance criteria must cover explicit holdout/forward approval, frozen-artifact
identity, holdout isolation from model selection, degradation checks, forward
test scope, lineage to frozen artifacts, and whether any post-holdout tuning or
scope change invalidated the result.

Output findings using the Standard Finding Format.

## 04 - Self-Running Research Factory

### Purpose

Determine whether a candidate can execute through the full lifecycle
autonomously.

For this repository, this section is a capability review only. It does not
authorize data generation, label/feature builds, WFA/modeling, prediction
generation, Phase 8 evaluation, promotion, artifact freeze, final holdout,
provider/download work, paper trading, live trading, staging, commit, or push.
If a bounded approval is missing, classify the stage and produce a plan instead
of executing it.

### Workflow Under Evaluation

```text
Audit
-> Generate Data
-> Generate Labels
-> Generate Features
-> Create WFA Splits
-> Train
-> Predict
-> Evaluate
-> Stress Test
-> Score
-> Promote / Reject
```

The workflow text above is a lifecycle shape, not an executable runbook. Before
any stage is executed, the current prompt or handoff must include a complete
Bounded Execution Template with exact scope, timeout, artifacts, forbidden
actions, stop condition, and pass/fail criteria. Otherwise the only permitted
output is a plan-only maturity assessment.

### Prompt

Apply Quant Research Platform Audit Standard v1.0.

Evaluate automation of every workflow stage.

For each stage classify:

- Automated
- Mostly Automated
- Partially Automated
- Manual
- Missing

Review:

- Orchestration
- Workflow Engines
- Registries
- Experiment Tracking
- Promotion Engines
- Scheduling
- Automation

Evaluate:

- Candidate Registry
- Feature Registry
- Label Registry
- Model Registry
- Artifact Registry
- Experiment Registry

Assess:

- Failure Recovery
- Configuration Management
- Scalability
- Resource Governance
- Deployment Parity
- Live Reproducibility

Classify maturity:

- Level 0 - Research Scripts
- Level 1 - Pipeline Research
- Level 2 - Automated Research Platform
- Level 3 - Research Factory
- Level 4 - Self-Running Research Factory
- Level 5 - Institutional Research Operating System

Output:

A. Executive Summary

B. Current Maturity Level

C. Missing Components

D. Manual Intervention Points

E. Automation Opportunities

F. Architecture Recommendations

G. Prioritized Build Order

H. Research Factory Score

I. Next 10 Engineering Tasks

## 05 - Pipeline Research-Readiness Review Prompt

### Purpose

Final research-readiness review of the platform.

Use certification, live, paper, promotion, freeze, or production language only
when that scope is explicitly approved and supported by primary evidence.

### Prompt

Apply Quant Research Platform Audit Standard v1.0.

Before executing this review, complete the Evidence Inventory Gate and Bounded
Execution Template.

Review:

- Overview Audit
- Phase 1A Audit
- Phase 1B Audit
- Phase 2 Audit
- Phase 3 Audit
- Phase 4 Audit
- Phase 5 Audit
- Phase 6 Audit
- Phase 7 Audit
- Phase 8 Audit
- Phase 9 Audit
- Phase 10 Audit
- Phase 11 Audit
- Research Factory Audit

Determine:

1. Remaining Uncovered Risks
2. Remaining Leakage Vectors
3. Remaining Reproducibility Gaps
4. Remaining Governance Gaps
5. Remaining Automation Gaps
6. Remaining Deployment Risks
7. Remaining Operational Risks

For `futures_intraday_model`, production, paper, live, broker, capital, artifact
freeze, and promotion-readiness items must be reported as
`N/A - not approved / not in scope` unless an explicit approved gate and primary
evidence manifest exist. Do not score scaffolding, plans, or untested code paths
as readiness evidence for those items.

Evaluate:

- Platform Integrity
- Data Integrity
- Leakage Control
- Statistical Validity
- Governance
- Research Automation
- Operational Resilience

Assign Scores:

```text
0-100
```

Interpretation:

- 0-40 = Not Ready
- 41-60 = Major Blockers
- 61-80 = Operational With Significant Weaknesses
- 81-95 = Research Factory Capable
- 96-100 = Institutional-Grade Research-Readiness Evidence

Output:

A. Executive Summary

B. Research-Readiness Blockers

C. Highest-Risk Findings

D. Remaining Blind Spots

E. Required Remediation

F. Research-Readiness Verdict

G. Final Readiness Score

H. Recommended Research Status
