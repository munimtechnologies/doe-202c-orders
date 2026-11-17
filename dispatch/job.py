# SPDX-License-Identifier: Apache-2.0
"""dispatch-1 job: hourly output of DOE 202(c)-ordered units in their grid's
tightest hours. See docs/dispatch-plan.md (pre-registered before any hourly
data was read).

Data (all public, no key): Catalyst Cooperative's PUDL nightly build (CC BY 4.0)
of EPA CEMS hourly emissions, EIA-930 hourly balancing-authority operations,
EIA-860 plants and the EPA-EIA unit crosswalk.

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
import dispatch_core as core  # noqa: E402

import pyarrow as pa  # noqa: E402
import pyarrow.compute as pc  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

BASE = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/"
UA = {"User-Agent": "mv2-dispatch-1/0.1 (MV2 of Munim, Inc.; mv2@munimtech.com)"}
REPO = os.path.dirname(HERE)
ORDERS = os.path.join(REPO, "skills", "doe-202c-orders", "doe_202c_orders.csv")
PLANTS = os.path.join(REPO, "skills", "doe-202c-orders", "doe_202c_plant_mw.csv")


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
        # plain datetime on the hour (pandas Timestamps hash and compare like this)
        return dt.datetime(x.year, x.month, x.day, x.hour, tzinfo=core.UTC)
    return None


def plain(col):
    """Decode dictionary-encoded columns so is_in compares plain values."""
    if pa.types.is_dictionary(col.type):
        return col.cast(col.type.value_type)
    return col


def plant_bas(path, ids):
    """Latest non-empty EIA-860 balancing authority code per plant."""
    names = pq.read_schema(path).names
    log("scd_plants columns:", names)
    if "balancing_authority_code_eia" not in names:
        return {}
    date_col = "report_date" if "report_date" in names else None
    cols = ["plant_id_eia", "balancing_authority_code_eia"] + ([date_col] if date_col else [])
    t = pq.read_table(path, columns=cols)
    t = t.filter(pc.is_in(t["plant_id_eia"], value_set=pa.array(ids, type=t["plant_id_eia"].type)))
    best = {}
    for r in t.to_pylist():
        ba = r["balancing_authority_code_eia"]
        if not ba:
            continue
        d = r.get(date_col) if date_col else None
        key = r["plant_id_eia"]
        if key not in best or (d is not None and (best[key][0] is None or d > best[key][0])):
            best[key] = (d, ba)
    return {k: (v[1], str(v[0])) for k, v in best.items()}


def unit_map(path, plants):
    """EPA emissions units for each plant's ordered EIA generators."""
    names = pq.read_schema(path).names
    log("crosswalk columns:", names)
    need = {"plant_id_eia", "generator_id", "emissions_unit_id_epa"}
    out = {k: set() for k in plants}
    if not need <= set(names):
        return out, "crosswalk columns missing"
    t = pq.read_table(path, columns=sorted(need))
    for r in t.to_pylist():
        for k, info in plants.items():
            if r["plant_id_eia"] == info["plant_id_eia"] and r["generator_id"] in info["generators"] \
                    and r["emissions_unit_id_epa"]:
                out[k].add(str(r["emissions_unit_id_epa"]))
    return out, "crosswalk"


def read_demand(path, bas):
    names = pq.read_schema(path).names
    log("eia930 columns:", names)
    order = [c for c in ("demand_imputed_eia_mwh", "demand_adjusted_mwh", "demand_reported_mwh") if c in names]
    t = pq.read_table(path, columns=["datetime_utc", "balancing_authority_code_eia"] + order)
    col = plain(t["balancing_authority_code_eia"])
    t = t.filter(pc.is_in(col, value_set=pa.array(sorted(bas), type=col.type)))
    demand = {b: {} for b in bas}
    for r in t.to_pylist():
        h = to_utc(r["datetime_utc"])
        if h is None or h < core.STUDY_START:
            continue
        v = None
        for c in order:
            if r[c] is not None:
                v = float(r[c])
                break
        if v is not None:
            demand[r["balancing_authority_code_eia"]][h] = v
    return demand, order


