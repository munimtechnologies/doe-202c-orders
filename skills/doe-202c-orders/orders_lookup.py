"""orders_lookup: offline lookup of every DOE Federal Power Act 202(c) emergency order, 2025-2026.

Copyright 2026 MV2, Munim, Inc. Apache-2.0. Made with AI agents working in MV2's name.

Reads doe_202c_orders.csv (one row per order, extension or amendment, transcribed from DOE's
2025 and 2026 202(c) order pages, plus one amended order that only ERCOT's page lists),
doe_202c_plant_mw.csv (summer MW of the units each plant order covers) and doe_202c_court.csv
(court actions on orders found in the opinions and in reporting), all next to this file.
Standard library only; no network.

    python orders_lookup.py in-force [--date 2026-11-09] [--kind plant|event|island] [--json]
    python orders_lookup.py expiring [--date 2026-11-09] [--days 30] [--json]
    python orders_lookup.py plant <plant key, name or EIA plant id> [--date ...] [--json]
    python orders_lookup.py order <order number, e.g. 202-26-39> [--json]
    python orders_lookup.py court [--json]
    python orders_lookup.py summary [--date ...] [--json]

Days are calendar dates; an order is in force from its start date through its expiry date,
both counted. Times of day are shown but not used. A court action changes nothing in the
in-force dates: they are the dates in DOE's orders. In the court table, date_kind says what a
date is: 'decided' (a ruling), 'filed' (a filing) or 'reported' (only a report's date is known).
Exit codes: 0 found, 1 nothing matched, 2 bad input.
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from collections import Counter

__version__ = "0.2.1"

# The last date DOE's pages were read for this table. Orders issued later are not in it.
TABLE_AS_OF = "2026-11-13"
# The last date court actions were looked for. Only actions found by then are in the court table.
COURT_AS_OF = "2026-11-13"
DOE_PAGES = ("https://www.energy.gov/ceser/2026-doe-202c-orders",
             "https://www.energy.gov/ceser/2025-doe-202c-orders")

HERE = os.path.dirname(os.path.abspath(__file__))
ORDERS = os.path.join(HERE, "doe_202c_orders.csv")
PLANT_MW = os.path.join(HERE, "doe_202c_plant_mw.csv")
COURT = os.path.join(HERE, "doe_202c_court.csv")
KINDS = ("plant", "event", "island")
COAL_FUELS = frozenset({"BIT", "SUB", "LIG", "ANT", "RC", "WC", "SGC"})
SHOW = ("order", "kind", "area", "recipient", "plant_key", "plant", "issued", "effective",
        "expires", "expires_time", "note", "source")
COURT_SHOW = ("order", "plant_key", "date", "date_kind", "court", "case", "action", "source", "note")
COURT_LIMIT = ("Court actions found as of %s; pending cases and actions not yet found are not "
               "listed. A court action on one order says nothing about any other order, and the "
               "in-force dates here are the dates in DOE's orders." % COURT_AS_OF)


def _date(s):
    s = (s or "").strip()
    return dt.date.fromisoformat(s) if s else None


def load_orders(path=ORDERS):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for c in ("issued", "effective", "expires"):
            r[c] = _date(r[c])
    return rows


def load_plants(path=PLANT_MW):
    with open(path, newline="", encoding="utf-8") as fh:
        out = {}
        for r in csv.DictReader(fh):
            r["summer_mw"] = float(r["summer_mw"])
            r["fuel"] = r["fuel"].strip().upper()
            out[r["plant_key"].strip()] = r
        return out


def load_court(path=COURT):
    """Court actions, oldest first. A missing file means no court table (older installs)."""
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["date"] = _date(r["date"])
    return sorted(rows, key=lambda r: (r["date"], r["order"]))


def base_order(order):
    """'202-26-01A' -> '202-26-01': the series an extension or amendment belongs to."""
    m = re.match(r"^(\d{3}-\d{2}-\d+)", order.strip())
    return m.group(1) if m else order.strip()


def chain_id(r):
    """Plant orders chain by plant; other orders by their series (an order and its A, B ... letters)."""
    return "plant:" + r["plant_key"] if r["kind"] == "plant" else "series:" + base_order(r["order"])


def successor(rows, r):
    """The next order in r's chain that starts after r does, if the table has one."""
    later = [x for x in rows if x is not r and chain_id(x) == chain_id(r)
             and x["effective"] is not None and x["effective"] > r["effective"]]
    return min(later, key=lambda x: (x["effective"], x["order"])) if later else None


