# Codex Handoff

- Updated at UTC: 2026-06-24T02:48:41Z
- Purpose: current-state handoff after refreshing non-DBN-mutating Phase 1B/1C readiness evidence following the partial 2010 status repair.
- Repo: `C:\Users\donny\Desktop\futures_intraday_model`

## Current Status

- User policy decision: Phase 1A now means all L0 DBN schemas are complete, including `status`.
- Phase 1A status under this definition: not complete. Current archive coverage evidence shows `missing_archives=55`, `missing_manifests=55`, and `invalid_manifests=0`.
- Code status: Phase 1A required schemas are now `ohlcv-1m`, `definition`, `statistics`, and `status` in `scripts/phase1_raw_contract.py`; `scripts/validation/check_dbn_archive_coverage.py` defaults to those schemas and rejects marking any of them optional.
- User policy decision: Phase 1B readiness means convert/combine Phase 1A downloads into raw market-year parquet, with each `tier_3_research` market-year having complete raw parquet data for the four L0 schemas: `ohlcv-1m`, `status`, `definition`/`definitions`, and `statistics`, matching the downloaded Phase 1A DBN data.
- Code status: `scripts/phase1B_convert/convert_databento_raw.py` now defaults Phase 1B conversion to `--include-optional-schemas status,statistics` and `--optional-schema-policy require` when those args are not explicitly provided.
- Code status: Phase 1B pre-conversion DBN gate now enforces required `status` and `statistics` archives when `--optional-schema-policy require` is active, so strict conversion fails before per-file conversion if four-L0 DBN inputs are incomplete.
- Code status: Phase 1C raw/DBN alignment now indexes required `status` and `statistics` DBNs, validates their manifests, reports missing metadata DBN counts, and fails when four-L0 DBN alignment is incomplete.
- Phase 1B status under this definition: not complete. Refreshed strict raw enriched audit report shows `status=FAIL`, `files=527`, `rows=130074125`, `file_failure_count=55`, `missing_status_archive_market_year_count=55`, `status_failure_count=55`, `missing_statistics_archive_market_year_count=0`, and `statistics_failure_count=0`.
- Phase 1C status under the four-L0 definition: not complete. Refreshed partial raw/DBN alignment report shows `status=FAIL`, `expected=461`, `raw=527`, `missing_status_dbn_count=55`, `missing_statistics_dbn_count=0`, `needs_phase1b_conversion_count=0`, `raw_only_count=55`, `invalid_manifest_count=0`, and `source_hash_mismatch_count=0`.
- Active next scope: get explicit approval to continue the remaining four parent-symbol `status` zero-cost repair commands with a longer command timeout. The approved sequence stopped after the first command exited with timeout `124`.
- Missing Phase 1A `status` DBN market-years grouped by year after the 2010 parent-symbol partial repair:
  - `2011`: `6C,HG,HO,LE,RB,UB,YM,ZB,ZF,ZM,ZN,ZS,ZT`
  - `2012`: `6E,HO,LE,NQ,RB,UB,YM,ZB,ZF,ZL,ZM,ZN,ZT`
  - `2013`: `6E,6M,HE,HO,KE,LE,RB,YM,ZL,ZM,ZS,ZT,ZW`
  - `2014`: `6A,6B,6C,6E,6J,6M,ES,GC,HG,NQ,RB,SI,YM,ZC,ZM,ZT`
- Existing `status` manifests use `schema=status`, `stype_in=continuous`, `stype_out=instrument_id`, and paths under `data/dbn/status/{market}/{year}/{start}_{end}.dbn.zst`.
- Missing-status dry-run verification passed:
  - Dry-run plan files: `reports/phase1A_status_repair_20260624/{2010,2011,2012,2013,2014}/databento_download_plan_dry_run.json`.
  - Task counts by year: `2010=12`, `2011=13`, `2012=13`, `2013=13`, `2014=16`, total `67`.
  - Planned unique market-years: `67`.
  - Bad schema count: `0`; all planned tasks use `schema=status`.
  - Bad output path count: `0`; all planned outputs target `data/dbn/status/...`.
  - Exact set comparison against `reports/raw_readiness/raw_enriched_optional_schema_audit.json`: `audit_missing=67`, `planned=67`, `missing_not_planned=0`, `planned_not_missing=0`.
