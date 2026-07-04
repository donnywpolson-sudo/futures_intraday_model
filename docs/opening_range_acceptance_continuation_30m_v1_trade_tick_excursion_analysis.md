# opening_range_acceptance_continuation_30m_v1 Trade Tick Excursion Analysis

## Summary

- Executed trades analyzed: `2668`.
- ES tick size/value: `0.25` points, `$12.50` per tick.
- Current configured round-turn cost: `$29.50` = `2.36` ticks.
- Total realized gross: `-141.00` ticks / `$-1762.50`.
- Total current-cost net: `-6437.48` ticks / `$-80468.50`.
- Trades whose max favorable excursion was only `<= 2` ticks: `447 (16.8%)`.
- Trades whose max favorable excursion did not cover the current `2.36`-tick cost: `447 (16.8%)`.
- Trades whose max adverse excursion was at least the current `2.36`-tick cost: `2269 (85.0%)`.

## Inputs And Validation

- Trades CSV: `reports/phase8_single_target_policy/opening_range_acceptance_continuation_30m_v1_model_expansion_s1/opening_range_acceptance_continuation_30m_v1_model_expansion_s1_single_target_policy_trades.csv`.
- ES 2024 materialized bars: `data/feature_matrices/opening_range_acceptance_continuation_30m_v1_wfa_smoke/ES/2024.parquet`.
- Costs config: `configs/costs.yaml`.
- Join checks: `2668` signal bars, `2668` entry bars, and `2668` exit bars matched.
- Path convention: highs/lows from entry timestamp up to but not after the exit-open bar, plus the exit price.
- Caveat: OHLC bars do not prove intrabar first-touch ordering. TP/SL rows where both thresholds touched are intentionally marked ambiguous.

## Overall Tick Distribution

| Metric | Mean | Median | P25 | P75 | P90 | Min | Max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Realized gross ticks | -0.05 | 0.00 | -9.00 | 9.00 | 22.00 | -313.00 | 197.00 |
| Current-cost net ticks | -2.41 | -2.36 | -11.36 | 6.64 | 19.64 | -315.36 | 194.64 |
| Max favorable excursion ticks | 14.91 | 9.00 | 4.00 | 19.00 | 34.00 | 0.00 | 207.00 |
| Max adverse excursion ticks | 15.11 | 10.00 | 4.00 | 19.00 | 34.00 | 0.00 | 335.00 |

## Favorable Excursion Buckets

| Max favorable ticks | Trades |
| --- | --- |
| <= 0 | 102 (3.8%) |
| > 0 to <= 1 | 157 (5.9%) |
| > 1 to <= 2 | 188 (7.0%) |
| > 2 to <= 4 | 313 (11.7%) |
| > 4 to <= 8 | 505 (18.9%) |
| > 8 to <= 10 | 185 (6.9%) |
| > 10 | 1218 (45.7%) |

## Take-Profit Reach Rates

| TP ticks reached | Trades |
| --- | --- |
| >= 1 | 2566 (96.2%) |
| >= 2 | 2409 (90.3%) |
| >= 3 | 2221 (83.2%) |
| >= 4 | 2081 (78.0%) |
| >= 5 | 1908 (71.5%) |
| >= 8 | 1515 (56.8%) |
| >= 10 | 1310 (49.1%) |

## Stop-Loss Reach Rates

| SL ticks reached | Trades |
| --- | --- |
| >= 1 | 2570 (96.3%) |
| >= 2 | 2421 (90.7%) |
| >= 3 | 2269 (85.0%) |
| >= 4 | 2114 (79.2%) |
| >= 5 | 1974 (74.0%) |
| >= 8 | 1563 (58.6%) |
| >= 10 | 1345 (50.4%) |

## Same-Size TP/SL Outcomes

| TP=SL ticks | TP only | SL only | Both ambiguous | Neither |
| --- | --- | --- | --- | --- |
| 1 | 98 (3.7%) | 102 (3.8%) | 2468 (92.5%) | 0 (0.0%) |
| 2 | 247 (9.3%) | 259 (9.7%) | 2162 (81.0%) | 0 (0.0%) |
| 3 | 396 (14.8%) | 444 (16.6%) | 1825 (68.4%) | 3 (0.1%) |
| 4 | 541 (20.3%) | 574 (21.5%) | 1540 (57.7%) | 13 (0.5%) |
| 5 | 632 (23.7%) | 698 (26.2%) | 1276 (47.8%) | 62 (2.3%) |
| 8 | 741 (27.8%) | 789 (29.6%) | 774 (29.0%) | 364 (13.6%) |
| 10 | 743 (27.8%) | 778 (29.2%) | 567 (21.3%) | 580 (21.7%) |

## Long Vs Short

| Position | Trades | Avg gross ticks | Avg net ticks | Median MFE | Median MAE | MFE <= 2 | MAE >= 3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| -1 | 1249 | -0.32 | -2.68 | 10.00 | 11.00 | 192 (15.4%) | 1088 (87.1%) |
| 1 | 1419 | 0.19 | -2.17 | 9.00 | 9.00 | 255 (18.0%) | 1181 (83.2%) |

