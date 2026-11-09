# doe-202c-orders

An agent skill and a small offline lookup for U.S. Department of Energy emergency orders under Federal Power Act section 202(c): every order, extension and amendment from May 2025 to 6 November 2026 (87 rows), in one table with the dates each is in force.

By MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no person has checked every row against the order PDFs. Code and skill: Apache-2.0. Tables: CC BY 4.0 (orders transcribed from DOE's public pages; summer MW from EIA-860M via PUDL, CC BY 4.0, Catalyst Cooperative). Information, not legal advice.

## What is in it

- [`skills/doe-202c-orders/SKILL.md`](skills/doe-202c-orders/SKILL.md): tells coding agents (Claude Code, Codex, Cursor and others) what the three kinds of order are (plant, event, island), how to run the lookup, and the traps in reading the orders: the table's as-of date, renewals that usually come 0-3 days before expiry, orders that name units rather than whole plants, order numbers that do not give the issue year, overlapping event orders, and legal challenges the table does not track.
- [`orders_lookup.py`](skills/doe-202c-orders/orders_lookup.py) 0.1.0: standard-library Python, no network. Commands `plant`, `in-force`, `expiring`, `order` and `summary`, each with `--json`.
- [`doe_202c_orders.csv`](skills/doe-202c-orders/doe_202c_orders.csv): one row per order (`order, kind, area, recipient, plant_key, plant, issued, effective, expires, expires_time, source, note`), as of 8 November 2026.
- [`doe_202c_plant_mw.csv`](skills/doe-202c-orders/doe_202c_plant_mw.csv): for the 8 plants with plant orders, the EIA plant id, the generators the orders cover, fuel and summer MW.

The table is the same one kept, with an analysis of event episodes and MW-days, in [munimtechnologies/eia860m-slip](https://github.com/munimtechnologies/eia860m-slip) (`data/doe_202c_orders.csv`, `docs/doe-202c-orders.md`). Other public trackers cover parts of this: [EDF's coal plant mandates page](https://coalcosts.edf.org/mechanisms/202c-orders/) (coal units and costs) and [POWER Magazine's order log](https://www.powermag.com/doe-has-issued-more-than-40-section-202c-emergency-orders-since-may-2025-heres-an-updated-log/).

## Use

As an agent skill:

```
npx skills add munimtechnologies/doe-202c-orders
```

Or directly, from the skill folder:

```
python orders_lookup.py plant campbell --date 2026-11-09
python orders_lookup.py expiring --date 2026-11-09 --days 30
python orders_lookup.py in-force --date 2026-01-26 --kind event --json
```

On 9 November 2026 the table has 10 orders in force: the 8 plant orders (4,849.9 summer MW, 3,692.9 MW of it coal) and PREPA's 202-25-1F and 202-25-2F. Campbell's 202-26-39 expires 14 November, Wagner's 202-26-25A 17 November and Eddystone's 202-26-40 20 November; no renewal of these was on DOE's page on 8 November.

Tests: `python -m unittest -v test_orders_lookup`.

## Updates

The table is updated when DOE posts a new order, and `TABLE_AS_OF` in `orders_lookup.py` moves with it. For any date after the as-of date the lookup prints a warning; check [DOE's 2026 page](https://www.energy.gov/ceser/2026-doe-202c-orders) for newer orders.

## Changes

- 0.1.0 (November 2026): first release, table as of 8 November 2026.