- Latest read-only Phase 1A archive coverage check still fails: `status=FAIL expected_archives=1844 missing_archives=67 missing_manifests=67 missing_optional_archives=0 missing_optional_manifests=0 invalid_manifests=0 extra_market_dirs=0`.
- Repeated approval-boundary recheck still fails with the same result: `status=FAIL expected_archives=1844 missing_archives=67 missing_manifests=67 missing_optional_archives=0 missing_optional_manifests=0 invalid_manifests=0 extra_market_dirs=0`.
- Approved repair attempt status before the gate fix: stopped on the first batch. The 2010 continuous-symbol `status` command passed `ZERO_COST_GATE status=PASS downloadable=12 billable_size=0`, then exited `1` after all 12 selected tasks returned `422 data_no_data_found_for_request`.
- Zero-size gate fix: `scripts/phase1A_download/download_databento_raw.py` now treats exact-zero-cost estimates with `billable_size=0` as provider-empty blockers, not downloadable DBN archives. The CLI prints `provider_empty=<count>` in zero-cost gate summaries.
- Refreshed 2010 continuous-symbol gate evidence: `reports/phase1A_status_repair_20260624/2010/databento_zero_cost_gate.json` now shows `status=FAIL`, `downloadable_zero_cost_task_count=0`, `provider_empty_estimate_count=12`, `selected_task_count=0`.
- Revised 2010 parent-symbol estimate-only probe: `reports/phase1A_status_repair_20260624/probe_parent_2010/databento_zero_cost_gate.json` shows `status=PASS`, `downloadable_zero_cost_task_count=12`, `provider_empty_estimate_count=0`, `zero_cost_billable_size=141320`. This indicates the 2010 blocker is request semantics (`continuous` status no-data), not provider absence for `status` itself.
- Parent-symbol estimate-only probes for the remaining missing `status` batches:
  - `probe_parent_2011`: `status=PASS`, `downloadable=13`, `provider_empty=0`, `billable_size=217400`.
  - `probe_parent_2012`: `status=PASS`, `downloadable=13`, `provider_empty=0`, `billable_size=144240`.
  - `probe_parent_2013`: `status=FAIL`, `downloadable=12`, `provider_empty=1`, `billable_size=223760`; only provider-empty estimate is `KE 2013`.
  - `probe_parent_2013_no_ke`: `status=PASS`, `downloadable=12`, `provider_empty=0`, `billable_size=223760`.
  - `probe_parent_2014`: `status=PASS`, `downloadable=16`, `provider_empty=0`, `billable_size=239200`.
- `KE 2013 status` provider-empty evidence: parent-symbol probe has `billable_size=0`, continuous-symbol probe under `reports/phase1A_status_repair_20260624/probe_continuous_KE_2013/` also has `status=FAIL`, `downloadable=0`, `provider_empty=1`, `billable_size=0`. Local `KE 2013` `ohlcv-1m`, `definition`, and `statistics` manifests exist; the gap is status-specific.
- Approved repair execution status: the first parent-symbol repair command (`parent_2010`) exited with timeout `124` after 600 seconds, so the remaining four repair commands were not run. Read-only inspection showed `reports/phase1A_status_repair_20260624/parent_2010/databento_download_results.json` contains 12 records, all `status=ok`, all `schema=status`, all `stype_in=parent`, products `6C,6J,GC,HO,LE,RB,UB,ZB,ZC,ZF,ZN,ZT`, and `total_bytes=68405`.
- Current Phase 1A archive coverage after the 2010 parent-symbol repair attempt: `status=FAIL expected_archives=1844 missing_archives=55 missing_manifests=55 missing_optional_archives=0 missing_optional_manifests=0 invalid_manifests=0 extra_market_dirs=0`.
- Professional end-state wording: "Complete the `tier_3_research` research pipeline from validated four-schema L0 Databento `.dbn.zst` archives (`ohlcv-1m`, `definition`, `statistics`, `status`) for every configured market-year, through source-matched raw market-year parquet, raw/DBN provenance validation, normalized causal-gated parquet, leakage-safe labels/features, purged walk-forward splits, train-only WFA predictions, cost-aware Phase 8 model/policy evaluation, and Phase 9 hypothesis/robustness gates with manifests, hashes, row counts, warnings, and failures recorded at every stage."
- Missing from the user's raw-to-complete wording: explicit manifests/hashes, raw/DBN alignment, as-of joins for definitions/status/statistics, session/calendar/roll/tick/cost assumptions, causal gating, leakage checks, target timing, purge/embargo, locked holdout/forward separation, generated artifact hygiene, WFA prediction evidence, Phase 8 cost/selection gates, and Phase 9 hypothesis registry/robustness evidence.
- Latest approved Phase 2 evidence:
  - Inputs/evidence roots: `data/causally_gated_normalized/_bounded_phase2_58_20260623` and `reports/phase_restart/bounded_phase2_58_20260623`.
  - Output membership at last review: expected `58`, actual `58`, missing `0`, extra `0`.
  - Deferred rows present in bounded outputs: `0`.
  - Manifest output path issues: `0`.
  - Scoped config status at last review showed no changes to `configs/data_manifest.yaml` or `configs/alpha_tiered.yaml`.
- Batch validation status at last review:
  - `KE`: `WARN`, rows `PASS=4 WARN=8 FAIL=0`, warnings `8`, failures `0`; warning category `roll maturity sequence not monotonic=8`.
  - `SR1`: `WARN`, rows `PASS=0 WARN=9 FAIL=0`, warnings `12`, failures `0`; warning categories `roll maturity sequence not monotonic=9`, `roll exclusion threshold breached=3`.
  - `TN`: `PASS`, rows `PASS=11 WARN=0 FAIL=0`, warnings `0`, failures `0`.
  - `ZL`: `WARN`, rows `PASS=7 WARN=7 FAIL=0`, warnings `7`, failures `0`; warning category `roll maturity sequence not monotonic=7`.
  - `ZM`: `WARN`, rows `PASS=4 WARN=8 FAIL=0`, warnings `8`, failures `0`; warning category `roll maturity sequence not monotonic=8`.
