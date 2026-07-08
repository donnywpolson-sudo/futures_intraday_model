# futures_intraday_model AGENTS.md

These instructions are repo-local guidance for this repository. For work inside this repo, follow this file over broader repository or global Codex guidance when there is a conflict, where allowed by higher-priority system or developer instructions. Do not defer to broader guidance for repo-specific choices.

Minimize tokens, reads, edits, commands, and output. Make the smallest safe change.

## Project-Specific Rules

### Runtime And Remote Guards

- Use `gpt5.5` with `extra high` reasoning for this project whenever the model and reasoning settings are user-controllable.
- If that model or reasoning level is unavailable, state the mismatch before substantive repo work.
- This repository must upload to `https://github.com/donnywpolson-sudo/futures_intraday_model`.
- Do not push to any other remote. If `origin` points elsewhere, stop and ask for explicit approval before changing remotes or pushing.

### Coordination Source Of Truth

- `PROJECT_OUTLINE.md` is the project outline, workflow, and runnable command authority. Update it only when the project objective, layout, phase order, phase commands, acceptance checks, stop conditions, or current project outline changes.
- `PIPELINE.md`, when kept, is a compatibility pointer for older references only. Do not add parallel phase checklists or runnable command catalogs there.
- `AGENTS.md` is the durable agent-rule authority. Update it only when agent behavior, safety policy, output format, bounded-command policy, or coordination maintenance rules change.
- `CODEX_HANDOFF.md` is mutable cross-run state. Update it after meaningful multi-step work, discovered blockers, research decisions, changed next steps, or any fresh-thread continuation need.
- Do not let `CODEX_HANDOFF.md` override repo evidence. Reconcile material handoff claims against `PROJECT_OUTLINE.md`, current files/reports, command output, and `git status` before acting.
- Run `python -m scripts.validation.check_coordination_docs` after coordination-doc edits when practical.

### Handoffs

- Use repo-local `CODEX_HANDOFF.md` only for work expected to continue across prompts or fresh Codex threads.
- For this solo project, keep only `AGENTS.md`, `PROJECT_OUTLINE.md`, and `CODEX_HANDOFF.md` as root coordination docs; do not create `PROJECT_STATE.md`, `research/JOURNAL.md`, or parallel handoff/state files unless explicitly requested.
- At the start of non-trivial work, inspect repo path and `git status --short`, then inspect `CODEX_HANDOFF.md` if it exists before deciding scope. Read only the newest/current active section first; treat older sections as historical evidence, not default instructions.
- Maintain `CODEX_HANDOFF.md` whenever a major feature completes, strategy direction changes, new issues are discovered, research conclusions are reached, or a fresh-thread continuation is needed.
- At the end of each multi-step run, update `CODEX_HANDOFF.md` before the final response with current status, files changed, commands run, validation results, blockers, remaining work, and the exact next recommended step.
- Keep the newest active section short and easy to scan. Put current status, blockers, and exact next recommended step before historical detail.
- Superseded `Exact Next Recommended Step` blocks are historical evidence only and must not be treated as active instructions.
- Do not create or update `CODEX_HANDOFF.md` for simple one-shot tasks.
- When `CODEX_HANDOFF.md` is updated, the final `Suggestions` section must align with its exact next recommended step.
- If follow-up should continue in a fresh Codex thread, include a `Suggestions` copy-paste prompt that starts with `Continue from CODEX_HANDOFF.md.`

### Protected Repo Surfaces

- Do not stage, commit, delete, move, rename, or revert files unless explicitly asked.
- Do not add dependencies, perform broad refactors, create generated artifacts, or change behavior/APIs unless the task requires it.
- Preserve user work, secrets, credentials, lockfiles, migrations, generated artifacts, and local data unless the task explicitly requires touching them.
- Never store secrets, tokens, API keys, credentials, or private keys in repo files, prompts, memory, or config.
- Do not stage, commit, or intentionally preserve generated artifacts: parquet, dbn, zst, generated csv/json reports, logs, cache files, model pickles, or large data outputs.
- Validation commands may regenerate ignored `data/` and `reports/` artifacts. That is allowed, but they must remain untracked.
- Some generated artifacts may already be tracked from prior repo history. Treat those as existing user work: do not refresh or edit them unless the task explicitly requires it. If validation incidentally changes already-tracked generated artifacts, report the paths and do not stage them without explicit approval.
- After validation, run `git status --short` when practical and confirm generated artifacts are not tracked.

