# futures_intraday_model AGENTS.md

These instructions are repo-local guidance for this repository. For work inside this repo, follow this file over broader repository or global Codex guidance when there is a conflict, where allowed by higher-priority system or developer instructions. Do not defer to broader guidance for repo-specific choices.

Minimize tokens, reads, edits, commands, and output. Make the smallest safe change.

## Runtime Preference

- Use `gpt5.5` with `extra high` reasoning for this project whenever the model and reasoning settings are user-controllable.
- If that model or reasoning level is unavailable, state the mismatch before substantive repo work and ask whether to proceed with a different setting.

## GitHub Upload Target

- This repository must upload to `https://github.com/donnywpolson-sudo/futures_intraday_model`.
- Do not push to any other remote. If `origin` points elsewhere, stop and ask for explicit approval before changing remotes or pushing.

## Codex Operating Discipline

- Be concise. Prefer concrete findings, file paths, commands, test results, and next actions over narration.
- Do not produce filler, praise, or repeated status updates that do not add new information.
- Do not expose hidden chain-of-thought. Provide brief rationale, assumptions, evidence, and decisions instead.
- Stay scoped to the user's latest request. Do not wander into unrelated refactors, speculative research, or broad cleanup.
- Before editing files, state the intended edit briefly.
- Distinguish evidence from assumptions. Evidence includes inspected files, command output, tests, and cited documentation. If something is inferred, label it as an assumption.
- Anti-loop rule: if the same approach fails twice, stop repeating it. Summarize the failure, change strategy, and proceed with a different diagnostic path.
- Blocker rule: after three unsuccessful attempts against the same blocker, stop and ask for the smallest missing input or approval needed to continue.
- Final responses should be short and outcome-focused: what changed, what was verified, and what remains.

## Workflow

- Work only in the active Git repo unless explicitly asked.
- Before editing, inspect repo path and `git status --short`.
- Implement directly when clear.
- Plan only for broad or risky work, under 120 words.
- Ask only to avoid wrong, destructive, or unactionable changes.
- Read targeted files only; search before opening many files.
- Skip generated, vendor, cache, build, data, log, and binary files unless relevant.
- Read files directly by path instead of asking for pasted large files, reports, logs, or full test output.
- Use short summaries instead of long copied output.
- Ask for full logs only when a short summary is not enough.

## Coordination source of truth

- `PIPELINE.md` is the project outline and runnable workflow authority. Update it only when phase order, phase commands, acceptance checks, stop conditions, or current project outline changes.
- `AGENTS.md` is the durable agent-rule authority. Update it only when agent behavior, safety policy, output format, bounded-command policy, or coordination maintenance rules change.
- `CODEX_HANDOFF.md` is mutable cross-run state. Update it after meaningful multi-step work, discovered blockers, research decisions, changed next steps, or any fresh-thread continuation need.
- Do not let `CODEX_HANDOFF.md` override repo evidence. Reconcile material handoff claims against `PIPELINE.md`, current files/reports, command output, and `git status` before acting.
- Run `python -m scripts.validation.check_coordination_docs` after coordination-doc edits when practical.

## Worktree hygiene

- Do not stage, commit, delete, move, or rename files unless explicitly asked.
- Do not add dependencies, perform broad refactors, or create generated artifacts unless explicitly asked.
- Preserve behavior and APIs unless the task requires changing them.
- Do not modify secrets, credentials, lockfiles, migrations, generated artifacts, or user work unless required or explicitly requested.
- Never store secrets, tokens, API keys, credentials, or private keys in repo files, prompts, memory, or config.

## Generated artifacts

Do not stage, commit, or intentionally preserve generated artifacts:

- parquet
- dbn
- zst
- generated csv/json reports
- logs
- cache files
- model pickles
- large data outputs

Validation commands may regenerate ignored `data/` and `reports/` artifacts. That is allowed, but they must remain untracked.

Some generated artifacts may already be tracked from prior repo history. Treat those as existing user work: do not refresh or edit them unless the task explicitly requires it. If validation incidentally changes already-tracked generated artifacts, report the paths and do not stage them without explicit approval.

After validation, run `git status --short` when practical and confirm generated artifacts are not tracked.

## Protected public contracts

Do not change these unless explicitly asked:

- CLI arguments
- config keys
- column names
- file paths
- output schemas
- report fields
- manifests
- test expectations

## Protected quant logic

No opportunistic refactors or semantic changes in:

- labels/targets
- feature computation
- session normalization
- causal gating
- WFA/train/test splits
- purge/embargo
- cost/slippage/commission math
- position policy
- validation checks
- metrics/reports/manifests
- timestamp alignment
- NaN handling
- row counts
- output formats

