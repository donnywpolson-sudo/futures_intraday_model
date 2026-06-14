# Manifests

This directory is for small, durable metadata that helps rebuild, audit, or
verify the project without committing raw data or generated artifacts.

Use `scripts/write_project_inventory.py` to generate `project_inventory.csv`.
The default inventory excludes local data/artifact directories and does not
hash files, which keeps it fast on a large working tree.

Commands:

```powershell
python scripts/write_project_inventory.py
python scripts/write_project_inventory.py --include-data
python scripts/write_project_inventory.py --hash
```

Do not use this directory for raw market data, model binaries, caches, or large
generated reports.
