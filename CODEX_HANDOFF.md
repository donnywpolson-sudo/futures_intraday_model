# Codex Handoff

Updated at UTC: 2026-06-22T00:23:29Z

## Current latest status
- Active instruction was Step 4/reporting only. No cleanup, movement, quarantine, rename, delete, Step 5, Step 6, DBN redownload, WFA, backtest, metrics, model selection, or final holdout was run in this continuation.
- Current `data/` top-level folders are exactly the six canonical names by read-only inspection.
- Existing local reports show Step 5 cleanup and Step 6 validation had already been performed before this continuation; those historical actions were not repeated.
- DBN immutability current compare: PASS; before=7692; current=7692; added=0; removed=0; changed=0.
- DBN coverage audit: 33 markets; missing OHLCV years remain for ['RTY', 'SR3', 'SR1', 'TN', 'KE'].
- L0/OHLCV overlap latest report status: PASS.
- Full rebuild continuation was not resumed because the active pasted instruction limits this run to Step 4/reporting scope.

## Files changed in this continuation
- `reports/data_reorg/dbn_immutability_after.csv`
- `reports/data_reorg/dbn_immutability_after.json`
- `reports/data_reorg/dbn_immutability_compare.md`
- `reports/data_reorg/data_folder_classification.csv`
- `reports/data_reorg/data_folder_classification.md`
- `reports/data_reorg/DATA_REORG_CHECKPOINT_STEP4.md`
- `reports/phase_restart/phase_restart_summary.md`
- `CODEX_HANDOFF.md`

## Commands run in this continuation
- `Get-Content -LiteralPath 'C:\Users\donny\.codex\attachments\ffd3af13-5673-4898-a8a1-c41beb0875a2\pasted-text-1.txt'`
- `Get-Location; git status --short`
- `if (Test-Path -LiteralPath 'CODEX_HANDOFF.md') { Get-Content -LiteralPath 'CODEX_HANDOFF.md' }`
- `rg -n \"def resolve_profile_inputs|def discover_raw_inputs|def build_phase2_readiness_report|raw alignment eligible\" scripts\phase2_causal_base\build_causal_base_data.py scripts\validation\audit_phase2_readiness.py`
- `rg -n \"futures_intraday_model|data_reorg|phase_restart|Step 4|phase 1A\" 'C:\Users\donny\.codex\memories\MEMORY.md'`
- `git status --short`
- `Get-ChildItem -LiteralPath data -Directory | Select-Object Name,FullName,LastWriteTime | Sort-Object Name | Format-Table -AutoSize`
- `Get-ChildItem -LiteralPath reports\data_reorg,reports\phase_restart -File -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime | Sort-Object FullName | Format-Table -AutoSize`
- `Read-only Python snippets to inspect existing JSON report schemas and summaries.`
- `Get-ChildItem -LiteralPath . -Directory -Filter '_data_reorg_quarantine*' | Select-Object Name,FullName,LastWriteTime | Sort-Object Name | Format-Table -AutoSize`
- `Get-ChildItem -LiteralPath _data_reorg_quarantine20260621T222448Z -Directory -ErrorAction SilentlyContinue | Select-Object Name,FullName | Sort-Object Name | Format-Table -AutoSize`
- `Get-ChildItem -LiteralPath data\dbn -Directory | Select-Object Name,FullName | Sort-Object Name | Format-Table -AutoSize`
- `rg -n --glob '!reports/**' --glob '!data/**' --glob '!_data_reorg_quarantine*/**' --glob '!CODEX_HANDOFF.md' \"causally_gated_normalized_tier3_candidate|dbn_sr_parent_candidate|raw_sr_front_contract_candidate|raw_sr_front_contract_candidate_parent_20260621|raw_sr_front_contract_candidate_quarterly\" .`
- `PowerShell here-string piped to python - to refresh report-only files listed in this checkpoint; first attempt failed at parse time and wrote nothing, second attempt wrote reports, third report-only command corrected immutable timestamp precision.`
- `apply_patch` report-only correction to replace a self-referential Phase 2 causal smoke evidence path with `reports/phase_restart/step6_blockerfix_phase_2_causal/causal_base_manifest.json`.

## Test results
- No tests or phase scripts were run in this continuation; existing smoke/test evidence is referenced in the refreshed reports.

## Remaining work
- Review `reports/data_reorg/DATA_REORG_CHECKPOINT_STEP4.md` and `reports/data_reorg/data_folder_classification.md`.
- Decide whether to approve any further cleanup or full rebuild work. No such work should run without approval.

## Next recommended step
- Review and approve/reject the refreshed Step 4 classification/checkpoint report.

## Live chart tier3 universe and higher-timeframe update
- Read goal objective attachment `C:\Users\donny\.codex\attachments\10b71462-502f-4513-a69b-68794f78fb36\goal-objective.md`.
- Located live chart implementation in `live_chart_feed.py`; this Python app owns chart UI setup, Databento historical/live calls, symbol resolution, market discovery, topbar interval controls, and candle aggregation.
- Added `4h` and `1d` chart intervals while preserving existing `1m`, `5m`, `15m`, `30m`, and `1h` behavior.
- Added timeframe-aware candle bucketing: `4h` anchors in exchange time and `1d` uses Globex trading-day starts based on `America/Chicago` 17:00 session open.
- Preserved config-driven tier3 market loading from `configs/alpha_tiered.yaml` and changed returned market order to match the YAML universe order.
- Added `chart_market_universe()` helper for UI/API-style callers.
- Added a topbar market selector populated from the config-driven market universe. It is currently a visible selector/watchlist control; full in-process Databento reconnect on selection remains incomplete.
- Added status HUD text for stale latest bars and `model output unavailable` placeholder; no fake model outputs were invented.
- Hardened chart UI event draining to ignore non-callable handlers.

