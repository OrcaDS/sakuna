"""Extract → bronze: the five number tables of each report, one Parquet row per table cell.

Readers (`sakuna.docx_reader`, `sakuna.pdf_reader`) turn a file into `Piece`s: a header path
per column plus the rows under it. This module picks the town-level table of each kind,
stitches tables that continue across pages, labels row levels, and writes bronze.
Only tables whose header names a REGION / PROVINCE / MUNICIPALITY column are read, so free
text (where names live) never reaches bronze.
"""

from __future__ import annotations

import csv
import logging
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from sakuna import manifest
from sakuna.settings import Settings

logger = logging.getLogger(__name__)

NUMBER = re.compile(r"^\(?-?[\d,]*\.?\d+\)?%?\*?$|^-+$")  # "38,620.00*": footnote mark
REGION_NAME = re.compile(
    # "NIR 6" / "NIR 7" (2025) are sub-totals under NIR, not regions
    r"^(REGION\b|NCR\b|CAR\b|CARAGA\b|MIMAROPA\b|CALABARZON\b|BARMM\b|ARMM\b"
    r"|NIR\b(?!\s*\d)|NEGROS ISLAND)",
    re.IGNORECASE,
)
# Names that are never a town or province (Caraga is also a town in Davao Oriental, so not here).
UNMISTAKABLE_REGION = re.compile(
    r"^(REGION\b|NCR$|CAR$|BARMM$|ARMM$|MIMAROPA$|CALABARZON$)", re.IGNORECASE
)
HASHES = re.compile(r"^#+$")
MAX_NAME_LEN = 100
COLUMNS = ["sha256", "kind", "row_no", "level", "name", "column", "value"]
LOG_FIELDS = ["sha256", "local_path", "status", "rows", "kinds", "dropped", "error"]


@dataclass
class Piece:
    """One table as read from a file: header path per column (empty = no header) and rows."""

    paths: list[str]
    rows: list[tuple[list[str], bool]] = field(default_factory=list)  # (cells, looks like area)


def clean(text: str | None) -> str:
    return " ".join((text or "").split())


def is_header_row(cells: list[str]) -> bool:
    """Header rows hold no number cells; the first row with a number starts the data."""
    return not any(NUMBER.match(c) for c in cells)


def header_paths(grid: list[list[str]]) -> list[str]:
    """Join each column's header cells top to bottom, e.g. 'NUMBER OF AFFECTED > Families'."""
    width = max((len(r) for r in grid), default=0)
    paths = []
    for j in range(width):
        parts: list[str] = []
        for row in grid:
            t = row[j] if j < len(row) else ""
            if t and (not parts or parts[-1] != t):
                parts.append(t)
        paths.append(" > ".join(parts))
    return paths


def name_columns(paths: list[str]) -> list[int]:
    """The REGION / PROVINCE / MUNICIPALITY columns, plus unlabelled columns right after them
    (some PDF pages split the name column in two)."""
    cols = [j for j, p in enumerate(paths) if p.upper().startswith("REGION") and len(p) < 80]
    while cols and cols[-1] + 1 < len(paths) and not paths[cols[-1] + 1]:
        cols.append(cols[-1] + 1)
    return cols


def kind_of(paths: list[str]) -> str | None:
    """Which of the five tables this is, by header keyword (never by position)."""
    if not name_columns(paths):
        return None
    h = " ".join(paths).upper()
    inside, outside = "INSIDE" in h, "OUTSIDE" in h
    found = [
        k
        for k, hit in (
            ("houses", "HOUSE" in h and "DAMAGE" in h),  # also "NO. OF DAMAGE HOUSES" (2022)
            ("cost", "COST OF ASSISTANCE" in h),
            ("affected", "AFFECTED" in h),
            ("displaced", inside and outside),  # 2017-2018: inside and outside ECs in one table
            ("inside_ec", inside and not outside),
            ("outside_ec", outside and not inside),
        )
        if hit
    ]
    if len(found) > 1:
        return "combined"  # 2018: one table with all measures; silver splits it by header
    return found[0] if found else None


def _is_grand_total(piece: Piece) -> bool:
    return any("GRAND TOTAL" in c.upper() for c in piece.rows[0][0][:3])


def _starts_total(piece: Piece) -> bool:
    """A headerless table starting with a TOTAL row is a new table (standby funds after the
    cost table, 2022), never the next page of the one before."""
    first = next((c for c in piece.rows[0][0] if c), "").upper()
    return first.startswith("TOTAL")


def _filled(cells: list[str]) -> list[str]:
    return [c for c in cells if c]


