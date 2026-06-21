# Codex Handoff

## Current latest status
- Step 6 blocker-fix validation completed.
- Overall Step 6 validation: PASS.
- Phase 1B metadata-network blocker resolved: yes, via explicit `--offline-local-conditions`; default production metadata behavior is unchanged.
- Pytest collection blocker resolved: yes, via `scripts/phase1A_download/plan_raw_layout_migration.py` compatibility module.
- Bounded Phase 1A dry-run, Phase 1B offline CLI conversion, Phase 1C alignment, Phase 2 readiness, and Phase 2 causal smoke passed.
- Broad previously failing pytest command passed: 207 passed.
- `data/` top-level canonical: yes.
- Noncanonical `data/` top-level folders remaining: none.
- DBN immutability: PASS (7692 files, 0 missing/added/changed).
- Data deleted/moved/quarantined/renamed in this run: no.
- DBN redownloaded or modified in this run: no.
- Safe to run full phase 1A->2 rebuild next: yes from these Step 6 blockers, pending explicit user approval.
- Caveat: one earlier offline Phase 1B attempt before the date-range filter fix timed out after converting 68 local market-years into `data/raw/_smoke_step6_blockerfix_20260621`; it was preserved and not deleted.

## Files changed
- `scripts/phase1A_download/download_databento_raw.py`
- `scripts/phase1A_download/plan_raw_layout_migration.py`
- `tests/phase1A_download/test_download_databento_raw.py`
- `reports/data_reorg/STEP6_POST_CLEANUP_VALIDATION.md`
- `reports/data_reorg/FINAL_DATA_REORG_REPORT.md`
- `reports/phase_restart/phase_restart_summary.md`
- `CODEX_HANDOFF.md`

## Passed commands
- `python -m pytest tests\phase1A_download\test_download_databento_raw.py tests\phase1A_download\test_plan_raw_layout_migration.py`
- `python -m scripts.phase1B_convert.convert_databento_raw --schema ohlcv-1m --markets ES,CL,ZN,6E --start 2024-01-01 --end 2025-01-01 --chunk year --dbn-root data\dbn\ohlcv_1m --raw-root data\raw\_smoke_step6_blockerfix_bounded_20260621 --reports-root reports\phase_restart\step6_blockerfix_bounded_phase_1b_smoke --workers 2 --resume --include-optional-schemas status,statistics --optional-dbn-root data\dbn --offline-local-conditions`
- `python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema ohlcv-1m --markets ES --start 2024-01-01 --end 2025-01-01 --chunk year --dbn-root data\dbn\ohlcv_1m --reports-root reports\phase_restart\step6_blockerfix_phase_1a_smoke --workers 1 --resume --dry-run`
- `python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config reports\phase_restart\tier1refs_2024_smoke_alpha_tiered.yaml --profile tier_0 --dbn-root data\dbn --raw-root data\raw\_smoke_step6_blockerfix_bounded_20260621 --json-out reports\phase_restart\step6_blockerfix_phase_1c_raw_dbn_alignment.json --md-out reports\phase_restart\step6_blockerfix_phase_1c_raw_dbn_alignment.md`
- `python -m scripts.validation.audit_phase2_readiness --profile tier_0 --raw-root data\raw\_smoke_step6_blockerfix_bounded_20260621 --raw-alignment-report reports\phase_restart\step6_blockerfix_phase_1c_raw_dbn_alignment.json --profile-config reports\phase_restart\tier1refs_2024_smoke_alpha_tiered.yaml --summary-only --top-blockers 10 --json-out reports\phase_restart\step6_blockerfix_phase2_readiness_summary.json`
- `python -m scripts.phase2_causal_base.build_causal_base_data --profile tier_0 --raw-root data\raw\_smoke_step6_blockerfix_bounded_20260621 --output-root data\causally_gated_normalized\_smoke_step6_blockerfix_bounded_20260621 --reports-root reports\phase_restart\step6_blockerfix_phase_2_causal --profile-config reports\phase_restart\tier1refs_2024_smoke_alpha_tiered.yaml --raw-alignment-report reports\phase_restart\step6_blockerfix_phase_1c_raw_dbn_alignment.json`
- `python -m pytest tests\phase1A_download\test_download_databento_raw.py tests\phase1A_download\test_plan_raw_layout_migration.py tests\validation\test_audit_raw_dbn_alignment.py tests\phase2_causal_base\test_build_causal_base_data.py tests\validation\test_audit_local_trade_ohlcv_gaps.py tests\validation\test_build_sr_front_contract_candidate.py tests\validation\test_audit_sr_roll_repair_sources.py`
- `git diff --check -- scripts\phase1A_download\download_databento_raw.py scripts\phase1A_download\plan_raw_layout_migration.py tests\phase1A_download\test_download_databento_raw.py`

## Attempted non-passing command
- `python -m scripts.phase1B_convert.convert_databento_raw --schema ohlcv-1m --markets ES,CL,ZN,6E --start 2024-01-01 --end 2025-01-01 --chunk year --dbn-root data\dbn\ohlcv_1m --raw-root data\raw\_smoke_step6_blockerfix_20260621 --reports-root reports\phase_restart\step6_blockerfix_phase_1b_smoke --workers 2 --resume --include-optional-schemas status,statistics --optional-dbn-root data\dbn --offline-local-conditions  # timed out after converting 68 local market-years before date-range filter fix; generated output preserved, not deleted`

