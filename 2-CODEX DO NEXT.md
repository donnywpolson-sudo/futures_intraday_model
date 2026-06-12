Make one explicit raw layout migration patch.

Preconditions:
- First inspect repo path and git status.
- Do not edit, move, delete, stage, or preserve generated data/report artifacts.
- Do not manually move existing DBN/parquet files.
- Run the Tier 2 Phase 1A/1B stability check first. If it fails, stop and report failures.

Target layout:
- Phase 1A DBN archives:
  data/raw/dbn/ohlcv_1m/{market}/{year}.dbn.zst
  data/raw/dbn/ohlcv_1m/{market}/{year}.dbn.zst.manifest.json
  data/raw/dbn/definition/{market}/{year}.dbn.zst
  data/raw/dbn/definition/{market}/{year}.dbn.zst.manifest.json
- Phase 1B parquet:
  data/raw/parquet/{market}/{year}.parquet

Patch scope:
- Update Phase 1A path generation/defaults.
- Update Phase 1B conversion discovery/defaults.
- Update configs/alpha_tiered.yaml raw_root to the parquet root if downstream Phase 2 reads parquet there.
- Update tests for Phase 1A/1B path expectations.
- Update Phase 2/validation tests only where path defaults/assertions require it.
- Update README.md and project_layout.md.
- Preserve CLI overrides like --dbn-root and --raw-root.
- Prefer backward-compatible reading of the old DBN layout where cheap and low-risk, but make the new layout canonical.

Validation:
- Run the narrowest Phase 1A/1B tests.
- Run Phase 2 raw input/path tests if touched.
- Run python -m pytest tests/phase1A_download/test_download_databento_raw.py -q.
- Run git status --short and confirm no generated data/report artifacts are tracked.

Report:
- Files changed.
- Commands run.
- Tests run and result.
- Any generated artifacts created by validation.
- Any unresolved migration risks.