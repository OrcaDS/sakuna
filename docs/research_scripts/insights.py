"""Milestone 6: answer the six questions from the gold tables, write docs/insights.md.

Run from the repo root after `dbt build`:  uv run python docs/research_scripts/insights.py
Charts are Mermaid (GitHub draws them from the text), so no plotting library is needed.
"""

import sys
from pathlib import Path

import duckdb

sys.stdout.reconfigure(encoding="utf-8")
con = duckdb.connect("lake/sakuna.duckdb", read_only=True)


def rows(sql):
    return con.execute(sql).fetchall()


def one(sql):
    return rows(sql)[0]


def fmt(x, nd=0):
    return "" if x is None else f"{x:,.{nd}f}"


def table(header, data):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(v) for v in r) + " |" for r in data]
    return "\n".join(out)


def hbar(title, labels, values, axis):
    labels = ", ".join(f'"{s}"' for s in labels)
    top = max(values) * 1.1
    vals = ", ".join(f"{v:.2f}" for v in values)
    return (
        f'```mermaid\nxychart-beta horizontal\n  title "{title}"\n  x-axis [{labels}]\n'
        f'  y-axis "{axis}" 0 --> {top:.2f}\n  bar [{vals}]\n```'
    )


def line(title, labels, values, axis, top):
    labels = ", ".join(f'"{s}"' for s in labels)
    vals = ", ".join(f"{v:.1f}" for v in values)
    return (
        f'```mermaid\nxychart-beta\n  title "{title}"\n  x-axis [{labels}]\n'
        f'  y-axis "{axis}" 0 --> {top}\n  line [{vals}]\n```'
    )


# Event label: local name + year; a few combined monsoon posts have no local name.
con.execute("""
create temp view ev as
select event_id, coalesce(local_name, upper(event_type[1]) || event_type[2:]) || ' ' || event_year as label,
       event_year, event_type, start_date, n_reports
from events
""")
# Short region name: "Region VII (Central Visayas)" -> "Central Visayas".
con.execute(
    "create temp macro reg(r) as coalesce(nullif(regexp_extract(r, '[(]([^)]+)[)]', 1), ''), r)"
)
# DSWD's own GRAND TOTAL row per report.
con.execute("""
create temp view tot as
select r.*, e.label, e.start_date from impacts_by_report r join ev e using (event_id)
where level = 'total'
""")

n_events, y0, y1 = one("select count(*), min(event_year), max(event_year) from events")
n_rows = one("select count(*) from impacts")[0]
md = [
    "# Insights: Philippine typhoon impacts since 2017",
    "",
    f"Six questions answered from the gold tables: {n_events} events, {y0}–{y1}, "
    f"{n_rows:,} event × town rows. All numbers are DSWD's own counts as reported in "
    "DROMIC situation reports; sakuna does not correct them. Read the "
    "[known gaps](known_gaps.md) first. Regenerate this page with "
    "`uv run python docs/research_scripts/insights.py`.",
    "",
    "Words used below: *affected* = people DSWD counted as affected; *displaced* = people "
    "who stayed inside or outside evacuation centres (ECs), counted once over the whole "
    "event; *houses* = totally plus partially damaged.",
]

# 1. Repeat-hit towns --------------------------------------------------------------
often = rows("""
select town, coalesce(province, reg(region)) prov, count(distinct event_id) n,
       sum(affected_persons) persons
from impacts where psgc_code is not null and affected_families > 0
group by psgc_code, town, prov order by n desc, persons desc limit 15
""")
hard = rows("""
select town, coalesce(province, reg(region)) prov, count(distinct event_id) n,
       sum(affected_persons) persons
from impacts where psgc_code is not null and affected_families > 0
group by psgc_code, town, prov order by persons desc limit 10
""")
n_hit = one(
    "select count(distinct psgc_code) from impacts where psgc_code is not null "
    "and affected_families > 0"
)[0]
n_towns = one("select count(*) from psgc where level in ('Mun', 'City')")[0]
md += [
    "",
    "## 1. Which towns are hit most often, and hardest?",
    "",
    f"{n_hit:,} of the country's {n_towns:,} towns and cities had at least one affected "
    f"family in at least one event. The most often hit are in the Cordillera (landslides "
    f"and monsoon rain around Baguio), the Pampanga river delta (Masantol, Macabebe: "
    f"flooded almost every monsoon season) and the northern tip of Luzon (Cagayan).",
    "",
    hbar(
        "Towns hit by the most events",
        [f"{t} ({p})" for t, p, _, _ in often],
        [n for _, _, n, _ in often],
        "Events with affected families",
    ),
    "",
    "Hardest hit, by affected persons added up over all events (a person hit by three "
    "events is counted three times):",
    "",
    table(
        ["Town", "Province", "Events", "Affected persons, all events"],
        [(t, p, n, fmt(x)) for t, p, n, x in hard],
    ),
]

