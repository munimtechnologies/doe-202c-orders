# Tests for skills/doe-202c-orders (orders_lookup.py 0.3.1, doe_202c_orders.csv,
# doe_202c_plant_mw.csv, doe_202c_court.csv, SKILL.md). Expected values were counted by hand
# from the tables.
# Copyright 2026 MV2, Munim, Inc. Apache-2.0. Made with AI agents working in MV2's name.
import datetime as dt
import io
import json
import os
import sys
import unittest
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "skills", "doe-202c-orders")
sys.path.insert(0, SKILL)
import orders_lookup as ol  # noqa: E402

D = dt.date
PLANT_ORDERS_NOV = {"campbell": "202-26-39", "wagner": "202-26-25A", "eddystone": "202-26-40",
                    "stanton": "202-26-42", "centralia": "202-26-44", "schahfer": "202-26-46",
                    "culley": "202-26-47", "craig": "202-26-49"}
CAMPBELL = ["202-25-3", "202-25-7", "202-25-9", "202-26-16", "202-26-22", "202-26-39", "202-26-51"]
PETITIONED = ["202-25-11", "202-25-12", "202-25-13", "202-25-14", "202-25-3", "202-25-4",
              "202-25-7", "202-25-8", "202-25-9", "202-26-16", "202-26-18", "202-26-19",
              "202-26-20", "202-26-22"]
PLANTS_PETITIONED = ["campbell", "centralia", "craig", "culley", "eddystone", "schahfer", "stanton"]
STATUS = {"decided": 3, "abeyance": 21, "briefing": 3, "no order seen": 8, "not in archive": 2}
OVERVIEW = ("Petitions for review found: 37 (35 docket numbers), naming 14 of 35 plant orders; "
            "10 name no order in the sources (plant inferred). Plants: campbell, centralia, craig, "
            "culley, eddystone, schahfer, stanton. Petition status: decided 3, abeyance 21, "
            "briefing 3, no order seen 8, not in archive 2. Court rulings found: 1.")
NAMED_DOCKETS = {
    ("202-25-3", "25-1159"), ("202-25-3", "25-1160"), ("202-25-3", "25-1162"),
    ("202-25-4", "25-1193"), ("202-25-4", "25-1194"),
    ("202-25-7", "25-1198"), ("202-25-7", "25-1202"), ("202-25-7", "25-1254"),
    ("202-25-8", "25-1287"), ("202-25-8", "25-1288"),
    ("202-25-9", "26-1024"), ("202-25-9", "26-1028"),
    ("202-25-11", "26-1252"), ("202-25-11", "26-1261"),
    ("202-25-12", "26-1056"), ("202-25-13", "26-1057"),
    ("202-25-14", "26-1059"), ("202-25-14", "26-1060"),
    ("202-25-12", "26-1075"), ("202-25-13", "26-1076"),
    ("202-25-12", "26-1077"), ("202-25-13", "26-1078"),
    ("202-26-19", "26-1186"), ("202-26-19", "26-1187"),
    ("202-26-20", "26-1186"), ("202-26-20", "26-1187"),
    ("202-26-22", "26-1233")}
UNNAMED_DOCKETS = {"26-1026", "26-1101", "26-3781", "26-1158", "26-1167", "26-1159", "26-1224",
                   "26-1256", "26-1255", "26-1273"}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = ol.main(list(argv))
    return code, out.getvalue()


class TestTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = ol.load_orders()
        cls.plants = ol.load_plants()
        cls.court = ol.load_court()

    def test_orders_table(self):
        self.assertEqual(len(self.rows), 88)
        self.assertEqual(len({r["order"] for r in self.rows}), 88)
        self.assertEqual(Counter(r["kind"] for r in self.rows),
                         Counter({"event": 38, "plant": 35, "island": 15}))
        self.assertEqual(Counter(r["issued"].year for r in self.rows), Counter({2025: 19, 2026: 69}))
        for r in self.rows:
            self.assertTrue(r["source"].startswith("https://"), r["order"])
            self.assertLessEqual(r["issued"], r["effective"], r["order"])
            if r["expires"] is not None:
                self.assertLessEqual(r["effective"], r["expires"], r["order"])
            self.assertEqual(r["kind"] == "plant", bool(r["plant_key"]), r["order"])
        self.assertEqual([r["order"] for r in self.rows if r["expires"] is None],
                         ["202-25-1", "202-25-2"])

    def test_campbell_renewal_row(self):
        (r,) = [x for x in self.rows if x["order"] == "202-26-51"]
        self.assertEqual((r["kind"], r["area"], r["plant_key"], r["issued"], r["effective"],
                          r["expires"]),
                         ("plant", "MISO", "campbell", D(2026, 11, 13), D(2026, 11, 15),
                          D(2027, 2, 12)))
        self.assertEqual((r["expires"] - r["effective"]).days + 1, 90)
        self.assertIn("only during the hours necessary to meet the emergency", r["note"])
        (craig,) = [x for x in self.rows if x["order"] == "202-26-49"]
        self.assertIn("only during hours necessary to meet the emergency", craig["note"])
        self.assertEqual(sorted(x["order"] for x in self.rows if "hours necessary" in x["note"]),
                         ["202-26-49", "202-26-51"])

    def test_as_of(self):
        newest = max(r["issued"] for r in self.rows)
        self.assertEqual(newest, D(2026, 11, 13))
        self.assertLessEqual(newest, D.fromisoformat(ol.TABLE_AS_OF))
        self.assertEqual(ol.TABLE_AS_OF, "2026-11-16")
        self.assertEqual(ol.COURT_AS_OF, "2026-11-16")
        self.assertEqual(ol.DOCKETS_READ, "2026-10-19")
        self.assertEqual(ol.__version__, "0.3.1")

    def test_plants_table(self):
        self.assertEqual(sorted(self.plants), sorted(PLANT_ORDERS_NOV))
        self.assertEqual({r["plant_key"] for r in self.rows if r["kind"] == "plant"},
                         set(self.plants))
        self.assertEqual(self.plants["campbell"]["plant_id_eia"], "1710")
        self.assertEqual(self.plants["stanton"]["summer_mw"], 453.4)

    def test_court_table(self):
        self.assertEqual(len(self.court), 41)
        by_order = {r["order"]: r for r in self.rows}
        for c in self.court:
            self.assertTrue(c["source"].startswith("https://"), c)
            self.assertIn(c["date_kind"], ("decided", "filed", "first seen", "reported"))
            self.assertIsNotNone(c["date"], c)
            self.assertLessEqual(c["date"], D.fromisoformat(ol.COURT_AS_OF))
            self.assertTrue(c["note"], c)
            self.assertTrue(c["case"], c)
            for k in ol.plant_keys(c):
                self.assertIn(k, self.plants, c)
            if c["order"]:
                self.assertIn(c["order"], by_order)  # every named order is in the table
                self.assertEqual(c["plant_key"], by_order[c["order"]]["plant_key"])
                # Nothing in court before the order it is about was issued.
                self.assertGreaterEqual(c["date"], by_order[c["order"]]["issued"], c)
            else:
                # Only petitions may lack an order, and the note says the order was not seen.
                self.assertEqual(c["action"], ol.PETITION, c)
                self.assertTrue("not seen" in c["note"] or "not confirmed" in c["note"], c)
            if c["action"] == ol.PETITION:
                self.assertIn(c["status"], ol.STATUSES, c)
                # Decided, abeyance and briefing rows carry the date of that order; the others none.
                self.assertEqual(c["status_date"] is not None,
                                 c["status"] in ("decided", "abeyance", "briefing"), c)
            else:
                self.assertEqual((c["status"], c["status_date"]), ("", None), c)
        self.assertEqual(Counter(c["date_kind"] for c in self.court),
                         Counter({"filed": 35, "first seen": 5, "decided": 1}))
        self.assertEqual(Counter(c["action"] for c in self.court),
                         Counter({"petition for review": 37, "opening brief of petitioners": 1,
                                  "vacated": 1, "rehearing petition by DOE": 1,
                                  "amicus brief supporting rehearing": 1}))
        self.assertEqual(Counter(c["plant_key"] for c in self.court),
                         Counter({"campbell": 13, "eddystone": 7, "centralia": 4, "schahfer": 4,
                                  "culley": 4, "schahfer|culley": 2, "craig": 6, "stanton": 1}))
        pets = [c for c in self.court if c["action"] == ol.PETITION]
        self.assertEqual(Counter(c["status"] for c in pets), Counter(STATUS))
        # The five abeyance groups of the docket census.
        self.assertEqual(Counter(c["status_date"] for c in pets if c["status"] == "abeyance"),
                         Counter({D(2026, 2, 18): 3, D(2026, 3, 13): 1, D(2026, 6, 8): 3,
                                  D(2026, 7, 28): 10, D(2026, 8, 26): 4}))
        # Oldest first.
        self.assertEqual([c["date"] for c in self.court], sorted(c["date"] for c in self.court))
        self.assertEqual((self.court[0]["order"], self.court[0]["date"], self.court[0]["case"][:11]),
                         ("202-25-3", D(2025, 7, 24), "No. 25-1159"))
        (vac,) = [c for c in self.court if c["action"] == "vacated"]
        self.assertEqual((vac["order"], vac["date"], vac["date_kind"], vac["case"][:11]),
                         ("202-25-3", D(2026, 9, 11), "decided", "No. 25-1159"))
        # The vacated order had already expired when the court ruled: 386 days earlier, and
        # 414 days after the first petition (24 July 2025).
        self.assertEqual((vac["date"] - by_order["202-25-3"]["expires"]).days, 386)
        first = min(c["date"] for c in pets if c["order"] == "202-25-3")
        self.assertEqual(first, D(2025, 7, 24))
        self.assertEqual((vac["date"] - first).days, 414)
        self.assertEqual(sorted(c["status"] for c in pets if c["order"] == "202-25-3"),
                         ["decided"] * 3)
        (reh,) = [c for c in self.court if c["action"] == "rehearing petition by DOE"]
        self.assertEqual((reh["date"], reh["date_kind"]), (D(2026, 10, 26), "filed"))
        # Filed on the 45th day after the decision (FRAP 40, a U.S. agency is a party).
        self.assertEqual((reh["date"] - vac["date"]).days, 45)
        self.assertIn("climate.law.columbia.edu", reh["source"])
        self.assertIn("publicpower.org", reh["note"])  # the earlier report is still cited
        self.assertIn("as of 2026-11-16", reh["note"])
        (ami,) = [c for c in self.court if c["action"] == "amicus brief supporting rehearing"]
        self.assertEqual((ami["order"], ami["date"]), ("202-25-3", D(2026, 11, 3)))
        self.assertIn("West Virginia and 12 other states", ami["note"])
        self.assertEqual(self.court[-1]["date"], D(2026, 11, 3))
        # Docket numbers, per named order and for petitions with no named order.
        self.assertEqual({(c["order"], d) for c in pets if c["order"] for d in ol.dockets(c)},
                         NAMED_DOCKETS)
        self.assertEqual({d for c in pets if not c["order"] for d in ol.dockets(c)},
                         UNNAMED_DOCKETS)
        self.assertEqual(len({d for c in pets for d in ol.dockets(c)}), 35)
        # Correction in 0.3.1: Schahfer's first order is in 26-1056, Culley's in 26-1057.
        (s,) = [c for c in pets if c["case"].startswith("No. 26-1056")]
        (k,) = [c for c in pets if c["case"].startswith("No. 26-1057")]
        self.assertEqual((s["order"], k["order"]), ("202-25-12", "202-25-13"))
        # Two tracker petitions have no docket in the archive.
        self.assertEqual(sorted(c["order"] for c in pets if c["case"] == "case number not found"),
                         ["202-26-16", "202-26-18"])
        ninth = sorted(c["order"] for c in self.court if "Ninth Circuit" in c["court"])
        self.assertEqual(ninth, ["", "202-25-11", "202-25-11", "202-26-18"])


