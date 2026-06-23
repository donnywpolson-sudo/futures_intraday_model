You are auditing this repo's data pipeline and data layout.

Repo root: `C:\Users\donny\Desktop\futures_intraday_model`

Goal: determine the actual canonical pipeline, path usage, generated artifacts, cleanup readiness, and next safe actions from repo evidence, not assumptions.

Do not execute destructive or expensive actions: no delete, move, overwrite, data regeneration, full rebuilds, source/DBN mutation, generated artifact staging, or commits.

Start read-only. Prefer code, CLI defaults, configs, manifests, reports, tests, file metadata, counts, schemas, and small samples. Avoid expensive full parquet scans unless necessary. Produce a cleanup plan only.

Expected pipeline to verify from code:

```text
phase1A_download      -> data\dbn
phase1B_convert       -> data\raw
phase1C_validate      -> reports only unless code proves otherwise
phase2_causal_base    -> data\causally_gated_normalized
phase3_labels         -> data\labeled
phase4_features       -> data\feature_matrices
predictions/modeling  -> data\predictions only if scripts/configs write it
```

Important corrections to enforce:

- Do not split normalize and causal gate unless separate scripts prove it.
- Treat labels and feature matrices as downstream of phase2 unless code proves otherwise.
- Treat `data\predictions` as required only if current modeling/prediction code writes it.
- Do not mark any folder safe to delete solely from its name or existence.

Canonical folders to check:

```text
data\dbn
data\raw
data\causally_gated_normalized
data\labeled
data\feature_matrices
data\predictions
```

Suspicious folders/patterns to classify:

```text
_data_reorg_quarantine20260621T222448Z
data\**\_diagnostic*
data\**\_repair*
data\**\_smoke*
data\raw\_full_rebuild_20260621
data\dbn\ohlcv_1m_parent
data\dbn\statistics_parent\statistics
data\dbn\status_parent\status
```

Audit tasks:

1. Record branch, `git status --short`, and ignored/untracked data/report artifact summary.
2. Inventory `data`: immediate children, underscore-prefixed folders, unexpected nested folders under canonical folders, and whether `data\predictions` exists.
3. Search scripts, configs, tests, reports, and docs for path/pattern references:

   ```text
   _smoke _repair _diagnostic _quarantine _full_rebuild
   ohlcv_1m_parent statistics_parent status_parent
   causally_gated_normalized labeled feature_matrices predictions
   data\dbn data\raw
   ```

   Report relevant file, line, risk, and fix.

4. Map phases from actual code for:

   ```text
   scripts\phase1A_download
   scripts\phase1B_convert
   scripts\phase1C_validate
   scripts\phase2_causal_base
   scripts\phase3_labels
   scripts\phase4_features
   ```

   For each existing phase, identify script/module, CLI/default inputs and outputs, configs, reports/manifests, tests, canonical folder reads/writes, and suspicious references. Report missing phase folders/scripts explicitly.

5. Validate pipeline completeness:

   ```text
   data\dbn -> data\raw -> phase1C reports -> data\causally_gated_normalized -> data\labeled -> data\feature_matrices -> data\predictions if required
   ```

   Check missing folders, missing reports/manifests, inconsistent market/year coverage, phase outputs missing for available inputs, noncanonical script paths, stale temp references, and whether predictions are current-scope or future-facing.

6. Summarize cheap data health for each canonical category: files, major schemas/subfolders, market/year coverage if inferable cheaply, producer/consumer role, missing/unexpected items, and whether it is canonical.

7. Classify each suspicious folder as `safe_candidate_delete`, `keep_until_verified`, `active_dependency`, or `unknown`. Evidence required: file count, total size, major extensions, cheap market/year coverage, code/config/test references, equivalent canonical data if any, unique files if inferable cheaply, and recommendation.

8. Identify blockers:

   - Severe: pipeline cannot run correctly, required canonical data missing, active scripts depend on suspicious folders, validation evidence missing for claimed production data, or cleanup is unsafe.
   - Medium: usable with caveats, incomplete verification, likely stale but unproven duplicate folder, missing optional report/manifest, or predictions missing when modeling is not yet required.
   - Low: cosmetic cleanup, stale docs/comments, empty folders, minor naming cleanup.

9. Write one report: `reports\data_layout_audit_YYYYMMDD.md`.

Report format:

```markdown
# Data Layout Audit

## Executive Summary
- Canonical folders healthy: yes/no/partial
- Actual pipeline order verified: yes/no/partial
- Suspicious folders found: N
- Active references to suspicious folders: N
- Safe cleanup candidates: N
- Medium-risk cleanup candidates: N
- Severe blockers: N
- Proceed status: yes / yes with medium blockers / no

## Actual Pipeline Flow
| Order | Phase | Script/Module | Role | Inputs | Outputs | Reports/Manifests | Tests | Status | Evidence |

## Canonical Data Folders
| Folder | Exists | Role | Producer Phase | Consumer Phase | Current Status | Evidence |

## Suspicious Folder Classification
| Folder | Classification | File Count | Size | Referenced By Code | Equivalent Canonical Data Exists | Evidence | Recommendation |

## Hardcoded Temporary References
| Reference | File | Line | Risk | Fix |

## Coverage Summary
| Data Category | Markets | Years | Files/Rows if cheap | Missing/Unexpected | Status |

## Pipeline Completeness
- DBN source complete:
- Raw conversion complete:
- Raw vs DBN validation complete:
- Causally gated normalized base complete:
- Labels complete:
- Feature matrices complete:
- Predictions required now:
- Predictions complete:
- Overall status:

## Blockers
### Severe
- ...

### Medium
- ...

### Low
- ...

Proceed status: yes / yes with medium blockers / no

## Next
1. Action -> expected result -> stop condition
2. Action -> expected result -> stop condition
3. Action -> expected result -> stop condition

## Metrics
Elapsed time: ...
Files inspected: ...
Suspicious folders classified: ...
Hardcoded suspicious references found: ...
Canonical folders checked: ...
Pipeline phases inspected: ...
Report: reports\data_layout_audit_YYYYMMDD.md
```

After writing the report, print only:

```text
Blockers
Severe:
- ...
Medium:
- ...
Low:
- ...
Proceed status: yes / yes with medium blockers / no

Next
1. ...
2. ...
3. ...

Metrics
Elapsed time: ...
Files inspected: ...
Suspicious folders classified: ...
Hardcoded suspicious references found: ...
Canonical folders checked: ...
Pipeline phases inspected: ...
Report: reports\data_layout_audit_YYYYMMDD.md
```
