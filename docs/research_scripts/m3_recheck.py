"""Re-extract (live, in parallel) only the files of a year whose bronze fails the sum check,
and print which still fail. usage: m3_recheck.py YEAR"""
import csv
import re
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq

from sakuna.extract import read_file, to_cells

num = lambda v: float(v.replace(",", "")) if re.fullmatch(r"[\d,]*\.?\d+", v) else 0.0


def off(rows) -> dict:
    """Worst region/total ratio per kind, for columns off by more than 1%."""
    cols = defaultdict(lambda: defaultdict(float))
    for kind, lvl, col, v in rows:
        cols[(kind, re.sub(r"[^A-Z]", "", col.upper()))][lvl] += num(v)
    worst = {}
    for (kind, col), lv in cols.items():
        t = lv["total"]
        if t > 0 and abs(lv["region"] - t) > 0.01 * t:
            r = lv["region"] / t
            if kind not in worst or abs(r - 1) > abs(worst[kind][1] - 1):
                worst[kind] = (col[:30], round(r, 2))
    return worst


def live(path: str) -> dict:
    cells, _ = to_cells("x", read_file(Path("raw") / path))
    return off(zip(cells["kind"], cells["level"], cells["column"], cells["value"]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    year = sys.argv[1]
    man = {r["sha256"]: r for r in csv.DictReader(open("raw/manifest.csv", encoding="utf-8")) if r["sha256"]}
    todo = []
    for r in csv.DictReader(open("lake/bronze/_log.csv", encoding="utf-8")):
        if r["status"] == "ok" and man[r["sha256"]]["event_year"] == year:
            t = pq.read_table(f"lake/bronze/{r['sha256']}.parquet").to_pylist()
            if off((c["kind"], c["level"], c["column"], c["value"]) for c in t):
                todo.append(r["local_path"])
    with ProcessPoolExecutor() as ex:
        results = list(ex.map(live, todo))
    still = [(p, w) for p, w in zip(todo, results) if w]
    for p, w in still:
        print(p[:90], "\n    ", w)
    print(f"{year}: {len(todo)} failing in bronze -> {len(still)} still failing")
