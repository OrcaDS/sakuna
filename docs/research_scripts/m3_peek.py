"""Print the first rows (level, name) of one table kind for a report of a given year."""
import csv
import sys
from collections import Counter

import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding="utf-8")
year, kind, pick = sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
man = {r["sha256"]: r for r in csv.DictReader(open("raw/manifest.csv", encoding="utf-8")) if r["sha256"]}
log = [r for r in csv.DictReader(open("lake/bronze/_log.csv", encoding="utf-8"))
       if r["status"] == "ok" and man[r["sha256"]]["event_year"] == year]
r = log[int(len(log) * pick)]
print(man[r["sha256"]]["local_path"])
t = [c for c in pq.read_table(f"lake/bronze/{r['sha256']}.parquet").to_pylist() if c["kind"] == kind]
seen = []
for c in t:
    if c["row_no"] not in seen:
        seen.append(c["row_no"])
        if len(seen) <= 14:
            print(c["row_no"], c["level"], c["name"][:40], "|", c["column"][:40], c["value"])
print(Counter(c["level"] for c in t if c["column"] == t[0]["column"]))
