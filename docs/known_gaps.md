# Known gaps

What this dataset does not cover, and where its numbers differ from DSWD's own totals. Read this before drawing conclusions.

## Coverage

- **Starts in January 2017.** For 2014–2016, see the HDX "Philippines Typhoon Impact Data 2014–2020" file.
- **Typhoons, tropical storms, tropical depressions and the southwest monsoon only.** No earthquakes, floods from other causes, or other hazards.
- **No casualties** (dead, injured, missing). DSWD's reports don't carry them by town; NDRRMC's do, but they name the victims.
- **Town level is the lowest level.** No barangay rows.

## Events missing from the release

DROMIC has 144 posts for 143 events (Odette 2021 is split over two posts); 128 events are in the release. The other 15:

| Why | Events |
|---|---|
| Only "Preparedness for Response" reports, written before landfall (pre-emptive evacuation, not impact) | Quedan 2017, Ramil 2017, Tino 2017, Paeng 2018, Marilyn 2019, Sarah 2019 |
| Report files no longer online (dead Google Docs links) | Bising 2017, Gorio 2017, Isang 2017, Jolina 2017 |
| The only impact report has no town table we can read | Kiko 2017, Nando 2017, Lannie 2017, Siony 2020 |
| Merged by DSWD into another event | Southwest Monsoon in Mindanao, Jul 2026 (counted under Kiyapo) |

## Report files we could not get

60 of 2,823 report files: 43 dead Google Docs links (HTTP 410), 10 that need a Google sign-in (401), 4 removed from DROMIC (404), and 3 on Google Drive, which robots.txt does not allow scripts to download. 56 of them are from 2017 and 2018. Most are earlier reports of events that still have a later report, so the event is in the release but its report-by-report history has holes.

## Numbers that change

- **DSWD revises reports for months or years.** Egay 2023 got its final report in February 2026. Events with `is_terminated = false` are still open and will change in later releases.
- **Day-1 reports undercount.** `impacts` uses the latest report; use `impacts_by_report` to see earlier figures.

## Where town rows and DSWD's totals differ

For 123 of 128 events, the sum of town rows is within 1% of DSWD's own GRAND TOTAL for affected families. The other 5:

| Event | Town rows | DSWD total | Why |
|---|---|---|---|
| Southwest Monsoon, Jul 2017 | 2,782 | 4,558 | DSWD's province and region rows are higher than the towns the report lists. |
| Southwest Monsoon + TD Karding, Aug 2018 | 475,277 | 434,573 | Central Luzon's town rows add up to 41,012 more than DSWD's Central Luzon total. |
| Ramon, Nov 2019 | 11,549 | 10,855 | DSWD's CAR total leaves out Kalinga. |
| Flooding in Sarangani and Maguindanao del Sur, Jul 2024 | 133,981 | 179,229 | The Special Geographic Areas of BARMM (45,248 families) have a total but no town rows. |
| Southwest Monsoon + TS Isang, Aug 2025 | 22,539 | 26,400 | BARMM (3,861 families) has a total but no town rows. |

Smaller mismatches between towns, provinces and regions inside a report are DSWD's own (for example, some reports count highly urbanised cities in the province total and others only in the region total). We keep DSWD's numbers as they are.

In about 7% of event × town rows, DSWD's affected persons are higher than the town's 2024 census population (for example Mariveles, Bataan, 2023: 335,487 affected, 156,200 residents). These are DSWD's figures; see [insights](insights.md#5-what-share-of-a-towns-people-is-affected).

## Cost of assistance

Town cost totals are often lower than DSWD's national cost. Some aid goes to provincial governments (PLGU) or is given only as a province figure, not per town. Those lines are in `impacts_by_report` with `level = 'other'`. Tisoy 2019's Region II cost row repeats one town's figure.

## Place names

- 31 town spellings have no PSGC code (276 rows across all reports). They are listed in `unmatched_places` with an empty `psgc_code` in the data. We don't guess. 24 of them come from one report (Agaton 2022) that lists towns under the wrong province.
- San Isidro, Davao del Norte, is now called Sawata. PSGC keeps no record of the old name, so its 7 rows are unmatched.
- Codes and names are PSA's current PSGC. Towns that moved province or were renamed are shown under today's name.
