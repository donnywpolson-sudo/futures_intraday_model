# Remaining Cleanup Blockers

Generated at UTC: 2026-06-22T10:44:37Z

## Summary

- Status manifest-policy rows are resolved by commit `c2f9998 Apply status manifest policy`.
- `reports/data_manifest/manifest_coverage_check.csv` now classifies the 68 missing `data/dbn/status` pairs as `expected_missing`, not `unexpected_missing`.
- Cleanup remains disabled in `configs/data_manifest.yaml`.
- Cleanup gate remains blocked by 76 repair approval rows and 12 duplicate policy rows.
- No cleanup, repair, merge, quarantine, data move, data delete, redownload, rebuild, conversion, phase 3+ command, or DBN source modification was run.

## Remaining Repair Approval Rows

Recommended decision choices:

- `APPROVE_BOUNDED_REPAIR_LATER`: user approves a later bounded repair goal for the listed market/year outputs.
- `DEFER_REPAIR_EXPLICITLY`: user accepts that cleanup evaluation remains blocked or the manifest policy must be changed later.

| Group | Count | Phase/script | Schema | Markets/years | Canonical output path | Boundedness |
|---|---:|---|---|---|---|---|
| Raw parquet repair | 10 | `scripts/phase1B_convert/convert_databento_raw.py` | `phase1b_raw_parquet` | KE, SR1, TN, ZL, ZM for 2025-2026 | `data/raw/{market}/{year}.parquet` | bounded per market/year using existing canonical DBN `ohlcv_1m` and `definition` inputs if present; no redownload without separate approval |
| Causal parquet repair | 66 | `scripts/phase2_causal_base/build_causal_base_data.py` | `phase2_causal_base_parquet` | KE 2013-2026; SR1 2018-2026; TN 2016-2026; ZL 2011-2026; ZM 2011-2026 | `data/causally_gated_normalized/{market}/{year}.parquet` | bounded per market/year after canonical raw parquet exists; 2025-2026 causal rows for KE/SR1/TN/ZL/ZM depend on the raw repair group |

Repair detail by market:

| Canonical path | Market | Count | Years |
|---|---|---:|---|
| `data/raw/{market}/{year}.parquet` | KE | 2 | 2025, 2026 |
| `data/raw/{market}/{year}.parquet` | SR1 | 2 | 2025, 2026 |
| `data/raw/{market}/{year}.parquet` | TN | 2 | 2025, 2026 |
| `data/raw/{market}/{year}.parquet` | ZL | 2 | 2025, 2026 |
| `data/raw/{market}/{year}.parquet` | ZM | 2 | 2025, 2026 |
| `data/causally_gated_normalized/{market}/{year}.parquet` | KE | 14 | 2013-2026 |
| `data/causally_gated_normalized/{market}/{year}.parquet` | SR1 | 9 | 2018-2026 |
| `data/causally_gated_normalized/{market}/{year}.parquet` | TN | 11 | 2016-2026 |
| `data/causally_gated_normalized/{market}/{year}.parquet` | ZL | 16 | 2011-2026 |
| `data/causally_gated_normalized/{market}/{year}.parquet` | ZM | 16 | 2011-2026 |

Later commands, only after explicit approval:

```powershell
python -m scripts.phase1C_validate.audit_raw_dbn_alignment --config <bounded-profile> --profile <bounded-profile> --dbn-root data/dbn --raw-root data/raw --expected-only
```

```powershell
python -m scripts.phase2_causal_base.build_causal_base_data --profile <bounded-profile> --raw-root data/raw --output-root data/causally_gated_normalized --readiness-only
```

Later stop conditions:

- Raw repair: each approved `data/raw/<market>/<year>.parquet` exists and bounded Phase 1C alignment passes for that pair.
- Causal repair: readiness-only passes first, approved causal output exists, Phase 2 validation passes for that pair, and generated `data/` outputs are handled only under the approved repair policy.

## Remaining Duplicate Policy Rows

Recommended decision choices:

- `KEEP_BOTH_DO_NOT_TOUCH`: accept preserving both DBN files in place; no data mutation.
- `APPROVE_MERGE_LATER`: user approves a later content/provenance review and merge target; stop before merge unless separately approved.
- `APPROVE_QUARANTINE_LATER`: user approves a later content/provenance review and quarantine target; stop before quarantine unless separately approved.
- `DEFER_DUPLICATE_POLICY`: leave cleanup blocked.

