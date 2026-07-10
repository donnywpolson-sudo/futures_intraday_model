# Prop Rule Configs

These files define prop-firm account constraints for trading-model simulations.

Use the YAML rule file as an account constraint layer:

```text
Trade PnL
-> PA rule checks
-> DLL/EOD threshold outcomes
-> payout eligibility
-> payout request simulation
-> usable balance update
-> PA active/paused/closed/completed status
```

For prop accounts, do not treat the headline account size as true cash capital.
For the Apex 50K EOD PA account, the model should treat the initial usable risk
budget as the drawdown budget, not as personal cash:

```text
nominal starting balance: 50000
initial fail level: 48000
initial practical risk budget: 2000
initial daily loss cap: 1000
threshold lock balance: 52100
locked EOD threshold: 50100
safety net: 52100
minimum balance to request first payout: 52600
maximum approved payouts: 6
```

Primary files:

```text
configs/prop_rules/apex_50k_eod_pa_2026-07-03.yaml
configs/report_schema/prop_backtest_report.yaml
```

Keep one dated rule file per account type. If Apex changes its rules, add a new
dated file instead of overwriting the old one so older backtests stay
reproducible.
