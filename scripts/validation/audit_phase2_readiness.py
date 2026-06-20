#!/usr/bin/env python3
"""Read-only fail-closed readiness audit for Phase 2 causal base inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.phase2_causal_base.build_causal_base_data import (
    DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
    DEFAULT_PROFILE,
    DEFAULT_PROFILE_CONFIG,
    DEFAULT_RAW_ALIGNMENT_REPORT,
    DEFAULT_ROLL_WINDOW_BARS,
    DEFAULT_SESSION_CONFIG,
    build_phase2_readiness_report,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--raw-root", default="data/raw")
    parser.add_argument("--raw-alignment-report", default=str(DEFAULT_RAW_ALIGNMENT_REPORT))
    parser.add_argument("--output-root", default="data/causally_gated_normalized")
    parser.add_argument("--profile-config", default=str(DEFAULT_PROFILE_CONFIG))
    parser.add_argument("--session-config", default=str(DEFAULT_SESSION_CONFIG))
    parser.add_argument("--allow-hardcoded-calendar", action="store_true")
    parser.add_argument("--roll-window-bars", type=int, default=DEFAULT_ROLL_WINDOW_BARS)
    parser.add_argument(
        "--max-synthetic-gap-minutes",
        type=int,
        default=DEFAULT_MAX_SYNTHETIC_GAP_MINUTES,
    )
    parser.add_argument("--fail-fast", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_phase2_readiness_report(
        profile=args.profile,
        raw_root=Path(args.raw_root),
        raw_alignment_report=Path(args.raw_alignment_report),
        output_root=Path(args.output_root),
        profile_config_path=Path(args.profile_config),
        session_config_path=Path(args.session_config),
        roll_window_bars=args.roll_window_bars,
        max_synthetic_gap_minutes=args.max_synthetic_gap_minutes,
        allow_hardcoded_calendar=args.allow_hardcoded_calendar,
        fail_fast=args.fail_fast,
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
