---
name: doe-202c-orders
description: Use when a question involves U.S. Department of Energy emergency orders under Federal Power Act section 202(c), for example whether a power plant (J.H. Campbell, Eddystone, H.A. Wagner, Centralia, R.M. Schahfer, F.B. Culley, Craig, Stanton) is under a DOE order to keep running, when its current order expires, how many times it has been renewed, whether a court has vacated one of these orders (the D.C. Circuit vacated Campbell's first order in September 2026), which grid-emergency orders (PJM, ERCOT, Duke, SPP, ISO-NE, NYISO, Florida utilities) or island orders (Puerto Rico's PREPA, Guam) were in force on a date, or how many megawatts the plant orders cover. Ships an offline, standard-library lookup over a table of all 87 orders, extensions and amendments of May 2025 to 6 November 2026, transcribed from DOE's pages, plus a small table of court actions, with the as-of dates and the traps in reading these orders.
license: Apache-2.0
---

# DOE 202(c) emergency orders

By MV2 of Munim, Inc. (mv2@munimtech.com), from github.com/munimtechnologies/doe-202c-orders (orders_lookup.py 0.2.1, orders table as of 2026-11-13, court table as of 2026-11-13). This skill and its lookup were made with AI agents working in MV2's name. Skill and code: Apache-2.0. Tables: CC BY 4.0; the orders are transcribed from DOE's public 202(c) pages, the court actions from the court's opinion, a law-school litigation tracker and press reports, and the megawatts come from EIA-860M via PUDL (CC BY 4.0, Catalyst Cooperative). No person has checked every row against the order PDFs. This is information, not legal advice.

Section 202(c) of the Federal Power Act lets the Secretary of Energy order generation or transmission to run during an emergency. Since May 2025 DOE has used it in three ways, which the table keeps apart in the `kind` column:

- `plant`: a named plant's units must stay available (each order about 90 days, renewed back to back). 8 plants, 34 orders.
- `event`: a grid operator or utility may run units beyond permit limits or use backup generation during a heat wave or winter storm (days to two weeks). 38 orders.
- `island`: system orders for Puerto Rico (PREPA) and Guam (about 90 days). 15 orders.

## When to use

- "Is plant X under a DOE emergency order?", "When does its order expire?", "How many times has it been renewed?"
- "Which 202(c) orders were in force on date D?", "How many MW are held by plant orders?"
- "Has a court struck down any of these orders?"
- Checking a news story, filing or dataset that cites an order number (202-26-39, 202-25-1F ...).

Not for: state emergency orders, FERC or RTO reliability-must-run contracts, or plants that announced a retirement delay without a DOE order.

## Run the lookup

The script and its three tables are in this skill's folder, next to this file: `orders_lookup.py`, `doe_202c_orders.csv`, `doe_202c_plant_mw.csv` and `doe_202c_court.csv`. It uses the Python standard library only and makes no network calls; read it before running it. If the files are not in this folder, do not download code yourself: tell the user they are in the repository named above and let them fetch it. From this folder:

```
python orders_lookup.py plant campbell --date 2026-11-13     # chain, gaps, current order, days left, court actions
python orders_lookup.py plant 1710                           # EIA plant id or part of the name also work
python orders_lookup.py in-force --date 2026-01-26 --kind event
python orders_lookup.py expiring --date 2026-11-13 --days 30
python orders_lookup.py order 202-25-3                       # one order, its successor and any court action on it
python orders_lookup.py court                                # every court action in the court table
python orders_lookup.py summary --json
```

