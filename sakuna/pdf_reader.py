"""Read the ruled tables of a PDF report (pdfplumber) into `Piece`s."""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from sakuna.extract import Piece, clean, is_header_row, kind_of

TOL = 0.5  # points
SLIVER = 8  # points: thinner cells are the strips left by inset row shading
WRAPPED = re.compile(r"[\d,]*[,.][\d,.]* [\d,.]+")  # a long number broken over two lines
GROUPED = re.compile(r"\d{1,3}(,\d{3})*(\.\d+)?")  # ...joined only if it reads as one number


def _inside(ch: dict, box: tuple) -> bool:
    x0, top, x1, bottom = box
    cx, cy = (ch["x0"] + ch["x1"]) / 2, (ch["top"] + ch["bottom"]) / 2
    return x0 <= cx <= x1 and top <= cy <= bottom


def _bold(chars: list[dict], boxes: list) -> bool:
    """Regions and provinces are bold (and shaded); towns are not. Looks at the row's first
    cell with text: some pages split the name column and leave the first cell empty."""
    for box in boxes:
        if box is None:
            continue
        ch = next((c for c in chars if c["text"].strip() and _inside(c, box)), None)
        if ch is not None:
            return "Bold" in ch["fontname"]
    return False


def _text(page, box: tuple) -> str:
    """Text whose centre lies in the box: header text often touches the cell border."""
    x0, top, x1, bottom = box

    def centred(o: dict) -> bool:
        if o.get("object_type") != "char":
            return False
        cx, cy = (o["x0"] + o["x1"]) / 2, (o["top"] + o["bottom"]) / 2
        return x0 <= cx <= x1 and top <= cy <= bottom

    return clean(page.filter(centred).extract_text())


def _paths(page, table, h: int, ref: list) -> list[str]:
    """Header path per column from the merged header cells covering that column's centre."""
    first_data_top = table.rows[h].bbox[1]
    header = sorted((c for c in table.cells if c[1] < first_data_top - TOL), key=lambda c: c[1])
    texts = [_text(page, c) for c in header]
    paths = []
    # pdfplumber's column boxes overlap under merged cells; a data row has one cell each.
    for col in ref:
        if col is None:
            paths.append("")
            continue
        mid = (col[0] + col[2]) / 2
        parts: list[str] = []
        for c, t in zip(header, texts, strict=True):
            if c[0] <= mid <= c[2] and t and (not parts or parts[-1] != t):
                parts.append(t)
        paths.append(" > ".join(parts))
    return paths


def _remap(words: list[tuple[float, float, str]], ref: list) -> list[str]:
    """Put each word (x0, x1, text) of a row under the reference column holding its x-centre.

    Words, not pdfplumber's cell text: shaded rows (regions, provinces) have thin extra
    columns from the inset shading, and long numbers spill a digit over the cell border
    into them ("7" + "40,972,976.86"). A word keeps the number whole. Thin strips are never
    columns; a word outside every column goes to the nearest one, so no number is lost."""
    out = [""] * len(ref)
    cols = [k for k, b in enumerate(ref) if b is not None and b[2] - b[0] >= SLIVER]
    for x0, x1, text in words:
        cx = (x0 + x1) / 2
        k = next((k for k in cols if ref[k][0] <= cx <= ref[k][2]), None)
        if k is None:
            k = min(cols, key=lambda k: max(ref[k][0] - cx, cx - ref[k][2]))
        out[k] = f"{out[k]} {text}".strip()
    # a long number wrapped onto a second line in a narrow cell: "864,877.9 5"
    return [_unwrap(t) for t in out]


def _unwrap(t: str) -> str:
    joined = t.replace(" ", "")
    return joined if WRAPPED.fullmatch(t) and GROUPED.fullmatch(joined) else t


def _row_words(words: list[dict], box: tuple) -> list[tuple[float, float, str]]:
    """Words whose centre lies in the row's box, in reading order (line by line)."""
    x0, top, x1, bottom = box
    inside = [
        w
        for w in words
        if x0 <= (w["x0"] + w["x1"]) / 2 <= x1 and top <= (w["top"] + w["bottom"]) / 2 <= bottom
    ]
    inside.sort(key=lambda w: (round(w["top"]), w["x0"]))
    return [(w["x0"], w["x1"], w["text"]) for w in inside]


def _n_cells(boxes: list) -> int:
    return sum(b is not None for b in boxes)


def read_pdf(path: Path) -> list[Piece]:
    pieces = []
    last = None  # (x0, x1, ref columns) of the last table with a header
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            for table in page.find_tables():
                cells = [[clean(c) for c in row] for row in table.extract()]
                h = next((i for i, r in enumerate(cells) if not is_header_row(r)), len(cells))
                if h == len(cells):
                    continue  # no numbers: page frames and free-text boxes are never kept
                x0, x1 = table.bbox[0], table.bbox[2]
                # column map: the data row with the most cells (some rows lack empty cells)
                ref = max((table.rows[i].cells for i in range(h, len(cells))), key=_n_cells)
                if h:
                    paths = _paths(page, table, h, ref)
                    if kind_of(paths):  # small side tables must not replace the main header
                        last = (x0, x1, ref)
                else:
                    paths = []
                    # a continuation page: same table, same x-positions, maybe a coarser grid
                    # or an empty strip left of the name column (its words map to the nearest)
                    if last and x0 < last[0] + 3 and abs(last[1] - x1) < 3:
                        ref = last[2]
                rows = []
                for i in range(h, len(cells)):
                    box = table.rows[i].bbox
                    if (
                        i > h
                        and box[1] > table.rows[i - 1].bbox[1] + TOL
                        and (box[3] <= table.rows[i - 1].bbox[3] + TOL)
                    ):
                        # a stray line inside a row makes a half-height sub-row; its words
                        # already belong to the row it sits in
                        continue
                    row = _remap(_row_words(words, box), ref)
                    rows.append((row, _bold(page.chars, table.rows[i].cells)))
                pieces.append(Piece(paths, rows))
    return pieces
