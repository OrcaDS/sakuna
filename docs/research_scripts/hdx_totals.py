import duckdb
from sakuna.psgc import _sheet_rows
X = 'data/typhonn-impacts.xlsx'
def num(s):
    s = (s or '').replace(',', '').strip()
    return 0 if s == '-' else (int(float(s)) if s else None)
tot = {}
for sheet, cols in [('People affected', {'fam': 'E', 'per': 'F'}), ('Damaged houses', {'tot': 'D', 'part': 'E'})]:
    for r in _sheet_rows(X, sheet):
        if r.get('B', '').isdigit() and int(r['B']) >= 2018 and r.get('C', '').upper() in ('GRAND TOTAL', 'TOTAL'):
            d = tot.setdefault(r['A'].title(), {})
            for k, c in cols.items():
                d.setdefault(k, num(r.get(c)))  # first total row only
c = duckdb.connect('lake/sakuna.duckdb', read_only=True)
def pct(a, b):
    return '   n/a' if not a or b is None else f'{(b - a) / a * 100:+6.1f}%'
print(f"{'event':10} {'HDX fam':>9} {'ours':>9} {'dswd':>9} {'Δours':>7} | {'HDX tot':>7} {'ours':>7} {'Δ':>7} | {'HDX part':>8} {'ours':>8} {'Δ':>7}")
for name, h in tot.items():
    rows = c.sql(f"""select event_id, affected_families, dswd_affected_families, houses_totally_damaged, houses_partially_damaged
                     from event_summary where local_name = '{name}' and event_year between 2018 and 2020""").fetchall()
    for eid, fam, dfam, ht, hp in rows:
        print(f"{name:10} {h.get('fam') or 0:>9} {fam or 0:>9} {dfam or 0:>9} {pct(h.get('fam'), fam):>7} | {h.get('tot') or 0:>7} {ht or 0:>7} {pct(h.get('tot'), ht):>7} | {h.get('part') or 0:>8} {hp or 0:>8} {pct(h.get('part'), hp):>7}  {eid}")
