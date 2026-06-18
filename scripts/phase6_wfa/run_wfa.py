#!/usr/bin/env python3
"""Phase 6 entrypoint for WFA model training and OOS predictions."""

from __future__ import annotations

from scripts.phase7_wfa.run_wfa import *  # noqa: F403
from scripts.phase7_wfa.run_wfa import main


if __name__ == "__main__":
    raise SystemExit(main())
