#!/usr/bin/env python3
"""Phase 6 entrypoint for combining WFA prediction shards."""

from __future__ import annotations

from scripts.phase7_wfa.combine_wfa_predictions import *  # noqa: F403
from scripts.phase7_wfa.combine_wfa_predictions import main


if __name__ == "__main__":
    raise SystemExit(main())
