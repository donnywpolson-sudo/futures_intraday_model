from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from pipeline.data_gate.manifest import build_data_manifest


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m pipeline.data.manifest")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--root", required=True)
    b.add_argument("--out")
    b.add_argument("--csv")
    b.add_argument("--stage", required=True)
    args = p.parse_args()
    if args.cmd == "build":
        report = build_data_manifest(args.root, stage=args.stage)
        root = Path(args.root)
        if args.out and Path(args.out) != root / "manifest.json":
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / "manifest.json", args.out)
        if args.csv and Path(args.csv) != root / "_manifest.csv":
            Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / "_manifest.csv", args.csv)
        print(f"manifest={report['status']} files={len(report['files'])}")


if __name__ == "__main__":
    main()
