"""Extract → bronze, on tiny reports built here (made-up places, no names of people)."""

import csv
import zipfile
from pathlib import Path

import pyarrow.parquet as pq

from sakuna import extract
from sakuna.extract import Piece, header_paths, kind_of, level_of, name_columns, select, to_cells
from sakuna.settings import load_settings

NOTE = "Prepared by Juana Example"  # free text that must never reach bronze

# ---- tiny .docx builder ---------------------------------------------------------------

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _tc(text: str, span: int = 1, bold: bool = False) -> str:
    pr = f'<w:tcPr><w:gridSpan w:val="{span}"/></w:tcPr>' if span > 1 else ""
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:tc>{pr}<w:p><w:r>{rpr}<w:t>{text}</w:t></w:r></w:p></w:tc>"


def _tbl(rows: list[list[tuple]]) -> str:
    return (
        "<w:tbl>"
        + "".join("<w:tr>" + "".join(_tc(*c) for c in r) + "</w:tr>" for r in rows)
        + "</w:tbl>"
    )


AFFECTED_HEAD = [
    [("REGION / PROVINCE / MUNICIPALITY", 2), ("NUMBER OF AFFECTED", 2)],
    [("", 2), ("Families",), ("Persons",)],
]
SUMMARY = AFFECTED_HEAD + [[("GRAND TOTAL", 2), ("30",), ("120",)]]
ANNEX = AFFECTED_HEAD + [
    [("GRAND TOTAL", 2), ("30",), ("120",)],
    [("REGION I", 2, True), ("30",), ("120",)],
    [("Provincia", 2, True), ("30",), ("120",)],
    [("",), ("Townville",), ("20",), ("1,000",)],
    [("",), ("Villa Dos",), ("10",), ("-",)],
]
FREE_TEXT = [[("DATE",), ("SITUATION",)], [("10 January 2017",), (NOTE,)]]


def make_docx(path: Path, tables: list[str]) -> Path:
    body = f"<w:p><w:r><w:t>{NOTE}</w:t></w:r></w:p>" + "".join(tables)
    xml = f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)
    return path


# ---- tiny PDF builder: ruled cells, Helvetica / Helvetica-Bold ------------------------


def _page_ops(cells: list[tuple], col_w: int = 90, row_h: int = 16) -> str:
    """cells: (row, col, colspan, rowspan, text, bold)."""
    ops = [f"BT /F1 8 Tf 40 770 Td ({NOTE}) Tj ET"]
    for r, c, cs, rs, text, bold in cells:
        x, y = 40 + c * col_w, 740 - (r + rs) * row_h
        ops.append(f"{x} {y} {cs * col_w} {rs * row_h} re S")
        if text:
            ops.append(f"BT /{'F2' if bold else 'F1'} 8 Tf {x + 3} {y + 5} Td ({text}) Tj ET")
    return "\n".join(ops)


def make_pdf(path: Path, pages: list[list[tuple]]) -> Path:
    n = len(pages)
    kids = " ".join(f"{5 + 2 * i} 0 R" for i in range(n))
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    for i, cells in enumerate(pages):
        stream = _page_ops(cells).encode()
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {6 + 2 * i} 0 R >>".encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(out)
    return path


PDF_HEAD = [
    (0, 0, 1, 2, "REGION / PROVINCE", False),  # must fit its cell: the fixture doesn't wrap
    (0, 1, 2, 1, "NUMBER OF AFFECTED", False),
    (1, 1, 1, 1, "Families", False),
    (1, 2, 1, 1, "Persons", False),
]


def _pdf_rows(start: int, rows: list[tuple]) -> list[tuple]:
    cells = []
    for i, (name, bold, *values) in enumerate(rows):
        cells.append((start + i, 0, 1, 1, name, bold))
        cells += [(start + i, 1 + j, 1, 1, v, False) for j, v in enumerate(values)]
    return cells


PDF_PAGE1 = PDF_HEAD + _pdf_rows(
    2,
    [
        ("GRAND TOTAL", True, "30", "120"),
        ("REGION I", True, "30", "120"),
        ("Provincia", True, "30", "120"),
        ("Townville", False, "20", "1,000"),
    ],
)
PDF_PAGE2 = PDF_HEAD + _pdf_rows(2, [("Villa Dos", False, "10", "-")])


def rows_of(cells: dict) -> list[tuple]:
    return list(zip(*(cells[c] for c in extract.COLUMNS), strict=True))


# ---- shared logic ---------------------------------------------------------------------


def test_header_paths_join_rows_per_column():
    grid = [["REGION", "NUMBER OF AFFECTED", "NUMBER OF AFFECTED"], ["", "Families", "Persons"]]
    assert header_paths(grid) == [
        "REGION",
        "NUMBER OF AFFECTED > Families",
        "NUMBER OF AFFECTED > Persons",
    ]


