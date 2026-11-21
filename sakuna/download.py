"""Download report files listed in the manifest into RAW_ROOT (local only, never committed)."""

from __future__ import annotations

import hashlib
import logging
import re
import time
import urllib.parse
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from sakuna import manifest
from sakuna.fetch import get
from sakuna.settings import Settings

logger = logging.getLogger(__name__)
MAGIC = {b"%PDF": ".pdf", b"PK\x03\x04": ".docx", b"\xd0\xcf\x11\xe0": ".doc"}
GOOGLE_DELAY_SECONDS = 1  # Crawl-delay in docs.google.com/robots.txt
SAVE_EVERY = 50


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def safe_name(text: str) -> str:
    return re.sub(r"[^\w.-]+", "_", text).strip("._")[:150] or "file"


def sniff(body: bytes) -> str | None:
    """File extension implied by the first bytes, or None if it isn't a document (e.g. HTML)."""
    return next((ext for magic, ext in MAGIC.items() if body.startswith(magic)), None)


def target_path(raw_root: Path, row: dict, body: bytes, sha: str) -> Path:
    """raw/<event slug>/<hash prefix>-<file name>: each changed version gets its own file."""
    event = safe_name(urllib.parse.urlparse(row["event_url"]).path.strip("/"))
    name = urllib.parse.unquote(row["download_url"].split("?")[0].rsplit("/", 1)[1])
    if "google.com" in row["download_url"]:
        name = row["file_url"].rsplit("/", 1)[1] + (sniff(body) or "")
    return raw_root / event / f"{sha[:12]}-{safe_name(name)}"


def fetch_one(row: dict, settings: Settings) -> dict:
    """Download one row's file. Returns the fields to update; never raises."""
    result = {"last_checked": now()}
    try:
        r = get(row["download_url"], settings)
    except Exception as e:  # network gave up after retries: record it, keep going
        return {**result, "status": "failed", "http_status": "", "error": repr(e)[:200]}
    result["http_status"] = str(r.status)
    if r.status != 200:
        return {**result, "status": "failed", "error": f"HTTP {r.status}"}
    if not sniff(r.body):  # dead Google links serve an HTML sign-in page with status 200
        return {**result, "status": "failed", "error": f"not a document ({r.content_type})"}
    sha = hashlib.sha256(r.body).hexdigest()
    path = target_path(settings.raw_root, row, r.body, sha)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.body)
    rel = path.relative_to(settings.raw_root).as_posix()
    return {
        **result,
        "status": "ok",
        "error": "",
        "sha256": sha,
        "bytes": str(len(r.body)),
        "local_path": rel,
    }


def apply(rows: list[dict], i: int, update: dict) -> None:
    """Record a result. A refreshed file with a new hash becomes a new row; old rows stay."""
    row = rows[i]
    if row["status"] != "ok":
        row.update(update)
    elif update["status"] == "ok" and update["sha256"] != row["sha256"]:
        rows.append({**row, **update, "first_seen": update["last_checked"]})
        logger.info("revised: %s", row["file_url"])
    else:  # unchanged, or a failed refresh: the file we have is still good
        row["last_checked"] = update["last_checked"]


def download(
    settings: Settings,
    refresh: bool = False,
    limit: int | None = None,
    fetch: Callable[[dict, Settings], dict] = fetch_one,
) -> dict[str, int]:
    """Fetch pending/failed files (and, with refresh, re-check ok ones). Returns status counts."""
    path = manifest.manifest_path(settings.raw_root)
    rows = manifest.read(path)
    wanted = {"pending", "failed"} | ({"ok"} if refresh else set())
    latest = {}  # refresh only the newest version of each file
    for i, r in enumerate(rows):
        latest[(r["event_url"], r["file_url"])] = i
    todo = [i for i in latest.values() if rows[i]["status"] in wanted][:limit]
    google = [i for i in todo if "google.com" in rows[i]["download_url"]]
    site = [i for i in todo if "google.com" not in rows[i]["download_url"]]
    logger.info("downloading %d files (%d DROMIC, %d Google)", len(todo), len(site), len(google))

    done = 0

    def record(i: int, update: dict) -> None:
        nonlocal done
        apply(rows, i, update)
        done += 1
        if update["status"] != "ok":
            logger.warning("%s: %s", update.get("error"), rows[i]["download_url"])
        if done % SAVE_EVERY == 0:
            manifest.write(path, rows)
            logger.info("%d/%d done", done, len(todo))

    try:
        with ThreadPoolExecutor(settings.max_parallel_requests) as pool:
            futures = {pool.submit(fetch, rows[i], settings): i for i in site}
            for fut in as_completed(futures):
                record(futures[fut], fut.result())
        for n, i in enumerate(google):  # one at a time, honouring Google's crawl delay
            if n:
                time.sleep(GOOGLE_DELAY_SECONDS)
            record(i, fetch(rows[i], settings))
    finally:
        manifest.write(path, rows)

    counts: dict[str, int] = {}
    for i in latest.values():
        counts[rows[i]["status"]] = counts.get(rows[i]["status"], 0) + 1
    return counts