- Interpretation: the bounded packet is approved for downstream Phase 3 planning only. `WARN` batches are accepted caveats with zero failures, not clean `PASS`.

## Important Prior Evidence

- Phase 2 readiness accepted-exception fail-fast fix was made in `scripts/phase2_causal_base/build_causal_base_data.py`; focused regression result at the time: `1 passed, 69 deselected`.
- Bounded readiness-only later passed for all five batches: `KE=12`, `SR1=9`, `TN=11`, `ZL=14`, `ZM=12`, total `58`, with `pending=0`, `blockers=0`, `failures=0`.
- Bounded Phase 2 build commands exited `0` for `KE`, `SR1`, `TN`, `ZL`, and `ZM`; generated 58 causal parquet outputs under `data/causally_gated_normalized/_bounded_phase2_58_20260623`.
- Phase 1C trades-derived raw provenance policy fix was made in `scripts/phase1C_validate/audit_raw_dbn_alignment.py`; focused validation at the time: `27 passed in 3.06s`; broad Phase 1C refresh status: `PASS`, expected `461`, raw `527`, needs Phase 1B `0`, raw-only `0`, invalid manifests `0`, source hash mismatches `0`.
- Current L0 DBN schema presence from `reports/data_manifest/master_data_health_summary.md`: `ohlcv_1m=527/527`, `definition=527/527`, `statistics=527/527`, `status=460/527`.
- Raw enriched schema audit is now strict for Phase 1B four-L0 readiness. Current result: `status=FAIL`, `core_raw_readiness=PASS`, `optional_status_readiness=FAIL`, `optional_statistics_readiness=PASS`, `file_failure_count=67`, `missing_status_archive_market_year_count=67`, `status_failure_count=67`.
- Current Phase 1B evidence from `reports/data_manifest/master_data_health_summary.md` and `reports/raw_readiness/raw_enriched_optional_schema_audit.json`: `raw_parquet_present=527/527`, `file_count=527`, `row_count=130074125`, `schema_failure_count=0`, `source_hash_mismatch_count=0`; this is not sufficient for the new Phase 1B definition until `status` is complete for all `tier_3_research` market-years.
- WFA prediction evidence remains separate and stale: `data/predictions` had `0` files and 24 historical `reports/wfa/*_predictions_manifest.json` references were missing current prediction parquet evidence. Do not treat those as current WFA evidence without a separately approved regeneration.
- Live-ops docs remain not production-live ready. Previously recorded closeout evidence: focused live-ops/chart validation `71 passed`, smoke CLI `PASS live trading smoke scenarios=34 decision_cycles=34 audit_rows=34`, broad bounded pytest `732 passed, 58 warnings`.

## Files Changed

- This run changed:
  - `scripts/phase1_raw_contract.py`
  - `scripts/validation/check_dbn_archive_coverage.py`
  - `tests/phase1A_download/test_download_databento_raw.py`
  - `tests/validation/test_check_dbn_archive_coverage.py`
  - `CODEX_HANDOFF.md`
- This wording/gap-map pass changed only `CODEX_HANDOFF.md`.
- This missing-status command-plan pass changed only `CODEX_HANDOFF.md`.
- This missing-status dry-run pass changed only `CODEX_HANDOFF.md` in tracked files. Dry-run JSON reports were generated under ignored `reports/phase1A_status_repair_20260624/`.
- This approval-boundary recheck changed only `CODEX_HANDOFF.md`.
- This repeated approval-boundary recheck changed only `CODEX_HANDOFF.md`.
- This approved repair attempt changed `CODEX_HANDOFF.md` and generated ignored reports under `reports/phase1A_status_repair_20260624/2010/`. It did not complete the first status batch.
- This zero-size gate repair changed `scripts/phase1A_download/download_databento_raw.py`, `tests/phase1A_download/test_download_databento_raw.py`, and `CODEX_HANDOFF.md`. It generated ignored refreshed/probe reports under `reports/phase1A_status_repair_20260624/`.
- This parent-probe pass changed only `CODEX_HANDOFF.md` in tracked files. It generated ignored estimate-only reports under `reports/phase1A_status_repair_20260624/probe_parent_2011`, `probe_parent_2012`, `probe_parent_2013`, `probe_parent_2013_no_ke`, `probe_parent_2014`, and `probe_continuous_KE_2013`.
- This continuation pass changed only `CODEX_HANDOFF.md`; no DBN/source/raw mutation was performed because the current user message did not explicitly approve the five parent-symbol repair commands.
- This Phase 1B strict-readiness pass changed `scripts/validation/audit_enriched_raw_optional_schemas.py`, `tests/validation/test_audit_enriched_raw_optional_schemas.py`, and `CODEX_HANDOFF.md`. It refreshed ignored/raw-readiness reports but did not mutate DBN/source/raw data.
- This Phase 1B wrapper-default pass changed `scripts/phase1B_convert/convert_databento_raw.py`, `tests/phase1A_download/test_download_databento_raw.py`, and `CODEX_HANDOFF.md`.
- This Phase 1B pre-conversion gate pass changed `scripts/phase1A_download/download_databento_raw.py`, `tests/phase1A_download/test_download_databento_raw.py`, and `CODEX_HANDOFF.md`. It refreshed ignored/raw-readiness reports but did not mutate DBN/source/raw data.
- This Phase 1C four-L0 alignment pass changed `scripts/phase1C_validate/audit_raw_dbn_alignment.py`, `tests/validation/test_audit_raw_dbn_alignment.py`, and `CODEX_HANDOFF.md`. It refreshed ignored/raw-ingest reports but did not mutate DBN/source/raw data.
- This Phase 1A parent-symbol repair execution changed `CODEX_HANDOFF.md` in tracked files and generated/updated ignored data/report artifacts under `data/dbn/status/{6C,6J,GC,HO,LE,RB,UB,ZB,ZC,ZF,ZN,ZT}/2010/` and `reports/phase1A_status_repair_20260624/parent_2010/`.
- This continuation pass changed only `CODEX_HANDOFF.md` in tracked files. It refreshed ignored reports under `reports/raw_readiness/` and `reports/raw_ingest/`, but did not mutate DBN/source/raw data or run downloads.
- Pre-existing dirty files preserved:
  - `.gitignore`
  - `scripts/phase1C_validate/audit_raw_dbn_alignment.py`
  - `scripts/phase2_causal_base/build_causal_base_data.py`
  - `tests/phase2_causal_base/test_build_causal_base_data.py`
  - `tests/validation/test_audit_raw_dbn_alignment.py`
  - `codex-local.ps1`
