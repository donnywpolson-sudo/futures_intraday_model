# Status Manifest Policy Decision

Generated at UTC: 2026-06-22T10:36:00Z

## Smoke Commit Review

- Reviewed commit: `ead39bc Add bounded phase smoke validation`.
- Commit contents: `CODEX_HANDOFF.md` and `reports/phase_restart/*` report evidence only.
- Smoke evidence status: accepted.
- Phase evidence: `reports/phase_restart/phase_restart_summary.md` records PASS for Phase 1A dry-run, Phase 1B existing-output check, Phase 1C expected-only alignment, and Phase 2 readiness-only.
- Targeted tests recorded in smoke evidence: `tests/validation/test_audit_raw_dbn_alignment.py` PASS, 25 passed; `tests/phase2_causal_base/test_build_causal_base_data.py` PASS, 65 passed.
- Production behavior review: `ead39bc` did not modify scripts/tests. Current smoke-validation implementation remains default-off for `--expected-only` and `--readiness-only`; production defaults are not changed by this commit.
- Safety review: no phase 3+ behavior, generated data artifact, DBN source file modification, cleanup, move, quarantine, merge, delete, redownload, or rebuild is present in `ead39bc`.

## Current Status Requirement

- `configs/data_manifest.yaml` includes DBN schema `status` at `data/dbn/status`.
- `configs/data_manifest.yaml` expects default DBN coverage from `default_start_year: 2010` through `end_year: 2026`, with market start overrides.
- `coverage_policy.missing_pairs.allowed_missing_pairs` is currently empty, so missing `status` pairs are classified as unexpected missing pairs.
- `artifact_policy.cleanup_allowed` is `false`; cleanup remains disabled.

## Evidence Summary

- `reports/data_manifest/manifest_coverage_summary.md`: `data/dbn/status` has 68 unexpected missing pairs, 3 allowed extras, and 3 known policy-deferred duplicates.
- `reports/data_manifest/manifest_policy_fix_proposal.csv`: 68 rows are `MANIFEST_FIX_RECOMMENDED`.
- `reports/data_lineage/pipeline_phase_io_map.md`: Phase 1B consumes `data/dbn/status` as optional enrichment; Phase 1C validates `ohlcv_1m` and `definition`; Phase 2 consumes `data/raw`.
- `reports/data_lineage/canonical_path_summary.md`: `data/dbn/status` inventory is 462/527 expected pairs with 68 missing pairs.
- `reports/data_manifest/manifest_cleanup_approval_packet.md`: current approval blockers are 76 repair approvals, 68 manifest-policy rows, and 12 duplicate rows.

## Affected Status Pairs

- Schema/path: `data/dbn/status`.
- Count: 68 missing status pairs.
- Affected markets: `6A`, `6B`, `6C`, `6E`, `6J`, `6M`, `ES`, `GC`, `HE`, `HG`, `HO`, `KE`, `LE`, `NQ`, `RB`, `SI`, `UB`, `YM`, `ZB`, `ZC`, `ZF`, `ZL`, `ZM`, `ZN`, `ZS`, `ZT`, `ZW`.
- Affected years: 2010 through 2014, depending on market.

| Market | Count | Years |
|---|---:|---|
| 6A | 1 | 2014 |
| 6B | 1 | 2014 |
| 6C | 3 | 2010, 2011, 2014 |
| 6E | 3 | 2012, 2013, 2014 |
| 6J | 2 | 2010, 2014 |
| 6M | 2 | 2013, 2014 |
| ES | 1 | 2014 |
| GC | 2 | 2010, 2014 |
| HE | 1 | 2013 |
| HG | 2 | 2011, 2014 |
| HO | 4 | 2010, 2011, 2012, 2013 |
| KE | 2 | 2013, 2014 |
| LE | 4 | 2010, 2011, 2012, 2013 |
| NQ | 2 | 2012, 2014 |
| RB | 5 | 2010, 2011, 2012, 2013, 2014 |
| SI | 1 | 2014 |
| UB | 3 | 2010, 2011, 2012 |
| YM | 4 | 2011, 2012, 2013, 2014 |
| ZB | 3 | 2010, 2011, 2012 |
| ZC | 2 | 2010, 2014 |
| ZF | 3 | 2010, 2011, 2012 |
| ZL | 2 | 2012, 2013 |
| ZM | 4 | 2011, 2012, 2013, 2014 |
| ZN | 3 | 2010, 2011, 2012 |
| ZS | 2 | 2011, 2013 |
| ZT | 5 | 2010, 2011, 2012, 2013, 2014 |
| ZW | 1 | 2013 |

