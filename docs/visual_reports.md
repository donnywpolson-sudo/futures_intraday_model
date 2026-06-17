# Visual Reports

`scripts/build_metric_visualizations.py` builds a static diagnostic dashboard
from the Phase 0 report inventory. It does not change model logic, labels,
features, WFA, data generation, configs, or trading assumptions.

Run:

```powershell
python scripts/build_metric_visualizations.py --reports-dir reports --out-dir reports/visualizations --inventory reports/report_inventory.json
```

Outputs:

- `reports/visualizations/dashboard.html`
- `reports/visualizations/charts/*.png`
- `reports/visualizations/visualization_manifest.json`

Supported dashboard sections are limited to the Phase 0 feasible source files:

- executive summary
- alpha research scorecard
- locked Tier 1 costed OOS gross/cost/net chart
- net return by market
- cost components
- trade activity / directional balance
- policy blocker counts
- promotion gate blockers
- artifact provenance/readiness
- feature and target hypothesis statuses
- Phase 9 stopped/rejected branch summary
- research/code response guide
- skipped and unavailable metrics

Skipped charts are intentionally listed in the dashboard and manifest:

- equity curve / cumulative PnL
- live execution/fill/slippage dashboard
- Tier 3/full-universe dashboard
- final holdout dashboard

The dashboard whitelists source files from `reports/report_inventory.json`.
It does not blindly scan `reports/`, does not read saved predictions, and does
not run WFA or Phase 8. Missing optional fields produce warnings instead of
crashes. Use `--strict` to fail when inventory source-of-truth files are
missing.

How to read the dashboard:

1. Start with the alpha research scorecard. Negative net after costs,
   negative gross before costs, high cost drag, failed promotion, or failed
   provenance means the branch should not advance.
2. Use cost, trade activity, and policy blocker charts to separate signal
   failure, cost/turnover failure, policy transformation failure, and
   provenance failure.
3. Use hypothesis and Phase 9 sections to avoid re-testing rejected branches or
   treating stopped feasibility work as a direction-model input.
4. Treat skipped and unavailable metrics as diagnostics to build later, not as
   hidden evidence. Equity curves, fold/year/hour concentration, live fills,
   latency, capacity, and final-holdout charts require their own
   source-of-truth artifacts before visualization.

The visuals are diagnostic only. They are not executable PnL, live trading
evidence, model promotion evidence, or a substitute for locked validation.
