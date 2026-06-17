# Visual Reports

`scripts/build_metric_visualizations.py` builds a static diagnostic dashboard
from the Phase 0 report inventory. It does not change model logic, labels,
features, WFA, data generation, configs, or trading assumptions.

Run:

```powershell
python scripts/build_metric_visualizations.py --reports-dir reports --out-dir reports/visualizations --inventory reports/report_inventory.json
```

Quick root launch:

```powershell
.\ZZ_OPEN_DASHBOARD.cmd
```

The root launcher uses `--fast`, which rebuilds the dashboard from current
saved reports and skips heavy locked prediction-parquet diagnostics so it opens
quickly. Use the full command above when you want score, lifecycle, and other
prediction-derived diagnostics refreshed.

Outputs:

- `reports/visualizations/dashboard.html`
- `reports/visualizations/charts/*.png`
- `reports/visualizations/visualization_manifest.json`
- `reports/visualizations/dashboard_metric_contract.json`
- `reports/visualizations/dashboard_metric_audit.md`

Dashboard sections:

1. Run identity/provenance
2. Promotion verdict
3. Alpha evidence
4. Risk/cost realism
5. Attribution
6. Signal quality
7. Policy/blocker diagnostics
8. Trade lifecycle
9. Label/data integrity
10. Deterministic next-action recommendations

The dashboard keeps the Phase 0 source-of-truth report list as its input
contract, then derives additional diagnostics from the locked OOS prediction
parquet when available. It does not run WFA or Phase 8.

Important naming rules:

- `trade_count` from Phase 8 is displayed as `active_signal_rows`.
- `long_count` and `short_count` are displayed as positioned rows.
- lifecycle entries/exits/flips are reconstructed diagnostics, not the source
  of the existing Phase 8 costed PnL.
- raw blocker counts are labeled non-exclusive; exclusive blocker counts use a
  documented deterministic priority.
- zero-trade markets are separated from losing markets.
- `net_sharpe_like` is demoted to a bar-level sample-scaled diagnostic;
  annualized daily Sharpe and Sortino are separate derived metrics.

Skipped charts are intentionally listed in the dashboard and manifest:

- equity curve / cumulative PnL
- live execution/fill/slippage dashboard
- Tier 3/full-universe dashboard
- final holdout dashboard

The dashboard whitelists source files from `reports/report_inventory.json`.
It does not blindly scan `reports/`, does not read saved predictions, and does
not run WFA or Phase 8. It may read the locked OOS prediction parquet named by
the WFA manifest to derive dashboard-only diagnostics. Missing optional fields
produce warnings instead of crashes. Use `--strict` to fail when inventory
source-of-truth files are missing.

How to read the dashboard:

1. Start with promotion verdict and alpha evidence. Negative gross or net means
   the run is rejected as alpha proof.
2. Use risk/cost, attribution, signal quality, and policy/blocker sections to
   diagnose whether failure is signal, costs, concentration, policy, or data.
3. Use trade lifecycle only as a diagnostic until execution/cost accounting is
   changed to lifecycle-level costs.
4. Use missing evidence to decide which upstream diagnostic artifact is needed
   before another dashboard claim can be made.

Current missing-evidence categories are staged:

- research-stage blockers: benchmark controls, bootstrap confidence intervals,
  pre-registered feature/label WFA-readiness proof,
  purge/embargo/leakage dashboard evidence, and prop-style loss-limit stress
  proxies.
- future-stage evidence: live fills/latency/capacity, final holdout evidence,
  and full prop-firm execution realism. These are intentionally deferred while
  the project is still in research.

The visuals are diagnostic only. They are not executable PnL, live trading
evidence, model promotion evidence, or a substitute for locked validation.
