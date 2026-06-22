# Pipeline Phase IO Map

Generated at UTC: 2026-06-22T09:08:15.207901+00:00

This is a read-only lineage map from script/config references plus filesystem metadata. No DBN conversion, Databento download, validation job, data move, data delete, or data overwrite was run.

| Phase | Script/module | Inputs | Outputs | Confidence |
|---|---|---|---|---|
| 1A | `scripts/phase1A_download/download_databento_raw.py --mode download-dbn|batch|all` | Databento Historical API GLBX.MDP3; credentials from secrets/databento.env or databento.env | data/dbn/<schema_path>/<market>/<year>/<start>_<end>.dbn.zst; default data/dbn/ohlcv_1m for ohlcv-1m | HIGH |
| 1A legacy/helper | `scripts/phase1A_download/download_databento_raw.py --mode stream --raw-format parquet` | Databento Historical API GLBX.MDP3 | data/raw/<market>/<year>.parquet | MEDIUM |
| 1A helper | `scripts/phase1A_download/plan_raw_layout_migration.py` | caller-provided raw_root scanned recursively for .dbn, .dbn.zst, .parquet and sidecar manifests | caller-provided target_root/<schema_path>/<market>/<year>/<start>_<end>.dbn.zst; apply_migration can move files if called | LOW |
| 1B | `scripts/phase1B_convert/convert_databento_raw.py -> download_databento_raw.py --mode convert-parquet` | data/dbn/ohlcv_1m/<market>/<year>/*.dbn.zst plus data/dbn/definition/<market>/<year>/*.dbn.zst; optional data/dbn/status and data/dbn/statistics | data/raw/<market>/<year>.parquet; reports/raw_ingest/databento_convert_results.json and raw_ingest/raw_parquet_manifest.json | HIGH |
| 1C | `scripts/phase1C_validate/audit_raw_dbn_alignment.py` | data/dbn/<ohlcv_1m|definition>/<market>/<year>/*.dbn.zst and data/raw/<market>/<year>.parquet | reports/raw_ingest/raw_dbn_alignment.json; reports/raw_ingest/raw_dbn_alignment.md | HIGH |
| 2 | `scripts/phase2_causal_base/build_causal_base_data.py` | data/raw/<market>/<year>.parquet selected by --profile and configs/alpha_tiered.yaml; reports/raw_ingest/raw_dbn_alignment.json guard | data/causally_gated_normalized/<market>/<year>.parquet; reports/causal_base/causal_base_manifest.json and validation files | HIGH |
| 2 helper | `scripts/phase2_causal_base/build_higher_timeframe_bars.py` | caller-provided causal/session-normalized parquet input_path | caller-provided output_path, tests use data/higher_timeframes/<timeframe>/<market>/<year>.parquet | MEDIUM |

## Key Evidence

- Phase 1A defaults `DEFAULT_DBN_OUT` to `data/dbn/ohlcv_1m`; schema path mapping is in `scripts/phase1_raw_contract.py`.
- Phase 1B wrapper inserts `--mode convert-parquet`, causing DBN input from `data/dbn/ohlcv_1m` and parquet output to `data/raw`.
- Phase 1C defaults are `--dbn-root data/dbn` and `--raw-root data/raw`; its current alignment report is `reports/raw_ingest/raw_dbn_alignment.json`.
- Phase 2 defaults are `--raw-root data/raw`, `--output-root data/causally_gated_normalized`, and `--raw-alignment-report reports/raw_ingest/raw_dbn_alignment.json`.
- `configs/alpha_tiered.yaml` defines `data/raw`, `data/causally_gated_normalized`, `data/labeled`, `data/feature_matrices/baseline`, and related downstream roots.

See `pipeline_phase_io_map.csv` for the full structured row set.