- No staging, commit, generated artifact preservation, cleanup, delete, move, DBN/source/raw mutation, Phase 3-8 run, WFA/model run, or config change was performed.

## Commands Run In This Run

- `Get-Location`
- `git status --short`
- `rg -n "futures_intraday_model|CODEX_HANDOFF|handoff" C:\Users\donny\.codex\memories\MEMORY.md`
- `Get-Content -Raw CODEX_HANDOFF.md`
- `git diff -- CODEX_HANDOFF.md`
- `rg -n "^(## |### Next recommended step|Next selected scope:|## Current selected scope|## Current Tier 1|## Current WFA|## Current SR1|## Data health|## Live-ops|## Latest run:|## Previous run:)" CODEX_HANDOFF.md`
- `Get-Content CODEX_HANDOFF.md -Tail 220`
- `Get-Date -AsUTC -Format "yyyy-MM-ddTHH:mm:ssZ"` failed because this PowerShell version lacks `-AsUTC`.
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`
- `git status --short`
- `Get-Content CODEX_HANDOFF.md -TotalCount 80`
- `(Get-Content CODEX_HANDOFF.md).Count`
- `Get-Content reports\data_manifest\master_data_health_summary.md -TotalCount 45`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`
- `rg -n "Phase 1A|phase1A|phase 1A|dbn_present|ohlcv_1m_dbn_present|definition_dbn_present|statistics_dbn_present|status_dbn_present|missing_status|downstream readiness|readiness" scripts tests configs -S`
- `Get-Content scripts\validation\check_dbn_archive_coverage.py -TotalCount 260`
- `Get-Content scripts\audit_data_manifest.py -TotalCount 280`
- `Get-Content tests\validation\test_check_dbn_archive_coverage.py -TotalCount 260`
- `Get-Content scripts\phase1_raw_contract.py -TotalCount 140`
- `python -m pytest tests/validation/test_check_dbn_archive_coverage.py tests/phase1A_download/test_download_databento_raw.py`
- `python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data/dbn`
- `rg --files scripts configs tests | rg "phase[1-9]|wfa|feature|label|causal|model|selection|prediction|promot|gate|manifest"`
- targeted reads of `configs/alpha_tiered.yaml`, `configs/models.yaml`, Phase 2/3/4/5/7/8/9 script headers/argument and manifest paths
- `Get-ChildItem -Path data\dbn\status -Recurse -Filter *.manifest.json | Select-Object -First 3 -ExpandProperty FullName`
- `Get-Content data\dbn\status\6A\2010\2010-06-06_2011-01-01.dbn.zst.manifest.json -TotalCount 80`
- PowerShell extraction from `reports\raw_readiness\raw_enriched_optional_schema_audit.json` to list and group the 67 missing `status` market-years.
- Targeted read of `scripts\phase1A_download\download_databento_raw.py` around `dbn_schema_root`, task output paths, and zero-cost gate behavior.
- Five Phase 1A missing-status `--dry-run` commands under `reports\phase1A_status_repair_20260624\{2010,2011,2012,2013,2014}`.
- `Get-ChildItem -Path reports\phase1A_status_repair_20260624 -Recurse -File`
- PowerShell verification of the five dry-run JSON plans for plan count, task counts, schema, output paths, unique planned keys, and exact set match against the 67 missing audit keys.
- `git status --short -- reports\phase1A_status_repair_20260624`
- `python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data\dbn`
- Repeated `python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data\dbn`
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6C,6J,GC,HO,LE,RB,UB,ZB,ZC,ZF,ZN,ZT --start 2010-01-01 --end 2011-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2010 --workers 4 --resume --zero-cost-only` failed in sandbox before launchable download because Databento cost checks could not reach the proxy target.
- Same 2010 command retried with scoped network approval. Zero-cost gate passed, then the command exited `1` after 12 Databento `422 data_no_data_found_for_request` download errors.
- `Get-ChildItem -Path reports\phase1A_status_repair_20260624\2010 -File | Select-Object Name,Length,LastWriteTime`
- `Get-Content reports\phase1A_status_repair_20260624\2010\databento_download_results.json -TotalCount 80`
- `Get-Content reports\phase1A_status_repair_20260624\2010\databento_zero_cost_gate.json -TotalCount 60`
- PowerShell summary of `databento_download_results.json` status counts: `download_error=12`.
- Inspected current handoff, Phase 1A readiness checker, data-manifest exception patterns, downloader zero-cost gate logic, and local 2010 status manifests.
- `python -m pytest tests/phase1A_download/test_download_databento_raw.py tests/validation/test_check_dbn_archive_coverage.py`
- Repeated after CLI summary change: `python -m pytest tests/phase1A_download/test_download_databento_raw.py tests/validation/test_check_dbn_archive_coverage.py`
- Reran the 2010 continuous-symbol zero-cost command after the gate fix. It exited `1` at the gate with `ZERO_COST_GATE status=FAIL downloadable=0 billable_size=0` and no batch submissions.
- `python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data\dbn`
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6C,6J,GC,HO,LE,RB,UB,ZB,ZC,ZF,ZN,ZT --start 2010-01-01 --end 2011-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\probe_parent_2010 --workers 1 --resume --estimate-cost --zero-cost-only`
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6C,HG,HO,LE,RB,UB,YM,ZB,ZF,ZM,ZN,ZS,ZT --start 2011-01-01 --end 2012-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\probe_parent_2011 --workers 1 --resume --estimate-cost --zero-cost-only`
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6E,HO,LE,NQ,RB,UB,YM,ZB,ZF,ZL,ZM,ZN,ZT --start 2012-01-01 --end 2013-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\probe_parent_2012 --workers 1 --resume --estimate-cost --zero-cost-only`
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6E,6M,HE,HO,KE,LE,RB,YM,ZL,ZM,ZS,ZT,ZW --start 2013-01-01 --end 2014-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\probe_parent_2013 --workers 1 --resume --estimate-cost --zero-cost-only`
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6A,6B,6C,6E,6J,6M,ES,GC,HG,NQ,RB,SI,YM,ZC,ZM,ZT --start 2014-01-01 --end 2015-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\probe_parent_2014 --workers 1 --resume --estimate-cost --zero-cost-only`
- Checked local `KE 2013` manifests for `ohlcv-1m`, `definition`, and `statistics`.
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets KE --start 2013-01-01 --end 2014-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\probe_continuous_KE_2013 --workers 1 --resume --estimate-cost --zero-cost-only`
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6E,6M,HE,HO,LE,RB,YM,ZL,ZM,ZS,ZT,ZW --start 2013-01-01 --end 2014-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\probe_parent_2013_no_ke --workers 1 --resume --estimate-cost --zero-cost-only`
- Continuation check: `python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data\dbn`
- Targeted Phase 1B readiness search/read of `scripts/validation/audit_enriched_raw_optional_schemas.py`, `tests/validation/test_audit_enriched_raw_optional_schemas.py`, `scripts/phase1C_validate/audit_raw_dbn_alignment.py`, and `scripts/audit_data_manifest.py`.
- `python -m pytest tests/validation/test_audit_enriched_raw_optional_schemas.py`
- `python -m scripts.validation.audit_enriched_raw_optional_schemas`
- `python -m pytest tests/phase1A_download/test_download_databento_raw.py tests/validation/test_audit_enriched_raw_optional_schemas.py`
- Repeated after Phase 1B pre-conversion gate change: `python -m pytest tests/phase1A_download/test_download_databento_raw.py tests/validation/test_audit_enriched_raw_optional_schemas.py`
- Repeated after Phase 1B pre-conversion gate change: `python -m scripts.validation.audit_enriched_raw_optional_schemas`
- `python -m pytest tests/validation/test_audit_raw_dbn_alignment.py` failed before fixture updates because clean two-L0 fixtures no longer satisfy the four-L0 alignment contract.
- Repeated after fixture/output updates: `python -m pytest tests/validation/test_audit_raw_dbn_alignment.py`
- `python -m scripts.phase1C_validate.audit_raw_dbn_alignment --skip-definition-join`
- `Get-Location`
- `git status --short`
- `Get-Content -Path CODEX_HANDOFF.md -TotalCount 260`
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6C,6J,GC,HO,LE,RB,UB,ZB,ZC,ZF,ZN,ZT --start 2010-01-01 --end 2011-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\parent_2010 --workers 4 --resume --zero-cost-only` timed out with exit `124` after 600 seconds.
- `Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | Format-List`
- `Get-ChildItem -Path reports\phase1A_status_repair_20260624\parent_2010 -File | Select-Object Name,Length,LastWriteTime`
- `python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data\dbn`
- PowerShell summaries of `reports\phase1A_status_repair_20260624\parent_2010\databento_download_results.json` for count/status/schema/stype/products/bytes.
- `git status --short -- data\dbn reports\phase1A_status_repair_20260624`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`
- `Get-Location`
- `git status --short`
- `Get-Content -Path CODEX_HANDOFF.md -TotalCount 280`
- `python -m scripts.validation.audit_enriched_raw_optional_schemas` printed `status=FAIL files=527 rows=130074125 core=PASS status_optional=FAIL statistics_optional=PASS file_failures=55`, but the shell call timed out with exit `124`.
- `python -m scripts.phase1C_validate.audit_raw_dbn_alignment --skip-definition-join` printed `status=FAIL expected=461 raw=527 missing_status=55 missing_statistics=0 needs_phase1b=0 raw_only=55 invalid_manifests=0 source_hash_mismatches=0 definition_join_status=skipped definition_join_mismatches=0`, but the shell call timed out with exit `124`.
- `python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data\dbn`
- `Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | Format-List`
- Read-only summaries of `reports\raw_readiness\raw_enriched_optional_schema_audit.json` and `reports\raw_ingest\raw_dbn_alignment.json`.
- `Get-Item reports\raw_readiness\raw_enriched_optional_schema_audit.json, reports\raw_ingest\raw_dbn_alignment.json | Select-Object Name,Length,LastWriteTime`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Test And Validation Results