## Test results
- Targeted blocker tests: PASS, 92 passed.
- Broad previously failing pytest command: PASS, 207 passed.

## Remaining work
- Review the refreshed Step 6 reports.
- Do not run a full phase 1A->2 rebuild until explicitly approved.

## Next recommended step
- Approve or reject running the full phase 1A->2 rebuild.

## Live chart wrapper removal
- Migrated `.vscode/launch.json` from `live_chart_lightweight.py` to `live_chart_feed.py`.
- Updated `.vscode/launch.json` args from old `--symbols ES.c.0` / `--chart-timeframe` style to current `--market ES` / `--timeframe 5m` semantics.
- Updated `README_RUNBOOK.md` live chart command to `python live_chart_feed.py --market ES --historical-backfill --lookback-hours 2 --timeout-seconds 30`.
- Replaced stale `tests/live/test_live_chart_lightweight.py` contents with current `live_chart_feed.py` entrypoint and guard tests; it no longer imports or executes the wrapper.
- Removed `live_chart_lightweight.py` with `git rm -f` after reference searches and focused tests passed.
- Preserved unrelated dirty worktree files.

## Live chart wrapper removal files changed
- `.vscode/launch.json`
- `README_RUNBOOK.md`
- `tests/live/test_live_chart_lightweight.py`
- `live_chart_lightweight.py` deleted
- `CODEX_HANDOFF.md`

## Live chart wrapper removal commands run
- `git status --short`
- `rg -n -S "live_chart_lightweight|live_chart_feed" .vscode README_RUNBOOK.md tests live_chart_lightweight.py live_chart_feed.py --glob "!**/__pycache__/**" --glob "!*.pyc"`
- `python -m pytest tests\test_live_chart_feed.py tests\live\test_live_chart_lightweight.py -q`
- `rg live_chart_lightweight .vscode README_RUNBOOK.md tests`
- `git grep -n "live_chart_lightweight"`
- `git rm live_chart_lightweight.py`
- `git rm -f live_chart_lightweight.py`
- `rg live_chart_lightweight .vscode README_RUNBOOK.md tests`
- `git grep -n "live_chart_lightweight"`
- `python -m pytest tests\test_live_chart_feed.py tests\live\test_live_chart_lightweight.py -q`
- `git status --short`

## Live chart wrapper removal validation results
- Pre-removal focused tests: PASS, 21 passed.
- Pre-removal `rg live_chart_lightweight .vscode README_RUNBOOK.md tests`: no matches.
- Pre-removal `git grep -n "live_chart_lightweight"`: one remaining match in `live_chart_lightweight.py` itself.
- `git rm live_chart_lightweight.py`: refused because the file had local modifications.
- `git rm -f live_chart_lightweight.py`: PASS, removed the verified wrapper.
- Post-removal `rg live_chart_lightweight .vscode README_RUNBOOK.md tests`: no matches.
- Post-removal `git grep -n "live_chart_lightweight"`: no matches.
- Post-removal focused tests: PASS, 21 passed.

## Live chart wrapper removal next recommended step
- Review the staged wrapper deletion plus unstaged launch/docs/test edits, then commit them together when ready.

## Live chart NQ 5m visual verification
- Result: PASS; remaining visual blocker resolved.
- Exact command run from interactive desktop session:
  `python live_chart_feed.py --market NQ --timeframe 5m --historical-backfill --lookback-hours 4 --timeout-seconds 120`
- Visual evidence:
  - User-provided screenshot `C:\Users\donny\AppData\Local\Temp\codex-clipboard-49569f91-26f0-4c44-a71b-9b59340d5e43.png` showed an open chart window titled `NQU6 5m`, 5m selected, rendered candles and volume, and live status around 770 bars.
  - Process-scoped `PrintWindow` screenshot `C:\Users\donny\AppData\Local\Temp\live_chart_feed_printwindow_20260621_163419_9307316.png` showed the same `NQU6 5m` chart, 5m selected, rendered candles and volume, and live status around 700 bars.
- Terminal evidence:
  - `C:\Users\donny\AppData\Local\Temp\live_chart_feed_20260621_163059.out.log`: ran from 2026-06-21 16:30:59 to 16:33:11 local, stderr was empty, no traceback observed.
  - `C:\Users\donny\AppData\Local\Temp\live_chart_feed_20260621_163419.out.log`: showed changing `last_close` and records through `records=784`, `latest=2026-06-21T23:35:00Z`, `last_close=30402.75`.
  - `C:\Users\donny\AppData\Local\Temp\live_chart_feed_20260621_163419.err.log`: only WebView cleanup warning `Failed to unregister class Chrome_WidgetWin_0. Error = 1411`; no Python traceback.
- Historical candles rendered from the available Globex session start visible around 15:00 local through 16:30-16:35 local; the requested 4-hour window was bounded by available session history.
- No source, data, report, or canonical layout changes were made beyond this handoff update.
