# Tests for skills/doe-202c-orders (orders_lookup.py 0.2.2, doe_202c_orders.csv,
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
        # No other row carries the dispatch wording note.
        self.assertEqual(sorted(x["order"] for x in self.rows if "hours necessary" in x["note"]),
                         ["202-26-49", "202-26-51"])

    def test_as_of(self):
        newest = max(r["issued"] for r in self.rows)
        self.assertEqual(newest, D(2026, 11, 13))
        self.assertLessEqual(newest, D.fromisoformat(ol.TABLE_AS_OF))
        self.assertEqual(ol.TABLE_AS_OF, "2026-11-14")
        self.assertEqual(ol.COURT_AS_OF, "2026-11-14")
        self.assertEqual(ol.__version__, "0.2.2")

    def test_plants_table(self):
        self.assertEqual(sorted(self.plants), sorted(PLANT_ORDERS_NOV))
        self.assertEqual({r["plant_key"] for r in self.rows if r["kind"] == "plant"},
                         set(self.plants))
        self.assertEqual(self.plants["campbell"]["plant_id_eia"], "1710")
        self.assertEqual(self.plants["stanton"]["summer_mw"], 453.4)

    def test_court_table(self):
        self.assertEqual(len(self.court), 2)
        by_order = {r["order"]: r for r in self.rows}
        for c in self.court:
            self.assertIn(c["order"], by_order)  # every action is on an order in the table
            self.assertEqual(c["plant_key"], by_order[c["order"]]["plant_key"])
            self.assertTrue(c["source"].startswith("https://"), c)
            self.assertIn(c["date_kind"], ("decided", "filed", "reported"))
            self.assertLessEqual(c["date"], D.fromisoformat(ol.COURT_AS_OF))
            self.assertTrue(c["note"], c)
        first, second = self.court
        self.assertEqual((first["order"], first["date"], first["action"], first["case"][:11]),
                         ("202-25-3", D(2026, 9, 11), "vacated", "No. 25-1159"))
        # The vacated order had already expired when the court ruled.
        self.assertLess(by_order["202-25-3"]["expires"], first["date"])
        self.assertEqual((second["date"], second["date_kind"], second["action"]),
                         (D(2026, 10, 26), "filed", "rehearing petition by DOE"))
        # Filed on the 45th day after the decision (FRAP 40, a U.S. agency is a party).
        self.assertEqual((second["date"] - first["date"]).days, 45)
        self.assertIn("climate.law.columbia.edu", second["source"])
        self.assertIn("publicpower.org", second["note"])  # the earlier report is still cited
        self.assertIn("as of 2026-11-14", second["note"])


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

    def test_in_force_november(self):
        for day in (D(2026, 11, 8), D(2026, 11, 9), D(2026, 11, 13), D(2026, 11, 14)):
            sel = ol.in_force(self.rows, day)
            self.assertEqual(len(sel), 10, day)
            self.assertEqual({r["plant_key"]: r["order"] for r in sel if r["kind"] == "plant"},
                             PLANT_ORDERS_NOV)
            self.assertEqual(sorted(r["order"] for r in sel if r["kind"] == "island"),
                             ["202-25-1F", "202-25-2F"])
            self.assertEqual([r for r in sel if r["kind"] == "event"], [])
        # From 15 November Campbell is under 202-26-51; nothing else changes that day.
        sel = ol.in_force(self.rows, D(2026, 11, 15))
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
        # Campbell's 202-26-39 now has a successor in the table, so it is no longer listed.
        got = [(r["order"], left) for r, left in ol.expiring(self.rows, D(2026, 11, 9), 14)]
        self.assertEqual(got, [("202-26-25A", 8), ("202-26-40", 11)])
        self.assertEqual(len(ol.expiring(self.rows, D(2026, 11, 9), 30)), 3)
        got = [(r["order"], left) for r, left in ol.expiring(self.rows, D(2026, 11, 14), 7)]
        self.assertEqual(got, [("202-26-25A", 3), ("202-26-40", 6)])
        # PREPA's 1E/2E expire 7 November but 1F/2F follow in the table; Guam's 202-26-38 does not.
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
        self.assertEqual(c["current"]["order"], "202-26-51")  # latest in the table
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
        # From the first order, Campbell is covered without a break through the newest expiry.
        self.assertEqual(ol.plant_status(camp, D(2025, 5, 23))["covered_through"], D(2027, 2, 12))
        wag = ol.chain(self.rows, "wagner")["orders"]
        st = ol.plant_status(wag, D(2026, 2, 1))  # inside Wagner's 141-day gap
        self.assertEqual((st["current"], st["next"]["order"], st["covered_through"]),
                         (None, "202-26-25", None))
        st = ol.plant_status(wag, D(2025, 12, 1))  # coverage stops at the gap
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
        self.assertEqual(len(ol.court_for(self.court, orders=["202-25-3"])), 2)
        self.assertEqual(len(ol.court_for(self.court, plant_key="campbell")), 2)
        self.assertEqual(ol.court_for(self.court, orders=["202-26-39"]), [])
        self.assertEqual(ol.court_for(self.court, orders=["202-26-51"]), [])
        self.assertEqual(ol.court_for(self.court, plant_key="eddystone"), [])
        # "202-25-3" must not match 202-25-3x orders or the other way round.
        self.assertEqual(ol.court_for([{"order": "202-25-30", "plant_key": "x"}],
                                      orders=["202-25-3"]), [])

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
        self.assertIn("202-25-3  2026-09-11 decided: vacated, No. 25-1159", out)
        self.assertIn("202-25-3  2026-10-26 filed: rehearing petition by DOE, No. 25-1159", out)
        self.assertIn("says nothing about any other order", out)
        self.assertNotIn("WARNING", out)

    def test_plant_on_last_day_before_renewal(self):
        # Regression: a renewal issued before it starts must not hide the order still in force.
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
        self.assertIn("WARNING: 2026-11-15 is after the table's as-of date (2026-11-14)", out)

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
        self.assertEqual([(c["order"], c["action"]) for c in p["court"]],
                         [("202-25-3", "vacated"), ("202-25-3", "rehearing petition by DOE")])
        # The vacatur changes nothing in the in-force dates: 202-26-39 is still current, and the
        # renewal issued that day is the next order, not the current one.
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
        self.assertIn("WARNING: 2026-12-01 is after the table's as-of date (2026-11-14)", out)
        # Wagner, Eddystone and Stanton have expired in the table by then; Campbell is renewed.
        self.assertIn("Plant orders cover 5 plant(s)", out)
        self.assertIn("202-26-51", out)
        for day in ("2026-11-13", "2026-11-14"):
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
        self.assertEqual([c["date"] for c in res["court"]], ["2026-09-11", "2026-10-26"])
        self.assertEqual([c["date_kind"] for c in res["court"]], ["decided", "filed"])
        self.assertEqual(res["court_as_of"], "2026-11-14")
        self.assertEqual(res["version"], "0.2.2")

    def test_court_cli(self):
        code, out = run("court")
        self.assertEqual(code, 0)
        self.assertIn("Court actions on 202(c) orders in the court table: 2.", out)
        self.assertIn("https://media.cadc.uscourts.gov/opinions/docs/2026/09/25-1159.pdf", out)
        self.assertIn("https://climate.law.columbia.edu/news/climate-litigation-updates-november-6-2026",
                      out)
        code, out = run("court", "--json")
        self.assertEqual(len(json.loads(out)["court"]), 2)

    def test_summary(self):
        code, out = run("summary", "--date", "2026-11-09", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual((res["orders"], res["by_kind"], res["in_force"], res["mw"]["summer_mw"],
                          res["court_actions"], res["orders_vacated"], res["by_year"]),
                         (88, {"plant": 35, "event": 38, "island": 15}, 10, 4849.9, 2, ["202-25-3"],
                          {"2025": 19, "2026": 69}))
        code, out = run("summary", "--date", "2026-11-09")
        self.assertIn("orders vacated by a court: 202-25-3.", out)

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
        self.assertIn("0.2.2", text)
        self.assertIn("26 October 2026", text)
        self.assertIn("202-26-51", text)
        self.assertIn("Apache-2.0", text)
        self.assertNotIn("MIT", text)


if __name__ == "__main__":
    unittest.main()
