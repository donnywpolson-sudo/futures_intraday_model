# Remove Compatibility Wrappers One by One

Use this prompt in Codex when you want to remove compatibility wrappers across
the repo without breaking canonical phase entry points.

## Goal

Remove only proven compatibility wrappers, one wrapper per pass. After each
removal, update all references to the canonical module, run targeted validation,
and stop with a concise report before removing another wrapper.

## Hard Rules

- Do not touch `data/`, `reports/`, generated artifacts, model outputs, or caches.
- Do not stage, commit, download data, or regenerate Phase 2+ artifacts.
- Do not remove real shared utilities, CLIs, or modules that contain business
  logic.
- Do not remove more than one wrapper in a single pass.
- Do not change CLI args, report schemas, config keys, column names, or output
  paths unless the wrapper removal explicitly requires updating an import/module
  path.
- Preserve behavior through a canonical replacement command/import.
- Do not remove wrappers documented in `PIPELINE.md`, tests, phase tables, or
  docs as canonical/public entrypoints unless this same one-pass removal
  explicitly migrates those references and validates the replacement.
- If a wrapper has any logic beyond delegating imports and `main`, stop and
  report it as not safe for automated wrapper removal.

## Wrapper Definition

A file is safe to treat as a compatibility wrapper only if all are true:

- It imports `main`, `*`, or selected public names from a canonical module.
- Its own executable behavior is limited to `raise SystemExit(main())`.
- It contains no data/model/trading logic, no schema definitions, no feature
  logic, no validation rules, and no material helper functions.
- All repo references can be updated to the canonical module path.
- The canonical module works directly with `python -m ... --help` or equivalent
  smoke check.

## One-Pass Procedure

1. Inspect current state:

   ```powershell
   git status --short --untracked-files=all
   Get-ChildItem -Path scripts -Recurse -Filter *.py | Select-Object FullName
   ```

2. Find wrapper candidates:

   ```powershell
   rg -n "Compatibility wrapper|from scripts\\..* import \\*|from scripts\\..* import main|raise SystemExit\\(main\\(\\)\\)" scripts tests PIPELINE.md README.md docs
   ```

3. Pick exactly one candidate. Prefer the smallest, clearest wrapper with the
   fewest references. Record:

   - wrapper path
   - canonical module path
   - why it qualifies as a wrapper
   - every reference that must change

4. Search for public-entrypoint references before deleting anything:

   ```powershell
   rg -n "<old.module.path>|python -m <old.module.path>|<old/path.py>" PIPELINE.md README.md docs scripts tests
   ```

   Classify the candidate as one of:

   - `safe wrapper`: pure wrapper with no public canonical-entrypoint role, or
     all public references will be migrated in this pass.
   - `protected public alias`: pure wrapper that is still documented or tested
     as a public/canonical entrypoint, and this pass does not migrate those
     references.
   - `not a wrapper`: contains logic, validation, schemas, helpers, feature
     code, data/model/trading behavior, or other material behavior.

   Stop without editing if the classification is `protected public alias` or
   `not a wrapper`.

5. Update all references from the wrapper module to the canonical module:

   ```powershell
   rg -n "<old.module.path>|python -m <old.module.path>|<old/path.py>" PIPELINE.md README.md docs scripts tests
   ```

6. Delete only that wrapper file.

7. Validate the canonical path:

   ```powershell
   python -m <canonical.module.path> --help
   ```

   If the canonical module is not a CLI, run the narrowest import smoke check:

   ```powershell
   python -c "import <canonical.module.path>; print('ok')"
   ```

8. Run targeted tests that cover the moved import/CLI. Use `python -m pytest`
   and disable cache writes:

   ```powershell
   python -m pytest -p no:cacheprovider <targeted_test_path>
   ```

9. Prove the old path is gone:

   ```powershell
   rg -n "<old.module.path>|python -m <old.module.path>|<old/path.py>" PIPELINE.md README.md docs scripts tests
   ```

   This command should return no matches unless a deliberate changelog note is
   being kept.

10. Run final hygiene:

   ```powershell
   git diff --check -- PIPELINE.md README.md docs scripts tests
   git status --short --untracked-files=all
   ```

11. Stop. Report files changed, wrapper removed, canonical replacement,
    commands run, validation result, and any remaining wrapper candidates.

## Current Known Root-Level Files

Do not automatically delete these root `scripts/*.py` files:

- `__init__.py`: package marker.
- `build_metric_visualizations.py`: referenced by docs/tests.
- `check_git_hygiene.py`: referenced by `README.md`.
- `databento_auth.py`: shared live Databento auth helper.
- `export_live_shadow_bundle.py`: live shadow export tool with tests.
- `live_shadow_runner.py`: live shadow runner used by export/tests.
- `live_smoke_databento.py`: covered by live Databento tests.
- `phase1_raw_contract.py`: shared Phase 1 schema/constants.
- `profile_scope.py`: shared profile-scope helper.
- `write_project_inventory.py`: inventory utility; do not remove without a
  dedicated reference and usage audit.

Known likely wrapper candidates must still go through the one-pass proof gate:

- `scripts/run_wfa.py` -> `scripts.phase6_wfa.run_wfa`

## Report Format

Use this final report shape after each pass:

```text
Removed wrapper:
- <old path>

Classification:
- safe wrapper | protected public alias | not a wrapper

Canonical replacement:
- <module/path>

References updated:
- <short list>

Public references migrated:
- yes/no

Validation:
- <command>: PASS/FAIL

Remaining known wrapper candidates:
- <list or none>

Git status:
<git status --short --untracked-files=all output>
```