# 2. Storms ranked -----------------------------------------------------------------
rank_sql = """
select label, {col} v from event_summary join ev using (event_id)
where {col} > 0 order by v desc limit 10
"""
aff = rows(rank_sql.format(col="affected_persons"))
dis = rows(rank_sql.format(col="inside_ec_persons + coalesce(outside_ec_persons, 0)"))
hou = rows(rank_sql.format(col="houses_totally_damaged + houses_partially_damaged"))
recent = sum(lab.endswith(("2024", "2025", "2026")) for lab, _ in aff)
md += [
    "",
    "## 2. Storms ranked by human impact",
    "",
    (
        f"{aff[0][0]} leads on all three measures."
        if aff[0][0] == dis[0][0] == hou[0][0]
        else f"{aff[0][0]} leads on affected persons, {dis[0][0]} on displaced and "
        f"{hou[0][0]} on damaged houses."
    )
    + f" {recent} of the ten events with the most affected people happened "
    "in 2024 or later. Several of the biggest are combined events "
    "(a storm plus the southwest monsoon, e.g. Crising 2025, Luis 2026): DSWD reports "
    "them as one.",
    "",
    hbar(
        "Affected persons (millions)",
        [x[0] for x in aff],
        [float(x[1]) / 1e6 for x in aff],
        "Millions",
    ),
    "",
    table(
        ["Rank", "Most displaced", "Persons", "Most houses damaged", "Houses"],
        [
            (i + 1, d[0], fmt(d[1]), h[0], fmt(h[1]))
            for i, (d, h) in enumerate(zip(dis, hou, strict=True))
        ],
    ),
]

