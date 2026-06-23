# Codex Handoff

- Updated at UTC: 2026-06-23T06:44:35Z
- Purpose: current-state handoff after live chart timing/state diagnostics.
- Repo: `C:\Users\donny\Desktop\futures_intraday_model`
- Pre-run worktree check: `git status --short` was clean.
- This handoff now includes the prior Tier 1 Phase 4 evidence restoration, WFA prediction artifact reconciliation, Databento live chart fallback fix, WFA prerequisite refresh blocker, Phase 5 feature-manifest gate policy fix, data-audit universe guard fix, guarded split-plan refresh, live chart timeframe switcher fix, live chart lag/data-flow fix, and the current live chart timing/state diagnostics. No cleanup, staging, commit, move, delete, redownload, DBN/source mutation, Phase 1-4 rebuild, Phase 7/8 run, WFA prediction generation, or generated artifact staging was run in this pass.

## Latest run: Live chart timing/state diagnostics

### What changed

- Added default-on `stderr` timing markers for chart launch/show, Databento dataset range lookup, symbology resolve, historical fetch/cache hits, first historical render, live subscribe/start, timeframe switch render, and market switch render.
- Replaced generic chart loading status text with explicit topbar states: `Resolving`, `Backfilling`, `Rendering`, `Connecting`, `Live`, `Historical-only`, `Reconnecting`, and `Stale`.
- Kept existing render/backfill/data semantics unchanged; this pass did not add latest-first backfill, incremental candle rendering, DNS/TCP preflight, or retry/backoff.
- Updated the live-connectivity fallback after historical backfill so the chart shows `Historical-only` instead of appending a generic live-unavailable suffix.

### Files changed

- `live_chart_feed.py`
- `tests/test_live_chart_feed.py`
- `CODEX_HANDOFF.md`

### Commands run

- `Get-Location`
- `git status --short`
- `Get-Content CODEX_HANDOFF.md -TotalCount 120`
- Targeted `rg` and `Get-Content` reads for live chart status, timing, rendering, switching, and tests
- `python -m pytest tests/test_live_chart_feed.py tests/live/test_live_chart_lightweight.py`
- `git diff -- live_chart_feed.py tests/test_live_chart_feed.py`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`

### Test results

- `python -m pytest tests/test_live_chart_feed.py tests/live/test_live_chart_lightweight.py`: `41 passed in 1.99s`

### Remaining work

- Manual visible-chart verification is still needed to confirm the new timing logs and topbar states during real Databento startup, timeframe switch, market switch, and live-connectivity fallback.
- Next performance scope remains render optimization: latest-first historical display and incremental latest-candle update instead of full re-render where possible.

## Latest run: Live chart lag/data-flow fix

### What changed

- Kept unrelated WFA files untouched.
- Reworked live chart display state so `raw_candles` remains canonical 1-minute source data while displayed timeframes are derived from that source.
- Added a per-timeframe in-memory render cache and invalidated it only when source candles change.
- Changed historical backfill loading to store 1-minute candles instead of storing already-aggregated display candles, so switching down from `4h` to `1m` keeps true 1-minute detail.
- Changed live trade aggregation to always build 1-minute source candles, independent of the selected display timeframe.
- Added an in-memory market runtime cache for resolved instrument and historical 1-minute source candles, so switching back to a previously loaded market avoids another historical backfill request.
- Moved chart creation/show before Databento dataset range lookup, symbology resolution, and backfill loading, with a resolving status while Databento work continues.

### Files changed

- `live_chart_feed.py`
- `tests/test_live_chart_feed.py`
- `CODEX_HANDOFF.md`

Unrelated dirty WFA files were preserved.

### Commands run

- `Get-Location`
- `git status --short`
- `Get-Content -TotalCount 140 CODEX_HANDOFF.md`
- Targeted `rg` and `Get-Content` reads for live chart rendering, switching, startup, and tests
- `python -m pytest tests/test_live_chart_feed.py tests/live/test_live_chart_lightweight.py`
- `git diff -- live_chart_feed.py tests/test_live_chart_feed.py`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`

### Test results

- First focused run failed because the new cache test's synthetic market-switch event was blocked by the existing market-switch debounce.
- Second focused run failed because the second synthetic switch was still inside the debounce window.
- Final focused run passed:
  - `python -m pytest tests/test_live_chart_feed.py tests/live/test_live_chart_lightweight.py`: `40 passed in 2.38s`

### Remaining work

- Manual visible-chart verification still needed for perceived startup, market-switch, and timeframe-switch responsiveness.
- Expected cause summary: timeframe switch lag was code/data-flow; first-load market switch lag is code plus Databento network; `.exe` to chart-open lag is Python/lightweight-charts cold start plus previous Databento pre-chart work; PC hardware may affect DataFrame/render speed but is not the primary diagnosis.

## Previous run: Live chart timeframe switcher fix

### What changed

