#!/usr/bin/env python3
"""Compatibility wrapper for scripts.phase1C_validate.audit_raw_dbn_alignment."""

from __future__ import annotations

from scripts.phase1C_validate.audit_raw_dbn_alignment import *  # noqa: F401,F403
from scripts.phase1C_validate.audit_raw_dbn_alignment import main


if __name__ == "__main__":
    raise SystemExit(main())
