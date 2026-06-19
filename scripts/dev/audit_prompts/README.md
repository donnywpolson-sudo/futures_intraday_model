# Codex Audit Prompts - Intraday Futures Model

Reusable prompts for auditing this repo.

Use in this order:

1. `01_meta_audit_prompt.md` - verifies the main audit prompt still matches the current repo.
2. `02_main_adversarial_audit_prompt.md` - read-only adversarial project audit.
3. `03_fix_prompt_after_confirmed_findings.md` - write-capable fix prompt for confirmed FATAL/HIGH findings only.

Do not skip the meta-audit when repo structure, config scope, pipeline scripts, or report paths have changed.
