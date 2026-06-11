Patch project layout for DBN raw-ingest workflow only.

Repo:
C:\Users\donny\Desktop\quant_project

Target:
build/project_layout.md
README.md only if it repeats stale Phase 1/profile wording

Do not edit code.
Do not run pipeline phases.
Do not modify generated data/reports.
Do not start Phase 5.

Problems to fix:
1. Phase 1 still describes direct external parquet input. Replace with:
   - Phase 1A: download/archive Databento DBN/DBN.ZST to data/dbn/{market}/{year}/...dbn.zst
   - Phase 1B: convert/stitch DBN chunks to immutable raw parquet at data/raw/{market}/{year}.parquet
   - Phase 2: validate/session-normalize/roll-audit/synthetic-mark/causally gate parquet

2. Add raw-ingest hard gates:
   - required parquet columns: ts_event, open, high, low, close, volume, rtype, publisher_id, instrument_id, symbol, data_quality_status, data_quality_degraded
   - preserve rtype/publisher_id/instrument_id/symbol
   - do not rename ts_event to ts in Phase 1
   - do not fill missing 1-minute bars in Phase 1
   - support one or many DBN chunks per market/year
   - hash every DBN chunk
   - convert all chunks, concatenate, sort by ts_event, check duplicates
   - fail if required schema/metadata is missing or fake-filled
   - report price_scale_policy, data_quality_source, vendor_quality_available, decoded_symbols, input_hashes, output_hash, row counts, first_ts, last_ts

3. Fix Tier-2 universe wording:
   - use exact 28-market Tier-2 universe
   - include VX
   - remove “27-market” wording
   - state missing Tier-2 data must fail validation, not shrink the universe

4. Add Phase 4 lookback rule:
   - rolling/lag/count features must not compute through feature_input_valid=false rows
   - invalid lookbacks produce NaN, not false/zero

5. Clarify registry responsibility:
   - Phase 4 writes initial feature_cols/target_cols/metadata_cols/excluded_cols
   - Phase 5 audits/freezes/promotes registry for WFA

Validation:
git diff -- build/project_layout.md README.md
git grep -n "27-market" build/project_layout.md README.md should return no matches
git grep -n "External Databento parquet exports" build/project_layout.md README.md should return no matches
git status --short

Stop after reporting changed files and final git status.