Full pair list:

```text
6A:2014
6B:2014
6C:2010
6C:2011
6C:2014
6E:2012
6E:2013
6E:2014
6J:2010
6J:2014
6M:2013
6M:2014
ES:2014
GC:2010
GC:2014
HE:2013
HG:2011
HG:2014
HO:2010
HO:2011
HO:2012
HO:2013
KE:2013
KE:2014
LE:2010
LE:2011
LE:2012
LE:2013
NQ:2012
NQ:2014
RB:2010
RB:2011
RB:2012
RB:2013
RB:2014
SI:2014
UB:2010
UB:2011
UB:2012
YM:2011
YM:2012
YM:2013
YM:2014
ZB:2010
ZB:2011
ZB:2012
ZC:2010
ZC:2014
ZF:2010
ZF:2011
ZF:2012
ZL:2012
ZL:2013
ZM:2011
ZM:2012
ZM:2013
ZM:2014
ZN:2010
ZN:2011
ZN:2012
ZS:2011
ZS:2013
ZT:2010
ZT:2011
ZT:2012
ZT:2013
ZT:2014
ZW:2013
```

## Recommendation

Recommend approval of an explicit deferred/optional policy for the 68 missing `data/dbn/status` pairs before any cleanup evaluation.

The smallest later config-only implementation, if the user approves, is to add these 68 pairs under `coverage_policy.missing_pairs.allowed_missing_pairs.status` with an optional-enrichment rationale. This narrows the decision to the observed missing status pairs and preserves the `status` schema, observed status files, status duplicate policy, and cleanup-disabled artifact policy.

Do not remove the `status` schema wholesale. Do not repair or redownload status data as part of this decision point.

## Approve Option

User decision needed: approve explicit deferral of the 68 missing `data/dbn/status` pairs.

Expected effect if approved and later implemented in `configs/data_manifest.yaml`:

- `MANIFEST_FIX_RECOMMENDED` status-policy rows: 68 -> 0.
- Overall approval-packet blockers: 156 -> 88 before any separate repair or duplicate decisions.
- Cleanup remains blocked by 76 repair approvals and 12 duplicate/user decision rows unless separately resolved.
- No data generation, redownload, DBN source modification, cleanup, move, quarantine, merge, or delete is required for the policy edit.

Stop condition after later approved config edit:

- `python scripts\audit_data_manifest.py` no longer reports these 68 `data/dbn/status` pairs as unexpected missing.
- `git status --short -- data` remains empty.
- `artifact_policy.cleanup_allowed` remains `false`.

## Reject Option

User decision needed: reject status deferral and keep full `data/dbn/status` coverage required.

Expected effect if rejected:

- The 68 status rows remain unresolved manifest-policy blockers.
- A later bounded status repair/redownload plan is required before cleanup can be evaluated.
- Current total approval-packet blockers remain 156 before any separate repair or duplicate decisions.
- Risk: status remains required even though lineage evidence treats it as optional Phase 1B enrichment and not required for the bounded Phase 1A/1B/1C/2 smoke path.

Stop condition after rejection:

- User approves a bounded status repair/download plan for exactly the missing pairs, or explicitly accepts that cleanup evaluation remains blocked.
- No status DBN redownload or source modification occurs without that separate approval.

## No-Action Confirmation

- `configs/data_manifest.yaml` was not edited.
- No cleanup, move, quarantine, merge, delete, redownload, rebuild, conversion, data generation, phase 3+ command, or expensive job was run.
- No DBN source files were modified.
- No generated data artifacts were staged.
- Cleanup remains disabled and blocked.
