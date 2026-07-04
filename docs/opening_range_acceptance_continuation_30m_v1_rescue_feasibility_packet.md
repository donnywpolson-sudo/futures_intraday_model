# opening_range_acceptance_continuation_30m_v1 Rescue Feasibility Packet

## Status

`opening_range_acceptance_continuation_30m_v1` is not proven tradable and is not rescued by the fixed-exit or first-touch evidence already reviewed.

This packet prepares one diagnostic-only salvage audit. The audit can preserve useful research signal for a later v2 hypothesis, but it cannot approve v1, select a bucket, select TP/SL parameters, mutate registry/status, promote, paper trade, or live trade.

## Exact Future Command

Run only after separate approval:

```powershell
python -m scripts.phase8_model_selection.candidate_rescue_feasibility --hypothesis-id opening_range_acceptance_continuation_30m_v1 --run opening_range_acceptance_continuation_30m_v1_model_expansion_s1 --market ES
```

Suggested timeout: 300 seconds.

## Inputs

- `data/predictions/opening_range_acceptance_continuation_30m_v1_model_expansion/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/oos_predictions.parquet`
- `reports/wfa/opening_range_acceptance_continuation_30m_v1_model_expansion/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_predictions_manifest.json`
- `reports/wfa/opening_range_acceptance_continuation_30m_v1_model_expansion/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_wfa_report.json`
- `reports/phase8_single_target_policy/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_single_target_policy_diagnostics.json`
- `reports/phase8_single_target_policy/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_single_target_policy_trades.csv`
- `reports/phase8_first_touch_feasibility/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_first_touch_feasibility_diagnostics.json`
- `reports/phase8_first_touch_feasibility/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_first_touch_feasibility_grid.csv`
- `data/feature_matrices/opening_range_acceptance_continuation_30m_v1_wfa_smoke/ES/2024.parquet`
- `configs/costs.yaml`

## Expected Outputs

- `reports/candidate_rescue_feasibility/opening_range_acceptance_continuation_30m_v1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/rescue_feasibility.json`
- `reports/candidate_rescue_feasibility/opening_range_acceptance_continuation_30m_v1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/rescue_feasibility.md`

These are generated `reports/` artifacts and must remain ignored/unstaged.

## Review Questions

- Is even optimistic MFE capture positive after current ES costs?
- Are any stable positive buckets present across predeclared pre-trade families: fold, side, UTC hour, model confidence, probability margin, or opening-range distance?
- Does first-touch evidence remain `NO_GO`, or does any apparent rescue depend on ambiguous OHLC ordering?
- Is the only defensible next step a separately approved v2 hypothesis packet rather than rescuing v1?

## Stop Conditions

Stop without retry or tuning if the command fails, times out, sees stale output paths, reports missing evidence, stages generated artifacts, or returns a decision that does not permit v2 packet review.

Do not run WFA/modeling, rerun diagnostics, select a TP/SL pair, select a bucket, mutate registry/status, promote, stage, commit, push, paper trade, or live trade from this packet.