def _repeats_total(piece: Piece, first_rows: list) -> bool:
    """Some PDFs repeat the GRAND TOTAL row on every page with the header. That is the same
    table going on when the total matches the run's and the next row is new; a fresh copy
    (summary vs annex) starts again with the same first region."""
    if len(piece.rows) < 2 or len(first_rows) < 2:
        return False
    return _filled(piece.rows[0][0]) == _filled(first_rows[0][0]) and _filled(
        piece.rows[1][0]
    ) != _filled(first_rows[1][0])


def select(pieces: list[Piece]) -> dict[str, list[tuple[list[str], list]]]:
    """Group pieces into runs (one table split over pages) and keep the longest run per kind.

    A run continues while pieces of the same kind follow each other; a piece starting with
    GRAND TOTAL starts a new run (the summary and annex copies of a table), unless it only
    repeats the run's total on a new page (`_repeats_total`).
    Headerless pieces continue the current run when their column count matches.
    """
    runs: list[tuple[str, list]] = []
    current: tuple[str, list[str]] | None = None  # (kind, paths) of the run being extended
    for p in pieces:
        if not p.rows:
            continue  # header-only boxes (page frames, free-text tables)
        if p.paths:
            kind, paths = kind_of(p.paths), p.paths
        elif current and len(p.rows[0][0]) == len(current[1]) and not _starts_total(p):
            kind, paths = current
        else:
            kind, paths = None, []
        if kind is None:
            current = None
            continue
        if current and current[0] == kind and not _is_grand_total(p):
            runs[-1][1].append((paths, p.rows))
        elif current and current[0] == kind and _repeats_total(p, runs[-1][1][0][1]):
            runs[-1][1].append((paths, p.rows[1:]))  # drop the repeated total row
        else:
            runs.append((kind, [(paths, p.rows)]))
        current = (kind, paths)
    best: dict[str, tuple[int, list]] = {}
    for kind, parts in runs:
        n = sum(len(rows) for _, rows in parts)
        if n > best.get(kind, (0, []))[0]:
            best[kind] = (n, parts)
    return {k: parts for k, (_, parts) in best.items()}


def level_of(name: str, area: bool) -> str:
    if "GRAND TOTAL" in name.upper():
        return "total"
    if not name:
        return "unknown"
    if UNMISTAKABLE_REGION.match(name):
        return "region"  # even without bold / span: some summary tables have neither
    if area:
        return "region" if REGION_NAME.match(name) else "province"
    return "town"


def _num(v: str) -> float | None:
    v = v.strip("()*%").replace(",", "")
    if not v:
        return None
    return 0.0 if set(v) == {"-"} else float(v)


def _cut_stray_copy(rows: list[tuple[str, str, list]]) -> list[tuple[str, str, list]]:
    """Some PDFs run a second, headerless copy of a table on from the first, with other numbers
    (Tino 2025 #3). Cut where a region name comes back with other numbers, but only when the
    regions before it already add up to the GRAND TOTAL; otherwise the rest is real rows."""
    total = next((r for r in rows if r[0] == "total"), None)
    if total is None or not total[2]:
        return rows
    col = total[2][0][0]

    def first(r: tuple) -> float | None:
        return next((_num(v) for p, v in r[2] if p == col), None)

    seen: dict[str, tuple] = {}
    for i, (level, name, values) in enumerate(rows):
        if level != "region":
            continue
        key = name.upper()
        if key in seen and seen[key] != tuple(values):
            regions = sum(first(r) or 0 for r in rows[:i] if r[0] == "region")
            target = first(total) or 0
            if abs(regions - target) <= max(1, 0.01 * abs(target)):
                return rows[:i]
            return rows
        seen[key] = tuple(values)
    return rows