Cleanup is allowed only in already-touched non-core code, only if clearly behavior-preserving, small, and reviewable.

Prefer boring, explicit, readable code over clever or shorter code. If unsure whether a change is behavior-preserving, skip it.

## Quant research policy

- Prioritize research-process correctness over model complexity.
- Before model selection, tuning, or hyperparameter changes, verify data integrity, instrument metadata, target construction, timestamp alignment, leakage checks, walk-forward splits, purge/embargo, and cost/slippage/commission math.
- Treat any improvement as suspect until it survives locked out-of-sample validation with realistic costs and no post-test retuning.
- Prefer simple robust baselines before ML or complex ensembles.
- Record experiment scope, tested variants, validation windows, costs, warnings, and failure modes.
- Do not cherry-pick isolated metrics.
- For intraday futures, account for sessions, rolls, tick/point values, spreads, liquidity regime, partial fills, rejected orders, latency assumptions, and capacity before trusting PnL.
- Add or change risk controls before increasing strategy aggressiveness: max loss, position limits, volatility targeting, kill switch, stale-data guards, and order throttles.

## Minimum acceptance checklist before trusting WFA/model results

- Raw data coverage and missing-bar handling checked.
- Instrument definitions, tick size, point value, contract rolls, and session boundaries verified.
- Target construction, timestamp alignment, feature windows, and NaN handling checked for leakage.
- Walk-forward split boundaries, purge/embargo, and locked out-of-sample windows verified.
- Commission, fees, spread, slippage, delay, capacity, and contract multiplier assumptions enabled or explicitly documented.
- Simple baseline comparison included before accepting ML or complex model improvements.
- Result manifest records config, data scope, validation windows, costs, warnings, and failure modes.
- No post-test retuning or cherry-picked metric is used as acceptance evidence.

## Audited-answer policy

For material finance, quant research, trading, model-selection, data-integrity, backtest, execution, or external factual claims, answer as if the output will be audited.

A claim is material if it could affect research conclusions, data/model validity, validation results, trading or execution behavior, risk controls, cost/resource spend, external actions, or public/provider/vendor choices.

Purely mechanical edits, local formatting, typo fixes, narrow status reports, and command-output summaries are non-material unless they make or depend on a material claim.

When material, separate:

- verified facts
- inferences
- assumptions
- what could be wrong or stale
- what should be verified independently before acting

When material claims require these distinctions, include them inside the allowed final sections instead of adding extra headings. Put completed verified evidence under `Done`, unresolved caveats under `Blockers`, and independent verification steps under `Next`.

Primary sources include exchange/regulator/vendor documentation, repo files, raw data, command/test output, local artifacts, and reproducible validation results.

Do not treat AI consensus as truth. Cross-model review is useful only as adversarial review; final acceptance requires primary evidence or reproducible local checks.

Do not recommend a product, trade, service, broker, platform, vendor, data provider, or model unless the reasoning survives without affiliate, advertising, ecosystem, or provider incentive.

If primary evidence is unavailable, stale, or inaccessible, say so explicitly and do not present the claim as verified.

## Validation/check policy

- Run the narrowest relevant check only when warranted by the change, safety risk, protected core logic, or explicit request.
- Prefer targeted tests while working.
- For data/model/WFA changes, prefer lightweight validation of affected artifacts, row counts, warnings, generated-file hygiene, and model/backtest metric deltas when practical.
- Ask before running full or expensive test suites.
- If a check fails before Python starts due to sandbox/spawn/permission handling, retry once with scoped approval if available.
- Do not treat pre-launch sandbox/spawn failures as project failures.
- Treat validation as failed only if Python launches and returns a traceback, failed assertion, failed test, or nonzero exit code.
- Do not add separate final sections named `Tests`, `Validation`, `Manual Check`, `Added`, `Removed`, `Modified`, `Changed`, `Notes`, or similar unless explicitly requested.
- Successful checks may be mentioned briefly under `Done` when material.
- Mention only unresolved failed checks, blockers, generated-artifact risks, row-count/model-metric risks, or caveats under `Blockers`.

## Bounded command gate

Before running expensive, broad, or high-risk commands, the current prompt, plan, or handoff must specify:

- exact command class or command family
- maximum scope, such as markets, years, rows, chunks, files, or profiles
- timeout or stopping budget
- checkpoint, report, or log output path when relevant
- forbidden command patterns
- expected generated artifacts and whether they are ignored or tracked
- stop condition and required evidence before continuing