### Protected Public Contracts

Do not change these unless explicitly asked:

- CLI arguments
- config keys
- column names
- file paths
- output schemas
- report fields
- manifests
- test expectations

### Protected Quant Logic

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

### Quant Research Guardrails

- Prioritize research-process correctness over model complexity.
- Before model selection, tuning, or hyperparameter changes, verify data integrity, instrument metadata, target construction, timestamp alignment, leakage checks, walk-forward splits, purge/embargo, and cost/slippage/commission math.
- Treat any improvement as suspect until it survives locked out-of-sample validation with realistic costs and no post-test retuning.
- Prefer simple robust baselines before ML or complex ensembles.
- Do not cherry-pick isolated metrics, retune after a test, or treat generated summaries as proof without primary evidence.
- Record experiment scope, tested variants, validation windows, costs, warnings, and failure modes.
- For intraday futures, account for sessions, rolls, tick/point values, spreads, liquidity regime, partial fills, rejected orders, latency assumptions, capacity, max loss, position limits, volatility targeting, stale-data guards, order throttles, and kill switches before trusting PnL or increasing aggressiveness.
- Use `PROJECT_OUTLINE.md` for detailed model-trust gates, runnable workflow, acceptance standards, and stop conditions.
- Do not make promotion, paper-trading, live-trading, provider, broker, vendor, or model-selection recommendations unless the reasoning survives without affiliate, advertising, ecosystem, or provider incentive.

### Research Claims And Audit Standard

For material finance, quant research, trading, model-selection, data-integrity, backtest, execution, or external factual claims, answer as if the output will be audited.

A claim is material if it could affect research conclusions, data/model validity, validation results, trading or execution behavior, risk controls, cost/resource spend, external actions, or public/provider/vendor choices.

Purely mechanical edits, local formatting, typo fixes, narrow status reports, and command-output summaries are non-material unless they make or depend on a material claim.

When material, separate verified facts, inferences, assumptions, what could be wrong or stale, and what should be verified independently before acting. Include those distinctions inside the allowed final output format instead of adding extra headings.

Primary sources include exchange/regulator/vendor documentation, repo files, raw data, command/test output, local artifacts, and reproducible validation results.

Do not treat AI consensus as truth. Cross-model review is useful only as adversarial review; final acceptance requires primary evidence or reproducible local checks.

If primary evidence is unavailable, stale, or inaccessible, say so explicitly and do not present the claim as verified.

### Bounded Execution

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

For data/model/WFA changes, prefer lightweight validation of affected artifacts, row counts, warnings, generated-file hygiene, and model/backtest metric deltas when practical.

## General Codex Rules For This Repo

### Work Style

- Be concise. Prefer concrete findings, file paths, commands, test results, and next actions over narration.
- Do not produce filler, praise, or repeated status updates that do not add new information.
- Do not expose hidden chain-of-thought. Provide brief rationale, assumptions, evidence, and decisions instead.
- Stay scoped to the user's latest request. Do not wander into unrelated refactors, speculative research, or broad cleanup.
- Implement directly when clear. Plan only for broad, risky, destructive, or ambiguous work.
- Ask only to avoid wrong, destructive, or unactionable changes.
- Read targeted files only; search before opening many files.
- Skip generated, vendor, cache, build, data, log, and binary files unless relevant.
- Read files directly by path instead of asking for pasted large files, reports, logs, or full test output.
- Use short summaries instead of long copied output. Ask for full logs only when a short summary is not enough.

### Repo Safety Before Edits

- Work only in the active Git repo unless explicitly asked.
- Before editing, inspect repo path and `git status --short`.
- Before editing files, state the intended edit briefly.
- If existing files are dirty, work with those changes and do not assume they are yours.
- Do not overwrite, revert, delete, move, rename, stage, commit, or push unless explicitly asked.
- Do not run destructive commands unless explicitly approved.
- Do not modify secrets, credentials, lockfiles, migrations, generated artifacts, or user work unless required or explicitly requested.

### Evidence And Failure Handling

- Distinguish evidence from assumptions. Evidence includes inspected files, command output, tests, and cited documentation. If something is inferred, label it as an assumption.
- Anti-loop rule: if the same approach fails twice, stop repeating it. Summarize the failure, change strategy, and proceed with a different diagnostic path.
- Blocker rule: after three unsuccessful attempts against the same blocker, stop and ask for the smallest missing input or approval needed to continue.

