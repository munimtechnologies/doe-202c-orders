# SPDX-License-Identifier: Apache-2.0
"""Core functions for pre-registration dispatch-1 (docs/dispatch-plan.md).

Question: were the units that DOE's Federal Power Act 202(c) orders kept open
actually generating during the grid's tightest hours?

Standard library only, so the tests run anywhere. The data loading (EPA CEMS
and EIA-930 via PUDL) lives in job.py.

MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's
name. Apache-2.0.
"""
import csv
import datetime as dt

UTC = dt.timezone.utc
HOUR = dt.timedelta(hours=1)

# Fixed standard-time UTC offsets (hours) for each plant's area. Order dates
# are read as whole local days in standard time (plan section 3).
PLANT_TZ = {
    "campbell": -5, "eddystone": -5, "wagner": -5, "stanton": -5,
    "schahfer": -6, "culley": -6, "craig": -7, "centralia": -8,
}

# Fallback EIA-930 balancing authority codes. The latest non-empty EIA-860
# value in PUDL wins when present (plan section 3).
PLANT_BA = {
    "campbell": "MISO", "schahfer": "MISO", "culley": "MISO",
    "eddystone": "PJM", "wagner": "PJM", "stanton": "FMPP",
    "craig": "WACM", "centralia": "BPAT",
}

# DOE event orders (orders table, kind 'event', column 'area') whose windows
# form stress set S2 for a plant. MISO and the West have no event orders.
PLANT_EVENT_AREAS = {
    "eddystone": {"PJM"}, "wagner": {"PJM"},
    "stanton": {"Florida"}, "craig": {"SPP"},
}

STUDY_START = dt.datetime(2021, 1, 1, tzinfo=UTC)
TOP_N = 100
BASELINE_SHIFTS = (2, 3, 4)


def parse_date(s):
    return dt.date.fromisoformat(s.strip())


def day_start_utc(d, offset_h):
    """UTC instant of local midnight starting date d, for a fixed offset."""
    return dt.datetime(d.year, d.month, d.day, tzinfo=UTC) - dt.timedelta(hours=offset_h)


def merge_intervals(intervals):
    """Merge [start, end) intervals that overlap or touch."""
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            if e > out[-1][1]:
                out[-1] = (out[-1][0], e)
        else:
            out.append((s, e))
    return out


