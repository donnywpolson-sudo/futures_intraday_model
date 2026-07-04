# opening_range_acceptance_continuation_30m_v1 Low Tick Rule Attribution

## Summary

- Prediction rows reviewed: `72539`.
- Candidate trades before non-overlap: `66473` (`91.6%` of prediction rows).
- Executed trades after non-overlap: `2668`; overlap-blocked candidates: `63805`.
- Executed fixed-exit realized ticks: mean `-0.05`, median `0.00`.
- Executed path MFE: median `9.00` ticks; median giveback to fixed exit `9.00` ticks.
- Trades with MFE `>=5` ticks but fixed-exit realized ticks `<=2`: `831 (31.1%)`.
- Trades with MFE `>=8` ticks but fixed-exit realized ticks `<=2`: `532 (19.9%)`.

Root cause: the target rewarded path opportunity, while the evaluated policy exited at a fixed 30-minute open. The model often identified the target direction, but the policy had no rule to capture favorable excursion before giveback.

## Inputs

- Predictions: `data/predictions/opening_range_acceptance_continuation_30m_v1_model_expansion/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/oos_predictions.parquet`.
- Executed trades: `reports/phase8_single_target_policy/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_single_target_policy_trades.csv`.
- ES 2024 materialized bars: `data/feature_matrices/opening_range_acceptance_continuation_30m_v1_wfa_smoke/ES/2024.parquet`.
- Costs config: `configs/costs.yaml`.

## Rule Stack

| Layer | Rule | Measured Effect | Attribution |
| --- | --- | --- | --- |
| Target | Close outside completed opening range; future path MFE must clear cost + min profit. | Median executed-trade MFE was 9.00 ticks. | Labels opportunity sometime in path, not fixed-exit PnL. |
| Materialization | Maps frozen path direction into target_sign_with_deadzone. | Target-direction matches averaged 4.53 fixed-exit ticks; mismatches averaged -11.86. | Correct class helped, but still did not guarantee enough fixed-exit edge. |
| Model | Logistic classifier predicts p_long/p_short/p_flat. | Confidence deciles did not create a monotonic fixed-exit edge. | It predicts class direction, not expected ticks or trade expectancy. |
| Policy | Trades any unique max long/short probability. | 66473 of 72539 rows were candidate trades (91.6%). | No confidence, margin, or minimum expected-tick threshold filtered weak edges. |
| Execution | One contract, non-overlap, next-bar entry, fixed 30-minute exit open. | Executed mean was -0.05 ticks and median was 0.00. | Fixed exit gave back path opportunity; no TP/SL captured the move. |
| Cost | Current ES round turn is configured as all-in cost. | $29.50 = 2.36 ticks. | Average gross trade did not cover even one round turn. |

## Candidate, Executed, And Blocked Stages

| Stage | Rows | Mean fixed-exit ticks | Median fixed-exit ticks | Realized <= 2 ticks |
| --- | --- | --- | --- | --- |
| candidate_pre_nonoverlap | 66473 | -0.26 | 0.00 | 38591 (58.1%) |
| executed_after_nonoverlap | 2668 | -0.05 | 0.00 | 1568 (58.8%) |
| blocked_by_nonoverlap | 63805 | -0.26 | 0.00 | 37023 (58.0%) |

## Path Label Direction Vs Fixed-Exit PnL

| Target direction | Trades | Mean realized ticks | Median realized ticks | Realized <= 2 | Median MFE | Median giveback |
| --- | --- | --- | --- | --- | --- | --- |
| match | 1922 | 4.53 | 4.00 | 43.6% | 14.00 | 9.00 |
| mismatch | 746 | -11.86 | -8.00 | 97.9% | 2.00 | 10.00 |

## Model Confidence Deciles

| Direction probability decile | Candidate rows | Executed rows | Mean fixed-exit ticks | Median fixed-exit ticks | Realized <= 2 |
| --- | --- | --- | --- | --- | --- |
| (0.499, 0.569] | 6648 | 373 | 0.21 | 0.00 | 64.1% |
| (0.569, 0.631] | 6647 | 305 | 0.67 | 0.00 | 62.7% |
| (0.631, 0.684] | 6647 | 273 | -0.00 | -1.00 | 62.6% |
| (0.684, 0.73] | 6647 | 251 | -0.43 | 0.00 | 58.4% |
| (0.73, 0.77] | 6648 | 256 | -0.69 | 0.00 | 57.0% |
| (0.77, 0.807] | 6647 | 250 | -0.99 | -1.00 | 58.5% |
| (0.807, 0.839] | 6647 | 251 | -1.65 | -1.00 | 57.5% |
| (0.839, 0.871] | 6647 | 251 | -0.47 | 0.00 | 53.9% |
| (0.871, 0.906] | 6647 | 225 | 0.49 | 0.00 | 52.8% |
| (0.906, 1.0] | 6648 | 233 | 0.31 | 0.00 | 53.0% |

## Opening-Range Acceptance Distance

| Abs acceptance distance | Executed trades | Mean realized ticks | Median realized ticks | Realized <= 2 |
| --- | --- | --- | --- | --- |
| 0-1 | 226 | 0.01 | -1.00 | 63.7% |
| 1-2 | 158 | -0.63 | -1.00 | 60.1% |
| 2-4 | 182 | 0.87 | 1.00 | 57.7% |
| 4-8 | 245 | 0.65 | 0.00 | 60.4% |
| 8+ | 1857 | -0.20 | -1.00 | 57.9% |

## Interpretation

- Non-overlap did not create the low-tick problem. Candidate, executed, and blocked candidates all had median fixed-exit ticks around zero.
- The class signal was not useless: target-direction matches were much better than mismatches. The problem is that correct direction at some point in the path did not reliably translate to fixed-exit dollars.
- Large both-side movement means simple TP/SL rescue cannot be inferred from OHLC alone. Any future stop/target policy needs ordered first-touch validation or lower-timeframe execution evidence.
- This report does not approve tuning, stop/target backtests, WFA/modeling, registry/status mutation, promotion, paper trading, or live trading.
