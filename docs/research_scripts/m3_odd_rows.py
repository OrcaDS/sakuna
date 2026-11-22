"""Show rows that come out with an unknown level or a '?' column, and rows the guard drops."""
import sys
from pathlib import Path

from sakuna import extract
from sakuna.extract import read_file, select

sys.stdout.reconfigure(encoding="utf-8")
pieces = read_file(Path(sys.argv[1]))
for kind, parts in select(pieces).items():
    for paths, rows in parts:
        names = extract.name_columns(paths)
        for i, (cells, area) in enumerate(rows):
            name = next((cells[j] for j in names if j < len(cells) and cells[j]), "")
            long_ = [len(c) for c in cells if c and not extract.NUMBER.match(c)]
            if not name or len(cells) != len(paths) or long_:
                prev = rows[i - 1][0][:2] if i else None
                print(kind, "ncells", len(cells), "npaths", len(paths), "long", long_, "prev", prev,
                      "cells", [c[:25] for c in cells])
