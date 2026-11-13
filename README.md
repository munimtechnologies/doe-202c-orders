# doe-202c-orders

An agent skill and a small offline lookup for U.S. Department of Energy emergency orders under Federal Power Act section 202(c): every order, extension and amendment from May 2025 to 6 November 2026 (87 rows), in one table with the dates each is in force, plus a small table of court actions on those orders.

By MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no person has checked every row against the order PDFs. Code and skill: Apache-2.0. Tables: CC BY 4.0 (orders transcribed from DOE's public pages; court actions from the court's opinion and press reports; summer MW from EIA-860M via PUDL, CC BY 4.0, Catalyst Cooperative). Information, not legal advice.

## What is in it

- [`skills/doe-202c-orders/SKILL.md`](skills/doe-202c-orders/SKILL.md): tells coding agents (Claude Code, Codex, Cursor and others) what the three kinds of order are (plant, event, island), how to run the lookup, and the traps in reading the orders: the table's as-of date, renewals that usually come 0-3 days before expiry, orders that name units rather than whole plants, order numbers that do not give the issue year, overlapping event orders, and court rulings that cover one order, not the whole chain.
- [`orders_lookup.py`](skills/doe-202c-orders/orders_lookup.py) 0.2.0: standard-library Python, no network. Commands `plant`, `in-force`, `expiring`, `order`, `court` and `summary`, each with `--json`.
- [`doe_202c_orders.csv`](skills/doe-202c-orders/doe_202c_orders.csv): one row per order (`order, kind, area, recipient, plant_key, plant, issued, effective, expires, expires_time, source, note`), as of 13 November 2026.
- [`doe_202c_plant_mw.csv`](skills/doe-202c-orders/doe_202c_plant_mw.csv): for the 8 plants with plant orders, the EIA plant id, the generators the orders cover, fuel and summer MW.
- [`doe_202c_court.csv`](skills/doe-202c-orders/doe_202c_court.csv): court actions on orders in the table (`order, plant_key, date, date_kind, court, case, action, source, note`), as of 13 November 2026.

The orders table is the same one kept, with an analysis of event episodes and MW-days, in [munimtechnologies/eia860m-slip](https://github.com/munimtechnologies/eia860m-slip) (`data/doe_202c_orders.csv`, `docs/doe-202c-orders.md`). Other public trackers cover parts of this: [EDF's coal plant mandates page](https://coalcosts.edf.org/mechanisms/202c-orders/) (coal units and costs) and [POWER Magazine's order log](https://www.powermag.com/doe-has-issued-more-than-40-section-202c-emergency-orders-since-may-2025-heres-an-updated-log/).

## Court actions

On 11 September 2026 the U.S. Court of Appeals for the D.C. Circuit, in *Michigan v. U.S. Department of Energy*, No. 25-1159 ([opinion](https://media.cadc.uscourts.gov/opinions/docs/2026/09/25-1159.pdf)), granted the petitions for review and vacated DOE Order No. 202-25-3, the first order that kept the J.H. Campbell plant in Michigan available (23 May to 21 August 2025). Challenges to the later Campbell orders were held in abeyance and not decided ([National Law Review](https://natlawreview.com/article/michigan-v-doe-dc-circuit-rejects-does-use-federal-power-act-emergency-powers-block)), and DOE has asked for panel rehearing or rehearing en banc ([APPA, 30 October 2026](https://www.publicpower.org/periodical/article/doe-seeks-rehearing-court-decision-coal-plants-operations)). DOE kept issuing Campbell orders: 202-26-39 runs to 14 November 2026, and no renewal was on DOE's page on 13 November.

The lookup shows these actions with the order and the plant (`order 202-25-3`, `plant campbell`, `court`), and says plainly that a ruling on one order changes nothing in the in-force dates of the others. The court table lists only actions found by its as-of date; cases still pending are not tracked.

## Use

As an agent skill:

```
npx skills add munimtechnologies/doe-202c-orders
```

Or directly, from the skill folder:

```
python orders_lookup.py plant campbell --date 2026-11-13
python orders_lookup.py expiring --date 2026-11-13 --days 30
python orders_lookup.py in-force --date 2026-01-26 --kind event --json
python orders_lookup.py court
```

On 13 November 2026 the table has 10 orders in force: the 8 plant orders (4,849.9 summer MW, 3,692.9 MW of it coal) and PREPA's 202-25-1F and 202-25-2F. Campbell's 202-26-39 expires 14 November, Wagner's 202-26-25A 17 November and Eddystone's 202-26-40 20 November; no renewal of these was on DOE's page on 13 November.

Tests: `python -m unittest -v test_orders_lookup`.

## Updates

The table is updated when DOE posts a new order, and `TABLE_AS_OF` in `orders_lookup.py` moves with it. For any date after the as-of date the lookup prints a warning; check [DOE's 2026 page](https://www.energy.gov/ceser/2026-doe-202c-orders) for newer orders. Corrections are welcome by issue or at mv2@munimtech.com.

## Changes

- 0.2.0 (13 November 2026): court actions table (`doe_202c_court.csv`) with the D.C. Circuit's vacatur of 202-25-3 and DOE's rehearing petition; `court` command; `order` and `plant` show court actions; skill trap 7 rewritten; tables as of 13 November 2026 (DOE's page showed no order issued after 6 November).
- 0.1.0 (November 2026): first release, table as of 8 November 2026.
