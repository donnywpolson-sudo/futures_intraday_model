# Databento Audit Runner

`scripts/databento_audit_runner.py` is a read-only staged audit runner for local
Databento futures data. It writes audit reports under `reports/data_audit` and
does not mutate `data/**`.

Phase map:

- Phase 0: folder triage
- Phase 1: raw DBN inventory
- Phase 2: sampled/raw source validity audit
- Phase 3: OHLCV-from-trades reconstruction
- Phase 4: derived lineage and raw-vs-derived audit
- Phase 5: final model-readiness gate
- Phase 6: quarantine plan only, no execution

Phase 6 is planning only. It must not move, delete, rename, archive, rewrite, or
regenerate data.

