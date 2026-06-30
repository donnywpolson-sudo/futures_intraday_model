# Audit Readiness Packet

Status date: 2026-06-30

This packet stabilizes the project baseline for deciding whether a formal data
audit may begin. It is not a data audit and does not approve data mutation,
cleanup, provider downloads, Phase 2 rebuilds, modeling, WFA, metrics,
predictions, promotion, or live-trading readiness.

## Scope Decision

Formal audit readiness is approved only for the raw/source layer:

- In scope: `data/dbn`, `data/raw`, DBN sidecar manifests, source hashes, raw
  schema/value checks, optional status/statistics raw enrichment posture, and
  raw/source lineage reports.
- Out of scope: `data/causally_gated_normalized`, labels, feature matrices,
  predictions, models, WFA, Phase 8 metrics, promotion gates, cleanup, and
  live/paper execution.
- Raw plus causal Phase 2 is not ready for formal audit authorization because
  current canonical Phase 2 coverage is incomplete and conflicts with older
  generated evidence.

Decision: `CONDITIONAL_GO_RAW_SOURCE_ONLY`.

## Verified Facts

- Source control is active; `git rev-parse --is-inside-work-tree` returned
  `true` during the readiness review.
- The worktree remains dirty with pre-existing code, config, report, and test
  changes outside this documentation stabilization scope.
- Deleted tracked docs were restored before this packet was written:
  `PIPELINE.md`, `README_RUNBOOK.md`, `DATA REBUILD.md`, `RESOURCES.md`, and
  the tracked `docs/*` files.
- `reports/data_manifest/master_data_health_summary.md` reports:
  - expected market/year rows: `527`
  - `raw_parquet_present`: `527/527`
  - `ohlcv_1m_dbn_present`: `527/527`
  - `definition_dbn_present`: `527/527`
  - `statistics_dbn_present`: `527/527`
  - `status_dbn_present`: `460/527`; current optional audit has a separate
    status archive scope
  - `causal_parquet_present`: `8/527`
  - accepted rows still requiring pre-build raw evidence: `0`
- `reports/raw_ingest/raw_dbn_alignment.md` reports status `PASS`, full audit
  completeness, expected market-years `461`, raw market-years `530`, invalid
  manifests `0`, raw schema/value failures `0`, source hash mismatches `0`, and
  definition join mismatches `0`.
- `reports/raw_readiness/raw_enriched_optional_schema_audit.md` reports status
  `PASS`, files `530`, rows `130086009`, schema signatures `1`, duplicate key
  rows `0`, source hash mismatches `0`, and alpha input readiness
  `LIMITED_RESEARCH_INPUT_ONLY`.
- `reports/data_lineage/pipeline_phase_io_map.md` maps the implemented raw
  pipeline as Phase 1A DBN download, Phase 1B raw parquet conversion, Phase 1C
  raw readiness reports, and Phase 2 causal base.

## Inferences

- The raw/source layer has enough local evidence to begin a formal raw/source
  audit after the current documentation baseline is accepted.
- The broader raw+causal Phase 2 dataset is not audit-ready because the current
  master health summary reports only `8/527` canonical causal parquet rows and
  explicitly records stale prior causal coverage evidence.
- Optional status/statistics fields may support audit context, but direct
  alpha-feature use still requires a separate leakage-safe feature design.

## Assumptions

- A formal data audit here means a reproducible review of source inventory,
  raw preservation, schema/value checks, source hashes, metadata capture,
  timestamp handling, and raw/source lineage.
- Generated reports under `reports/**` are evidence inputs, not artifacts to
  refresh or stage in this stabilization phase.
- Any future raw+causal Phase 2 audit will be planned as a separate gate after
  canonical causal coverage and stale evidence conflicts are reconciled.

## Stale Or Conflicting Evidence Policy

- Use `reports/data_manifest/master_data_health_summary.md` as the current
  summary for audit-readiness posture.
- Treat prior generated reports that claim much higher causal coverage as stale
  unless reconciled against current filesystem evidence and current health
  summaries.
- Preserve separate evidence scopes rather than merging counts: for example,
  row-level matrix `status_dbn_present` and optional-schema audit
  `status_archive_market_year_count` are not interchangeable.

## Required Before Starting Formal Raw/Source Audit

1. Accept or commit the documentation baseline that restores tracked docs and
   adds this packet.
2. Record the exact `git status --short` output as the audit baseline.
3. Confirm that the audit scope remains raw/source only.
4. Run only narrow readiness checks; do not refresh generated data or reports
   unless separately approved.

## Narrow Readiness Checks

Recommended checks after this packet is accepted:

```powershell
git status --short
Test-Path PIPELINE.md
Test-Path docs
rg -n "audit_readiness_packet|PIPELINE.md|raw/source|Phase 2" README.md PIPELINE.md README_RUNBOOK.md docs
python -m pytest tests/validation/test_refresh_master_data_health_matrix.py tests/validation/test_audit_raw_dbn_alignment.py -q
```

Stop if a command would mutate `data/**`, `data/dbn/**`, `data/raw/**`,
`configs/data_manifest.yaml`, generated reports, models, predictions, WFA
outputs, provider state, cleanup targets, staging, commits, or promotion
state.

## Current Authorization

- Raw/source formal audit: conditional go after baseline acceptance.
- Raw+causal Phase 2 formal audit: no-go.
- Modeling, WFA, metrics, promotion, predictions, live/paper execution: no-go.
