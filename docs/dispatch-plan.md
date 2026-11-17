# Were the plants DOE kept open running when the grid was tightest? (plan)

Pre-registration id: dispatch-1.

Written 17 November 2026, before any hourly generation or demand data for this question was read. MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name. Code Apache-2.0; text CC BY 4.0.

## 1. Question

Since May 2025 the U.S. Department of Energy has used Federal Power Act section 202(c) emergency orders to keep eight retiring fossil plants available: J.H. Campbell (MI), Eddystone 3-4 (PA), H.A. Wagner 4 (MD), Centralia 2 (WA), R.M. Schahfer 17-18 and F.B. Culley 2 (IN), Craig 1 (CO) and Stanton 1 (FL). The orders rest on one claim: without these units the grid could run short in its tightest hours. Their cost falls on customers. For Campbell alone, Consumers Energy has reported a net cost of $303 million through the end of September, after market revenues ([Utility Dive via Yahoo News, on the seventh Campbell order](https://www.yahoo.com/news/politics/articles/over-court-objections-doe-issues-135620619.html)).

**Were the ordered units actually generating in their own grid's highest-demand hours while the orders were in force, and more or less than in the same hours before the orders?**

Published checks so far use monthly or quarterly EIA-923 output. [Utility Dive, 23 June 2026](https://www.utilitydive.com/news/doe-202c-power-plants-centralia-campbell-schahfer/822062/) found Campbell's capacity factor down from about 66% to 46%, Centralia 2 at zero since 1 January 2026, Schahfer at 17% and Culley at 14% in early 2026 (both had units out for repairs), and Craig 1 running only 10-25 April 2026. An industry-funded memo ([Energy Ventures Analysis, Sept. 2025](https://americaspower.org/wp-content/uploads/2025/09/FINAL-Campbell-Analysis-Memo-9.5.25.pdf)) looked at Campbell's first five weeks. We found no hour-by-hour test across the eight plants, against grid demand, for the full period with data. Monthly averages cannot answer the question the orders raise, because a plant can have a low monthly output and still be there for the peak, or the reverse.

If the answer is striking either way, it matters: a fleet of emergency-ordered plants that is offline in the peak hours it was kept for is news, and so is a fleet that shows up for nearly every peak.

## 2. Data (all public, no key)

From Catalyst Cooperative's PUDL nightly build (CC BY 4.0), `https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/`:

- `core_epacems__hourly_emissions.parquet`: EPA CAMD hourly unit data (CEMS), 1995 to 2026 Q3, `gross_load_mw` per emissions unit and hour.
- `core_eia930__hourly_operations.parquet`: EIA-930 hourly demand per balancing authority (BA).
- `core_eia860__scd_plants.parquet`: each plant's BA code.
- `core_epa__assn_eia_epacamd.parquet`: the EPA-EIA crosswalk from EIA generators to EPA emissions units.
- The order dates are in this repo's `skills/doe-202c-orders/doe_202c_orders.csv` (88 rows, as of 16 November 2026). The ordered generators and summer MW are in `doe_202c_plant_mw.csv`.

## 3. Definitions (fixed now)

- **Ordered units**: the EPA emissions units that the crosswalk links to the generators each order covers (Campbell 1-3, Eddystone 3-4, Wagner 4, Centralia 2, Schahfer 17-18, Culley 2, Craig 1, Stanton 1). A plant with no linked unit is reported as not scorable. The job does not guess.
- **Output in an hour**: the sum of `gross_load_mw` over the ordered units. A unit-hour with no CEMS row, or a null load, counts as 0 MW, and hours with no row are counted separately. **Online** means output > 0.
- **Order hours**: every hour from 00:00 on an order's effective date to the end of its expiry date, in the plant's local standard time (UTC-5 for MI, PA, MD and FL, UTC-6 for IN, UTC-7 for CO, UTC-8 for WA). They run from 1 January 2021 to the last hour of CEMS data in the file.
- **BA**: the plant's latest non-empty EIA-860 balancing authority code in PUDL. If that is missing, the job uses MISO for Campbell, Schahfer and Culley, PJM for Eddystone and Wagner, FMPP for Stanton, WACM for Craig and BPAT for Centralia. **Demand** is the first non-null of `demand_imputed_eia_mwh`, `demand_adjusted_mwh` and `demand_reported_mwh` in the BA's hour, matched to CEMS by the PUDL UTC timestamps as given.
- **S1 (primary stress hours)**: the 100 order hours with the highest BA demand. Ties go to the earlier hour.
- **ALL**: all order hours.
- **BASE**: the order windows moved back 2, 3 and 4 years. That covers 2021 to 2024, all before any order. BASE takes the top 100 demand hours in each shifted window and pools them (300 hours).
- **S2 (DOE's own emergencies)**: hours inside DOE's 202(c) *event* orders for the plant's region while the plant's own order was in force. That means PJM for Eddystone and Wagner, Florida for Stanton and SPP for Craig, as whole local days from the effective date through the expiry date. MISO and the West had no event orders. **S2_any** is the same windows without the plant-order condition (descriptive).
- **CF** in a set of hours: mean output ÷ summer MW (gross output over net summer capacity, so it can exceed 100%). **Fleet CF in S1**: the sum over plants of mean S1 output ÷ the sum of their summer MW, over scorable plants.
- Descriptive only (not scored): the top 20 and top 500 hours, S1 with the EIA-930 stamp read one hour earlier (hour-start vs hour-end sensitivity), each baseline year separately, all hours of each baseline window, and every S1 hour with its demand and output.

## 4. Predictions (made before the data is read)

These probabilities are our guesses. They are informed only by the monthly and quarterly figures cited in section 1.

| id | prediction | probability |
|---|---|---|
| P1 | Centralia 2 is online in at most 5% of its S1 hours | 0.80 |
| P2 | Campbell is online in at least 90% of its S1 hours | 0.75 |
| P3 | Campbell's CF in S1 is higher than its CF over all order hours | 0.85 |
| P4 | Schahfer and Culley each have a lower CF in S1 than in BASE | 0.60 |
| P5 | Eddystone and Wagner together are online in at least 50% of their S2 hours (pooled) | 0.50 |
| P6 | Fleet CF in S1 is below 50% | 0.60 |
| P7 | Craig 1 is online in fewer than 50% of its S1 hours | 0.55 |
| P8 | Stanton 1 is online in at least 50% of its S1 hours | 0.60 |

A prediction about a plant with fewer than 100 S1 hours, or with no linked unit, is reported as not scorable (P5 and P6 need at least one plant with hours). The job scores them mechanically (`dispatch_core.score_predictions`). Results will be reported as held, failed or not scorable, failures included, and this plan will not be edited after the job starts.

## 5. What would be remarkable

- **Absent at the peak:** a fleet CF in S1 well below 50%, with several plants offline in most of their grid's 100 tightest hours. That would mean the plants were often not there in the hours the emergency orders were meant to cover.
- **Present at the peak:** CF in S1 near or above BASE for most plants. That would mean the orders did keep peak-hour capacity on line, whatever the monthly averages show.

Either way, this would be the first hour-by-hour public test of the orders' premise across all eight plants.

## 6. Limits known now

- Gross load is not net output, and summer MW is net capability, so the CFs are indexes, not exact shares.
- The top-demand hours are a proxy for grid stress. Reserve shortages, transmission limits and net load (demand minus wind and solar) can make other hours tighter. S2 uses DOE's own declarations, but only for PJM, Florida and SPP.
- A unit can be offline in a peak for legitimate reasons (forced outage, repairs the order required, fuel limits). This test measures whether the capacity was there, not whose fault it was.
- The order dates come from DOE's web pages. Whole-day windows widen the event orders slightly (several start at 23:59 ET).
- CEMS data runs to 2026 Q3, so the winter and autumn orders are covered only in part. Stanton's order began 4 June 2026, so its S1 hours fall in June-September 2026.
- No one has checked the job's unit links or outputs by hand. The results file lists every S1 hour so that anyone can.

## 7. Code

`dispatch/dispatch_core.py` (definitions and scoring, standard library only, tested in `dispatch/test_dispatch_core.py`) and `dispatch/job.py` (data loading). The job waits until this plan is public on GitHub before it reads any hourly data. Results will go in `docs/dispatch.md` and `data/dispatch1.json`.