def test_kind_of_matches_keywords_and_needs_a_region_column():
    assert kind_of(["REGION / PROVINCE", "NO. OF DAMAGED HOUSES > Total"]) == "houses"
    assert (
        kind_of(["REGION / PROVINCE", "INSIDE ECs > Families", "OUTSIDE ECs > Families"])
        == "displaced"
    )
    assert kind_of(["REGION / PROVINCE", "NUMBER OF DISPLACED > OUTSIDE ECs"]) == "outside_ec"
    assert kind_of(["REGION / PROVINCE", "NO. OF DAMAGE HOUSES > Total"]) == "houses"
    assert kind_of(["OFFICE", "STANDBY FUNDS"]) is None
    assert kind_of(["DATE", "NUMBER OF AFFECTED"]) is None  # no place column: free-text table


def test_name_columns_include_unlabelled_split_column():
    assert name_columns(["REGION / PROVINCE", "", "NUMBER OF AFFECTED > Families"]) == [0, 1]


def test_level_of():
    assert level_of("GRAND TOTAL", True) == "total"
    assert level_of("REGION VI", True) == "region"
    assert level_of("NCR", True) == "region"
    assert level_of("NIR", True) == "region"
    assert level_of("NIR 6", True) == "province"  # 2025 sub-total under NIR
    assert level_of("Aklan", True) == "province"
    assert level_of("Kalibo", False) == "town"


def test_select_keeps_longest_run_and_stitches_pages():
    paths = ["REGION", "NUMBER OF AFFECTED > Families"]
    summary = Piece(paths, [(["GRAND TOTAL", "30"], True)])
    annex1 = Piece(paths, [(["GRAND TOTAL", "30"], True), (["Townville", "20"], False)])
    frame = Piece(["Annex A text"], [])  # a page box with no number rows
    annex2 = Piece(paths, [(["Villa Dos", "10"], False)])  # header repeated on the next page
    annex3 = Piece([], [(["Villa Tres", "0"], False)])  # header missing on the next page
    out = select([summary, annex1, frame, annex2, annex3])
    assert [len(rows) for _, rows in out["affected"]] == [2, 1, 1]


def test_select_headerless_total_table_does_not_continue():
    paths = ["REGION", "COST OF ASSISTANCE > DSWD"]
    cost = Piece(paths, [(["GRAND TOTAL", "30"], True), (["Townville", "30"], False)])
    standby = Piece([], [(["TOTAL", "500"], False), (["DSWD CO", "400"], False)])
    out = select([cost, standby])
    assert [len(rows) for _, rows in out["cost"]] == [2]


def test_to_cells_cuts_stray_copy_only_when_regions_match_the_total():
    paths = ["REGION", "OUTSIDE ECs > Families"]

    def rows(*names_values):
        return [([n, v], n.isupper()) for n, v in names_values]

    stray = Piece(
        paths,
        rows(("GRAND TOTAL", "30"), ("REGION I", "10"), ("REGION II", "20"), ("Town", "20"))
        + rows(("REGION I", "99"), ("Town B", "99")),
    )
    cells, counts = to_cells("x", [stray])
    assert counts["outside_ec"] == 4
    # regions before the repeat (10) do not reach the total (109): the rest is real
    real = Piece(
        paths,
        rows(("GRAND TOTAL", "109"), ("REGION I", "10"), ("REGION I", "99"), ("Town B", "99")),
    )
    cells, counts = to_cells("x", [real])
    assert counts["outside_ec"] == 4


def test_select_stitches_pages_that_repeat_the_grand_total():
    paths = ["REGION", "NUMBER OF AFFECTED > Families"]
    total, region = (["GRAND TOTAL", "30"], True), (["REGION I", "30"], True)
    summary = Piece(paths, [total, region])
    page1 = Piece(paths, [total, region, (["Townville", "20"], False)])
    page2 = Piece(paths, [total, (["Villa Dos", "10"], False)])  # total repeated, new town
    out = select([summary, page1, page2])
    assert [len(rows) for _, rows in out["affected"]] == [3, 1]  # page1 is a fresh copy


def test_to_cells_drops_long_free_text_and_note_rows():
    paths = ["REGION", "NUMBER OF AFFECTED > Families", "NUMBER OF AFFECTED > Persons"]
    piece = Piece(
        paths,
        [
            (["GRAND TOTAL", "30", "90"], True),
            (["Townville", "20", "60"], False),
            (["Source: DSWD FOs", "", ""], False),
            (["Townville", "x" * 50, ""], False),
            (["Note: affected in", "Villa Dos;", ""], False),  # a note over the columns
            (["Villa Tres", "#######", "30"], False),  # Excel overflow: kept, value missing
        ],
    )
    cells, counts = to_cells("abc", [piece])
    assert [(r[4], r[6]) for r in rows_of(cells) if r[5].endswith("Families")] == [
        ("GRAND TOTAL", "30"),
        ("Townville", "20"),
        ("Villa Tres", ""),
    ]
    assert counts == {"affected": 3, "dropped": 2}


