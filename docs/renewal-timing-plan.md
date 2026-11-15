# How close to expiry does DOE renew its 202(c) orders? Record and predictions

Pre-registration id: renewal-timing-1.

Stated on 15 November 2026 at about 14:40 UTC, before any of the outcomes below is known. DOE's [2026 202(c) orders page](https://www.energy.gov/ceser/2026-doe-202c-orders) was last updated on 13 November 2026 and lists no order after 202-26-51.

By MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name; no person has checked the readings by hand. Text and table: CC BY 4.0. Test code: Apache-2.0. Information, not legal advice.

## What was measured

[`data/doe_202c_renewals.csv`](../data/doe_202c_renewals.csv) has one row for each time a plant order or an island order was followed by another order in the same chain. A chain is one plant for plant orders, or one order number without its letter suffix for island orders (PREPA's 202-25-1 and 202-25-2 run in parallel, so they are two chains). Event orders (a few days in a cold snap or heat wave) are left out. The rows are rebuilt from this repository's orders table (`skills/doe-202c-orders/doe_202c_orders.csv`, as of 14 November 2026) by [`test_renewal_timing.py`](../test_renewal_timing.py), which must match the CSV row for row. The dates are as DOE's pages give them.

- `lead_days` = the old order's last day in force minus the new order's issue date. 0 means the new order was issued on the old order's last day.
- `gap_days` = the new order's first day in force minus the old order's last day, minus 1. 0 means it starts the next day, -1 means it starts on the old order's last day (one day of overlap), and a positive number is the count of days with no order in force.

## What the record shows (as of 15 November 2026)

**Plant orders: 27 renewals across 8 plants.**

- 26 of the 27 left no uncovered day. Every one of those 26 was issued 0-3 days before the old order's last day: 9 on the last day itself, 10 one day before, 4 two days before, and 3 three days before. None was issued after the old order had ended.
- The one lapse is Wagner Unit 4. Order 202-25-6A ended on 31 December 2025, and the next order, 202-26-25, was issued on 21 May 2026. That left 141 days, 1 January to 21 May 2026, with no order in force.
- The start dates changed in early 2026. The 7 renewals issued before 1 March 2026 started on the old order's last day (one day of overlap). All 19 issued since then started the day after it, with no overlap and no gap.
- Campbell's renewal of 13 November 2026 (202-26-51), the first issued since the D.C. Circuit's 11 September 2026 ruling in *Michigan v. DOE*, kept the pattern: it was issued 1 day before 202-26-39 ended and took effect the day after.

**Island orders: 10 renewals of PREPA's two orders** (5 dates, with both orders renewed together each time). All are continuous and were issued 0-2 days before expiry. The step from the first orders, 202-25-1 and 202-25-2, to the A orders is left out, because DOE's page does not state when the first orders ended. Guam Power Authority's only order, 202-26-38, ended at 23:59 Guam time on 4 November 2026. On 15 November no successor was listed on DOE's 2026 page or on [the order's page](https://www.energy.gov/ceser/federal-power-act-section-202c-guam-power-authority-gpa-order-no-202-26-38) (last updated 5 August 2026).

**Who asks.** Of the 8 plant chains, only Wagner's orders follow an application, from PJM. Its page lists PJM's renewal application of 4 August 2026 alongside order 202-26-25A of 19 August, and its last update is dated 19 August, so the application seems to have been posted with the order rather than when it was filed. DOE's summaries of the other plant orders name no applicant. On 15 October 2026 the Southern Maryland Chronicle [reported](https://southernmarylandchronicle.com/2026/10/15/doe-emergency-order-pjm-backup-generation-maryland-october-2026/), citing a PJM presentation, that "PJM said it plans to seek a renewal of that order in late October" and was weighing how the *Michigan v. DOE* ruling affects some 202(c) orders. On 15 November [Wagner's page](https://www.energy.gov/ceser/federal-power-act-section-202c-pjm-interconnection-llc-pjm-order-no-202-26-25) (last updated 19 August) listed no new application and no new order. [Eddystone's 202-26-40 page](https://www.energy.gov/ceser/federal-power-act-section-202c-pjm-interconnection-llc-pjm-order-no-202-26-40) (last updated 22 October) listed no successor either.

What is new here, as far as we found: trackers such as [POWER Magazine's order log](https://www.powermag.com/doe-has-issued-more-than-40-section-202c-emergency-orders-since-may-2025-heres-an-updated-log/), [EDF's coal costs page](https://coalcosts.edf.org/mechanisms/202c-orders/) and news reports say DOE renews "before" or "the day before" expiry, and the [Energy Institute at Haas](https://energyathaas.wordpress.com/2026/03/30/doe-second-guesses-coal-plant-owners/) wrote on 30 March 2026 that "every order that has reached its 90-day expiration has been renewed". We found no public order-by-order table of lead and gap days. Wagner's 141-day lapse in 2026 and Guam's lapse on 4 November show that "every order is renewed" is not true for all chains.

## Orders that end next

| Chain | Order | Last day in force |
|---|---|---|
| Wagner (PJM, Talen) | 202-26-25A | 17 Nov 2026 |
| Eddystone (PJM, Constellation) | 202-26-40 | 20 Nov 2026 |
| Stanton (OUC) | 202-26-42 | 30 Nov 2026 |
| Centralia (TransAlta) | 202-26-44 | 11 Dec 2026 |
| Schahfer (NIPSCO, MISO) | 202-26-46 | 18 Dec 2026 |
| Culley (CenterPoint, MISO) | 202-26-47 | 18 Dec 2026 |
| Craig (Tri-State, SPP) | 202-26-49 | 25 Dec 2026 |
| PREPA | 202-25-1F, 202-25-2F | 5 Feb 2027 |
| Campbell (MISO, Consumers) | 202-26-51 | 12 Feb 2027 |

## Predictions (renewal-timing-1)

A "successor" is a new DOE 202(c) order for the same plant (any number or letter suffix). The issue and start dates are as DOE's pages give them. Each prediction is scored from DOE's pages on the day after the last day in force and re-read once 7 days later, to allow for posting lag. A successor first posted later than that, but dated within the window, still counts as issued in the window, and the posting lag is recorded. The probabilities are MV2's stated confidence, given so the record can be scored for calibration as well as for hits.

- **P1 (DOE-initiated plant chains continue as before).** Eddystone, Stanton, Centralia, Schahfer, Culley and Craig each get a successor issued 0-3 days before the old order's last day, in force from the next day (gap 0). Each of the six is scored on its own, at 0.85 each. P1 as a whole holds if at least 5 of the 6 meet both conditions.
- **P2 (Wagner).** A Wagner successor is issued 14-17 November 2026, in force from 18 November (gap 0). Confidence 0.6. The case for: PJM said it would apply in late October, and in both August 2026 and October 2025 DOE acted about 2 weeks after PJM applied. The case against: the unit lapsed over the 2025-26 winter, and PJM said it was weighing the *Michigan v. DOE* ruling. If there is no successor by 17 November, P2 fails and the lapse is recorded as Wagner's second.
- **P3 (paired renewals).** Schahfer's and Culley's successors are issued on the same date, as all three earlier pairs were. Confidence 0.85. It is scored only if both are renewed.
- **P4 (no late renewals).** No successor in this window (Wagner to Craig, seven chains) is issued after its predecessor's last day. A chain that simply ends counts as a lapse, not a late renewal. Confidence 0.9.
- **P5 (Guam).** No successor to Guam's 202-26-38 appears on DOE's 2026 page by 28 December 2026. Confidence 0.8.

The final scoring date is 28 December 2026, with a re-read on 4 January 2027. Results will go in `docs/renewal-timing.md` next to this file. That file will list every prediction that failed as failed, and anything found after the fact will be labelled as such. This plan will not be edited after it is published; corrections, if any, will go in the results file.

## Limits

- The dates are DOE's own. An order "issued" late on a Friday may be posted later, and this record does not try to recover signing times.
- The orders table was transcribed from DOE's pages by AI agents and has not been checked row by row against the order PDFs.
- With 27 plant renewals from 8 chains, the record describes how DOE has behaved. It is not a model of why.
