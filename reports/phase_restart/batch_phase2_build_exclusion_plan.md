# Batch Phase 2 Build/Exclusion Plan

- Updated at UTC: 2026-06-22T23:36:26Z
- Scope: bounded report-only build/exclusion plan refreshed after master data health matrix and KE exclusion policy.
- Decision state: PHASE2_BUILD_EXCLUSION_PLAN_REFRESHED_REPORT_ONLY

## Summary

- Total Phase 2 decision rows: 66.
- Accepted rows made eligible for future bounded Phase 2 build approval: 57.
- Deferred rows excluded from future bounded Phase 2 build batches: 9.
- Accepted rows with pre-build raw evidence prerequisites: 17.
- Phase 2 build commands run in this step: 0.
- Cleanup commands run in this step: 0.

This refreshed plan does not run Phase 2. It removes `KE:2015` from the accepted set to match the latest KE exclusion policy. Rows in the accepted set can only run later with explicit Phase 2 build approval, and rows listed as pre-build blocked need raw evidence work first.

## Deferred Exclusions

| Row | Exclusion reason |
| --- | --- |
| KE:2013 | Latest KE policy excludes KE 2013-2015 unless explicitly policy-excepted. |
| KE:2014 | Latest KE policy excludes KE 2013-2015 unless explicitly policy-excepted. |
| ZL:2012 | Explicitly deferred because canonical status source is absent. |
| ZL:2013 | Explicitly deferred because canonical status source is absent. |
| ZM:2011 | Explicitly deferred because canonical status source is absent. |
| ZM:2012 | Explicitly deferred because canonical status source is absent. |
| ZM:2013 | Explicitly deferred because canonical status source is absent. |
| ZM:2014 | Explicitly deferred because canonical status source is absent. |
| KE:2015 | Latest KE policy excludes KE 2013-2015 unless explicitly policy-excepted. |

## Accepted Batches

Run later only with explicit Phase 2 build approval. Any row listed in the pre-build blocked column needs raw evidence work first.

| Batch | Accepted rows | Count | Pre-build blocked rows |
| --- | --- | ---: | --- |
| KE | KE:2016, KE:2017, KE:2018, KE:2019, KE:2020, KE:2021, KE:2022, KE:2023, KE:2024, KE:2025, KE:2026 | 11 | KE:2025, KE:2026 |
| SR1 | SR1:2018, SR1:2019, SR1:2020, SR1:2021, SR1:2022, SR1:2023, SR1:2024, SR1:2025, SR1:2026 | 9 | SR1:2018, SR1:2019, SR1:2020, SR1:2021, SR1:2022, SR1:2023, SR1:2024, SR1:2025, SR1:2026 |
| TN | TN:2016, TN:2017, TN:2018, TN:2019, TN:2020, TN:2021, TN:2022, TN:2023, TN:2024, TN:2025, TN:2026 | 11 | TN:2025, TN:2026 |
| ZL | ZL:2011, ZL:2014, ZL:2015, ZL:2016, ZL:2017, ZL:2018, ZL:2019, ZL:2020, ZL:2021, ZL:2022, ZL:2023, ZL:2024, ZL:2025, ZL:2026 | 14 | ZL:2025, ZL:2026 |
| ZM | ZM:2015, ZM:2016, ZM:2017, ZM:2018, ZM:2019, ZM:2020, ZM:2021, ZM:2022, ZM:2023, ZM:2024, ZM:2025, ZM:2026 | 12 | ZM:2025, ZM:2026 |

## Later Command Pattern

For a later explicitly approved one-row Phase 2 build, use this pattern and replace `<slug>` with lowercase `<market>_<year>`:

```powershell
python -m scripts.phase2_causal_base.build_causal_base_data --profile phase2_repair --profile-config reports\phase_restart\<slug>_phase2_causal_repair.yaml --raw-root data\raw --output-root data\causally_gated_normalized --reports-root reports\phase_restart --raw-alignment-report reports\phase_restart\<slug>_phase2_raw_alignment.json
```

Stop conditions for any future build approval:

- `git status --short -- data` is non-empty before the run.
- The selected row is not in the accepted executable set.
- The selected row is deferred/excluded.
- The selected row appears in `pre_build_blocked_rows` and lacks later accepted raw evidence or explicit waiver.
- More than the approved row or market batch would run.
- Phase 2 validation fails.
- Cleanup would be required.

## Validation Required After Future Build

```powershell
python scripts\audit_data_manifest.py
git status --short -- data
```

Expected future build outputs are canonical causal parquet files under `data\causally_gated_normalized`. They are generated data artifacts and must remain untracked unless a separate data-artifact policy changes.

## Safety

- No Phase 2 build was run.
- No cleanup was run.
- No phase 3+ command was run.
- No move, merge, quarantine, delete, rebuild, or redownload occurred.
- DBN source files were not modified.
- No source/status acquisition or reconstruction was run.
- No policy threshold was changed.
- No canonical causal parquet was written in this step.
- No data artifact was staged.
- Cleanup remains disabled.
