# Artifact Readiness Audit

Audit spec: `ARTIFACT_AUDIT.md`

Audit target: current local artifact evidence, using `PROJECT_OUTLINE.md` as the
gate and workflow authority.

Date: 2026-07-04

## Evidence Scope

This audit refreshes the ES 2026 artifact-readiness state after the repaired
Phase 5 split, one bounded Phase 6 model smoke, and Phase 8 diagnostics review.

Commands and checks used:

- `python -m scripts.validation.run_local_trade_es2026_p1_downstream_wfa_split_build --execute --approval-token APPROVE_ES2026_P1_PHASE5_WFA_SPLIT_BUILD_V1`
- `python -m scripts.validation.run_local_trade_es2026_p1_downstream_model_build --execute --approval-token APPROVE_ES2026_P1_PHASE6_MODEL_SMOKE_V1`
- `python -m scripts.validation.run_local_trade_es2026_p1_downstream_metrics_build --execute --approval-token APPROVE_ES2026_P1_PHASE8_METRICS_V1`
- `python -m scripts.validation.build_local_trade_es2026_p1_downstream_metrics_review --print-review-json`
- `python -m scripts.validation.build_local_trade_es2026_p1_workflow_status --print-boundary-json`
- targeted reads of split, prediction, WFA, metrics, model-selection, and Phase 8
  reports
- `git status --short -- data reports`
- `git diff --cached --name-only -- data reports`

No provider downloads, broad scans, cleanup commands, staging, commits, pushes,
proof scans, promotion, artifact freeze, paper, or live execution were run.

## Verified Facts

- Phase 5 split execution returned
  `EXECUTED_ES2026_P1_DOWNSTREAM_WFA_SPLIT_BUILD` with 1 command executed, 2
  expected ignored split outputs generated, 0 unexpected outputs, 0 staged
  generated paths, and 0 failures.
- `reports/wfa/local_trade_es2026_p1_candidate/split_plan.json` records
  `profile=local_trade_es2026_p1_research_smoke`, exact `markets=["ES"]`, exact
  `years=[2026]`, `feature_manifest_profile=tier_3_forward`, `fold_count=4`, 4
  selectable research folds, purge/embargo `31/31`, and `failure_count=0`.
- Phase 6 model-smoke execution returned
  `EXECUTED_ES2026_P1_DOWNSTREAM_MODEL_BUILD` with 1 command executed, 3 expected
  ignored outputs generated, 0 unexpected outputs, 0 staged generated paths, and
  0 failures.
- The prediction manifest records exact ES 2026 scope, `matrix=baseline`,
  `run=local_trade_es2026_p1_model_smoke`, 122 features, 1 executed fold from 4
  selectable folds, 106,640 predictions, zero duplicate predictions,
  `artifact_evidence_ready=true`, `warning_count=0`, and `failure_count=0`.
- The prediction parquet has 106,640 rows, `market=["ES"]`, `year=[2026]`, and
  zero duplicate full rows.
- Phase 8 diagnostics generated the expected 8 ignored reports under
  `reports/metrics/local_trade_es2026_p1_candidate_model`,
  `reports/model_selection/local_trade_es2026_p1_candidate_model`, and
  `reports/phase8/local_trade_es2026_p1_candidate_model`.
- A wrapper-validator field-name mismatch was found and repaired: the Phase 8
  evaluator writes `prediction_manifest_path` in `model_selection_report.json`;
  the wrapper now accepts that actual report field.
- `build_local_trade_es2026_p1_downstream_metrics_review` returns
  `REVIEW_READY_ES2026_P1_DOWNSTREAM_METRICS_REVIEW` with model output `PASS`,
  metrics output `PASS`, 8 expected ignored existing reports, 0 commands
  executed, 0 generated outputs, 0 staged generated paths, and 0 failures.
- The Phase 8 review reports `research_policy_metrics_ready=true`,
  `research_alpha_ready=false`, `model_promotion_allowed=false`, and
  `alpha_promoted=false`.
- Main blockers recorded by the review include negative gross return
  (`-2850.0`), negative net return (`-8927.0`), negative net-sharpe-like
  (`-1.9225`), cost drag above threshold (`2.1323`), one market, one traded
  fold, nonpositive ES/fold net return, and missing statistical-validity evidence
  for PBO, Deflated Sharpe, Probabilistic Sharpe, bootstrap confidence
  intervals, multiple-testing adjustment, parameter stability, and regime
  breakdowns.
- Generated-artifact hygiene remained clean: `git status --short -- data reports`
  and `git diff --cached --name-only -- data reports` returned no paths.

## Assumptions

- This audit is focused on the active ES 2026 P1 candidate chain, not full Tier 1
  alpha proof.
- The `local_trade_es2026_p1_research_smoke` profile is research-smoke evidence
  only, not locked-forward, promotion, artifact-freeze, paper, or live evidence.

## Inferences

- The original zero-fold split blocker is resolved for this bounded ES 2026
  research-smoke chain.
- The exact baseline/model-smoke candidate should be killed or revised, not
  continued as alpha evidence, because Phase 8 diagnostics are structurally
  valid but economically negative and statistically incomplete.

## Missing Evidence

- No profitable or stable alpha evidence exists for this ES 2026 candidate.
- No statistical-validity package exists for this candidate: PBO, Deflated
  Sharpe, Probabilistic Sharpe, bootstrap confidence intervals, multiple-testing
  adjustment, parameter stability, and regime breakdowns are missing or failing.
- No promotion, artifact-freeze, proof-scan, paper, or live readiness evidence is
  approved or present.

## Findings