def read_cems(url, plants, units):
    """Sum gross load per plant-hour for the ordered units, years >= 2021."""
    f = HttpRangeFile(url)
    pf = pq.ParquetFile(f)
    md = pf.metadata
    names = pf.schema_arrow.names
    log("cems columns:", names, "row groups:", md.num_row_groups, "size:", f.size)
    idx = {md.row_group(0).column(i).path_in_schema: i for i in range(md.num_columns)}
    ids = sorted({p["plant_id_eia"] for p in plants.values()})
    by_id = {}
    for k, p in plants.items():
        by_id.setdefault(p["plant_id_eia"], []).append(k)
    cols = ["plant_id_eia", "emissions_unit_id_epa", "operating_datetime_utc", "gross_load_mw", "year"]
    gen = {k: {} for k in plants}
    units_seen = {k: {} for k in plants}
    coverage_end = None
    read_groups = 0
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        st = rg.column(idx["year"]).statistics
        if st is not None and st.has_min_max and st.max < core.STUDY_START.year:
            continue
        st = rg.column(idx["plant_id_eia"]).statistics
        if st is not None and st.has_min_max and (st.max < ids[0] or st.min > ids[-1]):
            # still needed for the coverage end; read only the time column
            tt = pf.read_row_group(g, columns=["operating_datetime_utc"])
            m = pc.max(tt["operating_datetime_utc"]).as_py()
            m = to_utc(m)
            if m is not None and (coverage_end is None or m > coverage_end):
                coverage_end = m
            continue
        t = pf.read_row_group(g, columns=cols)
        read_groups += 1
        m = to_utc(pc.max(t["operating_datetime_utc"]).as_py())
        if m is not None and (coverage_end is None or m > coverage_end):
            coverage_end = m
        t = t.filter(pc.is_in(t["plant_id_eia"], value_set=pa.array(ids, type=t["plant_id_eia"].type)))
        if t.num_rows == 0:
            continue
        for r in t.to_pylist():
            h = to_utc(r["operating_datetime_utc"])
            if h is None or h < core.STUDY_START:
                continue
            u = str(r["emissions_unit_id_epa"])
            mw = r["gross_load_mw"] or 0.0
            for k in by_id[r["plant_id_eia"]]:
                units_seen[k][u] = units_seen[k].get(u, 0.0) + mw
                if u in units[k]:
                    gen[k][h] = gen[k].get(h, 0.0) + mw
        if g % 20 == 0:
            log("row group", g, "of", md.num_row_groups, "fetched MB", round(f.fetched / 1e6, 1))
    log("row groups read:", read_groups, "fetched MB:", round(f.fetched / 1e6, 1))
    return gen, units_seen, coverage_end


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, dt.datetime):
        return x.isoformat()
    if isinstance(x, set):
        return sorted(x)
    return x