## Fold Summary

| Fold | Trades | Avg gross ticks | Avg net ticks | Median MFE | Median MAE | MFE <= 2 | MAE >= 3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ES_research_0001 | 697 | 0.28 | -2.08 | 9.00 | 8.00 | 115 (16.5%) | 599 (85.9%) |
| ES_research_0002 | 608 | 0.35 | -2.01 | 8.00 | 9.00 | 112 (18.4%) | 503 (82.7%) |
| ES_research_0003 | 617 | 0.65 | -1.71 | 9.00 | 8.00 | 107 (17.3%) | 502 (81.4%) |
| ES_research_0004 | 746 | -1.28 | -3.64 | 11.00 | 13.00 | 113 (15.1%) | 665 (89.1%) |

## Full TP/SL Grid

Each row counts whether the path touched the take-profit threshold, the stop-loss threshold, both, or neither. `Both` is not a win or loss because first touch is unknown from OHLC bars.

| TP | SL | TP only | SL only | Both ambiguous | Neither |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 98 | 102 | 2468 | 0 |
| 1 | 2 | 247 | 102 | 2319 | 0 |
| 1 | 3 | 399 | 102 | 2167 | 0 |
| 1 | 4 | 554 | 102 | 2012 | 0 |
| 1 | 5 | 694 | 102 | 1872 | 0 |
| 1 | 8 | 1100 | 97 | 1466 | 5 |
| 1 | 10 | 1310 | 89 | 1256 | 13 |
| 2 | 1 | 98 | 259 | 2311 | 0 |
| 2 | 2 | 247 | 259 | 2162 | 0 |
| 2 | 3 | 398 | 258 | 2011 | 1 |
| 2 | 4 | 552 | 257 | 1857 | 2 |
| 2 | 5 | 690 | 255 | 1719 | 4 |
| 2 | 8 | 1073 | 227 | 1336 | 32 |
| 2 | 10 | 1262 | 198 | 1147 | 61 |
| 3 | 1 | 98 | 447 | 2123 | 0 |
| 3 | 2 | 247 | 447 | 1974 | 0 |
| 3 | 3 | 396 | 444 | 1825 | 3 |
| 3 | 4 | 549 | 442 | 1672 | 5 |
| 3 | 5 | 678 | 431 | 1543 | 16 |
| 3 | 8 | 1024 | 366 | 1197 | 81 |
| 3 | 10 | 1190 | 314 | 1031 | 133 |
| 4 | 1 | 98 | 587 | 1983 | 0 |
| 4 | 2 | 247 | 587 | 1834 | 0 |
| 4 | 3 | 392 | 580 | 1689 | 7 |
| 4 | 4 | 541 | 574 | 1540 | 13 |
| 4 | 5 | 661 | 554 | 1420 | 33 |
| 4 | 8 | 980 | 462 | 1101 | 125 |
| 4 | 10 | 1135 | 399 | 946 | 188 |
| 5 | 1 | 98 | 760 | 1810 | 0 |
| 5 | 2 | 244 | 757 | 1664 | 3 |
| 5 | 3 | 384 | 745 | 1524 | 15 |
| 5 | 4 | 519 | 725 | 1389 | 35 |
| 5 | 5 | 632 | 698 | 1276 | 62 |
| 5 | 8 | 915 | 570 | 993 | 190 |
| 5 | 10 | 1053 | 490 | 855 | 270 |
| 8 | 1 | 94 | 1149 | 1421 | 4 |
| 8 | 2 | 219 | 1125 | 1296 | 28 |
| 8 | 3 | 339 | 1093 | 1176 | 60 |
| 8 | 4 | 445 | 1044 | 1070 | 109 |
| 8 | 5 | 533 | 992 | 982 | 161 |
| 8 | 8 | 741 | 789 | 774 | 364 |
| 8 | 10 | 853 | 683 | 662 | 470 |
| 10 | 1 | 89 | 1349 | 1221 | 9 |
| 10 | 2 | 200 | 1311 | 1110 | 47 |
| 10 | 3 | 302 | 1261 | 1008 | 97 |
| 10 | 4 | 390 | 1194 | 920 | 164 |
| 10 | 5 | 465 | 1129 | 845 | 229 |
| 10 | 8 | 646 | 899 | 664 | 459 |
| 10 | 10 | 743 | 778 | 567 | 580 |

## Trader Read

- The average realized trade was `-0.05` gross ticks before costs, while the current round-turn cost is `2.36` ticks.
- `1568 (58.8%)` of trades realized `<= 2` gross ticks, which is below the current cost threshold.
- `447 (16.8%)` of trades never offered more than `2` favorable ticks under the tradable path convention.
- Interpretation: this policy did not only lose because costs were high. The realized gross edge was near flat/slightly negative, many trades had limited favorable excursion, and adverse excursion was common enough that simple tight stops would need first-touch validation before being trusted.
- A future stop/target test should use ordered intrabar or lower-timeframe data before treating any ambiguous both-touched TP/SL cell as profitable or losing.
