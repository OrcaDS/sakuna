"""Command-line entry point: `sakuna <command>`."""

from __future__ import annotations

import argparse
import logging

from sakuna.settings import load_settings

logger = logging.getLogger("sakuna")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run one command."""
    parser = argparse.ArgumentParser(prog="sakuna")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show-config", help="print the resolved configuration")
    args = parser.parse_args(argv)

    settings = load_settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(message)s")
    if args.command == "show-config":
        for field, value in vars(settings).items():
            logger.info("%s = %s", field, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