- Current evidence verifies Phase 1A is not complete under the new all-L0-including-status definition.
- Current evidence verifies Phase 1B is not complete under the new convert/combine four-L0 definition because `status` archive coverage is `394/461` for `tier_3_research`.
- Focused validation after code change: `python -m pytest tests/validation/test_check_dbn_archive_coverage.py tests/phase1A_download/test_download_databento_raw.py` passed with `94 passed in 3.02s`.
- Current Phase 1A readiness checker result after code change: `status=FAIL expected_archives=1844 missing_archives=67 missing_manifests=67 missing_optional_archives=0 missing_optional_manifests=0 invalid_manifests=0 extra_market_dirs=0`.
- Current phase map evidence: Phase 6 is a compatibility wrapper over Phase 7 WFA; Phase 7 is the active train-only WFA prediction implementation used by current tests/reports.
- Missing `status` repair dry-run was executed and verified in this pass. No API download, cost estimate, DBN/source mutation, conversion, or Phase 3+ command was run.
- Latest read-only coverage recheck result: `status=FAIL expected_archives=1844 missing_archives=67 missing_manifests=67 missing_optional_archives=0 missing_optional_manifests=0 invalid_manifests=0 extra_market_dirs=0`.
- Repeated read-only coverage recheck result is unchanged: `status=FAIL expected_archives=1844 missing_archives=67 missing_manifests=67 missing_optional_archives=0 missing_optional_manifests=0 invalid_manifests=0 extra_market_dirs=0`.
- Approved 2010 repair command result: `ZERO_COST_GATE status=PASS downloadable=12 billable_size=0`, then `download_error=12`; each selected task returned `422 data_no_data_found_for_request`.
- Phase 1A coverage validation was not rerun after the failed repair because the approved stop condition required stopping on the first nonzero download command.
- Focused validation after the zero-size gate fix: `95 passed in 2.95s`.
- Refreshed 2010 continuous-symbol gate result after the fix: `status=FAIL`, `downloadable_zero_cost_task_count=0`, `provider_empty_estimate_count=12`, `selected_task_count=0`; no batch submissions were made.
- Current Phase 1A coverage validation remains failed: `status=FAIL expected_archives=1844 missing_archives=67 missing_manifests=67 missing_optional_archives=0 missing_optional_manifests=0 invalid_manifests=0 extra_market_dirs=0`.
- Continuation Phase 1A coverage validation remains failed with the same result: `status=FAIL expected_archives=1844 missing_archives=67 missing_manifests=67 missing_optional_archives=0 missing_optional_manifests=0 invalid_manifests=0 extra_market_dirs=0`.
- Focused Phase 1B strict-readiness tests passed: `6 passed in 1.47s`.
- Current strict raw enriched audit result: `status=FAIL files=527 rows=130074125 core=PASS status_optional=FAIL statistics_optional=PASS file_failures=67`.
- Current raw enriched audit summary: `missing_status_archive_market_year_count=67`, `status_failure_count=67`, `missing_statistics_archive_market_year_count=0`, `statistics_failure_count=0`, `source_hash_mismatch_count=0`, `schema_failure_count=0`.
- Focused Phase 1B wrapper/default and raw enriched readiness tests passed: `93 passed in 3.59s`.
- Focused Phase 1B gate/wrapper/default and raw enriched readiness tests passed: `95 passed in 3.68s`.
- Current strict raw enriched audit remains correctly failed: `status=FAIL files=527 rows=130074125 core=PASS status_optional=FAIL statistics_optional=PASS file_failures=67`.
- Current strict raw enriched audit summary remains: `missing_status_archive_market_year_count=67`, `status_failure_count=67`, `missing_statistics_archive_market_year_count=0`, `statistics_failure_count=0`, `source_hash_mismatch_count=0`, `schema_failure_count=0`.
- Focused Phase 1C four-L0 alignment tests passed after fixture updates: `27 passed in 3.24s`.
- Current partial Phase 1C raw/DBN alignment result: `status=FAIL expected=461 raw=527 missing_status_dbn_count=67 missing_statistics_dbn_count=0 needs_phase1b_conversion_count=0 raw_only_count=67 invalid_manifest_count=0 source_hash_mismatch_count=0 definition_join_status=skipped definition_join_mismatch_count=0`.
- Revised 2010 parent-symbol estimate-only probe passed: `ZERO_COST_GATE status=PASS downloadable=12 provider_empty=0 billable_size=141320`.
- Parent-symbol estimate-only repair scope now verified for 66 of 67 missing `status` market-years: `2010=12`, `2011=13`, `2012=13`, `2013_no_ke=12`, `2014=16`; all five exact repair subsets have `status=PASS`, `provider_empty=0`, and positive billable size.
- `KE 2013 status` remains provider-empty under both `parent` and `continuous` estimate-only probes.
- First approved parent-symbol repair command timed out with exit `124`, so the remaining four commands were not run. The generated `parent_2010` results file contains 12 records and all are `status=ok`, `schema=status`, `stype_in=parent`, with `bad_status=0`, `bad_schema=0`, `bad_stype=0`, `total_bytes=68405`.
- Current Phase 1A coverage validation after the `parent_2010` repair attempt: `status=FAIL expected_archives=1844 missing_archives=55 missing_manifests=55 missing_optional_archives=0 missing_optional_manifests=0 invalid_manifests=0 extra_market_dirs=0`.
- Refreshed strict raw enriched audit report after the `parent_2010` repair attempt: `status=FAIL files=527 rows=130074125 file_failure_count=55 missing_status_archive_market_year_count=55 status_failure_count=55 missing_statistics_archive_market_year_count=0 statistics_failure_count=0`.
- Refreshed partial Phase 1C raw/DBN alignment report after the `parent_2010` repair attempt: `status=FAIL expected=461 raw=527 missing_status_dbn_count=55 missing_statistics_dbn_count=0 needs_phase1b_conversion_count=0 raw_only_count=55 invalid_manifest_count=0 source_hash_mismatch_count=0`.
- Caveat: the two refreshed audit commands printed complete summaries but exited by shell timeout `124`; the JSON report files were refreshed and read successfully afterward.

