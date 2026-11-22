"""Run the extractor on given files and print a summary: kinds, levels, columns, sample rows."""
import sys
from collections import Counter
from pathlib import Path

from sakuna.extract import read_file, to_cells

sys.stdout.reconfigure(encoding="utf-8")
for f in sys.argv[1:]:
    cells, counts = to_cells("x", read_file(Path(f)))
    print("=" * 8, f[-80:], dict(counts))
    rows = list(zip(*(cells[c] for c in ("kind", "row_no", "level", "name", "column", "value"))))
    for kind in sorted({r[0] for r in rows}):
        kr = [r for r in rows if r[0] == kind]
        lv = Counter((r[1], r[2]) for r in kr)
        print(f"  {kind}: levels {dict(Counter(l for _, l in lv))}")
        for col, n in Counter(r[4] for r in kr).items():
            print(f"     col {n:5}  {col[:110]}")
        seen = []
        for r in kr:
            if r[1] not in seen:
                seen.append(r[1])
            if len(seen) > 4:
                break
            if r[1] == seen[-1] and len(seen) <= 4:
                pass
        for no in seen[:4]:
            rr = [r for r in kr if r[1] == no]
            print(f"     row {no} {rr[0][2]:8} {rr[0][3][:30]:30} " + " | ".join(r[5] for r in rr))
