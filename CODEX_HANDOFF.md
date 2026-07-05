# Project Overview

- Project: `futures_intraday_model`.
- Purpose: intraday futures research pipeline using Databento continuous-contract 1-minute OHLCV data.
- Status framing: research and walk-forward validation only; this is not live-trading or production readiness.
- Project outline authority: use `PROJECT_OUTLINE.md` for objective, layout, phase order, runnable phase commands, acceptance checks, and stop conditions.
- Repo guidance authority: use `AGENTS.md` for agent workflow, safety rules, bounded-command policy, and final-response format.
- Handoff role: this file is mutable cross-run state. Reconcile all material claims against current repo files, reports, command output, and `git status` before acting.
- Solo Codex files: keep `AGENTS.md`, `PROJECT_OUTLINE.md`, and `CODEX_HANDOFF.md` only; do not create `PROJECT_STATE.md`, `research/JOURNAL.md`, or parallel handoff/state files unless explicitly requested.

# Superseded Context

- This handoff was compacted on 2026-07-05 to remove stale executable prompts, old approval packets, obsolete exact-next blocks, and historical command catalogs from the active handoff.
- Exact historical run text remains recoverable from git history when needed.
- Any older instruction that points to stopped ES 2026 label wrappers, retired rescue actions, proof scans, discovery reruns, WFA/modeling, promotion, staging, commit, push, paper, or live action is historical only unless revalidated against `PROJECT_OUTLINE.md`, current files/reports, command output, and `git status`.

# Current State

- The bulk alpha-discovery queue runner v1, dry-run candidate generator v1, Phase 9 wizard entry, optional discovery-run step, launcher self-check, and autopsy module are implemented and ready for review.
- `C:\Users\donny\Desktop\RUN_ALPHA_DISCOVERY.bat` is the user-facing launcher and supports no-arg wizard mode, `--self-check`, dry-run candidate generation `--generate-candidates`, single-candidate `--config`, and serial queue `--queue` modes.
- The repo-owned launcher template is `RUN_ALPHA_DISCOVERY.bat`; the Desktop launcher was copied from it and currently passes static self-check.
- `scripts.validation.run_alpha_discovery_queue` consumes already-created candidate-specific config JSON files; it does not generate, register, mutate, stage, commit, promote, paper trade, or live trade.
- `scripts.validation.generate_alpha_discovery_candidates` consumes an explicit candidate spec, writes copied preflight-only candidate configs and one queue file under `configs/`, refuses overwrites, enforces max 100 candidates, and does not mutate registry/status, reports, data, logs, or models.
- Candidate generation now requires canonical Phase 9 target-discovery readiness: each candidate must be a clean `CANDIDATE` in canonical target registry/status files and supported by the ES 30m target smoke harness `TARGET_SPECS`.
- Queue modes mirror the single-candidate runner: `preflight`, `source-tests`, `discovery-packet`, `discovery-run`, and `review`.
- `discovery-run` remains approval-bound: it requires `--approve-discovery-run`, the non-secret approval phrase `RUN_PHASE9_DISCOVERY_ONCE`, and `approved=true` on each queue entry.
- Queue discovery defaults to at most 10 candidates per invocation, has an absolute 100-candidate cap, runs serially, and records timeout as `STOP_INFRASTRUCTURE_TIMEOUT` with `RETRY_WITH_BOUNDED_INFRA_FIX`.
- Queue logs are ignored generated artifacts under `logs/alpha_discovery_queue/`; single-candidate logs remain under `logs/alpha_discovery/`.
- Wizard readiness autopsy writes ignored reports under `reports/pipeline_audit/alpha_discovery_autopsy/<batch>/readiness/` after generation/preflight and stamps reports `FEASIBILITY ONLY - NOT MODEL-TRUST EVIDENCE - DO NOT RETUNE FROM THIS AUTOPSY`.
- If the user explicitly chooses optional discovery-run, the wizard prints the exact Desktop-launcher queue command, requires the fixed acknowledgement plus `RUN_PHASE9_DISCOVERY_ONCE`, writes a separate approved queue copy under `configs/`, runs bounded queue discovery, and writes post-discovery autopsy under `reports/pipeline_audit/alpha_discovery_autopsy/<batch>/discovery/`.
- Wrapper or queue completion is not candidate success. Candidate status must still be read from generated JSON when present.
- `DISCOVERY_PASS` is a candidate pass. Any `STOP_*` JSON decision is a candidate stop even if the subprocess exits `0`.
- Missing JSON/MD outputs remain `DISCOVERY_RUN_REVIEW_REQUIRED`.
- Generated configs may still fail later runner preflight for stale outputs or missing generated-output ignore rules, but the generator now blocks unregistered, non-canonical, advanced, stopped, or unsupported target candidates before writing configs.