## Remaining Work

- Do not treat Phase 1A as done until `status` DBN coverage is either repaired to `527/527` or the user explicitly changes the definition again.
- Do not treat Phase 1B as done until all `tier_3_research` market-year raw parquet files contain valid combined/enriched data for the four L0 schemas and match the downloaded Phase 1A DBN evidence.
- Phase 1B strict audit now fails closed on missing required `status`/`statistics` DBN coverage instead of treating status as a warning-only optional enrichment.
- Phase 1B conversion wrapper now defaults to required `status,statistics` enrichment; explicit overrides are still respected for test or diagnostic use.
- Phase 1B pre-conversion DBN gate now checks required status/statistics archives before conversion when strict mode is active.
- Phase 1C raw/DBN alignment now fails closed on missing required status/statistics DBN coverage, so it no longer reports four-L0 raw alignment as complete while `status` archives are missing.
- Do not rerun the continuous-symbol 2010 repair command; it is now proven provider-empty for these 12 market-years.
- Run the revised parent-symbol 2010 zero-cost repair command only after explicit approval because it mutates `data/dbn/status`.
- Continue the remaining four parent-symbol repair commands only after explicit approval because the approved sequence stopped on timeout `124`. Do not rerun `parent_2010` unless read-only evidence later contradicts its 12 `ok` results.
- Decide whether `KE 2013 status` should remain a severe blocker, be documented as a provider-unavailable explicit exception, or be excluded from the readiness universe. Do not silently pass Phase 1A while `KE 2013 status` is missing.
- Do not execute Phase 3, WFA/model selection, cleanup, quarantine, DBN/source/raw mutation, generated artifact staging, commits, or config changes unless explicitly approved.
- Phase 3 planning from the bounded Phase 2 packet should wait behind the Phase 1A status-coverage decision if strict all-L0 completeness is required before downstream work.
- Carry forward accepted WARN caveats for `KE`, `SR1`, `ZL`, and `ZM`; `SR1` includes roll exclusion threshold warnings.
- Keep deferred rows excluded unless separately approved: `KE:2013`, `KE:2014`, `ZL:2012`, `ZL:2013`, `ZM:2011`, `ZM:2012`, `ZM:2013`, `ZM:2014`.

