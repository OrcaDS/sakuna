"""Polite HTTP GET: our User-Agent, a timeout, retries with back-off (project.md §5.1)."""

from __future__ import annotations

import http.client
import logging
import string
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from sakuna.settings import Settings

logger = logging.getLogger(__name__)
RETRY_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    content_type: str


def get(url: str, settings: Settings, sleep=time.sleep) -> Response:
    """GET a URL. Retries network errors and 429/5xx; other HTTP errors return their status.

    Raises OSError (or http.client.HTTPException) once the retries run out.
    """
    # Percent-encode non-ASCII and spaces only (DROMIC file names contain curly quotes).
    url = urllib.parse.quote(url, safe=string.punctuation)
    req = urllib.request.Request(url, headers={"User-Agent": settings.http_user_agent})
    for attempt in range(settings.request_retries + 1):
        last = attempt == settings.request_retries
        try:
            with urllib.request.urlopen(req, timeout=settings.request_timeout_seconds) as r:
                return Response(r.status, r.read(), r.headers.get_content_type())
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUSES or last:
                return Response(e.code, b"", "")
            reason = f"HTTP {e.code}"
        except (OSError, http.client.HTTPException) as e:
            if last:
                raise
            reason = repr(e)
        wait = 2 ** (attempt + 1)
        logger.warning("retry %d in %ds (%s): %s", attempt + 1, wait, reason, url)
        sleep(wait)
    raise AssertionError("unreachable")
