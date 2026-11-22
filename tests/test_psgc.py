import zipfile

import pytest

from sakuna import psgc

HEADER = [
    "10-digit PSGC",
    "Name",
    "Correspondence Code",
    "Geographic Level",
    "Old names",
    "City Class",
    "Income",
    "Urban",
    "2024 Population",
]
ROWS = [
    ["0700000000", "Region VII", "", "Reg", "", "", "", "", "1"],
    ["0702200000", "Cebu", "", "Prov", "", "", "", "", "2"],
    ["0702234000", "City of Naga", "", "City", "", "CC", "", "", "3"],
    ["0702234001", "Barangay X", "", "Bgy", "", "", "", "", "4"],
    ["0730600000", "City of Cebua/", "", "City", "", "HUC", "", "", "5"],
]


def _xlsx(path, header):
    strings = []

    def cell(col, text):
        strings.append(text)
        return f'<c r="{col}1" t="s"><v>{len(strings) - 1}</v></c>'

    rows = "".join(
        "<row>" + "".join(cell("BCDEFGHIJ"[i], t) for i, t in enumerate(r)) + "</row>"
        for r in [header, *ROWS]
    )
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            f"<workbook {ns} {rel}><sheets>"
            '<sheet name="Notes" r:id="rId1"/><sheet name="PSGC" r:id="rId2"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            "<Relationships>"
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>',
        )
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet {ns}><sheetData/></worksheet>")
        z.writestr(
            "xl/worksheets/sheet2.xml", f"<worksheet {ns}><sheetData>{rows}</sheetData></worksheet>"
        )
        sst = "".join(f"<si><t>{s}</t></si>" for s in strings)
        z.writestr("xl/sharedStrings.xml", f"<sst {ns}>{sst}</sst>")
    return path


def test_read_psgc_drops_barangays_and_sets_parents(tmp_path):
    places = {p["name"]: p for p in psgc.read_psgc(_xlsx(tmp_path / "p.xlsx", HEADER))}
    assert set(places) == {"Region VII", "Cebu", "City of Naga", "City of Cebu"}
    assert places["City of Naga"]["province_code"] == "0702200000"
    assert places["City of Naga"]["region_code"] == "0700000000"
    assert places["City of Cebu"]["province_code"] == ""  # HUC: no province
    assert places["Region VII"]["province_code"] == ""


def test_read_psgc_rejects_missing_column(tmp_path):
    header = [h if h != "Old names" else "Something else" for h in HEADER]
    with pytest.raises(ValueError, match="old names"):
        psgc.read_psgc(_xlsx(tmp_path / "p.xlsx", header))