class TestLookups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = ol.load_orders()
        cls.plants = ol.load_plants()
        cls.court = ol.load_court()

    def test_base_order(self):
        self.assertEqual(ol.base_order("202-26-01A"), "202-26-01")
        self.assertEqual(ol.base_order("202-25-1F"), "202-25-1")
        self.assertEqual(ol.base_order("202-26-39"), "202-26-39")

    def test_helpers(self):
        self.assertEqual(ol.plant_keys({"plant_key": "schahfer|culley"}), ["schahfer", "culley"])
        self.assertEqual(ol.plant_keys({"plant_key": ""}), [])
        self.assertEqual(ol.dockets({"case": "No. 26-1186 or No. 26-1187 (State of Minnesota v. "
                                             "Chris Wright)"}), ["26-1186", "26-1187"])
        self.assertEqual(ol.dockets({"case": "case number not found"}), [])

    def test_in_force_november(self):
        for day in (D(2026, 11, 8), D(2026, 11, 9), D(2026, 11, 13), D(2026, 11, 14)):
            sel = ol.in_force(self.rows, day)
            self.assertEqual(len(sel), 10, day)
            self.assertEqual({r["plant_key"]: r["order"] for r in sel if r["kind"] == "plant"},
                             PLANT_ORDERS_NOV)
            self.assertEqual(sorted(r["order"] for r in sel if r["kind"] == "island"),
                             ["202-25-1F", "202-25-2F"])
            self.assertEqual([r for r in sel if r["kind"] == "event"], [])
        for day in (D(2026, 11, 15), D(2026, 11, 16)):
            sel = ol.in_force(self.rows, day)
            self.assertEqual({r["plant_key"]: r["order"] for r in sel if r["kind"] == "plant"},
                             dict(PLANT_ORDERS_NOV, campbell="202-26-51"))
        m = ol.mw_in_force(self.rows, self.plants, D(2026, 11, 9))
        self.assertEqual((len(m["plants"]), m["summer_mw"], m["coal_summer_mw"], m["missing_mw"]),
                         (8, 4849.9, 3692.9, []))
        self.assertEqual(ol.mw_in_force(self.rows, self.plants, D(2026, 11, 15))["summer_mw"],
                         4849.9)

    def test_in_force_january_events(self):
        sel = ol.in_force(self.rows, D(2026, 1, 26), "event")
        self.assertEqual(sorted(r["order"] for r in sel),
                         ["202-26-01", "202-26-01A", "202-26-02", "202-26-03", "202-26-04",
                          "202-26-06", "202-26-07", "202-26-08"])

    def test_expiring(self):
        got = [(r["order"], left) for r, left in ol.expiring(self.rows, D(2026, 11, 9), 14)]
        self.assertEqual(got, [("202-26-25A", 8), ("202-26-40", 11)])
        self.assertEqual(len(ol.expiring(self.rows, D(2026, 11, 9), 30)), 3)
        got = [(r["order"], left) for r, left in ol.expiring(self.rows, D(2026, 11, 14), 7)]
        self.assertEqual(got, [("202-26-25A", 3), ("202-26-40", 6)])
        got = [(r["order"], left) for r, left in ol.expiring(self.rows, D(2026, 11, 16), 14)]
        self.assertEqual(got, [("202-26-25A", 1), ("202-26-40", 4), ("202-26-42", 14)])
        got = [r["order"] for r, _ in ol.expiring(self.rows, D(2026, 11, 1), 7)]
        self.assertEqual(got, ["202-26-38"])

    def test_find_plants(self):
        self.assertEqual(ol.find_plants(self.plants, "1710"), ["campbell"])
        self.assertEqual(ol.find_plants(self.plants, "J.H. Campbell"), ["campbell"])
        self.assertEqual(ol.find_plants(self.plants, "Schahfer"), ["schahfer"])
        self.assertEqual(ol.find_plants(self.plants, "Stanton Energy Center"), ["stanton"])
        self.assertEqual(ol.find_plants(self.plants, "Brandon Shores"), [])
        self.assertEqual(ol.find_plants(self.plants, ""), [])

    def test_chains(self):
        c = ol.chain(self.rows, "campbell")
        self.assertEqual([r["order"] for r in c["orders"]], CAMPBELL)
        self.assertEqual((c["gaps"], c["first_start"]), ([], D(2025, 5, 23)))
        self.assertEqual(c["current"]["order"], "202-26-51")
        w = ol.chain(self.rows, "wagner")
        self.assertEqual(w["gaps"], [{"after": "202-25-6A", "before": "202-26-25", "days": 141,
                                      "from": "2026-01-01", "to": "2026-05-21"}])

    def test_plant_status(self):
        camp = ol.chain(self.rows, "campbell")["orders"]
        for day in (D(2026, 11, 8), D(2026, 11, 13), D(2026, 11, 14)):
            st = ol.plant_status(camp, day)
            self.assertEqual((st["current"]["order"], st["next"]["order"], st["covered_through"]),
                             ("202-26-39", "202-26-51", D(2027, 2, 12)), day)
        st = ol.plant_status(camp, D(2026, 11, 15))
        self.assertEqual((st["current"]["order"], st["next"], st["covered_through"]),
                         ("202-26-51", None, D(2027, 2, 12)))
        st = ol.plant_status(camp, D(2027, 2, 13))
        self.assertEqual((st["current"], st["next"], st["covered_through"]), (None, None, None))
        self.assertEqual(ol.plant_status(camp, D(2025, 5, 23))["covered_through"], D(2027, 2, 12))
        wag = ol.chain(self.rows, "wagner")["orders"]
        st = ol.plant_status(wag, D(2026, 2, 1))
        self.assertEqual((st["current"], st["next"]["order"], st["covered_through"]),
                         (None, "202-26-25", None))
        st = ol.plant_status(wag, D(2025, 12, 1))
        self.assertEqual((st["current"]["order"], st["next"]["order"], st["covered_through"]),
                         ("202-25-6A", "202-26-25", D(2025, 12, 31)))
        st = ol.plant_status(wag, D(2026, 11, 9))
        self.assertEqual((st["current"]["order"], st["next"], st["covered_through"]),
                         ("202-26-25A", None, D(2026, 11, 17)))

    def test_renewals(self):
        rs = ol.renewals(self.rows)
        self.assertEqual(len(rs), 27)
        self.assertEqual(Counter(r["lead_days"] for r in rs),
                         Counter({0: 9, 1: 10, 2: 4, 3: 3, -141: 1}))
        self.assertEqual([r["previous"] for r in rs if r["gap_days"]], ["202-25-6A"])
        (new,) = [r for r in rs if r["next"] == "202-26-51"]
        self.assertEqual((new["previous"], new["lead_days"], new["gap_days"]), ("202-26-39", 1, 0))
        note = ol.renewal_note(self.rows)
        self.assertIn("Plant renewals in the table: 27. 26 followed with no uncovered day, "
                      "issued 0 to 3 days before", note)
        self.assertIn("202-25-6A (wagner) lapsed for 141 days before 202-26-25.", note)

    def test_successor(self):
        by = {r["order"]: r for r in self.rows}
        self.assertEqual(ol.successor(self.rows, by["202-26-22"])["order"], "202-26-39")
        self.assertEqual(ol.successor(self.rows, by["202-26-39"])["order"], "202-26-51")
        self.assertIsNone(ol.successor(self.rows, by["202-26-51"]))
        self.assertIsNone(ol.successor(self.rows, by["202-26-25A"]))
        self.assertEqual(ol.successor(self.rows, by["202-25-1E"])["order"], "202-25-1F")
        self.assertEqual(ol.successor(self.rows, by["202-26-02"])["order"], "202-26-02A")

    def test_court_for(self):
        self.assertEqual(len(ol.court_for(self.court, orders=["202-25-3"])), 6)
        self.assertEqual(len(ol.court_for(self.court, plant_key="campbell")), 13)
        self.assertEqual(ol.court_for(self.court, orders=["202-26-39"]), [])
        self.assertEqual(ol.court_for(self.court, orders=["202-26-51"]), [])
        self.assertEqual(len(ol.court_for(self.court, plant_key="eddystone")), 7)
        self.assertEqual(len(ol.court_for(self.court, orders=["202-25-14"])), 2)
        self.assertEqual(len(ol.court_for(self.court, orders=["202-26-19"])), 1)
        self.assertEqual(ol.court_for(self.court, orders=["202-26-49"]), [])
        self.assertEqual(ol.court_for(self.court, plant_key="wagner"), [])
        # Petitions with an inferred plant are found by plant, never by an empty order.
        (st,) = ol.court_for(self.court, plant_key="stanton")
        self.assertEqual((st["order"], st["case"][:11]), ("", "No. 26-1224"))
        self.assertEqual(ol.court_for(self.court, orders=[""]), [])
        self.assertEqual(len(ol.court_for(self.court, plant_key="schahfer")), 6)
        self.assertEqual(len(ol.court_for(self.court, plant_key="culley")), 6)
        self.assertEqual(len(ol.court_for(self.court, plant_key="craig")), 6)
        self.assertEqual(len(ol.court_for(self.court, plant_key="centralia")), 4)
        # "202-25-3" must not match 202-25-3x orders or the other way round.
        self.assertEqual(ol.court_for([{"order": "202-25-30", "plant_key": "x"}],
                                      orders=["202-25-3"]), [])

    def test_court_overview(self):
        ov = ol.court_overview(self.court, self.rows)
        self.assertEqual(ov, {"petitions": 37, "dockets": 35, "orders_petitioned": PETITIONED,
                              "plant_orders_petitioned": 14, "plant_orders": 35,
                              "petitions_order_not_confirmed": 10,
                              "plants_petitioned": PLANTS_PETITIONED, "status": STATUS,
                              "rulings": 1})
        self.assertEqual(ol.overview_text(ov), OVERVIEW)
        self.assertEqual(ol.overview_text(ol.court_overview([], self.rows)),
                         "Petitions for review found: 0 (0 docket numbers), naming 0 of 35 plant "
                         "orders; 0 name no order in the sources (plant inferred). Plants: none. "
                         "Petition status: none. Court rulings found: 0.")

    def test_missing_court_file(self):
        self.assertEqual(ol.load_court(os.path.join(SKILL, "no_such_file.csv")), [])


