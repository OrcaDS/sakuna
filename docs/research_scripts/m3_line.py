"""Print every word on the text line of a page that contains a keyword, with x positions."""
import sys

import pdfplumber

sys.stdout.reconfigure(encoding="utf-8")
f, pg, key = sys.argv[1], int(sys.argv[2]), sys.argv[3]
with pdfplumber.open(f) as pdf:
    words = pdf.pages[pg - 1].extract_words()
    for w in words:
        if w["text"] == key.split()[-1]:
            line = [(round(x["x0"]), x["text"]) for x in words if abs(x["top"] - w["top"]) < 3]
            print(round(w["top"]), line)
