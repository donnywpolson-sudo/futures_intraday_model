# futures_intraday_model instructions

Scope and worktree hygiene:

* Work only in the active Git repo unless explicitly asked.
* Before editing, inspect repo path and `git status --short`.
* Do not stage, commit, delete, move, or rename files unless explicitly asked.
* Do not add dependencies, perform broad refactors, or create generated artifacts unless explicitly asked.

Hard safety rules:

* Do not stage, commit, or intentionally preserve generated artifacts: parquet, dbn, zst, generated csv/json reports, logs, cache files, model pickles, or large data outputs.
* Validation commands may regenerate ignored `data/` and `reports/` artifacts. That is allowed, but they must remain untracked.
* Do not change public contracts unless explicitly asked: CLI args, config keys, column names, file paths, output schemas, report fields, manifests, or test expectations.
* Do not tune model hyperparameters until data integrity, target construction, leakage checks, purge/embargo, and cost modeling are verified.
* Do not change trading/data semantics unless explicitly asked.
* Never store secrets, tokens, API keys, credentials, or private keys in repo files, prompts, memory, or config.

Quant research/model-building policy:

* Prioritize research-process correctness over model complexity.
* Before model selection or tuning, verify data integrity, instrument metadata, target construction, timestamp alignment, leakage checks, walk-forward splits, purge/embargo, and cost/slippage/commission math.
* Treat any improvement as suspect until it survives locked out-of-sample validation with realistic costs and no post-test retuning.
* Prefer simple robust baselines before ML or complex ensembles.
* Record experiment scope, tested variants, validation windows, costs, warnings, and failure modes; do not cherry-pick isolated metrics.
* For intraday futures, account for sessions, rolls, tick/point values, spreads, liquidity regime, partial fills, rejected orders, latency assumptions, and capacity before trusting PnL.
* Add or change risk controls before increasing strategy aggressiveness: max loss, position limits, volatility targeting, kill switch, stale-data guards, and order throttles.

Minimum acceptance checklist before trusting WFA/model results:

* Raw data coverage and missing-bar handling checked.
* Instrument definitions, tick size, point value, contract rolls, and session boundaries verified.
* Target construction, timestamp alignment, feature windows, and NaN handling checked for leakage.
* Walk-forward split boundaries, purge/embargo, and locked out-of-sample windows verified.
* Commission, fees, spread, slippage, delay, capacity, and contract multiplier assumptions enabled or explicitly documented.
* Simple baseline comparison included before accepting ML or complex model improvements.
* Result manifest records config, data scope, validation windows, costs, warnings, and failure modes.
* No post-test retuning or cherry-picked metric is used as acceptance evidence.

Audited-answer policy:

* For material finance, quant research, trading, model-selection, data-integrity, backtest, execution, or external factual claims, answer as if the output will be audited.
* Treat a claim as material when it could affect research conclusions, data/model validity, validation results, trading or execution behavior, risk controls, cost/resource spend, external actions, or public/provider/vendor choices.
* Treat purely mechanical edits, local formatting, typo fixes, narrow status reports, and command-output summaries as non-material unless they make or depend on a material claim.
* Do not apply the full audited-answer structure to routine mechanical repo edits unless the answer makes or relies on material claims in those areas.
* Use the five-part structure only when it materially improves correctness, reproducibility, or decision safety.
* Separate: verified facts with primary-source citations, inferences from those facts, assumptions, what could be wrong or stale, and what should be verified independently before acting.
* Primary sources include exchange/regulator/vendor documentation, repo files, raw data, command/test output, local artifacts, and reproducible validation results.
* Do not treat AI consensus as truth. Cross-model review with GPT, Gemini, Copilot, Claude, or other systems is useful only as adversarial review; final acceptance requires primary evidence or reproducible local checks.
* Do not recommend a product, trade, service, broker, platform, vendor, data provider, or model unless the reasoning survives without affiliate, advertising, ecosystem, or provider incentive.
* If primary evidence is unavailable, stale, or inaccessible, say so explicitly and do not present the claim as verified.

Core quant logic is protected:

* labels/targets
* feature computation
* session normalization
* causal gating
* WFA/train/test splits
* purge/embargo
* cost/slippage/commission math
* position policy
* validation checks
* metrics/reports/manifests
* timestamp alignment, NaN handling, row counts, and output formats

Refactor policy:

* No opportunistic refactors in protected core logic.
* Cleanup is allowed only in already-touched non-core code, only if clearly behavior-preserving, small, and reviewable.
* Prefer boring, explicit, readable code over clever, shorter code.
* If unsure whether a change is behavior-preserving, skip it.

Validation:

* Run the narrowest relevant test/check after edits.
* For data/model/WFA changes, report exact commands, files changed, metrics changed, row-count changes, and warnings.
* After validation, run `git status --short` and confirm generated artifacts are not tracked.
* Final reports after edits must use this compact shape:

```text
Added:
- ...

Removed:
- ...

Modified:
- ...

Validation:
- Command:
- Result:

Remaining risks:
- ...

```

* Include unexpected tracked/generated artifacts only when present. Do not include a full git status summary unless needed to report that risk.

## Codex command sandbox handling

If a command fails before Python starts due to sandbox/spawn/permission handling, retry once with scoped approval.

Do not treat pre-launch sandbox/spawn failures as project failures.

Only report validation failure if Python actually launches and returns a traceback, failed assertion, failed test, or nonzero exit code.
