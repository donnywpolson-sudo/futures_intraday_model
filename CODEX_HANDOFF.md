# Codex Handoff

## Phase/data reorg blocker resolution
- Updated at UTC: 2026-06-22T04:37:24Z
- Read objective attachment `C:\Users\donny\.codex\attachments\2de8e284-f885-4179-85d3-364e11187715\goal-objective.md`.
- Scope: resolve resume-audit verification blockers only. No data was deleted, moved, quarantined, redownloaded, rebuilt, or DBN source-modified. No phase after Phase 2 was run. Unowned live-ops changes in `live_ops/audit.py`, `live_ops/broker.py`, `live_ops/reconciliation.py`, and `tests/test_live_ops.py` were preserved.

Changed
- `scripts/phase2_causal_base/build_higher_timeframe_bars.py`: restored the missing higher-timeframe import path with the tested aggregation/report helper surface.
- `reports/phase_restart/INTERRUPTED_GOAL_RESUME_AUDIT.md`: updated verdict to COMPLETE, recorded broad collect-only PASS, and classified `phase_2_smoke.md` as stale/superseded by Step 6 / FINAL PASS evidence.
- `CODEX_HANDOFF.md`: recorded this blocker-resolution pass.
- Commands run: objective/report/handoff reads; `rg` reference search; `python -m pytest tests\phase2_causal_base\test_build_higher_timeframe_bars.py -q`; `python -m pytest tests -q --collect-only -p no:cacheprovider`; focused phase audit collect-only.
- Verification results: higher-timeframe focused tests PASS, 7 passed; broad collect-only PASS, 706 tests collected; focused phase audit collect-only PASS, 191 tests collected.

Blockers
Low
None

Medium
None

Severe
None

Proceed status: yes

Next
1. Review `reports/phase_restart/INTERRUPTED_GOAL_RESUME_AUDIT.md` -> confirm blocker resolution record is acceptable -> stop before cleanup or full rebuild unless separately approved.

## Interrupted phase/data reorg resume audit
- Updated at UTC: 2026-06-22T04:30:57Z
- Read objective attachment `C:\Users\donny\.codex\attachments\56e91250-ba13-46c1-8382-919b82918e3d\pasted-text-1.txt`.
- Scope was read-only audit plus report writing. No data was deleted, moved, quarantined, redownloaded, rebuilt, or DBN source-modified.
- Wrote `reports/phase_restart/INTERRUPTED_GOAL_RESUME_AUDIT.md`.
- Verdict: `PROBABLY COMPLETE, NEEDS VERIFICATION`.
- Current `data/` top-level folders are exactly the six canonical folders.
- Existing reports evidence historical Step 5 cleanup and Step 6 validation as complete, but the latest interrupted continuation stopped at Step 4 reporting/classification.
- Medium blocker: broad `python -m pytest tests -q --collect-only -p no:cacheprovider` fails collecting `tests/phase2_causal_base/test_build_higher_timeframe_bars.py` because `scripts.phase2_causal_base.build_higher_timeframe_bars` is missing.
- Focused phase audit collect-only passed: 191 tests collected for phase 1A, causal base, raw/DBN alignment, and phase 2 readiness.
- Final status also showed concurrent/unowned changes in `tests/test_live_ops.py` and later Phase 1/2A handoff content; this audit did not edit or revert them.
- Next recommended step: clear the broad pytest collection error, then decide whether to accept Step 6/FINAL reports as superseding the older `phase_2_smoke.md` `PARTIAL / WARN` status.

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

## Live chart market switching bug fix continuation
- Fixed the market selector callback to accept both the real chart-object callback shape and a direct selected market value.
- Added a local fake-Databento/fake-chart regression test that emits a synthetic `market_~_NQ` UI event while ES has an old queued live tick.
- The regression proves ES -> NQ switches the historical `get_range` request from instrument `101` to `202`, switches the live subscription from `101` to `202`, stops the old live client, clears the chart, renders NQ close `200.0`, and does not render the stale ES close `999.0`.
- URL/local-storage persistence was not implemented in this pass because this app is a Python `lightweight_charts` surface without a clean URL/localStorage startup read path.

## Live chart market switching bug fix files changed
- `live_chart_feed.py`
- `tests/test_live_chart_feed.py`
- `CODEX_HANDOFF.md`

## Live chart market switching bug fix commands run
- `python -m pytest tests/test_live_chart_feed.py -q`
- `python -m py_compile live_chart_feed.py`
- `python live_chart_feed.py --list-markets`
- `git diff --check`
- `git status --short`
- `python -m pytest tests\live\test_live_chart_lightweight.py -q`
- `python live_chart_feed.py --market ES --timeframe 5m --historical-backfill --lookback-hours 4 --timeout-seconds 30`
- `Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Select-Object ProcessId,CommandLine | Format-List`

## Live chart market switching bug fix validation results
- Focused live chart tests: PASS, 27 passed.
- Wrapper/CLI live chart tests: PASS, 7 passed.
- `py_compile`: PASS.
- `--list-markets`: PASS, printed 33 Tier 3 Research markets.
- `git diff --check`: PASS, line-ending warnings only.
- Bounded ES 5m live command: PASS, exit 0, streamed ES bars and retained Databento available-end clamp logs.
- Manual live ES -> NQ selector switching was not performed in this continuation, so live selector switching is not claimed as manually validated.
- No `live_chart_feed.py` Python processes remained after the bounded live run.

## Live chart market switching bug fix remaining work
- Manually validate ES -> NQ selector switching in the native chart window when interactive access is available.
- Add selected market/timeframe persistence if a clean Python chart startup/local-state path is chosen.

## Live chart market switching bug fix next recommended step
- Run the bounded live chart command interactively, switch the market selector from ES to NQ, and confirm the same chart window clears, backfills, and streams NQ.

## Focused pytest hang isolation update
- Updated at UTC: 2026-06-22T04:04:15Z
- Read goal objective attachment `C:\Users\donny\.codex\attachments\10b205c7-cc5c-419c-a58c-81e00f2e6c12\goal-objective.md`.
- Current repo state before patch: `git status --short` empty; `git diff --stat` empty.
- Interrupted goal changed files identified from this handoff history: `live_chart_feed.py`, `tests/test_live_chart_feed.py`, and `CODEX_HANDOFF.md`; no uncommitted interrupted-goal changes were present at the start of this run.
- Isolated the focused pytest hang to `tests\test_live_chart_feed.py::test_run_live_chart_uses_persisted_market_and_timeframe`.
- Root cause: the test passed `--timeout-seconds 0.01` but injected `clock=lambda: 103.0`, so `drain_chart_queue` could never observe the finite timeout deadline after queued fake data was exhausted.
- Patched only the test clock to use a deterministic advancing monotonic iterator.

## Focused pytest hang isolation files changed
- `tests/test_live_chart_feed.py`
- `CODEX_HANDOFF.md`

