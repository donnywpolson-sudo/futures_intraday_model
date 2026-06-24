#!/usr/bin/env python3
"""Phase 1B entry point for DBN archive to raw Parquet conversion."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1A_download.download_databento_raw import main


def _has_arg(name: str) -> bool:
    return any(arg == name or arg.startswith(f"{name}=") for arg in sys.argv[1:])


def phase1b_main() -> int:
    if not _has_arg("--mode"):
        sys.argv[1:1] = ["--mode", "convert-parquet"]
    if not _has_arg("--include-optional-schemas"):
        sys.argv.extend(["--include-optional-schemas", "status,statistics"])
    if not _has_arg("--optional-schema-policy"):
        sys.argv.extend(["--optional-schema-policy", "require"])
    return main()


if __name__ == "__main__":
    raise SystemExit(phase1b_main())
