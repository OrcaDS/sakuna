# Philippine Typhoon and Monsoon Impacts by Town (2017–now)

_Built with **sakuna**, the open-source pipeline in this repository. sakuna is the pipeline's name, not the dataset's._

The first open, town-by-town history of every Philippine typhoon and monsoon event since 2017, rebuilt from DSWD's own situation reports: affected families and persons, displaced people, damaged houses and cost of assistance.

128 events from January 2017 to November 2026, about 17,500 event × town rows, from 2,645 DSWD DROMIC reports.

## Get the data

Download from [Releases](https://github.com/OrcaDS/sakuna/releases/latest): every table as CSV and Parquet.

| File | One row per |
|---|---|
| `event_summary` | event: national totals, next to DSWD's own totals. Start here. |
| `impacts` | event × town or city, from each event's latest report |
| `impacts_by_report` | event × report × place, every report and level |
| `events`, `reports`, `unmatched_places` | event, report file, unmatched town spelling |

```sql
-- DuckDB, no download needed
select local_name, event_year, affected_persons, houses_totally_damaged
from 'https://github.com/OrcaDS/sakuna/releases/latest/download/event_summary.parquet'
order by affected_persons desc limit 10;
```

Read these before using the numbers:
- [Data dictionary](docs/data_dictionary.md): every column, and which file to use.
- [Known gaps](docs/known_gaps.md): missing events and reports, and where town rows differ from DSWD's totals.

What the data shows: [insights](docs/insights.md) (repeat-hit towns, storms ranked, time to empty evacuation centres, aid per family, share of towns affected, how much early reports undercount).

## Privacy

This dataset is built from public DSWD DROMIC situation reports. We extract only aggregate counts per region, province and municipality/city. We do not collect, store for publication or share any names or other personal details that appear in the source reports. Original report files are kept privately, only so we can re-check numbers when DSWD revises a report. Contact: open a GitHub issue.

## Source and licences

- Source: DSWD DROMIC situation reports. Cleaned by sakuna. Not an official DSWD product.
- Data tables: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Please credit "DSWD DROMIC situation reports, cleaned by sakuna".
- Code: MIT (see `LICENSE`).
- For 2014–2016, see the HDX "Philippines Typhoon Impact Data 2014–2020" file.

## How it's built

```
DROMIC posts → discover → download (raw files, private) → extract number tables (bronze, Parquet)
  → dbt + DuckDB: typed and matched to PSA's PSGC place codes (silver) → gold tables → release
```

- Reports come as Word files (2017–2022) and PDFs (2021 onward). The extractor reads number tables only, never free text, which is where names appear.
- Town names are matched to official PSGC codes; names that can't be matched are kept with an empty code and listed, never guessed.
- Checks: town rows are summed and compared with each report's own province, region and national totals; 2018–2020 numbers were compared with the HDX file.

## Run locally

```sh
uv sync
uv run pytest -q
uv run sakuna discover     # find events and report files, update raw/manifest.csv
uv run sakuna download     # download pending files into raw/ (add --refresh to re-check old ones)
uv run sakuna extract      # number tables → lake/bronze/
uv run sakuna psgc data/<PSGC xlsx>   # PSA's PSGC file (download by hand from psa.gov.ph)
uv run dbt build --project-dir transform --profiles-dir transform   # silver + gold → lake/sakuna.duckdb
uv run sakuna export       # gold → release/ (CSV + Parquet + docs + checksums)
uv run sakuna update       # all of the above except psgc, in one go
```

A daily check (`scripts/daily_check.ps1`, run by Windows Task Scheduler on the maintainer's PC) opens a `new-reports` issue when report files appear on DROMIC that are not in the latest release's `report_files.csv`. It runs locally because DROMIC does not answer requests from GitHub's servers. It downloads no reports; updates are built with `sakuna update` and published as a new release.

Raw report files stay on your machine (`raw/` is git-ignored) and are never published.
