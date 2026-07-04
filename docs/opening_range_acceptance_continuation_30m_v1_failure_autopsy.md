# opening_range_acceptance_continuation_30m_v1 Failure Autopsy

## Summary

This report separates what looked promising from what failed economically. The target/model evidence can be real while the executable policy still loses money.

## Evidence Timeline

| Layer | Result | Key Metric | Plain English |
| --- | --- | --- | --- |
| Target smoke: discovery | DISCOVERY_PASS | Top net $37,929.00; positive folds 4 | Target idea looked viable, not policy proof. |
| Target smoke: confirmation | CONFIRMATION_PASS | Top net $45,715.00; positive folds 4 | Target idea looked viable, not policy proof. |
| Target smoke: locked | LOCKED_PASS | Top net $50,403.00; positive folds 4 | Target idea looked viable, not policy proof. |
| WFA/model artifacts | failure_count=0 | 72539 predictions; duplicate predictions 0 | Prediction artifacts were mechanically usable. |
| Costed policy PnL | failure_count=0 | net $-80,468.50; trades 2668 | Economic result failed after costs. |
| First-touch TP/SL feasibility | FIRST_TOUCH_FEASIBILITY_NO_GO | positive stop-first grids 0/36 | Simple TP/SL capture did not rescue the policy. |

## What Looked Good

| Evidence | Metric | Context | Meaning |
| --- | --- | --- | --- |
| Locked target smoke | $50,403.00 | 4 positive top-net folds | The target contained ranked path opportunity. |
| Duplicate overlap | 0.632 | cap was 0.80 | The target was not just the existing baseline target. |
| WFA artifacts | 72539 predictions | artifact ready=True | The model output was clean enough to review. |

## What Failed

| Evidence | Metric | Context | Meaning |
| --- | --- | --- | --- |
| Gross PnL | $-1,762.50 | Before costs | The fixed-exit policy had no positive gross edge overall. |
| Costs | $78,706.00 | $29.50/trade | The cost load overwhelmed the captured edge. |
| Net PnL | $-80,468.50 | 2668 trades | The executable policy failed economically. |
| First-touch TP/SL | 0/36 positive grids | FIRST_TOUCH_FEASIBILITY_NO_GO | Simple TP/SL capture did not rescue the candidate. |

## Per-Trade Cost And Tick Translation

- Trades: `2668`.
- Gross PnL: `$-1,762.50`.
- Costs: `$78,706.00` = `$29.50` per trade.
- Cost in ticks: `2.36` ticks per trade.
- Net PnL: `$-80,468.50`.

## Fixed-Exit Versus Path Opportunity

The failed policy entered once and exited at the fixed horizon. It did not capture favorable path movement unless that movement was still present at the fixed exit.
- Median max favorable excursion: `9.00` ticks.
- Median fixed-exit realized ticks: `0.00` ticks.
- Median giveback by fixed exit: `9.00` ticks.
- Trades with MFE >= 5 ticks but realized <= 2 ticks: `831` (31.1%).

## Fold-Level PnL

| Fold | Trades | Gross | Costs | Net |
| --- | --- | --- | --- | --- |
| ES_research_0001 | 697 | $2,475.00 | $20,561.50 | $-18,086.50 |
| ES_research_0002 | 608 | $2,637.50 | $17,936.00 | $-15,298.50 |
| ES_research_0003 | 617 | $5,037.50 | $18,201.50 | $-13,164.00 |
| ES_research_0004 | 746 | $-11,912.50 | $22,007.00 | $-33,919.50 |

## Overtrading And Turnover

- Candidate trades before non-overlap: `66473`.
- Prediction rows: `72539`.
- Candidate trade rate: `91.6%`.
- Overlap-blocked candidates: `63805`.

Plain English: the model wanted to trade most rows, so the policy did not isolate a small high-quality subset.

## MFE, MAE, And Giveback

- Median MFE: `9.00` ticks.
- Median MAE: `10.00` ticks.
- Median giveback: `9.00` ticks.
- Realized <= 2 gross ticks: `1568` (58.8%).

## First-Touch TP/SL Feasibility

- Screen status: `FIRST_TOUCH_FEASIBILITY_NO_GO`.
- Positive stop-first grids: `0/36`.
- Positive ambiguous-excluded grids: `0/36`.
- Best stop-first cell: TP `2` / SL `10` with net `$-76,981.00`.

## Failure Classifications

| Classification | Trigger Metric | Plain English |
| --- | --- | --- |
| TARGET_LOOKED_GOOD_BUT_POLICY_FAILED | 3 target-smoke pass stages, policy net $-80,468.50 | The target idea passed its smoke gates, but the costed policy lost money. |
| GROSS_EDGE_ABSENT | gross PnL before costs $-1,762.50 | The policy did not have positive dollars even before costs. |
| COST_DRAG_DOMINANT | costs $78,706.00 versus gross $-1,762.50 | Execution costs were much larger than the captured gross edge. |
| OVERTRADING_OR_WEAK_FILTER | candidate trades 66473/72539 (91.6%) | The policy wanted to trade most rows, so it had little selectivity. |
| PATH_OPPORTUNITY_NOT_CAPTURED | median MFE 9.00 ticks, median realized 0.00 ticks | Trades often moved favorably but did not keep that value by the evaluated exit. |
| FIRST_TOUCH_NO_GO | positive stop-first TP/SL grids 0/36 | Simple first-touch TP/SL capture did not rescue the failed policy. |

## Trader Lesson

The useful lesson is not simply that this candidate lost money. The lesson is that target quality, model classification quality, and executable policy economics are separate layers.

For this candidate, the path-opportunity target looked good, but the evaluated policies did not turn that opportunity into net dollars after realistic ES costs. Future candidates should define the intended exit/capture rule at the same time as the target, then demand costed policy evidence before calling the candidate strong.

This report is diagnostic only. It does not approve rescue work, parameter selection, registry/status mutation, promotion, paper trading, or live trading.
