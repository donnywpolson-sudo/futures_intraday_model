# Tier 1 Data Audit To-Do

Snapshot updated: 2026-06-16. Refresh progress before acting.

## Current Reference Point

- Active workflow: `build_missing_minute_verification_manifest`.
- Current audit priority: Tier 1 markets `ES CL ZN 6E`, long research years `2010-2024`.
- Tier 1 missing-minute manifest records are complete: `60 / 60`, all `PASS`.
- Tier 1 totals from `reports/pipeline_audit/missing_minute_verification_manifest_tier_3_progress.jsonl`:
  - windows: `492996`
  - missing minutes: `803433`
  - failures: `0`
- Overall progress JSONL currently has `85` records: `PASS=85`, `FAIL=0`.
- Removed stale generated record: `RTY 2010 FAIL`, created before the planner was changed to skip unavailable pre-start years. Current planner skips unavailable years before the first common raw+causal parquet year.
- Current non-Tier-1 progress already recorded:
  - `NQ 2010-2024`: complete, all `PASS`
  - `RTY 2017-2024`: complete, all `PASS`
  - `YM 2010-2011`: complete, all `PASS`
- Planner changes for first-available-year trimming are currently local modifications and should be committed before relying on long unattended resumes.

## Meta-Audit Of The Plan

The goal is correct: build a Tier 1 data-integrity record before trusting core research, model selection, or WFA scaling.

The sequence is good, with these important caveats:

- The cumulative output of the chunked missing-minute run is the progress JSONL:
  `reports/pipeline_audit/missing_minute_verification_manifest_tier_3_progress.jsonl`.
- The `--json-out` and `--md-out` chunk files are not a full accumulated manifest when `--resume-progress` is used. They represent the current chunk plus skipped keys.
- `--resume-progress` skips any recorded market-year key, including a key that recorded `FAIL`. If any market-year fails, stop and diagnose it before continuing with the same progress file.
- `PASS` for `build_missing_minute_verification_manifest` means the audit record was built for that market-year. It does not prove missing OHLCV minutes had no trades.
- `PASS` for `audit_ohlcv_provenance_continuity` means local OHLCV lineage, DBN manifests/hashes, raw parquet source evidence, definition metadata, and causal continuity are internally consistent. It still does not prove no trades occurred inside missing OHLCV minutes.
- Trade-source verification with `trades` or `mbp-1` is a later, selected, provider-costed audit step. Do not start it until high-risk windows are selected.

## End Goal

Produce a Tier 1 data-integrity record with:

1. Missing-minute verification records for `ES CL ZN 6E`, 2010-2024.
2. Provenance/continuity audit records for `ES ZN CL 6E`, preferably one market at a time.
3. A market-year decision list: acceptable with caveat, quarantined, or requires trade-source verification.
4. No downstream research/model expansion until the data-integrity state is understood.

## Step 1 - Missing-Minute Verification

Status: complete for Tier 1.

Do not keep rerunning Tier 1 missing-minute manifest unless intentionally rebuilding or repairing the progress file.

Historical command pattern used:

```powershell
python -m scripts.validation.build_missing_minute_verification_manifest `
  --profile tier_3_research `
  --markets ES CL ZN 6E `
  --raw-root data/raw `
  --causal-root data/causally_gated_normalized `
  --session-config configs/market_sessions.yaml `
  --json-out reports/pipeline_audit/missing_minute_verification_manifest_tier_1_remaining_chunk.json `
  --md-out reports/pipeline_audit/missing_minute_verification_manifest_tier_1_remaining_chunk.md `
  --progress-jsonl reports/pipeline_audit/missing_minute_verification_manifest_tier_3_progress.jsonl `
  --resume-progress `
  --max-market-years 1
```

If rebuilding:

- Stop if any chunk returns `FAIL`.
- Stop if progress stops advancing for an unexpectedly long time.
- Stop before launching unrelated disk-heavy audits unless you intentionally accept disk contention.

## Step 2 - Check Missing-Minute Progress

Use this to summarize cumulative progress:

