# Manifests

This directory is for small, durable metadata that helps rebuild, audit, or
verify the project without committing raw data or generated artifacts.

Use `scripts/write_project_inventory.py` to generate `project_inventory.csv`.
The default inventory excludes local data/artifact directories and does not
hash files, which keeps it fast on a large working tree.

Feature sets live under `manifests/feature_sets/`. These are small tracked
metadata files that freeze an approved list of model input features without
committing generated feature matrices.

Feature hypothesis status lives under `manifests/feature_hypotheses/`. Use it
to track candidate, rejected, confirmed, frozen, retired, and quarantined
feature ideas before any WFA run consumes a frozen feature set.

Commands:

```powershell
python scripts/write_project_inventory.py
python scripts/write_project_inventory.py --include-data
python scripts/write_project_inventory.py --hash
python -m scripts.phase9_research.feature_hypothesis_registry
```

Do not use this directory for raw market data, model binaries, caches, or large
generated reports.
