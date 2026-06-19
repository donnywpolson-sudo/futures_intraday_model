#!/usr/bin/env python
"""Run the meta-audit prompt against the main adversarial audit prompt.

Default usage:
  python scripts/dev/audit_prompts/01_meta_audit_prompt.py
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


DEFAULT_AUDIT_PROMPT = "02_main_adversarial_audit_prompt.md"

META_AUDIT_PROMPT = r"""# Meta-Audit Prompt

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
Allowed commands are static inspection only: rg, git status/log/show/diff, Test-Path, Get-ChildItem, Get-Content, and parse-only snippets that do not write files or create caches/artifacts.
Do not run tests, WFA, rebuilds, report writers, ledger writers, or any command that creates or overwrites caches, data, reports, predictions, logs, generated JSON/CSV, parquet, DBN, zst, or model artifacts.
FIRST: Verify repo identity.
Confirm current directory, git remote, git branch, top-level files, and existence of:
- configs/alpha_tiered.yaml
- configs/models.yaml
- configs/costs.yaml
- configs/market_sessions.yaml
- scripts/
- scripts/phase9_research/
- tests/
- manifests/
- manifests/feature_sets/
- manifests/feature_hypotheses/
- manifests/target_hypotheses/
- scripts/dev/audit_prompts/
- scripts/dev/audit_prompts/README.md
- scripts/dev/audit_prompts/02_main_adversarial_audit_prompt.md
Generated evidence folders are optional audit targets when present, not repo identity requirements:
- data/
- reports/
- reports/pipeline_audit/
- reports/phase8_failure_breakdown/
- reports/model_selection/
- reports/experiments/
If this is not the intraday futures model repo, stop with:
Wrong repo selected - switch repo/folder before audit.
Goal:
Make sure the audit prompt below correctly matches the current project folder, audit templates, artifact layout, feature/target registry state, and current pipeline state.
Be token-efficient. Output only what is wrong and how to fix the prompt.
Tasks:
1. Inspect current repo structure.
2. Inspect configs/alpha_tiered.yaml.
3. Identify actual Tier 1 scope/profile/markets/years.
4. Inspect PIPELINE.md as orientation, then independently verify all claims.
5. Inspect scripts/dev/audit_prompts/README.md and scripts/dev/audit_prompts/02_main_adversarial_audit_prompt.md for existing prompt style and required sections.
6. Identify actual pipeline scripts, Phase 9 research harnesses, data folders, report folders, manifest folders, test files, and config names.
7. Inspect current no-go/audit evidence under reports/pipeline_audit/, reports/phase8_failure_breakdown/, reports/model_selection/, and reports/experiments/ where present.
8. Inspect manifests/feature_sets/, manifests/feature_hypotheses/, and manifests/target_hypotheses/ for FROZEN/CANDIDATE/DISCOVERY_PASS/CONFIRMATION_PASS/REJECTED/RETIRED/QUARANTINED/WFA-allowed state.
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
- target hypothesis CANDIDATE/DISCOVERY_PASS/FROZEN/REJECTED status
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
- configs/alpha_tiered.yaml currently resolves tier_1 -> tier_1_research.
- Current expected Tier 1 research scope is ES, CL, ZN, 6E for years 2023 and 2024.
- manifests/feature_sets/baseline_current.json is the only WFA-allowed frozen feature set and currently has feature_count 122.
- manifests/feature_hypotheses/registry.json and trial_statuses.jsonl are authoritative for feature hypothesis status.
- manifests/target_hypotheses/registry.json and trial_statuses.jsonl are authoritative for target hypothesis status.
- liquidity_cost_state_features_v1 is REJECTED from bounded smoke evidence.
- directional_path_quality_target_v1 is REJECTED from bounded smoke evidence.
- cost-clearability and market-balanced cost-clearability Phase 9 branches are stopped/no-go unless current evidence proves otherwise.
- Rejected/no-go Phase 9 evidence must not be used to justify WFA, Phase 8, full harnesses, threshold tuning, policy tuning, feature/target freezing, or near-neighbor rescue runs.
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
Audit prompt to meta-audit by default:
scripts/dev/audit_prompts/02_main_adversarial_audit_prompt.md
If a prompt was pasted instead, audit the pasted prompt and note that it differs from the repo file.
"""


def resolve_prompt_path(raw_path: str | None, script_path: Path) -> Path:
    if raw_path:
        prompt_path = Path(raw_path)
        if not prompt_path.is_absolute():
            prompt_path = Path.cwd() / prompt_path
        return prompt_path.resolve()
    return script_path.with_name(DEFAULT_AUDIT_PROMPT).resolve()


def repo_root_from_script(script_path: Path) -> Path:
    return script_path.parents[3]


def build_prompt(prompt_path: Path) -> str:
    return (
        META_AUDIT_PROMPT.rstrip()
        + "\n\n# Audit Prompt Under Review\n"
        + f"Audit this file now: {prompt_path}\n"
        + "Do not require a pasted prompt. Inspect the file directly.\n"
    )


def run_codex_exec(
    *,
    codex_bin: str,
    model: str | None,
    prompt: str,
    repo_root: Path,
) -> int:
    command = [
        codex_bin,
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "never",
        "--cd",
        str(repo_root),
    ]
    if model:
        command.extend(["--model", model])
    command.append("-")

    try:
        return subprocess.run(command, input=prompt, text=True, check=False).returncode
    except FileNotFoundError:
        sys.stderr.write(
            f"Codex CLI not found: {codex_bin}\n"
            "Install/sign in to Codex CLI or pass --codex-bin.\n"
        )
        return 127
    except PermissionError as exc:
        sys.stderr.write(f"Unable to launch Codex CLI: {exc}\n")
        return 126


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the read-only meta-audit against the main adversarial audit "
            "prompt through codex exec."
        )
    )
    parser.add_argument(
        "--prompt",
        help=(
            "Optional audit prompt path to embed. Defaults to "
            f"{DEFAULT_AUDIT_PROMPT} next to this script."
        ),
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex CLI executable to run. Defaults to codex.",
    )
    parser.add_argument(
        "--model",
        help="Optional Codex model override.",
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Print the generated meta-audit prompt without running Codex.",
    )
    args = parser.parse_args(argv)

    script_path = Path(__file__).resolve()
    repo_root = repo_root_from_script(script_path)
    prompt_path = resolve_prompt_path(args.prompt, script_path)

    if not prompt_path.exists():
        sys.stderr.write(f"Audit prompt not found: {prompt_path}\n")
        return 2

    prompt = build_prompt(prompt_path)
    if args.print_prompt:
        sys.stdout.write(prompt)
        return 0

    return run_codex_exec(
        codex_bin=args.codex_bin,
        model=args.model,
        prompt=prompt,
        repo_root=repo_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
