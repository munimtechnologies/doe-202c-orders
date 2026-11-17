# Do coal units scheduled to retire show up when the grid is tightest? (plan)

Pre-registration id: stress-1.

Written 17 November 2026, before any hourly generation or demand data for this question was read. MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name. Code Apache-2.0; text CC BY 4.0.

## 1. Question

Since May 2025 the U.S. Department of Energy has used Federal Power Act section 202(c) emergency orders to stop planned retirements of coal plants (this repo lists every order). The orders, and DOE's July 2025 resource adequacy report, treat a coal unit that has not yet retired as capacity the grid can count on in its tightest hours. Critics argue that units near the end of their lives fail more often. Utilities have said the same of specific plants. In February 2026 the utility for one ordered Indiana plant (F.B. Culley, going by the article's links) wrote to DOE that the plant ran at "less than half" its capacity during Winter Storm Fern. It added that "systemic equipment failures forced another outage" a day later ([FactCheck.org, Oct. 2026](https://www.factcheck.org/2026/10/trump-officials-mislead-about-electrical-grid-reliability/)). Nobody has tested this across the fleet.

**Across every U.S. coal unit with hourly EPA data, in each grid's tightest hours of 2022-2026, were units whose owners had scheduled them to retire running as often, and as hard, as coal units staying open?**

We searched for prior work on 17 November 2026 and found none. Published checks look at one plant at a time or use monthly data: Utility Dive's EIA-923 review of the 202(c) plants, Grid Status's monthly and market-level coal analysis (March 2026), and NERC/FERC's Winter Storm Fern outage totals, which do not separate units by retirement plans. Our own pre-registered test of the eight 202(c) plants ([dispatch-1](dispatch-plan.md)) is the single-plant version of this question. NERC's unit-level outage data (GADS) is not public.

## 2. Data (all public, no key)

From Catalyst Cooperative's PUDL nightly build (CC BY 4.0), `https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/`:

- `core_epacems__hourly_emissions.parquet`: EPA CAMD hourly data (CEMS), with `gross_load_mw` per emissions unit and hour, through 2026 Q3.
- `core_eia930__hourly_operations.parquet`: EIA-930 hourly demand for each balancing authority (BA).
- `core_eia860__scd_generators.parquet`: annual EIA-860 generator records, including status, energy source, nameplate MW, planned retirement date and actual retirement date.
- `core_eia860__scd_plants.parquet`: each plant's BA.
- `core_epa__assn_eia_epacamd_subplant_ids.parquet`: PUDL's subplants. Each subplant is the smallest group of EPA emissions units and EIA generators that are linked to each other.

## 3. Definitions (fixed now)

- **Unit of analysis**: a subplant with at least one EPA emissions unit and at least one EIA generator.
- **Study years**: Y = 2022 to 2026. 2026 runs to the last CEMS hour in the file.
- **Snapshot**: for study year Y, the latest EIA-860 report year on or before Y−1. Only generators listed as existing in that snapshot count. "Existing" means PUDL's `operational_status` is "existing", or, where that is empty, the status code is OP, SB, OA or OS.
- **Coal subplant-year**: every existing generator of the subplant has a coal energy source (`energy_source_code_1` in ANT, BIT, LIG, RC, SGC, SUB, WC), with a combined nameplate of at least 25 MW. Its **capacity** is that nameplate sum.
- **Groups**, set separately for each year:
  - **R (scheduled to retire)**: every existing generator has a planned retirement date on or before 31 December of Y+4. A date already passed counts.
  - **C (staying)**: no existing generator has one.
  - **MIXED**: some do and some don't. MIXED is reported but not used in the comparisons.
- **In service**: an hour counts only before the month after the subplant's actual retirement. The actual retirement date is the latest EIA-860 retirement date of its generators, used only if every one of them has one.
- **BA and stress hours**: each plant's BA is the latest non-empty EIA-860 code. **Stress hours** are the 50 hours of each calendar year with the highest demand in that BA, using the first non-null of `demand_imputed_eia_mwh`, `demand_adjusted_mwh` and `demand_reported_mwh`. Ties go to the earlier hour. That gives up to 250 hours per BA, matched to CEMS by PUDL's UTC timestamps as given. Subplants in BAs without EIA-930 demand are dropped and listed.
- **Output** in an hour: the sum of `gross_load_mw` over the subplant's EPA units. A missing row counts as 0 MW. **Online** means output > 0.
- **Metrics** for a group, over all its in-service subplant-stress-hour pairs:
  - **A** (capacity-weighted online share) = Σ capacity × online ÷ Σ capacity.
  - **SCF** (stress capacity factor) = Σ output ÷ Σ capacity.
  - **ACF** (all-hours capacity factor in the same subplant-years) = Σ annual gross MWh ÷ Σ capacity × in-service hours.
  - **Lift** = SCF ÷ ACF.
- **BA-matched gap**: in each BA that has both R and C pairs, A_R − A_C. These are averaged with R's capacity-hours in each BA as weights.
- **Uncertainty**: a 95% percentile interval for A_R − A_C and SCF_R − SCF_C. It comes from 1,000 bootstrap resamples of subplants within each group, seed 20261117.
- **Winter Storm Fern**: in each BA, the 20 highest-demand hours from 24 January to 2 February 2026 (UTC), with the 2026 groups.
- **Sensitivity checks** (descriptive only, not scored):
  - the 10 tightest hours per BA-year;
  - EIA-930 stamps read one hour earlier;
  - only subplant-years with some output in the year;
  - each year separately;
  - one row per subplant, with the 202(c)-ordered plants tagged.

## 4. Predictions (made before the data is read)

These probabilities are our own guesses. They are informed only by the sources in section 1.

| id | prediction | probability |
|---|---|---|
| S1 | A_R < A_C: scheduled-to-retire coal is online in a smaller capacity-weighted share of stress hours | 0.75 |
| S2 | A_C − A_R ≥ 10 percentage points | 0.45 |
| S3 | SCF_R < SCF_C | 0.80 |
| S4 | Lift_R > Lift_C: retiring units ramp up more for stress hours, relative to their own average | 0.60 |
| S5 | BA-matched gap A_R − A_C < 0 | 0.70 |
| S6 | Winter Storm Fern: A_R < A_C | 0.60 |
| S7 | A_C ≥ 80% | 0.60 |
| S8 | The 95% interval for A_R − A_C excludes 0 | 0.55 |

The job scores the predictions mechanically (`stress_core.score`). Each will be reported as held, failed or not scorable, failures included. This plan will not be edited after the job starts. Anything added later will be labelled as after the fact.

## 5. What would be remarkable

- **A large gap**: retiring coal online in, say, 60% of stress hours against 85% for staying coal. Each megawatt kept by order would then deliver much less in the hours it is kept for. Adequacy studies that count it as fully available would overstate it.
- **No gap**: retiring coal shows up as often as the rest. That would support the premise of the orders on this one point, whatever their cost.

Either way, this would be the first fleet-wide, hour-by-hour public measurement of the question.

## 6. Limits known now

- An offline unit in a stress hour may be on forced outage, on planned maintenance, short of fuel, or simply uneconomic. CEMS cannot tell these apart. The test measures whether the capacity was producing, not why.
- Top-demand hours in a BA are a proxy for grid stress. Reserve margins, imports, transmission limits and net load (demand minus wind and solar) can make other hours tighter. Large BAs such as MISO and PJM cover many local conditions.
- Gross load is not net output, and nameplate is not net capability, so CFs are indexes.
- Retirement plans in EIA-860 change, and some retiring units were kept running by 202(c) orders or by grid operators' reliability-must-run deals. Groups follow the snapshot, not later events.
- R and C differ in age, size and location. The BA-matched gap controls only for location.
- Nobody has checked the subplant links or results by hand. The output lists every subplant and every stress hour so that anyone can.

## 7. Code

`stress/stress_core.py` holds the definitions and scoring. It uses only the standard library and is tested in `stress/test_stress_core.py`. `stress/stress_job.py` loads the data. The job waits until this plan is public on GitHub before it reads any hourly data. Results will go in `docs/stress.md` and `data/stress1.json`.
