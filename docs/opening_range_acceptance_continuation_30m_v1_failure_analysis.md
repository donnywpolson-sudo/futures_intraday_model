# Opening Range Acceptance Continuation Failure Analysis

## Summary

`opening_range_acceptance_continuation_30m_v1` looked strong because it passed the target-construction smoke stages and later produced clean, nonconstant WFA predictions with high directional accuracy. It ultimately failed because those positives did not translate into a predeclared executable policy with realistic ES round-turn costs.

The core distinction is:

- Target smoke answered: can the target definition produce a ranked subset of high-net examples under bounded target-construction checks?
- WFA/model diagnostics answered: can a simple model produce nonconstant, artifact-clean single-target predictions?
- Costed policy diagnostics answered: does a predeclared one-contract, non-overlapping, single-target policy make money after costs?

The first two answers were yes. The third answer was no.

## Evidence Timeline

| Layer | Artifact | Result | What It Proved | What It Did Not Prove |
| --- | --- | --- | --- | --- |
| Phase 9 discovery smoke | `reports/pipeline_audit/es_30m_target_smoke_opening_range_acceptance_continuation_30m_v1_discovery_smoke.json` | `DISCOVERY_PASS`, `failure_count=0` | Target idea passed discovery gates. Top 5% rows had positive net. | Not WFA model evidence. Not an executable trading policy. |
| Phase 9 confirmation smoke | `reports/pipeline_audit/es_30m_target_smoke_opening_range_acceptance_continuation_30m_v1_confirmation_smoke.json` | `CONFIRMATION_PASS`, `failure_count=0` | Target idea repeated in confirmation. | Still not model promotion or policy PnL evidence. |
| Phase 9 locked smoke | `reports/pipeline_audit/es_30m_target_smoke_opening_range_acceptance_continuation_30m_v1_locked_smoke.json` | `LOCKED_PASS`, `failure_count=0` | Locked target-construction smoke passed all gates. | Did not prove a deployable or profitable model policy. |
| Phase 6 WFA expansion | `reports/wfa/opening_range_acceptance_continuation_30m_v1_model_expansion/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_predictions_manifest.json` and WFA report | `failure_count=0`, `prediction_count=72539`, `fold_count=4` | Prediction artifacts were present, clean, and metadata-ready. | Did not prove model trust or policy economics. |
| Phase 8 single-target diagnostics | `reports/phase8_single_target/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_single_target_diagnostics.json` | `failure_count=0`, nonconstant predictions, 3-class balance | The single-target prediction contract was coherent. | Diagnostic-only. Canonical multi-target Phase 8 policy was not applicable. |
| Costed single-target policy/PnL | `reports/phase8_single_target_policy/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_single_target_policy_diagnostics.json` | `failure_count=0`, but `net_return_dollars=-80468.5` | The predeclared executable single-target policy was evaluated cleanly. | It failed the economic decision bar. |

## What Was Working

The target-construction smoke evidence was legitimately strong for its purpose.

| Stage | Decision | Top fraction | Scored rows | Top rows | Top total net | Positive top-net folds |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Discovery | `DISCOVERY_PASS` | `0.05` | `2723` | `138` | `37929.0` | `4` |
| Confirmation | `CONFIRMATION_PASS` | `0.05` | `2561` | `130` | `45715.0` | `4` |
| Locked | `LOCKED_PASS` | `0.05` | `2770` | `141` | `50403.0` | `4` |

The locked smoke also passed the main target gates:

- Input/schema gate passed.
- Class balance gate passed: `event_count=16059`, long `6265`, short `5369`, flat `4425`.
- Duplicate overlap gate passed: overlap with the current 15-minute deadzone target was `0.6320268179473956`, below the `0.80` cap.
- Fold stability gate passed.
- Positive stage-net gate passed.

The WFA/model-quality layer also looked healthy:

- WFA prediction manifest had `failure_count=0`, `prediction_count=72539`, `fold_count=4`, `duplicate_prediction_count=0`, and `artifact_evidence_ready=true`.
- Single-target diagnostics had `failure_count=0`, `warning_count=0`, `row_count=72539`, `duplicate_prediction_count=0`, and `prediction_std=0.7409888972496982`.
- Class balance remained broad in the prediction set: `-1=24409`, `0=19935`, `1=28195`.
- Directional accuracy by fold was high for a simple single-target model:
  - `ES_research_0001`: `0.7357977276364218`
  - `ES_research_0002`: `0.7090463084839057`
  - `ES_research_0003`: `0.7295509104748522`
  - `ES_research_0004`: `0.7607880394019702`