- Confirmed `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, and `1d` were still present in `SUPPORTED_CHART_TIMEFRAMES`.
- Removed the runtime filter that hid chart switcher options below the currently selected/persisted timeframe. A persisted `4h` selection no longer hides `1m`, `5m`, `15m`, `30m`, or `1h`.
- Updated the fake topbar test helper to retain switcher options and asserted a persisted `4h` selection still exposes all supported chart timeframes.

### Files changed

- `live_chart_feed.py`
- `tests/test_live_chart_feed.py`
- `CODEX_HANDOFF.md`

Unrelated dirty WFA files were preserved.

### Commands run

- `Get-Location`
- `git status --short`
- `Get-Content -TotalCount 80 CODEX_HANDOFF.md`
- Targeted `rg` and `Get-Content` reads for live chart timeframe handling and tests
- Persisted state read from `%LOCALAPPDATA%\futures_intraday_model\live_chart_feed_state.json`
- `python -m pytest tests/test_live_chart_feed.py tests/live/test_live_chart_lightweight.py`
- `git diff -- live_chart_feed.py tests/test_live_chart_feed.py`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`

### Test results

- `python -m pytest tests/test_live_chart_feed.py tests/live/test_live_chart_lightweight.py`: `38 passed in 1.39s`

### Remaining work

- Reopen the live chart and verify the topbar offers all supported timeframes while the currently selected/persisted timeframe remains selected.

## Previous run: Phase 5 data-audit universe guard fix

### What changed

- Updated `scripts/validation/data_audit_universe_guard.py` so OHLCV caveat final decisions are accepted only when the data-audit universe row is explicitly `audit_status="usable"` and `usable_for_wfa=true`.
- Kept strict blocking for missing rows, non-`PASS` universe status, `usable_for_wfa=false`, `quarantined`/`diagnostic_only` audit statuses, and `keep_quarantined_ohlcv_only_evidence_insufficient`.
- Added focused guard and Phase 5 tests for the accepted caveat case and fail-closed cases.
- Reran the guarded Tier 1 split-plan refresh and stopped before Phase 7.

### Files changed

- `scripts/validation/data_audit_universe_guard.py`
- `tests/validation/test_data_audit_universe_guard.py`
- `tests/phase5_wfa/test_build_wfa_splits.py`
- `CODEX_HANDOFF.md`

Unrelated dirty live-chart files were preserved.

### Commands run

- `git status --short`
- Targeted reads of `CODEX_HANDOFF.md`, `scripts\validation\data_audit_universe_guard.py`, `tests\validation\test_data_audit_universe_guard.py`, `tests\phase5_wfa\test_build_wfa_splits.py`, and `scripts\phase5_wfa\build_wfa_splits.py`
- `python -m pytest tests/validation/test_data_audit_universe_guard.py tests/phase5_wfa/test_build_wfa_splits.py`
- `python -m scripts.phase5_wfa.build_wfa_splits --profile tier_1 --input-root data/feature_matrices/baseline --reports-root reports/wfa_tier1_current_baseline_20260622_split_plan --profile-config configs/alpha_tiered.yaml --models-config configs/models.yaml --feature-manifest reports/features_baseline/baseline_feature_manifest.json --data-audit-universe-json reports/pipeline_audit/tier_1_data_audit_universe.json`
- Split-plan verification for `failure_count`, `fold_count`, skipped inputs, data-audit hash, Phase 4 input hashes, and feature-manifest gate evidence
- Prediction target absence checks for `data\predictions\tier1_current_baseline_20260622` and `reports\wfa\tier1_current_baseline_20260622_predictions_manifest.json`

### Test results

- `python -m pytest tests/validation/test_data_audit_universe_guard.py tests/phase5_wfa/test_build_wfa_splits.py`: `29 passed in 2.49s`
- Guarded split-plan refresh result:
  - command exit code: 0
  - printed: `PASS WFA split plan: folds=48 markets=4 failures=0`
  - `failure_count`: 0
  - `fold_count`: 48
  - `skipped_input_count`: 0
  - `data_audit_hash_matches`: true
  - `input_hash_count`: 8
  - `input_hash_mismatch_count`: 0
  - `feature_manifest_gate.status`: `PASS`
  - `feature_manifest_gate.upstream_status`: `WARN`
  - accepted Phase 4 warning messages: 4 unique market messages
- No Phase 7 command was run.
- No prediction artifacts were created for `tier1_current_baseline_20260622`.

### Remaining work

- WFA prediction evidence remains missing by design until a separate approved Phase 7 regeneration run.
- Keep cleanup blocked until prediction evidence is regenerated/reconciled and broader validation evidence is refreshed.

### Next recommended step

