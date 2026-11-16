"""orders_lookup: offline lookup of every DOE Federal Power Act 202(c) emergency order, 2025-2026.

Copyright 2026 MV2, Munim, Inc. Apache-2.0. Made with AI agents working in MV2's name.

Reads doe_202c_orders.csv (one row per order, extension or amendment, transcribed from DOE's
2025 and 2026 202(c) order pages, plus one amended order that only ERCOT's page lists),
doe_202c_plant_mw.csv (summer MW of the units each plant order covers) and doe_202c_court.csv
(court actions on plant orders: one row per petition for review, with its docket number and
status where found, plus briefs, the ruling, the rehearing petition and an amicus brief), all
next to this file. Standard library only; no network.

    python orders_lookup.py in-force [--date 2026-11-16] [--kind plant|event|island] [--json]
    python orders_lookup.py expiring [--date 2026-11-16] [--days 30] [--json]
    python orders_lookup.py plant <plant key, name or EIA plant id> [--date ...] [--json]
    python orders_lookup.py order <order number, e.g. 202-26-51> [--json]
    python orders_lookup.py court [--json]
    python orders_lookup.py summary [--date ...] [--json]

Days are calendar dates; an order is in force from its start date through its expiry date,
both counted. Times of day are shown but not used. A court action changes nothing in the
in-force dates: they are the dates in DOE's orders. In the court table, date_kind says what a
date is: 'decided' (a ruling), 'filed' (a filing), 'first seen' (the docket has no filing date;
this is its earliest entry seen, so it was filed on or before) or 'reported' (only a report's
date is known). A petition row with an empty order names no order in the sources; its
plant_key is inferred (and may be 'schahfer|culley' where the record does not say which).
status is the latest docket status seen when the dockets were read (DOCKETS_READ).
For a plant, the order in force on the date is the current one; a renewal that DOE has issued
but that starts later is shown as the next order, never as the current one.
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

__version__ = "0.3.1"

# The last date DOE's pages were read for this table. Orders issued later are not in it.
TABLE_AS_OF = "2026-11-16"
# The last date court actions were looked for. Only actions found by then are in the court table.
COURT_AS_OF = "2026-11-16"
# The date the dockets were read in CourtListener's RECAP archive (petition statuses).
DOCKETS_READ = "2026-10-19"
DOE_PAGES = ("https://www.energy.gov/ceser/2026-doe-202c-orders",
             "https://www.energy.gov/ceser/2025-doe-202c-orders")

HERE = os.path.dirname(os.path.abspath(__file__))
ORDERS = os.path.join(HERE, "doe_202c_orders.csv")
PLANT_MW = os.path.join(HERE, "doe_202c_plant_mw.csv")
COURT = os.path.join(HERE, "doe_202c_court.csv")
KINDS = ("plant", "event", "island")
COAL_FUELS = frozenset({"BIT", "SUB", "LIG", "ANT", "RC", "WC", "SGC"})
PETITION = "petition for review"
STATUSES = ("decided", "abeyance", "briefing", "no order seen", "not in archive")
DOCKET_RE = re.compile(r"\b\d{2}-\d{4}\b")
SHOW = ("order", "kind", "area", "recipient", "plant_key", "plant", "issued", "effective",
        "expires", "expires_time", "note", "source")
COURT_SHOW = ("order", "plant_key", "date", "date_kind", "court", "case", "action", "status",
              "status_date", "source", "note")
COURT_LIMIT = ("Court actions found as of %s. Petitions and their status come from the D.C. and "
               "Ninth Circuit dockets in CourtListener's RECAP archive, read on %s (it holds only "
               "what PACER users uploaded, so petitions and orders can be missing, and a status can "
               "have changed since), joined with litigation trackers, press releases and the "
               "court's opinion; each row names its source. A court action on one order says "
               "nothing about any other order, and the in-force dates here are the dates in DOE's "
               "orders." % (COURT_AS_OF, DOCKETS_READ))


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
        r["status_date"] = _date(r.get("status_date"))
        r["status"] = (r.get("status") or "").strip()
        r["order"] = (r.get("order") or "").strip()
    return sorted(rows, key=lambda r: (r["date"], r["order"]))


def plant_keys(c):
    """The plant keys of a court row: 'schahfer|culley' -> ['schahfer', 'culley']."""
    return [k for k in (c.get("plant_key") or "").split("|") if k]


def dockets(c):
    """Docket numbers named in a court row's case column."""
    return DOCKET_RE.findall(c.get("case") or "")


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
    """A plant's orders in order of start, with gaps between one order's expiry and the next start.
    'current' is the latest order in the table; use plant_status() for the order in force on a day."""
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


