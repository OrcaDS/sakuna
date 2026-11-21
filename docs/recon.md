# sakuna: NDRRMC disaster reports, recon

*First look, 2026-11-11. Based on 5 sample reports (2020, 2021, 2024, 2025, 2026) and checks of where reports can be downloaded.*

## 1. What the data is today

NDRRMC (National Disaster Risk Reduction and Management Council) publishes a **Situational Report ("SitRep")** for every major disaster: typhoons, monsoon floods, earthquakes and more. A disaster gets a numbered series (SitRep No. 1, 2, 3 …), often one or two a day, until a **final report** closes it.

Each report is a **PDF of 20–200 pages**. There's no spreadsheet, API or history table. To answer "how many families did typhoons affect in Region 8 since 2020?", someone today has to open hundreds of PDFs by hand.

### What's inside one report (2026 example: TC Kiyapo, SitRep No. 7, 67 pages)

| Section | What it holds | Detail level |
|---|---|---|
| Narrative (p. 2) | storm track, landfall, dates | text |
| Summary tables (p. 3–5) | totals per region for every section below | region |
| Related incidents | floods, landslides, uprooted trees, with date and description | city/municipality |
| **Affected population** | barangays affected; families and persons inside and outside evacuation centers, each as cumulative ("CUM") and current ("NOW") | **barangay** |
| Casualties | dead, injured, missing | region → person (see §4) |
| Damaged houses | totally / partially damaged, cost | city/municipality |
| Roads, bridges, ports, airports | status (passable / not passable, suspended), dates | individual road or port |
| Power, water, communication | interruptions and restorations, with dates | city/municipality |
| Class / work suspensions | levels suspended, dates | city/municipality |
| Agriculture & infrastructure damage | area, farmers affected, cost in PHP | region / province |
| Assistance provided | relief goods and their cost | region |

Example: the main table, as text extracted from the PDF (2026):

```
REGION | PROVINCE | CITY/MUNICIPALITY | BARANGAY   Brgys  Families(CUM NOW)  Persons(CUM NOW) ...
GRAND TOTAL                          300 484  94,876 451,434  177 81  9,504 7,564 ...
REGION 1                               4  77   3,020   8,180   18  0 ...
ILOCOS NORTE                           4  77   3,020   8,180 ...
Batac                                  1  33   1,334   3,813    4  0 ...
```

## 2. How the format changed over time

| Year | Sample | Pages | Text layer? | Layout |
|---|---|---|---|---|
| 2020 | Ambo #13 | 82 | **Partly**: first 4 pages are images; tables have text | Older layout. Mixes portrait and landscape pages, lists injured people by name |
| 2021 | Jolina #7 | 97 | Yes | Current layout: summary pages, then one landscape table per section |
| 2024 | Carina #13 | 199 | Yes | Same as 2021, more sections (validated vs. for-validation counts, assistance) |
| 2025 | Tino #14 | 20+ | Yes | Same family |
| 2026 | Kiyapo #7 | 67 | Yes | Same family; header text identical to 2021 |

**Good news:** from 2021 on, the layout looks stable: same section titles, same column headers. One extractor per section could cover five-plus years. 2020 and earlier need checking.

## 3. Where to get the reports