def in_force(rows, day, kind=None):
    """Orders in force on day (start <= day <= expiry). Rows with no expiry are never counted."""
    sel = [r for r in rows if r["expires"] is not None and r["effective"] is not None
           and r["effective"] <= day <= r["expires"] and (kind is None or r["kind"] == kind)]
    return sorted(sel, key=lambda r: (r["kind"], r["expires"], r["order"]))


def expiring(rows, day, within):
    """Orders in force on day that expire within `within` days and have no successor in the table.
    Each item: (row, days from day to the expiry date)."""
    out = []
    for r in in_force(rows, day):
        left = (r["expires"] - day).days
        if left <= within and successor(rows, r) is None:
            out.append((r, left))
    return sorted(out, key=lambda x: (x[1], x[0]["order"]))


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def find_plants(plants, query):
    """Plant keys matching a key, an EIA plant id or part of a plant name."""
    q = _norm(query)
    if not q:
        return []
    hits = []
    for key, p in sorted(plants.items()):
        if q == _norm(key) or q == _norm(p["plant_id_eia"]) or q in _norm(p["plant"]):
            hits.append(key)
    return hits


def chain(rows, key):
    """A plant's orders in order of start, with gaps between one order's expiry and the next start."""
    seq = sorted((r for r in rows if r["kind"] == "plant" and r["plant_key"] == key),
                 key=lambda r: (r["effective"], r["order"]))
    gaps = []
    for a, b in zip(seq, seq[1:]):
        g = (b["effective"] - a["expires"]).days - 1
        if g > 0:
            gaps.append({"after": a["order"], "before": b["order"], "days": g,
                         "from": (a["expires"] + dt.timedelta(days=1)).isoformat(),
                         "to": (b["effective"] - dt.timedelta(days=1)).isoformat()})
    return {"plant_key": key, "orders": seq, "gaps": gaps,
            "first_start": seq[0]["effective"] if seq else None,
            "current": seq[-1] if seq else None}


def renewals(rows):
    """Every plant renewal: how many days before the previous order's expiry the next was issued
    (negative: issued after it lapsed) and the uncovered days between them."""
    out = []
    for key in sorted({r["plant_key"] for r in rows if r["kind"] == "plant"}):
        seq = chain(rows, key)["orders"]
        for a, b in zip(seq, seq[1:]):
            out.append({"plant_key": key, "previous": a["order"], "next": b["order"],
                        "lead_days": (a["expires"] - b["issued"]).days,
                        "gap_days": max(0, (b["effective"] - a["expires"]).days - 1)})
    return out


def renewal_note(rows):
    rs = renewals(rows)
    ok = [r["lead_days"] for r in rs if r["gap_days"] == 0]
    lapsed = [r for r in rs if r["gap_days"] > 0]
    text = ("Plant renewals in the table: %d. %d followed with no uncovered day, issued %d to %d "
            "days before the previous order's expiry date." % (len(rs), len(ok), min(ok), max(ok))
            if ok else "Plant renewals in the table: %d." % len(rs))
    for r in lapsed:
        text += " %s (%s) lapsed for %d days before %s." % (r["previous"], r["plant_key"],
                                                            r["gap_days"], r["next"])
    return text + " Description of past orders only, not a forecast."


def court_for(court, orders=None, plant_key=None):
    """Court actions on any of `orders` (order numbers) or on any order of `plant_key`."""
    want = {_norm(o) for o in (orders or [])}
    return [c for c in court if _norm(c["order"]) in want
            or (plant_key is not None and c["plant_key"] == plant_key)]


def mw_in_force(rows, plants, day):
    on = sorted({r["plant_key"] for r in in_force(rows, day, "plant")})
    return {"plants": on,
            "summer_mw": round(sum(plants[k]["summer_mw"] for k in on if k in plants), 1),
            "coal_summer_mw": round(sum(plants[k]["summer_mw"] for k in on
                                        if k in plants and plants[k]["fuel"] in COAL_FUELS), 1),
            "missing_mw": [k for k in on if k not in plants]}


