# Feature Hypothesis Registry

This directory tracks feature research status before any WFA run consumes a
feature set.

Statuses:

- `CANDIDATE`: pre-registered idea, not tested.
- `DISCOVERY_PASS`: passed discovery gates only.
- `CONFIRMATION_PASS`: passed discovery and untouched confirmation gates.
- `FROZEN`: approved for WFA through a frozen feature-set manifest.
- `REJECTED`: failed registered gates.
- `RETIRED`: previously approved but no longer active.
- `QUARANTINED`: blocked by leakage, provenance, or data-integrity risk.

Only `FROZEN` entries may set `wfa_allowed: true`.

Files:

- `registry.json`: current hypothesis status table.
- `trial_statuses.jsonl`: append-only status/event ledger.

Validate before WFA:

```powershell
python -m scripts.phase9_research.feature_hypothesis_registry
```

Register a new candidate without hand-editing JSON:

```powershell
python -m scripts.phase9_research.feature_hypothesis_registry register-candidate `
  --hypothesis-id example_candidate `
  --description "One sentence pre-registered hypothesis." `
  --feature-family example_family `
  --markets ES,CL,ZN,6E `
  --years 2023,2024
```