def plant_status(orders, day):
    """For a plant's orders (from chain()) on `day`: the order in force ('current', None if none),
    the next order in the table that starts after `day` ('next'), and the last day the orders cover
    without an uncovered day, counting from `day` ('covered_through', None if none is in force)."""
    seq = sorted(orders, key=lambda r: (r["effective"], r["order"]))
    now = [r for r in seq if r["effective"] <= day <= r["expires"]]
    cur = now[-1] if now else None
    later = [r for r in seq if r["effective"] > day]
    nxt = later[0] if later else None
    through = None
    if cur is not None:
        through = max(r["expires"] for r in now)
        for r in later:
            if r["effective"] <= through + dt.timedelta(days=1):
                through = max(through, r["expires"])
    return {"current": cur, "next": nxt, "covered_through": through}


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
    """Court actions on any of `orders` (order numbers) or on any order of `plant_key`
    (including petitions whose order is not confirmed but whose plant is inferred)."""
    want = {_norm(o) for o in (orders or []) if _norm(o)}
    return [c for c in court if (c["order"] and _norm(c["order"]) in want)
            or (plant_key is not None and plant_key in plant_keys(c))]


def court_overview(court, rows):
    """Petitions for review in the court table: how many, docket numbers, which plant orders they
    name, which plants, their status counts, and how many rulings the table has."""
    kinds = {r["order"]: r["kind"] for r in rows}
    pets = [c for c in court if c["action"] == PETITION]
    named = sorted({c["order"] for c in pets if c["order"]})
    status = Counter(c["status"] for c in pets)
    return {"petitions": len(pets),
            "dockets": len({d for c in pets for d in dockets(c)}),
            "orders_petitioned": named,
            "plant_orders_petitioned": sum(1 for o in named if kinds.get(o) == "plant"),
            "plant_orders": sum(1 for r in rows if r["kind"] == "plant"),
            "petitions_order_not_confirmed": sum(1 for c in pets if not c["order"]),
            "plants_petitioned": sorted({k for c in pets for k in plant_keys(c)}),
            "status": {s: status[s] for s in STATUSES if status[s]},
            "rulings": sum(1 for c in court if c["date_kind"] == "decided")}


def overview_text(ov):
    return ("Petitions for review found: %d (%d docket numbers), naming %d of %d plant orders; "
            "%d name no order in the sources (plant inferred). Plants: %s. Petition status: %s. "
            "Court rulings found: %d."
            % (ov["petitions"], ov["dockets"], ov["plant_orders_petitioned"], ov["plant_orders"],
               ov["petitions_order_not_confirmed"], ", ".join(ov["plants_petitioned"]) or "none",
               ", ".join("%s %d" % kv for kv in ov["status"].items()) or "none", ov["rulings"]))


def mw_in_force(rows, plants, day):
    on = sorted({r["plant_key"] for r in in_force(rows, day, "plant")})
    return {"plants": on,
            "summer_mw": round(sum(plants[k]["summer_mw"] for k in on if k in plants), 1),
            "coal_summer_mw": round(sum(plants[k]["summer_mw"] for k in on
                                        if k in plants and plants[k]["fuel"] in COAL_FUELS), 1),
            "missing_mw": [k for k in on if k not in plants]}