def summary(rows, plants, day, court=()):
    by_kind = Counter(r["kind"] for r in rows)
    return {"orders": len(rows),
            "by_year": {str(y): n for y, n in sorted(Counter(r["issued"].year for r in rows).items())},
            "by_kind": {k: by_kind.get(k, 0) for k in KINDS},
            "plants": sorted({r["plant_key"] for r in rows if r["kind"] == "plant"}),
            "in_force": len(in_force(rows, day)),
            "mw": mw_in_force(rows, plants, day),
            "court_actions": len(court),
            "orders_vacated": sorted({c["order"] for c in court if c["action"] == "vacated"})}


def row_out(r):
    return {c: (r[c].isoformat() if isinstance(r.get(c), dt.date) else (r.get(c) or ""))
            for c in SHOW}


def court_out(c):
    return {k: (c[k].isoformat() if isinstance(c.get(k), dt.date) else (c.get(k) or ""))
            for k in COURT_SHOW}


def header(day):
    lines = ["doe-202c-orders lookup %s. Table as of %s, transcribed from DOE's 202(c) pages "
             "(%s); orders issued after that date are not in it. Made with AI agents working in "
             "MV2's name; not legal advice." % (__version__, TABLE_AS_OF, DOE_PAGES[0])]
    if day is not None and day > dt.date.fromisoformat(TABLE_AS_OF):
        lines.append("WARNING: %s is after the table's as-of date (%s). An order shown as expired "
                     "may have been renewed, and new orders may exist: check DOE's page."
                     % (day.isoformat(), TABLE_AS_OF))
    return lines


def line(r, day=None):
    s = "%s  %-6s %-12s %s" % (r["order"], r["kind"], r["area"], r["plant"] or r["recipient"])
    s += "  in force %s to %s" % (r["effective"], r["expires"] or "(no expiry on DOE's page)")
    if r.get("expires_time"):
        s += " %s" % r["expires_time"]
    if day is not None and r["expires"] is not None and r["effective"] <= day <= r["expires"]:
        s += "  (%d days until expiry date)" % (r["expires"] - day).days
    if r.get("note"):
        s += "  [%s]" % r["note"]
    return s


def court_line(c):
    return "%s  %s %s: %s, %s. Source: %s" % (c["order"], c["date"], c["date_kind"], c["action"],
                                              c["case"], c["source"])


def court_text(sel):
    if not sel:
        return ["  Court actions in the court table: none. " + COURT_LIMIT]
    return (["  Court actions in the court table:"] + ["    " + court_line(c) for c in sel]
            + ["    " + COURT_LIMIT])


