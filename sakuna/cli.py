"""Command-line entry point: `sakuna <command>`."""

from __future__ import annotations

import argparse
import logging
import subprocess
from datetime import date
from pathlib import Path

from sakuna import discover, download, export, extract, manifest, psgc
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
    rel = sub.add_parser("export", help="write gold tables as CSV + Parquet for a release")
    rel.add_argument("--out", type=Path, default=Path("release"), help="output folder")
    ck = sub.add_parser("check", help="list DROMIC report files not in a known file list")
    ck.add_argument("--known", type=Path, required=True, help="report_files.csv or manifest.csv")
    ck.add_argument("--out", type=Path, help="write an issue body here if anything is new")
    up = sub.add_parser("update", help="discover, download, extract, dbt build, export")
    up.add_argument("--refresh", action="store_true", help="also re-check downloaded files")
    args = parser.parse_args(argv)

    settings = load_settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(message)s")
    if args.command == "show-config":
        for field, value in vars(settings).items():
            logger.info("%s = %s", field, value)
    elif args.command == "discover":
        found = _discover_all(settings)
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
    elif args.command == "export":
        counts = export.export(
            settings.lake_root / "sakuna.duckdb",
            args.out,
            manifest=manifest.manifest_path(settings.raw_root),
        )
        logger.info("exported %d tables to %s", len(counts), args.out)
    elif args.command == "check":
        new = discover.unseen(_discover_all(settings), manifest.read(args.known))
        logger.info("%d new report files", len(new))
        for f in new:
            logger.info("new: %s | %s", f["event_title"], f["file_url"])
        if new and args.out:
            args.out.write_text(discover.new_reports_markdown(new), encoding="utf-8")
    elif args.command == "update":
        main(["discover"])
        main(["download", *(["--refresh"] if args.refresh else [])])
        main(["extract"])
        # Own process: in-process dbt keeps the DuckDB file open and export can't reopen it.
        build = ["dbt", "build", "--project-dir", "transform", "--profiles-dir", "transform"]
        if subprocess.run(build, check=False).returncode != 0:
            logger.error("dbt build failed; nothing exported")
            return 1
        main(["export"])
    return 0


def _discover_all(settings) -> list[dict]:
    # Category 2016 holds early-2017 events (Auring, 07 Jan 2017).
    return discover.discover(settings, list(range(2016, date.today().year + 1)))


if __name__ == "__main__":
    raise SystemExit(main())
