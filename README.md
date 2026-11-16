# doe-202c-orders

An agent skill and a small offline lookup for U.S. Department of Energy emergency orders under Federal Power Act section 202(c): every order, extension and amendment from May 2025 to 13 November 2026 (88 rows), in one table with the dates each is in force, plus a table of court actions on those orders (41 rows: 37 petitions for review with their docket numbers and status, a brief, the D.C. Circuit's ruling, DOE's rehearing petition and an amicus brief).

By MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no person has checked every row against the order PDFs or the court dockets. Code and skill: Apache-2.0. Tables: CC BY 4.0 (orders transcribed from DOE's public pages; petitions from the court dockets in CourtListener's RECAP archive, joined with the court's opinion, litigation trackers and press releases; summer MW from EIA-860M via PUDL, CC BY 4.0, Catalyst Cooperative). Information, not legal advice.

## What is in it

- [`skills/doe-202c-orders/SKILL.md`](skills/doe-202c-orders/SKILL.md): tells coding agents (Claude Code, Codex, Cursor and others) what the three kinds of order are (plant, event, island), how to run the lookup, and the traps in reading the orders: the table's as-of date, renewals that usually come 0-3 days before expiry, renewals that are issued but not yet in force, orders that name units rather than whole plants, order numbers that do not give the issue year, overlapping event orders, court rulings and petitions that cover one order, not the whole chain, and dispatch wording that differs between orders.
- [`orders_lookup.py`](skills/doe-202c-orders/orders_lookup.py) 0.3.1: standard-library Python, no network. Commands `plant`, `in-force`, `expiring`, `order`, `court` and `summary`, each with `--json`.
- [`doe_202c_orders.csv`](skills/doe-202c-orders/doe_202c_orders.csv): one row per order (`order, kind, area, recipient, plant_key, plant, issued, effective, expires, expires_time, source, note`), as of 16 November 2026.
- [`doe_202c_plant_mw.csv`](skills/doe-202c-orders/doe_202c_plant_mw.csv): for the 8 plants with plant orders, the EIA plant id, the generators the orders cover, fuel and summer MW.
- [`doe_202c_court.csv`](skills/doe-202c-orders/doe_202c_court.csv): court actions on plant orders (`order, plant_key, date, date_kind, court, case, action, status, status_date, source, note`), as of 16 November 2026. One row per petition for review, plus the other actions. `date_kind` is `decided`, `filed`, `first seen` (no filing date on the docket; its earliest entry) or `reported`. `status` is the petition's status in the dockets as read on 19 October 2026 (`decided`, `abeyance`, `briefing`, `no order seen`, `not in archive`). An empty `order` means no source named the order and the plant is inferred. Each row names its source and says what was not checked.
- [`data/doe_202c_renewals.csv`](data/doe_202c_renewals.csv): one row per renewal of a plant or island order, with the days between the new order's issue date and the old order's last day (`lead_days`) and any uncovered days (`gap_days`). It is rebuilt from the orders table by `test_renewal_timing.py`. See [`docs/renewal-timing-plan.md`](docs/renewal-timing-plan.md).
- [`data/doe_202c_applications.csv`](data/doe_202c_applications.csv): for each of the 35 plant orders, whether DOE's page for it lists an application from the recipient, plant owner or grid operator dated on or before the issue date, with the applicant, the date, the page link and the page's "last updated" date. See [`docs/applications.md`](docs/applications.md).

An earlier copy of the orders table (as of 13 November 2026), with an analysis of event episodes and MW-days, and MV2's census of the petition dockets (as of 19 October 2026, `data/doe_202c_petitions.csv`, [`docs/doe-202c-court.md`](https://github.com/munimtechnologies/eia860m-slip/blob/main/docs/doe-202c-court.md)) are kept in [munimtechnologies/eia860m-slip](https://github.com/munimtechnologies/eia860m-slip); the copies here are the newer ones. Other public trackers cover parts of this: [EDF's coal plant mandates page](https://coalcosts.edf.org/mechanisms/202c-orders/) (coal units and costs), [POWER Magazine's order log](https://www.powermag.com/doe-has-issued-more-than-40-section-202c-emergency-orders-since-may-2025-heres-an-updated-log/), and two litigation trackers, the [State Power Project's](https://statepowerproject.org/challenges-to-doe-202c-orders/) and the [State Impact Center's](https://stateimpactcenter.org/insights/tracking-ag-activity-on-department-of-energy-emergency-orders). This table puts each petition next to the order it challenges, so an agent asked about one plant or one order gets its case numbers, dates and status.

## Court actions (0.3.1, 16 November 2026)

The court table has **37 petitions for review**, 35 with a docket number, against the plant orders of seven of the eight plants. They name **14 of the 35 plant orders**. Ten more name no order in the sources we read, so their plant is inferred from the petitioners or from the case they were consolidated with. All are in the D.C. Circuit except Centralia's, which are in the Ninth Circuit. Status is from the dockets as read on 19 October 2026:

| Plant | Orders named | Dockets | Status on 19 October 2026 |
|---|---|---|---|
| J.H. Campbell | 202-25-3, 202-25-7, 202-25-9, 202-26-16, 202-26-22 | 25-1159, 25-1160, 25-1162 (first order); 25-1198, 25-1202, 25-1254 (second); 26-1024, 26-1028 (third); 26-1233 (fifth); a Minnesota and Illinois petition against the fourth order (18 June 2026) has no docket in the archive | first order decided 11 September 2026; second-order cases in abeyance since 18 February 2026; the rest no later order seen |
| Eddystone | 202-25-4, 202-25-8 | 25-1193, 25-1194, 25-1287, 25-1288; 26-1026 and 26-1167 (order not named) | 25-1193 group in abeyance since 26 August 2026 (briefing suspended 11 June); 26-1026 in abeyance since 13 March 2026; 26-1167 no later order seen |
| Centralia | 202-25-11, 202-26-18 | 26-1252, 26-1261 (Ninth Circuit); 26-3781 (order not confirmed); Washington's petition against the second order (11 June 2026) has no docket in the archive | being briefed |
| R.M. Schahfer and F.B. Culley | 202-25-12, 202-25-13, 202-26-19, 202-26-20 | 26-1056 (Schahfer), 26-1057 (Culley), 26-1075 to 26-1078, 26-1158, 26-1159, 26-1186, 26-1187 | all ten consolidated under 26-1056 and in abeyance since 28 July 2026 |
| Craig | 202-25-14 | 26-1059, 26-1060, 26-1101; 26-1255, 26-1256, 26-1273 (order not named) | first three in abeyance since 8 June 2026; the September-October petitions no later order seen |
| Stanton | none named | 26-1224 (Environmental Defense Fund, Florida Rising, Sierra Club; plant inferred) | no later order seen |
| H.A. Wagner | none | none found | |

Only one order has been decided. On 11 September 2026 the D.C. Circuit, in *Michigan v. U.S. Department of Energy*, No. 25-1159, with 25-1160 and 25-1162 ([opinion](https://media.cadc.uscourts.gov/opinions/docs/2026/09/25-1159.pdf)), granted the petitions for review and vacated DOE Order No. 202-25-3, Campbell's first order (23 May to 21 August 2025). That was 414 days after the first petition (24 July 2025) and 386 days after the order had expired. The clerk withheld the mandate the same day. On 26 October 2026, the 45th day after the decision, DOE petitioned for panel rehearing or rehearing en banc ([Sabin Center for Climate Change Law, Climate Litigation Updates, 6 November 2026](https://climate.law.columbia.edu/news/climate-litigation-updates-november-6-2026)), and on 3 November West Virginia and 12 other states filed an amicus brief supporting rehearing ([Sabin Center's climate litigation database](https://www.climatecasechart.com/collections/people-of-the-state-of-michigan-v-u-s-department-of-energy_b08b)). No ruling on the petition was found as of 16 November 2026; Utility Dive reported it still pending that day.

Every order named in a petition has expired, and the orders now in force (Campbell's 202-26-51 and the rest) have no petition naming them in this table. Of the 37 petitions, 21 were in abeyance on 19 October 2026, in five groups, and at least 10 of them by their orders' own words wait on the Campbell decision or its mandate. Only Centralia's three, in the Ninth Circuit, were being briefed.

What joining the docket census to the trackers added: Michigan's petition 26-1078 is matched to Culley's first order (the tracker lists Michigan's Culley petition the same day; Michigan's Schahfer petition is 26-1077). The four-state petitions of 17 July 2026 against Schahfer's and Culley's second orders are matched to 26-1186 and 26-1187, the only two dockets with exactly those four states, but which is which was not confirmed. Two state petitions on the trackers, Washington's against 202-26-18 and Minnesota and Illinois's against 202-26-16, were not in the archive.

Limits: the dockets were read in CourtListener's RECAP archive on 19 October 2026. It holds only what PACER users uploaded, so petitions and orders can be missing, and a status can have changed since. Seven dockets show no filing date, so the table uses their earliest entry (`first seen`). The trackers were last updated in August (State Impact Center) and about late October 2026 (State Power Project). The lookup shows these rows with the order and the plant (`order`, `plant`, `court`). It says plainly that a petition or ruling on one order changes nothing in the in-force dates of the others.

## Who asked for each plant order (applications-1, 15 November 2026)

Of the 35 plant orders, only the 4 for H.A. Wagner Unit 4 have an application listed on DOE's pages, each one from PJM, filed 0-15 days before the order. The other 31 orders, for Campbell, Eddystone, Centralia, Schahfer, Culley, Craig and Stanton, list no application from the recipient, the plant owner or the grid operator; the only document dated on or before each issue date is DOE's order. The 24 renewals that came without an application all left no day uncovered. Wagner, the only chain that starts with a request, is also the only one that lapsed (no PJM application was posted between 10 October 2025 and 21 May 2026). That is a single chain, so it describes the record rather than proving a rule. [`docs/applications.md`](docs/applications.md) has the table, its limits (DOE's pages were read, not the order PDFs) and three predictions about the renewals due by 31 December 2026.

## Renewal timing (pre-registration renewal-timing-1, 15 November 2026)

Of 27 renewals of plant orders, 26 left no day uncovered, and every one of those 26 was issued 0-3 days before the old order's last day (9 on the last day, 10 one day before, 4 two days before, 3 three days before). None was issued late. The exception is Wagner Unit 4, whose order lapsed for 141 days (1 January to 21 May 2026). Since March 2026, every renewal has started the day after the old order ended. Before that, renewals started on the old order's last day. PREPA's island orders follow the same pattern (10 renewals, 0-2 days ahead). Guam's only order ended on 4 November 2026, and no successor was listed on 16 November. [`docs/renewal-timing-plan.md`](docs/renewal-timing-plan.md) states five predictions, made before the outcomes are known, for the orders ending between 17 November (Wagner) and 25 December 2026 (Craig). They will be scored after 28 December 2026.

## Campbell's November 2026 renewal

On 13 November 2026, one day before Order No. 202-26-39 expired, DOE issued [Order No. 202-26-51](https://www.energy.gov/ceser/federal-power-act-section-202c-midcontinent-independent-system-operator-miso-order-no-202-2) to MISO, in coordination with Consumers Energy, for the J.H. Campbell plant in West Olive, Michigan. It is in force from 15 November 2026 through 12 February 2027 (90 days), so Campbell has been under order without an uncovered day since 23 May 2025: seven orders in all. It is the first Campbell order issued since the D.C. Circuit's ruling (above). DOE's page for it says MISO is to employ economic dispatch "only during the hours necessary to meet the emergency"; 202-26-39 said "to minimize costs to ratepayers". Craig's 202-26-49 (25 September 2026) made the same change for Craig Unit 1. Schahfer's and Culley's orders of 18 September 2026 did not, going by DOE's summaries. The lookup records this wording in the `note` column and does not interpret it.

## Use

As an agent skill:

```
npx skills add munimtechnologies/doe-202c-orders
```

Or directly, from the skill folder:

```
python orders_lookup.py plant centralia --date 2026-11-16
python orders_lookup.py expiring --date 2026-11-16 --days 30
python orders_lookup.py in-force --date 2026-01-26 --kind event --json
python orders_lookup.py court
```

On 16 November 2026 the table has 10 orders in force: the 8 plant orders (4,849.9 summer MW, 3,692.9 MW of it coal), with Campbell under 202-26-51, and PREPA's 202-25-1F and 202-25-2F. Wagner's 202-26-25A expires 17 November, Eddystone's 202-26-40 20 November and Stanton's 202-26-42 30 November. At about 20:50 UTC on 16 November, DOE's pages showed no renewal of these and no new Wagner application (the 2026 page was last updated 13 November).

Tests: `python -m unittest -v test_orders_lookup test_renewal_timing test_applications`.

## Updates

The table is updated when DOE posts a new order, and `TABLE_AS_OF` in `orders_lookup.py` moves with it. For any date after the as-of date the lookup prints a warning; check [DOE's 2026 page](https://www.energy.gov/ceser/2026-doe-202c-orders) for newer orders. Corrections are welcome by issue or at mv2@munimtech.com, especially docket numbers, orders and statuses in the court table.

## Changes

- 0.3.1 (16 November 2026): the court table goes from 18 to 41 rows, one per petition for review, by joining MV2's docket census (CourtListener's RECAP archive, read 19 October 2026) to the tracker rows of 0.3.0. There are 37 petitions (35 docket numbers), naming 14 of the 35 plant orders, plus 10 whose order is not named and whose plant is inferred. New columns `status` and `status_date`; new `date_kind` `first seen`; rows with an empty `order`; `plant_key` may be `schahfer|culley`. `court_overview()` now counts petitions, docket numbers and statuses. New row: the amicus brief of West Virginia and 12 other states supporting rehearing (3 November 2026). Corrections to 0.3.0: Schahfer's first order is in No. 26-1056 (0.3.0 said 26-1057, which is Culley's). Michigan's petition No. 25-1159 was filed 24 July 2025, not 25 July, so the ruling came 414 days after the first petition, not 413. Stanton has a petition (No. 26-1224, plant inferred); 0.3.0 said none was found. Petitions name 14 plant orders, not 10. Orders table re-read at about 20:50 UTC on 16 November: no new order since 13 November.
- 0.3.0 (16 November 2026): the court table goes from 2 to 18 rows of petitions for review found on litigation trackers and in press releases. New `court_overview()`; `court` and `summary` report how many plant orders have a petition found and for which plants. Skill trap 8 is rewritten. Orders table re-read on 16 November: no new order since 13 November (`TABLE_AS_OF` 2026-11-16).
- 15 November 2026, later (no release): applications table (`data/doe_202c_applications.csv`, 35 plant orders), [`docs/applications.md`](docs/applications.md) with predictions A1-A3, and `test_applications.py`. The skill and lookup are unchanged.
- 15 November 2026 (no release): renewal-timing table (`data/doe_202c_renewals.csv`), test, and pre-registered predictions (`docs/renewal-timing-plan.md`). The skill and lookup are unchanged.
- 0.2.2 (14 November 2026): Campbell's renewal, Order No. 202-26-51 (issued 13 November, in force 15 November 2026 to 12 February 2027), added; 88 orders, 27 plant renewals (26 with no uncovered day). Fixed `plant`: once a renewal was in the table before its start date, the lookup took the newest order as current and said no order was in force on the old order's last days; it now reports the order in force on the date, plus `next_order`, `next_effective` and `covered_through`. The `note` column records the dispatch wording of 202-26-49 and 202-26-51 ("only during (the) hours necessary to meet the emergency"). Skill traps 3 and 9 are new. Court table re-checked: no ruling on DOE's rehearing petition found as of 14 November.
- 0.2.1 (13 November 2026): DOE's rehearing petition in No. 25-1159 is now dated by its filing, 26 October 2026 (`date_kind` `filed`, source: the Sabin Center's Climate Litigation Updates), instead of by APPA's 30 October report, which is still cited in the note; no ruling on the petition was found as of 13 November. Skill trap 7 and the sources updated.
- 0.2.0 (13 November 2026): court actions table (`doe_202c_court.csv`) with the D.C. Circuit's vacatur of 202-25-3 and DOE's rehearing petition; `court` command; `order` and `plant` show court actions; skill trap 7 rewritten; tables as of 13 November 2026 (DOE's page showed no order issued after 6 November).
- 0.1.0 (November 2026): first release, table as of 8 November 2026.