## Focused pytest hang isolation commands run
- `Get-Content -Raw -LiteralPath 'C:\Users\donny\.codex\attachments\10b205c7-cc5c-419c-a58c-81e00f2e6c12\goal-objective.md'`
- `Test-Path -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\CODEX_HANDOFF.md'`
- `Get-Content -Raw -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\CODEX_HANDOFF.md'`
- `git status --short`
- `git diff --stat`
- Targeted `rg` inspection of `tests\test_live_ops.py`, `tests\test_live_chart_feed.py`, and `live_chart_feed.py`.
- `python -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py --collect-only -q`
- `python -m pytest --help | Select-String -Pattern '--timeout'`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py -vv -s --tb=short --durations=20`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_chart_feed.py -vv -s --tb=short --durations=20`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_chart_feed.py::test_run_live_chart_uses_persisted_market_and_timeframe -vv -s --tb=short --durations=20`
- PowerShell job wrapper after patch: `python -X faulthandler -m pytest tests\test_live_chart_feed.py::test_run_live_chart_uses_persisted_market_and_timeframe -vv -s --tb=short --durations=20`
- PowerShell job wrapper after patch: `python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -vv -s --tb=short --durations=20`
- `(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Focused pytest hang isolation validation results
- Collection: PASS, 47 tests collected.
- `tests\test_live_ops.py`: PASS, 18 passed in 0.19s under the 120s job wrapper.
- Pre-patch `tests\test_live_chart_feed.py`: HUNG under the 120s job wrapper after `test_run_live_chart_switches_backfill_and_subscription_to_selected_market` passed.
- Pre-patch isolated test: HUNG under the 30s job wrapper.
- Post-patch isolated test: PASS, 1 passed in 0.84s under the 30s job wrapper.
- Post-patch focused combined run: PASS, 47 passed in 1.11s under the 120s job wrapper.

## Focused pytest hang isolation remaining work
- No remaining focused pytest hang is known.
- Broad test suites were not run, per the goal objective.

## Focused pytest hang isolation next recommended step
- Resume the larger scaffold only after reviewing this focused fix; stop before broad validation unless explicitly approved.

## Phase 0 recovery and baseline gate verification
- Updated at UTC: 2026-06-22T04:18:41Z
- Scope: recovery, current repo state inspection, known hang-fix confirmation, focused hang-safe validation only. No Phase 1 scaffold audit or broader implementation was run.
- Current repo state at start and end: `CODEX_HANDOFF.md` and `tests/test_live_chart_feed.py` modified.
- Current diff stat at start and end: 2 files changed, 46 insertions(+), 1 deletion(-).
- Changed files from interrupted/focused recovery work remain `tests/test_live_chart_feed.py` and `CODEX_HANDOFF.md`; nothing was reverted.
- Confirmed the known hang fix is present in `tests\test_live_chart_feed.py::test_run_live_chart_uses_persisted_market_and_timeframe`: the test uses an advancing `monotonic_values` iterator for the injected `clock`.
- Targeted inspection found no repo fixtures, subprocess test launches, blocking GUI launches, or tests invoking `--no-timeout` in the focused files. The focused `run_live_chart` tests use fake chart/Databento objects and finite `--timeout-seconds` args.
- `pytest-timeout` was not available from `python -m pytest --help`, so focused validation used the PowerShell `Start-Job` / `Wait-Job` / `Stop-Job` wrapper.

## Phase 0 recovery and baseline gate commands run
- `Get-Content -Raw -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\CODEX_HANDOFF.md'`
- `git status --short`
- `git diff --stat`
- `rg -n -C 18 "def test_run_live_chart_uses_persisted_market_and_timeframe|monotonic_values|clock=lambda" tests\test_live_chart_feed.py`
- Targeted `rg` inspection of `tests\test_live_ops.py`, `tests\test_live_chart_feed.py`, `live_chart_feed.py`, and imported `live_ops` modules used by those tests.
- `git diff -- tests\test_live_chart_feed.py`
- `python -m pytest --help | Select-String -Pattern '--timeout'`
- `python -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py --collect-only -q`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -vv -s --tb=short --durations=20`
- Final `git status --short`
- Final `git diff --stat`
- `(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Phase 0 recovery and baseline gate validation results
- Collection: PASS, 47 tests collected in 0.13s.
- Focused test command: PASS, 47 passed in 1.03s under the 120s PowerShell job wrapper.

## Phase 0 recovery and baseline gate remaining work
- Send Phase 1 audit goal only after reviewing this Phase 0 handoff; Phase 1 should map scaffold gaps without broad implementation.

## Phase 1 safety scaffold gap audit
- Updated at UTC: 2026-06-22T04:24:26Z
- Scope: audit-only gap map against Parts A-S. No scaffold implementation, broker path, broad pytest, `--no-timeout`, GUI/chart launch, generated artifact change, or Phase 2 work was run.
- Current repo state before audit edits: clean by `git status --short`; `git diff --stat` empty.
- Current safety-critical result: no Severe blockers found in the audited live-ops scaffold surface. The remaining gaps are Medium because they are incomplete/deferred scaffold depth, not unsafe defaults or real broker execution.

## Phase 1 requirement map
- Part A - console output: partially implemented. Owner: `live_ops/operator.py`, `live_chart_feed.py`. Evidence: `render_operator_status`, `print_operator_status`, `emit_status_line`, `tests\test_live_ops.py::test_operator_status_rendering_width`. Missing: explicit debug/verbose log flag is not fully developed. Recommended Phase 2: add a narrow debug/log path only if needed.
- Part B - timeout/run control: implemented. Owner: `live_chart_feed.py`, `tests\test_live_ops.py`, `tests\test_live_chart_feed.py`. Evidence: `--timeout-seconds`, `--no-timeout`, default `DEFAULT_TIMEOUT_SECONDS=None`, finite test `--timeout-seconds`, advancing clock fix. Missing: none for scaffold audit. Recommended Phase 2: preserve behavior.
- Part C - historical/live feed parity: partially implemented. Owner: `live_ops/bar_builder.py`, `tests\test_live_ops.py`. Evidence: `LiveBarBuilder`, `check_bar_parity`, synthetic L1-like tests. Missing: full standalone data contract coverage for sessions, rollover policy, no-trade intervals, and model feature exclusion policy is minimal. Recommended Phase 2: expand contract documentation/tests before model integration.
- Part D - live data-quality gate: partially implemented. Owner: `live_ops/quality.py`, `tests\test_live_ops.py`. Evidence: timezone, monotonicity, duplicate policy, OHLC, volume, tick grid, symbol/contract, stale, heartbeat, gap, session, and contract-mix checks. Missing: heartbeat/reconnect inputs are caller-supplied; no automated rollover calendar. Recommended Phase 2: add targeted tests/config plumbing for caller-supplied heartbeat/reconnect/rollover paths.
- Part E - signal state: implemented. Owner: `live_ops/model.py`, `live_ops/schemas.py`, `tests\test_live_ops.py`. Evidence: `SignalState`, `build_signal_state`, model unavailable and partial-bar tests. Missing: no production model adapter, intentionally deferred. Recommended Phase 2: keep stub behavior until model artifact contract exists.
- Part F - feature/model readiness: partially implemented. Owner: `live_ops/model.py`. Evidence: model path, expected features/order, scaler flag, warmup, supported symbols, finite feature checks, version fields. Missing: imputer/scaler object integration is only represented by flags. Recommended Phase 2: add concrete adapter checks when model artifacts exist.
- Part G - risk manager: partially implemented. Owner: `live_ops/risk.py`, `tests\test_live_ops.py`. Evidence: fail-closed defaults, paper-only gate, live-broker block, symbol/contract/session/data/model/signal/order size/loss/trade count/rate/spread/slippage/reconnect/reconciliation checks. Missing: flatten-before-close action and configured session parsing are minimal. Recommended Phase 2: fill only the highest-priority safety gaps.
- Part H - kill switch/operator controls: partially implemented. Owner: `live_ops/risk.py`, `scripts\kill_switch_on.py`, `scripts\kill_switch_off.py`, `scripts\paper_cancel_all.py`, `scripts\paper_flatten_all.py`. Evidence: file/config kill switch, scripts affect paper/sim state, tests block orders. Missing: optional cancel/flatten-on-kill behavior is not wired as a config action. Recommended Phase 2: add targeted paper-only behavior if required.
- Part I - PaperBroker/SimBroker only: partially implemented. Owner: `live_ops/broker.py`, `tests\test_live_ops.py`. Evidence: deterministic paper fills, positions, open orders, duplicate rejection, cancel_all, flatten_all, state load/save, `LiveBroker.place_order` raises `NotImplementedError`. Missing: next-bar-open fill policy and direct audit-log append from broker are not implemented. Recommended Phase 2: add only if smoke requirements need it.
- Part J - reconciliation: partially implemented. Owner: `live_ops/reconciliation.py`, `live_ops/risk.py`. Evidence: strategy vs broker position mismatch, duplicate fill, stale open order warning, risk blocks reconciliation failure. Missing: audit-state reconciliation is minimal. Recommended Phase 2: extend reconciliation only around paper audit state.
- Part K - audit logging: partially implemented. Owner: `live_ops/audit.py`, `live_ops/smoke.py`, `tests\test_live_ops.py`. Evidence: append-only JSONL writer, one-row-per-cycle smoke accounting, error row scenario. Missing: no fsync/atomic durability hardening and no full runtime audit integration outside smoke. Recommended Phase 2: integrate with selected decision loop only.
- Part L - connectivity/process failure handling: partially implemented. Owner: `live_chart_feed.py`, `live_ops/quality.py`, `live_ops/risk.py`, `live_ops/smoke.py`. Evidence: stale data, heartbeat timeout if supplied, timestamp gaps, configured timeout, chart close handling, SDK error handling, reconnect reconciliation risk input. Missing: system clock drift and low disk warnings are not implemented; reconnect/backfill policy is not a full live ops loop. Recommended Phase 2: keep best-effort warnings as Medium unless safety behavior depends on them.
- Part M - contract rollover/symbol safety: partially implemented. Owner: `live_ops/bar_builder.py`, `live_ops/quality.py`, `live_chart_feed.py`, `docs\live_trading_readiness.md`. Evidence: active symbol/contract fields, no mix in bar builder, active contract mismatch and contract-mix blocks, chart instrument resolution. Missing: no rollover calendar automation/interface beyond explicit active-contract checks. Recommended Phase 2: add placeholder rollover policy only if needed by safety tests.
- Part N - session/calendar safety: partially implemented. Owner: `live_ops/risk.py`, `live_ops/quality.py`, `tests\test_live_ops.py`. Evidence: `SessionGuard`, outside-session risk rejection, missing session returns closed. Missing: monitor-only outside session and flatten-before-close behavior are not wired. Recommended Phase 2: add focused behavior if selected as high priority.
- Part O - operator console and chart status: partially implemented. Owner: `live_ops/operator.py`, `live_chart_feed.py`, `tests\test_live_chart_feed.py`. Evidence: operator line fields, chart topbar model unavailable/stale status, model overlay placeholder tests. Missing: live chart status uses fixed scaffold values for kill/risk/reconciliation rather than a real live decision loop. Recommended Phase 2: wire status from scaffold state only after decision loop scope is chosen.
- Part P - smoke-test CLI: implemented. Owner: `scripts\smoke_live_trading.py`, `live_ops/smoke.py`, `tests\test_live_ops.py`. Evidence: deterministic no-live-data smoke, paper override, bad OHLC, stale, duplicate timestamp, kill switch, oversize, max position, duplicate order, reconciliation, reconnect gap, contract mismatch, outside session, audit rows, status width. Missing: none for scaffold audit. Recommended Phase 2: keep smoke deterministic.
- Part Q - unit tests: partially implemented. Owner: `tests\test_live_ops.py`, `tests\test_live_chart_feed.py`, `tests\live\*`. Evidence: focused 47-test collect-only covers operator, timeout, bar builder, data quality, model/signal, risk, paper broker, reconciliation, audit, live broker placeholder, chart queue/timeframe/market behavior. Missing: no direct script-level tests for kill/cancel/flatten and no best-effort system-check tests. Recommended Phase 2: add only targeted tests for selected gaps.
- Part R - config: implemented. Owner: `configs\live_trading_safe.yaml`, `live_ops/schemas.py`. Evidence: `mode: disabled`, `allow_trading: false`, `allow_paper_trading: false`, `allow_live_broker: false`, low limits, stale/heartbeat thresholds, duplicate policy `block`, audit dir, kill switch file. Missing: none for safe defaults. Recommended Phase 2: preserve fail-closed defaults.
- Part S - documentation: implemented. Owner: `docs\live_trading_readiness.md`. Evidence: paper/smoke-only status, no real broker execution, smoke command, kill switch commands, paper scripts, go-live checklist, known limitations. Missing: doc is concise; system clock/disk and rollover automation remain known limitations. Recommended Phase 2: update docs only when implementation changes.

## Phase 1 safety-critical invariant check
- Chart UI does not submit orders: PASS by targeted search. `live_chart_feed.py` imports only `OperatorStatusState`/`print_operator_status` from `live_ops` and has no `PaperBroker`, `LiveBroker`, `OrderIntent`, or `place_order` path.
- No real broker SDK imports in audited live-ops scaffold: PASS by targeted search for IBKR/TWS/CQG/Rithmic/Tradovade/NinjaTrader tokens in the audit scope. One unrelated research cost config mentions Interactive Brokers fees, not live execution.
- No broker credentials/account IDs/broker env vars in audited scaffold: PASS by targeted search. Databento market-data auth exists and is not a broker execution credential.
- PaperBroker/SimBroker only: PASS. `live_ops\broker.py` implements `PaperBroker`; `LiveBroker.place_order` raises `NotImplementedError`; test proves it.
- Fail-closed defaults: PASS. `live_ops\schemas.py` and `configs\live_trading_safe.yaml` default `allow_trading=false`, `allow_paper_trading=false`, `allow_live_broker=false`, and `duplicate_timestamp_policy=block`.
- Tests/smoke finite or deterministic: PASS for focused audit surface. `tests\test_live_chart_feed.py` uses fake Databento/chart objects and finite `--timeout-seconds`; the prior deterministic clock hang fix is present.
- No validation path requires `--no-timeout`: PASS for audited focused validation. `--no-timeout` is only parsed/tested for CLI behavior and was not run.

## Phase 1 audit commands run
- `Get-Content -Raw -LiteralPath 'C:\Users\donny\.codex\attachments\18a72a94-bdc2-4796-bdfa-138e02f19daf\goal-objective.md'`
- `Get-Content -Raw -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\CODEX_HANDOFF.md'`
- `git status --short`
- `git diff --stat`
- `rg -n "live ops|live_chart|futures_intraday_model|CODEX_HANDOFF|Phase 0|Phase 1|safety scaffold|broker|pytest hang" 'C:\Users\donny\.codex\memories\MEMORY.md'`
- `rg --files live_ops scripts configs docs tests | rg "(live_ops|live_chart|live_trading|smoke_live_trading|kill_switch|paper_cancel|paper_flatten|alpha_tiered|test_live)"`
- Targeted `rg` inspections of audit-scope files for classes/functions/defaults/timeouts/broker paths.
- `Get-Content -Raw` for `live_ops\schemas.py`, `live_ops\quality.py`, `live_ops\risk.py`, `live_ops\broker.py`, `live_ops\bar_builder.py`, `live_ops\model.py`, `live_ops\reconciliation.py`, `live_ops\audit.py`, `live_ops\operator.py`, `live_ops\smoke.py`, scripts, config, and doc.
- Safety search for broker SDKs, broker credentials, order paths, timeouts, subprocess/chart blocking patterns.
- `python -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py --collect-only -q`
- `(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Phase 1 audit validation result
- Focused collect-only: PASS, 47 tests collected in 0.12s.
- Broad pytest was not run, per Phase 1 rules.

## Phase 1 recommended Phase 2 scope
- Highest priority: close Medium safety gaps that affect operator trust but do not add live execution: status wiring, selected data-quality/reconnect/rollover/session gaps, and direct tests for paper-only control scripts.
- Keep Phase 2 focused: no broker SDKs, no credentials, no real order path, no broad Parts A-S expansion, no generated artifact work.
- Stop Phase 2 when touched tests and focused live ops/chart tests pass under hard timeouts.

## Phase 2A core fail-closed safety gates
- Updated at UTC: 2026-06-22T04:29:53Z
- Scope: core fail-closed gates only. No real broker SDKs, broker credentials, account IDs, broker env vars, live order paths, production live trading, GUI/chart launch, broad pytest, generated artifact changes, or broad scaffold implementation were added.
- Read Phase 1 map in this handoff before editing. Starting repo state showed only `CODEX_HANDOFF.md` modified from the Phase 1 audit.
- Runtime behavior modules already enforced the Phase 2A defaults, so code changes were test-only.

## Phase 2A files changed
- `tests/test_live_ops.py`: added focused evidence for stale-bar blocking, safe-default fields, unsafe live mode / `allow_live_broker` blocking, and AST-based real broker SDK import absence across the live scaffold surface.
- `CODEX_HANDOFF.md`: recorded Phase 2A commands, results, remaining blockers, and recommended Phase 2B scope.

## Phase 2A commands run
- `Get-Content -Raw -LiteralPath 'C:\Users\donny\.codex\attachments\fb6ffde8-0c13-4e32-bdc5-fe307f86532a\pasted-text-1.txt'`
- `Get-Content -Raw -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\CODEX_HANDOFF.md'`
- `git status --short`
- `git diff --stat`
- Targeted `rg` inspections of `tests\test_live_ops.py`, `live_ops\schemas.py`, `live_ops\quality.py`, `live_ops\model.py`, `live_ops\risk.py`, `live_ops\broker.py`, and `configs\live_trading_safe.yaml`.
- `Get-Content -Raw -LiteralPath 'tests\test_live_ops.py'`
- `python -m pytest --help | Select-String -Pattern '--timeout'`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py -vv -s --tb=short --durations=20`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -vv -s --tb=short --durations=20`
- `git status --short`
- `git diff --stat`
- `git diff -- tests\test_live_ops.py`
- `(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Phase 2A validation results
- `pytest-timeout` was not available from `python -m pytest --help`; all pytest validation used the 120s PowerShell `Start-Job` / `Wait-Job` / `Stop-Job` wrapper.
- Touched tests: PASS, `tests\test_live_ops.py` collected 20 tests and passed in 0.33s.
- Focused live ops/chart gate: PASS, `tests\test_live_ops.py tests\test_live_chart_feed.py` collected 49 tests and passed in 1.20s.

## Phase 2A fail-closed evidence added
- Duplicate timestamp default remains BLOCK: existing test preserved in `tests\test_live_ops.py::test_data_quality_gate_blocks_bad_ohlc_and_duplicate_timestamp`.
- Bad OHLC blocks: existing test preserved in `tests\test_live_ops.py::test_data_quality_gate_blocks_bad_ohlc_and_duplicate_timestamp`.
- Stale bar blocks: added direct assertion for `DATA_STALE`.
- Model unavailable and missing features emit `NO_SIGNAL`: existing test preserved in `tests\test_live_ops.py::test_model_unavailable_and_feature_missing_emit_no_signal`.
- Partial bar is non-tradable by default: existing test preserved in `tests\test_live_ops.py::test_partial_bar_signal_is_non_tradable`.
- Default risk config rejects order intent and safe defaults are explicit: expanded `tests\test_live_ops.py::test_risk_blocks_by_default_and_paper_override_does_not_weaken_defaults`.
- Unsafe live mode and `allow_live_broker=true` are blocked: added `tests\test_live_ops.py::test_risk_blocks_live_mode_and_live_broker_flag`.
- No real broker SDK imports exist in the live scaffold surface: added `tests\test_live_ops.py::test_live_scaffold_has_no_real_broker_sdk_imports`.

## Phase 2A remaining Medium blockers
- Remaining deferred scaffold gaps by Part ID: A, C, D, F, G, H, I, J, K, L, M, N, O, Q.
- Phase 2A removed no Severe blockers because none were present; it strengthened focused evidence for the core fail-closed gates.

## Phase 2A recommended Phase 2B scope
- Send Phase 2B goal for paper broker, kill switch, reconciliation, and audit logging.
- Keep Phase 2B focused on the next safety layer: paper-only controls, reconciliation/audit state coverage, and touched tests under hard timeouts.
- Continue to avoid broker SDKs, credentials, real order paths, GUI/chart validation, broad scaffold completion, and generated artifact changes.

## Phase 2B paper broker, kill switch, reconciliation, audit logging
- Updated at UTC: 2026-06-22T04:37:23Z
- Scope: paper broker / sim behavior, paper-only control scripts, reconciliation, append-only audit logging, and focused tests only.
- No real broker SDKs, broker credentials, account IDs, broker env vars, live order paths, production live trading, chart/UI order path, GUI/chart launch, `--no-timeout`, broad pytest, or generated report/log/data modifications were added.
- Starting repo state had uncommitted `CODEX_HANDOFF.md` and `tests/test_live_ops.py` from prior Phase 1/2A work. Final status also showed an untracked `scripts/phase2_causal_base/build_higher_timeframe_bars.py`; this Phase 2B run did not create, edit, or remove it.
- The default smoke CLI was not run because `python scripts\smoke_live_trading.py` writes under `reports/live_trading_smoke/`; the smoke path is still covered through `run_smoke(..., audit_dir=tmp_path)` in the focused tests.

## Phase 2B files changed
- `live_ops/broker.py`: persisted paper open orders and fills in `PaperBroker.save/load` so paper-only scripts can operate on saved simulated state.
- `live_ops/reconciliation.py`: added optional represented open-order comparison and `OPEN_ORDER_MISMATCH` failure.
- `live_ops/audit.py`: added recursive redaction for sensitive audit field names before JSONL write.
- `tests/test_live_ops.py`: added/expanded focused coverage for safe-default broker rejection, persisted paper fills, paper control scripts, open-order reconciliation mismatch blocking risk, audit redaction, and existing no-real-broker/import/live-broker checks.
- `CODEX_HANDOFF.md`: recorded Phase 2B commands, results, remaining Medium blockers, and recommended Phase 2C scope.

## Phase 2B commands run
- `Get-Content -Raw -LiteralPath 'C:\Users\donny\.codex\attachments\aa0230bd-95bd-445f-bd0f-9e154aa9eccb\pasted-text-1.txt'`
- `Get-Content -Raw -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\CODEX_HANDOFF.md'`
- `git status --short`
- `git diff --stat`
- `Get-Content -Raw` for `live_ops\broker.py`, `live_ops\reconciliation.py`, `live_ops\audit.py`, and paper-control scripts.
- Targeted `rg` inspection of `tests\test_live_ops.py`.
- `python -m pytest --help | Select-String -Pattern '--timeout'`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py -vv -s --tb=short --durations=20`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -vv -s --tb=short --durations=20`
- `git status --short`
- `git diff --stat`
- `git diff -- live_ops\broker.py live_ops\reconciliation.py live_ops\audit.py tests\test_live_ops.py`
- `git diff --check -- live_ops\audit.py live_ops\broker.py live_ops\reconciliation.py tests\test_live_ops.py CODEX_HANDOFF.md`
- `(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Phase 2B validation results
- `pytest-timeout` was not available from `python -m pytest --help`; all pytest validation used the 120s PowerShell `Start-Job` / `Wait-Job` / `Stop-Job` wrapper.
- Touched tests: PASS, `tests\test_live_ops.py` collected 21 tests and passed in 0.37s.
- Focused live ops/chart gate: PASS, `tests\test_live_ops.py tests\test_live_chart_feed.py` collected 50 tests and passed in 1.42s.
- Touched-file whitespace check: PASS; only line-ending warnings were reported.

## Phase 2B safety evidence added
- Paper broker fill works only with approved paper risk: `PaperBroker.place_order` rejects safe-default/unapproved risk and fills approved paper order.
- Paper state persistence now includes positions, accepted order IDs, open orders, and fills; reload tests prove persisted fill/open-order behavior.
- Duplicate order ID rejection remains covered.
- Kill switch scripts affect a monkeypatched configured temp kill-switch file only.
- `paper_cancel_all.py` cancels persisted paper open orders in a temp state file.
- `paper_flatten_all.py` flattens persisted paper positions in a temp state file.
- Clean reconciliation passes; position mismatch fails; represented open-order mismatch fails and blocks RiskManager; stale open order warning remains `OK / STALE_OPEN_ORDER`.
- Audit logger writes newline-delimited JSON rows, preserves exception fields, and redacts sensitive fields such as `api_key` and nested `password`.
- Real broker SDK import absence and `LiveBroker.place_order` `NotImplementedError` checks remain covered.

## Phase 2B remaining Medium blockers
- Remaining deferred scaffold gaps by Part ID: A, C, D, F, G, H, I, J, K, L, M, N, O, Q.
- Phase 2B improved H, I, J, K, and Q, but broader optional behavior remains deferred: cancel/flatten-on-kill config action, next-bar fill policy, full runtime audit integration, audit-state reconciliation, best-effort system checks, session/contract/reconnect expansion, and operator status wiring.

## Phase 2B recommended Phase 2C scope
- Send Phase 2C goal for remaining safety gaps in session/calendar behavior, contract/rollover safety, reconnect/backfill handling, and operator status wiring.
- Keep Phase 2C focused, paper/sim only, and stop when touched tests and the focused live ops/chart gate pass under hard timeouts.
- Continue to avoid broker SDKs, credentials, real order paths, GUI/chart validation, generated artifact changes, and broad scaffold completion.

## Phase 2C session, contract, reconnect, operator status layer
- Updated at UTC: 2026-06-22T04:48:27Z
- Scope: session/calendar fail-closed evidence, contract/symbol mismatch evidence, reconnect/gap/stale-feed fail-closed evidence, operator status rendering/state display, and focused tests only.
- No broker SDKs, broker credentials, account IDs, broker env vars, live order paths, production live trading, chart/UI order path, GUI/chart launch, `--no-timeout`, broad pytest, or generated report/log/data modifications were added.
- The older interrupted-goal recovery objective file was read as context only. This run followed the active Phase 2C goal and kept validation finite.
- The default smoke CLI was not run because `python scripts\smoke_live_trading.py` writes under `reports/live_trading_smoke/`; the smoke path remains covered through `run_smoke(..., audit_dir=tmp_path)` in the focused tests.

## Phase 2C files changed
- `live_ops/operator.py`: status renderer now displays both root symbol and active contract as `symbol/contract` when both are available, preserving the single-token display when they match.
- `tests/test_live_ops.py`: added/expanded focused coverage for operator fields, mixed-contract bar windows, active-contract mismatch risk blocking, missing session config risk blocking, stale heartbeat risk blocking, reconnect reconciliation gating, reconnect timestamp gap and duplicate timestamp blocking, and chart/status no-order-path assertions.
- `CODEX_HANDOFF.md`: recorded Phase 2C commands, results, remaining Medium blockers, recommended Phase 3 scope, and updated requirement map.

## Phase 2C commands run
- `Get-Content -LiteralPath 'C:\Users\donny\.codex\attachments\10b205c7-cc5c-419c-a58c-81e00f2e6c12\goal-objective.md'`
- `Get-Content -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\CODEX_HANDOFF.md' -Tail 180`
- `git status --short`
- `git status --short --untracked-files=all`
- `git diff --stat`
- `git diff --cached --stat`
- Targeted `rg` and `Get-Content` inspection of `live_ops\risk.py`, `live_ops\quality.py`, `live_ops\bar_builder.py`, `live_ops\operator.py`, `live_ops\schemas.py`, `live_chart_feed.py`, `tests\test_live_ops.py`, and `tests\test_live_chart_feed.py`.
- `git diff -- live_ops\operator.py tests\test_live_ops.py`
- `python -m pytest --help | Select-String -Pattern '--timeout'`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py -vv -s --tb=short --durations=20`
- PowerShell job wrapper rerun after fixing a too-narrow test assertion: `python -X faulthandler -m pytest tests\test_live_ops.py -vv -s --tb=short --durations=20`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -vv -s --tb=short --durations=20`
- `git diff --check -- live_ops\operator.py tests\test_live_ops.py CODEX_HANDOFF.md`
- `(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Phase 2C validation results
- `pytest-timeout` was not available from `python -m pytest --help`; all pytest validation used the 120s PowerShell `Start-Job` / `Wait-Job` / `Stop-Job` wrapper.
- First touched-test attempt: FAIL, `tests\test_live_ops.py::test_operator_status_rendering_width` used `width=180` and truncated the final `err=DATA_STALE` field. The test width was corrected; no runtime logic changed for that failure.
- Final touched tests: PASS, `tests\test_live_ops.py` collected 28 tests and passed in 0.42s.
- Focused live ops/chart gate: PASS, `tests\test_live_ops.py tests\test_live_chart_feed.py` collected 57 tests and passed in 1.29s.
- Touched-file whitespace check: PASS; only line-ending warnings were reported.

## Phase 2C safety evidence added
- Operator status rendering shows feed status, root symbol and active contract, timeframe, row count, latest bar time, latest age, close, model status, signal, trading mode, kill switch, risk status, reconciliation status, paper position, and last error code within bounded width.
- Missing session config fails closed through both `SessionGuard`-backed risk approval and `DataQualityGate` session checks.
- Active-contract mismatch now has direct data-quality and risk-layer assertions for `CONTRACT_MISMATCH` / `DATA_QUALITY_CONTRACT_MISMATCH`.
- Mixed contract updates inside one live bar builder window raise before producing a mixed bar.
- Stale heartbeat blocks at data quality and propagates to `DATA_QUALITY_HEARTBEAT_STALE` at risk.
- Reconnect approval is blocked until the explicit reconnect reconciliation flag is true and reconciliation status is `OK`; the positive path remains paper-only approval.
- Timestamp gaps and duplicate timestamps after reconnect-style sequences both fail closed at risk. Duplicate timestamp policy remains `block`.
- Chart/status path is statically asserted to have no `live_ops.broker` import, no `place_order` attribute call, and no `PaperBroker`/`LiveBroker`/`OrderIntent` usage.
- No real broker SDK import test remains covered across the live scaffold surface.

## Phase 2C requirement map update
- No Severe blockers remain in the focused live-ops/chart scaffold gate.
- Core Phase 2C safety layer is now covered: session fail-closed behavior, contract mismatch/mix behavior, reconnect/gap/stale heartbeat behavior, operator status fields, and chart no-order-path assertions.
- Parts D, G, L, M, N, O, and Q were improved by Phase 2C. Their core fail-closed checks are no longer unresolved for this phase, but broader production-depth items below remain deferred Medium work.

## Phase 2C remaining Medium blockers
- Remaining deferred scaffold gaps by Part ID: A, C, F, H, I, J, K, L, M, N, O, Q.
- A: explicit debug/verbose logging mode remains minimal.
- C: full historical/live data contract coverage for sessions, rollover policy, no-trade intervals, and model feature exclusion remains incomplete.
- F: imputer/scaler object integration is still represented by readiness flags, not concrete model artifact adapters.
- H: optional cancel/flatten-on-kill config action is not wired as a runtime behavior.
- I: next-bar-open paper fill policy and direct broker audit append remain deferred.
- J: audit-state reconciliation remains minimal.
- K: full runtime audit integration and fsync/atomic durability hardening remain deferred.
- L: system clock drift, low disk warnings, and full reconnect/backfill policy remain deferred.
- M: rollover calendar automation/interface remains deferred beyond explicit active-contract checks.
- N: monitor-only outside session and flatten-before-close runtime behavior remain deferred.
- O: live chart status still displays scaffold status values rather than a full decision-loop state feed.
- Q: best-effort system-check tests/scripts remain deferred.

## Phase 2C recommended Phase 3 scope
- Send Phase 3 goal for broader production-readiness gaps only after accepting the Phase 2A/2B/2C focused safety gates.
- Prioritize a finite, non-GUI, paper/sim-only decision-loop integration that wires runtime audit rows and operator status from real scaffold state without adding live broker execution.
- Keep Phase 3 validations hard-timeout wrapped; do not run broad pytest until touched and focused live ops/chart gates pass.

## Phase 3 finite paper/sim decision-loop integration
- Updated at UTC: 2026-06-22T04:59:48Z
- Scope: finite, deterministic, non-GUI, paper/sim-only decision-loop integration and focused tests only.
- No broker SDKs, broker credentials, account IDs, broker env vars, live order paths, production live trading, chart/UI order path, GUI/chart launch, `--no-timeout`, broad pytest, or tracked generated report/log/data modifications were added.
- The smoke CLI writes `reports/live_trading_smoke/audit.jsonl`; `reports/` and `*.jsonl` are ignored. This is the explicitly allowed finite smoke output path.
- `scripts\phase2_causal_base\build_higher_timeframe_bars.py` still exists and was not modified.

## Phase 3 files changed
- `live_ops/smoke.py`: hardened the smoke path into a single finite decision-cycle runner that executes data quality, model readiness, signal state, risk, paper broker, reconciliation, audit row, and operator status for each scenario.
- `scripts/smoke_live_trading.py`: added repo-root import bootstrap, `--audit-dir`, and `--force-failure` CLI support while keeping the default command finite and non-GUI.
- `tests/test_live_ops.py`: expanded smoke tests to verify audit row shape/count, decision-loop operator status, default safe rejection, explicit paper fill, exception fail-closed logging, and CLI zero/nonzero behavior.
- `CODEX_HANDOFF.md`: recorded Phase 3 commands, results, remaining Medium blockers, recommended Phase 4 scope, and updated requirement map.

## Phase 3 commands run
- `Get-Content -LiteralPath 'C:\Users\donny\.codex\attachments\06f71253-960b-4a6a-93f5-e07b1aa4ec20\pasted-text-1.txt'`
- `git status --short --untracked-files=all`
- `git diff --stat`
- `Get-Content -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\CODEX_HANDOFF.md' -Tail 140`
- Targeted `rg` and `Get-Content` inspection of `live_ops\smoke.py`, `scripts\smoke_live_trading.py`, `tests\test_live_ops.py`, `live_ops\schemas.py`, `live_ops\broker.py`, `live_ops\audit.py`, and `live_ops\reconciliation.py`.
- `python -m py_compile live_ops\smoke.py scripts\smoke_live_trading.py tests\test_live_ops.py`
- `python -m pytest --help | Select-String -Pattern '--timeout'`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py -vv -s --tb=short --durations=20`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -vv -s --tb=short --durations=20`
- `python scripts\smoke_live_trading.py`
- `git diff --check -- live_ops\smoke.py scripts\smoke_live_trading.py tests\test_live_ops.py CODEX_HANDOFF.md live_ops\operator.py`
- `Test-Path -LiteralPath 'scripts\phase2_causal_base\build_higher_timeframe_bars.py'`
- `(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Phase 3 validation results
- `pytest-timeout` was not available from `python -m pytest --help`; all pytest validation used the 120s PowerShell `Start-Job` / `Wait-Job` / `Stop-Job` wrapper.
- Compile check: PASS, `python -m py_compile live_ops\smoke.py scripts\smoke_live_trading.py tests\test_live_ops.py`.
- First actual smoke CLI attempt: FAIL before scenario execution because `python scripts\smoke_live_trading.py` could not import `live_ops` from the script directory. Fixed by bootstrapping repo root into `sys.path`.
- Final touched tests: PASS, `tests\test_live_ops.py` collected 29 tests and passed in 0.44s.
- Final focused live ops/chart gate: PASS, `tests\test_live_ops.py tests\test_live_chart_feed.py` collected 58 tests and passed in 1.31s.
- Final deterministic smoke CLI: PASS, `python scripts\smoke_live_trading.py` reported `PASS live trading smoke scenarios=26 decision_cycles=26 audit_rows=26`.
- Touched-file whitespace check: PASS; only line-ending warnings were reported.

## Phase 3 safety evidence added
- Finite smoke runner uses deterministic synthetic bars/signals and requires no Databento credentials, broker credentials, chart, GUI, broker SDK, or live broker path.
- Every completed smoke decision cycle writes exactly one JSONL audit row with nullable `exception`, `operator_status`, `operator_status_line`, data quality, model, signal, risk, broker response, reconciliation, positions, and open orders.
- Operator status in smoke now reflects actual decision-loop state, including paper fill position `ES:ESU6=1`, current signal, risk reason, reconciliation reason, and error code.
- Default safe config remains disabled/fail-closed; explicit paper override is required for deterministic paper fill.
- Smoke scenarios cover missing model output, missing features, disabled trading, paper fill, operator kill switch, operator trading disabled, operator pause new entries, bad OHLC, stale bar, stale heartbeat, duplicate timestamp, kill switch, oversize, duplicate order ID, reconciliation mismatch, reconnect timestamp gap, reconnect pending/cleared, contract mismatch, outside session, missing session config, unsafe live mode, and forced exception fail-closed audit logging.
- `scripts\smoke_live_trading.py --force-failure` returns nonzero in focused tests without changing the safe default smoke behavior.
- Existing no-real-broker-SDK and chart/status no-order-path tests remain covered in the focused gate.

## Phase 3 requirement map update
- No Severe blockers remain in the focused live-ops/chart scaffold gate or finite smoke CLI.
- Phase 3 completed the requested finite, deterministic, non-GUI, paper/sim-only decision-loop integration path.
- Parts K, O, and Q were improved by Phase 3 through full smoke audit rows, decision-loop-derived operator status, CLI coverage, forced failure coverage, and focused tests.
- Remaining items below are broader production-depth gaps, not blockers for the Phase 3 paper/sim smoke objective.

## Phase 3 remaining Medium blockers
- Remaining deferred scaffold gaps by Part ID: A, C, F, H, I, J, K, L, M, N, O, Q.
- A: explicit debug/verbose logging mode remains minimal.
- C: full historical/live data contract coverage for sessions, rollover policy, no-trade intervals, and model feature exclusion remains incomplete outside smoke/parity checks.
- F: imputer/scaler object integration is still represented by readiness flags, not concrete model artifact adapters.
- H: optional cancel/flatten-on-kill config action is not wired as a runtime behavior.
- I: next-bar-open paper fill policy and direct broker-owned audit append remain deferred.
- J: audit-state reconciliation remains minimal.
- K: finite smoke audit integration exists, but fsync/atomic durability hardening and broader runtime durability remain deferred.
- L: system clock drift, low disk warnings, and full reconnect/backfill policy remain deferred.
- M: rollover calendar automation/interface remains deferred beyond explicit active-contract checks.
- N: monitor-only outside session and flatten-before-close runtime behavior remain deferred.
- O: finite smoke operator status uses decision-loop state, but live chart status is still not wired to a full live decision-loop state feed.
- Q: focused tests cover the Phase 3 path, but bounded broader validation and best-effort system-check tests/scripts remain deferred.

## Phase 3 recommended Phase 4 scope
- Send Phase 4 validation/docs goal to run bounded broader validation, inspect ignored generated smoke output hygiene, and update readiness documentation to reflect the completed finite paper/sim decision-loop path.
- Keep Phase 4 paper/sim only; do not add live broker SDKs, credentials, live order paths, GUI/manual chart validation, or production go-live behavior.
- Stop Phase 4 with a final scaffold status that separates completed safety gates from remaining Medium production-depth gaps.

## Phase 4 bounded validation, readiness docs, final scaffold status
- Updated at UTC: 2026-06-22T05:08:07Z
- Scope: validation and documentation for the current paper/smoke scaffold only.
- No broker SDKs, broker credentials, account IDs, broker env vars, live order paths, production live trading, chart/UI order path, GUI/chart launch, `--no-timeout`, or tracked generated report/log/data modifications were added.
- The smoke CLI wrote ignored output under `reports/live_trading_smoke/`. `git status --short --ignored -- reports\live_trading_smoke\audit.jsonl` reported `!! reports/live_trading_smoke/`.
- `scripts\phase2_causal_base\build_higher_timeframe_bars.py` still exists and was not modified.
- No commit was created; repo policy says not to commit unless explicitly asked.

## Phase 4 files changed
- `docs/live_trading_readiness.md`: updated current status, validation commands, smoke commands, paper control commands, smoke scenario coverage, known limitations, remaining Medium blockers, skipped chart validation reason, broad validation status, and go-live checklist.
- `CODEX_HANDOFF.md`: recorded Phase 4 commands, validation results, smoke result, chart command skip, final scaffold status, remaining blockers, and recommended next step.

## Phase 4 commands run
- `Get-Content -LiteralPath 'C:\Users\donny\.codex\attachments\61f8a267-ad2f-4839-bb98-0f0258be1a2f\pasted-text-1.txt'`
- `git status --short --untracked-files=all`
- `git diff --stat`
- `Get-Content -LiteralPath 'C:\Users\donny\Desktop\futures_intraday_model\CODEX_HANDOFF.md' -Tail 160`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -vv -s --tb=short --durations=20`
- `python scripts\smoke_live_trading.py`
- PowerShell job wrapper: `python -X faulthandler -m pytest tests -q --tb=short --durations=20`
- `git diff --check`
- `rg -n "chart_factory|\.show\(|DATABENTO_API_KEY|db_module\.Live|block_for_close|--timeout-seconds" live_chart_feed.py tests\test_live_chart_feed.py`
- `git status --short --ignored -- reports\live_trading_smoke\audit.jsonl`
- `rg -n "ib_insync|ibapi|InteractiveBrokers|TWS|CQG|Rithmic|Tradovate|NinjaTrader|broker credential|account_id|api_key|secret|password" .`
- `rg -n "ib_insync|ibapi|InteractiveBrokers|TWS|CQG|Rithmic|Tradovate|NinjaTrader" live_ops scripts tests live_chart_feed.py docs configs`
- `rg -n "from live_ops\.broker|PaperBroker|LiveBroker|OrderIntent|place_order" live_chart_feed.py live_ops scripts tests\test_live_ops.py`
- Targeted `Get-Content` inspection of `docs\live_trading_readiness.md` and `live_chart_feed.py`
- `Test-Path -LiteralPath 'scripts\phase2_causal_base\build_higher_timeframe_bars.py'`
- `(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Phase 4 validation results
- Focused live ops/chart gate: PASS, `tests\test_live_ops.py tests\test_live_chart_feed.py` collected 58 tests and passed in 1.28s.
- Deterministic smoke CLI: PASS, `python scripts\smoke_live_trading.py` reported `PASS live trading smoke scenarios=26 decision_cycles=26 audit_rows=26`.
- Broad bounded pytest: FAIL outside the live scaffold, `2 failed, 712 passed, 58 warnings in 99.09s`.
- Broad failures:
  - `tests/phase8_model_selection/test_audit_event_level_edge_feasibility.py::test_event_level_audit_selects_non_overlapping_events`: expected `current_policy_traded_rows == 4`, actual `3`.
  - `tests/phase8_model_selection/test_audit_event_level_edge_feasibility.py::test_event_level_audit_fails_closed_without_target_windows`: expected `SystemExit` message matching `policy frame missing required diagnostic columns`, actual `policy executable signals missing target_entry_ts/target_exit_ts: 4`.
- Touched-file whitespace/static diff check: PASS; only CRLF warnings were reported.
- Generated smoke output hygiene: PASS for this phase; smoke output stayed under ignored `reports/live_trading_smoke/`.

## Phase 4 chart command result
- Skipped `python .\live_chart_feed.py --timeout-seconds 10`.
- Reason: `run_live_chart` constructs a chart and calls `show_chart(chart)` before live subscription; `show_chart` calls `show(block=False)` when available. This phase forbids opening a blocking GUI/chart, and the command also depends on live Databento chart/feed setup rather than the finite paper/smoke scaffold.
- Replacement evidence: focused chart tests passed using fake chart and Databento objects, and static tests still assert chart/status has no broker placement path.

## Phase 4 static safety results
- No real broker SDK imports were found in the live scaffold targeted search. Hits for `ibapi`/`ib_insync` were only blocked-token strings in `tests/test_live_ops.py`.
- `live_chart_feed.py` has no `from live_ops.broker` import, no `PaperBroker`, no `LiveBroker`, no `OrderIntent`, and no `place_order` path in the targeted order-path search.
- Broad secret/credential search hits were Databento market-data auth references, documentation/checklist text, audit redaction marker names, test fixture strings, and generated build metadata. No broker credential/account/live order path was added by this work.

## Phase 4 final scaffold status
- Current scaffold status: paper/smoke only.
- Production live trading status: not implemented.
- Real broker execution status: disabled; `LiveBroker.place_order` raises `NotImplementedError`.
- Chart/UI order status: no chart/status broker placement path in targeted static search and focused tests.
- Focused safety gate: passing.
- Deterministic paper/smoke decision loop: passing.
- Readiness documentation: updated.
- Broad repo validation: not fully green because of unrelated Phase 8 model-selection test failures listed above.

## Phase 4 remaining Medium blockers
- Remaining production-depth scaffold gaps by Part ID: A, C, F, H, I, J, K, L, M, N, O, Q.
- A: explicit debug/verbose logging mode remains minimal.
- C: full historical/live data contract coverage for sessions, rollover policy, no-trade intervals, and model feature exclusion remains incomplete outside smoke/parity checks.
- F: imputer/scaler object integration is still represented by readiness flags, not concrete model artifact adapters.
- H: optional cancel/flatten-on-kill config action is not wired as runtime behavior.
- I: next-bar-open paper fill policy and direct broker-owned audit append remain deferred.
- J: audit-state reconciliation remains minimal.
- K: finite smoke audit integration exists, but fsync/atomic durability hardening and broader runtime durability remain deferred.
- L: system clock drift, low disk warnings, and full reconnect/backfill policy remain deferred.
- M: rollover calendar automation/interface remains deferred beyond explicit active-contract checks.
- N: monitor-only outside session and flatten-before-close runtime behavior remain deferred.
- O: finite smoke operator status uses decision-loop state, but live chart status is not wired to a full live decision-loop state feed.
- Q: focused tests cover the paper/smoke path, but best-effort system-check tests/scripts remain deferred.
- Chart command validation was skipped because it would open chart UI.
- Broad validation has two unrelated Phase 8 model-selection failures; focused live-ops/chart validation and smoke pass.

## Phase 4 recommended next step
- Review final scaffold status and decide whether to commit Phase 0-4 work.
- If committing, keep generated/ignored smoke output untracked and do not stage ignored `reports/`, caches, logs, or data artifacts.
- If continuing implementation instead of committing, next useful scope is a separate production-depth cleanup goal for selected Medium blockers, still without live broker execution.

## Operator controls scaffold slice
- Updated at UTC: 2026-06-22T05:18:32Z
- Scope: paper/smoke-only operator control state and local JSON control source for preventing new paper order submissions.
- What changed: added operator control state/decision loading and evaluation; wired smoke decision cycles to block broker submission after existing risk approval when kill switch, trading disabled, pause-new-entries, or malformed control input applies; added audit/status fields and focused tests.
- Files changed by this slice: `live_ops/operator.py`, `live_ops/smoke.py`, `tests/test_live_ops.py`, `CODEX_HANDOFF.md`.
- Commands run: `python -m py_compile live_ops\operator.py live_ops\smoke.py`; `python -m pytest tests\test_live_ops.py -q -p no:cacheprovider`; `python -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -q -p no:cacheprovider`; `git diff --check`; `git status --short`.
- Test results: PASS, `tests\test_live_ops.py` collected 30 tests; PASS, `tests\test_live_ops.py tests\test_live_chart_feed.py` collected 59 tests; `git diff --check` reported only CRLF warnings.
- Remaining work: no broker cancel-all, flatten-all, live broker integration, or real order path was added.
- Next recommended step: included in the commit gate after reviewing the expected Phase 0-4 scaffold files and rerunning focused validation.

## Live/OHLCV parity and model readiness hardening
- Updated at UTC: 2026-06-22T05:52:48Z
- Scope: Part C historical/live OHLCV parity and Part F model readiness, paper/smoke-only.
- What changed: parity results now expose missing/extra columns, dtype mismatches, UTC timezone status, final/partial-bar status, ordered expected columns, and default mixed-contract-window blocking; model readiness results now expose observed feature order.
- Files changed by this slice: `live_ops/bar_builder.py`, `live_ops/model.py`, `live_ops/schemas.py`, `tests/test_live_ops.py`, `CODEX_HANDOFF.md`.
- Commands run: read goal objective file; `git status --short --untracked-files=all`; `git log -2 --oneline`; `git diff --stat`; `python -m py_compile live_ops\schemas.py live_ops\bar_builder.py live_ops\model.py tests\test_live_ops.py`; PowerShell job wrapper for `python -X faulthandler -m pytest tests\test_live_ops.py -vv -s --tb=short --durations=20`; PowerShell job wrapper for `python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -q`; PowerShell job wrapper for `python scripts\smoke_live_trading.py`; PowerShell job wrapper for `python -X faulthandler -m pytest tests -q --tb=short --durations=20`; `git diff --check`; `git status --short --untracked-files=all`.
- Test results: PASS, compile; PASS, focused live ops `33 passed`; PASS, live-ops sanity `62 passed`; PASS, smoke CLI `PASS live trading smoke scenarios=26 decision_cycles=26 audit_rows=26`; PASS, broad bounded pytest `718 passed, 58 warnings`; PASS, `git diff --check` with CRLF warnings only.
- Remaining work: no broker SDKs, credentials, GUI/chart launch, live order paths, generated artifact staging, or model research output changes were added.
- Next recommended step: select the next scoped live-ops production-depth part, likely Part A/O operator console polish or Part L/M/N runtime failure guards.

## Runtime failure, contract, and session safety guards
- Updated at UTC: 2026-06-22T06:35:22Z
- Scope: Part L runtime/connectivity/process guards, Part M contract/symbol safety, and Part N session/calendar safety; paper/smoke-only.
- What changed: added audit preflight, structured session check results, explicit feed/heartbeat/reconnect-backfill/root-symbol runtime data-quality guards, risk blocks for active symbol/contract and monitor-only state, and smoke coverage for disconnect, no heartbeat, reconnect backfill, closed/missing sessions, root/contract mismatch, feature/model/broker exceptions, and audit preflight failure.
- Files changed by this slice: `live_ops/audit.py`, `live_ops/quality.py`, `live_ops/risk.py`, `live_ops/smoke.py`, `tests/test_live_ops.py`, `CODEX_HANDOFF.md`.
- Commands run: read goal objective file; `git status --short --untracked-files=all`; `git log -3 --oneline`; `git diff --stat`; `python -m py_compile live_ops\audit.py live_ops\quality.py live_ops\risk.py live_ops\smoke.py tests\test_live_ops.py`; PowerShell job wrapper for `python -X faulthandler -m pytest tests\test_live_ops.py -vv -s --tb=short --durations=20`; PowerShell job wrapper for `python -X faulthandler -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -q`; PowerShell job wrapper for `python scripts\smoke_live_trading.py`; PowerShell job wrapper for `python -X faulthandler -m pytest tests -q --tb=short --durations=20`; `git diff --check`; `git status --short --untracked-files=all`.
- Test results: PASS, compile; PASS, focused live ops `36 passed`; PASS, live-ops sanity `65 passed`; PASS, smoke CLI `PASS live trading smoke scenarios=34 decision_cycles=34 audit_rows=34`; PASS, broad bounded pytest `721 passed, 58 warnings`; PASS, `git diff --check` with CRLF warnings only.
- Remaining work: no broker SDKs, credentials, GUI/chart launch, live order paths, generated artifact staging, or production live trading behavior were added.
- Next recommended step: choose the next remaining live-ops part, likely Part A/O operator console polish or Part H/I/J/K operational controls depth.

## Order-intent safety gate
- Updated at UTC: 2026-06-22T08:14:15Z
- Scope: paper/smoke-only decision/order-intent scaffold gate before broker submission.
- What changed: added `OrderIntentDecision` and a broker-agnostic operator gate that returns either a validated `OrderIntent` or a blocked decision with reason code for operator controls, disabled/live mode, malformed prediction payloads, unsupported symbols/contracts, invalid quantities, stale bars, flat/no-signal, and below-threshold confidence.
- Files changed by this slice: `live_ops/operator.py`, `live_ops/schemas.py`, `tests/test_live_ops.py`, `CODEX_HANDOFF.md`.
- Tests run: `python -m pytest tests\test_live_ops.py -q -p no:cacheprovider`; `python -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -q -p no:cacheprovider`; `git diff --check`.
- Test results: PASS, focused live ops `40 passed`; PASS, live-ops/chart `69 passed`; PASS, `git diff --check` with CRLF warnings only.
- Deferred: broker submit, cancel-all, flatten-all, live account integration, production risk sizing, broker SDKs, credentials, GUI/chart launch, and generated artifact staging.

## Broker-agnostic risk preflight gate
- Updated at UTC: 2026-06-22T08:21:42Z
- Scope: paper/smoke-only pre-routing risk/limits scaffold after validated order-intent creation.
- What changed: added `OrderPreflightResult` and `preflight_order_intent`, which accepts or blocks an `OrderIntentDecision` without broker submission or broker state mutation. The gate checks upstream intent status, kill switch, trading/live mode, allowed symbols/contracts, side, quantity, max order size, optional open-order/duplicate/cooldown guards, and projected symbol/total position limits.
- Files changed by this slice: `live_ops/risk.py`, `live_ops/schemas.py`, `tests/test_live_ops_preflight.py`, `CODEX_HANDOFF.md`.
- Commands run: `python -m pytest tests\test_live_ops_preflight.py -q -p no:cacheprovider`; `python -m pytest tests\test_live_ops.py -q -p no:cacheprovider`; `python -m pytest tests\test_live_ops.py tests\test_live_chart_feed.py -q -p no:cacheprovider`; `git diff --check`.
- Test results: PASS, preflight `5 passed`; PASS, focused live ops `41 passed`; PASS, live-ops/chart `71 passed`; PASS, `git diff --check` with CRLF warnings only.
- Deferred: broker submit, cancel-all, flatten-all, account balance/margin integration, production sizing, live account integration, broker SDKs, credentials, GUI/chart launch, and generated artifact staging.
