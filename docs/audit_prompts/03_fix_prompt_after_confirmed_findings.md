# Fix Prompt After Confirmed FATAL/HIGH Findings

Use in regular/write-capable Codex mode, not Plan Mode.

```text
MODE: IMPLEMENT CONFIRMED FATAL/HIGH FIXES ONLY.
You are fixing confirmed audit findings in the current intraday futures repo.
Do not run in read-only/Plan Mode.
Do not refactor unrelated code.
Do not change modeling assumptions.
Do not regenerate large artifacts.
Do not overwrite data/reports/predictions.
Do not commit.
Do not touch generated artifacts except temporary test fixtures.
Add tests for every guard you implement.
Run only targeted tests.
FIRST: Verify repo identity.
Confirm this repo has:
- configs/alpha_tiered.yaml
- configs/models.yaml
- configs/costs.yaml
- configs/market_sessions.yaml
- scripts/phase2_causal_base/build_causal_base_data.py
- scripts/phase3_labels/build_labels.py
- scripts/phase4_features/build_baseline_features.py
- scripts/phase5_wfa/build_wfa_splits.py
- scripts/phase7_wfa/run_wfa.py
- scripts/phase8_model_selection/evaluate_predictions.py
- tests/
If this is not the intraday futures model repo, stop and say:
Wrong repo selected - switch repo/folder before fixing.
Confirmed findings to fix:
<PASTE ONLY CONFIRMED FATAL/HIGH FINDINGS HERE>
Rules:
- Fix only confirmed bugs.
- Add tests for each fix.
- Keep generated artifacts out of git.
- Do not rebuild full Tier 1 artifacts.
- If a rebuild is needed, list the command only.
Output format:
# Files Changed
- path: reason
# Guards/Fixes Added
- item:
# Tests Added
- test path/name:
- what it proves:
# Tests Run
- command:
- result:
# Not Done
List anything intentionally not fixed.
# Manual Commands To Run Later, Not Now
List rebuild commands only if guards/tests pass.
# Final Verdict
Ready to rebuild Tier 1 artifacts: Yes/No
Why:
Next exact action:
```
