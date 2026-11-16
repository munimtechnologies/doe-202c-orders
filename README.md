# doe-202c-orders

An agent skill and a small offline lookup for U.S. Department of Energy emergency orders under Federal Power Act section 202(c): every order, extension and amendment from May 2025 to 13 November 2026 (88 rows), in one table with the dates each is in force, plus a table of court actions on those orders (18 rows: petitions for review, a brief, the D.C. Circuit's ruling and DOE's rehearing petition).

By MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no person has checked every row against the order PDFs or the court dockets. Code and skill: Apache-2.0. Tables: CC BY 4.0 (orders transcribed from DOE's public pages; court actions from the court's opinion, litigation trackers and press releases; summer MW from EIA-860M via PUDL, CC BY 4.0, Catalyst Cooperative). Information, not legal advice.

## What is in it

- [`skills/doe-202c-orders/SKILL.md`](skills/doe-202c-orders/SKILL.md): tells coding agents (Claude Code, Codex, Cursor and others) what the three kinds of order are (plant, event, island), how to run the lookup, and the traps in reading the orders: the table's as-of date, renewals that usually come 0-3 days before expiry, renewals that are issued but not yet in force, orders that name units rather than whole plants, order numbers that do not give the issue year, overlapping event orders, court rulings and petitions that cover one order, not the whole chain, and dispatch wording that differs between orders.
- [`orders_lookup.py`](skills/doe-202c-orders/orders_lookup.py) 0.3.0: standard-library Python, no network. Commands `plant`, `in-force`, `expiring`, `order`, `court` and `summary`, each with `--json`.
- [`doe_202c_orders.csv`](skills/doe-202c-orders/doe_202c_orders.csv): one row per order (`order, kind, area, recipient, plant_key, plant, issued, effective, expires, expires_time, source, note`), as of 16 November 2026.
- [`doe_202c_plant_mw.csv`](skills/doe-202c-orders/doe_202c_plant_mw.csv): for the 8 plants with plant orders, the EIA plant id, the generators the orders cover, fuel and summer MW.
- [`doe_202c_court.csv`](skills/doe-202c-orders/doe_202c_court.csv): court actions on orders in the table (`order, plant_key, date, date_kind, court, case, action, source, note`), as of 16 November 2026. `date_kind` is `decided` (a ruling), `filed` (a filing) or `reported` (only a report's date is known). Each row names its source and says what was not checked.
- [`data/doe_202c_renewals.csv`](data/doe_202c_renewals.csv): one row per renewal of a plant or island order, with the days between the new order's issue date and the old order's last day (`lead_days`) and any uncovered days (`gap_days`). It is rebuilt from the orders table by `test_renewal_timing.py`. See [`docs/renewal-timing-plan.md`](docs/renewal-timing-plan.md).
- [`data/doe_202c_applications.csv`](data/doe_202c_applications.csv): for each of the 35 plant orders, whether DOE's page for it lists an application from the recipient, plant owner or grid operator dated on or before the issue date, with the applicant, the date, the page link and the page's "last updated" date. See [`docs/applications.md`](docs/applications.md).

An earlier copy of the orders table (as of 13 November 2026), with an analysis of event episodes and MW-days, is kept in [munimtechnologies/eia860m-slip](https://github.com/munimtechnologies/eia860m-slip) (`data/doe_202c_orders.csv`, `docs/doe-202c-orders.md`); the copy here is the newer one. Other public trackers cover parts of this: [EDF's coal plant mandates page](https://coalcosts.edf.org/mechanisms/202c-orders/) (coal units and costs), [POWER Magazine's order log](https://www.powermag.com/doe-has-issued-more-than-40-section-202c-emergency-orders-since-may-2025-heres-an-updated-log/), and two litigation trackers, the [State Power Project's](https://statepowerproject.org/challenges-to-doe-202c-orders/) and the [State Impact Center's](https://stateimpactcenter.org/insights/tracking-ag-activity-on-department-of-energy-emergency-orders). This table puts their court cases next to each order, so an agent asked about one plant or one order gets its case numbers and dates.

## Court actions (0.3.0, 16 November 2026)

Petitions for review were found against **10 of the 35 plant orders**, for six of the eight plants. All are in the D.C. Circuit except Centralia's, which are in the Ninth Circuit:

| Plant | Orders challenged | Cases found (filed) |
|---|---|---|
| J.H. Campbell | 202-25-3, 202-26-16 | No. 25-1159, Michigan v. U.S. Department of Energy (25 July 2025; Minnesota and Illinois filed separately the same day); Minnesota and Illinois against the fourth order (18 June 2026, number not found) |
| Eddystone | 202-25-4 | No. 25-1193, Joint Consumer Advocates (25 September 2025); NRDC, PennFuture, Clean Air Task Force, EDF and Sierra Club (26 September 2025, number not found); petitioners' opening brief 8 May 2026 |
| Centralia | 202-25-11, 202-26-18 | No. 26-1252, Washington v. U.S. Department of Energy (3 March 2026); No. 26-1261, Sierra Club v. U.S. Department of Energy (4 March 2026); Washington against the second order (11 June 2026, number not found) |
| R.M. Schahfer and F.B. Culley | 202-25-12, 202-25-13, 202-26-19, 202-26-20 | No. 26-1057, Sierra Club, et al. v. DOE (16 March 2026); state attorneys general (2 April and 17 July 2026, numbers not found) |
| Craig | 202-25-14 | No. 26-1059, Colorado, and No. 26-1060, Vote Solar, Sierra Club and EDF (both 18 March 2026) |
| H.A. Wagner, Stanton | none | none found |

Only one has been decided. On 11 September 2026 the D.C. Circuit, in *Michigan v. U.S. Department of Energy*, No. 25-1159 ([opinion](https://media.cadc.uscourts.gov/opinions/docs/2026/09/25-1159.pdf)), granted the petitions for review and vacated DOE Order No. 202-25-3, Campbell's first order (23 May to 21 August 2025). That was 413 days after Michigan's petition and 386 days after the order had expired. Challenges to the later Campbell orders were held in abeyance and not decided ([National Law Review](https://natlawreview.com/article/michigan-v-doe-dc-circuit-rejects-does-use-federal-power-act-emergency-powers-block)). On 26 October 2026, the 45th day after the decision, DOE petitioned for panel rehearing or rehearing en banc ([Sabin Center for Climate Change Law, Climate Litigation Updates, 6 November 2026](https://climate.law.columbia.edu/news/climate-litigation-updates-november-6-2026); reported by [APPA on 30 October 2026](https://www.publicpower.org/periodical/article/doe-seeks-rehearing-court-decision-coal-plants-operations)). No ruling on the petition was found as of 16 November 2026.

Each order lasts about 90 days and is renewed back to back, so every order challenged above had expired by 16 November 2026, and the orders now in force (Campbell's 202-26-51 and the rest) have no petition for review in this table. Limits: the rows come from trackers, press releases and the court's opinion, not from the dockets, which were not read. The State Impact Center's tracker was last updated on 21 August 2026, so later petitions are probably missing. Some numbers come from a single source: 26-1059 and 26-1060 from the State Power Project only, and 25-1193 from the name of the petition file the State Impact Center links. Whether docket 26-1057 names Schahfer's order as well as Culley's was not confirmed. The lookup shows these rows with the order and the plant (`order`, `plant`, `court`) and says plainly that a petition or ruling on one order changes nothing in the in-force dates of the others.

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

On 16 November 2026 the table has 10 orders in force: the 8 plant orders (4,849.9 summer MW, 3,692.9 MW of it coal), with Campbell under 202-26-51, and PREPA's 202-25-1F and 202-25-2F. Wagner's 202-26-25A expires 17 November, Eddystone's 202-26-40 20 November and Stanton's 202-26-42 30 November; no renewal of these, and no new Wagner application, was on DOE's pages at about 06:10 UTC on 16 November (the 2026 page was last updated 13 November).

Tests: `python -m unittest -v test_orders_lookup test_renewal_timing test_applications`.

## Updates

The table is updated when DOE posts a new order, and `TABLE_AS_OF` in `orders_lookup.py` moves with it. For any date after the as-of date the lookup prints a warning; check [DOE's 2026 page](https://www.energy.gov/ceser/2026-doe-202c-orders) for newer orders. Corrections are welcome by issue or at mv2@munimtech.com, especially docket numbers and filings missing from the court table.

## Changes

- 0.3.0 (16 November 2026): the court table goes from 2 to 18 rows. It now lists the petitions for review found against 10 of the 35 plant orders: Campbell (No. 25-1159 and a later state petition), Eddystone (No. 25-1193 and the environmental groups' petition, plus the opening brief), Centralia (Ninth Circuit No. 26-1252 and No. 26-1261, plus Washington's second petition), Schahfer and Culley (No. 26-1057 and state petitions), and Craig (No. 26-1059 and No. 26-1060). New `court_overview()`; `court` and `summary` report how many plant orders have a petition found and for which plants. Skill trap 8 is rewritten: a petition is not a ruling, every challenged order has expired, and the sources are trackers, not dockets. Orders table re-read on 16 November: no new order since 13 November (`TABLE_AS_OF` 2026-11-16).
- 15 November 2026, later (no release): applications table (`data/doe_202c_applications.csv`, 35 plant orders), [`docs/applications.md`](docs/applications.md) with predictions A1-A3, and `test_applications.py`. The skill and lookup are unchanged.
- 15 November 2026 (no release): renewal-timing table (`data/doe_202c_renewals.csv`), test, and pre-registered predictions (`docs/renewal-timing-plan.md`). The skill and lookup are unchanged.
- 0.2.2 (14 November 2026): Campbell's renewal, Order No. 202-26-51 (issued 13 November, in force 15 November 2026 to 12 February 2027), added; 88 orders, 27 plant renewals (26 with no uncovered day). Fixed `plant`: once a renewal was in the table before its start date, the lookup took the newest order as current and said no order was in force on the old order's last days; it now reports the order in force on the date, plus `next_order`, `next_effective` and `covered_through`. The `note` column records the dispatch wording of 202-26-49 and 202-26-51 ("only during (the) hours necessary to meet the emergency"). Skill traps 3 and 9 are new. Court table re-checked: no ruling on DOE's rehearing petition found as of 14 November.
- 0.2.1 (13 November 2026): DOE's rehearing petition in No. 25-1159 is now dated by its filing, 26 October 2026 (`date_kind` `filed`, source: the Sabin Center's Climate Litigation Updates), instead of by APPA's 30 October report, which is still cited in the note; no ruling on the petition was found as of 13 November. Skill trap 7 and the sources updated.
- 0.2.0 (13 November 2026): court actions table (`doe_202c_court.csv`) with the D.C. Circuit's vacatur of 202-25-3 and DOE's rehearing petition; `court` command; `order` and `plant` show court actions; skill trap 7 rewritten; tables as of 13 November 2026 (DOE's page showed no order issued after 6 November).
- 0.1.0 (November 2026): first release, table as of 8 November 2026.
