# Project: sakuna, Philippine typhoon impacts

> Brief for Claude. Read it by section before writing code. If the real data contradicts it, trust the data, tell Kurt, and propose an edit to this file.
>
> v1.1 (2026-11-21): scope narrowed to DROMIC 2017 → now (`docs/superpowers/specs/2026-11-21-scope-2017-onward-design.md`). Evidence: `docs/recon.md` (NDRRMC recon; its §5 scope is **superseded** by this file), `docs/pia.md` (privacy), `HANDOFF.md` key findings (DROMIC layouts, PSGC matching).

## 1. What this is

The first open, town-by-town history of every Philippine typhoon and monsoon event since 2017, rebuilt from DSWD's own situation reports and kept up to date. It covers affected families and persons, displaced people, damaged houses and aid cost, with no personal data. Anyone should be able to load it in one line (CSV or Parquet; DuckDB reads it straight from a URL).

**The problem:**
- The data exists: for each storm, DSWD publishes affected families, displaced people, damaged houses and aid cost for every town.
- It's buried: about 2,750 reports since 2017, in Google Docs, Word and PDF, with layouts that change and numbers revised for years.
- Nobody keeps a clean copy: the only open dataset (HDX "Philippines Typhoon Impact Data 2014–2020") stopped in 2020, and NDRRMC blocks downloads and names victims.
- So researchers, LGUs, NGOs and newsrooms can't easily compare storms, find repeat-hit towns, or see how long evacuations last.