### Validation Checks

- Run the narrowest relevant check only when warranted by the change, safety risk, protected core logic, or explicit request.
- Prefer targeted tests while working.
- Ask before running full or expensive test suites.
- If a check fails before Python starts due to sandbox/spawn/permission handling, retry once with scoped approval if available.
- Do not treat pre-launch sandbox/spawn failures as project failures.
- Treat validation as failed only if Python launches and returns a traceback, failed assertion, failed test, or nonzero exit code.

### Final Response Format

- Output language has three user-selectable levels. Default for this repo is `Level 2: Plain English / Balanced`.
- If the user asks to use `Level 1`, `Level 2`, or `Level 3`, switch to that level for future replies in this repo until the user changes it again. A requested level changes wording density only; it does not override required sections, repo safety rules, bounded execution, evidence discipline, or audit requirements.
- `Level 1: Caveman / Ultra Simple`: use the shortest plain-English wording. Prefer short sentences, minimal jargon, and only the result, real problems, and one next action.
- `Level 2: Plain English / Balanced`: use clear everyday language with concrete files, commands, checks, and caveats. Keep audit terms only when they materially matter.
- `Level 3: Detailed / Rigorous / Precise`: use more exact evidence, assumptions, risks, and technical terms while staying concise. Use this for audits, high-risk changes, or when the user asks for rigorous detail.
- Be concise and outcome-focused.
- Start with a concise opening outcome when there is a completed result to report. Include the concrete result, files touched, and checks run there instead of using a `Done` section. Omit the opening outcome only when nothing completed.
- For normal implementation, status, and handoff runs, use only these real final sections in this order:
  - `Problems`: write `None. Proceed status: yes.` when clear. Otherwise list only real problems or caveats as `Low`, `Medium`, or `Severe`, with concrete evidence where practical. End with `Proceed status: yes.`, `Proceed status: yes with medium problems.`, or `Proceed status: no.`
  - `Suggestions`: write `None.` only when the request is complete and no useful continuation remains. Otherwise give exactly one next action: one human decision, one bounded executable phase, or one fenced paste-ready prompt.
- Mention successful validation briefly in the opening outcome. Mention only unresolved failed checks, generated-artifact risks, row-count/model-metric risks, or material caveats under `Problems`.
- Do not add extra final sections such as `Tests`, `Validation`, `Notes`, `Changed`, or `Next Steps` unless the user explicitly asks for that format.
- If the user asks for an audit, review, or prompt template with a specific structure, use the requested structure while preserving all repo safety rules.
- Required system/developer appendages, app directives, git directives, and memory citations may appear after the repo-local final sections, but keep them minimal.
- For `Suggestions`, use `None.` only for true terminal one-shot work. If any nontrivial, risky, broad, data/model, provider/network, generated-artifact, WFA, cleanup, mutating, or fresh-thread follow-up remains, prefer one fenced paste-ready prompt.
- Use a human decision only when the agent cannot safely choose.
- Use a bounded executable phase only when follow-up is ready to run. For expensive, broad, data/model, provider/network, generated-artifact, WFA, cleanup, or mutating work, include command family, scope limit, timeout or stop budget, artifacts, forbidden patterns, expected generated files, and stop condition.
- A paste-ready prompt must state whether the next agent should plan only or execute, name the target objective, require repo path and `git status --short` inspection, require reconciliation against `CODEX_HANDOFF.md`, `PROJECT_OUTLINE.md`, and current evidence, and include exact bounded scope, forbidden actions, artifacts, timeout or stop budget, stop condition, and validation expectations.
- If execution is not already safely bounded, the paste-ready prompt must request one implementable `<proposed_plan>` and explicitly say not to mutate files or run data/model commands yet.
- When `CODEX_HANDOFF.md` was updated or fresh-thread continuation is likely, start the paste-ready prompt with `Continue from CODEX_HANDOFF.md.`
- Do not use vague suggestions such as `continue implementation`, `run next phase`, or `improve the model`; convert them into `None.`, one human decision, one bounded executable phase, or one fenced paste-ready prompt.
- When `CODEX_HANDOFF.md` is updated, final `Suggestions` must match its exact next recommended step.
