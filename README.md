# sakuna

The first open, town-by-town history of every Philippine typhoon and monsoon event since 2017, rebuilt from DSWD's own situation reports and kept up to date: affected families and persons, displaced people, damaged houses and aid cost.

**Status:** in development. No data release yet.

## Privacy

This dataset is built from public DSWD DROMIC situation reports. We extract only aggregate counts per region, province and municipality/city. We do not collect, store for publication or share any names or other personal details that appear in the source reports. Original report files are kept privately, only so we can re-check numbers when DSWD revises a report. Contact: open a GitHub issue.

## Source and licences

- Source: DSWD DROMIC situation reports. Cleaned by sakuna. Not an official DSWD product.
- Data tables: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Code: MIT (see `LICENSE`).
- For 2014–2016, see the HDX "Philippines Typhoon Impact Data 2014–2020" file.

## Run locally

```sh
uv sync
uv run pytest -q
uv run sakuna show-config
```
