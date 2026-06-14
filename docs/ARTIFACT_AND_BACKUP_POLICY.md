# Artifact And Backup Policy

GitHub tracks the source of truth needed to rebuild the project logic:

- Code and utilities in `scripts/`.
- Configuration in `configs/`.
- Tests in `tests/`.
- Documentation in `README*.md` and `docs/`.
- Small inventories and summaries in `manifests/`.

GitHub does not store raw market data, generated parquet files, DBN/ZST
archives, model binaries, local virtual environments, caches, logs, temporary
reports, or secrets.

Do not commit:

- Raw market data under `data/`.
- Generated `*.parquet`, `*.dbn`, `*.zst`, `*.pkl`, `*.joblib`, `*.npy`, or
  `*.npz` files.
- Model artifacts under `models/`.
- Local environments such as `.venv/`.
- API keys, credentials, `.env` files, `.key` files, or `.pem` files.

If a generated report is important for future review, save a small durable
summary under `manifests/` or `docs/` instead of committing the heavy report.

Recommended backup model:

1. Local working copy on the primary machine.
2. External SSD or NAS backup for ignored data/artifacts.
3. Off-site or cloud backup for disaster recovery.

GitHub restores the code and rebuild instructions. Full byte-for-byte restore
of the current local working tree also requires backup coverage for ignored
data and generated artifacts.