## Next Recommended Step

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: user approval to continue the remaining Phase 1A `status` parent-symbol repair after the 2010 command timed out.
Rules:
- Do not run cleanup, Phase 1B conversion, Phase 2+, WFA/model selection, generated artifact staging, commits, or config changes.
- Do not rerun any old continuous-symbol repair commands.
- Do not rerun `parent_2010` unless current read-only evidence contradicts `reports/phase1A_status_repair_20260624/parent_2010/databento_download_results.json` showing 12 `ok` records.
- Do not include `KE` in the 2013 repair command; both parent and continuous estimate-only probes show `KE 2013 status` is provider-empty.
- Do not mutate DBN/source data unless the user explicitly approves the four remaining parent-symbol commands below.
- Treat Phase 1A and Phase 1B as incomplete until `python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data/dbn` passes.
- Use a longer command timeout than 600 seconds for each remaining repair command.
- Use current evidence first: `reports/phase1A_status_repair_20260624/parent_2010/databento_download_results.json`, `reports/phase1A_status_repair_20260624/probe_parent_{2011,2012,2013_no_ke,2014}/databento_zero_cost_gate.json`, and `reports/phase1A_status_repair_20260624/probe_continuous_KE_2013/databento_zero_cost_gate.json`.
Task:
- If the user approves DBN mutation, run only these four revised zero-cost commands:
  `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6C,HG,HO,LE,RB,UB,YM,ZB,ZF,ZM,ZN,ZS,ZT --start 2011-01-01 --end 2012-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\parent_2011 --workers 4 --resume --zero-cost-only`
  `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6E,HO,LE,NQ,RB,UB,YM,ZB,ZF,ZL,ZM,ZN,ZT --start 2012-01-01 --end 2013-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\parent_2012 --workers 4 --resume --zero-cost-only`
  `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6E,6M,HE,HO,LE,RB,YM,ZL,ZM,ZS,ZT,ZW --start 2013-01-01 --end 2014-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\parent_2013_no_ke --workers 4 --resume --zero-cost-only`
  `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in parent --stype-out instrument_id --markets 6A,6B,6C,6E,6J,6M,ES,GC,HG,NQ,RB,SI,YM,ZC,ZM,ZT --start 2014-01-01 --end 2015-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\parent_2014 --workers 4 --resume --zero-cost-only`