def summary(rows, plants, day, court=()):
    by_kind = Counter(r["kind"] for r in rows)
    ov = court_overview(court, rows)
    return {"orders": len(rows),
            "by_year": {str(y): n for y, n in sorted(Counter(r["issued"].year for r in rows).items())},
            "by_kind": {k: by_kind.get(k, 0) for k in KINDS},
            "plants": sorted({r["plant_key"] for r in rows if r["kind"] == "plant"}),
            "in_force": len(in_force(rows, day)),
            "mw": mw_in_force(rows, plants, day),
            "court_actions": len(court),
            "orders_vacated": sorted({c["order"] for c in court if c["action"] == "vacated"}),
            "petitions": ov["petitions"],
            "dockets": ov["dockets"],
            "petition_status": ov["status"],
            "orders_petitioned": ov["orders_petitioned"],
            "plant_orders_petitioned": ov["plant_orders_petitioned"],
            "plants_petitioned": ov["plants_petitioned"]}


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
    label = c["order"] or "(order not confirmed, %s)" % " or ".join(plant_keys(c))
    s = "%s  %s %s: %s, %s" % (label, c["date"], c["date_kind"], c["action"], c["case"])
    if c.get("status"):
        s += "; status: %s" % c["status"]
        if c.get("status_date"):
            s += " %s" % c["status_date"]
    return s + ". Source: %s" % c["source"]


def court_text(sel):
    if not sel:
        return ["  Court actions in the court table: none. " + COURT_LIMIT]
    return (["  Court actions in the court table:"] + ["    " + court_line(c) for c in sel]
            + ["    " + COURT_LIMIT])


def status_text(day, st):
    cur, nxt, through = st["current"], st["next"], st["covered_through"]
    if cur is not None:
        s = ("On %s: under order %s, %d days until its expiry date %s"
             % (day, cur["order"], (cur["expires"] - day).days, cur["expires"]))
        if nxt is not None:
            s += ("; next order %s (issued %s) in force %s to %s"
                  % (nxt["order"], nxt["issued"], nxt["effective"], nxt["expires"]))
        if through != cur["expires"]:
            s += "; covered without a break through %s" % through
        elif nxt is not None:
            s += "; %d uncovered day(s) before it starts" % ((nxt["effective"] - cur["expires"]).days - 1)
        return s + "."
    s = "On %s: no order of this plant in force in the table" % day
    if nxt is not None:
        s += "; next order %s (issued %s) starts %s" % (nxt["order"], nxt["issued"], nxt["effective"])
    return s + "."


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
                 "dockets_read": DOCKETS_READ,
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
            st = plant_status(c["orders"], day)
            live = st["current"] is not None
            # The order in force on the date; if none, the latest order in the table (as before).
            cur = st["current"] if live else c["current"]
            nxt = st["next"]
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
                "next_order": nxt["order"] if nxt else None,
                "next_effective": nxt["effective"].isoformat() if nxt else None,
                "covered_through": st["covered_through"].isoformat() if st["covered_through"] else None,
                "court": [court_out(a) for a in acts]})
            text.append("%s (%s, EIA plant %s, generators %s, %s, %.1f summer MW): %d orders since %s."
                        % (p["plant"], p["state"], p["plant_id_eia"], p["generators"].replace("|", ", "),
                           p["fuel"], p["summer_mw"], len(c["orders"]), c["first_start"]))
            text += ["  " + line(r, day) for r in c["orders"]]
            text.append("  Gaps between orders: %s." % ("; ".join(
                "%s to %s (%d days, between %s and %s)" % (g["from"], g["to"], g["days"], g["after"],
                                                           g["before"]) for g in c["gaps"]) or "none"))
            text.append("  " + status_text(day, st))
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
        ov = court_overview(court, rows)
        res["court"] = [court_out(c) for c in court]
        res["overview"] = ov
        res["court_limit"] = COURT_LIMIT
        text.append("Court actions on 202(c) orders in the court table: %d." % len(court))
        text += ["  " + court_line(c) for c in court]
        text.append(overview_text(ov))
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
        text.append(overview_text(court_overview(court, rows)))

    if args.json:
        print(json.dumps(res, indent=1))
    else:
        print("\n".join(text))
    return 0 if found else 1


if __name__ == "__main__":
    raise SystemExit(main())