This gate applies to provider/network downloads, broad data builds, report or artifact generators, cleanup/archive/quarantine actions, WFA/modeling, predictions, metrics, promotion gates, and any command that can mutate `data/**`, `reports/**`, models, predictions, configs, or manifests.

If the gate is incomplete, do not run the command. Ask for the missing decision or produce a bounded plan instead.

## Multi-step work

Use repo-local `CODEX_HANDOFF.md` only for work expected to continue across prompts or fresh Codex threads.
- For this solo project, keep only `AGENTS.md` and `CODEX_HANDOFF.md` as Codex coordination docs; do not create `PROJECT_STATE.md`, `research/JOURNAL.md`, or parallel handoff/state files unless explicitly requested.
- Maintain `CODEX_HANDOFF.md` whenever:
  - A major feature is completed
  - Strategy direction changes
  - New issues are discovered
  - Research conclusions are reached
- At the start of non-trivial work, inspect repo path and `git status --short`, then inspect `CODEX_HANDOFF.md` if it exists before deciding scope. Read only the newest/current active section first; treat older sections as historical evidence, not default instructions. Search older handoff history only when the newest section points to it, current state is ambiguous, or exact evidence is needed.
- Treat `CODEX_HANDOFF.md` as mutable cross-run state, not committed truth, final output, or approval by itself. Reconcile it against current repo files, reports, command output, and `git status` before relying on material claims.
- At the end of each multi-step run, update `CODEX_HANDOFF.md` before the final response with:
  - current status and what changed
  - files changed
  - commands run
  - validation/test results
  - unresolved blockers
  - remaining work
  - exact next recommended step
- Keep the newest active section short and easy to scan. Put current status, blockers, and exact next recommended step before historical detail.
- Superseded `Exact Next Recommended Step` blocks are historical evidence only and must not be treated as active instructions.
- Do not create or update `CODEX_HANDOFF.md` for simple one-shot tasks.
- When `CODEX_HANDOFF.md` exists and is updated, the final `Next` section must align with its exact next recommended step.
- If follow-up should continue in a fresh Codex thread, include the final `Next` copy-paste prompt that starts with `Continue from CODEX_HANDOFF.md.`
- Do not stage, commit, revert, or otherwise dispose of `AGENTS.md` or `CODEX_HANDOFF.md` unless the user explicitly approves the exact disposition: leave local, commit as documentation-only scope, or revert.

## Output Style

- Be concise.
- Do not include long reasoning, tutorials, full diffs, repeated code dumps, praise, or chain-of-thought unless asked.
- Final responses must use only the sections listed below.
- Exception: when the user explicitly asks for an audit, review, or prompt-template output with a specific structure, use the requested finding-first or template format instead of the default final sections. This exception changes only response format; all safety, scope, and evidence rules still apply.

## Final Output

For normal implementation, status, and handoff runs, final response must contain only these sections, in this order:

### Done

- Include 1-3 completed items.
- Include concrete files touched, checks run, and elapsed time/token usage when available.
- Omit this section if nothing completed.

### Blockers

- If no blockers: `None. Proceed status: yes.`
- Show only `Low`, `Medium`, or `Severe` tiers that contain blockers.
- Use `Low` for minor follow-up only with no correctness, safety, validation, data, or goal impact.
- Use `Medium` for real caveats, incomplete verification, or non-blocking risks; result is usable but should be verified before merge, cleanup, promotion, or broader execution.
- If only Low blockers exist, end with: `Proceed status: yes.`
- Use `Severe` for blocking issues where the result is unsafe, invalid, misleading, incomplete, or not ready.
- If any Medium blockers exist, end with: `Proceed status: yes with medium blockers.`
- If any Severe blockers exist, end with: `Proceed status: no.`
- Do not include generic notes or completed work here.
- Use concrete evidence where applicable: command output, failed test name, file path, metric, row count, or report path.

### Next