- Stop immediately if any zero-cost gate fails, any command exits nonzero, or any planned task is nonzero-cost.
- If all four commands pass, rerun `python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data\dbn`.
Stop when:
- The remaining 54 downloadable status archives are repaired and coverage is rechecked, or the first zero-cost/download/validation blocker is recorded. Expect `KE 2013 status` to remain the next unresolved policy blocker unless separately addressed.
```

## Obsolete Phase 1A Status Repair Command Plan

Do not run these continuous-symbol commands for the 2010 blocker. The 2010 continuous-symbol gate is proven provider-empty (`provider_empty_estimate_count=12`), while the parent-symbol probe is zero-cost with positive billable size. Keep this block only as historical evidence for the original dry-run set comparison.

Historical dry-run planning commands:

```powershell
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6C,6J,GC,HO,LE,RB,UB,ZB,ZC,ZF,ZN,ZT --start 2010-01-01 --end 2011-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2010 --workers 4 --resume --dry-run
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6C,HG,HO,LE,RB,UB,YM,ZB,ZF,ZM,ZN,ZS,ZT --start 2011-01-01 --end 2012-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2011 --workers 4 --resume --dry-run
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6E,HO,LE,NQ,RB,UB,YM,ZB,ZF,ZL,ZM,ZN,ZT --start 2012-01-01 --end 2013-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2012 --workers 4 --resume --dry-run
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6E,6M,HE,HO,KE,LE,RB,YM,ZL,ZM,ZS,ZT,ZW --start 2013-01-01 --end 2014-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2013 --workers 4 --resume --dry-run
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6A,6B,6C,6E,6J,6M,ES,GC,HG,NQ,RB,SI,YM,ZC,ZM,ZT --start 2014-01-01 --end 2015-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2014 --workers 4 --resume --dry-run
```

Obsolete continuous-symbol download commands:

```powershell
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6C,6J,GC,HO,LE,RB,UB,ZB,ZC,ZF,ZN,ZT --start 2010-01-01 --end 2011-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2010 --workers 4 --resume --zero-cost-only
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6C,HG,HO,LE,RB,UB,YM,ZB,ZF,ZM,ZN,ZS,ZT --start 2011-01-01 --end 2012-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2011 --workers 4 --resume --zero-cost-only
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6E,HO,LE,NQ,RB,UB,YM,ZB,ZF,ZL,ZM,ZN,ZT --start 2012-01-01 --end 2013-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2012 --workers 4 --resume --zero-cost-only
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6E,6M,HE,HO,KE,LE,RB,YM,ZL,ZM,ZS,ZT,ZW --start 2013-01-01 --end 2014-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2013 --workers 4 --resume --zero-cost-only
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema status --stype-in continuous --stype-out instrument_id --markets 6A,6B,6C,6E,6J,6M,ES,GC,HG,NQ,RB,SI,YM,ZC,ZM,ZT --start 2014-01-01 --end 2015-01-01 --chunk year --dbn-root data\dbn --reports-root reports\phase1A_status_repair_20260624\2014 --workers 4 --resume --zero-cost-only
```

Validate Phase 1A readiness after any approved repair:

```powershell
python -m scripts.validation.check_dbn_archive_coverage --config configs/alpha_tiered.yaml --profile tier_3_research --dbn-root data\dbn
```
