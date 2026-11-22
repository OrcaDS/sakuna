"""Command-line entry point: `sakuna <command>`."""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from sakuna import discover, download, extract, manifest, psgc
from sakuna.settings import load_settings

logger = logging.getLogger("sakuna")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run one command."""
    parser = argparse.ArgumentParser(prog="sakuna")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("show-config", help="print the resolved configuration")
    sub.add_parser("discover", help="find events and report files; add new ones to the manifest")
    dl = sub.add_parser("download", help="download pending and failed files in the manifest")
    dl.add_argument("--refresh", action="store_true", help="also re-check downloaded files")
    dl.add_argument("--limit", type=int, help="download at most this many files")
    ex = sub.add_parser("extract", help="read number tables from downloaded files into bronze")
    ex.add_argument("--force", action="store_true", help="also re-extract files already done")
    ex.add_argument("--limit", type=int, help="extract at most this many files")
    ps = sub.add_parser("psgc", help="turn PSA's PSGC .xlsx into transform/seeds/psgc.csv")
    ps.add_argument("xlsx", type=Path, help="PSGC publication datafile downloaded from psa.gov.ph")
    args = parser.parse_args(argv)

    settings = load_settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(message)s")
    if args.command == "show-config":
        for field, value in vars(settings).items():
            logger.info("%s = %s", field, value)
    elif args.command == "discover":
        # Category 2016 holds early-2017 events (Auring, 07 Jan 2017).
        found = discover.discover(settings, list(range(2016, date.today().year + 1)))
        path = manifest.manifest_path(settings.raw_root)
        rows = manifest.read(path)
        added = manifest.merge(rows, found, download.now())
        manifest.write(path, rows)
        logger.info("%d files found, %d new; manifest: %s", len(found), added, path)
    elif args.command == "download":
        counts = download.download(settings, refresh=args.refresh, limit=args.limit)
        logger.info("manifest status: %s", counts)
    elif args.command == "extract":
        counts = extract.extract(settings, force=args.force, limit=args.limit)
        logger.info("bronze status: %s; log: %s", dict(counts), extract.bronze_root(settings))
    elif args.command == "psgc":
        out = Path("transform/seeds/psgc.csv")
        logger.info("%d places → %s", psgc.write_seed(args.xlsx, out), out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