```text
Continue from CODEX_HANDOFF.md.

Next selected scope: Phase 7 WFA prediction regeneration for tier1_current_baseline_20260622.

Rules:
- Do not run cleanup, Phase 1-5 rebuilds, redownloads, DBN/source mutation, Phase 8/model selection, generated artifact staging, or commits.
- Do not edit historical WFA manifests.
- Keep generated data/report artifacts ignored and untracked.

Task:
- Preflight the refreshed split plan at reports/wfa_tier1_current_baseline_20260622_split_plan/split_plan.json: require failure_count=0, fold_count=48, skipped_input_count=0, current data-audit hash evidence, current Phase 4 input hashes, and feature_manifest_gate.status=PASS.
- Run only:
  python -m scripts.phase7_wfa.run_wfa --profile tier_1 --matrix baseline --run tier1_current_baseline_20260622 --input-root data/feature_matrices/baseline --split-plan reports/wfa_tier1_current_baseline_20260622_split_plan/split_plan.json --predictions-root data/predictions --reports-root reports/wfa --models-config configs/models.yaml --profile-config configs/alpha_tiered.yaml --feature-set manifests/feature_sets/baseline_current.json --data-audit-universe-json reports/pipeline_audit/tier_1_data_audit_universe.json
- Verify prediction parquet existence, prediction manifest existence, failure_count=0, prediction_count>0, artifact_evidence_ready=true, stale_output_path_exists=false, fold_count=48, all Phase 7A model ids, manifest output hash match, and parquet metadata row count equals manifest prediction_count.
- Update CODEX_HANDOFF.md with commands, results, blockers, and next selected scope.

Stop when:
- WFA prediction evidence passes verification, or the first blocker is recorded without running Phase 8.
```

## Latest run: Databento live chart visible verification

### What happened

- Initial `git status --short` showed existing modified files:
  - `CODEX_HANDOFF.md`
  - `live_chart_feed.py`
  - `scripts/phase5_wfa/build_wfa_splits.py`
  - `scripts/pipeline_gates.py`
  - `tests/phase5_wfa/test_build_wfa_splits.py`
  - `tests/test_live_chart_feed.py`
  - `tests/test_pipeline_gates.py`
- Opened a visible PowerShell verification window and ran:
  - `python live_chart_feed.py --historical-backfill --market ES --lookback-hours 168 --timeout-seconds 120 --no-data-warning-seconds 15`
- Verification log path outside the repo:
  - `C:\Users\donny\AppData\Local\Temp\live_chart_verify_20260622_225107.log`
- Databento historical/symbology clamp output was captured:
  - `Databento symbology end date: requested=2026-06-24, available_exclusive=2026-06-23, final=2026-06-23`
  - `Databento historical end date: requested=2026-06-23, available_exclusive=2026-06-23, final=2026-06-23`
- Live DNS/connectivity did not fail in this run. The chart reached live streaming and printed live status rows through `latest=2026-06-23 05:45Z`.
- Final chart output:
  - `Live chart stopped: records_updated=47058 first=2026-06-16T05:45:00Z latest=2026-06-23T05:45:00Z last_close=7472.25 timed_out=False chart_closed=True`
  - `TRUE_EXIT_CODE=0`
- No `Databento live chart failed` output was captured.
- No lingering `python.exe` live-chart process remained after completion.

### Verification result

- The original live DNS failure did not reproduce.
- Actual Databento live connectivity was verified in a visible terminal run.
- Historical backfill reached the expected Databento date-clamp path.
- The process completed with true exit code `0`.
- The fallback-specific message `Databento live stream unavailable after historical backfill` was not expected or observed because the live connection succeeded.

### Remaining work

- No remaining live-chart verification blocker from this pass.
- If the Databento DNS failure reappears later, use the previously added fallback path and capture the visible terminal output from that failing live-connectivity run.

## Previous run: Phase 5 feature-manifest gate policy fix

### What changed

- Updated `scripts/pipeline_gates.py` so upstream manifest gates remain strict by default but can opt in to explicit allowed statuses and exact accepted warning messages.
- Updated `scripts/phase5_wfa/build_wfa_splits.py` only: Phase 5 now accepts Phase 4 `WARN` manifests for the exact self-market unavailable feature warnings generated from the active profile markets.
- Added focused tests proving default gates still reject `WARN`, opt-in gates accept only exact approved warnings, failures/stale hashes remain rejected, and Phase 5 accepts the approved zero-failure Phase 4 warning case.
- Reran the guarded split-plan refresh. It now passes `feature_manifest_gate` but still fails before Phase 7 because the data-audit universe guard blocks all 8 Tier 1 market-years.

### Files changed

- `scripts/pipeline_gates.py`
- `scripts/phase5_wfa/build_wfa_splits.py`
- `tests/test_pipeline_gates.py`
- `tests/phase5_wfa/test_build_wfa_splits.py`
- `CODEX_HANDOFF.md`

### Commands run

