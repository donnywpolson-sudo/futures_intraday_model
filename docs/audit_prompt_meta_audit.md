# Databento Audit Automation Meta-Audit

| Issue | Severity | Affected phase | Fix implemented in this automation | Remaining risk |
|---|---|---|---|---|
| Manual multi-prompt audit flow can skip gates or reuse stale state. | Severe | All | Single runner writes per-phase gates and `audit_state.json`. | Later phases still need careful review before full scans. |
| Phase names can drift across prompts. | Severe | All | Phase map is fixed in `configs/audit/databento_audit_plan.yaml` and runner help. | Future edits must preserve the exact phase map. |
| Source data mutation would invalidate audit evidence. | Severe | All data-scanning phases | Source manifest before/after files and mutation check are written under `reports/data_audit/state`. | Content-only changes can evade size/mtime checks if timestamps are preserved until hashes are enabled. |
| Phase 6 quarantine wording could imply action. | Severe | Phase 6 | Phase 6 is defined as quarantine plan only, no execution. | Separate explicit approval would be required for any future quarantine action. |
| OHLCV no-trade convention can be misread as missing data. | Medium | Phase 3 | Phase 3 policy says no raw OHLCV record is required for no-trade minutes. | Reconstruction still depends on overlap with locally available trades. |
| `statistics` can be misused as OHLCV. | Severe | Phase 2-3 | Runner phase policy treats `statistics` as metadata/enrichment only, never OHLCV bars. | Future source-validity code must keep this invariant. |
| Bid/ask/book checks can wander beyond available schemas. | Medium | Phase 2-3 | MBP/MBO/quote/book checks stay disabled unless such schemas are explicitly discovered and requested. | Schema discovery must remain conservative. |
| Overbroad write permissions could mutate protected data. | Severe | All | Implementation confines writes to audit scripts/configs/docs/tests and `reports/data_audit/**`. | External commands outside runner remain governed by repo rules. |
| Report schemas can be underspecified. | Medium | All | Gates use a fixed minimum schema and blockers CSV path. | Later phase-specific schemas should stay additive. |
| Heavy scans could run accidentally. | Severe | Phase 2-3 | Full scans require `--allow-full-scan`; Phase 2/3 support sampled-first policy. | Operator still controls requested command line. |

