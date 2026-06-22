#!/usr/bin/env python3
"""Disable the paper-only kill switch."""

from __future__ import annotations

from live_ops.risk import KillSwitch
from live_ops.schemas import safe_default_config


def main() -> int:
    config = safe_default_config()
    KillSwitch(config.kill_switch_file).turn_off()
    print(f"paper kill switch OFF: {config.kill_switch_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
