"""Sum check (regions vs GRAND TOTAL, ±1%) run live on a sample of one year's files, no re-extract.
usage: m3_live_check.py YEAR [N]"""
import csv
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from sakuna.extract import is_preparedness, read_file, to_cells

sys.stdout.reconfigure(encoding="utf-8")
year, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40
rows = [r for r in csv.DictReader(open("raw/manifest.csv", encoding="utf-8"))
        if r["status"] == "ok" and r["event_year"] == year and not is_preparedness(r)]
random.seed(1)
num = lambda v: float(v.replace(",", "")) if re.fullmatch(r"[\d,]*\.?\d+", v) else 0.0
bad = 0
for r in random.sample(rows, min(n, len(rows))):
    cells, _ = to_cells("x", read_file(Path("raw") / r["local_path"]))
    cols = defaultdict(lambda: defaultdict(float))
    for kind, lvl, col, v in zip(cells["kind"], cells["level"], cells["column"], cells["value"]):
        cols[(kind, re.sub(r"[^A-Z]", "", col.upper()))][lvl] += num(v)  # "GRAND > TOTAL" = "GRAND TOTAL"
    off = [(k, c[:40], lv["total"], lv["region"]) for (k, c), lv in cols.items()
           if lv["total"] > 0 and abs(lv["region"] - lv["total"]) > 0.01 * lv["total"]]
    if off:
        bad += 1
        print(r["local_path"][:110])
        for o in off[:4]:
            print("    ", *o)
print(f"{bad} of {min(n, len(rows))} files off")