These facts explain why the candidate looked promising. It had a plausible target, stable target-smoke top-net evidence, clean artifacts, nonconstant predictions, and strong directional classification diagnostics.

## What Failed

The costed policy/PnL diagnostic changed the question from "can this target/model rank or classify useful rows?" to "does a predeclared policy turn these predictions into net dollars after costs?"

The answer was no.

| Scope | Rows | Trades | Candidate trades | Overlap-blocked | Gross | Costs | Net |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | `72539` | `2668` | `66473` | `63805` | `-1762.5` | `78706.0` | `-80468.5` |
| `ES_research_0001` | `18747` | `697` | `17466` | `16769` | `2475.0` | `20561.5` | `-18086.5` |
| `ES_research_0002` | `16714` | `608` | `14815` | `14207` | `2637.5` | `17936.0` | `-15298.5` |
| `ES_research_0003` | `17079` | `617` | `15518` | `14901` | `5037.5` | `18201.5` | `-13164.0` |
| `ES_research_0004` | `19999` | `746` | `18674` | `17928` | `-11912.5` | `22007.0` | `-33919.5` |

The policy diagnostic was mechanically clean: `failure_count=0`, `prediction_manifest_artifact_evidence_ready=true`, and promotion/live flags stayed blocked. The failure was economic, not artifact-related.

The most important facts:

- Gross PnL was already negative overall: `-1762.5`.
- Costs were much larger than the gross signal: `78706.0`.
- Net PnL was materially negative: `-80468.5`.
- All 4 folds were net negative after costs.
- Net Sharpe-like was negative: `-5.377058720573415`.
- Win rate on net-positive trades was only `0.4122938530734633`.

## Root Cause

The target-smoke success and model-quality success were real, but they were not the same as policy success.

The smoke harness evaluated a top-fraction target-construction/ranking scenario. In the locked smoke, the top `141` of `2770` scored rows produced `50403.0` top total net. That is useful evidence that the target contains high-value cases when sorted by the smoke model's score. It is not evidence that a later model policy will select a sparse, profitable, cost-resilient trade set.

The single-target WFA model had high directional accuracy, but directional accuracy does not measure:

- whether correct calls have enough dollar magnitude to cover costs;
- whether incorrect calls are larger than correct calls;
- whether the policy trades too often;
- whether the selected trades are the same high-value rows seen in the target-smoke top fraction;
- whether a single direction target is enough to filter expected return, fade risk, and side-aware trend danger.

The predeclared costed policy made this mismatch visible. It used unique max probability across `p_long`, `p_short`, and `p_flat`, at most one contract, and non-overlapping target windows. That still produced `66473` candidate trades and `2668` executed trades. After applying ES round-turn costs, the gross edge was not large enough. In fact, the gross edge was slightly negative before costs.

So the failure was not "the target was never good." The better explanation is:

1. The target smoke found a promising subset under target-construction ranking checks.
2. The WFA model learned a nonconstant directional signal with good classification diagnostics.
3. The executable single-target policy did not preserve enough of the smoke-stage economic edge.
4. Costs and trade selection overwhelmed the directional signal.

## Lessons

- Treat target smokes as idea filters, not proof of tradable edge.
- Treat directional accuracy as model-quality evidence, not PnL evidence.
- Require costed policy diagnostics before saying a candidate is "doing well" in an economic sense.
- Separate three decisions: target validity, model predictability, and executable policy economics.
- For future hypotheses, define earlier whether the intended acceptance bar is top-fraction target value, model classification quality, or actual costed policy PnL.

## Status And Caveats

Verified facts in this report come from the local JSON/CSV artifacts listed above. The current registry/trial-status files are status context only; they are not used as proof of model performance.

This report does not recommend tuning, rerunning, promotion, WFA expansion, registry/status mutation, paper trading, or live trading. Any registry/status disposition, including a schema-compatible `RETIRED` update, remains a separate decision.
