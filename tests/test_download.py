"""Manifest merge and the download loop, with a fake fetcher (no network)."""

import pytest

from sakuna import download, manifest
from sakuna.fetch import Response
from sakuna.settings import load_settings

SITE = "https://dromic.dswd.gov.ph/wp-content/uploads/2024/01/Report-1%20x.pdf"
DOC = "https://docs.google.com/document/d/ID1/export?format=docx"


def found(file_url, download_url):
    return {
        "event_url": "https://dromic.dswd.gov.ph/typhoon-x-01-jan-2024/",
        "event_title": "T",
        "event_year": 2024,
        "file_url": file_url,
        "download_url": download_url,
        "label": "L",
        "report_no": "1",
        "report_date": "",
    }


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_ROOT", str(tmp_path))
    monkeypatch.setattr(download, "GOOGLE_DELAY_SECONDS", 0)
    s = load_settings()
    rows = []
    manifest.merge(
        rows,
        [
            found(SITE, SITE),
            found("https://docs.google.com/document/d/ID1", DOC),
            found("https://docs.google.com/file/d/ID2", ""),
        ],
        "t0",
    )
    manifest.write(manifest.manifest_path(s.raw_root), rows)
    return s


def test_merge_adds_only_new(settings):
    rows = manifest.read(manifest.manifest_path(settings.raw_root))
    assert [r["status"] for r in rows] == ["pending", "pending", "manual"]
    assert manifest.merge(rows, [found(SITE, SITE)], "t1") == 0


def fake(bodies):
    def get(url, settings):
        return Response(200, bodies[url], "application/pdf")

    return get


def test_download_then_refresh_keeps_old_version(settings, monkeypatch):
    bodies = {SITE: b"%PDF-1 v1", DOC: b"<html>sign in</html>"}
    monkeypatch.setattr(download, "get", fake(bodies))
    assert download.download(settings) == {"ok": 1, "failed": 1, "manual": 1}

    rows = manifest.read(manifest.manifest_path(settings.raw_root))
    ok = rows[0]
    assert ok["local_path"].startswith("typhoon-x-01-jan-2024/")
    assert ok["local_path"].endswith("-Report-1_x.pdf")
    assert (settings.raw_root / ok["local_path"]).read_bytes() == b"%PDF-1 v1"
    assert rows[1]["error"].startswith("not a document")

    bodies[SITE] = b"%PDF-1 v2"  # DSWD revised the file
    bodies[DOC] = b"PK\x03\x04docx"
    download.download(settings, refresh=True)
    rows = manifest.read(manifest.manifest_path(settings.raw_root))
    assert len(rows) == 4  # old version row kept, revision appended
    assert rows[0]["sha256"] != rows[3]["sha256"]
    assert (settings.raw_root / rows[0]["local_path"]).exists()
    assert rows[1]["status"] == "ok" and rows[1]["local_path"].endswith("-ID1.docx")


def test_network_failure_is_recorded(settings, monkeypatch):
    def boom(url, settings):
        raise TimeoutError("timed out")

    monkeypatch.setattr(download, "get", boom)
    assert download.download(settings, limit=1) == {"failed": 1, "pending": 1, "manual": 1}
