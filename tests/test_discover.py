"""Discovery parsing, on small synthetic snippets shaped like DROMIC pages (no names)."""

import pytest

from sakuna.discover import is_event, label_fields, last_date, parse_listing, parse_post

LISTING = """
<h2 class="post-title" itemprop="name"><a href="https://dromic.dswd.gov.ph/a/" rel="bookmark">
Severe Tropical Storm &#8220;Vinta&#8221; [20 Dec 2017]</a></h2>
<h2 class="post-title" itemprop="name"><a href="https://dromic.dswd.gov.ph/b/" rel="bookmark">Fire Incident [05 Dec 2017]</a></h2>
<a class="next page-link" href="https://dromic.dswd.gov.ph/category/situation-reports/2017/page/2/">Next</a>
"""

POST = """
<a href="https://www.dswd.gov.ph/issuances/AOs/AO_2023-017.pdf" class="dropdown-item">AO</a>
<a href="https://dromic.dswd.gov.ph/wp-content/uploads/2024/01/DSWD-DROMIC-Report-26-on-Typhoon-Marce-as-of-15-January-2025-6PM.pdf" class="ead-document-btn">Download</a>
<a href="https://dromic.dswd.gov.ph/wp-content/uploads/2024/01/DSWD-DROMIC-Report-26-on-Typhoon-Marce-as-of-15-January-2025-6PM.pdf">Download</a>
<a href="https://docs.google.com/a/icab.gov.ph/document/d/1AbC-d_9/edit?usp=drivesdk"><span>DSWD DROMIC Report #32 on Severe Tropical Storm VINTA as of 20 March 2018, 7PM.docx</span></a>
<a href="https://docs.google.com/a/dswd.gov.ph/file/d/0B8xyz/view">Terminal Report on TS X.pdf</a>
<a href="https://dromic.dswd.gov.ph/wp-content/uploads/2024/01/photo.jpg">photo</a>
<a href="https://docs.google.com/viewer?url=https%3A%2F%2Fdromic.dswd.gov.ph%2Fwp-content%2Fuploads%2F2021%2F09%2FTerminal-Report-17-September-2021.docx&#038;hl=en">View</a>
"""


def test_parse_listing():
    items, more = parse_listing(LISTING)
    assert items == [
        ("https://dromic.dswd.gov.ph/a/", "Severe Tropical Storm “Vinta” [20 Dec 2017]"),
        ("https://dromic.dswd.gov.ph/b/", "Fire Incident [05 Dec 2017]"),
    ]
    assert more
    assert parse_listing("<p>empty</p>") == ([], False)


@pytest.mark.parametrize(
    ("title", "keep"),
    [
        ("Typhoon “Marce” [04 Nov 2024][Terminated]", True),
        ("Effects of Southwest Monsoon [12 Jul 2024]", True),
        ("Effects of Habagat [01 Aug 2018]", True),
        ("Flooding due to Intertropical Convergence Zone [01 Jan 2019]", False),
        ("Fire Incident [05 Dec 2017]", False),
    ],
)
def test_is_event(title, keep):
    assert is_event(title) is keep


def test_parse_post():
    files = parse_post(POST)
    assert [f["file_url"] for f in files] == [
        "https://dromic.dswd.gov.ph/wp-content/uploads/2024/01/DSWD-DROMIC-Report-26-on-Typhoon-Marce-as-of-15-January-2025-6PM.pdf",
        "https://docs.google.com/document/d/1AbC-d_9",
        "https://docs.google.com/file/d/0B8xyz",
        "https://dromic.dswd.gov.ph/wp-content/uploads/2021/09/Terminal-Report-17-September-2021.docx",
    ]
    site, doc, drive, viewer = files
    assert viewer["download_url"] == viewer["file_url"]
    assert (viewer["report_no"], viewer["report_date"]) == ("terminal", "2021-09-17")
    assert (site["report_no"], site["report_date"]) == ("26", "2025-01-15")
    assert doc["download_url"] == "https://docs.google.com/document/d/1AbC-d_9/export?format=docx"
    assert (doc["report_no"], doc["report_date"]) == ("32", "2018-03-20")
    assert drive["download_url"] == ""  # robots.txt blocks Drive downloads: manual
    assert drive["report_no"] == "terminal"


def test_label_fields_unknown_stays_empty():
    assert label_fields("Annex.pdf") == {"report_no": "", "report_date": ""}


def test_last_date():
    assert str(last_date("Typhoon Nina [23 Dec 2016] as of 05 Jan 2017")) == "2017-01-05"
    assert last_date("no date 31 Feb 2017") is None