- `Get-Location`
- `git status --short`
- `Get-Content -LiteralPath CODEX_HANDOFF.md -TotalCount 220`
- Targeted reads of `scripts\pipeline_gates.py`, `scripts\phase5_wfa\build_wfa_splits.py`, `tests\test_pipeline_gates.py`, and `tests\phase5_wfa\test_build_wfa_splits.py`
- `python -m pytest tests/test_pipeline_gates.py tests/phase5_wfa/test_build_wfa_splits.py`
- `python -m scripts.phase5_wfa.build_wfa_splits --profile tier_1 --input-root data/feature_matrices/baseline --reports-root reports/wfa_tier1_current_baseline_20260622_split_plan --profile-config configs/alpha_tiered.yaml --models-config configs/models.yaml --feature-manifest reports/features_baseline/baseline_feature_manifest.json --data-audit-universe-json reports/pipeline_audit/tier_1_data_audit_universe.json`
- Split-plan failure summary from `reports\wfa_tier1_current_baseline_20260622_split_plan\split_plan.json`
- Prediction target absence check for `tier1_current_baseline_20260622`
- `git diff -- scripts\pipeline_gates.py scripts\phase5_wfa\build_wfa_splits.py tests\test_pipeline_gates.py tests\phase5_wfa\test_build_wfa_splits.py`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`

### Test results

- `python -m pytest tests/test_pipeline_gates.py tests/phase5_wfa/test_build_wfa_splits.py`: `26 passed in 2.73s`
- Guarded split-plan refresh result:
  - command exit code: 1
  - printed: `FAIL WFA split plan: folds=0 markets=4 failures=1`
  - `feature_manifest_gate.status`: `PASS`
  - `feature_manifest_gate.accepted_warning_count`: 8
  - `failure_count`: 1
  - `fold_count`: 0
  - `skipped_input_count`: 8
  - failure: `data-audit universe blocked all market-years; no folds generated`
  - first skip detail: `WFA split-plan generation: data-audit universe blocks ES 2023 with final_decision='acceptable_with_caveat_ohlcv_empty_minutes_assumed': decision table marks market-year acceptable under current OHLCV-only evidence`
- No Phase 7 command was run.
- No prediction artifacts were created for `tier1_current_baseline_20260622`.

### Remaining work

- WFA prediction regeneration remains blocked until the data-audit universe WFA-usability policy is reconciled for `acceptable_with_caveat_ohlcv_empty_minutes_assumed` market-years.
- Do not run Phase 7 until a guarded split plan has `failure_count=0`, `fold_count=48`, current data-audit evidence, and current Phase 4 input hashes.

### Next recommended step

```text
Continue from CODEX_HANDOFF.md.

Next selected scope: data-audit universe WFA-usability policy for OHLCV caveat decisions.

Rules:
- Do not run cleanup, Phase 1-4 rebuilds, redownloads, DBN/source mutation, WFA prediction generation, generated artifact staging, or commits.
- Do not bypass data-audit universe guards or edit historical WFA manifests.
- Preserve unrelated dirty `live_chart_feed.py` and `tests/test_live_chart_feed.py` changes.

Task:
- Inspect `scripts.validation.data_audit_universe_guard`, `scripts.validation.build_data_audit_universe`, and focused tests for final_decision handling.
- Decide and implement the smallest explicit policy, if justified, for treating `acceptable_with_caveat_ohlcv_empty_minutes_assumed` as WFA-usable when `usable_for_wfa=true` and the universe status is `PASS`.
- Add focused tests proving quarantined/diagnostic decisions still block WFA.
- Rerun focused data-audit guard tests and the guarded Phase 5 split-plan refresh.
- Update CODEX_HANDOFF.md with commands, results, blockers, and next selected scope.

Stop when:
- The guarded split plan reaches `failure_count=0` and `fold_count=48`, or the first blocker is recorded without running Phase 7.
```

## Previous run: Databento live chart fallback verification attempt

### What happened

- Pre-run `git status --short` matched the expected three modified files:
  - `CODEX_HANDOFF.md`
  - `live_chart_feed.py`
  - `tests/test_live_chart_feed.py`
- Sandboxed verification command failed before Databento/chart runtime execution with `[WinError 5] Access is denied` while `lightweight_charts` imported and tried to create a Windows multiprocessing pipe.
- Retried the exact command outside the sandbox after approval:
  - `python live_chart_feed.py --historical-backfill --market ES --lookback-hours 168 --timeout-seconds 120 --no-data-warning-seconds 15`
- The unsandboxed command exceeded the tool timeout after `154021 ms`, produced no captured stdout/stderr, and left the exact verification process running as PID `8604`.
- PID `8604` was stopped with approval using `Stop-Process -Id 8604 -Force`.
- Final `git status --short` showed the same three live-chart/handoff files plus unrelated modified WFA gate files `scripts/phase5_wfa/build_wfa_splits.py`, `scripts/pipeline_gates.py`, `tests/phase5_wfa/test_build_wfa_splits.py`, and `tests/test_pipeline_gates.py`; this verification pass did not edit those WFA gate files.

### Verification result

- Fallback behavior was not confirmed.
- No Databento historical date clamp output was captured from the unsandboxed attempt.
- No `Databento live stream unavailable after historical backfill` output was captured.
- No `Databento live chart failed` output was captured.
- Process exit code for the unsandboxed attempt was not the chart process exit code; the tool returned timeout code `124`.

### Next recommended step

```text
Continue from CODEX_HANDOFF.md.

Next selected scope: clear the Databento live chart verification blocker without code edits.

Rules:
- Do not edit code, cleanup, stage, commit, redownload, mutate DBN/source data, or generate model/WFA artifacts.
- Do not run WFA/model or data rebuild commands.
- Keep generated artifacts untracked.

Task:
- Run the live chart verification command from a visible interactive terminal or VS Code run button so stdout/stderr and chart close behavior can be observed directly:
  python live_chart_feed.py --historical-backfill --market ES --lookback-hours 168 --timeout-seconds 120 --no-data-warning-seconds 15
