# Phase 1B Manifest Reconciliation

This note reconciles a stale Phase 1B manifest with the later raw-readiness and
Phase 2 finalization evidence. Do not use the old Phase 1B manifest alone to
claim global Phase 1B cleanliness.

## Stale Manifest

- Manifest: `reports/phase1B_definition_provenance_rebuild_20260624/raw_parquet_manifest.json`
- Generated at: `2026-06-24T07:14:34.098723+00:00`
- Root inputs: `data/dbn/ohlcv_1m`
- Raw root: `data/raw`
- Output rows: `532`
- Status counts: `525 ok`, `7 convert_error`

The `convert_error` rows are stale for finalized data-phase readiness. They must
be reconciled against the later Phase 1C raw-readiness report and Phase 2
finalization manifests before being treated as blockers.

## Current Authority

- Raw readiness: `reports/raw_ingest/raw_dbn_alignment.json`
- Generated at: `2026-06-24T08:04:59.255449+00:00`
- Status: `PASS`
- `missing_raw_count=0`
- `needs_phase1b_conversion_count=0`
- `missing_ohlcv_dbn_count=0`
- `missing_definition_dbn_count=0`
- `missing_status_dbn_count=0`
- `missing_statistics_dbn_count=0`

Finalized Phase 2 evidence is under
`reports/phase2_finalized_canonical_write_20260625T203537Z/`. The candidate
manifest used for finalization explicitly excludes the fail-closed rows listed
below where applicable.

## Seven Row Classification

| Market | Year | Old Phase 1B status | Current classification |
| --- | ---: | --- | --- |
| `6M` | 2026 | `convert_error` | Out of `tier_3_research`; 2026 is forward scope. Current raw metrics exist in Phase 1C and show no invalid timestamps, duplicate timestamps, bad OHLC rows, or negative volume rows. |
| `NG` | 2017 | `convert_error` | Superseded by current Phase 1C raw readiness and explicitly excluded/fail-closed by Phase 2 finalization. |
| `SR3` | 2018 | `convert_error` | Superseded by current Phase 1C raw readiness and explicitly excluded/fail-closed by Phase 2 finalization. |
| `ZC` | 2016 | `convert_error` | Superseded by current Phase 1C raw readiness and explicitly excluded/fail-closed by Phase 2 finalization. |
| `ZL` | 2010 | `convert_error` | Current Phase 1C classifies this as a `pre_availability` exemption; no raw file is required. |
| `ZM` | 2010 | `convert_error` | Current Phase 1C classifies this as a `pre_availability` exemption; no raw file is required. |
| `ZS` | 2010 | `convert_error` | Superseded by current Phase 1C raw readiness and explicitly excluded/fail-closed by Phase 2 finalization. |

## Audit Rule

For data-phase status claims, prefer the later raw-readiness report
`reports/raw_ingest/raw_dbn_alignment.json` plus this reconciliation note over
the older Phase 1B manifest. The old manifest remains useful as historical
provenance for successful rows, but its seven `convert_error` rows are not
current blockers for the finalized data phase.
