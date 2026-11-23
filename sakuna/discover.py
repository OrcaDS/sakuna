"""Discover typhoon/monsoon events and their report files on DROMIC.

Reads only post titles, link URLs and link text. Never the post body text.
"""

from __future__ import annotations

import html
import logging
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

from sakuna.fetch import get
from sakuna.settings import Settings

logger = logging.getLogger(__name__)

FIRST_YEAR = 2017
TITLE_KEEP = re.compile(
    r"Typhoon|Tropical Storm|Tropical Depression|Southwest Monsoon|Habagat", re.I
)
TITLE_DROP = re.compile(r"Intertropical", re.I)
LISTING_ITEM = re.compile(r'<h2 class="post-title"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
NEXT_PAGE = 'class="next page-link"'
LINK = re.compile(r'<a\s[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
TAG = re.compile(r"<[^>]+>")
SITE_FILE = re.compile(
    r"^https?://dromic\.dswd\.gov\.ph/wp-content/uploads/[^?#\"]+\.(?:pdf|docx?|xlsx?)$", re.I
)
GOOGLE = re.compile(
    r"^https?://(?:docs|drive)\.google\.com/(?:a/[^/]+/)?(document|file)/d/([\w-]+)"
)
MONTH = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
DATE = re.compile(r"\b(\d{1,2})[\s-]+" + MONTH + r"[\s,-]+(\d{4})\b", re.I)
REPORT_NO = re.compile(r"Report\W{0,3}(?:No\W{0,2})?(\d+)\b(?![\s-]+" + MONTH + ")", re.I)


def clean(text: str) -> str:
    return " ".join(html.unescape(TAG.sub(" ", text)).split())


def last_date(text: str) -> date | None:
    """The last 'DD Month YYYY' in a text, or None."""
    for d, mon, y in reversed(DATE.findall(text)):
        try:
            return datetime.strptime(f"{d} {mon[:3]} {y}", "%d %b %Y").date()
        except ValueError:
            continue
    return None


def is_event(title: str) -> bool:
    return bool(TITLE_KEEP.search(title)) and not TITLE_DROP.search(title)


def parse_listing(page: str) -> tuple[list[tuple[str, str]], bool]:
    """(post url, title) pairs on one category page, and whether a next page exists."""
    items = [(url, clean(title)) for url, title in LISTING_ITEM.findall(page)]
    return items, NEXT_PAGE in page


def label_fields(label: str) -> dict:
    """Report number and 'as of' date, best effort from a file label. Unknown stays empty."""
    low = label.lower()
    m = REPORT_NO.search(label)
    report_no = (
        m.group(1) if m else "terminal" if "terminal" in low else "final" if "final" in low else ""
    )
    d = last_date(label)
    return {"report_no": report_no, "report_date": d.isoformat() if d else ""}


def parse_post(page: str) -> list[dict]:
    """Report files linked from one event post, in page order, without duplicates."""
    files, seen = [], set()
    for href, text in LINK.findall(page):
        url = html.unescape(href).strip()
        if url.startswith("https://docs.google.com/viewer?"):  # 2021 posts wrap DROMIC files
            url = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("url", [""])[0]
        if SITE_FILE.match(url):
            label = urllib.parse.unquote(url.rsplit("/", 1)[1])
            download_url = url
        elif m := GOOGLE.match(url):
            kind, doc_id = m.groups()
            label = clean(text)
            # Drive file downloads (/uc, drive.usercontent) are disallowed by robots.txt: manual.
            download_url = (
                f"https://docs.google.com/document/d/{doc_id}/export?format=docx"
                if kind == "document"
                else ""
            )
            url = f"https://docs.google.com/{kind}/d/{doc_id}"  # one form per document
        else:
            continue
        if url in seen:
            continue
        seen.add(url)
        files.append({"file_url": url, "download_url": download_url, "label": label})
        files[-1].update(label_fields(label))
    return files


def _fetch_text(url: str, settings: Settings) -> str:
    r = get(url, settings)
    if r.status != 200:
        raise RuntimeError(f"HTTP {r.status} for {url}")
    return r.body.decode("utf-8", "replace")


def list_year(year: int, settings: Settings) -> list[tuple[str, str, int]]:
    """Every (url, title, category year) in one year's Situation Reports category."""
    out, page = [], 1
    while True:
        url = f"{settings.dromic_base_url}/category/situation-reports/{year}/"
        items, more = parse_listing(
            _fetch_text(url + (f"page/{page}/" if page > 1 else ""), settings)
        )
        out += [(u, t, year) for u, t in items]
        if not more or not items:
            return out
        page += 1


def discover(settings: Settings, years: list[int]) -> list[dict]:
    """Manifest rows (without download fields) for every in-scope event's report files."""
    with ThreadPoolExecutor(settings.max_parallel_requests) as pool:
        listed = [
            p
            for year_posts in pool.map(lambda y: list_year(y, settings), years)
            for p in year_posts
        ]
        events = {}
        for url, title, cat_year in listed:  # a post can sit in several year categories
            d = last_date(title)
            year = d.year if d else cat_year
            if is_event(title) and year >= FIRST_YEAR and url not in events:
                events[url] = (title, year)
        logger.info("%d posts listed, %d in-scope events", len(listed), len(events))
        pages = pool.map(lambda u: _fetch_text(u, settings), events)
        rows = []
        for (url, (title, year)), page in zip(events.items(), pages, strict=True):
            files = parse_post(page)
            if not files:
                logger.warning("no report files found: %s", url)
            rows += [
                {"event_url": url, "event_title": title, "event_year": year, **f} for f in files
            ]
    return rows
