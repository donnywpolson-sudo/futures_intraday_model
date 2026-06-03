from __future__ import annotations

import argparse

from pipeline.session.normalize import session_normalize_root


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in-root", default="data/validated")
    p.add_argument("--out-root", default="data/session_normalized")
    p.add_argument("--sessions", default="data/market_sessions.yaml")
    args = p.parse_args()
    report = session_normalize_root(args.in_root, args.out_root, args.sessions)
    print(report["status"])


if __name__ == "__main__":
    main()