- If it opens a chart, close the chart window after historical candles render or after the live-unavailable status appears.
- Record exact terminal output, whether the chart opened, whether historical candles rendered, and the true process exit code.

Stop when:
- The fallback behavior is confirmed with exact output and exit code, or the first different failure is captured with exact output.
```

## Previous run: WFA prerequisite refresh attempt

### What changed

- Ran the approved WFA preflight for `tier1_current_baseline_20260622`.
- Preflight passed: Phase 4 manifest is `WARN` with `failure_count=0`, 8 outputs exist, 4 baseline registries exist, the frozen baseline feature set has 122 features and matches `feature_cols.json`, and `reports/pipeline_audit/tier_1_data_audit_universe.json` is `PASS` with 8/8 `usable_for_wfa`.
- Stopped before Phase 7 because guarded Phase 5 split-plan generation failed on the current feature-manifest gate: upstream Phase 4 manifest and all 8 outputs are `WARN` with warnings, not `PASS` with zero warnings.
- Confirmed no target artifacts were created:
  - `reports/wfa_tier1_current_baseline_20260622_split_plan`
  - `data/predictions/tier1_current_baseline_20260622`
  - `reports/wfa/tier1_current_baseline_20260622_predictions_manifest.json`
  - `reports/wfa/tier1_current_baseline_20260622_wfa_report.json`

### Files changed

- `CODEX_HANDOFF.md`

### Commands run

- `Get-Location`
- `git status --short`
- `Get-Content -LiteralPath CODEX_HANDOFF.md -TotalCount 260`
- Phase 4 preflight summary from `reports\features_baseline\baseline_feature_manifest.json`
- Feature-set/registry preflight for `manifests\feature_sets\baseline_current.json` and `data\feature_matrices\baseline\feature_cols.json`
- Data-audit universe preflight for `reports\pipeline_audit\tier_1_data_audit_universe.json`
- Target-output collision checks for `tier1_current_baseline_20260622`
- `python -m scripts.phase5_wfa.build_wfa_splits --profile tier_1 --input-root data/feature_matrices/baseline --reports-root reports/wfa_tier1_current_baseline_20260622_split_plan --profile-config configs/alpha_tiered.yaml --models-config configs/models.yaml --feature-manifest reports/features_baseline/baseline_feature_manifest.json --data-audit-universe-json reports/pipeline_audit/tier_1_data_audit_universe.json`
- Post-failure target-output existence checks
- `git status --short -- data reports CODEX_HANDOFF.md`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`

### Test results

- No pytest was run; no code changed.
- Guarded Phase 5 split-plan command failed before writing outputs:
  - `feature_manifest_gate failed: upstream manifest status is 'WARN', not 'PASS'; upstream manifest warning_count is 8, not 0; ... upstream manifest output 7 warning_count is 1, not 0`

### Remaining work

- WFA prediction regeneration remains blocked until Phase 5 has an approved policy/code path for this restored Phase 4 evidence, or Phase 4 evidence is regenerated in a way that produces `PASS`.
- Do not bypass the `feature_manifest_gate`; the next safe scope is a separate Phase 5 gate policy/code decision for zero-failure Phase 4 `WARN` manifests with accepted warnings.

### Next recommended step

```text
Continue from CODEX_HANDOFF.md.

Next selected scope: Phase 5 feature_manifest_gate policy/code decision for zero-failure Phase 4 WARN manifests.

Rules:
- Do not run cleanup, Phase 1-4 rebuilds, redownloads, DBN/source mutation, WFA prediction generation, generated artifact staging, or commits.
- Do not bypass WFA provenance gates or edit historical WFA manifests.
- Keep any generated data/report artifacts ignored and untracked.

Task:
- Inspect `scripts.phase5_wfa.build_wfa_splits` and the upstream manifest gate helper/tests.
- Decide and implement the smallest explicit policy for accepting Phase 4 `WARN` only when `failure_count=0`, all expected outputs exist, and warnings are accepted/documented.
- Add or update focused tests proving Phase 5 still rejects real failures and only accepts the approved zero-failure warning case.
- Run the focused Phase 5 WFA split tests.
- Update CODEX_HANDOFF.md with commands, results, blockers, and the next selected scope.

Stop when:
- The policy/code decision is implemented and focused tests pass, or the first blocker is recorded without running Phase 7.
```

## Latest run: Databento live chart DNS fallback

### What changed

- Diagnosed the pasted failure as a Databento live DNS/connection failure after historical backfill had already succeeded.
- Updated `live_chart_feed.py` so a live DNS/connection failure after loaded historical candles keeps the historical chart open until chart close/timeout and exits 0 instead of surfacing `Databento live chart failed` with exit code 1.
- Prevented persisted market selection from overriding legacy `--symbols`-only calls without `--market`, matching existing CLI semantics tests.

### Files changed

- `live_chart_feed.py`
- `tests/test_live_chart_feed.py`
- `CODEX_HANDOFF.md`

### Commands run

