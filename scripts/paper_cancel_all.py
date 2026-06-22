#!/usr/bin/env python3
"""Cancel simulated paper orders only."""

from __future__ import annotations

from pathlib import Path

from live_ops.broker import PaperBroker

STATE_PATH = Path(".runtime/paper_broker_state.json")


def main() -> int:
    broker = PaperBroker.load(STATE_PATH)
    count = broker.cancel_all()
    print(f"paper cancel_all canceled={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
