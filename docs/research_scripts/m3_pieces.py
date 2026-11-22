"""List every table piece a file yields (page order) with kind, width, first/last name, so lost
pages show up: compare with what select() keeps."""
import sys
from pathlib import Path

from sakuna.extract import kind_of, name_columns, read_file, select

sys.stdout.reconfigure(encoding="utf-8")
pieces = read_file(Path(sys.argv[1]))
for i, p in enumerate(pieces):
    k = kind_of(p.paths) if p.paths else "-"
    first = p.rows[0][0][:3] if p.rows else []
    last = p.rows[-1][0][:3] if p.rows else []
    print(f"{i:3} kind={k!s:10} w={len(p.rows[0][0]) if p.rows else 0:2} hdrw={len(p.paths):2} "
          f"rows={len(p.rows):3} first={first} last={last}")
print("--- selected")
for kind, parts in select(pieces).items():
    print(kind, [len(r) for _, r in parts], name_columns(parts[0][0]))
