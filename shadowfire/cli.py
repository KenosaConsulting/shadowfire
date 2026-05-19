from __future__ import annotations

import argparse
import sys

from .store import DB_PATH, init


def _cmd_init_db(_: argparse.Namespace) -> int:
    init()
    print(f"Initialized DuckDB at {DB_PATH}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shadowfire",
        description="ShadowFire command-line utilities",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser(
        "init-db",
        help="Create the local DuckDB file and required tables.",
    )
    init_db.set_defaults(func=_cmd_init_db)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
