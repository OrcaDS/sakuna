import sys
import pdfplumber
from sakuna.extract import clean, is_header_row
from sakuna.pdf_reader import _paths

sys.stdout.reconfigure(encoding="utf-8")
f, pages = sys.argv[1], [int(x) for x in sys.argv[2:]]
with pdfplumber.open(f) as pdf:
    for pg in pages:
        page = pdf.pages[pg - 1]
        for t in page.find_tables():
            cells = [[clean(c) for c in r] for r in t.extract()]
            h = next((i for i, r in enumerate(cells) if not is_header_row(r)), len(cells))
            if h == len(cells):
                continue
            print(f"p{pg} rows={len(cells)} h={h} ncols={len(t.columns)} data_top={t.rows[h].bbox[1]:.1f}")
            print("  cols", [(round(c.bbox[0]), round(c.bbox[2])) for c in t.columns])
            for c in sorted(t.cells, key=lambda c: (c[1], c[0])):
                if c[1] < t.rows[h].bbox[1]:
                    print("  hdr", [round(x) for x in c], clean(page.within_bbox(c).extract_text())[:50])
            print("  paths", _paths(page, t, h))
            print("  row0", cells[h])