# 3. Days to empty evacuation centres ----------------------------------------------
ec = rows("""
with p as (
  select event_id, label, start_date,
         max(inside_ec_persons_now) peak,
         arg_max(report_date, inside_ec_persons_now) peak_date,
         count(*) n_rep, max(report_date) last_date
  from tot group by all
), d as (
  select p.*,
    (select min(report_date) from tot t where t.event_id = p.event_id
       and report_date > p.peak_date and inside_ec_persons_now <= 0.1 * p.peak) d10,
    (select min(report_date) from tot t where t.event_id = p.event_id
       and report_date > p.peak_date and inside_ec_persons_now = 0) d0
  from p where peak >= 1000 and n_rep >= 5
)
select label, peak, peak_date - start_date, d10 - start_date, d0 - start_date,
       last_date - start_date
from d order by peak desc
""")
n_ec = len(ec)
d10 = sorted(r[3] for r in ec if r[3] is not None)
d0 = [r[4] for r in ec if r[4] is not None]
med10 = d10[len(d10) // 2]
never0 = n_ec - len(d0)
md += [
    "",
    "## 3. How long until evacuation centres empty?",
    "",
    f"Counted over the {n_ec} events with at least five reports and at least 1,000 people "
    "inside ECs at the peak, measured from the event's start date and using DSWD's "
    "*now* column (people still inside on the report date). Reports come out daily at "
    "first, then weekly or less, so days are upper bounds.",
    "",
    f"- **Most people go home within days.** In half of these events, the number inside "
    f"ECs fell below 10% of its peak by day {med10} ({len(d10)} of {n_ec} events reached "
    "10% in the reports).",
    f"- **The last families stay for months.** {never0} of {n_ec} events never show zero "
    "in any report: DSWD stopped reporting while some ECs were still open. Odette 2021 "
    "still had 582 people in 4 ECs in May 2023, 17 months after landfall.",
    "",
    table(
        [
            "Event",
            "Peak inside ECs",
            "Peak on day",
            "Below 10% by day",
            "Zero by day",
            "Last report day",
        ],
        [
            (lab, fmt(pk), a, "" if b is None else b, "never" if c is None else c, e)
            for lab, pk, a, b, c, e in ec[:12]
        ],
    ),
]

# 4. Aid per affected family by region ---------------------------------------------
aid = rows("""
select reg(region), sum(cost_total) / sum(affected_families) per_fam,
       count(distinct event_id) n
from impacts_by_report
where level = 'region' and is_latest and affected_families > 0
group by region order by per_fam desc
""")
md += [
    "",
    "## 4. Aid per affected family, by region",
    "",
    "Total cost of assistance (DSWD, local governments, NGOs and others) divided by "
    "affected families, from each region's row in each event's latest report, so aid "
    "given to provinces rather than towns is included. All events added up; pesos are "
    "not adjusted for inflation.",
    "",
    hbar(
        "Aid per affected family (PHP)",
        [r for r, _, _ in aid],
        [float(v) for _, v, _ in aid],
        "PHP",
    ),
    "",
    "Poverty comparison: still to do. It needs PSA's regional poverty incidence table, "
    "which has to be downloaded by hand (psa.gov.ph blocks scripts).",
]

# 5. Share of town population affected ---------------------------------------------
share_sql = """
from impacts i join psgc p using (psgc_code)
where p.population_2024 > 0 and i.affected_persons > 0
"""
bands = one(f"""
select count(*),
  count(*) filter (where affected_persons < 0.1 * population_2024),
  count(*) filter (where affected_persons >= 0.1 * population_2024
                   and affected_persons < 0.5 * population_2024),
  count(*) filter (where affected_persons >= 0.5 * population_2024
                   and affected_persons <= population_2024),
  count(*) filter (where affected_persons > population_2024),
  median(affected_persons / population_2024)
{share_sql}
""")
half = rows(f"""
select town, coalesce(province, reg(i.region)) prov, count(*) n
{share_sql} and affected_persons >= 0.5 * population_2024
  and affected_persons <= population_2024
group by psgc_code, town, prov order by n desc, town limit 10
""")
tot_n = bands[0]
md += [
    "",
    "## 5. What share of a town's people is affected?",
    "",
    "Affected persons divided by the town's 2024 census population (PSA, in the PSGC "
    f"file), for the {tot_n:,} event × town rows with a population and at least one "
    f"affected person. In a typical row {bands[5] * 100:.0f}% of the town is affected.",
    "",
    table(
        ["Share of population affected", "Event × town rows", "Share of rows"],
        [
            (lab, fmt(n), f"{100 * n / tot_n:.0f}%")
            for lab, n in zip(
                ["under 10%", "10–50%", "50–100%", "over 100%"], bands[1:5], strict=True
            )
        ],
    ),
    "",
    f"**{bands[4]:,} rows count more affected people than the town's population.** These "
    "are DSWD's numbers, not a matching error (Mariveles, Bataan, 2023: 335,487 affected, "
    "156,200 residents, the same figure in each of its last five reports). Possible causes: people from nearby towns counted where they took "
    "shelter, families multiplied by an assumed household size, or older population "
    "figures in the field. Treat shares above 100% as \"most or all of the town\".",
    "",
    "Towns where at least half the population was affected most often (rows over 100% "
    "left out):",
    "",
    table(["Town", "Province", "Events with 50–100% affected"], half),
]

# 6. Day-1 undercount --------------------------------------------------------------
curve_days = [0, 1, 2, 3, 5, 7, 14, 30]
curve = rows(f"""
with f as (
  select event_id, min(report_date) d1, max_by(affected_persons, is_latest::int) final
  from tot where affected_persons is not null group by event_id
  having final >= 1000
), g as (select unnest({curve_days}) n)
select g.n, median(coalesce((
    select max_by(t.affected_persons, t.report_date::varchar || lpad(coalesce(t.report_no, 9999)::varchar, 4, '0'))
    from tot t where t.event_id = f.event_id and t.affected_persons is not null
      and t.report_date <= f.d1 + g.n::int), 0) / f.final) med,
  count(*) n_ev
from f, g group by g.n order by g.n
""")
first = one("""
with f as (
  select event_id, min(report_date) d1, max_by(affected_persons, is_latest::int) final
  from tot where affected_persons is not null group by event_id having final >= 1000
)
select count(*),
  median(datediff('day', d1, (select report_date from tot t where t.event_id = f.event_id
                              and t.is_latest limit 1)))
from f
""")
md += [
    "",
    "## 6. How much do day-1 reports undercount?",
    "",
    f"For the {first[0]} events with at least 1,000 affected persons in the final count, "
    "the line shows the median share of the final affected-persons count that DSWD's "
    "own national total had reached N days after the first report. The first report "
    f"shows a median **{100 * curve[0][1]:.0f}%** of the final number; it takes about "
    f"{next((d for d, m, _ in curve if m >= 0.5), '30+')} days to reach half. The latest "
    f"report comes a median {first[1]:.0f} days after the first.",
    "",
    line(
        "Median share of final affected count, by day",
        [f"Day {d}" for d in curve_days],
        [100 * float(m) for _, m, _ in curve],
        "% of final count",
        100,
    ),
    "",
    "Early reports are a floor, not an estimate: anyone using a first-week report "
    "(for news, funding or models) should expect the final count to be many times "
    "larger.",
]

md += [
    "",
    "---",
    "Source: DSWD DROMIC situation reports. Cleaned by sakuna. Not an official DSWD "
    "product.",
    "",
]
Path("docs/insights.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
print("\n".join(md))
