"""Write the gold tables to a release folder as CSV + Parquet, with docs and checksums.

Reads `lake/sakuna.duckdb` (made by `dbt build`). Counts are whole numbers in the source
reports, so they are written as integers; costs (PHP) keep two decimals.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import shutil
from pathlib import Path

import duckdb  # ships with dbt-duckdb

logger = logging.getLogger(__name__)

# Table → sort order, so files diff cleanly between releases.
TABLES = {
    "events": "event_year, start_date, event_id",
    "reports": "event_id, report_date, report_no, sha256",
    "event_summary": "event_year, start_date, event_id",
    "impacts": "event_id, region_code, province_code, psgc_code, dswd_name",
    "impacts_by_report": (
        "event_id, report_date, report_no, sha256, level, region_code, province_code, "
        "psgc_code, dswd_name"
    ),
    "unmatched_places": "region_code, province_code, dswd_name",
}
GZIP_CSV = {"impacts_by_report"}  # ~420 MB as plain CSV; gzip brings it to a download size
DOCS = ("docs/data_dictionary.md", "docs/known_gaps.md")
# Manifest columns published as report_files.csv: every file DROMIC lists, read or not. The
# scheduled check (`sakuna check`) compares DROMIC against it. URLs and DSWD file names only.
REPORT_FILE_FIELDS = ["event_url", "file_url", "label", "report_date", "status", "sha256"]


def _select(con: duckdb.DuckDBPyConnection, table: str) -> str:
    """SELECT for one table: decimals become integers, except cost_* columns."""
    cols = con.execute(
        "select column_name, data_type from information_schema.columns "
        "where table_name = ? order by ordinal_position",
        [table],
    ).fetchall()
    parts = []
    for name, dtype in cols:
        if dtype.startswith("DECIMAL"):
            target = "decimal(18,2)" if name.startswith("cost_") else "bigint"
            parts.append(f'cast("{name}" as {target}) as "{name}"')
        elif dtype == "HUGEINT":
            parts.append(f'cast("{name}" as bigint) as "{name}"')
        else:
            parts.append(f'"{name}"')
    return f"select {', '.join(parts)} from {table} order by {TABLES[table]}"


def export(
    db_path: Path, out_dir: Path, docs_root: Path = Path("."), manifest: Path | None = None
) -> dict[str, int]:
    """Write every gold table (and the manifest's file list) to out_dir; return row counts."""
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found: run dbt build first")
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with duckdb.connect(str(db_path), read_only=True) as con:
        for table in TABLES:
            query = _select(con, table)
            csv = ("csv.gz", "header, compression gzip") if table in GZIP_CSV else ("csv", "header")
            for ext, opts in (csv, ("parquet", "format parquet, compression zstd")):
                path = (out_dir / f"{table}.{ext}").as_posix()
                con.execute(f"copy ({query}) to '{path}' ({opts})")
            counts[table] = con.execute(f"select count(*) from {table}").fetchall()[0][0]
            logger.info("%s: %d rows", table, counts[table])
    if manifest is not None:
        counts["report_files"] = _write_report_files(manifest, out_dir / "report_files.csv")
    for doc in DOCS:
        src = docs_root / doc
        if src.exists():
            shutil.copy(src, out_dir / src.name)
        else:
            logger.warning("%s missing; not copied", src)
    _write_checksums(out_dir)
    return counts


def _write_report_files(manifest: Path, out: Path) -> int:
    with manifest.open(newline="", encoding="utf-8") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: (r["event_url"], r["file_url"]))
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REPORT_FILE_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    logger.info("report_files: %d rows", len(rows))
    return len(rows)


def _write_checksums(out_dir: Path) -> None:
    """SHA256SUMS in the format `sha256sum -c` reads."""
    lines = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
    (out_dir / "SHA256SUMS").write_text("".join(lines), encoding="utf-8", newline="\n")
