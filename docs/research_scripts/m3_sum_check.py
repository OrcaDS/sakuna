"""Classify region-sum mismatches: by year/format and by how they're off."""
import csv
import re
import sys
from collections import Counter, defaultdict

import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding="utf-8")
man = {r["sha256"]: r for r in csv.DictReader(open("raw/manifest.csv", encoding="utf-8")) if r["sha256"]}
log = [r for r in csv.DictReader(open("lake/bronze/_log.csv", encoding="utf-8")) if r["status"] == "ok"]
num = lambda v: float(v.replace(",", "")) if re.fullmatch(r"[\d,]*\.?\d+", v) else 0.0
files = Counter()
how = Counter()
examples = defaultdict(list)
for r in log:
    m = man[r["sha256"]]
    t = pq.read_table(f"lake/bronze/{r['sha256']}.parquet").to_pylist()
    cols = defaultdict(lambda: defaultdict(float))
    totals = Counter(c["kind"] for c in t if c["level"] == "total" and c["column"])
    for c in t:
        cols[(c["kind"], re.sub(r"[^A-Z]", "", c["column"].upper()))][c["level"]] += num(c["value"])
    bad_file = False
    for (kind, col), lv in cols.items():
        tot = lv["total"]
        if tot <= 0 or abs(lv["region"] - tot) <= 0.01 * tot:
            continue
        bad_file = True
        if lv["region"] == 0:
            k = "no region rows"
        elif lv["region"] > tot:
            k = "regions > total"
        else:
            k = "regions < total"
        how[k] += 1
        if len(examples[k]) < 6:
            examples[k].append((m["local_path"][:100], kind, col[:45], tot, lv["region"], lv["province"], lv["town"]))
    files[(m["event_year"], bad_file)] += 1
for y in sorted({k[0] for k in files}):
    print(y, "files off:", files[(y, True)], "of", files[(y, True)] + files[(y, False)])
print(how)
for k, ex in examples.items():
    print("==", k)
    for e in ex:
        print("  ", *e)
