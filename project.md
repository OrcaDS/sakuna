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
- Formats (checked 2026-11-21): two file types, told apart by their first bytes, not the file name (some names were cut before the extension). **.docx** 2017–2022 (1,014 files) and **PDF** 2021–2026 (1,820 files); no old .doc. Within each type the layout barely changes, so there are two readers (`docx_reader`, `pdf_reader`) sharing one set of header rules (`extract`).
- "Preparedness for Response" reports (written before landfall: pre-emptive evacuations, not impacts) are skipped (Kurt, 2026-11-21): 112 files; 7 events have only these.
- Five tables per report: affected, displaced inside ECs, displaced outside ECs, damaged houses, cost of assistance. 2017–2018 put inside and outside ECs in one table (`displaced`). Town rows sit in annexes (2017 "Annex A–D"; Ompong with extra columns such as 2015 population and "returned home"; 2019–20 the main tables are already town-level).
- **Match tables and columns by header keyword, never by position.** Headers span 2–4 rows (CUM / NOW columns). A table counts only if a header cell starts with REGION (the place column), which keeps free-text tables out. If several copies of a table match, take the one with the most rows.
- PDF tables run over many pages: pieces of the same kind are joined until a new GRAND TOTAL row starts another copy. Headers are usually repeated per page; a page without one continues the table before it.
- Row levels: GRAND TOTAL → region → province → town. Word: a province fills the first name cell (spanning 2 columns), a town leaves it empty. PDF: regions and provinces are bold (and shaded), towns are not. Region vs province is decided by name (REGION …, NCR, CAR, CARAGA, MIMAROPA, CALABARZON, BARMM, NIR). NCR cities sit directly under the region and come out as "province": silver fixes that.
- Bronze: one Parquet file per report (`lake/bronze/<sha256>.parquet`), one row per table cell: sha256, kind, row_no, level, name, column (header path, e.g. `NUMBER OF AFFECTED > Families`), value. Cell text is kept exactly as read; typing and the header → gold column mapping happen in silver. `lake/bronze/_log.csv` lists each file's status (ok / empty / failed), row counts per table and dropped rows.
- The extractor reads tables only. It never stores free text (names live there): rows with no number cells (table notes) are skipped, and a row with a value longer than 40 characters or a name longer than 100 is dropped and counted.

### 5.3 Silver and gold (dbt)
- Numbers: `1,017` / `1017` → 1017; `-` → 0. Empty → NULL.
- PSGC matching: normalise (accents, "City of", "(capital)", Sta./Sto./Gen.), apply `place_aliases.csv` (seed), then look up the town within its province → region → unique nationwide. An alias whose DSWD spelling contains "City" or brackets applies only to rows that contain them too ("City of Viga" ≠ the town Viga). Unmatched rows are kept with a NULL code and listed in gold `unmatched_places`; never guessed.
- Fallback check (2026-11-24): region/nationwide matches that land outside the province DSWD lists them under were reviewed; the rest are DSWD layout (missing province header rows, ICCs such as Cotabato City). Known miss: San Isidro, Davao del Norte (renamed Sawata, no old name in PSGC; 7 rows).
- Row level comes from PSGC, not bold font: total, region, province, town, `group` (sub-headers with no code: Metro Manila, Maguindanao before 2022; seed `place_groups`) and `other` (aid lines, not places: PLGU, "District" rows, legislators' lines, rows DSWD left unnamed). `other` rows stay in `impacts_by_report` but are not towns.
- Privacy in SQL: a legislator's title and name (Cong./Rep./Hon. …) is cut from aid lines; dbt test `no_official_names` fails if one gets through. Names are never listed in a seed (seeds are public).
- HUCs and ICCs: DSWD counts them in the province total in some reports and only in the region total in others; checks accept both. `province_code` is PSGC's (HUCs have none); sums use the province DSWD lists the row under.
- Evacuation columns: DSWD gives CUM (everyone who stayed) and NOW (still there). `impacts_by_report` keeps both; `impacts` and `event_summary` use CUM.
- One event split over two DROMIC posts (Odette 2021 "archives") is merged by seed `event_merges`.
- v1 uses the **latest report per event**: terminal report first, then latest date, then highest number. All reports are kept, for insight 3 and insight 6.
- **Accuracy checks**:
  1. dbt test `sum_check` (warn): town rows add up to each report's own province, region and grand totals. Remaining gaps are DSWD's own tables (6,587 rows as of 2026-11-24).
  2. HDX 2018–2020 (done 2026-11-24, `docs/research_scripts/hdx_*.py`): all 11 overlapping typhoons; town rows 99% identical to the same DSWD report; gaps come from HDX using earlier, later-revised reports. No parser bug.
  3. `event_summary` sits next to DSWD's own GRAND TOTAL: 123/128 events within 1% on affected families. Cost: town sums are lower than DSWD's total in 42 events because aid to provinces and PLGUs is not given per town (in `other` rows, or only in the province total); 32 close exactly with `other` rows, the rest are DSWD-side errors (e.g. Tisoy 2019 Region II row copies one town).

### 5.4 Gold tables

| Table | One row per | Main columns |
|---|---|---|
| `events` | event | event_id, local and international name, type, year, start date, n_reports |
| `reports` | report file | event_id, report_no, report_date, is_terminal, source_url, is_latest |
| `impacts` | event × town (latest report) | event_id, report_no, report_date, psgc_code, region, province, town, dswd_name, match_rule, affected_brgys, affected_families, affected_persons, inside_ec_count, inside_ec_families, inside_ec_persons, outside_ec_families, outside_ec_persons, houses_totally_damaged, houses_partially_damaged, cost_dswd, cost_lgu, cost_ngo, cost_other, cost_total, has_repeated_rows, n_unreadable, source_url |
| `impacts_by_report` | event × report × place | same counts for every report and every level (total, region, province, town, group, other), with CUM and NOW evacuation columns |
| `event_summary` | event | national totals from `impacts` next to DSWD's own GRAND TOTAL (`dswd_` columns), n_towns, n_unmatched_towns: the table most people will want |
| `unmatched_places` | town spelling with no PSGC code | region, province, dswd_name, n_events, example event and URL |

Counts are numbers of families/persons/houses; costs are PHP. `has_repeated_rows`: DSWD listed the place twice in one table and the rows were added up. `n_unreadable`: cells that were not a clean number (counted as NULL). Town cost sums are lower than the national cost because some aid goes to provinces, not towns (see §5.3).

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
- Known gaps to document: starts in 2017 (for 2014–2016 see the HDX "Philippines Typhoon Impact Data 2014–2020" file), dead 2017 links (Jolina, Isang, Bising), reports revised later (Egay 2023 got its final report in Feb 2026); events DSWD reported only as a region or group total (Isang 2025 BARMM, Sarangani 2024 SGA); DSWD totals that don't match their own rows (Ramon 2019 CAR omits Kalinga, Tisoy 2019 Region II cost, 2017 SW monsoon flood); the 31 unmatched town spellings; aid given to provinces rather than towns.
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
