#!/usr/bin/env python3
"""Flatten simulated paper positions only."""

from __future__ import annotations

from pathlib import Path

from live_ops.broker import PaperBroker

STATE_PATH = Path(".runtime/paper_broker_state.json")


def main() -> int:
    broker = PaperBroker.load(STATE_PATH)
    fills = broker.flatten_all()
    print(f"paper flatten_all fills={len(fills)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