## Live chart tier3 universe and higher-timeframe files changed
- `live_chart_feed.py`
- `tests/test_live_chart_feed.py`
- `CODEX_HANDOFF.md`

## Live chart tier3 universe and higher-timeframe commands run
- `Get-Content -LiteralPath 'C:\Users\donny\.codex\attachments\10b71462-502f-4513-a69b-68794f78fb36\goal-objective.md'`
- `git status --short`
- `rg -n "SUPPORTED_CHART_TIMEFRAMES|DEFAULT_CHART_TIMEFRAMES|timeframe_seconds|aggregate_candles|configure_chart|topbar|switcher|market|search|localStorage|query|model|overlay|prediction|signal|session" live_chart_feed.py tests\test_live_chart_feed.py tests\live -S`
- `rg -n "tier_3_research|tier3research|markets:" configs\alpha_tiered.yaml live_chart_feed.py tests\test_live_chart_feed.py`
- `python -m pytest tests\test_live_chart_feed.py tests\live\test_live_chart_lightweight.py -q`
- `python -m py_compile live_chart_feed.py`
- `c:\Users\donny\Desktop\futures_intraday_model\.venv\Scripts\python.exe c:/Users/donny/Desktop/futures_intraday_model/live_chart_feed.py --market ES --timeframe 5m --historical-backfill --lookback-hours 4 --timeout-seconds 10`
- `c:\Users\donny\Desktop\futures_intraday_model\.venv\Scripts\python.exe c:/Users/donny/Desktop/futures_intraday_model/live_chart_feed.py --market NQ --timeframe 4h --historical-backfill --lookback-hours 24 --timeout-seconds 8`
- `c:\Users\donny\Desktop\futures_intraday_model\.venv\Scripts\python.exe c:/Users/donny/Desktop/futures_intraday_model/live_chart_feed.py --market ES --timeframe 1d --historical-backfill --lookback-hours 72 --timeout-seconds 8`
- `git diff --check -- live_chart_feed.py tests\test_live_chart_feed.py CODEX_HANDOFF.md`
- `Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Select-Object ProcessId,CommandLine | Format-List`

## Live chart tier3 universe and higher-timeframe validation results
- Focused tests: PASS, 30 passed.
- `py_compile`: PASS.
- `git diff --check`: PASS.
- ES 5m bounded live validation: PASS, exit 0, streamed live status and retained Databento available-end clamp logs.
- NQ 4h bounded live validation: PASS, exit 0, streamed live status with 4h bucket `2026-06-21T21:00:00Z`.
- ES 1d bounded live validation: PASS, exit 0, streamed daily bars from Globex session starts including `2026-06-18T22:00:00Z` and `2026-06-21T22:00:00Z`.
- No `live_chart_feed.py` Python processes remained after validation.

## Live chart tier3 universe and higher-timeframe remaining work
- Full in-process market switching without restarting the Databento subscription remains incomplete. Current selector is visible and config-driven, but it uses a no-op callback to avoid false switch events from `lightweight_charts`.
- URL/local-storage persistence is not implemented in this Python chart surface.
- Model overlay adapter is only a UI/status placeholder; no real model endpoint/artifact adapter was added.

## Live chart tier3 universe and higher-timeframe next recommended step
- Implement real market-change handling by stopping the current Databento live client, resolving the selected market, backfilling, clearing candles, and subscribing to the new instrument in the same chart window.

## Live chart in-process market switching update
- Added market switch callback plumbing with an initialization gate to avoid startup switch events.
- `drain_chart_queue` can now return a requested `switch_market`.
- `run_live_chart` now handles a market switch by stopping the active Databento live client, clearing chart candles/session markers/status, resolving the selected market, replaying historical backfill for the original lookback window, and subscribing to the new instrument in the same chart window.
- Added a small model overlay adapter surface with `ModelOverlayState`, `model_overlay_state()`, and `model_overlay_status_text()`.
- Added a visible model overlay toggle control; unavailable model output remains explicit and no fake predictions are generated.
- Added focused tests for market switch queue filtering and model overlay status formatting.

## Live chart in-process market switching files changed
- `live_chart_feed.py`
- `tests/test_live_chart_feed.py`
- `CODEX_HANDOFF.md`

## Live chart in-process market switching commands run
- `python -m pytest tests\test_live_chart_feed.py tests\live\test_live_chart_lightweight.py -q`
- `python -m py_compile live_chart_feed.py`
- `python live_chart_feed.py --list-markets`
- `git diff --check -- live_chart_feed.py tests\test_live_chart_feed.py CODEX_HANDOFF.md`
- `git status --short`

## Live chart in-process market switching validation results
- Focused tests: PASS, 32 passed.
- `py_compile`: PASS.
- `--list-markets`: PASS, printed 33 Tier 3 Research markets from `configs/alpha_tiered.yaml`.
- `git diff --check`: PASS, line-ending warnings only.
- Bounded live Databento validation was not rerun in this continuation because the required escalation was rejected by the approval system: usage limit reached.

## Live chart in-process market switching remaining work
- Live in-window market switching is implemented but not live-validated after this update because the environment rejected Databento validation for usage-limit reasons.
- URL/local-storage persistence remains unimplemented in this Python chart surface.

## Live chart in-process market switching next recommended step
- When Databento/live-command approval is available, run `python live_chart_feed.py --market ES --timeframe 5m --historical-backfill --lookback-hours 4 --timeout-seconds 30`, use the chart market selector to switch to `NQ`, and confirm the same window clears, backfills, and streams NQ without a restart.
