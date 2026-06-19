# Meta-Audit Prompt

Use in Codex Plan Mode / read-only.

MODE: PLAN / READ-ONLY META-AUDIT ONLY.
You are auditing the audit prompt below against the actual current repo.
Do not edit files.
Do not commit.
Do not stage.
Do not regenerate artifacts.
Do not overwrite data/reports.
Do not execute the corrected audit prompt; only return the corrected prompt.
Do not run WFA, Phase 8, prediction-combine scripts, feature/label/causal rebuilds, full pytest, or experiment ledger writers.
Do not create reports, data, predictions, model artifacts, logs, generated JSON/CSV, or other artifacts.
You may inspect files, configs, reports, manifests, tests, and run safe read-only commands.
FIRST: Verify repo identity.
Confirm current directory, git remote, git branch, top-level files, and existence of:
- configs/alpha_tiered.yaml
- configs/models.yaml
- configs/costs.yaml
- configs/market_sessions.yaml
- scripts/
- scripts/phase9_research/
- tests/
- data/
- reports/
- reports/pipeline_audit/
- reports/phase8_failure_breakdown/
- reports/model_selection/
- reports/experiments/
- manifests/
- manifests/feature_sets/
- manifests/feature_hypotheses/
- docs/audit_prompts/
If this is not the intraday futures model repo, stop with:
Wrong repo selected - switch repo/folder before audit.
Goal:
Make sure the audit prompt below correctly matches the current project folder, audit templates, artifact layout, feature registry state, and current pipeline state.
Be token-efficient. Output only what is wrong and how to fix the prompt.
Tasks:
1. Inspect current repo structure.
2. Inspect configs/alpha_tiered.yaml.
3. Identify actual Tier 1 scope/profile/markets/years.
4. Inspect PIPELINE.md as orientation, then independently verify all claims.
5. Inspect docs/audit_prompts/ for existing prompt style and required sections.
6. Identify actual pipeline scripts, Phase 9 research harnesses, data folders, report folders, manifest folders, test files, and config names.
7. Inspect current no-go/audit evidence under reports/pipeline_audit/, reports/phase8_failure_breakdown/, reports/model_selection/, and reports/experiments/ where present.
8. Inspect manifests/feature_sets/ and manifests/feature_hypotheses/ for FROZEN/CANDIDATE/REJECTED/WFA-allowed state.
9. Compare audit prompt wording to repo reality.
10. Find outdated, wrong, missing, misleading, unsafe, or over-assumed wording.
11. Rewrite only incorrect or missing parts of the audit prompt.
12. Do not run the full audit yet.
Check mismatches in:
- Tier/profile names
- market list assumptions
- year/date range assumptions
- script paths
- data folder names
- report folder names
- manifest folder/file names
- feature pipeline status
- feature-set registry status
- feature hypothesis CANDIDATE/DISCOVERY_PASS/FROZEN/REJECTED status
- WFA-allowed feature status
- Phase 9 no-go/rejected branch state
- WFA/model pipeline status
- metrics/gate file names
- label names/column names
- causal/session column names
- test file names
- commands
- PowerShell compatibility
- write permissions and generated-artifact safety
- latest evidence/run selection logic
- anti-overfit/no-tuning guards
- stale smoke/default/partial/Tier 3 evidence handling
- assumptions that artifacts exist
- stale wording from prior repo states
- root planning docs treated as pipeline truth
- _archive/ or cleanup folders being mistaken for active pipeline inputs
Current state to verify, not assume:
- manifests/feature_sets/baseline_current.json is the only WFA-allowed frozen feature set.
- manifests/feature_hypotheses/registry.json and trial_statuses.jsonl are authoritative for hypothesis status.
- liquidity_cost_state_features_v1 is REJECTED from bounded smoke evidence.
- cost-clearability and market-balanced cost-clearability Phase 9 branches are stopped/no-go unless current evidence proves otherwise.
- Rejected/no-go Phase 9 evidence must not be used to justify WFA, Phase 8, threshold tuning, policy tuning, feature freezing, or near-neighbor rescue runs.
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
# Safety Fixes
List wording needed to prevent writes, artifact regeneration, unsafe tests, WFA/Phase 8 reruns, or tuning rejected evidence.
# Corrected Audit Prompt
Return a revised token-efficient audit prompt that matches this repo exactly.
Here is the audit prompt to meta-audit:
<PASTE MAIN AUDIT PROMPT HERE>
