# futures_intraday_model AGENTS.override.md

These instructions are repo-local guidance for this repository. For work inside this repo, follow this file over broader repository or global Codex guidance when there is a conflict, where allowed by higher-priority system or developer instructions. Do not defer to broader guidance for repo-specific choices.

Minimize tokens, reads, edits, commands, and output. Make the smallest safe change.

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

## Multi-step work

Use repo-local `CODEX_HANDOFF.md` only for work expected to continue across prompts or fresh Codex threads.
- At the start of non-trivial work, inspect repo path and `git status --short`, then read `CODEX_HANDOFF.md` if it exists before deciding scope.
- Treat `CODEX_HANDOFF.md` as persistent cross-run state, not final output.
- At the end of each multi-step run, update `CODEX_HANDOFF.md` before the final response with:
  - current status and what changed
  - files changed
  - commands run
  - validation/test results
  - unresolved blockers
  - remaining work
  - exact next recommended step
- Do not create or update `CODEX_HANDOFF.md` for simple one-shot tasks.
- When `CODEX_HANDOFF.md` exists and is updated, the final `Next` section must align with its exact next recommended step.
- If follow-up should continue in a fresh Codex thread, include the final `Next` copy-paste prompt that starts with `Continue from CODEX_HANDOFF.md.`

## Final output

Final response must contain only these sections, in this order:

### Done

- Include 1-3 completed items.
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

- Use `None.` if no next action.
- Otherwise use numbered action items for immediate next actions.
- A fenced next-run prompt is allowed under `Next` only when follow-up work should continue in a fresh Codex thread.
- If any Severe blockers exist, focus only on clearing the Severe blocker.
- If Medium blockers exist and no Severe blockers exist, focus on verification, caveat approval, or risk reduction.
- If no Medium or Severe blockers exist, name the next forward-progress task.
- Format each numbered item as:
  `1. Action -> expected result -> stop condition`
- If user input is required:
  `User decision needed: <specific decision>`
When follow-up work should continue in a fresh Codex thread, include a copy-paste-ready prompt under `Next` after the numbered action item using this format:

```text
Continue from CODEX_HANDOFF.md.
Next selected scope: <one row, one approved batch, or one decision>.
Rules:
- <forbidden actions>
- <scope limits>
- <validation requirements>
Task:
- <exact action 1>
- <exact action 2>
- <exact action 3>
Stop when:
- <clear acceptance condition>
```

The next-run prompt must include exact scope, files, commands, stop conditions, and forbidden actions as far as they are known. If exact scope is not known, state the required user decision instead of guessing.

Preserve project safety rules when relevant: no cleanup, no generated artifact staging, no unapproved build, no DBN/source mutation, and no commit unless explicitly requested.

If any Severe problem exists, the prompt must focus only on clearing that problem. If no Severe problems exist but Medium problems exist, the prompt must focus on verification, caveat approval, or risk reduction. If no Medium or Severe problems exist, the prompt must name the next forward-progress task.

Do not include vague items like "continue improving," "investigate further," or "clean things up."

### Metrics

```text
Elapsed time: <duration>
Token usage: <tokens>
```

Do not estimate or fabricate elapsed time or token usage. If metrics are unavailable, write `not available to agent`.

## Final output restrictions

- Do not include top-level sections other than `Done`, `Blockers`, `Next`, and `Metrics` unless explicitly requested.
- Do not include `Problems`, `Changed`, `Notes/blockers`, `Tests`, `Validation`, `Manual Check`, `Why`, `Added`, `Removed`, `Modified`, `Next Step(s)`, or similar sections unless explicitly requested.