| Source | Access | Coverage | Notes |
|---|---|---|---|
| **ndrrmc.gov.ph** (official) | ❌ **Blocks automated downloads** (Cloudflare bot check) | All | Can still be browsed by hand. The main risk for a daily pipeline |
| **ADINET** (ASEAN disaster info network, adinet.ahacentre.org) | ✅ Direct PDF downloads work | Copies of NDRRMC SitReps, at least 2021–2026 seen | Best automatic source found so far. Need to find how its listing works |
| **archive.org** | ✅ Works | 2020 season: 118 PDFs (about 59 reports, plus OCR'd copies); one 2021 item | Good for history, but patchy |
| **ReliefWeb** (UN) | ⚠️ API needs a free registered app name | Likely many years | Request an app name; no cost |
| **FOI request** (foi.gov.ph) | Manual | Could get bulk history | Slow, but legitimate for backfill |

## 4. Problems to plan for

1. **Reports revise each other.** SitRep No. 7 replaces No. 6's numbers. The final report per event is the one to trust. Keep every report in bronze (raw) anyway: the changes over time are themselves interesting (how fast counts grow).
2. **"CUM" vs "NOW" columns.** Cumulative (ever affected) vs. currently in evacuation centers. Both must be kept and clearly labelled, never mixed.
3. **Personal data.** The 2020 casualty tables list **names, ages and home addresses** of injured and dead people. The published dataset must contain **counts only, never names**. Bronze can keep the raw text (it's not published), but silver must drop name columns.
4. **Place names.** Barangay and town names are typed by hand ("Batac", "CLUSTER PIKIT II", Bangsamoro "clusters"). They need mapping to official PSGC codes; that's the "places crosswalk" idea, which this project would need anyway.
5. **Combined events.** One report can cover several storms at once ("Southwest Monsoon and TC Kiyapo", "Butchoy and Carina"). The event table must allow that.
6. **Messy tables.** Region, province, town and barangay rows are mixed in one table, told apart only by capitals or indentation. Rows repeat (a town line, then the same numbers again without the name). This is the same kind of work as the DA price matrices in tawad.
7. **Validated vs. for-validation** counts (2024+): keep both.
8. **Older years** (before 2020): format unknown; may be scans needing OCR.

## 5. What we aim for

**Goal:** the first clean, open, machine-readable history of Philippine disaster impacts, loadable in one line by any developer or analyst.

### Version 1 scope (keep it small)

- **Disasters:** tropical cyclones and monsoon events, **2021 to now** (the stable layout).
- **Sections:** the four most useful only:
  1. affected population (barangay level)
  2. casualties: counts, plus de-identified details (age band, sex, injury/cause, town). **Never names** (see "Personal data" below)
  3. damaged houses
  4. agriculture and infrastructure damage cost
- **Final values per event** plus the full report-by-report history.

### Personal data (PII) and casualty details

Casualty tables are in scope: they show *what* hurts people in disasters (drowning, landslides, falling trees, electrocution) and *who* (age, sex). Only **de-identified** details are published. Three layers:

1. **Allowlist, not blocklist.** Each casualty extractor keeps only approved columns (age, sex, casualty type, injury/cause, town). Name, middle name, surname and address columns are never copied past bronze.
2. **PII detection on free text.** Columns like Description, Remarks and Actions Taken can contain names ("Juan dela Cruz, 45, drowned"). They're scanned by a detector (candidate: Microsoft Presidio, free and open source, plus patterns for Filipino name forms, "Brgy."/"Purok" addresses, phone numbers). A hit **flags the row for review**; it's never trusted as clean automatically. English-trained models are weak on Filipino names, so it's tested on a hand-labelled set of real rows first.
3. **No re-identification through details.** Even without names, "male, 41, punctured wound, Brgy. Carolina" can point to one person. Published casualty rows use **age bands** (0–4, 5–17, 18–59, 60+), location at **town level** (not barangay or street), and groups smaller than an agreed minimum (e.g. fewer than 3 people) are rolled up.

**Consequence for storage:** bronze (raw PDFs and raw text) contains names, so unlike tawad's public `lake` release, **sakuna's raw data can't be public**. Where the pipeline keeps its private state (free tier) is an open decision; see §6.

Also check: how the Data Privacy Act (RA 10173) and NPC guidance treat publishing de-identified casualty data.

### Planned output tables (gold)

| Table | One row per | Main columns |
|---|---|---|
| `events` | disaster | event id, name(s), local + international name, type, start / end date, number of reports |
| `reports` | SitRep | event id, report no., date and time, source URL, is_final |
| `affected_population` | event × report × place | PSGC code, place names, families / persons (cum + now), inside / outside evacuation centers |
| `casualties` | event × report × place | dead, injured, missing (counts only) |
| `casualty_details` | event × de-identified person | casualty type (dead/injured/missing), age band, sex, injury or cause, town (PSGC), validated or not. **No names, exact ages or addresses** |
| `damaged_houses` | event × report × place | totally, partially, cost (PHP) |
| `damage_cost` | event × report × region × sector | agriculture / infrastructure cost (PHP) |
| `event_summary` | disaster | final totals: the table most people will want |

### How it's published (same pattern as tawad)

- CSV + Parquet on GitHub Releases, mirrored on Hugging Face so DuckDB can query it directly
- data dictionary (what each column means) and known gaps, written in plain English
- automated runs: check for new reports daily during typhoon season
- tech stack: copy tawad's (Python, pdfplumber, dbt + DuckDB, GitHub Actions, free tiers only)

### Who it's for

Developers and analysts building disaster dashboards or models; researchers; newsrooms that want "worst-hit provinces since 2021" without opening 1,000 PDFs.

### Not in version 1

Earthquakes and other disaster types · reports before 2021 (and any OCR) · roads, power, ports, class suspensions · maps / dashboard (later, as a demo like tawad's)

## 6. Open questions (next recon steps)

1. **How to list all reports automatically?** Check ADINET's search pages and request a ReliefWeb app name. Without a reliable list, there's no pipeline.
2. **How many events and reports exist from 2021 to now?** This sets the size of the job.
3. **Do the 2021–2026 section headers really stay identical?** Check 10–20 reports, not 5.
4. **Licence / terms** of NDRRMC data and of ADINET's copies, so the open release is on safe ground.
5. **Where does private bronze live, for free?** Options to compare: a private GitHub repo's release, a private Hugging Face dataset, or a free cloud bucket. Must stay non-public and cost nothing.
6. **Which free-text columns actually contain names, and since when?** Sample casualty and incident tables across 2020–2026 to size the PII-detection job and build the labelled test set.
7. ~~Does someone already publish this?~~ Checked 2026-11-11 (web search only; datasets not opened). See §7.

## 7. Existing datasets (checked 2026-11-11)

| Dataset | Covers | Level | Maintained? |
|---|---|---|---|
| [Philippines Typhoon Impact Data 2014–2020](https://data.humdata.org/dataset/philippines-typhoon-impact-data-2014-2020/resource/70fb3b7a-078c-40c7-b601-0b265a6c71df) (HDX, likely Red Cross 510) | people affected, houses damaged, from NDRRMC + DSWD reports | municipality (to confirm) | **No: stops at 2020** |
| [DSWD Municipality Tropical Cyclone Dataset](https://b2find.eudat.eu/dataset/51e42f00-cbf9-5b3f-bd34-462ca58b29b9) | building damage, 39 cyclones | municipality | No, one-off research release |
| [Province-level TC impacts 2010–2020](https://link.springer.com/article/10.1007/s11069-025-07394-x) (Springer, 2025) | deaths, affected, housing damage, losses | province | No |
| [510 typhoon impact model](https://www.github.com/rodekruis/Typhoon-Impact-based-forecasting-model) | uses NDRRMC/DSWD damaged-house counts to validate predictions | municipality | Model code, not a public impact dataset |
| [DSWD DROMIC reports](https://dromic.dswd.gov.ph/) | affected families / persons | barangay | PDFs only, no bulk download |

**Conclusion:** nothing maintained covers 2021 onward, and none has casualty details or report-by-report history. **Position sakuna as the continuation:** match the HDX 2014–2020 columns where possible, so existing users get 2021+ with no extra work. Next: open that HDX file and compare its columns and licence.
