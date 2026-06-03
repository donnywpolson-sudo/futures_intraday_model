from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.data_gate.manifest import build_data_manifest


ROOTS = {
    "raw": Path("data/raw"),
    "validated": Path("data/validated"),
    "session_normalized": Path("data/session_normalized"),
    "causally_gated_normalized": Path("data/causally_gated_normalized"),
    "labeled": Path("data/labeled"),
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stages", nargs="+", default=list(ROOTS))
    args = p.parse_args()
    for stage in args.stages:
        if stage not in ROOTS:
            raise SystemExit(f"unknown stage: {stage}")
        ROOTS[stage].mkdir(parents=True, exist_ok=True)
        report = build_data_manifest(ROOTS[stage], stage=stage)
        print(f"{stage}: {len(report['files'])} files")


if __name__ == "__main__":
    main()