```powershell
python -c "exec('import json,pathlib,collections\np=pathlib.Path(\"reports/pipeline_audit/missing_minute_verification_manifest_tier_3_progress.jsonl\")\ntier1={\"ES\",\"CL\",\"ZN\",\"6E\"}\nby=collections.Counter(); statuses=collections.Counter(); tier1_records=0; tier1_windows=0; tier1_missing=0; tier1_fail=[]; lines=0\nif p.exists():\n    with p.open(encoding=\"utf-8\") as f:\n        for line in f:\n            if not line.strip():\n                continue\n            lines += 1\n            r = json.loads(line)\n            m = r.get(\"market\")\n            by[m] += 1\n            statuses[r.get(\"status\")] += 1\n            if m in tier1:\n                tier1_records += 1\n                s = r.get(\"summary\") or {}\n                tier1_windows += int(s.get(\"window_count\") or 0)\n                tier1_missing += int(s.get(\"total_missing_minutes\") or 0)\n                if r.get(\"status\") != \"PASS\":\n                    tier1_fail.append((m, r.get(\"year\"), r.get(\"failures\")))\nprint(\"records\", lines)\nprint(\"statuses\", dict(statuses))\nprint(\"by_market\", dict(by))\nprint(\"tier1_records\", tier1_records, \"/ 60\")\nprint(\"tier1_windows\", tier1_windows)\nprint(\"tier1_missing_minutes\", tier1_missing)\nprint(\"tier1_failures\", tier1_fail)')"
```

Completion criteria for Step 1:

- `tier1_records 60 / 60`.
- `tier1_failures []`.
- Every Tier 1 market has 15 records.

## Step 3 - Run Provenance/Continuity Audit One Market At A Time

After Step 1 is complete, run `audit_ohlcv_provenance_continuity` one market at a time.

Current market order:

```text
ES CL ZN 6E
```

Template:

```powershell
$market = "ES"

python -m scripts.validation.audit_ohlcv_provenance_continuity `
  --markets $market `
  --years 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 `
  --raw-root data/raw `
  --causal-root data/causally_gated_normalized `
  --dbn-root data/dbn `
  --session-config configs/market_sessions.yaml `
  --json-out reports/pipeline_audit/ohlcv_provenance_$($market)_2010_2024.json `
  --md-out reports/pipeline_audit/ohlcv_provenance_$($market)_2010_2024.md
```

Already run separately:

- `ES 2024` provenance audit: `PASS`, decision `keep_quarantined_ohlcv_only_evidence_insufficient`.

That single-year report does not replace the full 2010-2024 Tier 1 provenance pass.

For each market, review:

- report status
- failures
- decision
- synthetic row counts
- active-session synthetic share
- largest gap size
- provenance hash/source match

Stop and diagnose any `FAIL` before continuing to the next market.

## Step 4 - Build The Decision List

After provenance audits finish, create a concise decision table by market-year:

- `acceptable_with_caveat_ohlcv_empty_minutes_assumed`
- `keep_quarantined_ohlcv_only_evidence_insufficient`
- `requires_trade_source_verification`
- `failed_local_provenance_or_inputs`

Do not change Phase 2/session/fill semantics from OHLCV-only evidence.

## Step 5 - Optional Trade-Source Verification

Only after Steps 1-4, select high-risk windows for `trades` or `mbp-1` verification.

Use this only for targeted gaps because it may require provider access and cost:

1. Build a source-gap plan.
2. Estimate provider cost.
3. Review cost and scope.
4. Download only if intentionally approved.
5. Use the result to decide whether specific missing OHLCV minutes had trade or book activity.

## Do Not Do During This Audit

- Do not run broad model tuning or full WFA scaling.
- Do not continue broad Tier 3 missing-minute runs while the current priority is Tier 1 provenance and decisioning, unless explicitly requested.
- Do not promote any model or policy output.
- Do not change session normalization, target construction, fill semantics, or cost assumptions from OHLCV-only audit evidence.
- Do not stage or commit generated `data/` or `reports/` artifacts unless explicitly requested.
