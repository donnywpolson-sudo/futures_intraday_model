# Project Overview

- Project: `futures_intraday_model`.
- Purpose: intraday futures research pipeline using Databento continuous-contract 1-minute OHLCV data.
- Status framing: research and walk-forward validation only; this is not live-trading or production readiness.
- Pipeline authority: use `PIPELINE.md` for phase order, runnable pipeline commands, acceptance checks, and stop conditions.
- Repo guidance authority: use `AGENTS.md` for agent workflow, safety rules, and final-response format.
- Handoff role: this file is mutable cross-run state. Reconcile all material claims against current repo files, reports, command output, and `git status` before acting.
- Solo Codex files: keep `AGENTS.md` and `CODEX_HANDOFF.md` only; do not create `PROJECT_STATE.md`, `research/JOURNAL.md`, or parallel handoff/state files unless explicitly requested.
- History note: this file was compacted on 2026-06-30 from the prior chronological handoff log into a standing-state handoff. Use git history only if exact older run text is needed.

# Current State

- Active repo path verified on 2026-07-01: `C:\Users\donny\Desktop\futures_intraday_model`.
- The environment path `C:\Users\donny\Desktop\15_min_long_short` was not present during this handoff update.
- Git state before this handoff-only update: `main...origin/main [ahead 20]` with only the seven broad-loop untracked files listed below remaining dirty.
- Latest stabilization commits before this handoff-only update:
  - `2e6d23a Add coordination document checks`
  - `9927adb Add bounded OHLCV gap scan progress guards`
- Remaining untracked broad build/loop files remain excluded from stabilization and proof-scan prep:
  - `scripts/validation/build_broad_manifest_527_rebuild.py`
  - `scripts/validation/monitor_broad_manifest_527_rebuild.py`
  - `scripts/validation/run_broad_manifest_527_step_loop.ps1`
  - `scripts/validation/run_broad_manifest_527_step_loop.py`
  - `scripts/validation/run_broad_manifest_source_gap_fail_closed_loop.py`
  - `tests/validation/test_build_broad_manifest_527_rebuild.py`
  - `tests/validation/test_run_broad_manifest_source_gap_fail_closed_loop.py`
- Local trade/OHLCV proof remains no-go. The capped scan against `data\causal_proof_candidates\local_trade_2025_2026_v1` completed cleanly as `FAIL` after the approved `--max-runtime-seconds 900` limit.
- Latest capped proof artifacts are ignored/generated local reports:
  - `reports\pipeline_audit\local_trade_ohlcv_gap_crosscheck_phase2_uncovered_29_candidate_capped_20250618_20260613.json`
  - `reports\pipeline_audit\local_trade_ohlcv_gap_crosscheck_phase2_uncovered_29_candidate_capped_20250618_20260613.md`
  - `reports\pipeline_audit\local_trade_ohlcv_gap_crosscheck_phase2_uncovered_29_candidate_capped_20250618_20260613.progress.jsonl`
- Latest capped proof result: `status=FAIL`, failure `--max-runtime-seconds limit exceeded`, stopped at `YM 2025` (`market_year_index=5/58`), `status_counts={PASS:4, FAIL:1}`, `trade_rows_scanned=116752954`, `verified_empty_minutes=8717`, `unverified_minutes=2196`, `failed_minutes=0`.
- Candidate causal proof inputs were previously generated under `data\causal_proof_candidates\local_trade_2025_2026_v1` for the 29 uncovered markets and 2025/2026 only. Treat these as ignored local generated artifacts unless separately approved.
- Full 527-row promoted/canonical Phase 2 remains no-go.
- Optional metadata is classified and blocked, but field-level point-in-time availability has not been proven.
- No generated `data/**`, generated reports, configs, models, predictions, cleanup, labels, feature matrices, modeling, WFA, metrics, or live/paper execution should be touched without explicit approval.

# Recent Changes