def main(argv=None, rows=None, plants=None, court=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("in-force", "expiring", "plant", "order", "court", "summary"):
        p = sub.add_parser(name)
        if name in ("plant", "order"):
            p.add_argument("query")
        if name not in ("order", "court"):
            p.add_argument("--date", default=dt.date.today().isoformat())
        if name == "in-force":
            p.add_argument("--kind", choices=KINDS)
        if name == "expiring":
            p.add_argument("--days", type=int, default=30)
        p.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        day = dt.date.fromisoformat(args.date) if getattr(args, "date", None) else None
    except ValueError:
        print("bad --date %r (want YYYY-MM-DD)" % args.date, file=sys.stderr)
        return 2
    rows = load_orders() if rows is None else rows
    plants = load_plants() if plants is None else plants
    court = load_court() if court is None else court
    res, text = {"version": __version__, "table_as_of": TABLE_AS_OF, "court_as_of": COURT_AS_OF,
                 "date": day.isoformat() if day else None}, header(day)
    found = True

    if args.cmd == "in-force":
        sel = in_force(rows, day, args.kind)
        res["orders"] = [row_out(r) for r in sel]
        res["mw"] = mw_in_force(rows, plants, day)
        text.append("In force on %s: %d order(s)%s." % (day, len(sel),
                                                        " of kind %s" % args.kind if args.kind else ""))
        text += ["  " + line(r, day) for r in sel]
        m = res["mw"]
        text.append("Plant orders cover %d plant(s), %.1f summer MW (%.1f coal)."
                    % (len(m["plants"]), m["summer_mw"], m["coal_summer_mw"]))
        found = bool(sel)
    elif args.cmd == "expiring":
        sel = expiring(rows, day, args.days)
        res["orders"] = [dict(row_out(r), days_until_expiry=left) for r, left in sel]
        res["renewal_note"] = renewal_note(rows)
        text.append("In force on %s, expiring within %d days, no later order in the table: %d."
                    % (day, args.days, len(sel)))
        text += ["  " + line(r, day) for r, _ in sel]
        text.append(res["renewal_note"])
        found = bool(sel)
    elif args.cmd == "plant":
        keys = find_plants(plants, args.query)
        res["plants"] = []
        if not keys:
            text.append("No plant under a 202(c) plant order matches %r. Plants in the table: %s."
                        % (args.query, ", ".join(sorted(plants))))
            found = False
        for k in keys:
            c, p = chain(rows, k), plants[k]
            cur = c["current"]
            live = cur is not None and cur["effective"] <= day <= cur["expires"]
            acts = court_for(court, plant_key=k)
            res["plants"].append({
                "plant_key": k, "plant": p["plant"], "state": p["state"],
                "plant_id_eia": p["plant_id_eia"], "generators": p["generators"].split("|"),
                "fuel": p["fuel"], "summer_mw": p["summer_mw"],
                "orders": [row_out(r) for r in c["orders"]], "gaps": c["gaps"],
                "current_order": cur["order"] if cur else None,
                "current_expiry": cur["expires"].isoformat() if cur else None,
                "in_force_on_date": live,
                "days_until_expiry": (cur["expires"] - day).days if live else None,
                "court": [court_out(a) for a in acts]})
            text.append("%s (%s, EIA plant %s, generators %s, %s, %.1f summer MW): %d orders since %s."
                        % (p["plant"], p["state"], p["plant_id_eia"], p["generators"].replace("|", ", "),
                           p["fuel"], p["summer_mw"], len(c["orders"]), c["first_start"]))
            text += ["  " + line(r, day) for r in c["orders"]]
            text.append("  Gaps between orders: %s." % ("; ".join(
                "%s to %s (%d days, between %s and %s)" % (g["from"], g["to"], g["days"], g["after"],
                                                           g["before"]) for g in c["gaps"]) or "none"))
            text.append("  On %s: %s." % (day, "under order %s, %d days until its expiry date %s"
                                          % (cur["order"], (cur["expires"] - day).days, cur["expires"])
                                          if live else "no order of this plant in force in the table"))
            text += court_text(acts)
    elif args.cmd == "order":
        q = _norm(args.query)
        sel = [r for r in rows if _norm(r["order"]) == q]
        res["orders"] = [row_out(r) for r in sel]
        if sel:
            nxt = successor(rows, sel[0])
            acts = court_for(court, orders=[sel[0]["order"]])
            res["next_in_chain"] = nxt["order"] if nxt else None
            res["court"] = [court_out(a) for a in acts]
            text += ["  " + line(r) for r in sel]
            text.append("  Next order in the same chain: %s." % (nxt["order"] if nxt else
                                                                 "none in the table"))
            text.append("  Source: %s" % sel[0]["source"])
            text += court_text(acts)
        else:
            text.append("No order %r in the table (as of %s)." % (args.query, TABLE_AS_OF))
            found = False
    elif args.cmd == "court":
        res["court"] = [court_out(c) for c in court]
        res["court_limit"] = COURT_LIMIT
        text.append("Court actions on 202(c) orders in the court table: %d." % len(court))
        text += ["  " + court_line(c) for c in court]
        text.append(COURT_LIMIT)
        found = bool(court)
    else:
        s = summary(rows, plants, day, court)
        res.update(s)
        res["renewal_note"] = renewal_note(rows)
        text.append("%d orders, extensions and amendments (by year issued: %s; by kind: %s)."
                    % (s["orders"], ", ".join("%s %d" % kv for kv in s["by_year"].items()),
                       ", ".join("%s %d" % kv for kv in s["by_kind"].items())))
        text.append("Plants with plant orders: %s." % ", ".join(s["plants"]))
        text.append("In force on %s: %d order(s); plant orders cover %.1f summer MW (%.1f coal)."
                    % (day, s["in_force"], s["mw"]["summer_mw"], s["mw"]["coal_summer_mw"]))
        text.append(res["renewal_note"])
        text.append("Court actions in the court table: %d; orders vacated by a court: %s."
                    % (s["court_actions"], ", ".join(s["orders_vacated"]) or "none"))

    if args.json:
        print(json.dumps(res, indent=1))
    else:
        print("\n".join(text))
    return 0 if found else 1


if __name__ == "__main__":
    raise SystemExit(main())
