# Codex Handoff

- Updated at UTC: 2026-06-23T04:50:20Z
- Purpose: compacted the previous append-only handoff into a current-state handoff. The old file was about 276 KB and is superseded by this summary.
- Repo: `C:\Users\donny\Desktop\futures_intraday_model`
- Pre-compaction worktree check: `git status --short` was empty.
- This compaction run changed only `CODEX_HANDOFF.md`; no data build, repair, cleanup, staging, commit, move, delete, redownload, DBN/source mutation, Phase 3+, or generated artifact staging was run.

## Current selected scope

- Active next scope: `SR1:2020` one-row Phase 2 build, only if explicitly approved.
- Current readiness state: `SR1:2020` readiness exception accepted and readiness-only refresh passed.
- Required stop limits for the next run: one row only, stop before cleanup, stop before Phase 3+, do not redownload, do not mutate DBN/source files, do not stage generated artifacts, and do not commit unless explicitly asked.

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

## Files changed by this compaction

- `CODEX_HANDOFF.md`: replaced the long accumulated append-only handoff with this compact current-state handoff.

## Commands run in this compaction

- `Get-Location`
- `git status --short`
- `Get-Content -LiteralPath .\CODEX_HANDOFF.md -TotalCount 120`
- `Get-Content -LiteralPath .\CODEX_HANDOFF.md -Tail 160`
- `rg -n "^## " .\CODEX_HANDOFF.md`
- Targeted read of SR1:2018/SR1:2019 context from `CODEX_HANDOFF.md`
- `[DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')`
- `Get-Item -LiteralPath .\CODEX_HANDOFF.md | Select-Object FullName,Length,LastWriteTime`
- `git status --short`
- `git diff --check -- CODEX_HANDOFF.md`
- `Get-Content -LiteralPath .\CODEX_HANDOFF.md -TotalCount 40`

## Test results for this compaction

- No tests were run. This was a documentation compaction only.
- Validation performed: pre-edit `git status --short` was empty; targeted reads confirmed the current next action and immediate supporting evidence.
- Post-edit file size: 7060 bytes.
- Post-edit `git status --short`: `M CODEX_HANDOFF.md`.
- Post-edit `git diff --check -- CODEX_HANDOFF.md`: CRLF normalization warning only, no whitespace errors.

## Remaining work

- Run no cleanup unless separately approved.
- Do not treat `WARN` build manifests for `SR1:2018` or `SR1:2019` as failures by themselves; the warnings were intentionally preserved as accepted roll-maturity evidence with zero failures.
- Before trusting broader Phase 2/model results, continue to verify row-level raw alignment, readiness, warning exceptions, generated output presence, manifest audit, and generated-artifact hygiene.

## Next recommended step

```text
Continue from CODEX_HANDOFF.md.

Next selected scope: one-row SR1:2020 Phase 2 build.

Rules:
- Do not run cleanup, Phase 3+, redownloads, DBN/source mutation, generated artifact staging, or commits.
- Do not build any row except SR1:2020.
- Stop before any additional row.
- Keep generated data/report artifacts untracked.

Task:
- Run the SR1:2020 Phase 2 build using reports\phase_restart\sr1_2020_phase2_causal_repair.yaml.
- Run python scripts\audit_data_manifest.py.
- Run git status --short -- data and confirm generated data artifacts remain untracked.
- Sanity-check the SR1:2020 output row count, manifest status, warnings, and failure count.
- Update CODEX_HANDOFF.md with changed files, commands, results, remaining work, and the next one-row scope.

Stop when:
- SR1:2020 build evidence is recorded, or the first blocker/failure is recorded with exact command output and no further row is attempted.
```