- 2026-07-01: ran the capped local trade/OHLCV proof scan with `--causal-root data\causal_proof_candidates\local_trade_2025_2026_v1`; it completed cleanly with generated `FAIL` evidence after the 900-second runtime cap. No Python process remained afterward.
- 2026-07-01: patched `scripts/validation/audit_local_trade_ohlcv_gaps.py` after stuck/opaque runs: added finer `--progress-jsonl` events, runtime checks during gap grouping, global stop on first scan-limit failure, faster nanosecond adjacent timestamp lookup, and exception-to-FAIL-report handling. Focused test file `tests/validation/test_audit_local_trade_ohlcv_gaps.py` now covers these paths.
- 2026-07-01: stabilized the worktree before any proof scan by committing coordination docs/checker separately from OHLCV guard/progress changes. The proof scan was not run.
- 2026-07-01: added coordination source-of-truth rules to `AGENTS.md` and added `scripts/validation/check_coordination_docs.py` with focused tests in `tests/validation/test_check_coordination_docs.py`.
- 2026-07-01: committed OHLCV local trade gap scan progress and fail-closed guard changes in `scripts/validation/audit_local_trade_ohlcv_gaps.py` and `tests/validation/test_audit_local_trade_ohlcv_gaps.py`.
- 2026-06-30: compacted `CODEX_HANDOFF.md` into a single standing-state handoff with project overview, current state, recent changes, active tasks, known issues, and next steps.
- 2026-06-30: local trade/OHLCV gap auditor guard fix was committed in `d7d9e89`; the auditor now has fail-closed scan limits and a default runtime ceiling.

# Active Tasks

- Keep this handoff as the single current project-state file for Codex continuation.
- Keep `AGENTS.md` as the durable agent-rule file.
- Run `python -m scripts.validation.check_coordination_docs` after future coordination-doc edits when practical.
- Decide whether to commit the local process-safety patch in `scripts\validation\audit_local_trade_ohlcv_gaps.py`, `tests\validation\test_audit_local_trade_ohlcv_gaps.py`, and this `CODEX_HANDOFF.md`.
- After the process-safety patch is committed or explicitly left local, plan sharded capped proof scans; the single 29-market run reached only 5 of 58 market-years before the approved runtime cap.
- Keep the seven pre-existing untracked broad build/loop files out of any documentation-only or proof-scan commit unless the user explicitly approves their disposition.

# Known Issues

- Severe: local trade/OHLCV proof is still no-go; latest capped proof scan stopped at the approved runtime limit before completing all 58 market-years.
- Medium: process-safety patch from the completed capped scan is local and uncommitted.
- Medium: generated candidate causal proof data/reports are ignored local artifacts and should not be staged by default.
- Medium: field-level point-in-time availability for optional metadata has not been proven.
- Medium: full 527-row promoted/canonical Phase 2 remains no-go.
- Medium: the original configured cwd `C:\Users\donny\Desktop\15_min_long_short` was absent; use `C:\Users\donny\Desktop\futures_intraday_model` unless the user says otherwise.
- Medium: branch is ahead of origin and contains local commits; verify sync intent before pushing or rebasing.
- Medium: seven broad-loop untracked files remain intentionally excluded.

# Next Steps

Exact next recommended step:

Review and, if approved, commit only the process-safety scope: `scripts\validation\audit_local_trade_ohlcv_gaps.py`, `tests\validation\test_audit_local_trade_ohlcv_gaps.py`, and this `CODEX_HANDOFF.md`. Do not stage the seven broad build/loop files, generated `data/**`, generated reports, configs, models, predictions, cleanup, labels, feature matrices, modeling, WFA, metrics, or live/paper execution. After that, separately plan sharded capped proof scans rather than one full 29-market run.

Fresh-thread prompt:

```text
Continue from CODEX_HANDOFF.md.

Goal: decide whether to commit the local process-safety patch from the capped scan run, then plan sharded capped proof scans separately.

Rules:
- First verify repo path, git status, and the current CODEX_HANDOFF.md.
- Do not stage generated artifacts.
- Do not refresh promoted Phase 2 reports.
- Do not run broad build/loop files.
- Do not promote canonical data.
- Do not touch modeling, WFA, metrics, predictions, cleanup, labels, feature matrices, or live/paper execution.
- If commit approval is missing, stop with a plan only.

Allowed commit scope:
- scripts\validation\audit_local_trade_ohlcv_gaps.py
- tests\validation\test_audit_local_trade_ohlcv_gaps.py
- CODEX_HANDOFF.md

Do not stage:
- generated data/**
- generated reports
- seven broad build/loop files
- configs, models, predictions, cleanup, labels, feature matrices, modeling, WFA, metrics, or live/paper execution
```