# Recent Changes

- 2026-07-05 added `scripts/validation/run_alpha_discovery_queue.py`, `configs/alpha_discovery_queue.example.json`, `.bat` queue routing, queue tests, and a `PROJECT_OUTLINE.md` queue-runner note.
- 2026-07-05 updated and copied the launcher to `C:\Users\donny\Desktop\RUN_ALPHA_DISCOVERY.bat` so it enters the repo root before calling Python.
- 2026-07-05 added `scripts/validation/generate_alpha_discovery_candidates.py`, `configs/alpha_discovery_candidates.example.json`, generator tests, Desktop `.bat` generator routing, and a `PROJECT_OUTLINE.md` generator note.
- 2026-07-05 tightened the generator with a canonical Phase 9 target-discovery gate tied to `manifests/target_hypotheses/*` and the ES 30m smoke harness target specs.
- 2026-07-05 added repo-owned `RUN_ALPHA_DISCOVERY.bat`, `scripts.validation.run_alpha_discovery_wizard`, `scripts.validation.alpha_discovery_autopsy`, static launcher self-check, Desktop launcher sync, safe autopsy wording, bounded queue discovery caps, and child-process-tree timeout cleanup.
- 2026-07-05 completed the wizard optional discovery-run branch: exact command display, fixed acknowledgement and approval phrase, approved queue copy, bounded queue invocation, and post-discovery autopsy.
- 2026-07-05 targeted validation passed: `python -m pytest -q tests\validation\test_alpha_discovery_wizard.py tests\validation\test_alpha_discovery_autopsy.py tests\validation\test_run_alpha_discovery_queue.py tests\validation\test_run_alpha_discovery.py tests\validation\test_generate_alpha_discovery_candidates.py`.
- 2026-07-05 targeted validation passed: `python -m pytest -q tests\validation\test_run_alpha_discovery.py tests\validation\test_run_alpha_discovery_queue.py`.
- 2026-07-05 compacted this handoff so active state is short, current, and checker-enforced.
- 2026-07-05 hardened `scripts/validation/check_coordination_docs.py` to cap active handoff length and reject duplicate or stale continuation markers.
- 2026-07-05 preserved the current `README.md` rewrite while restoring the checker-compatible `PROJECT_OUTLINE.md` / `PIPELINE.md` source-of-truth sentence.
- Older detailed run chronology was intentionally removed from active handoff text; use git history only if exact historical command text is needed.

# Active Tasks

- Review the wizard, autopsy, queue runner, generator diffs, and targeted validation.
- Use no-arg `C:\Users\donny\Desktop\RUN_ALPHA_DISCOVERY.bat` for the guided wizard only after intended Phase 9 target-discovery candidates are canonical registered.
- Keep all discovery execution behind separate bounded approval of the exact command.

# Known Issues

- Historical blocked research/data branches are not active instructions.
- Active blockers must be re-derived from `PROJECT_OUTLINE.md`, registries/manifests, current files/reports, command output, and `git status`.
- Generated artifacts under `data/`, `reports/`, and `logs/` remain ignored unless explicitly approved.
- The current `README.md` rewrite is user work and should be preserved unless the user asks for broader edits.
- Generator v1 expands copied configs only; it does not create valid canonical hypotheses or change registry/status ledgers. Candidate registration remains a separate prerequisite.
- The Desktop launcher self-check assumes the repo remains at `%USERPROFILE%\Desktop\futures_intraday_model` and blocks if the Desktop launcher differs from the repo template.
- This handoff is intentionally capped; future updates should summarize or replace active state instead of appending chronology.

# Next Steps

Exact next recommended step: register any intended Phase 9 target-discovery candidates in canonical target registry/status files first, then double-click `C:\Users\donny\Desktop\RUN_ALPHA_DISCOVERY.bat` to run the guided wizard through generation, queue preflight, readiness autopsy, and optional bounded discovery-run only if the wizard prints the exact command and the user supplies the required acknowledgement plus approval phrase; do not run confirmation, locked smoke, WFA/modeling, Phase 8, tuning, promotion, registry/status mutation, staging, commit, push, paper, or live trade.
