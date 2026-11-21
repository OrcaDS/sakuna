# Privacy Impact Assessment: Philippine typhoon impacts dataset

Version 1 · 2026-11-11 · Owner: Kurt (project maintainer) · Review: yearly, or when sources, scope or purpose change (NPC Advisory 2026-01, Sec 3F).

Prepared with Claude's help. It records our reasoning and is not legal advice.

## 1. What we do, and why
- **Purpose:** build an open, town-level history of typhoon and monsoon impacts in the Philippines (affected families and persons, displaced people, damaged houses, aid cost) for research, planning and public understanding.
- **Source:** DSWD DROMIC reports (dromic.dswd.gov.ph, linked Google Docs). About 2,750 report files covering 2017 to now, downloaded once, then only new reports. The HDX "Philippines Typhoon Impact Data 2014–2020" file (aggregate counts only) is used only to check our 2018–2020 numbers and is not published.
- **What we keep for publishing:** numbers per region, province and town, with official PSGC place codes and a link to the source report. No names, ages, addresses or barangay-level rows.

## 2. What personal data is involved
- The **number tables we publish** are aggregate counts. They are not personal information (DPA Sec 3(g); NPC AO 2017-027).
- The **raw report files** we download contain names in their free text: barangay captains, DSWD and LGU staff, and the officials who sign. These are government officers named in their official role, which the DPA excludes from its scope (Sec 4(a)). Reports may occasionally name private people (for example, in incident notes).
- **No sensitive personal information** (health, age, religion and similar) is extracted.

## 3. Lawful basis
- Our published output contains no personal data.
- For handling the raw files: the officials' names fall outside DPA scope (Sec 4(a)). Any other names are covered by the research exemption, limited to the minimum needed (Sec 4(d)), and by legitimate interest as a fallback (Sec 12(f)). The data was published by a government agency for public information. We read it only to extract numbers.

## 4. Risks and what we do about them
| Risk | Likelihood / harm | What we do |
|---|---|---|
| Names in raw files get re-published | Medium / medium | Raw files are **never published** or committed to git. The parser reads number tables only and never reads free text. |
| A small count points to a household (e.g. "1 family affected" in a small town) | Low / low | Town level only, never barangay. Disaster impact is already public through DSWD. We accept this residual risk for v1 counts. |
| Combining with other data (census, poverty) identifies someone | Very low / low | Every join happens at town level or above, never at person level. |
| Future casualty data (v2, NDRRMC) is more sensitive | Medium / high | Counts per town only, never per-person rows. Names are dropped while parsing. Groups smaller than 3 are rolled up. This assessment gets updated before v2 starts. |
| Unauthorized scraping (Advisory Sec 4) | Low / — | We follow robots.txt (DROMIC only blocks /wp-admin/) and terms of service. We never bypass blocks: sites that refuse scripts (NDRRMC, PSA, NPC) are skipped or downloaded by hand. Polite rate: at most 6 parallel requests, with retries and back-off. |
| Raw files kept too long (Sec 6E) | Low / low | Kept only to re-read reports that DSWD revises, sometimes years later. Stored on the maintainer's computer only. Deleted if the project stops. |
| Bias in use (Sec 7C) | Medium / low | We document gaps: coverage starts in 2017, some 2017 reports are unavailable, and reports change over time. |

## 5. Privacy notice (to publish in the README)
> This dataset is built from public DSWD DROMIC situation reports. We extract only aggregate counts per region, province and municipality/city. We do not collect, store for publication or share any names or other personal details that appear in the source reports. Original report files are kept privately, only so we can re-check numbers when DSWD revises a report. Contact: open a GitHub issue.

## 6. Review log
- 2026-11-11: first version.
- 2026-11-21: v1 scope narrowed to DROMIC 2017 → now; HDX no longer published (used only as an accuracy check). No change to risks.