def fmt(v, pct=True):
    if v is None:
        return "n/a"
    return "%.1f%%" % (100 * v) if pct else "%.1f" % v


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

    rows = core.read_orders(ORDERS)
    plants = core.read_plants(PLANTS)
    summer = {k: v["summer_mw"] for k, v in plants.items()}
    ids = sorted({p["plant_id_eia"] for p in plants.values()})

    p860 = download("core_eia860__scd_plants.parquet", a.data_dir)
    xw = download("core_epa__assn_eia_epacamd.parquet", a.data_dir)
    e930 = download("core_eia930__hourly_operations.parquet", a.data_dir)

    ba860 = plant_bas(p860, ids)
    ba = {}
    for k, p in plants.items():
        if p["plant_id_eia"] in ba860:
            ba[k] = {"ba": ba860[p["plant_id_eia"]][0], "source": "EIA-860 " + ba860[p["plant_id_eia"]][1],
                     "fallback": core.PLANT_BA[k]}
        else:
            ba[k] = {"ba": core.PLANT_BA[k], "source": "fallback", "fallback": core.PLANT_BA[k]}
    log("BA:", ba)
    units, umethod = unit_map(xw, plants)
    log("units:", units, umethod)
    demand, dcols = read_demand(e930, {v["ba"] for v in ba.values()})
    for b, d in demand.items():
        log("demand", b, len(d), "hours", min(d) if d else None, max(d) if d else None)

    gen, seen, cov = read_cems(BASE + "core_epacems__hourly_emissions.parquet", plants, units)
    if cov is None:
        sys.exit("no CEMS rows read for 2021 or later")
    coverage_end = cov + core.HOUR
    log("CEMS coverage end (exclusive):", coverage_end)

    results = {}
    for k, info in plants.items():
        if not units[k]:
            results[k] = {"unmapped": True, "units_seen": seen[k]}
            log(k, "UNMAPPED; units seen:", seen[k])
            continue
        d = demand.get(ba[k]["ba"], {})
        if not d:
            results[k] = {"no_demand": True, "ba": ba[k]}
            log(k, "no demand for", ba[k])
            continue
        r = core.analyse_plant(k, info, rows, d, gen[k], coverage_end)
        r["ba"] = ba[k]
        r["units"] = sorted(units[k])
        r["units_seen_mwh_since_2021"] = {u: round(v, 1) for u, v in seen[k].items()}
        r["S1_detail"] = [{"hour_utc": h.isoformat(), "demand_mwh": d.get(h), "gen_mw": gen[k].get(h)}
                          for h in r["S1_hours"]]
        del r["S1_hours"]
        results[k] = r

    preds = core.score_predictions(results, summer)
    fleet = core.fleet_cf(results, summer, "S1")
    fleet_all = core.fleet_cf(results, summer, "ALL")
    fleet_base = core.fleet_cf(results, summer, "BASE")
    out = {
        "preregistration": "dispatch-1",
        "generated_utc": dt.datetime.now(core.UTC).isoformat(),
        "cems_coverage_end_exclusive": coverage_end.isoformat(),
        "demand_columns_in_order": dcols,
        "unit_method": umethod,
        "fleet_cf_S1": fleet, "fleet_cf_ALL": fleet_all, "fleet_cf_BASE": fleet_base,
        "predictions": preds,
        "plants": results,
    }
    with open(os.path.join(a.out_dir, "dispatch1.json"), "w", encoding="utf-8") as f:
        json.dump(jsonable(out), f, indent=1)

    lines = ["# dispatch-1 results (machine-written)", "",
             "CEMS data through %s (exclusive). Demand: first non-null of %s." % (coverage_end.isoformat(), dcols), "",
             "| plant | BA | units | order hours | S1 online | S1 CF | all-order CF | baseline S1 CF | S2 online (n) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for k, r in results.items():
        if r.get("unmapped") or r.get("no_demand"):
            lines.append("| %s | | not scorable (%s) | | | | | | |" % (k, "unmapped units" if r.get("unmapped") else "no demand"))
            continue
        s2 = r.get("S2")
        lines.append("| %s | %s | %s | %d | %s | %s | %s | %s | %s |" % (
            k, r["ba"]["ba"], "|".join(r["units"]), r["order_hours"],
            fmt(r["S1"]["online_share"]), fmt(r["S1"]["cf"]), fmt(r["ALL"]["cf"]), fmt(r["BASE"]["cf"]),
            ("%s (%d)" % (fmt(s2["online_share"]), s2["n"])) if s2 and s2["n"] else "n/a"))
    lines += ["", "Fleet: S1 %s, all order hours %s, baseline S1 %s." % (fmt(fleet), fmt(fleet_all), fmt(fleet_base)), "",
              "Predictions: " + ", ".join("%s=%s" % (k, {True: "held", False: "failed", None: "not scorable"}[v])
                                         for k, v in preds.items())]
    with open(os.path.join(a.out_dir, "dispatch1.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
