# Professional Consensus
The highest priority is not model complexity. It is building a research process that makes it hard to fool yourself.
For an intraday futures algorithm, the priority order should be:
Data integrity first
Exact timestamps, sessions, contract rolls, tick size, point value, missing bars, corporate/exchange calendar effects, volume, spreads, and instrument definitions. Bad data creates fake edge.

# Market microstructure and execution realism
Intraday futures PnL is often decided by spread, queue position, slippage, commissions, partial fills, latency, and liquidity regime. Market microstructure research centers on how trading rules affect transaction costs, price discovery, liquidity, and behavior: market microstructure. CME Globex access also requires proper clearing/application/connectivity setup, not just signals: CME Globex.

# Leakage-resistant validation
Use chronological walk-forward, locked out-of-sample, purging/embargo when labels overlap, and no retuning after seeing test results. Purged CV exists specifically because normal CV leaks in financial time series: purged cross-validation. Walk-forward is a standard trading validation framework: walk-forward optimization.

# Overfitting control
Record every experiment. Penalize multiple testing. Treat impressive Sharpe from many trials as suspect. Deflated Sharpe Ratio adjusts for selection bias, overfitting, sample length, and non-normal returns: DSR. Harvey/Liu also emphasize false discoveries from repeated testing in finance: False and Missed Discoveries.

# Cost model before alpha model
Backtests must include commissions, exchange fees, spread crossing, slippage, delay, rejected trades, realistic fill assumptions, and capacity. Many algorithmic execution methods are explicitly cost-reduction methods measured versus execution benchmarks: algorithmic trading transaction cost reduction.

# Risk and position policy
Define max daily loss, per-trade risk, contract limits, volatility targeting, stop-out logic, kill switch, news/event restrictions, drawdown response, and portfolio concentration before optimizing alpha.

# Simple robust baselines before ML
Start with simple trend/mean-reversion/order-flow/volatility-regime baselines. ML is useful only after data, labels, costs, validation, and risk controls are correct. Carr and López de Prado explicitly warn that repeated historical calibration contributes to backtest overfitting: Determining Optimal Trading Rules without Backtesting.

# Production controls
A prop-level system has audit logs, reproducible configs, paper/live comparison, monitoring, sanity checks, stale-data guards, order throttles, self-match prevention, and emergency shutdown. CME documents self-match prevention and related order-control behavior: CME Self-Match Prevention. Algorithmic trading controls are a distinct professional concern: Nine Challenges in Modern Algorithmic Trading and Controls.

# For Your Project
Your trading knowledge should drive hypotheses; the code should enforce discipline. In this repo, the practical next priority is to finish/verify raw futures data coverage and instrument metadata before trusting evaluate_predictions.py results. Model selection comes after target construction, leakage checks, walk-forward splits, purge/embargo, and cost modeling are verified.

# Best reading order:
Larry Harris, Trading and Exchanges
Barry Johnson, Algorithmic Trading and DMA
Marcos López de Prado, Advances in Financial Machine Learning
Robert Pardo, The Evaluation and Optimization of Trading Strategies
Ernest Chan, Algorithmic Trading
Robert Carver, Systematic Trading
Perry Kaufman, Trading Systems and Methods