sakuna picks up where the HDX file stopped. It's dataset #2 in Kurt's aim to make Philippine data accessible (tawad was #1) and it's also a portfolio project, so code quality, tests and docs matter.

Free tiers only: nothing may cost money.

## 2. Questions the gold tables must answer

1. **Repeat-hit towns:** which towns are hit most often, and hardest, since 2017?
2. **Storms ranked by human impact:** affected persons, displaced persons, damaged houses.
3. **Time to empty evacuation centres:** how many days until the people inside ECs reach zero (uses every report for an event, not only the last).
4. **Aid per affected family** by region, alongside poverty data.
5. **Share of town population affected** (with census population).
6. **How much day-1 reports undercount** compared with the final report.

## 3. Sources

| Source | Years | Level | How we get it |
|---|---|---|---|
| DSWD DROMIC situation reports (dromic.dswd.gov.ph + linked Google Docs) | 2017 → now | town | Script. robots.txt only blocks `/wp-admin/`. 144 events and 2,823 report files on 2026-11-21 (the research list `docs/dromic_report_files_2017-2026.json` had 143 and 2,749 and missed files in combined posts) |
| HDX "Philippines Typhoon Impact Data 2014–2020" (`data/typhonn-impacts.xlsx`) | 2018–2020 | town? (confirm at milestone 4) | Already downloaded by hand (HDX blocks scripts). **Accuracy check only, never published** (§5.3) |
| PSA PSGC (official place codes) | current | all | Kurt downloads the .xlsx by hand (psa.gov.ph blocks scripts). Fallback for checks: psgc.gitlab.io/api |
| PSA census population, poverty stats | latest | town / province | Later, for insights 4–5. Hand download |

Not in v1: NDRRMC (blocks downloads, and its casualty tables carry names), earthquakes and other hazards, anything before 2017. Possible add-ons later: HDX 2014–2016 as-is, and DSWD's 2015–2016 town data if the optional eFOI request (`docs/foi_request_dswd_2015-2016.md`) is ever answered. Nothing waits on either.

## 4. Tech stack

Same as tawad: Python 3.11+ with uv · pdfplumber (PDFs) · stdlib zipfile + XML for .docx · pyarrow Parquet · dbt Core + dbt-duckdb · pytest · ruff · GitHub Actions. Ask Kurt before adding anything else.

## 5. Pipeline

```
DROMIC posts ─▶ discover ─▶ download ─▶ RAW FILES (private, local only, never committed)
                                              │ extract: number tables only, never free text
                                              ▼
                                        BRONZE  rows as text + source URL (Parquet)
PSGC xlsx ────────────────────────────────────┤
                                              ▼
                               dbt + DuckDB: SILVER (typed, PSGC-matched) ─▶ GOLD
HDX xlsx 2018–20 ─▶ accuracy check against silver (never published)
                                              ▼
                               CSV + Parquet + data dictionary on GitHub Releases
```

### 5.1 Discover and download
- List posts per year and keep titles matching `Typhoon|Tropical Storm|Tropical Depression|Southwest Monsoon|Habagat`, excluding "Intertropical". Hazard categories on the site are unreliable.
- Handle duplicate posts (Karen 2016 is also listed under 2017), combined posts, and events that cross a year.
- Posts are listed from the HTML year pages (`/category/situation-reports/{year}/page/N/`); the WordPress REST API needs a login, so it is not used. The event year comes from the date in the title (category 2016 holds Auring, 07 Jan 2017).
- Google links: `docs.google.com/document/d/{id}/export?format=docx`, one request per second (Google's robots.txt crawl delay). Drive file links (`/file/d/{id}`, 3 files) are blocked by robots.txt on every download route: status `manual`, Kurt downloads them by hand. 2021 posts wrap DROMIC files in `docs.google.com/viewer?url=…`: unwrap them. Some Google Docs are dead (HTTP 410; 2017 Jolina, Isang, Bising): mark them failed, don't drop them.
- A downloaded file must start like a PDF, .docx or .doc; anything else (e.g. a Google sign-in page) is marked failed.
- Politeness: at most 6 parallel requests, 60 s timeout, 3 retries with back-off. Never bypass a block (NPC Advisory 2026-01 Sec 4).
- A manifest keeps one row per report file (event, report number, date, URL, hash, status). DSWD revises reports for years, so files are re-downloaded and rows are never deleted.

### 5.2 Extract → bronze
- Formats: 2017 Google Docs only; 2018 mixed; 2019–21 mostly .docx; 2022+ PDF.
- Five tables per report: affected, displaced inside ECs, displaced outside ECs, damaged houses, cost of assistance. Town rows sit in annexes (2017 "Annex A–D"; 2018 Ompong unlabelled after the signatory, with extra columns and cost split in 2 tables; 2019–20 the main tables are already town-level).
- **Match tables and columns by header keyword, never by position.** Headers span 2–3 rows. If several tables match, take the one with the most rows.
- Row levels: GRAND TOTAL → region → province (first cell spans 2 columns) → town (empty first cell, name in the second). NCR cities sit directly under the region.
- Bronze keeps cell text exactly as read; typing happens in silver.
- The extractor reads tables only. It never stores free text (names live there).

### 5.3 Silver and gold (dbt)
- Numbers: `1,017` / `1017` → 1017; `-` → 0. Empty → NULL.
- PSGC matching: normalise (accents, "City of", "(capital)", Sta./Sto./Gen.), apply `place_aliases.csv` (seed), then look up the town within its province → region → unique nationwide. The test gets 99.4% matched (`docs/research_scripts/match.py`). Unmatched rows are kept with a NULL code and listed; never guessed.
- Check that the nationwide fallback never picks the wrong town of the same name (not verified yet).
- v1 uses the **latest report per event**. All reports are kept, for insight 3 and insight 6.
- **Accuracy checks** (dbt tests; tolerances set at milestone 4):
  1. Town rows add up to each report's own province, region and grand totals (every year).
  2. Our 2018–2020 event totals match the HDX file. A big gap points to a parsing bug.

### 5.4 Gold tables

| Table | One row per | Main columns |
|---|---|---|
| `events` | event | event_id, local and international name, type, year, start date, n_reports |
| `reports` | report file | event_id, report_no, report_date, source_url, is_latest |
| `impacts` | event × town (latest report) | event_id, psgc_code, region, province, town, affected_brgys, affected_families, affected_persons, inside_ec_count, inside_ec_families, inside_ec_persons, outside_ec_families, outside_ec_persons, houses_totally_damaged, houses_partially_damaged, cost_dswd, cost_lgu, cost_ngo, cost_other, source_url |
| `impacts_by_report` | event × report × place | same counts as `impacts`, for every report |
| `event_summary` | event | national totals from `impacts`: the table most people will want |

Counts are numbers of families/persons/houses; costs are PHP.

## 6. Privacy (from `docs/pia.md`; that file wins)
- Publish only number tables plus source URLs. Never names, exact ages, addresses or barangay-level rows.
- Raw report files stay private: local only, git-ignored, never uploaded. Kept so revised reports can be re-parsed; deleted if the project stops.
- v1 counts are not rolled up (Kurt: town counts identify no one).
- Joins with census or poverty data happen only at town level or above.
- v2 (NDRRMC casualties): counts per town only, names dropped at parse time, groups smaller than 3 rolled up. **Update the PIA before v2 starts.**
- README carries the privacy notice from PIA §5.

## 7. Publishing
- GitHub Releases: gold as CSV + Parquet + data dictionary + known gaps, in plain English.
- Attribution: "Source: DSWD DROMIC situation reports. Cleaned by sakuna. Not an official DSWD product."
- Known gaps to document: starts in 2017 (for 2014–2016 see the HDX "Philippines Typhoon Impact Data 2014–2020" file), dead 2017 links (Jolina, Isang, Bising), reports revised later (Egay 2023 got its final report in Feb 2026).
- Automation (later): a scheduled GitHub Action checks for new reports during typhoon season. Raw files can't go to a public release; where the scheduled run keeps them is decided at that milestone.

## 8. Milestones
Stop at the end of each one, summarise, and wait for Kurt's review.

1. **Skeleton:** git repo, uv, config, `.gitignore` (raw files, data), ruff, pytest, CI on an empty test suite.
2. **Discover + download:** manifest of all events and report files 2017 → now; full raw download kept local.
3. **Extract → bronze:** one extractor per format era, with tests on fixture files that contain no names.
4. **Silver + gold:** dbt models, PSGC matching with the alias seed, both accuracy checks (§5.3), dbt tests.
5. **Publish:** first open-data release + README with the privacy notice.
6. **Insights:** the six questions in §2, written up with charts.
7. **Automation:** scheduled updates.

## 9. Ask Kurt rather than assume
- Anything that publishes: a release, a push, a public repo.
- Creating any cloud resource or anything that could cost money.
- New dependencies beyond §4.
- Ambiguous place matches, and events that might be duplicates or combined.
- Licence: output tables CC BY 4.0 (Kurt, 2026-11-21); code MIT (same as tawad).
- DROMIC terms of service: checked 2026-11-21. DROMIC has no terms page; robots.txt only blocks `/wp-admin/`; the DSWD privacy policy covers visitor data only; government works carry no copyright (IP Code Sec 176).
