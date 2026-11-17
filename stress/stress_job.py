# SPDX-License-Identifier: Apache-2.0
"""stress-1 job: were U.S. coal units scheduled to retire running in their
grid's tightest hours of 2022-2026 as often as coal units staying open?
See docs/stress-plan.md (pre-registered before any hourly data was read).

Data (all public, no key): Catalyst Cooperative's PUDL nightly build (CC BY 4.0)
of EPA CEMS hourly emissions, EIA-930 hourly balancing-authority operations,
EIA-860 generators and plants, and the EPA-EIA subplant crosswalk.

MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's
name. Apache-2.0.
"""
import argparse
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stress_core as core  # noqa: E402

import pyarrow as pa  # noqa: E402
import pyarrow.compute as pc  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

BASE = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/"
UA = {"User-Agent": "mv2-stress-1/0.1 (MV2 of Munim, Inc.; mv2@munimtech.com)"}
# Plants with DOE 202(c) orders (descriptive tag only): Campbell, Centralia,
# Craig, Culley, Schahfer, Stanton.
ORDERED = {1710: "J.H. Campbell", 3845: "Centralia", 6021: "Craig", 1012: "F.B. Culley",
           6085: "R.M. Schahfer", 564: "Stanton"}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def wait_for(url, token, minutes):
    """Do not read any hourly data until the plan is public."""
    deadline = time.time() + minutes * 60
    while True:
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                if token in r.read().decode("utf-8", "replace"):
                    log("plan live:", url)
                    return True
        except Exception as e:  # noqa: BLE001
            log("plan check failed:", e)
        if time.time() > deadline:
            log("plan not live after", minutes, "minutes; stopping")
            return False
        time.sleep(300)


