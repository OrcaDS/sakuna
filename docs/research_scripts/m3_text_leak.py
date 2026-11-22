"""Count bronze values that are not numbers (free text leaking into number columns)."""
import sys
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from sakuna.extract import NUMBER

sys.stdout.reconfigure(encoding="utf-8")
bad, files, samples = Counter(), set(), []
for f in Path("lake/bronze").glob("*.parquet"):
    t = pq.read_table(f, columns=["value", "name"]).to_pylist()
    for c in t:
        v = c["value"]
        if v and not NUMBER.match(v):
            bad["non-number"] += 1
            files.add(f.stem)
            if len(samples) < 25:
                samples.append((f.stem[:8], c["name"][:40], v[:60]))
print(bad, "files:", len(files))
for s in samples:
    print(s)