| Decision group | Count | Canonical path/schema | Pairs | Recommended action |
|---|---:|---|---|---|
| Keep both | 1 | `data/dbn/ohlcv_1m` / `ohlcv-1m` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` |
| Keep both | 1 | `data/dbn/ohlcv_1s` / `ohlcv-1s` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` |
| Keep both | 1 | `data/dbn/ohlcv_1h` / `ohlcv-1h` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` |
| Keep both | 1 | `data/dbn/ohlcv_1d` / `ohlcv-1d` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` |
| Keep both | 1 | `data/dbn/statistics` / `statistics` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` |
| Keep both | 1 | `data/dbn/status` / `status` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` |
| Keep both | 1 | `data/dbn/definition` / `definition` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` |
| Keep both | 1 | `data/dbn/trades` / `trades` | 6M:2026 | `KEEP_BOTH_DO_NOT_TOUCH` |
| User decision | 2 | `data/dbn/statistics` / `statistics` | RTY:2017, SR3:2018 | choose keep both, approve later merge, approve later quarantine, or defer |
| User decision | 2 | `data/dbn/status` / `status` | RTY:2017, SR3:2018 | choose keep both, approve later merge, approve later quarantine, or defer |

Duplicate path detail:

| Schema | Pair | Canonical path candidate | Duplicate path candidate | Current recommendation |
|---|---|---|---|---|
| `ohlcv-1m` | 6M:2026 | `data/dbn/ohlcv_1m/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/ohlcv_1m/6M/2026/2026-06-12_2026-06-13.dbn.zst` | keep both |
| `ohlcv-1s` | 6M:2026 | `data/dbn/ohlcv_1s/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/ohlcv_1s/6M/2026/2026-06-12_2026-06-13.dbn.zst` | keep both |
| `ohlcv-1h` | 6M:2026 | `data/dbn/ohlcv_1h/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/ohlcv_1h/6M/2026/2026-06-12_2026-06-13.dbn.zst` | keep both |
| `ohlcv-1d` | 6M:2026 | `data/dbn/ohlcv_1d/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/ohlcv_1d/6M/2026/2026-06-12_2026-06-13.dbn.zst` | keep both |
| `statistics` | 6M:2026 | `data/dbn/statistics/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/statistics/6M/2026/2026-06-12_2026-06-13.dbn.zst` | keep both |
| `status` | 6M:2026 | `data/dbn/status/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/status/6M/2026/2026-06-12_2026-06-13.dbn.zst` | keep both |
| `definition` | 6M:2026 | `data/dbn/definition/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/definition/6M/2026/2026-06-12_2026-06-13.dbn.zst` | keep both |
| `trades` | 6M:2026 | `data/dbn/trades/6M/2026/2026-01-01_2026-06-13.dbn.zst` | `data/dbn/trades/6M/2026/2026-06-12_2026-06-13.dbn.zst` | keep both |
| `statistics` | RTY:2017 | `data/dbn/statistics/RTY/2017/2017-01-01_2018-01-01.dbn.zst` | `data/dbn/statistics/RTY/2017/2017-06-05_2018-01-01.dbn.zst` | user decision required |
| `statistics` | SR3:2018 | `data/dbn/statistics/SR3/2018/2018-01-01_2019-01-01.dbn.zst` | `data/dbn/statistics/SR3/2018/2018-04-23_2019-01-01.dbn.zst` | user decision required |
| `status` | RTY:2017 | `data/dbn/status/RTY/2017/2017-01-01_2018-01-01.dbn.zst` | `data/dbn/status/RTY/2017/2017-06-05_2018-01-01.dbn.zst` | user decision required |
| `status` | SR3:2018 | `data/dbn/status/SR3/2018/2018-01-01_2019-01-01.dbn.zst` | `data/dbn/status/SR3/2018/2018-04-23_2019-01-01.dbn.zst` | user decision required |

Later command, only after explicit approval:

```powershell
python <approved content/provenance comparison command> <approved duplicate path pair>
```

No merge, quarantine, move, delete, or cleanup command is approved by this report.

## Cleanup Gate

- Cleanup remains disabled.
- Cleanup remains blocked until the 76 repair approval rows and 12 duplicate policy rows are resolved or explicitly deferred by policy.
- `UNKNOWN_BLOCKING_CLEANUP`: 0 in the refreshed gate decision.
