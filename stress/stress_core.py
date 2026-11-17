# SPDX-License-Identifier: Apache-2.0
"""Core functions for pre-registration stress-1 (docs/stress-plan.md).

Question: in each grid's tightest hours of 2022-2026, were U.S. coal units
whose owners had scheduled them to retire running as often as coal units that
were staying open?

Standard library only, so the tests run anywhere. The data loading (EPA CEMS,
EIA-930, EIA-860 and the EPA-EIA subplant crosswalk, all via PUDL) lives in
stress_job.py.

MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's
name. Apache-2.0.
"""
import datetime as dt
import random

UTC = dt.timezone.utc
HOUR = dt.timedelta(hours=1)

# EIA energy source codes counted as coal.
COAL = {"ANT", "BIT", "LIG", "RC", "SGC", "SUB", "WC"}
# EIA operational status codes counted as existing when PUDL's text status is empty.
EXISTING_CODES = {"OP", "SB", "OA", "OS"}

YEARS = (2022, 2023, 2024, 2025, 2026)
STUDY_START = dt.datetime(2022, 1, 1, tzinfo=UTC)
TOP_K = 50          # stress hours per balancing authority and calendar year
TOP_K_SMALL = 10    # sensitivity: the 10 tightest hours per BA-year
HORIZON_YEARS = 4   # "scheduled to retire": planned date on or before 31 Dec of year Y+4
MIN_MW = 25.0       # smallest subplant counted (nameplate MW)
FERN = (dt.datetime(2026, 1, 24, tzinfo=UTC), dt.datetime(2026, 2, 3, tzinfo=UTC))
FERN_K = 20
BOOT = 1000
SEED = 20261117


def as_date(x):
    """date from a date, datetime, ISO string or None."""
    if x is None:
        return None
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    s = str(x).strip()
    if not s or s.lower() in ("nat", "none", "nan"):
        return None
    return dt.date.fromisoformat(s[:10])


def month_after(d):
    """00:00 UTC on the first day of the month after date d."""
    return dt.datetime(d.year + (1 if d.month == 12 else 0), d.month % 12 + 1, 1, tzinfo=UTC)


def is_existing(status, code):
    if status:
        return str(status).strip().lower() == "existing"
    return (code or "").strip().upper() in EXISTING_CODES


def year_bounds(y, lo, hi):
    """[start, end) of calendar year y (UTC), clipped to [lo, hi)."""
    s = max(dt.datetime(y, 1, 1, tzinfo=UTC), lo)
    e = min(dt.datetime(y + 1, 1, 1, tzinfo=UTC), hi)
    return s, e


def top_k(demand, start, end, k):
    """The k hours in [start, end) with the highest demand. Ties go to the
    earlier hour; hours with no demand value are skipped."""
    cand = [(h, v) for h, v in demand.items() if start <= h < end and v is not None]
    cand.sort(key=lambda x: (-x[1], x[0]))
    return [h for h, _ in cand[:k]]


def stress_sets(demand_by_ba, years, study_start, coverage_end, k):
    """{(ba, year): [top-k demand hours of that BA in that year]}."""
    out = {}
    for ba, d in demand_by_ba.items():
        for y in years:
            s, e = year_bounds(y, study_start, coverage_end)
            if s >= e:
                continue
            out[(ba, y)] = top_k(d, s, e, k)
    return out


def window_sets(demand_by_ba, window, coverage_end, k, year):
    """{(ba, year): top-k hours inside window [start, end), clipped to coverage}."""
    s, e = window[0], min(window[1], coverage_end)
    out = {}
    if s >= e:
        return out
    for ba, d in demand_by_ba.items():
        out[(ba, year)] = top_k(d, s, e, k)
    return out


def shift_demand(demand):
    """EIA-930 stamp t read as the hour starting t - 1 h (sensitivity)."""
    return {h - HOUR: v for h, v in demand.items()}


def truncate_sets(sets, k):
    return {key: hours[:k] for key, hours in sets.items()}


def snapshot_year(available, y):
    """Latest EIA-860 report year on or before y - 1, or None."""
    c = [a for a in available if a <= y - 1]
    return max(c) if c else None


def classify(gens, snap_plant, y, horizon=HORIZON_YEARS):
    """Group of a subplant in study year y from the EIA-860 snapshot rows of
    its plant ({generator_id: {"status", "code", "esc", "cap", "planned"}}).

    Only generators that exist in the snapshot count. Returns (group, cap, ex):
    group None (no existing generator), "NOTCOAL" (an existing generator is
    not coal), "R" (every existing generator has a planned retirement date on
    or before 31 Dec of y + horizon, including dates already past), "C" (none
    has), or "MIXED"; cap is their summed nameplate MW (0 unless coal); ex is
    the sorted list of existing generator ids."""
    ex = [g for g in sorted(gens)
          if g in snap_plant and is_existing(snap_plant[g].get("status"), snap_plant[g].get("code"))]
    if not ex:
        return None, 0.0, []
    if any(snap_plant[g].get("esc") not in COAL for g in ex):
        return "NOTCOAL", 0.0, ex
    cap = sum(float(snap_plant[g].get("cap") or 0.0) for g in ex)
    lim = dt.date(y + horizon, 12, 31)
    flags = [snap_plant[g].get("planned") is not None and snap_plant[g]["planned"] <= lim for g in ex]
    if all(flags):
        grp = "R"
    elif not any(flags):
        grp = "C"
    else:
        grp = "MIXED"
    return grp, cap, ex


def retire_end(gens, retired):
    """First hour after service ends: the month after the latest actual
    retirement date, if every generator has one; else None (still in service)."""
    ds = [retired.get(g) for g in gens]
    if not ds or any(d is None for d in ds):
        return None
    return month_after(max(ds))


