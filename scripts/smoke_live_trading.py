#!/usr/bin/env python3
"""Run deterministic paper-only live trading smoke scenarios."""

from __future__ import annotations

import sys

from live_ops.smoke import run_smoke


def main() -> int:
    return 0 if run_smoke(stdout=sys.stdout) else 1


if __name__ == "__main__":
    raise SystemExit(main())
