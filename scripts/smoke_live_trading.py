#!/usr/bin/env python3
"""Run deterministic paper-only live trading smoke scenarios."""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from live_ops.smoke import run_smoke


def build_arg_parser() -> ArgumentParser:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", default="reports/live_trading_smoke")
    parser.add_argument("--force-failure", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    return 0 if run_smoke(audit_dir=args.audit_dir, stdout=sys.stdout, force_failure=args.force_failure) else 1


if __name__ == "__main__":
    raise SystemExit(main())
