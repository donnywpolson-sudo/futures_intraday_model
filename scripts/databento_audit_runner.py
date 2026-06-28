#!/usr/bin/env python3
"""Controlled staged Databento futures data audit runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_databento_common import (  # noqa: E402
    AUDIT_STATE_PATH,
    DEFAULT_DATA_ROOT,
    DEFAULT_OUTPUT_DIR,
    PHASES,
    gate_passes,
    phase_gate_path,
    phase_name,
    read_json_if_exists,
    repo_path,
)
from scripts.audit_databento_phase0 import run_phase0  # noqa: E402
from scripts.audit_databento_phase1 import run_phase1  # noqa: E402
from scripts.audit_databento_phase2 import run_phase2  # noqa: E402
from scripts.audit_databento_phase3 import run_phase3  # noqa: E402
from scripts.audit_databento_phase4 import run_phase4  # noqa: E402
from scripts.audit_databento_phase5 import run_phase5  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--phase", type=int, choices=sorted(PHASES))
    mode.add_argument("--safe-auto", action="store_true")
    parser.add_argument("--through", type=int, choices=sorted(PHASES), default=0)
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--schemas", nargs="*")
    parser.add_argument("--markets", nargs="*")
    parser.add_argument("--years", nargs="*")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    sample_mode = parser.add_mutually_exclusive_group()
    sample_mode.add_argument("--sample", action="store_true")
    sample_mode.add_argument("--full", action="store_true")
    parser.add_argument("--sample-first", action="store_true")
    parser.add_argument("--allow-full-scan", action="store_true")
    parser.add_argument("--stop-on-severe", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--fail-on-severe", action="store_true")
    parser.add_argument("--reconstruct-ohlcv-from-trades", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def gate_for_phase(output_dir: str | Path, phase: int) -> Path:
    if phase == 0:
        return phase_gate_path(Path(output_dir), 0, "phase0_readiness_gate.json")
    if phase == 1:
        return phase_gate_path(Path(output_dir), 1, "phase1_readiness_gate.json")
    if phase == 2:
        return phase_gate_path(Path(output_dir), 2, "phase2_readiness_gate.json")
    if phase == 5:
        return repo_path(Path(output_dir) / "final" / "model_readiness_gate.json")
    return phase_gate_path(Path(output_dir), phase, f"phase{phase}_readiness_gate.json")


def enforce_full_scan_policy(args: argparse.Namespace, phase: int) -> None:
    if args.full and not args.allow_full_scan:
        raise SystemExit("full scans require --allow-full-scan")
    if phase in {2, 3} and args.full and args.sample_first and not args.allow_full_scan:
        raise SystemExit("Phase 2/3 full scans require sampled pass first and --allow-full-scan")


def enforce_prerequisites(args: argparse.Namespace, phase: int) -> None:
    if phase == 0:
        return
    for previous in range(0, phase):
        gate = gate_for_phase(args.output_dir, previous)
        if not gate_passes(gate):
            raise SystemExit(f"missing or failed prerequisite gate for phase {previous}: {gate}")


def enforce_resume(args: argparse.Namespace) -> None:
    if not args.resume:
        return
    state_path = repo_path(AUDIT_STATE_PATH)
    state = read_json_if_exists(state_path)
    if state is None:
        raise SystemExit(f"--resume requested but state file is missing: {state_path}")
    expected = {
        "data_root": str(args.data_root),
        "output_dir": str(args.output_dir),
    }
    mismatches = {
        key: {"state": state.get(key), "current": value}
        for key, value in expected.items()
        if state.get(key) != value
    }
    if mismatches:
        raise SystemExit("--resume scope/options conflict with audit_state.json: " + json.dumps(mismatches, sort_keys=True))


def run_registered_non_phase0(phase: int) -> int:
    print(f"{phase_name(phase)} is registered for staged execution but was not run in this Phase 0-only pass.")
    return 0


def run_single_phase(args: argparse.Namespace, phase: int) -> int:
    enforce_full_scan_policy(args, phase)
    enforce_prerequisites(args, phase)
    if phase == 0:
        payload = run_phase0(args)
        severe_count = int(payload.get("severe_count", payload.get("blocker_counts", {}).get("severe", 0)))
        if severe_count and args.stop_on_severe:
            print("stop-on-severe: stopping after phase0")
        return 1 if severe_count and args.fail_on_severe else 0
    if phase == 1:
        payload = run_phase1(args)
        severe_count = int(payload.get("severe_count", 0))
        if severe_count and args.stop_on_severe:
            print("stop-on-severe: stopping after phase1")
        return 1 if severe_count and args.fail_on_severe else 0
    if phase == 2:
        payload = run_phase2(args)
        severe_count = int(payload.get("severe_count", 0))
        if severe_count and args.stop_on_severe:
            print("stop-on-severe: stopping after phase2")
        return 1 if severe_count and args.fail_on_severe else 0
    if phase == 3:
        payload = run_phase3(args)
        severe_count = int(payload.get("severe_count", 0))
        if severe_count and args.stop_on_severe:
            print("stop-on-severe: stopping after phase3")
        return 1 if severe_count and args.fail_on_severe else 0
    if phase == 4:
        payload = run_phase4(args)
        severe_count = int(payload.get("severe_count", 0))
        if severe_count and args.stop_on_severe:
            print("stop-on-severe: stopping after phase4")
        return 1 if severe_count and args.fail_on_severe else 0
    if phase == 5:
        payload = run_phase5(args)
        severe_count = int(payload.get("severe_count", 0))
        if severe_count and args.stop_on_severe:
            print("stop-on-severe: stopping after phase5")
        return 1 if severe_count and args.fail_on_severe else 0
    return run_registered_non_phase0(phase)


def run_safe_auto(args: argparse.Namespace) -> int:
    for phase in range(0, int(args.through) + 1):
        code = run_single_phase(args, phase)
        if code != 0:
            return code
        gate = read_json_if_exists(gate_for_phase(args.output_dir, phase))
        severe_count = int((gate or {}).get("severe_count", 0))
        if severe_count and args.stop_on_severe:
            return 1 if args.fail_on_severe else 0
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    enforce_resume(args)
    if args.safe_auto:
        return run_safe_auto(args)
    phase = 0 if args.phase is None else int(args.phase)
    return run_single_phase(args, phase)


if __name__ == "__main__":
    raise SystemExit(main())