- `Get-Location`
- `git status --short`
- `Test-Path CODEX_HANDOFF.md`
- `rg --files -g "live_chart_feed.py" -g "CODEX_HANDOFF.md"`
- `Get-Content -Raw CODEX_HANDOFF.md`
- Targeted `rg` and `Get-Content` reads for `live_chart_feed.py`, live chart tests, and live Databento scripts
- `python -m pytest tests/test_live_chart_feed.py`
- `python -m pytest tests\live\test_live_chart_lightweight.py`
- `python -m pytest tests/test_live_chart_feed.py tests\live\test_live_chart_lightweight.py`
- `git diff -- live_chart_feed.py tests\test_live_chart_feed.py`
- `git status --short`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`

### Test results

- `python -m pytest tests/test_live_chart_feed.py`: `31 passed in 1.18s`
- Initial `python -m pytest tests\live\test_live_chart_lightweight.py`: failed because persisted local chart state let a legacy `--symbols`-only call reach `lightweight_charts` and hit `[WinError 5] Access is denied`; fixed by ignoring persisted market selection when `--symbols` is supplied without `--market`.
- Final `python -m pytest tests/test_live_chart_feed.py tests\live\test_live_chart_lightweight.py`: `38 passed in 1.24s`

### Remaining work

- Rerun the same live chart command/window that produced `getaddrinfo failed`; if Databento live DNS still fails, expected behavior is historical candles remain visible until chart close/timeout with a live-unavailable message and process exit 0.
- If actual live streaming is required, resolve the local/network DNS path to `glbx-mdp3.lsg.databento.com:13000`; this code change does not fix external DNS/connectivity.

### Next recommended step

```text
Continue from CODEX_HANDOFF.md.

Next selected scope: rerun the Databento live chart command/window that produced the `getaddrinfo failed` error, read output only first.

Rules:
- Do not cleanup, stage, commit, redownload, mutate DBN/source data, or generate model/WFA artifacts.
- Do not change trading/data semantics or public CLI contracts.
- Keep generated artifacts untracked.

Task:
- Launch the same live chart path that previously printed `Databento live chart failed: Connection to glbx-mdp3.lsg.databento.com:13000 failed: [Errno 11002] getaddrinfo failed`.
- Verify historical candles render and the terminal reports `Databento live stream unavailable after historical backfill` instead of `Databento live chart failed`.
- Record the exit code and whether the chart stays open until close/timeout.

