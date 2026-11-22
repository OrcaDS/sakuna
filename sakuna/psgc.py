"""Turn PSA's PSGC publication .xlsx into the dbt seed `transform/seeds/psgc.csv`.

Keeps regions, provinces, cities, municipalities and Manila's sub-municipalities (no barangays).
Codes are 10 digits: region = first 2, province = first 5, city/municipality = first 7.
Reads the workbook with stdlib zipfile + XML; columns are found by header text, not position.
"""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
LEVELS = {"Reg", "Prov", "City", "Mun", "SubMun"}
HEADERS = {  # seed column → start of the PSA header text
    "psgc_code": "10-digit psgc",
    "name": "name",
    "level": "geographic level",
    "old_names": "old names",
    "city_class": "city class",
    "population_2024": "2024 population",
}
FIELDS = [*HEADERS, "region_code", "province_code"]


def _sheet_rows(xlsx: Path, sheet_name: str) -> list[dict[str, str]]:
    """Return the sheet's rows as {column letter: text}."""
    with zipfile.ZipFile(xlsx) as z:
        strings = [
            "".join(t.text or "" for t in si.iter(NS + "t"))
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si")
        ]
        book = ET.fromstring(z.read("xl/workbook.xml"))
        rel_id = next(s.get(REL) for s in book.iter(NS + "sheet") if s.get("name") == sheet_name)
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == rel_id)
        sheet = ET.fromstring(z.read("xl/" + target.lstrip("/").removeprefix("xl/")))
    rows = []
    for row in sheet.iter(NS + "row"):
        cells = {}
        for c in row.iter(NS + "c"):
            v = c.find(NS + "v")
            text = (v.text or "") if v is not None else ""
            if c.get("t") == "s":
                text = strings[int(text)]
            cells[re.match(r"[A-Z]+", c.get("r"))[0]] = text.strip()
        rows.append(cells)
    return rows


def read_psgc(xlsx: Path) -> list[dict[str, str]]:
    """Rows for every place above barangay level, with parent region and province codes."""
    rows = _sheet_rows(xlsx, "PSGC")
    header = {v.lower(): k for k, v in rows[0].items()}
    cols = {}
    for field, start in HEADERS.items():
        matches = [col for text, col in header.items() if text.startswith(start)]
        if len(matches) != 1:
            raise ValueError(f"PSGC sheet: expected one '{start}' column, found {len(matches)}")
        cols[field] = matches[0]
    places = [
        {field: r.get(col, "") for field, col in cols.items()}
        for r in rows[1:]
        if r.get(cols["level"]) in LEVELS
    ]
    provinces = {p["psgc_code"] for p in places if p["level"] == "Prov"}
    for p in places:
        p["name"] = re.sub(r"(?<=[a-z])[a-z]/$", "", p["name"])  # footnote mark: "City of Lucenaa/"
        code = p["psgc_code"]
        if not re.fullmatch(r"\d{10}", code):
            raise ValueError(f"PSGC code is not 10 digits: {code!r}")
        p["region_code"] = code[:2] + "0" * 8
        prov = code[:5] + "0" * 5
        # HUCs and NCR cities carry their own province digits but belong to no province.
        p["province_code"] = prov if prov in provinces and p["level"] != "Reg" else ""
    return places


def write_seed(xlsx: Path, out: Path) -> int:
    """Write the seed CSV and return the number of places."""
    places = read_psgc(xlsx)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(places)
    return len(places)
