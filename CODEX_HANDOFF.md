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
- Local trade/OHLCV proof remains no-go until a separately approved capped proof scan completes with acceptable evidence.
- Candidate causal proof inputs were previously generated under `data\causal_proof_candidates\local_trade_2025_2026_v1` for the 29 uncovered markets and 2025/2026 only. Treat these as ignored local generated artifacts unless separately approved.
- Full 527-row promoted/canonical Phase 2 remains no-go.
- Optional metadata is classified and blocked, but field-level point-in-time availability has not been proven.
- No generated `data/**`, generated reports, configs, models, predictions, cleanup, labels, feature matrices, modeling, WFA, metrics, or live/paper execution should be touched without explicit approval.

# Recent Changes

- 2026-07-01: stabilized the worktree before any proof scan by committing coordination docs/checker separately from OHLCV guard/progress changes. The proof scan was not run.
- 2026-07-01: added coordination source-of-truth rules to `AGENTS.md` and added `scripts/validation/check_coordination_docs.py` with focused tests in `tests/validation/test_check_coordination_docs.py`.
- 2026-07-01: committed OHLCV local trade gap scan progress and fail-closed guard changes in `scripts/validation/audit_local_trade_ohlcv_gaps.py` and `tests/validation/test_audit_local_trade_ohlcv_gaps.py`.
- 2026-06-30: compacted `CODEX_HANDOFF.md` into a single standing-state handoff with project overview, current state, recent changes, active tasks, known issues, and next steps.
- 2026-06-30: local trade/OHLCV gap auditor guard fix was committed in `d7d9e89`; the auditor now has fail-closed scan limits and a default runtime ceiling.

# Active Tasks

- Keep this handoff as the single current project-state file for Codex continuation.
- Keep `AGENTS.md` as the durable agent-rule file.
- Run `python -m scripts.validation.check_coordination_docs` after future coordination-doc edits when practical.
- Decide whether to run a capped local trade/OHLCV proof scan against `data\causal_proof_candidates\local_trade_2025_2026_v1`.
- Keep the seven pre-existing untracked broad build/loop files out of any documentation-only or proof-scan commit unless the user explicitly approves their disposition.

# Known Issues

- Severe: local trade/OHLCV proof is still no-go until capped proof evidence passes.
- Medium: generated candidate causal proof data/reports are ignored local artifacts and should not be staged by default.
- Medium: field-level point-in-time availability for optional metadata has not been proven.
- Medium: full 527-row promoted/canonical Phase 2 remains no-go.
- Medium: the original configured cwd `C:\Users\donny\Desktop\15_min_long_short` was absent; use `C:\Users\donny\Desktop\futures_intraday_model` unless the user says otherwise.
- Medium: branch is ahead of origin and contains local commits; verify sync intent before pushing or rebasing.
- Medium: seven broad-loop untracked files remain intentionally excluded.

# Next Steps

Exact next recommended step:

Approve or reject a capped local trade/OHLCV proof scan using existing local archives and `--causal-root data\causal_proof_candidates\local_trade_2025_2026_v1` for the same 29 uncovered markets and 2025/2026 only. The scan must specify explicit `--max-gap-windows`, `--max-trade-rows-scanned`, `--max-archives-read`, `--max-runtime-seconds`, `--progress-jsonl`, report output paths, shell timeout, and stop condition. Do not stage generated artifacts, refresh promoted Phase 2 reports, run broad build/loop files, promote canonical data, or touch modeling, WFA, metrics, predictions, cleanup, labels, feature matrices, or live/paper execution.

Fresh-thread prompt:

```text
Continue from CODEX_HANDOFF.md.

Goal: decide whether to run the capped local trade/OHLCV proof scan for the 29 uncovered markets and 2025/2026 only, using existing local archives and --causal-root data\causal_proof_candidates\local_trade_2025_2026_v1.

Rules:
- First verify repo path, git status, and the current CODEX_HANDOFF.md.
- Do not stage generated artifacts.
- Do not refresh promoted Phase 2 reports.
- Do not run broad build/loop files.
- Do not promote canonical data.
- Do not touch modeling, WFA, metrics, predictions, cleanup, labels, feature matrices, or live/paper execution.
- If approval is missing or the bounded command gate is incomplete, stop with a plan only.

Required bounds before any scan:
- explicit --max-gap-windows
- explicit --max-trade-rows-scanned
- explicit --max-archives-read
- explicit --max-runtime-seconds
- explicit --progress-jsonl
- explicit shell timeout
- explicit report output paths
- explicit stop condition
```
