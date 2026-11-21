"""Retry behaviour of the polite fetcher (no network)."""

import io
import urllib.error

import pytest

from sakuna import fetch
from sakuna.settings import load_settings


def test_retries_then_gives_up(monkeypatch):
    calls, waits = [], []

    def urlopen(req, timeout):
        calls.append(timeout)
        raise urllib.error.URLError("down")

    monkeypatch.setattr(fetch.urllib.request, "urlopen", urlopen)
    with pytest.raises(OSError):
        fetch.get("https://example.invalid/", load_settings(), sleep=waits.append)
    assert len(calls) == 4 and waits == [2, 4, 8]  # 3 retries, back-off


def test_non_ascii_url_is_encoded(monkeypatch):
    sent = []

    def urlopen(req, timeout):
        sent.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO())

    monkeypatch.setattr(fetch.urllib.request, "urlopen", urlopen)
    fetch.get("https://x.invalid/a/Report “Ompong” 1%20x.pdf?q=1", load_settings(), sleep=None)
    assert sent == ["https://x.invalid/a/Report%20%E2%80%9COmpong%E2%80%9D%201%20x.pdf?q=1"]


def test_404_is_not_retried(monkeypatch):
    def urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, io.BytesIO())

    monkeypatch.setattr(fetch.urllib.request, "urlopen", urlopen)
    assert fetch.get("https://example.invalid/", load_settings(), sleep=None).status == 404