- Use exactly one of: `None.`, one human decision request, or one bounded executable phase.
- Use `None.` when the requested objective is complete, no Medium or Severe blockers remain, and there is no concrete user-approved next phase.
- Do not create recursive prompt loops. After an implementation run completes, the default `Next` is `None.` unless real remaining work, an unresolved blocker, an explicit fresh-thread handoff, or a required human decision exists.
- Provide a fenced Plan Mode handoff prompt only when follow-up work is actually needed. For simple completed tasks with no meaningful follow-up, use `None.`.
- When providing a handoff prompt, output one copy-paste-ready Plan Mode prompt in a fenced `text` block, with no prose outside the block.
- Do not write `None.` merely because the next step is unclear while Medium or Severe blockers, unfinished scope, or missing decisions remain. In those cases, hand off a Plan Mode prompt focused on the blocker or decision.
- The Plan Mode prompt is a planning handoff. Its required output should normally be one decision-complete `<proposed_plan>` block that the user can execute with `Implement Plan`; it must not ask Plan Mode to create a second execution prompt or another generic plan unless a real decision/blocker prevents execution planning.
- Do not request, generate, or refer to retired pursue-goal workflow handoffs.
- Allow Plan Mode to include a short blocker or decision note only when it cannot produce a decision-complete `<proposed_plan>` without user input.
- Include exact current status, next scope, relevant files/artifacts, commands, rules/forbidden actions, stop conditions, and validation requirements as far as they are known.
- If exact scope is unknown, make the Plan Mode prompt request the required user decision or choose between concrete options instead of guessing.
- If any Severe blockers exist, the Plan Mode prompt must focus only on clearing the Severe blocker.
- If Medium blockers exist and no Severe blockers exist, the Plan Mode prompt must focus on verification, caveat approval, or risk reduction.
- If no Medium or Severe blockers exist but real follow-up remains, the Plan Mode prompt must name the next full pursued objective or next gated phase, not automatically shrink the work below the user's pursued scope. If no real follow-up remains, use `None.` instead of a prompt.
- For a bounded executable phase, include the bounded command gate fields when any expensive, broad, data/model, provider/network, or generated-artifact command is involved.
- When follow-up should continue in a fresh Codex thread, include `Continue from CODEX_HANDOFF.md.` near the top of the prompt.
- Preserve project safety rules when relevant: no generated artifact staging, no raw data mutation, no unapproved pipeline/model run, no cleanup beyond the approved scope, and no commit unless explicitly requested.
- Do not include vague items like "continue improving," "investigate further," or "clean things up."

Preferred `Next` prompt format:

`PLAN MODE` is a copy-paste workflow convention. The active runtime mode is controlled only by the environment's current system/developer instructions; if those conflict with copied prompt text, obey the active runtime instructions.

```text
You are in PLAN MODE.

Parent project goal:
- <one sentence describing the larger repo/project goal>

Current milestone:
- <active phase, checkpoint, or blocker being cleared>

Progress ledger:
- Verified current state:
  - <repo status, dirty files, accepted evidence, blockers>
- Completed last step:
  - <exact thing completed>
- Remaining known work:
  - <known next phases, blockers, or None>

Next atomic goal:
- <one small, testable goal that directly advances the current milestone>

Relevant files/artifacts:
- <paths, reports, handoff files, configs, or generated artifacts to inspect/preserve>

Required first step:
- Re-check repo state and handoff truth before planning:
  - git status --short --untracked-files=all
  - git status --ignored --short -- <relevant ignored/local paths if any>
  - git diff -- <relevant tracked paths if dirty>
  - Read CODEX_HANDOFF.md first when present and relevant.
- If current state conflicts with this prompt, trust the fresh repo evidence and call out the conflict.

Rules:
- Do not edit files.
- Do not stage, unstage, commit, or run destructive commands.
- Do not broaden scope.
- Do not read secrets or print env-file contents.
- Preserve project safety rules:
  - no generated artifact staging
  - no raw data mutation
  - no unapproved pipeline/model runs
  - no cleanup beyond the approved scope
  - no commit unless explicitly requested

Plan output required:
1. Brief diagnosis of the refreshed state.
2. One recommended next action.
3. One complete `<proposed_plan>` block for the next executable phase or blocker-clearing decision.
4. Exact read-only verification commands and approval-required implementation commands, clearly separated.
5. Acceptance criteria and stop conditions.
6. Updated `Next` handoff only if real follow-up remains after the planned work; otherwise specify that final `Next` should be `None.`

The user will press `Implement Plan`; do not produce a separate execution prompt.
```

## Final Output Restrictions

- Do not include top-level final-response sections other than `Done`, `Blockers`, and `Next` unless explicitly requested or using the audit/review/template exception above.
- Higher-priority required appendages, such as app/tool directives, memory citations, or system/developer-mandated wrappers, are allowed after the required repo-local sections. Keep them minimal and do not use them for extra narrative.
- Do not include `Problems`, `Changed`, `Notes/blockers`, `Tests`, `Validation`, `Manual Check`, `Why`, `Added`, `Removed`, `Modified`, `Next Step(s)`, `Next Codex Prompt`, or similar sections unless explicitly requested.
- Under `Next`, use either `None.` or one fenced Plan Mode prompt. Do not include free-standing action lists, summaries, or explanations outside the fenced prompt.
- The fenced Plan Mode prompt is a handoff artifact only for real continuation work. It must produce one implementable plan that the user can execute with `Implement Plan`.
