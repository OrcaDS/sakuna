"""Read the tables of a .docx report (stdlib zipfile + XML) into `Piece`s."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from sakuna.extract import Piece, clean, header_paths, is_header_row, name_columns

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _text(tc: ET.Element) -> str:
    return clean(" ".join("".join(t.text or "" for t in p.iter(W + "t")) for p in tc.iter(W + "p")))


def _int_attr(el: ET.Element, path: str, default: int) -> int:
    found = el.find(path)
    return int(found.get(W + "val", default)) if found is not None else default


def _bold(tc: ET.Element) -> bool:
    b = tc.find(f".//{W}rPr/{W}b")
    return b is not None and b.get(W + "val", "1") not in ("0", "false")


def read_docx(path: Path) -> list[Piece]:
    body = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml")).find(W + "body")
    pieces = []
    for tbl in body.iter(W + "tbl"):
        # Expand merged cells: a header fills all its columns, a data cell only its first.
        rows = []
        for tr in tbl.findall(W + "tr"):
            n = _int_attr(tr, f"{W}trPr/{W}gridBefore", 0)
            head, data, bold = [""] * n, [""] * n, False
            for i, tc in enumerate(tr.findall(W + "tc")):
                text, span = _text(tc), _int_attr(tc, f"{W}tcPr/{W}gridSpan", 1)
                if i == 0:
                    bold = _bold(tc)
                head += [text] * span
                data += [text] + [""] * (span - 1)
            rows.append((head, data, bold))
        h = next((i for i, r in enumerate(rows) if not is_header_row(r[0])), len(rows))
        paths = header_paths([r[0] for r in rows[:h]])
        wide = len(name_columns(paths)) > 1
        # Province rows fill the first name column (spanning 2); town rows leave it empty.
        piece = Piece(paths, [(d, bool(d and d[0]) if wide else b) for _, d, b in rows[h:]])
        pieces.append(piece)
    return pieces
