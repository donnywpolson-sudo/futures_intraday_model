from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.session.normalize import session_normalize_root


def _parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [x.strip() for x in value.split(",") if x.strip()]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in-root", default="data/validated")
    p.add_argument("--out-root", default="data/session_normalized")
    p.add_argument("--sessions", default="configs/raw_data_validation.yaml")
    p.add_argument("--markets", help="Comma-separated markets to process, e.g. ES,CL,ZN")
    p.add_argument("--start-year", type=int)
    p.add_argument("--end-year", type=int)
    args = p.parse_args()
    report = session_normalize_root(
        args.in_root,
        args.out_root,
        args.sessions,
        markets=_parse_csv(args.markets),
        start_year=args.start_year,
        end_year=args.end_year,
    )
    print(report["status"])


if __name__ == "__main__":
    main()