Stop when:
- The rerun confirms the new fallback behavior, or the first different failure is captured with exact output.
```

## Current selected scope

- Active next scope: reopen the live chart and manually verify startup, market-switch, and timeframe-switch responsiveness after the source-candle/cache changes.
- Current readiness state: focused live chart tests pass; the chart now opens before Databento metadata/symbology/backfill work, all timeframe options remain visible, display timeframes derive from canonical 1-minute source candles, and repeat market switches can reuse cached historical source candles. WFA prediction evidence still requires a separate approved Phase 7 run after the refreshed split plan.
- Required stop limits for the next run: do not run cleanup, Phase 1-5 rebuilds, redownloads, DBN/source mutation, generated artifact staging, WFA prediction generation, model/WFA artifact generation, code edits, or commits unless explicitly approved.

## Current Tier 1 Phase 4 evidence

- Preflight passed:
  - `reports/labels/label_manifest.json` status: `PASS`
  - Label manifest profile: `tier_1`
  - Label manifest outputs: 8
  - Missing label output paths: 0
  - Planned Phase 4 outputs present before regeneration: 0 of 8
  - Planned Phase 4 root registries present before regeneration: 0 of 4
- Tier 1 Phase 4 baseline feature regeneration completed:
  - Command: `python -m scripts.phase4_features.build_baseline_features --profile tier_1 --input-root data/labeled --output-root data/feature_matrices/baseline --reports-root reports/features_baseline --label-manifest reports/labels/label_manifest.json`
  - Manifest: `reports/features_baseline/baseline_feature_manifest.json`
  - Manifest status: `WARN`
  - Manifest profile: `tier_1`
  - Expected inputs: 8
  - Actual inputs: 8
  - Outputs: 8
  - Failure count: 0
  - Warning count: 8
  - Missing manifest output paths after regeneration: 0
  - Root registries restored: `feature_cols.json`, `target_cols.json`, `metadata_cols.json`, `excluded_cols.json`
- Output row counts:
  - `ES:2023`: rows=353428, training_valid=344171
  - `ES:2024`: rows=355065, training_valid=346913
  - `CL:2023`: rows=353359, training_valid=319190
  - `CL:2024`: rows=355962, training_valid=304103
  - `ZN:2023`: rows=353549, training_valid=239248
  - `ZN:2024`: rows=355249, training_valid=231530
  - `6E:2023`: rows=354284, training_valid=296557
  - `6E:2024`: rows=356478, training_valid=285372
- Preserved Phase 4 warnings:
  - `ES:2023` and `ES:2024`: `features fully unavailable: feature_rel_ret_vs_ES_15,feature_corr_vs_ES_60`
  - `CL:2023` and `CL:2024`: `features fully unavailable: feature_rel_ret_vs_CL_15,feature_corr_vs_CL_60`
  - `ZN:2023` and `ZN:2024`: `features fully unavailable: feature_rel_ret_vs_ZN_15,feature_corr_vs_ZN_60`
  - `6E:2023` and `6E:2024`: `features fully unavailable: feature_rel_ret_vs_6E_15,feature_corr_vs_6E_60`
- Focused Phase 4 tests passed:
  - Command: `python -m pytest tests/phase4_features/test_build_baseline_features.py`
  - Result: `33 passed in 10.36s`
- Generated-artifact hygiene:
  - `git status --short -- data reports CODEX_HANDOFF.md` was empty before the handoff edit because regenerated `data/` and `reports/` artifacts are ignored.
  - `data/predictions` remains unreconciled and was not regenerated.

## Current WFA prediction artifact reconciliation

- Report: `reports/wfa_prediction_artifact_reconciliation_20260622.md`
- Scope checked:
  - `reports/wfa/*_predictions_manifest.json`
  - `data/predictions`
  - Fixture-only reference: `reports/wfa_fixture_smoke/data/predictions/fixture_smoke/oos_predictions.parquet`
- Reconciliation counts:
  - Prediction manifests checked: 24
  - Prediction files currently under `data/predictions`: 0
  - `valid_current_evidence`: 0
  - `stale_missing_prediction`: 24
  - Present invalid or hash-mismatch manifests: 0
  - Manifests with `artifact_evidence_ready=true`: 24
  - Manifests with `stale_output_path_exists=true`: 0
  - Manifests with output hash entries for their prediction path: 24
- Result:
  - No `reports/wfa` prediction manifest currently has a valid prediction parquet on disk.
  - The fixture-smoke parquet exists but is fixture evidence only and is not a recovery source for `reports/wfa`.
  - Treat existing `reports/wfa/*_predictions_manifest.json` files as historical until a separately approved regeneration run writes matching current `data/predictions/<run>/oos_predictions.parquet` artifacts.

## Current SR1 Phase 2 evidence

- `SR1:2018` Phase 2 pilot was built.
  - Output: `data/causally_gated_normalized/SR1/2018.parquet`
  - Rows: 1562
  - Build manifest status: `WARN`
  - Failures: 0
  - Preserved accepted warnings: `roll maturity sequence not monotonic: backsteps=36`; `roll exclusion threshold breached: rows_pct=7.426376 rows=116`
  - Focused Phase 2 tests at the time: `69 passed`
  - Broader related tests later: `290 passed in 37.22s` for `tests\phase2_causal_base` and `tests\validation`

- `SR1:2019` Phase 2 build was completed.
  - Output: `data/causally_gated_normalized/SR1/2019.parquet`
  - Rows: 10252
  - Build manifest status: `WARN`
  - Failures: 0
  - Preserved accepted warning: `roll maturity sequence not monotonic: backsteps=50`
  - Manifest audit at the time: `manifest_check issues=166 failures=0`
  - `git status --short -- data` was empty after the build.

- `SR1:2020` readiness passed but build has not been run.
  - Config: `reports/phase_restart/sr1_2020_phase2_causal_repair.yaml`
  - Existing raw alignment: `reports/phase_restart/sr1_2020_phase2_raw_alignment.json`
  - Raw alignment status: `PASS`
  - Raw alignment counts: `needs_phase1b_conversion_count=0`, `raw_only_count=0`, `source_hash_mismatch_count=0`, `invalid_manifest_count=0`, `repair_manifest_failure_count=0`
  - Readiness refresh: `reports/phase_restart/sr1_2020_phase2_readiness_refresh.json` and `.md`
  - Readiness refresh status: `PASS`
  - Readiness refresh counts: `failure_count=0`, `blocker_count=0`, `accepted_exception_count=1`
  - Accepted warnings exactly: `roll maturity sequence not monotonic: backsteps=72`; `roll exclusion threshold breached: rows_pct=2.674358 rows=255`
  - Raw file exists: `data/raw/SR1/2020.parquet`
  - Phase 2 output remains absent: `data/causally_gated_normalized/SR1/2020.parquet`
  - `git status --short -- data` was empty after readiness-only refresh.

## Data health and prerequisite state

- Latest refreshed health matrix and Phase 2 prerequisite snapshot recorded:
  - Manifest audit: `issues=168 failures=0`
  - Raw optional-schema audit: `FAIL` with 9 file failures
  - Health counts: `OK=45`, `POLICY=464`, `EXCLUDED=9`, `UNKNOWN=9`
  - Phase 2 accepted rows with pre-build raw evidence prerequisites: 9
  - Cleared from stale unknown/pre-build prerequisite status: `SR3:2019-2024` and `SR1:2018-2024`
- `SR3:2019` and `SR3:2020` source-reference corrections were completed before this compaction.
  - `SR3:2019` conversion wrote 4608 rows and cleared source-reference/hash failures for that row.
  - `SR3:2020` conversion wrote 10630 rows and cleared source-reference/hash failures for that row.
  - Optional-schema audit remained `FAIL` overall because unrelated rows still failed.
- Cleanup remains disabled. Keep cleanup disabled until blockers are zero and cleanup is separately approved.

## Live-ops state

- Paper/smoke live-ops scaffold work reached closeout documentation.
- Current docs state is explicitly not production-live ready.
- Focused live-ops/chart validation at closeout: `71 passed`
- Smoke CLI at closeout: `PASS live trading smoke scenarios=34 decision_cycles=34 audit_rows=34`
- Broad bounded pytest at closeout: `732 passed, 58 warnings`
- Deferred live-ops production-depth items remain: broker SDK/account integration, real live order path, GUI/chart launch, `--no-timeout` runtime, cancel/flatten-on-kill production behavior, direct broker-owned audit append, deeper reconciliation, and broader runtime durability.

## Files changed by this run

- Ignored/generated:
  - `data/feature_matrices/baseline/{ES,CL,ZN,6E}/{2023,2024}.parquet`
  - `data/feature_matrices/baseline/feature_cols.json`
  - `data/feature_matrices/baseline/target_cols.json`
  - `data/feature_matrices/baseline/metadata_cols.json`
  - `data/feature_matrices/baseline/excluded_cols.json`
  - `reports/features_baseline/baseline_feature_manifest.json`
  - `reports/features_baseline/baseline_feature_report.json`
  - `reports/features_baseline/feature_registry.json`
  - `reports/features_baseline/feature_correlation_report.csv`
  - `reports/wfa_prediction_artifact_reconciliation_20260622.md`
- Tracked:
  - `CODEX_HANDOFF.md`

## Commands run in this run

- `Get-Location`
- `git rev-parse --show-toplevel`
- `git status --short`
- `Get-Content -LiteralPath CODEX_HANDOFF.md`
- Label manifest preflight summary from `reports\labels\label_manifest.json`
- Phase 4 output and registry absence preflight under `data\feature_matrices\baseline`
- Existing Phase 4 manifest stale-output preflight from `reports\features_baseline\baseline_feature_manifest.json`
- `python -m scripts.phase4_features.build_baseline_features --profile tier_1 --input-root data/labeled --output-root data/feature_matrices/baseline --reports-root reports/features_baseline --label-manifest reports/labels/label_manifest.json`
- Post-run Phase 4 output, registry, and manifest verification
- `git status --short -- data reports CODEX_HANDOFF.md`
- `python -m pytest tests/phase4_features/test_build_baseline_features.py`
- Phase 4 warning summary from `reports\features_baseline\baseline_feature_manifest.json`
- WFA Phase 4 preflight summary from `reports\features_baseline\baseline_feature_manifest.json`
- `Get-ChildItem -LiteralPath data\predictions -File -Recurse`
- `Get-Date -Format yyyyMMdd`
- WFA prediction manifest reconciliation summary from `reports\wfa\*_predictions_manifest.json`
- `Get-ChildItem -LiteralPath data\predictions -Directory -Recurse`
- `Test-Path -LiteralPath reports\wfa_fixture_smoke\data\predictions\fixture_smoke\oos_predictions.parquet`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`

## Test results for this run

- `python -m pytest tests/phase4_features/test_build_baseline_features.py`: `33 passed in 10.36s`
- No pytest or WFA/modeling tests were run during reconciliation; no code changed and no prediction generation was performed.

## Remaining work

- Run no cleanup unless separately approved.
- Keep cleanup blocked. `data/predictions` has 0 files and 24 WFA manifests reference missing prediction parquet files; this run did not change or regenerate predictions.
- Before WFA/model evidence can be trusted, run one separately approved Tier 1 baseline WFA regeneration with a new run name, then verify prediction parquet existence, manifest hash fields, `failure_count=0`, `prediction_count>0`, and evidence flags.
- Refresh broader validation evidence only after WFA prediction artifact state is understood.
- Do not treat `WARN` build manifests for `SR1:2018` or `SR1:2019` as failures by themselves; the warnings were intentionally preserved as accepted roll-maturity evidence with zero failures.
- Before trusting broader Phase 2/model results, continue to verify row-level raw alignment, readiness, warning exceptions, generated output presence, manifest audit, and generated-artifact hygiene.

## Next recommended step

```text
Continue from CODEX_HANDOFF.md.

Next selected scope: one approved Tier 1 baseline WFA regeneration plan/run decision.

Rules:
- Do not run cleanup, Phase 1-4 rebuilds, redownloads, DBN/source mutation, generated artifact staging, or commits.
- Do not overwrite historical `reports/wfa` manifests or `data/predictions` runs.
- If WFA regeneration is approved, use a new run name.
- Keep generated artifacts ignored/untracked.

Task:
- Choose a new run name for one Tier 1 baseline WFA regeneration, for example `tier1_current_baseline_20260622`.
- Preflight current `data/feature_matrices/baseline`, `reports/wfa/split_plan.json`, `configs/models.yaml`, and exact model/profile arguments.
- Propose or run the exact WFA command only if the new user request explicitly approves prediction regeneration.
- Verify generated prediction parquet and manifest fields, hash evidence, `artifact_evidence_ready`, and `failure_count`.
- Update CODEX_HANDOFF.md with commands, results, blockers, and the next selected scope.

Stop when:
- The WFA regeneration command is approved and completed with evidence, or the first blocker is recorded without running broader scopes.
```
