"""Print total/region rows of one kind from a bronze file, filtered by a column keyword.
usage: m3_bronze_rows.py SHA_PREFIX KIND [COLUMN_KEYWORD]"""
import sys
from pathlib import Path

import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding="utf-8")
sha, kind = sys.argv[1], sys.argv[2]
key = sys.argv[3].upper() if len(sys.argv) > 3 else ""
f = next(Path("lake/bronze").glob(f"{sha}*.parquet"))
for c in pq.read_table(f).to_pylist():
    if c["kind"] == kind and c["level"] in ("total", "region") and key in c["column"].upper():
        print(c["row_no"], c["level"], c["name"], "|", c["column"], "|", c["value"])
