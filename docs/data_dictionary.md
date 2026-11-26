# sakuna data dictionary

Every Philippine typhoon, tropical storm, tropical depression and southwest monsoon (habagat) event that DSWD reported on from January 2017, town by town. Built from DSWD DROMIC situation reports.

Source: DSWD DROMIC situation reports. Cleaned by sakuna. Not an official DSWD product. Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Which file to use

| File | One row per | Use it for |
|---|---|---|
| `event_summary` | event | Ranking storms, national totals. Start here. |
| `impacts` | event × town | Town-level questions: repeat-hit towns, maps, joins with census data. Uses each event's latest report. |
| `events` | event | Event names, type, dates. |
| `reports` | report file | Which reports exist for an event, links to the originals. |
| `impacts_by_report` | event × report × place | How numbers changed from report to report (e.g. how long evacuation centres stayed open). Every level: total, region, province, town. |
| `unmatched_places` | town spelling | Town names we could not match to an official place code. |

Every table comes as CSV (`impacts_by_report` as `.csv.gz`, which most tools read directly) and as Parquet. `SHA256SUMS` lets you check the downloads (`sha256sum -c SHA256SUMS`).

```sql
-- DuckDB, straight from the latest release
select * from 'https://github.com/OrcaDS/sakuna/releases/latest/download/event_summary.parquet';
```

## Conventions

- **Empty means missing.** DSWD left the cell blank or the column does not exist in that report. A dash (`-`) in the report is 0.
- **Counts** are whole numbers of families, persons, houses or barangays. **Costs** are Philippine pesos (PHP), two decimals.
- **Place codes** are PSA's PSGC codes (10 digits, keep them as text to keep the leading zero). Names come from PSGC; `dswd_name` keeps DSWD's own spelling.
- **Latest report.** `impacts` and `event_summary` use one report per event: the terminal (final) report if there is one, else the latest date, else the highest report number.
- **Evacuation counts** in `impacts` and `event_summary` are cumulative: everyone who stayed in or outside an evacuation centre (EC) during the event. `impacts_by_report` also has the count on the report date (`_now`).
- **We never correct DSWD's numbers.** Where DSWD's totals and its own town rows disagree, both are kept; see `known_gaps.md`.

## event_summary

| Column | Meaning |
|---|---|
| event_id | Event key (the DROMIC post's web address). Joins all tables. |
| event_title | Title of the DROMIC post. |
| local_name | PAGASA name (e.g. Odette). Empty when the title has none (most monsoon events). |
| event_type | super typhoon, typhoon, severe tropical storm, tropical storm, tropical depression, tropical cyclone (several storms in one post), monsoon. |
| event_year | Year of the start date. |
| start_date | Date in the post title. |
| n_towns | Towns and cities with a row in the latest report. |
| n_unmatched_towns | Of those, how many have no place code (see `unmatched_places`). |
| affected_families, affected_persons | Sum of town rows. |
| inside_ec_families, inside_ec_persons | Displaced and staying inside evacuation centres (cumulative), sum of town rows. |
| outside_ec_families, outside_ec_persons | Displaced and staying elsewhere, e.g. with relatives (cumulative), sum of town rows. |
| houses_totally_damaged, houses_partially_damaged | Sum of town rows. |
| cost_total | Cost of assistance (PHP) given to towns, sum of town rows. Lower than DSWD's total when aid went to provinces (see known gaps). |
| dswd_… | The same figure from DSWD's own GRAND TOTAL row in the same report. |
| source_url | Link to the report used. |

## impacts

One row per event and town/city, from the event's latest report.

| Column | Meaning |
|---|---|
| event_id, report_no, report_date | Event and the report the numbers come from. `report_no` is empty for the terminal report. |
| psgc_code | PSGC code of the town or city. Empty if unmatched. |
| region_code, region | PSGC region. |
| province_code, province | PSGC province. Empty for highly urbanised cities (HUCs) and NCR cities, which belong to no province. |
| town | Official PSGC name. |
| dswd_name | The name as DSWD wrote it. |
| match_rule | How the name was matched: `province` (within the province DSWD listed it under), `region` (within the region), `nationwide` (the only town with that name), `unmatched`. |
| affected_brgys | Barangays affected. |
| affected_families, affected_persons | Affected families and persons. |
| inside_ec_count | Evacuation centres opened (cumulative). |
| inside_ec_families, inside_ec_persons | Displaced inside evacuation centres (cumulative). |
| outside_ec_families, outside_ec_persons | Displaced outside evacuation centres (cumulative). |
| houses_totally_damaged, houses_partially_damaged | Damaged houses. |
| cost_dswd, cost_lgu, cost_ngo, cost_other, cost_total | Cost of assistance in PHP, by who gave it. |
| has_repeated_rows | `true` when DSWD listed the town twice in one table; the rows were added up. |
| n_unreadable | Cells that were not a clean number (e.g. a typo like `28,12`); they are left empty. |
| source_url | Link to the report. |

## impacts_by_report

Same counts as `impacts`, for **every** report of every event and every level. Extra columns:

| Column | Meaning |
|---|---|
| is_latest | `true` for the report `impacts` uses. |
| level | `total` (DSWD's GRAND TOTAL), `region`, `province`, `town`, `group` (a sub-heading DSWD uses that is not a PSGC place, e.g. Metro Manila), `other` (aid lines that are not places, e.g. "PLGU Pangasinan" for aid given to the provincial government). |
| place | Official name for the level (region, province or town name). |
| inside_ec_…_cum / _now | Cumulative, and on the report date. |
| houses_total | DSWD's total damaged houses column. |
| sha256 | Fingerprint of the report file; tells apart two files posted on the same day. |

Do not add up all rows of a report: totals, regions, provinces and towns overlap. Filter on `level`.

## events

| Column | Meaning |
|---|---|
| event_id, event_title, local_name, event_type, event_year, start_date | As in `event_summary`. |
| international_name | International name when the title gives it (e.g. SANBA). |
| with_monsoon | `true` when the post covers the southwest monsoon as well. |
| n_reports | Report files used. |
| last_report_date | Date of the latest report. |
| is_terminated | DSWD has closed the event (terminal report or "Terminated" in the title). Open events can still change. |

## reports

| Column | Meaning |
|---|---|
| event_id | Event. |
| report_no | Report number; empty for the terminal report. |
| report_date | Date of the report. |
| is_terminal | Final report for the event. |
| is_latest | The report `impacts` uses. |
| source_url | Link to the original report on DROMIC or Google Docs. |
| sha256 | Fingerprint of the report file. |

## unmatched_places

| Column | Meaning |
|---|---|
| region_code, region, province_code, province | Where DSWD listed the row. |
| dswd_name | DSWD's spelling. |
| n_events | Events that list it. |
| example_event_id, example_source_url | One report where it appears. |
