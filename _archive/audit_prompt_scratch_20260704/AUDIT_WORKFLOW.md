# Pipeline Audit Workflow

This file is an operator guide for the pipeline-outline audit loop. It is not a
source of truth for pipeline behavior, approvals, research conclusions, or
current project state.

## File Roles

- `AUDIT.md`: audit prompt/spec. It defines the allowed evidence, audit scope,
  required gates, output format, scorecard, and next-action rules.
- `PROJECT_OUTLINE.md`: audit target and pipeline authority. Fix audit findings
  here when the issue is about phase order, gates, commands, acceptance checks,
  stop conditions, or downstream blockers.
- `docs/pipeline_outline_audit.md`: audit output/report. Refresh this after
  running `AUDIT.md`; do not treat it as the source of truth.
- `AGENTS.md`: repo operating rules for scope, safety, bounded commands,
  output format, and coordination-doc policy.
- `CODEX_HANDOFF.md`: mutable continuation state for multi-step work. Use it to
  preserve current blockers and next steps, but reconcile it against current
  files and command output before acting.

## Audit Loop

1. Preflight `AUDIT.md`.
   - Verify the repo root and inspect `git status --short`.
   - Check the `Project context`, `Non-authoritative phase checklist`, and
     `Audit rules` sections against the current `PROJECT_OUTLINE.md`.
   - Update stale orientation text in `AUDIT.md` before running the audit. Keep
     the audit target as `PROJECT_OUTLINE.md`.
2. Run `AUDIT.md`.
   - Audit `PROJECT_OUTLINE.md` only.
   - Do not run training, backtests, downloads, broad scans, cleanup, staging,
     commits, pushes, or generated data/model artifact commands.
   - Write or refresh `docs/pipeline_outline_audit.md` with the audit result.
3. Triage findings.
   - Extract exactly one `Next Action` from the audit output.
   - If the finding is an obvious docs-only outline gap, patch
     `PROJECT_OUTLINE.md`.
   - If the finding requires code, data, generated reports, model runs, provider
     calls, or ambiguous research judgment, do not execute it directly. Write a
     bounded plan or explain why it cannot be safely fixed from outline evidence
     alone.
4. Validate and repeat.
   - Run narrow validation:
     - `python -m scripts.validation.check_coordination_docs`
     - `git diff --check -- AUDIT.md PROJECT_OUTLINE.md docs/pipeline_outline_audit.md AUDIT_WORKFLOW.md`
   - Re-run `AUDIT.md` and refresh `docs/pipeline_outline_audit.md`.
   - Repeat until the audit output has no remaining findings or one explicit
     approval-bound next action.

## Efficient Next-Action Format

When refreshing `docs/pipeline_outline_audit.md`, end with one machine-readable
block so the next step is easy to apply:

```text
NEXT_ACTION:
type: docs_only_fix | rerun_audit | approval_required | none
target_file:
summary:
bounded_command:
```

Use `docs_only_fix` only when the fix is a narrow documentation change in
`PROJECT_OUTLINE.md` or another explicitly named doc. Use `approval_required`
when any command could mutate data, reports, models, predictions, configs,
manifests, provider state, or live/paper execution paths.

## Fix Rules

- Fix the audit target, usually `PROJECT_OUTLINE.md`, not the audit report.
- Keep `docs/pipeline_outline_audit.md` as a report of the latest audit run.
- Do not use old audit output, handoff notes, or prior conversation as proof of
  current pipeline state.
- If `PROJECT_OUTLINE.md` and `docs/pipeline_outline_audit.md` conflict,
  inspect the current files and rerun the audit.
- Keep fixes small and reviewable. One audit finding should usually produce one
  focused docs patch plus one refreshed audit report.

## Stop Conditions

Stop and ask for approval before running any non-doc command that can:

- mutate `data/**`, `reports/**`, models, predictions, configs, or manifests;
- download provider data or touch provider state;
- run WFA/modeling, metrics, proof scans, promotion, freeze, live, or paper
  execution;
- stage, commit, push, delete, move, or archive files.

For those actions, provide a bounded plan with command family, maximum scope,
timeout/stop budget, expected artifacts, forbidden patterns, stop condition, and
required evidence before proceeding.
