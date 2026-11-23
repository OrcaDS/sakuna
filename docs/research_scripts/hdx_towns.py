# Town-level check: each HDX row vs the same-named row in the report whose totals match HDX best.
import re, sys, duckdb
from collections import Counter
from sakuna.psgc import _sheet_rows
X = 'data/typhonn-impacts.xlsx'
def num(s):
    s = (s or '').replace(',', '').strip()
    return 0 if s == '-' else (int(float(s)) if s else None)
def norm(s):
    s = s.lower().replace('ñ', 'n')
    s = re.sub(r'\(.*?\)|\bcity of\b|\bcity\b|[^a-z ]', ' ', s)
    return ' '.join(s.split())
c = duckdb.connect('lake/sakuna.duckdb', read_only=True)
SHEETS = [('People affected', {'affected_families': 'E', 'affected_persons': 'F'}),
          ('Damaged houses', {'houses_totally_damaged': 'D', 'houses_partially_damaged': 'E'})]
for sheet, cols in SHEETS:
    hdx = {}
    for r in _sheet_rows(X, sheet):
        if r.get('B', '').isdigit() and int(r['B']) >= 2018 and r.get('C') and 'TOTAL' not in r['C'].upper():
            hdx.setdefault(r['A'].title(), []).append(r)
    for name, rows in hdx.items():
        m0, col0 = next(iter(cols.items()))
        # pick the report whose town values agree with HDX most
        reps = c.sql(f"""select sha256, report_no, report_date from reports join events e using (event_id)
                         where e.local_name='{name}' and e.event_year between 2018 and 2020""").fetchall()
        best = None
        for sha, no, dt in reps:
            ours = {}
            for n, met, v in c.sql(f"select name, metric, value from place_metrics where sha256='{sha}' and level not in ('total')").fetchall():
                ours.setdefault((norm(n), met), []).append(int(v))
            res = Counter()
            bad = []
            for r in rows:
                for met, col in cols.items():
                    h = num(r.get(col))
                    if h is None: continue
                    got = ours.get((norm(r['C']), met))
                    k = 'missing' if got is None else ('equal' if h in got else 'differs')
                    res[k] += 1
                    if k != 'equal': bad.append((r['C'], met, h, got))
            if best is None or res['equal'] > best[0]['equal']:
                best = (res, no, dt, bad)
        res, no, dt, bad = best
        tot = sum(res.values())
        print(f"{sheet[:6]} {name:8} report #{no} {dt}: {res['equal']}/{tot} equal, {res['differs']} differ, {res['missing']} not found")
        for b in bad[:int(sys.argv[1]) if len(sys.argv) > 1 else 0]:
            print('    ', b)