### High: ES 2026 P1 Model-Smoke Fails Alpha Evidence

- Artifact gate: Phase 8 diagnostics review.
- Evidence inspected: `alpha_promotion_decision.json`, Phase 8 metrics review,
  model-selection reports, and metrics JSON.
- Issue: diagnostics are structurally review-ready but reject alpha readiness:
  negative gross/net performance, high cost drag, one market/fold only, and
  missing statistical-validity evidence.
- Why it matters: continuing this exact candidate would invite tuning against a
  bad first result and increase data-snooping risk.
- Missing or contradictory evidence: no positive net performance, no fold/market
  stability, and no statistical-validity support.
- Recommended fix or bounded plan: kill this exact ES 2026 P1 baseline/model
  smoke as alpha evidence; only continue through a newly predeclared alpha
  thesis or clearly revised hypothesis.
- Correct next gate placement: Phase 9 bounded alpha-discovery loop, before any
  new WFA/model execution.

### Medium: Artifact Chain Is Structurally Complete Through Diagnostics

- Artifact gate: Phase 5, Phase 6, and Phase 8.
- Evidence inspected: split manifest, prediction manifest, prediction parquet,
  metrics reports, metrics review, and generated-artifact hygiene checks.
- Issue: the chain produced valid split, prediction, and metrics artifacts, but
  the diagnostics reject alpha quality.
- Why it matters: the workflow is now useful for falsifiable alpha tests, but
  the tested candidate did not pass.
- Missing or contradictory evidence: no promotion-eligible performance evidence.
- Recommended fix or bounded plan: preserve this result as a rejected smoke and
  move to the next small predeclared alpha idea.
- Correct next gate placement: new bounded alpha hypothesis declaration.

### Medium: Fully Unavailable Feature Warning Remains A Research Risk

- Artifact gate: Phase 4 feature evidence and Phase 6 model evidence.
- Evidence inspected: feature manifest, split manifest, and model-smoke reports.
- Issue: the ES-only feature manifest still carries the fully unavailable
  intermarket/Tier 1 feature warning.
- Why it matters: feature unavailability may weaken model interpretability and
  transfer to broader profiles.
- Missing or contradictory evidence: no dedicated ablation or model-stage
  feature handling report for unavailable feature groups.
- Recommended fix or bounded plan: do not rescue this rejected smoke by tuning;
  handle feature availability policy before any broader candidate promotion.
- Correct next gate placement: next alpha thesis precheck or Phase 4/6 feature
  policy, depending on the next hypothesis.

## A. Artifact Dependency Status

1. Scope/current gate: verified through Phase 8 metrics review for the ES 2026 P1
   smoke.
2. Raw data and metadata: partial; not re-audited in this refresh.
3. Cleaning/causal base: partial; upstream exact ES 2026 evidence exists but was
   not fully re-audited here.
4. Labels/targets: partial; upstream exact ES 2026 label evidence exists.
5. Features: partial; feature artifacts exist with one accepted warning.
6. Splits/WFA design: verified for bounded research-smoke use.
7. Models/predictions: verified for one first-fold model smoke.
8. Metrics/costs/risk/statistical validity: partial; diagnostics exist and reject
   alpha readiness, while statistical-validity evidence is missing/failing.
9. Promotion/artifact freeze: blocked.
10. Paper/live execution: deferred.

## B. Model-Trust Readiness Scorecard

- Artifact Completeness: 75. The smoke chain now has labels/features/splits,
  predictions, and metrics artifacts.
- Data Lineage Evidence: 60. Current manifests carry exact scope, but full raw
  metadata lineage was not re-audited here.
- Warning/Exception Defensibility: 55. Warnings are scoped, but unavailable
  feature policy remains a research risk.
- Label/Feature Leakage Defense: 65. Upstream gates are present; no new leakage
  failure was found in this refresh.
- Split/WFA Evidence: 70. Four selectable research folds exist, but only one
  fold was used in the model smoke.
- Prediction Artifact Evidence: 80. Prediction manifest/parquet evidence is
  exact-scope and internally clean for the smoke.
- Cost/Risk Evidence: 45. Costs are applied in Phase 8 diagnostics, but the
  result fails economics and realistic execution remains outside scope.
- Statistical Validity Evidence: 10. Required statistical-validity evidence is
  missing/failing.
- Promotion Readiness: 0. Explicitly blocked.
- Production/Paper Readiness: N/A. Deferred and not in scope.
- Overall Model-Trust Confidence: 35. Artifacts are present, but the candidate
  failed the alpha test.

## C. Remediation Roadmap

Phase 1: artifact blockers before any model trust

- Treat this ES 2026 P1 baseline/model-smoke as rejected alpha evidence.

Phase 2: validation evidence gaps

- Predeclare the next alpha thesis before any further execution. Do not tune this
  failed smoke result.

Phase 3: statistical and robustness evidence

- Only candidates with positive net, cost-robust, fold-stable evidence should
  earn broader folds, markets, or statistical-validity work.

Phase 4: promotion/freeze or paper/live readiness, only if in scope

- Keep promotion, artifact freeze, paper, and live readiness blocked.

## D. Next Action

Kill or revise this exact ES 2026 P1 baseline/model-smoke candidate, then choose
the next predeclared alpha thesis from `configs/alpha_tiered.yaml` for a new
small bounded discovery loop.

```text
NEXT_ACTION:
type: approval_required
target_file: configs/alpha_tiered.yaml
summary: Select or add one predeclared next alpha thesis for a new bounded smoke; do not retune this failed ES 2026 P1 result.
bounded_command:
```