Every command takes `--json`. Exit codes: 0 found, 1 nothing matched, 2 bad input. An order is in force from its start date through its expiry date, both counted. In the court table, `date_kind` says what a date is: `decided` (a ruling), `filed` (a filing) or `reported` (only a report's date is known).

## Traps (tell the user the ones that apply)

1. **The table has an as-of date (2026-11-13).** DOE issues new orders often, sometimes days before the old one expires. For any date after the as-of date the script prints a WARNING. Before saying a plant's order has lapsed or that no order exists, tell the user to check DOE's page (energy.gov/ceser/2026-doe-202c-orders) for orders issued since.
2. **A coming expiry is not a lapse.** In the table, 25 of 26 plant renewals were issued 0 to 3 days before the previous order's expiry date, with no uncovered day. The one exception: H.A. Wagner's 202-25-6A expired on 31 December 2025, and the next order (202-26-25) started 141 days later. This describes past orders only; it is not a forecast of what DOE will do.
3. **Orders name units, not whole plants.** Campbell units 1-3, Eddystone 3 and 4, Wagner 4, Centralia 2, Schahfer 17 and 18, Culley 2, Craig 1, Stanton 1. `doe_202c_plant_mw.csv` lists the EIA generators and their summer MW in the EIA-860M report before each plant's first order. That is capacity, not generation: an order to stay available does not say how much a unit ran.
4. **Order numbers do not give the issue year.** Letters mark extensions and amendments (202-26-25A extends 202-26-25). PREPA's 2025 series continues into 2026 as 202-25-1C to 202-25-1F. Use the `issued` column, not the number.
5. **Event orders overlap.** In a winter storm several areas can be under orders at once (8 event orders were in force on 26 January 2026). Count days covered, not orders, when describing how long an emergency lasted.
6. **Sources differ slightly.** 202-26-01A (ERCOT, customer-owned backup generation) is listed on ERCOT's page but not on DOE's 2026 list. For the first PREPA orders (202-25-1, 202-25-2) DOE's page gives no start or expiry, so the issue date is used as the start and they are never counted as in force. The `note` column says where a date was inferred.
7. **A court ruling covers one order, not the chain.** On 11 September 2026 the D.C. Circuit (No. 25-1159, Michigan v. U.S. Department of Energy) granted the petitions for review and vacated Campbell's first order, 202-25-3, which had expired in August 2025. It held that section 202(c) is for an identified risk of a substantial supply shortfall that calls for immediate action. Challenges to the later Campbell orders were held in abeyance and not decided. DOE petitioned for panel rehearing or rehearing en banc on 26 October 2026; no ruling on that petition was found as of 13 November 2026 (the table does not track the court's mandate). Campbell's later orders, and every other plant's orders, stay in force on their own dates in the table. `doe_202c_court.csv` lists only court actions found as of its as-of date; requests for rehearing at DOE, cases still pending (other states and plants have them) and actions not yet found are not in it. Do not infer from a missing row that an order was upheld or that a petition was decided, and do not say an order is no longer in force because of a ruling on a different order.

## Explain the results honestly

- Quote the order number, its dates and the source URL in the `source` column, and say the table's as-of date.
- Say that the rows were transcribed by AI agents from DOE's pages and that no person has checked every row against the order PDFs. If a row matters for a decision, open the order itself, and for court actions, the opinion or the court's docket.
- Do not give legal advice on what an order requires of a utility or on what a ruling means for a case.

## Sources and limits

- DOE CESER 202(c) pages: energy.gov/ceser/2025-doe-202c-orders and energy.gov/ceser/2026-doe-202c-orders (read through 13 November 2026; the 2026 page then showed nothing issued after 6 November); ERCOT's DOE 202(c) page for 202-26-01A.
- Court actions: the D.C. Circuit's opinion in No. 25-1159 (media.cadc.uscourts.gov/opinions/docs/2026/09/25-1159.pdf), National Law Review's summary of it, the Sabin Center for Climate Change Law's Climate Litigation Updates of 6 November 2026 (climate.law.columbia.edu) for the 26 October rehearing petition, and APPA's report of that petition (publicpower.org, 30 October 2026). The court's docket itself was not read.
- Summer MW: EIA-860M via PUDL nightly builds (October 2026). Fuel codes are EIA's (SUB, BIT coal; NG gas; DFO oil).
- The same orders table, with an analysis of event episodes and MW-days, is kept in github.com/munimtechnologies/eia860m-slip (`data/doe_202c_orders.csv`, `docs/doe-202c-orders.md`). Other public trackers: EDF's coal plant mandates page and POWER Magazine's order log.
- Questions or corrections: mv2@munimtech.com or an issue on the repo.
