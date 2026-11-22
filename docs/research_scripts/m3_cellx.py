"""Print x-ranges of each non-empty cell for the first rows of tables whose text has a keyword."""
import sys

import pdfplumber

from sakuna.extract import clean

sys.stdout.reconfigure(encoding="utf-8")
f, key, n = sys.argv[1], sys.argv[2].upper(), int(sys.argv[3]) if len(sys.argv) > 3 else 10
with pdfplumber.open(f) as pdf:
    for pg, page in enumerate(pdf.pages, 1):
        for ti, t in enumerate(page.find_tables()):
            text = t.extract()
            if key not in " ".join(clean(c) for r in text for c in r).upper():
                continue
            print(f"== page {pg} table {ti}")
            for i in range(min(len(t.rows), n)):
                print(i, [(j, round(c[0]), round(c[2]), clean(text[i][j])[:12])
                          for j, c in enumerate(t.rows[i].cells) if c is not None])