class TestCli(unittest.TestCase):
    def test_plant(self):
        code, out = run("plant", "campbell", "--date", "2026-11-08")
        self.assertEqual(code, 0)
        self.assertIn("J.H. Campbell (MI, EIA plant 1710", out)
        self.assertIn("7 orders since 2025-05-23", out)
        self.assertIn("under order 202-26-39, 6 days until its expiry date 2026-11-14", out)
        self.assertIn("Gaps between orders: none.", out)
        self.assertIn("202-25-3  2025-07-24 filed: petition for review, No. 25-1159 (People of the "
                      "State of Michigan v. DOE); status: decided 2026-09-11. Source: https://", out)
        self.assertIn("202-25-7  2025-10-09 filed: petition for review, No. 25-1198 (Sierra Club v. "
                      "DOE); status: abeyance 2026-02-18.", out)
        self.assertIn("202-26-16  2026-06-18 filed: petition for review, case number not found; "
                      "status: not in archive.", out)
        self.assertIn("202-25-3  2026-09-11 decided: vacated, No. 25-1159 (Michigan v. U.S. "
                      "Department of Energy). Source:", out)
        self.assertIn("202-25-3  2026-10-26 filed: rehearing petition by DOE, No. 25-1159", out)
        self.assertIn("202-25-3  2026-11-03 filed: amicus brief supporting rehearing, No. 25-1159",
                      out)
        self.assertIn("says nothing about any other order", out)
        self.assertIn("read on 2026-10-19", out)
        self.assertNotIn("WARNING", out)

    def test_plant_centralia_ninth_circuit(self):
        code, out = run("plant", "centralia", "--date", "2026-11-16")
        self.assertEqual(code, 0)
        self.assertIn("202-25-11  2026-03-03 filed: petition for review, No. 26-1252 (State of "
                      "Washington v. United States Department of Energy); status: briefing "
                      "2026-03-23.", out)
        self.assertIn("(order not confirmed, centralia)  2026-06-11 filed: petition for review, "
                      "No. 26-3781", out)
        self.assertIn("under order 202-26-44, 25 days until its expiry date 2026-12-11", out)
        self.assertNotIn("WARNING", out)

    def test_plant_inferred_rows(self):
        code, out = run("plant", "stanton", "--date", "2026-11-16")
        self.assertEqual(code, 0)
        self.assertIn("(order not confirmed, stanton)  2026-08-27 filed: petition for review, "
                      "No. 26-1224 (Environmental Defense Fund v. DOE); status: no order seen.", out)
        code, out = run("plant", "schahfer", "--date", "2026-11-16")
        self.assertIn("(order not confirmed, schahfer or culley)  2026-06-15 first seen: petition "
                      "for review, No. 26-1158 (Sierra Club v. DOE); status: abeyance 2026-07-28.",
                      out)
        self.assertIn("202-25-12  2026-03-16 filed: petition for review, No. 26-1056", out)
        code, out = run("plant", "wagner", "--date", "2026-11-16")
        self.assertIn("Court actions in the court table: none.", out)

    def test_plant_on_last_day_before_renewal(self):
        code, out = run("plant", "campbell", "--date", "2026-11-14")
        self.assertEqual(code, 0)
        self.assertIn("On 2026-11-14: under order 202-26-39, 0 days until its expiry date "
                      "2026-11-14; next order 202-26-51 (issued 2026-11-13) in force 2026-11-15 "
                      "to 2027-02-12; covered without a break through 2027-02-12.", out)
        self.assertNotIn("no order of this plant in force", out)
        self.assertNotIn("WARNING", out)
        code, out = run("plant", "campbell", "--date", "2026-11-15")
        self.assertIn("On 2026-11-15: under order 202-26-51, 89 days until its expiry date "
                      "2027-02-12.", out)
        self.assertNotIn("WARNING", out)
        code, out = run("plant", "campbell", "--date", "2026-11-17")
        self.assertIn("WARNING: 2026-11-17 is after the table's as-of date (2026-11-16)", out)

    def test_plant_in_gap(self):
        code, out = run("plant", "wagner", "--date", "2026-02-01")
        self.assertEqual(code, 0)
        self.assertIn("On 2026-02-01: no order of this plant in force in the table; next order "
                      "202-26-25 (issued 2026-05-21) starts 2026-05-22.", out)
        code, out = run("plant", "wagner", "--date", "2025-12-01")
        self.assertIn("under order 202-25-6A, 30 days until its expiry date 2025-12-31; next order "
                      "202-26-25 (issued 2026-05-21) in force 2026-05-22 to 2026-08-19; "
                      "141 uncovered day(s) before it starts.", out)

    def test_plant_json(self):
        code, out = run("plant", "Wagner", "--date", "2026-11-09", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        (p,) = res["plants"]
        self.assertEqual((p["plant_key"], p["current_order"], p["current_expiry"],
                          p["days_until_expiry"], len(p["orders"]), len(p["gaps"]), p["court"],
                          p["next_order"], p["covered_through"]),
                         ("wagner", "202-26-25A", "2026-11-17", 8, 4, 1, [], None, "2026-11-17"))
        code, out = run("plant", "1710", "--date", "2026-11-13", "--json")
        (p,) = json.loads(out)["plants"]
        got = [(c["order"], c["action"]) for c in p["court"]]
        self.assertEqual(len(got), 13)
        self.assertEqual(got[:3], [("202-25-3", "petition for review")] * 3)
        self.assertEqual(got[8:], [("202-26-16", "petition for review"),
                                   ("202-26-22", "petition for review"),
                                   ("202-25-3", "vacated"),
                                   ("202-25-3", "rehearing petition by DOE"),
                                   ("202-25-3", "amicus brief supporting rehearing")])
        self.assertEqual([c["status"] for c in p["court"]][:3], ["decided"] * 3)
        self.assertEqual(p["court"][0]["status_date"], "2026-09-11")
        self.assertEqual(p["court"][-1]["status_date"], "")
        self.assertEqual((p["current_order"], p["days_until_expiry"], p["in_force_on_date"],
                          p["next_order"], p["next_effective"], p["covered_through"]),
                         ("202-26-39", 1, True, "202-26-51", "2026-11-15", "2027-02-12"))

    def test_unknown_plant(self):
        code, out = run("plant", "Brandon Shores", "--date", "2026-11-09")
        self.assertEqual(code, 1)
        self.assertIn("No plant under a 202(c) plant order matches", out)

    def test_in_force_after_as_of_warns(self):
        code, out = run("in-force", "--date", "2026-12-01")
        self.assertEqual(code, 0)
        self.assertIn("WARNING: 2026-12-01 is after the table's as-of date (2026-11-16)", out)
        self.assertIn("Plant orders cover 5 plant(s)", out)
        self.assertIn("202-26-51", out)
        for day in ("2026-11-13", "2026-11-14", "2026-11-16"):
            code, out = run("in-force", "--date", day)
            self.assertNotIn("WARNING", out)

    def test_expiring_cli(self):
        code, out = run("expiring", "--date", "2026-11-09", "--days", "14", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual([(o["order"], o["days_until_expiry"]) for o in res["orders"]],
                         [("202-26-25A", 8), ("202-26-40", 11)])
        self.assertIn("Description of past orders only, not a forecast.", res["renewal_note"])
        self.assertIn("Plant renewals in the table: 27.", res["renewal_note"])

    def test_order(self):
        code, out = run("order", "202-25-1e")
        self.assertEqual(code, 0)
        self.assertIn("Next order in the same chain: 202-25-1F.", out)
        self.assertIn("Court actions in the court table: none.", out)
        code, out = run("order", "202-26-39")
        self.assertIn("Next order in the same chain: 202-26-51.", out)
        code, out = run("order", "202-26-51", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual((res["orders"][0]["effective"], res["orders"][0]["expires"],
                          res["next_in_chain"], res["court"]),
                         ("2026-11-15", "2027-02-12", None, []))
        code, out = run("order", "202-26-99")
        self.assertEqual(code, 1)

    def test_order_court(self):
        code, out = run("order", "202-25-3", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["next_in_chain"], "202-25-7")
        self.assertEqual([c["date"] for c in res["court"]],
                         ["2025-07-24", "2025-07-24", "2025-07-25", "2026-09-11", "2026-10-26",
                          "2026-11-03"])
        self.assertEqual([c["date_kind"] for c in res["court"]],
                         ["filed", "filed", "filed", "decided", "filed", "filed"])
        self.assertEqual((res["court_as_of"], res["dockets_read"]), ("2026-11-16", "2026-10-19"))
        self.assertEqual(res["version"], "0.3.1")
        code, out = run("order", "202-25-14", "--json")
        res = json.loads(out)
        self.assertEqual([c["case"] for c in res["court"]],
                         ["No. 26-1059 (State of Colorado v. DOE)", "No. 26-1060 (Sierra Club v. DOE)"])
        self.assertEqual([(c["status"], c["status_date"]) for c in res["court"]],
                         [("abeyance", "2026-06-08")] * 2)
        self.assertEqual(res["next_in_chain"], "202-26-21")

    def test_court_cli(self):
        code, out = run("court")
        self.assertEqual(code, 0)
        self.assertIn("Court actions on 202(c) orders in the court table: 41.", out)
        self.assertIn("https://media.cadc.uscourts.gov/opinions/docs/2026/09/25-1159.pdf", out)
        self.assertIn("https://climate.law.columbia.edu/news/climate-litigation-updates-november-6-2026",
                      out)
        self.assertIn(OVERVIEW, out)
        code, out = run("court", "--json")
        res = json.loads(out)
        self.assertEqual(len(res["court"]), 41)
        self.assertEqual(res["overview"]["orders_petitioned"], PETITIONED)
        self.assertEqual(res["overview"]["status"], STATUS)
        self.assertEqual(sum(1 for c in res["court"] if c["order"] == ""), 10)
        self.assertEqual(res["court"][0]["status_date"], "2026-09-11")

    def test_summary(self):
        code, out = run("summary", "--date", "2026-11-09", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual((res["orders"], res["by_kind"], res["in_force"], res["mw"]["summer_mw"],
                          res["court_actions"], res["orders_vacated"], res["by_year"]),
                         (88, {"plant": 35, "event": 38, "island": 15}, 10, 4849.9, 41, ["202-25-3"],
                          {"2025": 19, "2026": 69}))
        self.assertEqual((res["plant_orders_petitioned"], res["plants_petitioned"],
                          res["orders_petitioned"], res["petitions"], res["dockets"],
                          res["petition_status"]),
                         (14, PLANTS_PETITIONED, PETITIONED, 37, 35, STATUS))
        code, out = run("summary", "--date", "2026-11-09")
        self.assertIn("orders vacated by a court: 202-25-3.", out)
        self.assertIn(OVERVIEW, out)

    def test_bad_date(self):
        code, _ = run("in-force", "--date", "11/09/2026")
        self.assertEqual(code, 2)


class TestSkillDoc(unittest.TestCase):
    def test_skill_md(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("---\nname: doe-202c-orders\n"))
        self.assertIn("\nlicense: Apache-2.0\n", text.split("\n---\n", 1)[0] + "\n")
        self.assertIn("made with AI agents", text)
        self.assertIn(ol.TABLE_AS_OF, text)
        self.assertNotIn("2026-11-08", text)
        self.assertIn("orders_lookup.py %s" % ol.__version__, text)
        self.assertIn("doe_202c_court.csv", text)
        self.assertIn("No. 25-1159", text)
        self.assertIn("No. 26-1252", text)
        self.assertIn("No. 26-1224", text)
        self.assertIn("petitions for review", text)
        self.assertIn("41 court actions (37 petitions for review)", text)
        self.assertIn("37 petitions for review (35 docket numbers)", text)
        self.assertIn("14 of the 35 plant orders", text)
        self.assertIn("414 days", text)
        self.assertNotIn("413 days", text)
        self.assertNotIn("10 of the 35 plant orders", text)
        self.assertIn("19 October 2026", text)
        self.assertIn("RECAP", text)
        self.assertIn("26 October 2026", text)
        self.assertNotIn("reported 30 October", text)
        self.assertIn("202-26-51", text)
        self.assertIn("all 88 orders", text)
        self.assertIn("26 of 27 plant renewals", text)
        self.assertIn("hours necessary to meet the emergency", text)
        for bad in ("git clone", "curl ", "wget ", "pip install", "npx "):
            self.assertNotIn(bad, text)

    def test_readme(self):
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("0.3.1", text)
        self.assertIn("26 October 2026", text)
        self.assertIn("202-26-51", text)
        self.assertIn("26-1252", text)
        self.assertIn("14 of the 35 plant orders", text)
        self.assertIn("414 days", text)
        self.assertIn("37 petitions for review", text)
        self.assertIn("Apache-2.0", text)
        self.assertNotIn("MIT", text)


if __name__ == "__main__":
    unittest.main()
