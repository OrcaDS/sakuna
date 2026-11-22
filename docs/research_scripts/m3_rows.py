"""Dump one table kind of a file: header paths, then each row's level, bold flag and cells."""
import sys
from pathlib import Path

from sakuna.extract import level_of, name_columns, read_file, select

sys.stdout.reconfigure(encoding="utf-8")
parts = select(read_file(Path(sys.argv[1])))[sys.argv[2]]
for j, p in enumerate(parts[0][0]):
    print(j, p)
for paths, rows in parts:
    names = name_columns(paths)
    for cells, area in rows:
        name = next((cells[j] for j in names if j < len(cells) and cells[j]), "")
        print(f"{level_of(name, area):8} {area!s:5} {cells}")