def read_orders(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_plants(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for r in rows:
        out[r["plant_key"]] = {
            "plant": r["plant"],
            "plant_id_eia": int(r["plant_id_eia"]),
            "generators": [g.strip() for g in r["generators"].split("|") if g.strip()],
            "summer_mw": float(r["summer_mw"]),
        }
    return out


def order_intervals(rows, plant_key, offset_h):
    """In-force intervals of a plant's orders: effective 00:00 local to the end
    of the expiry day (local), merged."""
    iv = []
    for r in rows:
        if r["kind"] != "plant" or r["plant_key"] != plant_key:
            continue
        if not r["effective"] or not r["expires"]:
            continue
        s = day_start_utc(parse_date(r["effective"]), offset_h)
        e = day_start_utc(parse_date(r["expires"]) + dt.timedelta(days=1), offset_h)
        iv.append((s, e))
    return merge_intervals(iv)


def event_intervals(rows, areas, offset_h):
    """Windows of DOE event orders in the given areas, as whole local days."""
    iv = []
    for r in rows:
        if r["kind"] != "event" or r["area"] not in areas:
            continue
        if not r["effective"] or not r["expires"]:
            continue
        s = day_start_utc(parse_date(r["effective"]), offset_h)
        e = day_start_utc(parse_date(r["expires"]) + dt.timedelta(days=1), offset_h)
        iv.append((s, e))
    return merge_intervals(iv)


def intersect_intervals(a, b):
    out = []
    for s1, e1 in a:
        for s2, e2 in b:
            s, e = max(s1, s2), min(e1, e2)
            if s < e:
                out.append((s, e))
    return merge_intervals(out)


def hours_in(intervals, lo, hi):
    """Hour starts h with lo <= h < hi inside the intervals."""
    hours = []
    for s, e in intervals:
        h = max(s, lo)
        end = min(e, hi)
        while h < end:
            hours.append(h)
            h += HOUR
    return hours


def shift_years(h, k):
    """The same clock hour k years earlier (29 Feb -> 28 Feb)."""
    try:
        return h.replace(year=h.year - k)
    except ValueError:
        return h.replace(year=h.year - k, day=28)


def shift_intervals(intervals, k):
    return merge_intervals([(shift_years(s, k), shift_years(e, k)) for s, e in intervals])


def top_n_hours(demand, eligible, n):
    """The n eligible hours with the highest demand. Ties go to the earlier hour.
    Hours with no demand value are skipped."""
    cand = [(h, demand[h]) for h in eligible if demand.get(h) is not None]
    cand.sort(key=lambda x: (-x[1], x[0]))
    return [h for h, _ in cand[:n]]


def plant_metrics(gen, hours, summer_mw):
    """gen: hour -> summed gross load (MW) of the ordered units, for hours with
    at least one CEMS row. Hours without a row count as 0 MW (no_record_hours)."""
    n = len(hours)
    if n == 0:
        return {"n": 0, "online_hours": 0, "online_share": None,
                "mean_mw": None, "cf": None, "no_record_hours": 0}
    vals = [gen.get(h, 0.0) or 0.0 for h in hours]
    online = sum(1 for v in vals if v > 0)
    total = sum(vals)
    return {
        "n": n,
        "online_hours": online,
        "online_share": online / n,
        "mean_mw": total / n,
        "cf": total / (n * summer_mw),
        "no_record_hours": sum(1 for h in hours if h not in gen),
    }


def ratio(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def _get(results, plant, key, field):
    m = (results.get(plant) or {}).get(key)
    if not m or not m.get("n"):
        return None
    return m.get(field)


def score_predictions(results, summer_mw):
    """Score P1-P8 of docs/dispatch-plan.md. Returns {id: True/False/None};
    None means not scorable (missing plant, unmapped units or too few hours)."""
    out = {}

    def full_s1(p):
        m = (results.get(p) or {}).get("S1")
        return bool(m) and m.get("n", 0) >= TOP_N

    # P1 Centralia online in at most 5% of its S1 hours.
    v = _get(results, "centralia", "S1", "online_share")
    out["P1"] = None if v is None or not full_s1("centralia") else v <= 0.05
    # P2 Campbell online in at least 90% of its S1 hours.
    v = _get(results, "campbell", "S1", "online_share")
    out["P2"] = None if v is None or not full_s1("campbell") else v >= 0.90
    # P3 Campbell S1 capacity factor above its all-order-hours capacity factor.
    a = _get(results, "campbell", "S1", "cf")
    b = _get(results, "campbell", "ALL", "cf")
    out["P3"] = None if a is None or b is None or not full_s1("campbell") else a > b
    # P4 Schahfer and Culley each: S1 cf below pooled baseline cf.
    ok = []
    for p in ("schahfer", "culley"):
        a = _get(results, p, "S1", "cf")
        b = _get(results, p, "BASE", "cf")
        ok.append(None if a is None or b is None or not full_s1(p) else a < b)
    out["P4"] = None if None in ok else all(ok)
    # P5 Eddystone + Wagner pooled online share in S2 at least 50%.
    on = n = 0
    for p in ("eddystone", "wagner"):
        m = (results.get(p) or {}).get("S2")
        if m and m.get("n"):
            on += m["online_hours"]
            n += m["n"]
    out["P5"] = None if n == 0 else on / n >= 0.5
    # P6 fleet: sum of S1 mean MW over sum of summer MW below 0.5.
    num = den = 0.0
    for p, mw in summer_mw.items():
        mm = _get(results, p, "S1", "mean_mw")
        if mm is None:
            continue
        num += mm
        den += mw
    out["P6"] = None if den == 0 else num / den < 0.5
    # P7 Craig online in fewer than 50% of its S1 hours.
    v = _get(results, "craig", "S1", "online_share")
    out["P7"] = None if v is None or not full_s1("craig") else v < 0.5
    # P8 Stanton online in at least 50% of its S1 hours.
    v = _get(results, "stanton", "S1", "online_share")
    out["P8"] = None if v is None or not full_s1("stanton") else v >= 0.5
    return out


def fleet_cf(results, summer_mw, key="S1"):
    num = den = 0.0
    for p, mw in summer_mw.items():
        mm = _get(results, p, key, "mean_mw")
        if mm is None:
            continue
        num += mm
        den += mw
    return None if den == 0 else num / den


def analyse_plant(plant_key, info, rows, demand, gen, coverage_end,
                  study_start=STUDY_START, top_n=TOP_N):
    """All hour sets and metrics for one plant (plan section 4).

    demand: hour -> MWh for the plant's BA; gen: hour -> MW of ordered units."""
    off = PLANT_TZ[plant_key]
    mw = info["summer_mw"]
    oiv = order_intervals(rows, plant_key, off)
    order_hours = hours_in(oiv, study_start, coverage_end)
    res = {"order_intervals": [(s.isoformat(), e.isoformat()) for s, e in oiv],
           "order_hours": len(order_hours)}
    res["ALL"] = plant_metrics(gen, order_hours, mw)
    s1 = top_n_hours(demand, order_hours, top_n)
    res["S1"] = plant_metrics(gen, s1, mw)
    res["S1_hours"] = s1
    res["S1_top20"] = plant_metrics(gen, top_n_hours(demand, order_hours, 20), mw)
    res["S1_top500"] = plant_metrics(gen, top_n_hours(demand, order_hours, 500), mw)
    # Sensitivity: EIA-930 stamp t read as the hour starting t - 1 h.
    shifted = {h - HOUR: v for h, v in demand.items()}
    res["S1_shift"] = plant_metrics(gen, top_n_hours(shifted, order_hours, top_n), mw)
    # Baseline: the order windows shifted back 2, 3 and 4 years.
    base_hours = []
    for k in BASELINE_SHIFTS:
        bh = hours_in(shift_intervals(oiv, k), study_start, coverage_end)
        top = top_n_hours(demand, bh, top_n)
        res["BASE_k%d" % k] = plant_metrics(gen, top, mw)
        res["BASEALL_k%d" % k] = plant_metrics(gen, bh, mw)
        base_hours.extend(top)
    res["BASE"] = plant_metrics(gen, base_hours, mw)
    # S2: DOE's own event-order windows in the plant's area.
    areas = PLANT_EVENT_AREAS.get(plant_key)
    if areas:
        eiv = event_intervals(rows, areas, off)
        res["S2"] = plant_metrics(gen, hours_in(intersect_intervals(eiv, oiv), study_start, coverage_end), mw)
        res["S2_any"] = plant_metrics(gen, hours_in(eiv, study_start, coverage_end), mw)
    else:
        res["S2"] = None
        res["S2_any"] = None
    res["R_S1_over_ALL"] = ratio(res["S1"]["cf"], res["ALL"]["cf"])
    res["R_S1_over_BASE"] = ratio(res["S1"]["cf"], res["BASE"]["cf"])
    return res