# ---- readers end to end ---------------------------------------------------------------


def check_affected(cells: dict) -> None:
    rows = rows_of(cells)
    got = {(r[3], r[4], r[5]): r[6] for r in rows}
    assert got[("total", "GRAND TOTAL", "NUMBER OF AFFECTED > Families")] == "30"
    assert got[("region", "REGION I", "NUMBER OF AFFECTED > Persons")] == "120"
    assert got[("province", "Provincia", "NUMBER OF AFFECTED > Families")] == "30"
    assert got[("town", "Townville", "NUMBER OF AFFECTED > Persons")] == "1,000"
    assert got[("town", "Villa Dos", "NUMBER OF AFFECTED > Persons")] == "-"  # kept as read
    assert {r[1] for r in rows} == {"affected"}
    assert [r[2] for r in rows] == sorted(r[2] for r in rows)  # row order kept for the hierarchy
    assert not any(NOTE in str(v) for r in rows for v in r)


def test_docx_reader(tmp_path):
    f = make_docx(tmp_path / "r.docx", [_tbl(SUMMARY), _tbl(ANNEX), _tbl(FREE_TEXT)])
    cells, counts = to_cells("abc", extract.read_file(f))
    check_affected(cells)
    assert counts == {"affected": 5}


def test_pdf_reader_stitches_pages(tmp_path):
    f = make_pdf(tmp_path / "r.pdf", [PDF_PAGE1, PDF_PAGE2])
    cells, counts = to_cells("abc", extract.read_file(f))
    check_affected(cells)
    assert counts == {"affected": 5}


def test_pdf_reader_continuation_page_wider_on_the_left(tmp_path):
    # Agaton 2022 #46: a continuation page adds an empty strip left of the name column.
    # It (and every page after it) used to be dropped for not matching the column count.
    def shift(cells):
        return [(r, c + 1, cs, rs, t, b) for r, c, cs, rs, t, b in cells]

    wide = [(r, 0, 1, 1, "", False) for r in range(3)] + shift(
        _pdf_rows(0, [("Villa Dos", False, "5", "-"), ("Villa Tres", False, "5", "-")])
    )
    wide += [(3, 0, 1, 1, "", False)] + shift(_pdf_rows(3, [("Villa Cuatro", False, "0", "-")]))
    last = shift(_pdf_rows(0, [("Villa Cinco", False, "0", "-")]))
    f = make_pdf(tmp_path / "r.pdf", [shift(PDF_PAGE1), wide, last])
    cells, counts = to_cells("abc", extract.read_file(f))
    assert counts == {"affected": 8}
    names = [r[4] for r in rows_of(cells) if r[5] == "NUMBER OF AFFECTED > Families"]
    assert names[-4:] == ["Villa Dos", "Villa Tres", "Villa Cuatro", "Villa Cinco"]