def in_service_hours(y, study_start, coverage_end, rend):
    s, e = year_bounds(y, study_start, coverage_end)
    if rend is not None:
        e = min(e, rend)
    if e <= s:
        return 0
    return int((e - s).total_seconds() // 3600)


def collect(subyears, sets, sub_load, ann_load, study_start, coverage_end):
    """Accumulate stress-hour sums per (subplant, group) cluster.

    subyears: dicts {"key", "y", "group", "cap", "ba", "rend"}.
    sets: {(ba, y): [hours]}. sub_load: {key: {hour: MW}} (missing = 0 MW).
    ann_load: {key: {year: MWh}} (CEMS gross load summed over the year).
    Cluster sums: n (subplant-hours), w_n (sum of cap), w_on (sum of cap
    where output > 0), load (sum of MW), ann_load and ann_caph (cap x
    in-service hours of the year), for the all-hours capacity factor."""
    clusters = {}
    for sy in subyears:
        c = clusters.setdefault((sy["key"], sy["group"]), {
            "ba": sy["ba"], "n": 0, "w_n": 0.0, "w_on": 0.0, "load": 0.0,
            "ann_load": 0.0, "ann_caph": 0.0})
        loads = sub_load.get(sy["key"], {})
        for h in sets.get((sy["ba"], sy["y"]), []):
            if sy["rend"] is not None and h >= sy["rend"]:
                continue
            mw = loads.get(h, 0.0) or 0.0
            c["n"] += 1
            c["w_n"] += sy["cap"]
            c["load"] += mw
            if mw > 0:
                c["w_on"] += sy["cap"]
        c["ann_load"] += ann_load.get(sy["key"], {}).get(sy["y"], 0.0) or 0.0
        c["ann_caph"] += sy["cap"] * in_service_hours(sy["y"], study_start, coverage_end, sy["rend"])
    return clusters


def _div(a, b):
    return None if not b else a / b


def group_stats(clusters, group):
    cs = [clusters[k] for k in sorted(clusters, key=repr) if k[1] == group and clusters[k]["w_n"] > 0]
    wn = sum(c["w_n"] for c in cs)
    scf = _div(sum(c["load"] for c in cs), wn)
    acf = _div(sum(c["ann_load"] for c in cs), sum(c["ann_caph"] for c in cs))
    return {
        "clusters": len(cs),
        "pairs": sum(c["n"] for c in cs),
        "A": _div(sum(c["w_on"] for c in cs), wn),
        "SCF": scf,
        "ACF": acf,
        "lift": None if scf is None or not acf else scf / acf,
    }


def ba_matched(clusters):
    """Mean over BAs with both groups of A_R - A_C, weighted by R's sum of cap."""
    by = {}
    for k in sorted(clusters, key=repr):
        c = clusters[k]
        if k[1] not in ("R", "C") or c["w_n"] <= 0:
            continue
        d = by.setdefault(c["ba"], {"R": [0.0, 0.0], "C": [0.0, 0.0]})
        d[k[1]][0] += c["w_on"]
        d[k[1]][1] += c["w_n"]
    num = den = 0.0
    nba = 0
    for ba in sorted(by):
        d = by[ba]
        if d["R"][1] > 0 and d["C"][1] > 0:
            diff = d["R"][0] / d["R"][1] - d["C"][0] / d["C"][1]
            num += d["R"][1] * diff
            den += d["R"][1]
            nba += 1
    return (None if den == 0 else num / den), nba


def boot_ci(clusters, field="A", b=BOOT, seed=SEED):
    """95% percentile interval of (R - C) for A (field "A") or SCF (field
    "SCF"), resampling subplant clusters with replacement within each group."""
    num = "w_on" if field == "A" else "load"
    r = [clusters[k] for k in sorted(clusters, key=repr) if k[1] == "R" and clusters[k]["w_n"] > 0]
    c = [clusters[k] for k in sorted(clusters, key=repr) if k[1] == "C" and clusters[k]["w_n"] > 0]
    if not r or not c:
        return None

    def stat(cs):
        return sum(x[num] for x in cs) / sum(x["w_n"] for x in cs)

    rng = random.Random(seed)
    diffs = []
    for _ in range(b):
        rr = [r[rng.randrange(len(r))] for _ in range(len(r))]
        cc = [c[rng.randrange(len(c))] for _ in range(len(c))]
        diffs.append(stat(rr) - stat(cc))
    diffs.sort()
    return [diffs[int(round(0.025 * (b - 1)))], diffs[int(round(0.975 * (b - 1)))]]


def score(main, gap, fern, ci_a):
    """Score S1-S8 of docs/stress-plan.md: {id: True/False/None}."""
    R, C = main["R"], main["C"]
    out = {}
    both_a = R["A"] is not None and C["A"] is not None
    out["S1"] = (R["A"] < C["A"]) if both_a else None
    out["S2"] = (C["A"] - R["A"] >= 0.10) if both_a else None
    out["S3"] = (R["SCF"] < C["SCF"]) if R["SCF"] is not None and C["SCF"] is not None else None
    out["S4"] = (R["lift"] > C["lift"]) if R["lift"] is not None and C["lift"] is not None else None
    out["S5"] = None if gap is None else gap < 0
    fr, fc = (fern or {}).get("R"), (fern or {}).get("C")
    out["S6"] = (fr["A"] < fc["A"]) if fr and fc and fr["A"] is not None and fc["A"] is not None else None
    out["S7"] = None if C["A"] is None else C["A"] >= 0.80
    out["S8"] = None if not ci_a else (ci_a[1] < 0 or ci_a[0] > 0)
    return out