def to_cells(sha: str, pieces: list[Piece]) -> tuple[dict[str, list], Counter]:
    """Bronze rows (column-wise) for the selected tables, plus counts per kind and dropped rows."""
    out: dict[str, list] = {c: [] for c in COLUMNS}
    counts: Counter = Counter()
    for kind, parts in select(pieces).items():
        kept: list[tuple[str, str, list]] = []
        seen: set[tuple] = set()  # 2018 combined tables repeat each region row above its block
        for paths, rows in parts:
            names = name_columns(paths)
            for cells, area in rows:
                name = next((cells[j] for j in names if j < len(cells) and cells[j]), "")
                values = [
                    (paths[j] if j < len(paths) else "", cells[j])
                    for j in range(len(cells))
                    if j not in names
                ]
                # "####": Excel's too-wide-to-show mark in DSWD's file; the number is missing
                values = [(p or "?", "" if HASHES.match(v) else v) for p, v in values if p or v]
                # value cells must be numbers: any text there is a note (names live in notes)
                if len(name) > MAX_NAME_LEN or any(v and not NUMBER.match(v) for _, v in values):
                    counts["dropped"] += 1
                    continue
                if not any(v for _, v in values):
                    continue  # blank rows and table notes ("Source: DSWD FOs") carry no numbers
                level = level_of(name, area)
                if level in ("total", "region"):
                    key = (level, name.upper(), tuple(v for _, v in values))
                    if key in seen:
                        continue
                    seen.add(key)
                kept.append((level, name, values))
        if kind != "combined":  # combined tables repeat region rows on purpose
            kept = _cut_stray_copy(kept)
        for row_no, (level, name, values) in enumerate(kept, 1):
            counts[kind] += 1
            for path, value in values:
                row = (sha, kind, row_no, level, name, path, value)
                for col, v in zip(COLUMNS, row, strict=True):
                    out[col].append(v)
    return out, counts


def read_file(path: Path) -> list[Piece]:
    """Pick the reader by the file's first bytes (some names were cut before the extension)."""
    with path.open("rb") as f:
        magic = f.read(4)
    if magic == b"%PDF":
        from sakuna.pdf_reader import read_pdf

        return read_pdf(path)
    if magic == b"PK\x03\x04":
        from sakuna.docx_reader import read_docx

        return read_docx(path)
    raise ValueError(f"not a PDF or .docx: {magic!r}")


def write_parquet(path: Path, cells: dict[str, list]) -> None:
    schema = pa.schema([(c, pa.int32() if c == "row_no" else pa.string()) for c in COLUMNS])
    tmp = path.with_suffix(".tmp")
    pq.write_table(pa.table(cells, schema=schema), tmp)
    os.replace(tmp, path)


def extract_one(sha: str, src: Path, dst: Path) -> dict:
    """Extract one file to `dst`. Never raises: a bad file is logged and the run goes on."""
    try:
        cells, counts = to_cells(sha, read_file(src))
        write_parquet(dst, cells)
    except Exception as e:  # noqa: BLE001 - one broken report must not stop the run
        return {"status": "failed", "error": f"{type(e).__name__}: {e}"[:300]}
    dropped = counts.pop("dropped", 0)
    return {
        "status": "ok" if counts else "empty",
        "rows": sum(counts.values()),
        "kinds": " ".join(f"{k}={n}" for k, n in sorted(counts.items())),
        "dropped": dropped,
    }


def is_preparedness(row: dict) -> bool:
    """Pre-landfall reports count pre-emptive evacuations, not impacts (Kurt, 2026-11-21)."""
    return "preparedness" in (row["label"] + row["local_path"]).lower()


def bronze_root(settings: Settings) -> Path:
    return settings.lake_root / "bronze"


def read_log(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as f:  # -sig: survives an Excel save
        return {r["sha256"]: r for r in csv.DictReader(f)}


def write_log(path: Path, log: dict[str, dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in LOG_FIELDS} for r in log.values())
    os.replace(tmp, path)


def extract(settings: Settings, force: bool = False, limit: int | None = None) -> Counter:
    """Extract every downloaded, non-preparedness file not yet done. Returns status counts."""
    out = bronze_root(settings)
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "_log.csv"
    log = read_log(log_path)
    todo: dict[str, dict] = {}
    for r in manifest.read(manifest.manifest_path(settings.raw_root)):
        if r["status"] == "ok" and not is_preparedness(r) and r["sha256"] not in todo:
            if force or log.get(r["sha256"], {}).get("status") not in ("ok", "empty"):
                todo[r["sha256"]] = r
    jobs = list(todo.values())[:limit]
    logger.info("%d files to extract", len(jobs))
    with ProcessPoolExecutor() as ex:
        futures = {
            ex.submit(
                extract_one,
                r["sha256"],
                settings.raw_root / r["local_path"],
                out / f"{r['sha256']}.parquet",
            ): r
            for r in jobs
        }
        for i, fut in enumerate(as_completed(futures), 1):
            r = futures[fut]
            log[r["sha256"]] = {
                "sha256": r["sha256"],
                "local_path": r["local_path"],
                **fut.result(),
            }
            if log[r["sha256"]]["status"] == "failed":
                logger.warning("failed %s: %s", r["local_path"], log[r["sha256"]]["error"])
            if i % 50 == 0:
                write_log(log_path, log)
                logger.info("%d / %d done", i, len(jobs))
    write_log(log_path, log)
    return Counter(r["status"] for r in log.values())