def download(name, data_dir):
    path = os.path.join(data_dir, name)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        log("cached", name, os.path.getsize(path))
        return path
    tmp = path + ".part"
    req = urllib.request.Request(BASE + name, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(tmp, path)
    log("downloaded", name, os.path.getsize(path))
    return path


class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable view of a remote file through HTTP Range requests."""

    def __init__(self, url, block=4 << 20):
        super().__init__()
        req = urllib.request.Request(url, method="HEAD", headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            self.size = int(r.headers["Content-Length"])
        self.url, self.pos, self.block = url, 0, block
        self._cs, self._cb = None, b""
        self.fetched = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        if whence == 0:
            self.pos = off
        elif whence == 1:
            self.pos += off
        else:
            self.pos = self.size + off
        return self.pos

    def _get(self, start, end):
        last = None
        for attempt in range(6):
            try:
                hdr = dict(UA)
                hdr["Range"] = "bytes=%d-%d" % (start, end - 1)
                req = urllib.request.Request(self.url, headers=hdr)
                with urllib.request.urlopen(req, timeout=180) as r:
                    data = r.read()
                if len(data) != end - start:
                    raise IOError("short read %d of %d" % (len(data), end - start))
                self.fetched += len(data)
                return data
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2 ** attempt)
        raise last

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if n == 0:
            return b""
        if n >= self.block:
            data = self._get(self.pos, self.pos + n)
        else:
            if not (self._cs is not None and self._cs <= self.pos
                    and self.pos + n <= self._cs + len(self._cb)):
                end = min(self.size, self.pos + self.block)
                self._cb = self._get(self.pos, end)
                self._cs = self.pos
            off = self.pos - self._cs
            data = self._cb[off:off + n]
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def to_utc(x):
    if x is None:
        return None
    if isinstance(x, dt.datetime):
        x = x.replace(tzinfo=core.UTC) if x.tzinfo is None else x.astimezone(core.UTC)
        return dt.datetime(x.year, x.month, x.day, x.hour, tzinfo=core.UTC)
    return None


def plain(col):
    """Decode dictionary-encoded columns so is_in / group_by see plain values."""
    if pa.types.is_dictionary(col.type):
        return col.cast(col.type.value_type)
    return col


def plain_table(t):
    for i, name in enumerate(t.column_names):
        if pa.types.is_dictionary(t.schema.field(i).type):
            t = t.set_column(i, name, plain(t.column(i)))
    return t


def isin(col, values):
    col = plain(col)
    return pc.is_in(col, value_set=pa.array(values, type=col.type))


def read_generators(path):
    names = pq.read_schema(path).names
    cols = ["plant_id_eia", "generator_id", "report_date", "operational_status", "operational_status_code",
            "energy_source_code_1", "capacity_mw", "planned_generator_retirement_date", "generator_retirement_date"]
    missing = [c for c in cols if c not in names]
    if missing:
        sys.exit("scd_generators is missing columns %s; have %s" % (missing, names))
    t = plain_table(pq.read_table(path, columns=cols))
    coal = t.filter(isin(t["energy_source_code_1"], sorted(core.COAL)))
    plants = sorted({p for p in coal["plant_id_eia"].to_pylist() if p is not None})
    t = t.filter(isin(t["plant_id_eia"], plants))
    snap, retired, statuses = {}, {}, {}
    for r in t.to_pylist():
        rd = core.as_date(r["report_date"])
        if rd is None or r["plant_id_eia"] is None or r["generator_id"] is None:
            continue
        y, p, g = rd.year, r["plant_id_eia"], str(r["generator_id"])
        snap.setdefault(y, {}).setdefault(p, {})[g] = {
            "status": r["operational_status"], "code": r["operational_status_code"],
            "esc": r["energy_source_code_1"], "cap": r["capacity_mw"],
            "planned": core.as_date(r["planned_generator_retirement_date"])}
        key = (r["operational_status"], r["operational_status_code"])
        statuses[str(key)] = statuses.get(str(key), 0) + 1
        ret = core.as_date(r["generator_retirement_date"])
        if ret is not None:
            prev = retired.get((p, g))
            if prev is None or y > prev[0]:
                retired[(p, g)] = (y, ret)
    log("generator rows:", t.num_rows, "coal plants:", len(plants), "report years:", sorted(snap))
    log("status values:", statuses)
    return snap, {k: v[1] for k, v in retired.items()}, plants


def read_subplants(path, plants):
    names = pq.read_schema(path).names
    log("subplant columns:", names)
    t = plain_table(pq.read_table(path, columns=["plant_id_eia", "subplant_id", "emissions_unit_id_epa", "generator_id"]))
    t = t.filter(isin(t["plant_id_eia"], plants))
    subs, unit_sub, conflicts = {}, {}, 0
    for r in t.to_pylist():
        if r["subplant_id"] is None or r["plant_id_eia"] is None:
            continue
        key = (r["plant_id_eia"], int(r["subplant_id"]))
        s = subs.setdefault(key, {"units": set(), "gens": set()})
        if r["emissions_unit_id_epa"]:
            u = (r["plant_id_eia"], str(r["emissions_unit_id_epa"]))
            s["units"].add(u[1])
            if u in unit_sub and unit_sub[u] != key:
                conflicts += 1
            else:
                unit_sub[u] = key
        if r["generator_id"]:
            s["gens"].add(str(r["generator_id"]))
    log("subplants:", len(subs), "EPA units:", len(unit_sub), "unit conflicts:", conflicts)
    return subs, unit_sub, conflicts


def plant_bas(path, ids):
    """Latest non-empty EIA-860 balancing authority code per plant."""
    t = plain_table(pq.read_table(path, columns=["plant_id_eia", "report_date", "balancing_authority_code_eia"]))
    t = t.filter(isin(t["plant_id_eia"], ids))
    best = {}
    for r in t.to_pylist():
        ba = r["balancing_authority_code_eia"]
        d = core.as_date(r["report_date"])
        if not ba or d is None:
            continue
        if r["plant_id_eia"] not in best or d > best[r["plant_id_eia"]][0]:
            best[r["plant_id_eia"]] = (d, str(ba))
    return {k: v[1] for k, v in best.items()}


def read_demand(path, bas):
    names = pq.read_schema(path).names
    order = [c for c in ("demand_imputed_eia_mwh", "demand_adjusted_mwh", "demand_reported_mwh") if c in names]
    t = plain_table(pq.read_table(path, columns=["datetime_utc", "balancing_authority_code_eia"] + order))
    t = t.filter(isin(t["balancing_authority_code_eia"], sorted(bas)))
    demand = {}
    for r in t.to_pylist():
        h = to_utc(r["datetime_utc"])
        if h is None:
            continue
        v = None
        for c in order:
            if r[c] is not None:
                v = float(r[c])
                break
        if v is not None:
            demand.setdefault(r["balancing_authority_code_eia"], {})[h] = v
    log("demand BAs:", len(demand), "of", len(bas), "columns:", order)
    return demand, order


def cems_open(url):
    f = HttpRangeFile(url)
    pf = pq.ParquetFile(f)
    md = pf.metadata
    idx = {md.row_group(0).column(i).path_in_schema: i for i in range(md.num_columns)}
    log("cems columns:", pf.schema_arrow.names, "row groups:", md.num_row_groups, "size:", f.size)
    groups, cov = [], None
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        st = rg.column(idx["year"]).statistics
        if st is not None and st.has_min_max and st.max < core.STUDY_START.year:
            continue
        groups.append(g)
        st = rg.column(idx["operating_datetime_utc"]).statistics
        m = None
        if st is not None and st.has_min_max:
            m = to_utc(st.max) if isinstance(st.max, dt.datetime) else None
        if m is None:
            tt = pf.read_row_group(g, columns=["operating_datetime_utc"])
            m = to_utc(pc.max(tt["operating_datetime_utc"]).as_py())
        if m is not None and (cov is None or m > cov):
            cov = m
    log("row groups from", core.STUDY_START.year, ":", len(groups), "coverage max hour:", cov)
    return f, pf, idx, groups, cov


def cems_read(f, pf, idx, groups, plant_ids, hours, ba_of_plant, wanted):
    """Annual gross load per (plant, unit, year) and hourly gross load per
    (plant, unit) for the stress hours of the plant's BA."""
    md = pf.metadata
    cols = ["plant_id_eia", "emissions_unit_id_epa", "operating_datetime_utc", "gross_load_mw", "year"]
    ann, hourly = {}, {}
    hours_sorted = sorted(hours)
    lo, hi = plant_ids[0], plant_ids[-1]
    for n, g in enumerate(groups):
        st = md.row_group(g).column(idx["plant_id_eia"]).statistics
        if st is not None and st.has_min_max and (st.max < lo or st.min > hi):
            continue
        t = plain_table(pf.read_row_group(g, columns=cols))
        t = t.filter(isin(t["plant_id_eia"], plant_ids))
        if t.num_rows == 0:
            continue
        agg = t.group_by(["plant_id_eia", "emissions_unit_id_epa", "year"]).aggregate([("gross_load_mw", "sum")])
        for r in agg.to_pylist():
            k = (r["plant_id_eia"], str(r["emissions_unit_id_epa"]), int(r["year"]))
            ann[k] = ann.get(k, 0.0) + (r["gross_load_mw_sum"] or 0.0)
        tc = t["operating_datetime_utc"]
        try:
            if tc.type.tz is None:
                vs = pa.array([h.replace(tzinfo=None) for h in hours_sorted], type=tc.type)
            else:
                vs = pa.array(hours_sorted, type=tc.type)
            ts = t.filter(pc.is_in(tc, value_set=vs))
            rows = ts.select(["plant_id_eia", "emissions_unit_id_epa", "operating_datetime_utc", "gross_load_mw"]).to_pylist()
            fallback = False
        except Exception as e:  # noqa: BLE001
            log("is_in on timestamps failed (%s); filtering in Python" % e)
            rows = t.select(["plant_id_eia", "emissions_unit_id_epa", "operating_datetime_utc", "gross_load_mw"]).to_pylist()
            fallback = True
        for r in rows:
            h = to_utc(r["operating_datetime_utc"])
            if fallback and h not in hours:
                continue
            ba = ba_of_plant.get(r["plant_id_eia"])
            if ba is None or h not in wanted.get(ba, ()):
                continue
            k = (r["plant_id_eia"], str(r["emissions_unit_id_epa"]))
            hourly.setdefault(k, {})
            hourly[k][h] = hourly[k].get(h, 0.0) + (r["gross_load_mw"] or 0.0)
        if n % 20 == 0:
            log("row group", n, "of", len(groups), "fetched MB", round(f.fetched / 1e6, 1))
    log("CEMS done; fetched MB", round(f.fetched / 1e6, 1), "unit-years", len(ann), "units with stress rows", len(hourly))
    return ann, hourly


def evaluate(subyears, sets, sub_load, sub_ann, coverage_end, boot=True):
    cl = core.collect(subyears, sets, sub_load, sub_ann, core.STUDY_START, coverage_end)
    out = {g: core.group_stats(cl, g) for g in ("R", "C", "MIXED")}
    gap, nba = core.ba_matched(cl)
    out["ba_matched_gap_A"] = gap
    out["ba_matched_n_ba"] = nba
    if boot:
        out["ci_A_R_minus_C"] = core.boot_ci(cl, "A")
        out["ci_SCF_R_minus_C"] = core.boot_ci(cl, "SCF")
    return out, cl


def fmt(v):
    return "n/a" if v is None else "%.1f%%" % (100 * v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-for", default="")
    ap.add_argument("--token", default="")
    ap.add_argument("--minutes", type=int, default=240)
    a = ap.parse_args()
    os.makedirs(a.data_dir, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    if a.wait_for and not wait_for(a.wait_for, a.token, a.minutes):
        sys.exit(3)

    gpath = download("core_eia860__scd_generators.parquet", a.data_dir)
    ppath = download("core_eia860__scd_plants.parquet", a.data_dir)
    spath = download("core_epa__assn_eia_epacamd_subplant_ids.parquet", a.data_dir)
    dpath = download("core_eia930__hourly_operations.parquet", a.data_dir)

    snap, retired, coal_plants = read_generators(gpath)
    subs, unit_sub, conflicts = read_subplants(spath, coal_plants)
    bas = plant_bas(ppath, coal_plants)
    avail = sorted(snap)

    # subplant-years
    counts, raw = {}, []
    for key in sorted(subs, key=repr):
        s = subs[key]
        if not s["units"] or not s["gens"]:
            continue
        for y in core.YEARS:
            sy = core.snapshot_year(avail, y)
            sp = snap.get(sy, {}).get(key[0], {})
            grp, cap, ex = core.classify(s["gens"], sp, y)
            ck = "%d %s" % (y, grp)
            counts[ck] = counts.get(ck, 0) + 1
            if grp not in ("R", "C", "MIXED") or cap < core.MIN_MW:
                continue
            rend = core.retire_end([(key[0], g) for g in ex], retired)
            raw.append({"key": key, "y": y, "group": grp, "cap": cap, "ba": bas.get(key[0]),
                        "rend": rend, "snapshot": sy, "gens": ex})
    log("subplant-year groups:", counts)
    demand, dcols = read_demand(dpath, {r["ba"] for r in raw if r["ba"]})
    subyears = [r for r in raw if r["ba"] in demand]
    no_demand = sorted({str(r["ba"]) for r in raw if r["ba"] not in demand})
    log("subplant-years kept:", len(subyears), "dropped for no BA demand:", len(raw) - len(subyears), no_demand)

    url = BASE + "core_epacems__hourly_emissions.parquet"
    f, pf, idx, groups, cov = cems_open(url)
    if cov is None:
        sys.exit("no CEMS rows for the study years")
    coverage_end = cov + core.HOUR
    log("CEMS coverage end (exclusive):", coverage_end)

    used = sorted({r["ba"] for r in subyears})
    dem = {b: demand[b] for b in used}
    main_sets = core.stress_sets(dem, core.YEARS, core.STUDY_START, coverage_end, core.TOP_K)
    small_sets = core.truncate_sets(main_sets, core.TOP_K_SMALL)
    shift_sets = core.stress_sets({b: core.shift_demand(d) for b, d in dem.items()}, core.YEARS,
                                  core.STUDY_START, coverage_end, core.TOP_K)
    fern_sets = core.window_sets(dem, core.FERN, coverage_end, core.FERN_K, 2026)
    wanted, hours = {}, set()
    for sets in (main_sets, shift_sets, fern_sets):
        for (b, _y), hs in sets.items():
            wanted.setdefault(b, set()).update(hs)
            hours.update(hs)
    log("stress hours (distinct):", len(hours))

    plant_ids = sorted({r["key"][0] for r in subyears})
    ba_of_plant = {p: bas[p] for p in plant_ids}
    ann, hourly = cems_read(f, pf, idx, groups, plant_ids, hours, ba_of_plant, wanted)

    sub_load, sub_ann = {}, {}
    unmapped = 0
    for (p, u), hrs in hourly.items():
        key = unit_sub.get((p, u))
        if key is None:
            unmapped += 1
            continue
        d = sub_load.setdefault(key, {})
        for h, mw in hrs.items():
            d[h] = d.get(h, 0.0) + mw
    for (p, u, y), mwh in ann.items():
        key = unit_sub.get((p, u))
        if key is None:
            continue
        sub_ann.setdefault(key, {})
        sub_ann[key][y] = sub_ann[key].get(y, 0.0) + mwh
    log("CEMS units with stress rows but no subplant:", unmapped)

    main_res, cl = evaluate(subyears, main_sets, sub_load, sub_ann, coverage_end)
    res = {"main": main_res}
    res["top10"], _ = evaluate(subyears, small_sets, sub_load, sub_ann, coverage_end, boot=False)
    res["shift"], _ = evaluate(subyears, shift_sets, sub_load, sub_ann, coverage_end, boot=False)
    active = [r for r in subyears if (sub_ann.get(r["key"], {}).get(r["y"], 0.0) or 0.0) > 0]
    res["active_years_only"], _ = evaluate(active, main_sets, sub_load, sub_ann, coverage_end, boot=False)
    fern_years = [r for r in subyears if r["y"] == 2026]
    res["fern"], _ = evaluate(fern_years, fern_sets, sub_load, sub_ann, coverage_end, boot=False)
    by_year = {}
    for y in core.YEARS:
        by_year[str(y)], _ = evaluate([r for r in subyears if r["y"] == y], main_sets, sub_load, sub_ann,
                                      coverage_end, boot=False)
    res["by_year"] = by_year

    preds = core.score(main_res, main_res["ba_matched_gap_A"], res["fern"], main_res["ci_A_R_minus_C"])

    subtable = []
    for k in sorted(cl, key=repr):
        c = cl[k]
        rows = [r for r in subyears if r["key"] == k[0] and r["group"] == k[1]]
        subtable.append({
            "plant_id_eia": k[0][0], "subplant_id": k[0][1], "group": k[1], "ba": c["ba"],
            "years": sorted({r["y"] for r in rows}), "cap_mw": max(r["cap"] for r in rows),
            "generators": sorted({g for r in rows for g in r["gens"]}),
            "ordered_202c_plant": ORDERED.get(k[0][0], ""),
            "stress_hours": c["n"],
            "A": None if not c["w_n"] else c["w_on"] / c["w_n"],
            "SCF": None if not c["w_n"] else c["load"] / c["w_n"],
            "ACF": None if not c["ann_caph"] else c["ann_load"] / c["ann_caph"]})

    out = {
        "preregistration": "stress-1",
        "generated_utc": dt.datetime.now(core.UTC).isoformat(),
        "cems_coverage_end_exclusive": coverage_end.isoformat(),
        "eia860_report_years": avail,
        "demand_columns_in_order": dcols,
        "subplant_year_counts": counts,
        "subplant_unit_conflicts": conflicts,
        "dropped_bas_without_demand": no_demand,
        "results": res,
        "predictions": preds,
        "stress_hours": {"%s %d" % k: [h.isoformat() for h in v] for k, v in sorted(main_sets.items())},
        "subplants": subtable,
    }

    def js(x):
        if isinstance(x, dict):
            return {str(k): js(v) for k, v in x.items()}
        if isinstance(x, (list, tuple, set)):
            return [js(v) for v in x]
        if isinstance(x, (dt.datetime, dt.date)):
            return x.isoformat()
        return x

    with open(os.path.join(a.out_dir, "stress1.json"), "w", encoding="utf-8") as fh:
        json.dump(js(out), fh, indent=1)

    m = main_res
    lines = ["# stress-1 results (machine-written)", "",
             "CEMS through %s (exclusive). EIA-860 report years %s. Demand: first non-null of %s." % (
                 coverage_end.isoformat(), avail, dcols), "",
             "| set | group | subplants | subplant-hours | online (cap-weighted) | stress CF | all-hours CF | lift |",
             "|---|---|---|---|---|---|---|---|"]
    for name in ("main", "top10", "shift", "active_years_only", "fern"):
        for g in ("R", "C", "MIXED"):
            s = res[name][g]
            lines.append("| %s | %s | %d | %d | %s | %s | %s | %s |" % (
                name, g, s["clusters"], s["pairs"], fmt(s["A"]), fmt(s["SCF"]), fmt(s["ACF"]),
                "n/a" if s["lift"] is None else "%.2f" % s["lift"]))
    lines += ["", "BA-matched gap in online share (R - C): %s over %d BAs." % (
        fmt(m["ba_matched_gap_A"]), m["ba_matched_n_ba"]),
        "95%% bootstrap interval, online share R - C: %s; stress CF R - C: %s." % (
            m["ci_A_R_minus_C"], m["ci_SCF_R_minus_C"]), "",
        "Predictions: " + ", ".join("%s=%s" % (k, {True: "held", False: "failed", None: "not scorable"}[v])
                                   for k, v in preds.items())]
    with open(os.path.join(a.out_dir, "stress1.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
