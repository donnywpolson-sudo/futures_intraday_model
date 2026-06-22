# Phase 1A Smoke

Status: PASS

Scope: manifest-bounded ZN 2023 dry-run only. No Databento request was executed and no DBN source file was written.

Command:
```powershell
python -m scripts.phase1A_download.download_databento_raw --mode download-dbn --schema ohlcv-1m --markets ZN --start 2023-01-01 --end 2024-01-01 --chunk year --dbn-root data/dbn/ohlcv_1m --raw-root data/raw --reports-root reports/phase_restart/manifest_phase_1a_smoke --workers 1 --resume --dry-run
```

Result:
- Dry-run plan status: PASS.
- Planned tasks: 1.
- Product/year: ZN 2023.
- Planned canonical DBN output: `data/dbn/ohlcv_1m/ZN/2023/2023-01-01_2024-01-01.dbn.zst`.
- Resolved raw root: `data/raw`.
- Evidence: `reports/phase_restart/manifest_phase_1a_smoke/databento_download_plan_dry_run.json`.

Safety checks:
- DBN download/run kind: `dry_run`.
- Phase after phase 2: not run.
- Data mutation check after run: `git status --short -- data` returned no output.
