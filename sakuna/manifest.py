"""The manifest: one CSV row per report file (and per changed version). Rows are never deleted."""

from __future__ import annotations

import csv
import os
from pathlib import Path

FIELDS = [
    "event_url",
    "event_title",
    "event_year",
    "file_url",
    "download_url",
    "label",
    "report_no",
    "report_date",
    "status",  # pending | ok | failed | manual (robots.txt blocks scripts: Kurt downloads by hand)
    "http_status",
    "error",
    "sha256",
    "bytes",
    "local_path",
    "first_seen",
    "last_checked",
]


def manifest_path(raw_root: Path) -> Path:
    return raw_root / "manifest.csv"


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path: Path, rows: list[dict]) -> None:
    """Write via a temp file so a crash never leaves a half-written manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows({k: row.get(k, "") for k in FIELDS} for row in rows)
    os.replace(tmp, path)


def merge(rows: list[dict], found: list[dict], now: str) -> int:
    """Append discovered files not yet in the manifest (keyed by event + file). Returns count."""
    seen = {(r["event_url"], r["file_url"]) for r in rows}
    added = 0
    for f in found:
        key = (f["event_url"], f["file_url"])
        if key in seen:
            continue
        seen.add(key)
        status = "pending" if f["download_url"] else "manual"
        rows.append({**f, "status": status, "first_seen": now})
        added += 1
    return added
