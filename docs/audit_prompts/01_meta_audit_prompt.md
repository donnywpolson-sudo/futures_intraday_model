# Meta-Audit Prompt

Use in Codex Plan Mode / read-only.

```text
MODE: PLAN / READ-ONLY META-AUDIT ONLY.
You are auditing the audit prompt below against the actual current repo.
Do not edit files.
Do not commit.
Do not regenerate artifacts.
Do not overwrite data/reports.
Do not execute the corrected audit prompt; only return the corrected prompt.
You may inspect files, configs, reports, tests, and run safe read-only commands.
FIRST: Verify repo identity.
Confirm current directory, git remote, git branch, top-level files, and existence of:
- configs/alpha_tiered.yaml
- configs/models.yaml
- configs/costs.yaml
- configs/market_sessions.yaml
- scripts/
- tests/
- data/
- reports/
If this is not the intraday futures model repo, stop with:
Wrong repo selected - switch repo/folder before audit.
Goal:
Make sure the audit prompt below correctly matches the current project folder.
Be token-efficient. Output only what is wrong and how to fix the prompt.
Tasks:
1. Inspect current repo structure.
2. Inspect configs/alpha_tiered.yaml.
3. Identify actual Tier 1 scope/profile/markets/years.
4. Identify actual pipeline scripts, data folders, report folders, test files, and config names.
5. Compare audit prompt wording to repo reality.
6. Find outdated, wrong, missing, misleading, or over-assumed wording.
7. Rewrite only incorrect parts of the audit prompt.
8. Do not run the full audit yet.
Check mismatches in:
- Tier/profile names
- market list assumptions
- year/date range assumptions
- script paths
- data folder names
- report folder names
- feature pipeline status
- WFA/model pipeline status
- metrics/gate file names
- label names/column names
- causal/session column names
- test file names
- commands
- PowerShell compatibility
- assumptions that artifacts exist
- stale wording from prior repo states
Output format only:
# Verdict
Prompt matches repo: Yes/No/Mostly
Biggest mismatch:
# Required Prompt Fixes
## P<n>: <short title>
Wrong wording:
Repo evidence:
Replace with:
# Removed Assumptions
List unsupported prompt claims to delete.
# Missing Audit Targets
List repo components the prompt should audit but misses.
# Corrected Audit Prompt
Return a revised token-efficient audit prompt that matches this repo exactly.
Here is the audit prompt to meta-audit:
<PASTE MAIN AUDIT PROMPT HERE>
```
