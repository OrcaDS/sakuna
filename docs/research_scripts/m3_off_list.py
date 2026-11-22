"""List files of one year whose regions don't sum to GRAND TOTAL (±1%): worst column per kind.
usage: m3_off_list.py YEAR"""
import csv
import re
import sys
from collections import defaultdict

import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding="utf-8")
year = sys.argv[1]
man = {r["sha256"]: r for r in csv.DictReader(open("raw/manifest.csv", encoding="utf-8")) if r["sha256"]}
log = [r for r in csv.DictReader(open("lake/bronze/_log.csv", encoding="utf-8"))
       if r["status"] == "ok" and man[r["sha256"]]["event_year"] == year]
num = lambda v: float(v.replace(",", "")) if re.fullmatch(r"[\d,]*\.?\d+", v) else 0.0
for r in log:
    cols = defaultdict(lambda: defaultdict(float))
    for c in pq.read_table(f"lake/bronze/{r['sha256']}.parquet").to_pylist():
        cols[(c["kind"], re.sub(r"[^A-Z]", "", c["column"].upper()))][c["level"]] += num(c["value"])
    worst = {}
    for (kind, col), lv in cols.items():
        t = lv["total"]
        if t > 0 and abs(lv["region"] - t) > 0.01 * t:
            ratio = lv["region"] / t
            if kind not in worst or abs(ratio - 1) > abs(worst[kind][1] - 1):
                worst[kind] = (col[:30], ratio)
    if worst:
        print(r["sha256"][:12], man[r["sha256"]]["local_path"][:70])
        print("    ", "  ".join(f"{k}:{v[0]}={v[1]:.2f}" for k, v in sorted(worst.items())))