def test_extract_run_skips_preparedness_and_logs(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    (raw / "ev").mkdir(parents=True)
    make_docx(raw / "ev" / "a-report", [_tbl(ANNEX)])  # no extension: read by first bytes
    make_docx(raw / "ev" / "b.docx", [_tbl(ANNEX)])
    (raw / "ev" / "c.docx").write_bytes(b"PK\x03\x04 broken")
    with (raw / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["status", "sha256", "label", "local_path"])
        w.writeheader()
        w.writerow(
            {"status": "ok", "sha256": "a1", "label": "Report #1", "local_path": "ev/a-report"}
        )
        w.writerow(
            {
                "status": "ok",
                "sha256": "b2",
                "label": "Preparedness Report #1",
                "local_path": "ev/b.docx",
            }
        )
        w.writerow(
            {"status": "ok", "sha256": "c3", "label": "Report #2", "local_path": "ev/c.docx"}
        )
        w.writerow({"status": "failed", "sha256": "", "label": "Report #3", "local_path": ""})
    monkeypatch.setenv("RAW_ROOT", str(raw))
    monkeypatch.setenv("LAKE_ROOT", str(tmp_path / "lake"))
    settings = load_settings()

    assert extract.extract(settings) == {"ok": 1, "failed": 1}
    bronze = extract.bronze_root(settings)
    assert pq.read_table(bronze / "a1.parquet").num_rows == 10  # 5 rows x 2 columns
    assert not (bronze / "b2.parquet").exists()
    log = extract.read_log(bronze / "_log.csv")
    assert log["a1"]["kinds"] == "affected=5"
    assert log["c3"]["status"] == "failed"
    assert extract.extract(settings) == {"ok": 1, "failed": 1}  # done files are not redone


def test_kind_of_combined_table():
    paths = ["REGION / PROVINCE", "NUMBER OF AFFECTED > Families", "NO. OF DAMAGED HOUSES > Total"]
    assert kind_of(paths) == "combined"


def test_unmistakable_region_without_bold_or_span():
    assert level_of("REGION MIMAROPA", False) == "region"
    assert level_of("ARMM", False) == "region"
    assert level_of("Caraga", False) == "town"  # also a town in Davao Oriental


def test_repeated_region_rows_are_kept_once():
    summary = Piece(
        ["REGION", "NUMBER OF AFFECTED > Families"],
        [(["GRAND TOTAL", "30"], True), (["REGION I", "30"], True)],
    )
    block = Piece(  # same table continues: one block per region, region row repeated
        ["REGION", "", "NUMBER OF AFFECTED > Families"],
        [(["REGION I", "", "30"], True), (["", "Townville", "30"], False)],
    )
    cells, counts = to_cells("abc", [summary, block])
    assert [(r[3], r[4]) for r in rows_of(cells)] == [
        ("total", "GRAND TOTAL"),
        ("region", "REGION I"),
        ("town", "Townville"),
    ]


def test_pdf_reader_split_name_column(tmp_path):
    # Some pages put an empty narrow cell before the name: level must come from the name cell.
    head = [
        (0, 0, 1, 2, "REGION / PROVINCE", False),
        (0, 1, 1, 2, "", False),
        (0, 2, 2, 1, "NUMBER OF AFFECTED", False),
        (1, 2, 1, 1, "Families", False),
        (1, 3, 1, 1, "Persons", False),
    ]
    body = []
    rows = [("GRAND TOTAL", True), ("REGION I", True), ("Provincia", True), ("Townville", False)]
    for i, (name, bold) in enumerate(rows, 2):
        body += [(i, 0, 1, 1, "", False), (i, 1, 1, 1, name, bold)]
        body += [(i, 2, 1, 1, "30", False), (i, 3, 1, 1, "120", False)]
    f = make_pdf(tmp_path / "r.pdf", [head + body])
    cells, _ = to_cells("abc", extract.read_file(f))
    levels = {r[4]: r[3] for r in rows_of(cells)}
    assert levels == {
        "GRAND TOTAL": "total",
        "REGION I": "region",
        "Provincia": "province",
        "Townville": "town",
    }


def test_remap_puts_words_under_shaded_row_columns():
    from sakuna.pdf_reader import _remap

    # shaded row grid: inset shading adds 5-pt strips (x as in a 2024 report)
    ref = [(54, 0, 60, 1), (60, 0, 304, 1), (304, 0, 309, 1), (309, 0, 315, 1), (315, 0, 386, 1)]
    out = _remap([(62, 100, "Townville"), (370, 384, "3")], ref)
    assert out == ["", "Townville", "", "", "3"]
    # a number spilling over the cell border on either side is one word, so it stays whole
    assert _remap([(300, 380, "740,972,976.86")], ref)[4] == "740,972,976.86"
    # a "-" sitting in a strip goes to the nearest real column
    assert _remap([(305, 308, "-")], ref)[1] == "-"
    # a long number wrapped onto a second line in a narrow cell
    assert _remap([(330, 380, "864,877.9"), (330, 335, "5")], ref)[4] == "864,877.95"
    assert _remap([(330, 380, "1,306,45"), (330, 350, "0.00")], ref)[4] == "1,306,450.00"
    # two whole numbers in one column are never glued together
    assert _remap([(320, 340, "11,986"), (350, 380, "39,014")], ref)[4] == "11,986 39,014"


def test_to_cells_combined_keeps_the_region_row_above_its_block():
    paths = ["REGION", "NUMBER OF AFFECTED > Families", "NO. OF DAMAGED HOUSES > Total"]
    rows = [
        (["GRAND TOTAL", "30", "3"], True),
        (["REGION I", "10", "1"], True),
        (["REGION III", "20", "2"], True),
        (["REGION I", "10", "1"], True),
        (["Townville", "10", "1"], False),
        (["REGION III", "20", "2"], True),
        (["Villa Dos", "20", "2"], False),
    ]
    cells, _ = to_cells("x", [Piece(paths, rows)])
    order = list(dict.fromkeys(zip(cells["row_no"], cells["name"], strict=True)))
    assert [n for _, n in order] == [
        "GRAND TOTAL",
        "REGION I",
        "Townville",
        "REGION III",
        "Villa Dos",
    ]
